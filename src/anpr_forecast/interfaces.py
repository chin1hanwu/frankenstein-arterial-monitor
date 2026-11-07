"""Interface skeleton for ANPR probabilistic travel-time forecasting.

Stdlib only. The real models live in the open-source repo
``availability-aware-anpr-forecasting`` (MIT); this module fixes the
shapes the orchestrator relies on so the wiring can be built before
the models are vendored in.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

PERIOD_SECONDS = 300  # 5-minute periods, cut on strict boundaries.
SEQUENCE_LENGTH = 30  # feature rows per model input, the last one being the current period.


@dataclass
class AvailabilityFeatures:
    """14-dim availability feature vector ``x_t`` for one period.

    ``extra`` holds the full 14-dim vector in the public column order
    of ``data_processing.compute_rolling_features``: N_up, N_match,
    R_comp, bar_y, s_y^2, then 9 time features. When ``extra`` is set,
    the named fields are views of it. Fields with no public counterpart
    are NaN (see ``docs/wiring.md`` section 2).
    """

    r_comp: float  # completion rate of trips in the period (public column R_comp)
    rho_t: float  # in-transit (right-censored) ratio per the spec. NaN on the synthetic path: the public code has no such column. Its gate input is bar_y/300, named bar_y_over_300 in synthetic.py; the in-transit definition is pending HW confirmation
    mean: float  # mean of completed travel times (public column bar_y)
    variance: float  # variance of completed travel times (public column s_y^2)
    time_code: float  # temporal encoding; no single public column (NaN on the synthetic path)
    space_code: float  # spatial encoding; the public code has none (NaN on the synthetic path)
    extra: tuple[float, ...] = field(default_factory=tuple)


@dataclass
class ForecastRequest:
    """One period to forecast, with the feature history that ends at its start.

    ``history`` holds the previous feature rows, oldest first. Together
    with ``features`` they give ``SEQUENCE_LENGTH`` rows.
    """

    period_start: int  # epoch seconds, period boundary
    period_end: int  # period_start + 300
    features: AvailabilityFeatures
    history: tuple[AvailabilityFeatures, ...] = field(default_factory=tuple)


@dataclass
class ForecastResult:
    """Probabilistic forecast for one period."""

    quantiles: dict[float, float]  # level -> travel time in seconds
    interval_low: float  # 90% interval lower end
    interval_high: float  # 90% interval upper end
    provenance: str = ""  # e.g. "synthetic-only; not the paper's frozen path"


@dataclass
class GateDecision:
    """Service-level reliability gate for one period."""

    publish: bool  # True: publish the interval; False: fall back
    fallback: bool  # True: fall back to the training marginal prior
    coverage: float  # achieved coverage of the published interval


PredictFn = Callable[[ForecastRequest], "tuple[ForecastResult, GateDecision]"]
_predictor: PredictFn | None = None


def set_predictor(fn: PredictFn | None) -> None:
    """Register the backend that implements ``predict``.

    The skeleton does not import the source repo's models. A backend
    such as ``anpr_forecast.synthetic.SyntheticForecaster.predict``
    is registered by the caller before the event loop runs.
    """
    global _predictor
    _predictor = fn


def predict(request: ForecastRequest) -> tuple[ForecastResult, GateDecision]:
    """Forecast one period and gate the result.

    Delegates to the registered backend. Raises RuntimeError if none is
    registered. The frozen-evaluation path in the source repo is not
    implemented here; see ``docs/wiring.md`` section 2.
    """
    if _predictor is None:
        raise RuntimeError("no ANPR predictor registered; call set_predictor() first")
    return _predictor(request)
