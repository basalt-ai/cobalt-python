"""Statistical utilities for experiment result aggregation."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _percentile(data: list[float], p: float) -> float:
    """Return the p-th percentile of *data* (0–100)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    idx = (p / 100) * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_data[lo]
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def calculate(scores: list[float]) -> "ScoreStats":  # noqa: F821
    """Return descriptive statistics for a list of scores."""
    from cobalt.types import ScoreStats

    if not scores:
        return ScoreStats(avg=0.0, min=0.0, max=0.0, p50=0.0, p95=0.0, p99=0.0)

    return ScoreStats(
        avg=statistics.mean(scores),
        min=min(scores),
        max=max(scores),
        p50=_percentile(scores, 50),
        p95=_percentile(scores, 95),
        p99=_percentile(scores, 99),
    )
