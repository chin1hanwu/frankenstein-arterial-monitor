"""Interface skeleton for explicit Gaussian point-process wake-up filters.

Stdlib only. The real filters live in ``wake-up-overshoot``
(``experiment/``); ``anpr_forecast`` is not involved. The kernel
binding in ``kernel.py`` calls ``experiment/engine.exe`` one bin at a
time. This module fixes the shapes the orchestrator relies on.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

BIN_WIDTHS_MS = (10, 50, 250, 1000)


@dataclass
class FilterConfig:
    """One tuned filter configuration.

    ``method`` is one of the 5 tuned methods in
    ``experiment/frozen_params.json`` (kept as a plain string here so
    this skeleton never invents a method name). ``kappa`` is the
    crossing index from ``experiment/theory_regions.json``, computed
    per synthetic cell. It is None when the caller has none, and then
    the region is "unclassified". This field is NOT the OU mean-reversion
    rate that the engine calls ``kappa`` for method OU_I; the engine
    value comes from ``frozen_params.json``.
    """

    method: str
    bin_width_ms: int  # one of BIN_WIDTHS_MS
    kappa: float | None = None


@dataclass
class BinUpdate:
    """One closed time bin of events. A bin with no events has event_count 0."""

    bin_start: int  # epoch milliseconds
    event_count: int
    observed_rate: float  # events per second in this bin


@dataclass
class FilterState:
    """Filter state carried across bins.

    ``update`` changes this object in place. Leave ``theta``, ``V`` and
    ``silent_seconds`` at their defaults for a new stream. The backend
    fills in the frozen initial values on the first call.
    """

    config: FilterConfig
    predicted_rate: float  # predicted rate for the next bin, events per second
    theta: float | None = None  # engine log-rate posterior; None: frozen initial_theta
    V: float | None = None  # engine variance posterior; None: frozen initial_V
    silent_seconds: float = 0.0  # length of the current run of empty bins


@dataclass
class FilterResult:
    """Filter output for one bin."""

    predicted_rate: float  # prediction for this bin, events per second
    overshoot: bool  # True: post-wake prediction overshoots the resumed rate
    region: str  # "crossing" / "no-crossing" / "transition" by kappa; "unclassified" if kappa is None


BackendFn = Callable[["FilterState", "BinUpdate"], "FilterResult"]
_backend: BackendFn | None = None


def set_backend(fn: BackendFn | None) -> None:
    """Register the kernel backend. ``kernel.KernelBackend(...).update`` is the usual one."""
    global _backend
    _backend = fn


def update(state: FilterState, update: BinUpdate) -> FilterResult:
    """Advance the filter by one bin and judge overshoot.

    Delegates to the registered backend. Raises RuntimeError if none is
    registered. The backend's overshoot rule is in ``kernel.py``.
    """
    if _backend is None:
        raise RuntimeError("no wake-up filter backend registered; call set_backend() first")
    return _backend(state, update)
