"""Interface skeleton for ANPR probabilistic travel-time forecasting.

Stdlib only. The real models live in the open-source repo
``availability-aware-anpr-forecasting`` (MIT); this module fixes the
shapes the orchestrator relies on so the wiring can be built before
the models are vendored in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PERIOD_SECONDS = 300  # 5-minute periods, cut on strict boundaries.


@dataclass
class AvailabilityFeatures:
    """14-dim availability feature vector ``x_t`` for one period.

    Named fields are the ones the paper calls out explicitly; the
    remaining dims (full 14-dim layout) are defined in the open-source
    repo's ``data_processing.py`` and carried in ``extra``.
    """

    r_comp: float  # completion rate of trips in the period
    rho_t: float  # in-transit (right-censored) ratio
    mean: float  # mean of completed travel times
    variance: float  # variance of completed travel times
    time_code: float  # temporal encoding
    space_code: float  # spatial encoding
    extra: tuple[float, ...] = field(default_factory=tuple)


@dataclass
class ForecastRequest:
    """One closed 5-minute period to forecast."""

    period_start: int  # epoch seconds, period boundary
    period_end: int  # period_start + 300
    features: AvailabilityFeatures


@dataclass
class ForecastResult:
    """Probabilistic forecast for one period."""

    quantiles: dict[float, float]  # level -> travel time in seconds
    interval_low: float  # 90% interval lower end
    interval_high: float  # 90% interval upper end


@dataclass
class GateDecision:
    """Service-level reliability gate for one period."""

    publish: bool  # True: publish the interval; False: fall back
    fallback: bool  # True: fall back to the training marginal prior
    coverage: float  # achieved coverage of the published interval


def predict(request: ForecastRequest) -> tuple[ForecastResult, GateDecision]:
    """Forecast one closed period and gate the result.

    TODO: wire to ``forecast_models.py`` (snapshot / recurrent mixture
    density networks and quantile gradient-boosted trees) in
    availability-aware-anpr-forecasting; service KPIs are evaluated
    by ``frozen_evaluation.py``. Reported baseline (private repo
    README): Snapshot Quantile GBDT, CRPS 8.364 s; gate keeps 74.9%
    of periods at coverage 0.918, mean width 59.1 s.
    """
    raise NotImplementedError("wire predict() to the source-repo models")
