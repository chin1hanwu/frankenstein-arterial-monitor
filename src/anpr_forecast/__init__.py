"""ANPR probabilistic travel-time forecasting (interface skeleton).

Real implementation lives in the open-source repo
``availability-aware-anpr-forecasting`` (MIT): ``data_processing.py``
builds the availability features, ``forecast_models.py`` holds the
snapshot / recurrent mixture density networks, ``probabilistic_
metrics.py`` holds the probabilistic scores, ``experiment_runner.py``
runs the development stages, and ``frozen_evaluation.py`` does the
one-shot frozen test evaluation and service KPIs. This package fixes
the interface the orchestrator calls. The synthetic-only backend that
uses the public functions is ``anpr_forecast.synthetic``.
"""

from .interfaces import (
    PERIOD_SECONDS,
    SEQUENCE_LENGTH,
    AvailabilityFeatures,
    ForecastRequest,
    ForecastResult,
    GateDecision,
    predict,
    set_predictor,
)

__all__ = [
    "PERIOD_SECONDS",
    "SEQUENCE_LENGTH",
    "AvailabilityFeatures",
    "ForecastRequest",
    "ForecastResult",
    "GateDecision",
    "predict",
    "set_predictor",
]
