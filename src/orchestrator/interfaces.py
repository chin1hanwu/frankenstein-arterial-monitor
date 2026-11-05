"""Interface skeleton for the orchestrator.

Stdlib only. The orchestrator routes events to the two parts,
aggregates their outputs into one monitoring record per period,
and owns config and logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AppConfig:
    """Runtime config, loaded from ``config/local.yaml``."""

    anpr_repo: str  # local path of the LSTM-MDN-git-ready checkout
    filter_repo: str  # local path of the wake-up-overshoot checkout
    anpr_dir: str  # ANPR data dir (desensitised CSVs)
    binance_raw: str  # Binance aggTrades dir (downloaded separately)
    log_dir: str = "outputs/logs"
    publish_on_fallback: bool = False


@dataclass
class Event:
    """One incoming event, of either kind."""

    kind: Literal["anpr_observation", "point_event"]
    timestamp: int  # epoch seconds (ANPR) or ms (point events)
    payload: dict = field(default_factory=dict)


@dataclass
class MonitoringOutput:
    """One aggregated monitoring record per 5-minute period."""

    period_start: int
    period_end: int
    published: bool  # False when the gate fell back to the prior
    interval_low: float | None = None  # 90% interval, when published
    interval_high: float | None = None
    overshoot: bool = False  # wake-up filter overshoot flag for the period
