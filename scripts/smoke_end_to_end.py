"""End-to-end smoke test: one full 300 s period over synthetic data.

Run from the repository root with the baseline venv:

    /projects/sandbox/.venv-baseline/bin/python scripts/smoke_end_to_end.py

Steps:
1. Read paths from config/local.yaml.
2. Generate synthetic ANPR events with the source repo's public generator.
   Output goes to outputs/, not to the source repo.
3. Fit the synthetic-only ANPR forecaster (public functions, synthetic data).
4. Build a synthetic point-event stream. The 29 warm-up periods have
   background traffic. The target period has a 60 s silence, then a burst.
5. Run run_event_loop over the stream and check the target period's output.
6. Check the filter stream against one batch kernel call.

All outputs are labelled synthetic. Nothing here is a result of the paper.
The run summary goes to outputs/smoke/last_run.json.
"""

from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from anpr_forecast.interfaces import PERIOD_SECONDS, SEQUENCE_LENGTH  # noqa: E402
from anpr_forecast.synthetic import (  # noqa: E402
    SyntheticForecaster,
    generate_synthetic_events,
    to_features,
)
from orchestrator.interfaces import AppConfig, Event  # noqa: E402
from orchestrator.pipeline import run_event_loop  # noqa: E402
from wakeup_filter import kernel  # noqa: E402
from wakeup_filter.interfaces import BinUpdate, FilterConfig, FilterState  # noqa: E402

BASE_RATE_PER_S = 4.0  # background synthetic traffic, events per second
SILENCE_START_S = 120  # offsets inside the target period
SILENCE_END_S = 180
BURST_RATE_PER_S = 20.0
SEED = 2026
BIN_MS = 1000
METHOD = "E"


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    return bool(ok)


def point_events_ms(warm_start, n_periods, rng):
    """Synthetic Poisson point events (epoch ms), sorted.

    Every period has background traffic. The last period (the target) has
    a silence from SILENCE_START_S to SILENCE_END_S, then a burst.
    """
    target_start = warm_start + (n_periods - 1) * PERIOD_SECONDS
    times = []
    for period in range(n_periods):
        p0 = warm_start + period * PERIOD_SECONDS
        if p0 == target_start:
            segments = [(0, SILENCE_START_S, BASE_RATE_PER_S),
                        (SILENCE_START_S, SILENCE_END_S, 0.0),
                        (SILENCE_END_S, PERIOD_SECONDS, BURST_RATE_PER_S)]
        else:
            segments = [(0, PERIOD_SECONDS, BASE_RATE_PER_S)]
        for a, b, rate in segments:
            if rate <= 0:
                continue
            n = rng.poisson(rate * (b - a))
            times.extend(rng.uniform(p0 + a, p0 + b, size=n))
    return sorted(int(t * 1000) for t in times)


def batch_predictions(engine, work, counts, theta0, V0, cfg, width_ms):
    """Run the kernel once over all bins and return the prior prediction per bin."""
    dt = width_ms / 1000.0
    n = len(counts)
    work.mkdir(parents=True, exist_ok=True)
    inp, out = work / "batch.in", work / "batch.out"
    with inp.open("wb") as f:
        f.write(struct.pack("<6i4d", kernel.PROTOCOL_GAUSSIAN, n, 1, 0, 1, -1, dt, theta0, V0, 0.0))
        f.write(struct.pack(f"<{n}i", *counts))
        f.write(struct.pack(f"<{n}d", *([-1.0] * n)))
        f.write(struct.pack("<i4d", kernel.METHODS.index(METHOD), float(cfg["qc"]),
                            float(cfg["cap"]), float(cfg["mu"]), float(cfg["kappa"])))
    subprocess.run([str(engine), str(inp), str(out)], check=True, capture_output=True)
    vals = struct.unpack(f"<{12 + 10 * n}d", out.read_bytes())
    return [math.exp(vals[12 + 10 * k]) for k in range(n)]


