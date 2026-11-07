"""Event loop: route, close periods, aggregate, log. No model code here.

Data flow (see ``docs/wiring.md`` section 4):

- An ``anpr_observation`` event at a period boundary B carries the
  features known at B. The loop stores them. Opening the period [B, B+300)
  calls ``anpr_forecast.predict`` with the feature history that ends at B.
- A ``point_event`` event is placed in its bin. Bins are fed to
  ``wakeup_filter.update`` in time order, including empty bins, so
  silences are measured. An overshoot flag joins the open period.
- Closing a period (the clock reaches the next boundary) emits one
  ``MonitoringOutput`` and appends it to ``<log_dir>/monitor.jsonl``.

Ordering assumptions. Events must be sorted by time. The feature row for
boundary B must arrive before any point event at or after B. A violation
raises ``ValueError``. The partial period at the end of the stream is not
emitted.

Interval publication. If the gate publishes, the model interval is
emitted. If the gate falls back, nothing is emitted unless
``AppConfig.publish_on_fallback`` is true, in which case the prior
interval is emitted.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from anpr_forecast.interfaces import PERIOD_SECONDS, SEQUENCE_LENGTH, ForecastRequest
from anpr_forecast.interfaces import predict as anpr_predict
from orchestrator.interfaces import AppConfig, Event, MonitoringOutput
from wakeup_filter.interfaces import BinUpdate, FilterConfig, FilterState
from wakeup_filter.interfaces import update as filter_update

LOG_NAME = "monitor.jsonl"


@dataclass
class _Period:
    start: int
    forecast: object = None  # ForecastResult, when a forecast was issued
    decision: object = None  # GateDecision, when a forecast was issued
    reason: str = ""  # why no forecast was issued, if none
    overshoot: bool = False
    bins: int = 0
    events: int = 0


class _Monitor:
    def __init__(self, config: AppConfig):
        if (PERIOD_SECONDS * 1000) % config.bin_width_ms:
            raise ValueError("bin width must divide the 300 s period")
        self.config = config
        self.width_ms = config.bin_width_ms
        self.width_s = config.bin_width_ms / 1000.0
        self.state = FilterState(
            config=FilterConfig(method=config.filter_method, bin_width_ms=config.bin_width_ms),
            predicted_rate=0.0,
        )
        self.rows = {}  # boundary (epoch s) -> AvailabilityFeatures, pruned to SEQUENCE_LENGTH
        self.period = None  # open _Period, or None before the first boundary
        self.boundary = None  # next boundary (epoch s) to process
        self.open_bin = None  # index of the open bin
        self.open_count = 0
        self.last_ms = None
        self.log_path = Path(config.log_dir) / LOG_NAME
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # --- bins -------------------------------------------------------------
    def _flush_bins_until(self, t_ms):
        """Feed every bin that ends at or before ``t_ms`` to the filter."""
        while self.open_bin is not None and (self.open_bin + 1) * self.width_ms <= t_ms:
            upd = BinUpdate(
                bin_start=self.open_bin * self.width_ms,
                event_count=self.open_count,
                observed_rate=self.open_count / self.width_s,
            )
            result = filter_update(self.state, upd)
            if self.period is not None:
                self.period.bins += 1
                self.period.overshoot = self.period.overshoot or result.overshoot
            self.open_bin += 1
            self.open_count = 0

    # --- periods ----------------------------------------------------------
    def _open_period(self, b):
        period = _Period(start=b)
        if b not in self.rows:
            period.reason = "no feature row at period start"
            return period
        history = [self.rows.get(b - k * PERIOD_SECONDS) for k in range(SEQUENCE_LENGTH - 1, 0, -1)]
        if any(h is None for h in history):
            history = []  # a gap breaks the window; predict() then falls back
        request = ForecastRequest(
            period_start=b,
            period_end=b + PERIOD_SECONDS,
            features=self.rows[b],
            history=tuple(history),
        )
        period.forecast, period.decision = anpr_predict(request)
        return period

    def _close_period(self, period, b):
        out = None
        if period.forecast is None:
            emit, low, high = False, None, None
        elif period.decision.publish or self.config.publish_on_fallback:
            emit = True
            low, high = period.forecast.interval_low, period.forecast.interval_high
        else:
            emit, low, high = False, None, None
        reason = period.reason or (period.forecast.provenance if period.forecast else "")
        provenance = f"anpr: {reason}; events: {self.config.event_source}"
        record = MonitoringOutput(
            period_start=period.start,
            period_end=b,
            published=emit,
            interval_low=low,
            interval_high=high,
            overshoot=period.overshoot,
            provenance=provenance,
        )
        self._log(record, period)
        return record

    def _log(self, record, period):
        entry = {
            "period_start": record.period_start,
            "period_end": record.period_end,
            "published": record.published,
            "interval_low": record.interval_low,
            "interval_high": record.interval_high,
            "overshoot": record.overshoot,
            "provenance": record.provenance,
            "gate_publish": None if period.decision is None else period.decision.publish,
            "gate_fallback": None if period.decision is None else period.decision.fallback,
            "bins": period.bins,
            "events": period.events,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, allow_nan=False) + "\n")

    def _advance(self, t_ms, out):
        """Move the clock to ``t_ms``: flush bins and close/open periods at boundaries."""
        while self.boundary is not None and self.boundary * 1000 <= t_ms:
            b = self.boundary
            self._flush_bins_until(b * 1000)
            if self.period is not None:
                out.append(self._close_period(self.period, b))
            self.period = self._open_period(b)
            self.boundary += PERIOD_SECONDS
        self._flush_bins_until(t_ms)

    def _start_if_needed(self, t_ms):
        if self.boundary is None:
            self.open_bin = t_ms // self.width_ms
            seconds = t_ms / 1000.0
            self.boundary = int(math.ceil(seconds / PERIOD_SECONDS)) * PERIOD_SECONDS

    # --- events -----------------------------------------------------------
    def handle(self, event: Event, out: list):
        if event.kind == "anpr_observation":
            t_ms = int(event.timestamp) * 1000
            self._check_order(t_ms)
            self._start_if_needed(t_ms)
            if event.timestamp % PERIOD_SECONDS:
                raise ValueError("anpr_observation timestamp must be a 300 s boundary")
            features = event.payload.get("features")
            if features is None:
                raise ValueError("anpr_observation needs payload['features']")
            if event.timestamp in self.rows:
                raise ValueError(f"duplicate feature row at {event.timestamp}")
            if self.boundary is not None and event.timestamp < self.boundary:
                raise ValueError("feature row arrived after its boundary was processed")
            self.rows[int(event.timestamp)] = features
            self._prune(int(event.timestamp))
            self._advance(t_ms, out)
            return
        if event.kind == "point_event":
            t_ms = int(event.timestamp)
            self._check_order(t_ms)
            self._start_if_needed(t_ms)
            self._advance(t_ms, out)
            if t_ms // self.width_ms != self.open_bin:
                raise AssertionError("bin bookkeeping out of step")
            self.open_count += 1
            if self.period is not None:
                self.period.events += 1
            return
        raise ValueError(f"unknown event kind {event.kind!r}")

    def _check_order(self, t_ms):
        if self.last_ms is not None and t_ms < self.last_ms:
            raise ValueError("events must be sorted by time")
        self.last_ms = t_ms

    def _prune(self, latest):
        keep_from = latest - SEQUENCE_LENGTH * PERIOD_SECONDS
        for key in [k for k in self.rows if k < keep_from]:
            del self.rows[key]


def run_event_loop(config: AppConfig, events):
    """Consume events in time order and yield one ``MonitoringOutput`` per closed period.

    Requires a registered ANPR predictor (``anpr_forecast.interfaces.set_predictor``)
    and a registered filter backend (``wakeup_filter.interfaces.set_backend``).
    """
    monitor = _Monitor(config)
    for event in events:
        out = []
        monitor.handle(event, out)
        yield from out
