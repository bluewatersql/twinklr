"""Statistics of a render's decoded channel values."""

from __future__ import annotations

from itertools import pairwise
import logging

import numpy as np

from twinklr.core.reporting.evaluation.models import (
    CurveStats,
)

logger = logging.getLogger(__name__)


def physical_channel_stats(values: list[float], *, frame_ms: int) -> CurveStats:
    """Statistics of one channel of a physical render, in the channel's own unit.

    `values` holds one value per frame (`physical_channel_values`). `energy` is the
    mean absolute rate of change per second. No clamp percentage is reported: the
    physical renderer refuses a value outside the axis' operable range instead of
    clamping it. No flag is raised. `values` is never empty: a fixture has a value in every frame.
    """
    arr = np.array(values)
    return CurveStats(
        min=float(arr.min()),
        max=float(arr.max()),
        range=float(arr.max() - arr.min()),
        mean=float(arr.mean()),
        std=float(arr.std()),
        energy=_calculate_energy(arr) * 1000 / frame_ms,
    )


def lit_motion(
    values: list[float], intensity: list[float], *, frame_ms: int
) -> tuple[float, float] | None:
    """A pose channel's range over its lit frames (emitted intensity above 0) and its
    mean absolute rate of change per second between consecutive lit frames: the motion
    an audience sees, without the dark repositioning. None when no frame is lit."""
    lit = [value for value, level in zip(values, intensity, strict=True) if level > 0]
    if not lit:
        return None
    steps = [
        abs(b - a)
        for (a, b), (la, lb) in zip(pairwise(values), pairwise(intensity), strict=True)
        if la > 0 and lb > 0
    ]
    rate = sum(steps) / len(steps) * 1000 / frame_ms if steps else 0.0
    return max(lit) - min(lit), rate


def largest_step(
    values: list[float], *, start_ms: int, frame_ms: int, lit: list[float] | None = None
) -> tuple[float, int, int] | None:
    """The largest change between consecutive frames, signed, with the times of the two
    frames (`values[0]` at `start_ms`); with `lit` (emitted intensity per frame), only
    between two lit frames. The first of equal steps wins; None when there is no pair."""
    best: tuple[float, int, int] | None = None
    for index, (a, b) in enumerate(pairwise(values)):
        if lit is not None and not (lit[index] > 0 and lit[index + 1] > 0):
            continue
        if best is None or abs(b - a) > abs(best[0]):
            at = start_ms + index * frame_ms
            best = (b - a, at, at + frame_ms)
    return best


def _calculate_energy(arr: np.ndarray) -> float:
    """Calculate mean absolute derivative (movement energy).

    Args:
        arr: Sample array

    Returns:
        Mean absolute difference between consecutive samples
    """
    if len(arr) < 2:
        return 0.0

    derivatives = np.abs(np.diff(arr))
    return float(derivatives.mean())
