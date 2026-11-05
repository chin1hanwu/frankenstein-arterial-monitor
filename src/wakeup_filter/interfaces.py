"""Interface skeleton for explicit Gaussian point-process wake-up filters.

Stdlib only. The real filters live in ``wake-up-overshoot``
(``experiment/``); this module fixes the shapes the orchestrator
relies on so the wiring can be built before the kernel is vendored in.
"""

from __future__ import annotations

from dataclasses import dataclass

BIN_WIDTHS_MS = (10, 50, 250, 1000)


@dataclass
class FilterConfig:
    """One tuned filter configuration.

    ``method`` is one of the 5 tuned methods in
    ``experiment/frozen_params.json`` (kept as a plain string here so
    this skeleton never invents a method name); ``kappa`` is the
    crossing index from ``experiment/theory_regions.json`` (None until
    the cell region is looked up).
    """

    method: str
    bin_width_ms: int  # one of BIN_WIDTHS_MS
    kappa: float | None = None


@dataclass
class BinUpdate:
    """One closed time bin of events."""

    bin_start: int  # epoch milliseconds
    event_count: int
    observed_rate: float  # events per second in this bin


@dataclass
class FilterState:
    """Filter state carried across bins."""

    config: FilterConfig
    predicted_rate: float


@dataclass
class FilterResult:
    """Filter output for one bin."""

    predicted_rate: float
    overshoot: bool  # True: post-wake prediction overshoots the resumed rate
    region: str  # crossing / no-crossing / transition (by kappa)


def update(state: FilterState, update: BinUpdate) -> FilterResult:
    """Advance the filter by one bin and judge overshoot.

    TODO: wire to the ``engine.cpp`` Python wrapper in
    wake-up-overshoot ``experiment/``; look the cell region up in
    ``theory_regions.json`` via the crossing index kappa.
    """
    raise NotImplementedError("wire update() to the filter kernel")
