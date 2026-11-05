"""Stdlib-only self-check for the skeleton interfaces.

Run from the repository root:

    python scripts/check_interfaces.py

It imports the three interface modules, builds one instance of each
message type with dummy values, and asserts the shared constants.
It must keep working with no third-party dependency installed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    import anpr_forecast.interfaces as anpr
    import orchestrator.interfaces as orch
    import orchestrator.pipeline as pipeline
    import wakeup_filter.interfaces as filt

    # Shared constants.
    assert anpr.PERIOD_SECONDS == 300, "ANPR period must be 300 s"
    assert filt.BIN_WIDTHS_MS == (10, 50, 250, 1000), "unexpected bin widths"

    # ANPR messages construct.
    features = anpr.AvailabilityFeatures(
        r_comp=0.9, rho_t=0.1, mean=81.0, variance=25.0,
        time_code=0.5, space_code=1.0,
    )
    request = anpr.ForecastRequest(
        period_start=0, period_end=300, features=features,
    )
    result = anpr.ForecastResult(
        quantiles={0.05: 60.0, 0.5: 81.0, 0.95: 105.0},
        interval_low=60.0, interval_high=105.0,
    )
    decision = anpr.GateDecision(publish=True, fallback=False, coverage=0.91)
    assert request.period_end - request.period_start == 300
    assert result.interval_low <= result.quantiles[0.5] <= result.interval_high
    assert decision.publish and not decision.fallback

    # Filter messages construct.
    config = filt.FilterConfig(method="explicit", bin_width_ms=250, kappa=None)
    update = filt.BinUpdate(bin_start=0, event_count=3, observed_rate=12.0)
    state = filt.FilterState(config=config, predicted_rate=10.0)
    fresult = filt.FilterResult(
        predicted_rate=10.5, overshoot=False, region="no-crossing",
    )
    assert state.config.bin_width_ms in filt.BIN_WIDTHS_MS
    assert update.event_count >= 0 and fresult.predicted_rate > 0

    # Orchestrator messages construct, and the pipeline entry exists.
    event = orch.Event(kind="anpr_observation", timestamp=0, payload={"plate": "hash"})
    output = orch.MonitoringOutput(
        period_start=0, period_end=300, published=True,
        interval_low=60.0, interval_high=105.0, overshoot=False,
    )
    assert event.kind in ("anpr_observation", "point_event")
    assert output.published and output.interval_low < output.interval_high
    assert callable(pipeline.run_event_loop)

    print("interfaces OK: anpr_forecast, wakeup_filter, orchestrator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
