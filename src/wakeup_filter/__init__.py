"""Explicit Gaussian point-process wake-up filters (interface skeleton).

Real implementation lives in the source repo ``wake-up-overshoot``:
``experiment/engine.cpp`` is the C++ filter kernel with a Python
wrapper, ``experiment/frozen_params.json`` holds the 20 tuned
configurations (5 methods x 4 bin widths), ``experiment/
theory_regions.json`` holds the crossing index kappa and the region
of each of the 200 synthetic cells. This package only fixes the
interface the orchestrator calls.
"""

from .interfaces import (
    BIN_WIDTHS_MS,
    BinUpdate,
    FilterConfig,
    FilterResult,
    FilterState,
    update,
)

__all__ = [
    "BIN_WIDTHS_MS",
    "BinUpdate",
    "FilterConfig",
    "FilterResult",
    "FilterState",
    "update",
]
