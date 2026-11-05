"""Kiro multi-agent orchestration (interface skeleton).

The orchestrator routes events, aggregates the two parts' outputs
into one monitoring record per period, and owns config and logging.
It does no model computation itself. The event loop skeleton lives
in ``pipeline.py``.
"""

from .interfaces import AppConfig, Event, MonitoringOutput

__all__ = ["AppConfig", "Event", "MonitoringOutput"]
