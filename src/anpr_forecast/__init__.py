"""ANPR probabilistic travel-time forecasting (interface skeleton).

Real implementation lives in the source repo ``LSTM-MDN-git-ready``
(Layer 2): ``enhanced_data_processing.py`` builds the availability
features, ``revision_models.py`` holds SnapshotMDN / RecurrentMDN /
Quantile GBDT, ``revision_metrics.py`` holds CRPS / NLL / PIT /
Pinball, ``gate_selectivity.py`` holds the reliability gate.
This package only fixes the interface the orchestrator calls.
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
