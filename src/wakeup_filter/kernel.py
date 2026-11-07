"""Per-bin binding to the wake-up-overshoot C++ kernel (``experiment/engine.exe``).

Stdlib only. The binary protocol follows ``experiment/engine.py``
(``run``) and ``experiment/engine.cpp`` (``gaussian``). Each call runs
``engine.exe`` on one bin and carries the engine's ``(theta, V)``
posterior to the next call. Batch and streaming runs therefore give
the same trace; ``scripts/smoke_end_to_end.py`` checks this.

Files: the source repo is only read. The binary input and output go
to a skeleton-side work directory, never to the source repo.

Overshoot rule (the source repo has no online flag; this is the
backend's definition, pending HW confirmation): a wake bin is a bin with
at least one event, preceded by at least ``SILENCE_TRIGGER_S`` seconds
of empty bins. The bin is flagged when the post-wake prediction (the
prediction for the next bin, after this bin's update) exceeds the
observed rate of the wake bin. The 5 s trigger is the shortest silence
length in the synthetic grid (``experiment/config.py`` LENGTHS).
"""

from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import tempfile
from pathlib import Path

from .interfaces import BIN_WIDTHS_MS, BinUpdate, FilterResult, FilterState

PROTOCOL_GAUSSIAN = 202610211
METHODS = ["E", "I", "E_cap", "I_cap", "OU_I"]  # same order as experiment/config.py
SILENCE_TRIGGER_S = 5.0
LOG_10 = math.log(10.0)
TRACE_COLUMNS = 10
SUMMARY_DOUBLES = 12


def region_for_kappa(kappa):
    """Map a crossing index to a region with the rule used in theory_regions.json."""
    if kappa is None:
        return "unclassified"
    if kappa >= LOG_10:
        return "crossing"
    if kappa <= -LOG_10:
        return "no-crossing"
    return "transition"


class KernelBackend:
    """Frozen-configuration kernel with per-bin state. Register with ``set_backend``."""

    def __init__(self, filter_repo, workdir=None):
        exp = Path(filter_repo).resolve() / "experiment"
        self.engine = exp / "engine.exe"
        if not self.engine.is_file():
            raise FileNotFoundError(f"engine binary not found: {self.engine} (build it first)")
        params = json.loads((exp / "frozen_params.json").read_text(encoding="utf-8"))
        self.initial_theta = float(params["initial_theta"])
        self.initial_V = float(params["initial_V"])
        self._selected = {
            (r["method"], round(float(r["dt"]), 6)): r for r in params["selected"]
        }
        self.workdir = Path(workdir or tempfile.mkdtemp(prefix="wakeup_kernel_")).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._calls = 0

    def frozen(self, method, bin_width_ms):
        """Return the frozen configuration for one (method, bin width)."""
        if bin_width_ms not in BIN_WIDTHS_MS:
            raise ValueError(f"bin width {bin_width_ms} ms not in {BIN_WIDTHS_MS}")
        if method not in METHODS:
            raise ValueError(f"unknown method {method!r}")
        key = (method, round(bin_width_ms / 1000.0, 6))
        if key not in self._selected:
            raise KeyError(f"no frozen configuration for {key}")
        return self._selected[key]

    def _call_engine(self, method, dt, theta, V, counts):
        """Run engine.exe on one bin. Returns (tp, theta_post, V_post)."""
        cfg = self.frozen_by_dt(method, dt)
        self._calls += 1
        stem = self.workdir / f"call_{os.getpid()}_{self._calls}"
        inp, out = stem.with_suffix(".in"), stem.with_suffix(".out")
        with inp.open("xb") as f:
            # 6 int32 header, 4 doubles: dt, theta, V, maxtruth. Then counts, truth, configs.
            f.write(struct.pack("<6i4d", PROTOCOL_GAUSSIAN, 1, 1, 0, 1, -1, dt, theta, V, 0.0))
            f.write(struct.pack("<i", int(counts)))
            f.write(struct.pack("<d", -1.0))
            f.write(struct.pack("<i4d", METHODS.index(method), float(cfg["qc"]),
                                float(cfg["cap"]), float(cfg["mu"]), float(cfg["kappa"])))
        try:
            proc = subprocess.run([str(self.engine), str(inp), str(out)],
                                  capture_output=True, cwd=str(self.engine.parent))
            if proc.returncode or proc.stdout or proc.stderr:
                raise RuntimeError(
                    f"engine.exe failed (rc={proc.returncode}): {proc.stderr.decode(errors='replace')}"
                )
            raw = out.read_bytes()
        finally:
            inp.unlink(missing_ok=True)
            out.unlink(missing_ok=True)
        width = SUMMARY_DOUBLES + TRACE_COLUMNS
        expected = width * 8
        if len(raw) != expected:
            raise ValueError(f"engine output length {len(raw)} != {expected}")
        vals = struct.unpack(f"<{width}d", raw)
        trace = vals[SUMMARY_DOUBLES:]
        tp, v_pred = trace[0], trace[1]
        theta_post, V_post = trace[4], trace[5]
        if not all(math.isfinite(x) for x in (tp, theta_post, V_post)) or V_post < 0:
            raise ValueError("engine returned a non-finite state")
        return tp, theta_post, V_post, cfg

    def frozen_by_dt(self, method, dt):
        return self.frozen(method, int(round(dt * 1000)))

    def update(self, state: FilterState, upd: BinUpdate) -> FilterResult:
        """Advance one bin, judge overshoot, and update ``state`` in place."""
        if upd.event_count < 0:
            raise ValueError("negative event count")
        method = state.config.method
        width = state.config.bin_width_ms
        dt = width / 1000.0
        theta = self.initial_theta if state.theta is None else state.theta
        V = self.initial_V if state.V is None else state.V
        tp, theta_post, V_post, cfg = self._call_engine(method, dt, theta, V, upd.event_count)

        predicted = math.exp(tp)
        # Next-bin prediction. Method OU_I mean-reverts toward mu; the others use theta.
        if method == "OU_I":
            rho = math.exp(-float(cfg["kappa"]) * dt)
            next_tp = float(cfg["mu"]) + rho * (theta_post - float(cfg["mu"]))
        else:
            next_tp = theta_post
        post_wake_prediction = math.exp(next_tp)
        # Overshoot: at a wake bin (events after >= SILENCE_TRIGGER_S of silence),
        # the post-wake prediction for the next bin exceeds the observed rate of the wake bin.
        overshoot = (
            upd.event_count > 0
            and state.silent_seconds >= SILENCE_TRIGGER_S
            and post_wake_prediction > upd.observed_rate
        )
        state.theta = theta_post
        state.V = V_post
        state.predicted_rate = post_wake_prediction
        state.silent_seconds = 0.0 if upd.event_count > 0 else state.silent_seconds + dt
        return FilterResult(
            predicted_rate=predicted,
            overshoot=overshoot,
            region=region_for_kappa(state.config.kappa),
        )


def register(filter_repo, workdir=None):
    """Create a backend and register its ``update`` as the wake-up filter backend."""
    from .interfaces import set_backend

    backend = KernelBackend(filter_repo, workdir=workdir)
    set_backend(backend.update)
    return backend
