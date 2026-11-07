"""Synthetic-only ANPR forecaster built on the public source-repo code.

This is NOT the paper's frozen evaluation path. The frozen path needs
the paper's record counts (``experiment_config.yaml`` expected_split),
which synthetic data cannot reach, so ``experiment_runner.py prepare``
stops at its count check. This backend calls the public functions
directly (``load_matched_data``, ``compute_rolling_features``,
``create_trajectory_indexed_dataset``, ``train_density_model``,
``predict_density``, ``truncated_mixture_quantile``) and fits a
snapshot mixture density network on synthetic events only.

Every output carries ``PROVENANCE``. No number produced here is a
result of the paper.

Gate. The public code computes its gate inputs from the last feature
row: ``R_comp`` (column 2) and ``bar_y / 300`` (column 3 / 300). This
backend uses the same computation and names the second input
``bar_y_over_300``. It does not call it the in-transit ratio, because
the in-transit definition is pending HW confirmation (``docs/wiring.md``
section 2).

Thresholds are picked on validation trips only. The rule: the highest
publication rate whose validation coverage is at least 0.90. If no
threshold pair reaches 0.90, the gate falls back to the training prior
for every period.

numpy, pandas, scikit-learn and torch are used only by this module.
The interface modules stay stdlib-only.
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .interfaces import (
    PERIOD_SECONDS,
    SEQUENCE_LENGTH,
    AvailabilityFeatures,
    ForecastRequest,
    ForecastResult,
    GateDecision,
    set_predictor,
)

PROVENANCE = "synthetic-only; not the paper's frozen path"
DELTA_OBS_MIN = 5
WINDOW_WIDTH_MIN = 30
COVERAGE_TARGET = 0.90
Z_90_HALF = 1.6448536269514722  # standard normal 0.95 quantile, for the 90% prior interval
QR_GRID = (0.0, 0.1, 0.2, 0.3, 0.5)  # quantiles of R_comp used as the publish floor
QRHO_GRID = (0.5, 0.7, 0.9, 1.0)  # quantiles of bar_y/300 used as the publish ceiling
NUM_MIXTURES = 3
NAN = float("nan")


def _import_public(anpr_repo):
    """Import the public modules from the source repo without writing bytecode into it."""
    sys.dont_write_bytecode = True
    repo = str(Path(anpr_repo).resolve())
    if repo not in sys.path:
        sys.path.insert(0, repo)
    import data_processing
    import forecast_models
    import probabilistic_metrics

    return data_processing, forecast_models, probabilistic_metrics


def generate_synthetic_events(anpr_repo, out_dir, n_events=30000, seed=42):
    """Run the public synthetic generator with its output directory set.

    The generator writes into ``out_dir``, so nothing is written into the
    source repo. Returns the upstream and downstream CSV paths.
    """
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    script = Path(anpr_repo).resolve() / "examples" / "generate_synthetic_events.py"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run(
        [sys.executable, str(script), "--output-dir", str(out),
         "--n-events", str(n_events), "--seed", str(seed)],
        check=True, env=env, cwd=str(out), capture_output=True, text=True,
    )
    return out / "upstream_events.csv", out / "downstream_events.csv"


def to_features(vec):
    """Map one public 14-dim row to the skeleton's AvailabilityFeatures.

    Named fields come from the public columns they match. ``rho_t`` and the
    two encodings are NaN: the public code has no in-transit column and no
    spatial encoding.
    """
    v = tuple(float(x) for x in vec)
    return AvailabilityFeatures(
        r_comp=v[2], rho_t=NAN, mean=v[3], variance=v[4],
        time_code=NAN, space_code=NAN, extra=v,
    )


class SyntheticForecaster:
    """Fit on synthetic events; serve ``predict`` for one period at a time."""

    def __init__(self, anpr_repo, events_dir, workdir, seed=42, max_epochs=5, hidden_dim=64):
        self.anpr_repo = str(Path(anpr_repo).resolve())
        self.upstream_csv = Path(events_dir).resolve() / "upstream_events.csv"
        self.downstream_csv = Path(events_dir).resolve() / "downstream_events.csv"
        self.workdir = Path(workdir).resolve()
        self.seed = seed
        self.max_epochs = max_epochs
        self.hidden_dim = hidden_dim
        self.fitted = False

    def fit(self):
        dp, fm, pm = _import_public(self.anpr_repo)
        from sklearn.preprocessing import MinMaxScaler

        config = {
            "data": {
                "plate1_path": str(self.upstream_csv),
                "plate2_path": str(self.downstream_csv),
                "camera_up": ["UPSTREAM_CAMERA_ID"],
                "camera_down": ["DOWNSTREAM_CAMERA_ID"],
                "delta_obs": DELTA_OBS_MIN,
                "window_width": WINDOW_WIDTH_MIN,
            },
        }
        t_up, _t_down, merged = dp.load_matched_data(config)
        grid_start = t_up["timestamp_up"].min().floor(f"{DELTA_OBS_MIN}min")
        aligned_df, aligned_times = dp._aligned_sample_frame(
            merged, grid_start, DELTA_OBS_MIN, SEQUENCE_LENGTH
        )
        # Same provisional split as load_and_preprocess_data (data_processing.py),
        # used only to take the train-split median and variance.
        codes, _ = pd.factorize(pd.to_datetime(aligned_times), sort=False)
        provisional = pd.DataFrame({
            "case_id": np.arange(len(aligned_df), dtype=np.int64),
            "update_period_id": codes.astype(np.int64),
            "prediction_time": pd.to_datetime(aligned_times).to_numpy(),
        })
        bounds = dp.complete_period_split_boundaries(provisional, 0.7, 0.15, 0.15)
        train_tt = aligned_df.iloc[: bounds["train_end"]]["travel_time"].values
        mu_default = float(np.median(train_tt))
        s2_default = float(np.var(train_tt, ddof=1))

        feature_df = dp.compute_rolling_features(
            t_up, merged, DELTA_OBS_MIN, WINDOW_WIDTH_MIN,
            mu_default=mu_default, s2_default=s2_default,
        )
        if feature_df.shape[1] != 14:
            raise ValueError(f"expected 14 feature columns, got {feature_df.shape[1]}")
        X, y, metadata = dp.create_trajectory_indexed_dataset(
            merged, feature_df, DELTA_OBS_MIN, SEQUENCE_LENGTH, return_metadata=True
        )
        X = X.numpy().astype(float)
        y = y.numpy().astype(float)
        X_tr, X_va, X_te, y_tr, y_va, y_te, _meta, _b = dp.split_time_series_data_by_period(
            X, y, metadata, 0.7, 0.15, 0.15
        )
        # Public feature rows, keyed by epoch seconds (grid is UTC-naive, as in the source code).
        self.feature_rows = {
            int(ts.value // 10**9): tuple(float(x) for x in row)
            for ts, row in zip(feature_df.index, feature_df.values)
        }

        X_tr_s, X_va_s, X_te_s, x_scaler = dp.fit_scaler_on_train_only(X_tr, X_va, X_te)
        y_scaler = MinMaxScaler(feature_range=(0, 1)).fit(y_tr.reshape(-1, 1))
        y_tr_s = y_scaler.transform(y_tr.reshape(-1, 1)).ravel()
        y_va_s = y_scaler.transform(y_va.reshape(-1, 1)).ravel()

        self.workdir.mkdir(parents=True, exist_ok=True)
        spec = dict(
            family="snapshot", hidden_dim=self.hidden_dim, num_layers=1,
            learning_rate=1e-3, weight_decay=1e-4, history_length=SEQUENCE_LENGTH,
            config_id="synthetic_snapshot",
        )
        self.model, _details = fm.train_density_model(
            X_tr_s, y_tr_s, X_va_s, y_va_s, spec, NUM_MIXTURES, self.seed,
            self.workdir / "synthetic_snapshot.pth",
            max_epochs=self.max_epochs, min_epochs=1, patience=2,
            batch_size=128, min_delta=1e-4,
        )
        self.x_scaler = x_scaler
        self.y_scaler = y_scaler
        self._fm, self._pm = fm, pm

        # Prior: Normal(mean, sd) of training travel times, as in ap06 (sd with ddof=1).
        self.prior_mu = float(y_tr.mean())
        self.prior_sd = float(y_tr.std(ddof=1))

        # Gate and thresholds on validation trips only.
        lo_va, hi_va = self._interval_seconds(X_va_s)
        inside_va = (y_va >= lo_va) & (y_va <= hi_va)
        prior_lo, prior_hi = self._prior_bounds()
        prior_inside_va = (y_va >= prior_lo) & (y_va <= prior_hi)
        R_va = X_va[:, -1, 2]
        rho_va = X_va[:, -1, 3] / 300.0  # bar_y_over_300 (see module docstring)
        self.policy = self._select_policy(R_va, rho_va, inside_va)
        self.prior_coverage_val = float(prior_inside_va.mean())
        if self.policy["mode"] == "fallback_only":
            self.policy["coverage_val"] = self.prior_coverage_val

        # Held-out synthetic test, reported only; the thresholds above never see it.
        lo_te, hi_te = self._interval_seconds(X_te_s)
        inside_te = (y_te >= lo_te) & (y_te <= hi_te)
        R_te = X_te[:, -1, 2]
        rho_te = X_te[:, -1, 3] / 300.0
        pub_te = self._publish_mask(R_te, rho_te)
        self.test_summary = dict(
            provenance=PROVENANCE,
            publish_rate=float(pub_te.mean()),
            coverage_published=float(inside_te[pub_te].mean()) if pub_te.any() else None,
            mean_width_published_s=float((hi_te - lo_te)[pub_te].mean()) if pub_te.any() else None,
            prior_coverage=float(((y_te >= prior_lo) & (y_te <= prior_hi)).mean()),
            n_test_trips=int(len(y_te)),
        )
        self.val_summary = dict(
            provenance=PROVENANCE,
            n_val_trips=int(len(y_va)),
            model_coverage_all_val=float(inside_va.mean()),
            prior_coverage_val=self.prior_coverage_val,
            policy=self.policy,
        )
        self.fitted = True
        return self

    def _interval_seconds(self, X_scaled):
        pis, mus, sig = self._mixture_raw(X_scaled)
        lo = self._pm.truncated_mixture_quantile(pis, mus, sig, 0.05)
        hi = self._pm.truncated_mixture_quantile(pis, mus, sig, 0.95)
        return np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)

    def _mixture_raw(self, X_scaled):
        pis, mus, sig = self._fm.predict_density(self.model, X_scaled)
        mus_raw = self.y_scaler.inverse_transform(mus.reshape(-1, 1)).reshape(mus.shape)
        sig_raw = sig / float(self.y_scaler.scale_[0])
        return pis, mus_raw, sig_raw

    def _prior_bounds(self):
        return (self.prior_mu - Z_90_HALF * self.prior_sd,
                self.prior_mu + Z_90_HALF * self.prior_sd)

    def _publish_mask(self, R, rho):
        p = self.policy
        if p["mode"] != "gate":
            return np.zeros(len(R), dtype=bool)
        return (R >= p["R_low"]) & (rho <= p["rho_high"])

    @staticmethod
    def _select_policy(R, rho, inside):
        best = None
        for qr in QR_GRID:
            r_low = float(np.quantile(R, qr))
            for qrho in QRHO_GRID:
                rho_high = float(np.quantile(rho, qrho))
                pub = (R >= r_low) & (rho <= rho_high)
                if not pub.any():
                    continue
                cov = float(inside[pub].mean())
                rate = float(pub.mean())
                if cov >= COVERAGE_TARGET and (
                    best is None or (rate, cov) > (best["publish_rate_val"], best["coverage_val"])
                ):
                    best = dict(q_R=qr, q_rho=qrho, R_low=r_low, rho_high=rho_high,
                                publish_rate_val=rate, coverage_val=cov)
        if best is None:
            return dict(mode="fallback_only", coverage_target=COVERAGE_TARGET)
        best["mode"] = "gate"
        best["coverage_target"] = COVERAGE_TARGET
        return best

    def period_request(self, period_start, history_len=SEQUENCE_LENGTH - 1):
        """Build the ForecastRequest for one period from the public feature rows."""
        if not self.fitted:
            raise RuntimeError("fit() before building requests")
        t = int(period_start)
        if t not in self.feature_rows:
            raise KeyError(f"no feature row at {t}")
        history = []
        for k in range(history_len, 0, -1):
            key = t - k * PERIOD_SECONDS
            if key in self.feature_rows:
                history.append(to_features(self.feature_rows[key]))
        return ForecastRequest(
            period_start=t, period_end=t + PERIOD_SECONDS,
            features=to_features(self.feature_rows[t]), history=tuple(history),
        )

    def predict(self, request):
        """Forecast one period and gate it. Outputs are labelled synthetic."""
        if not self.fitted:
            raise RuntimeError("fit() before predict()")
        rows = list(request.history) + [request.features]
        if len(rows) < SEQUENCE_LENGTH:
            return self._fallback(request, f"insufficient history: {len(rows)} of {SEQUENCE_LENGTH} rows")
        vectors = [tuple(r.extra) for r in rows[-SEQUENCE_LENGTH:]]
        if any(len(v) != 14 for v in vectors):
            raise ValueError("each feature row needs the 14-dim vector in extra")
        X = np.asarray(vectors, dtype=float)[None, :, :]
        X_s = self.x_scaler.transform(X.reshape(-1, 14)).reshape(1, SEQUENCE_LENGTH, 14)
        pis, mus, sig = self._mixture_raw(X_s)
        quantiles = {
            p: float(np.asarray(self._pm.truncated_mixture_quantile(pis, mus, sig, p))[0])
            for p in (0.05, 0.5, 0.95)
        }
        current = vectors[-1]
        R = current[2]
        rho = current[3] / 300.0  # bar_y_over_300 (see module docstring)
        publish = (
            self.policy["mode"] == "gate"
            and R >= self.policy["R_low"]
            and rho <= self.policy["rho_high"]
        )
        if not publish:
            return self._fallback(request, "gate closed")
        result = ForecastResult(
            quantiles=quantiles, interval_low=quantiles[0.05],
            interval_high=quantiles[0.95], provenance=PROVENANCE,
        )
        return result, GateDecision(publish=True, fallback=False,
                                    coverage=float(self.policy["coverage_val"]))

    def _fallback(self, request, reason):
        lo, hi = self._prior_bounds()
        q = {0.05: lo, 0.5: self.prior_mu, 0.95: hi}
        result = ForecastResult(
            quantiles=q, interval_low=lo, interval_high=hi,
            provenance=f"{PROVENANCE}; fallback prior ({reason})",
        )
        return result, GateDecision(publish=False, fallback=True,
                                    coverage=float(self.prior_coverage_val))

    def register(self):
        """Make this forecaster the backend of ``anpr_forecast.interfaces.predict``."""
        set_predictor(self.predict)
        return self
