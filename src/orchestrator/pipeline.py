"""Event-loop skeleton: route, aggregate, log. No model code here.

Data flow (see ``docs/wiring.md`` section 4):

- ANPR observations accumulate into the current 5-minute period.
  When a period closes, call ``anpr_forecast.predict`` and apply the
  gate: publish the interval, or fall back to the marginal prior.
- Point events are binned by width and fed to
  ``wakeup_filter.update``; the overshoot flag joins the current
  period's monitoring record.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from anpr_forecast.interfaces import predict as anpr_predict
from orchestrator.interfaces import AppConfig, Event, MonitoringOutput
from wakeup_filter.interfaces import update as filter_update


def run_event_loop(config: AppConfig, events: Iterable[Event]) -> Iterator[MonitoringOutput]:
    """Consume events and yield one monitoring record per closed period.

    TODO (in task order, see ``.kiro/specs/arterial-monitoring/tasks.md``):
    1. Buffer ANPR observations into the current 300 s period.
    2. On period close, build AvailabilityFeatures, call
       ``anpr_predict``, and apply the GateDecision.
    3. Bin point events by the configured widths, call
       ``filter_update`` per bin, and carry the overshoot flag.
    4. Yield a MonitoringOutput per period and log to config.log_dir.
    """
    raise NotImplementedError("implement run_event_loop per tasks.md")
