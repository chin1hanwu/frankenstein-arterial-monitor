"""ANPR probabilistic travel-time forecasting (interface skeleton).

Real implementation lives in the open-source repo
``availability-aware-anpr-forecasting`` (MIT): ``data_processing.py``
builds the availability features, ``forecast_models.py`` holds the
snapshot / recurrent mixture density networks, ``probabilistic_
metrics.py`` holds the probabilistic scores, ``experiment_runner.py``
runs the development stages, and ``frozen_evaluation.py`` does the
one-shot frozen test evaluation and service KPIs. This package only
fixes the interface the orchestrator calls.
"""

from .interfaces import (
    PERIOD_SECONDS,
    AvailabilityFeatures,
    ForecastRequest,
    ForecastResult,
    GateDecision,
    predict,
)

__all__ = [
    "PERIOD_SECONDS",
    "AvailabilityFeatures",
    "ForecastRequest",
    "ForecastResult",
    "GateDecision",
    "predict",
]