def main():
    cfg_file = yaml.safe_load((ROOT / "config" / "local.yaml").read_text(encoding="utf-8"))
    anpr_repo = cfg_file["paths"]["anpr_repo"]
    filter_repo = cfg_file["paths"]["filter_repo"]
    out_dir = ROOT / "outputs" / "smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"labels": "synthetic only; not the paper's results"}
    all_ok = True

    # ANPR: generate, fit, register.
    events_dir = ROOT / "outputs" / "synthetic" / "anpr" / "events"
    generate_synthetic_events(anpr_repo, events_dir, n_events=30000, seed=42)
    forecaster = SyntheticForecaster(
        anpr_repo, events_dir, ROOT / "outputs" / "synthetic" / "anpr" / "model",
        seed=42, max_epochs=5,
    ).fit()
    forecaster.register()
    results["anpr_val_summary"] = forecaster.val_summary
    results["anpr_test_summary"] = forecaster.test_summary

    # Filter: register the kernel backend.
    kernel_dir = ROOT / "outputs" / "wakeup" / "kernel_work"
    backend = kernel.register(filter_repo, workdir=kernel_dir)

    # Target period: the 85th percentile boundary, so 29 earlier rows exist.
    boundaries = sorted(forecaster.feature_rows)
    target = boundaries[int(0.85 * len(boundaries))]
    warm_start = target - (SEQUENCE_LENGTH - 1) * PERIOD_SECONDS
    n_periods = SEQUENCE_LENGTH  # 29 warm-up + the target
    rng = np.random.default_rng(SEED)

    # Event stream: feature rows at boundaries, merged with point events in time order.
    rows = [
        Event(kind="anpr_observation", timestamp=b,
              payload={"features": to_features(forecaster.feature_rows[b])})
        for b in range(warm_start, target + PERIOD_SECONDS + 1, PERIOD_SECONDS)
        if b in forecaster.feature_rows
    ]
    points = [Event(kind="point_event", timestamp=t) for t in point_events_ms(warm_start, n_periods, rng)]
    stream = []
    i = 0
    for p in points:
        while i < len(rows) and rows[i].timestamp * 1000 <= p.timestamp:
            stream.append(rows[i])
            i += 1
        stream.append(p)
    stream.extend(rows[i:])

    run_cfg = AppConfig(
        anpr_repo=anpr_repo, filter_repo=filter_repo,
        anpr_dir="", binance_raw=cfg_file["data"]["binance_raw"],
        log_dir=str(out_dir / "logs"), publish_on_fallback=False,
        filter_method=METHOD, bin_width_ms=BIN_MS, event_source="synthetic",
    )
    log_path = Path(run_cfg.log_dir) / "monitor.jsonl"
    if log_path.exists():
        log_path.unlink()

    outputs = list(run_event_loop(run_cfg, stream))
    target_out = [o for o in outputs if o.period_start == target]
    results["n_events"] = len(stream)
    results["n_outputs"] = len(outputs)
    results["target_period_start"] = target

    all_ok &= check("exactly one output for the target period", len(target_out) == 1,
                    f"{len(target_out)} for period {target}")
    if target_out:
        o = target_out[0]
        all_ok &= check("output spans one 300 s period", o.period_end - o.period_start == PERIOD_SECONDS)
        all_ok &= check("output is labelled synthetic", "synthetic" in o.provenance, o.provenance)
        if o.published:
            all_ok &= check("published interval is finite and ordered",
                            math.isfinite(o.interval_low) and math.isfinite(o.interval_high)
                            and o.interval_low <= o.interval_high,
                            f"[{o.interval_low:.2f}, {o.interval_high:.2f}]")
        else:
            all_ok &= check("no interval published (gate fell back, publish_on_fallback off)",
                            o.interval_low is None and o.interval_high is None)
        results["target_output"] = o.__dict__
    all_ok &= check("monitor log has one line per closed period",
                    log_path.exists() and sum(1 for _ in log_path.open(encoding="utf-8")) == len(outputs))

    # Filter stream vs one batch kernel call on the same bins.
    t_start = warm_start * 1000
    n_bins = (target + PERIOD_SECONDS) * 1000 // BIN_MS - t_start // BIN_MS
    times_ms = np.array([e.timestamp for e in points])
    idx = ((times_ms - t_start) // BIN_MS).astype(int)
    counts = np.bincount(idx, minlength=n_bins).astype(int).tolist()
    state = FilterState(config=FilterConfig(method=METHOD, bin_width_ms=BIN_MS), predicted_rate=0.0)
    stream_pred = []
    for k, c in enumerate(counts):
        r = backend.update(state, BinUpdate(bin_start=t_start + k * BIN_MS, event_count=c,
                                            observed_rate=c / (BIN_MS / 1000.0)))
        stream_pred.append(r.predicted_rate)
    batch_pred = batch_predictions(
        Path(filter_repo) / "experiment" / "engine.exe", kernel_dir / "batch",
        counts, backend.initial_theta, backend.initial_V, backend.frozen(METHOD, BIN_MS), BIN_MS,
    )
    worst = max(abs(a - b) / b for a, b in zip(stream_pred, batch_pred))
    all_ok &= check("filter stream matches one batch kernel call", worst == 0.0,
                    f"worst relative difference {worst}")
    results["stream_vs_batch_worst_rel_diff"] = worst
    results["all_passed"] = bool(all_ok)
    (out_dir / "last_run.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print("RESULT:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
