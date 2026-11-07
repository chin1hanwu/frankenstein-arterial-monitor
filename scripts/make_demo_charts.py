"""Draw the three demo charts from the smoke-test run. All charts are SYNTHETIC ONLY.

Run after scripts/smoke_end_to_end.py:

    /projects/sandbox/.venv-baseline/bin/python scripts/make_demo_charts.py

Inputs (all written by the smoke test or the synthetic generator):
- outputs/smoke/last_run.json          target period output and summaries
- outputs/smoke/logs/monitor.jsonl     one line per closed period (gate decisions)
- outputs/smoke/filter_bins.json       per-bin filter trace for the whole stream
- outputs/synthetic/anpr/events/*.csv  synthetic trips for the observed travel times

Outputs (PNG): demo/assets/chart-a-intervals.png, chart-b-gate.png, chart-c-filter.png
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-config")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "outputs" / "smoke"
EVENTS = ROOT / "outputs" / "synthetic" / "anpr" / "events"
ASSETS = ROOT / "demo" / "assets"
PERIOD = 300
LABEL = "SYNTHETIC ONLY"


def load_inputs():
    run = json.loads((SMOKE / "last_run.json").read_text(encoding="utf-8"))
    log = [json.loads(line) for line in (SMOKE / "logs" / "monitor.jsonl").read_text(encoding="utf-8").splitlines()]
    bins = json.loads((SMOKE / "filter_bins.json").read_text(encoding="utf-8"))
    return run, log, bins


def chart_a(run):
    """Model interval vs observed travel times of the trips in the target period."""
    target = run["target_period_start"]
    out = run["target_output"]
    up = pd.read_csv(EVENTS / "upstream_events.csv", parse_dates=["leave_time"])
    down = pd.read_csv(EVENTS / "downstream_events.csv", parse_dates=["leave_time"])
    trips = up[["vehicle_id", "leave_time"]].merge(
        down[["vehicle_id", "leave_time"]], on="vehicle_id", suffixes=("_up", "_down"))
    trips["t_up"] = (trips["leave_time_up"] - pd.Timestamp("1970-01-01")).dt.total_seconds()
    trips["travel"] = (trips["leave_time_down"] - trips["leave_time_up"]).dt.total_seconds()
    sel = trips[(trips["t_up"] >= target) & (trips["t_up"] < target + PERIOD)].copy()
    sel["offset"] = sel["t_up"] - target
    inside = ((sel["travel"] >= out["interval_low"]) & (sel["travel"] <= out["interval_high"])).mean()

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axhspan(out["interval_low"], out["interval_high"], color="tab:blue", alpha=0.2,
               label=f"model 90% interval [{out['interval_low']:.1f}, {out['interval_high']:.1f}] s")
    ax.scatter(sel["offset"], sel["travel"], s=18, color="black", label="observed travel time (synthetic trips)")
    ax.set_xlabel("upstream passage time within the target period (s)")
    ax.set_ylabel("travel time (s)")
    ax.set_title(f"{LABEL}: ANPR 90% interval vs observed travel times\n"
                 f"target period {target}; {len(sel)} trips, {inside:.0%} inside the interval")
    ax.set_xlim(0, PERIOD)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(ASSETS / "chart-a-intervals.png", dpi=150)
    plt.close(fig)
    return dict(trips=int(len(sel)), inside=float(inside))


def gate_category(entry):
    if entry["published"]:
        return "published (model interval)"
    prov = entry.get("provenance", "")
    if "insufficient history" in prov:
        return "fallback: insufficient history"
    if entry.get("gate_fallback"):
        return "fallback: gate closed"
    return "no forecast"


def chart_b(log):
    """Gate decision per closed period, with the reason for each non-published period."""
    colors = {
        "published (model interval)": "tab:green",
        "fallback: insufficient history": "tab:gray",
        "fallback: gate closed": "tab:red",
        "no forecast": "tab:orange",
    }
    cats = [gate_category(e) for e in log]
    counts = {}
    for c in cats:
        counts[c] = counts.get(c, 0) + 1
    fig, ax = plt.subplots(figsize=(10, 3.8))
    for i, c in enumerate(cats):
        ax.bar(i, 1, color=colors[c])
    ax.set_yticks([])
    ax.set_xlabel("closed period index (0 = first period in the stream)")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([str(i) for i in range(len(cats))], fontsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[k]) for k in colors if k in counts]
    ax.legend(handles, [f"{k} ({counts[k]})" for k in colors if k in counts],
              loc="upper left", bbox_to_anchor=(0, -0.22), ncol=2, fontsize=8)
    ax.set_title(f"{LABEL}: gate decision per period, {len(cats)} periods\n"
                 "29 of 30 periods have only 1 feature row in the stream, so the gate never runs for them")
    fig.tight_layout()
    fig.savefig(ASSETS / "chart-b-gate.png", dpi=150)
    plt.close(fig)
    return counts


def chart_c(bins):
    """Per-bin observed and predicted rate across the target period, with overshoot marks."""
    target = bins["target_period_start"]
    rows = [b for b in bins["bins"] if b["in_target"]]
    x = [(b["bin_start_ms"] - target * 1000) / 1000 for b in rows]
    observed = [b["observed_rate"] for b in rows]
    predicted = [b["predicted_rate"] for b in rows]
    flags = [xi for xi, b in zip(x, rows) if b["overshoot"]]
    zeros = [b["bin_start_ms"] for b in rows if b["event_count"] == 0]
    zero_run = longest = 0
    prev = None
    for b in rows:
        if b["event_count"] == 0:
            zero_run = zero_run + 1 if prev == "z" else 1
            longest = max(longest, zero_run)
            prev = "z"
        else:
            prev = "e"
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x, observed, width=1.0, color="tab:gray", alpha=0.6, label="observed rate (events/s, 1 s bins)")
    ax.plot(x, predicted, color="tab:blue", lw=1.6, label="filter predicted rate (events/s)")
    if flags:
        ax.scatter(flags, [0] * len(flags), marker="^", color="tab:red", s=60, zorder=5,
                   label=f"overshoot flag ({len(flags)})")
    ax.set_xlabel("seconds into the target period")
    ax.set_ylabel("events per second")
    ax.set_title(f"{LABEL}: wake-up filter, per-bin predicted vs observed rate\n"
                 f"method {bins['method']}, {bins['bin_ms']} ms bins; longest run of empty bins: {longest} s; "
                 f"overshoot flags: {len(flags)}")
    ax.set_xlim(0, PERIOD)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(ASSETS / "chart-c-filter.png", dpi=150)
    plt.close(fig)
    return dict(bins=len(rows), overshoot_flags=len(flags), longest_empty_run_s=longest,
                max_predicted=max(predicted), max_observed=max(observed))


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    run, log, bins = load_inputs()
    summary = {
        "chart_a": chart_a(run),
        "chart_b_counts": chart_b(log),
        "chart_c": chart_c(bins),
    }
    print(json.dumps(summary, indent=2))
    (ASSETS / "chart-data-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
