"""Analyze curves and generate metrics/flags.

This module computes statistical metrics on curve samples and generates
flags for issues like clamping, discontinuities, and limited range.
"""

from __future__ import annotations

from itertools import pairwise
import logging

import numpy as np

from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.models import (
    ContinuityCheck,
    CurveStats,
    ReportFlag,
    ReportFlagLevel,
)

logger = logging.getLogger(__name__)


def analyze_curve(
    samples: list[float],
    config: EvalConfig,
    curve_type: str | None = None,
) -> tuple[CurveStats, list[ReportFlag]]:
    """Analyze curve samples and generate flags.

    Computes statistical metrics and checks for issues based on
    configuration thresholds.

    Args:
        samples: Curve sample values (normalized 0-1)
        config: Configuration with thresholds
        curve_type: Type of curve (e.g., "HOLD", "PULSE", "MOVEMENT_TRIANGLE")

    Returns:
        Tuple of (CurveStats, list[ReportFlag])

    Example:
        >>> samples = [0.0, 0.0, 0.5, 1.0, 1.0]
        >>> config = EvalConfig()
        >>> stats, flags = analyze_curve(samples, config)
        >>> stats.clamp_pct
        80.0
    """
    if not samples:
        # Empty curve
        return (
            CurveStats(
                min=0.0,
                max=0.0,
                range=0.0,
                mean=0.0,
                std=0.0,
                clamp_pct=0.0,
                energy=0.0,
            ),
            [],
        )

    arr = np.array(samples)

    # Compute statistics
    clamp_pct = _calculate_clamp_percentage(arr)
    stats = CurveStats(
        min=float(arr.min()),
        max=float(arr.max()),
        range=float(arr.max() - arr.min()),
        mean=float(arr.mean()),
        std=float(arr.std()),
        clamp_pct=clamp_pct,
        energy=_calculate_energy(arr),
    )

    # Generate flags
    flags = []

    # Determine curve characteristics
    is_hold_curve = curve_type and "HOLD" in curve_type.upper()
    is_pulse_curve = curve_type and "PULSE" in curve_type.upper()

    # Clamp warnings/errors
    # Skip for HOLD curves - they're supposed to be static at boundaries
    # Relax threshold for PULSE curves - they're designed to hit max brightness
    if not is_hold_curve:
        # Use relaxed threshold for PULSE curves (60% instead of 40%)
        error_threshold = 0.60 if is_pulse_curve else config.clamp_error_threshold
        warning_threshold = 0.50 if is_pulse_curve else config.clamp_warning_threshold

        if clamp_pct > error_threshold * 100:
            flags.append(
                ReportFlag(
                    level=ReportFlagLevel.ERROR,
                    code="CLAMP_PCT_HIGH",
                    message=f"Curve clamps {stats.clamp_pct:.1f}% of samples",
                    details={
                        "clamp_pct": stats.clamp_pct,
                        "threshold": error_threshold * 100,
                    },
                )
            )
        elif clamp_pct > warning_threshold * 100:
            flags.append(
                ReportFlag(
                    level=ReportFlagLevel.WARNING,
                    code="CLAMP_PCT",
                    message=f"Curve clamps {stats.clamp_pct:.1f}% of samples",
                    details={
                        "clamp_pct": stats.clamp_pct,
                        "threshold": warning_threshold * 100,
                    },
                )
            )

    # Limited range
    # Skip for HOLD curves - they're supposed to have zero range
    if not is_hold_curve and stats.range < 0.1:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.INFO,
                code="LIMITED_RANGE",
                message=f"Curve has limited range: {stats.range:.3f}",
                details={"range": stats.range},
            )
        )

    # Static curve - only flag if truly static (no range AND no energy)
    # A curve with jumps will have low energy but non-zero range
    # Skip for HOLD curves - they're intentionally static
    if not is_hold_curve and stats.energy < 0.001 and stats.range < 0.01 and len(samples) > 1:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.INFO,
                code="STATIC_CURVE",
                message="Curve appears static or nearly static",
                details={"energy": stats.energy, "range": stats.range},
            )
        )

    return stats, flags


def physical_channel_stats(values: list[float], *, frame_ms: int) -> CurveStats:
    """Statistics of one channel of a physical render, in the channel's own unit.

    `values` holds one value per frame (`physical_channel_values`). `energy` is the
    mean absolute rate of change per second. No clamp percentage is reported: the
    physical renderer refuses a value outside the axis' operable range instead of
    clamping it. No flag is raised: the legacy flags key on curve types a physical
    render does not have. `values` is never empty: a fixture has a value in every frame.
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


def check_loop_continuity(
    samples: list[float],
    threshold: float = 0.05,
    curve_type: str | None = None,
    channel: str | None = None,
) -> ContinuityCheck:
    """Check if curve is continuous at loop boundary.

    For repeatable templates, the curve should start and end at similar
    values to avoid discontinuities when looping.

    Loop continuity is primarily a movement concept (pan/tilt). Dimmer curves
    often fade in/out and aren't meant to loop, so the check is skipped for them.

    Args:
        samples: Curve sample values
        threshold: Maximum acceptable difference (normalized)
        curve_type: Type of curve (e.g., "LINEAR", "SINE", "PULSE")
        channel: Channel name (e.g., "pan", "tilt", "dimmer")

    Returns:
        ContinuityCheck with loop_delta and pass/fail status

    Example:
        >>> samples = [0.5, 0.6, 0.7, 0.51]  # Close loop
        >>> check = check_loop_continuity(samples, threshold=0.05, channel="pan")
        >>> check.ok
        True
    """
    if len(samples) < 2:
        return ContinuityCheck(loop_delta=0.0, ok=True, threshold=threshold)

    # Skip loop check for dimmer curves - they're not movement and often fade
    if channel and channel.lower() == "dimmer":
        delta = abs(samples[-1] - samples[0])
        return ContinuityCheck(
            loop_delta=delta,
            ok=True,  # Always pass for dimmers
            threshold=threshold,
        )

    # Determine if this curve type is expected to loop
    # Non-looping curves: LINEAR (fades), EXPONENTIAL (fades), FADE_IN, FADE_OUT
    is_loopable = True
    if curve_type:
        curve_upper = curve_type.upper()
        non_looping_patterns = ["LINEAR", "FADE_IN", "FADE_OUT", "EXPONENTIAL"]
        is_loopable = not any(pattern in curve_upper for pattern in non_looping_patterns)

    # If curve isn't meant to loop, skip the check (always pass)
    if not is_loopable:
        delta = abs(samples[-1] - samples[0])
        return ContinuityCheck(
            loop_delta=delta,
            ok=True,  # Pass by default for non-looping curves
            threshold=threshold,
        )

    # For looping curves, check continuity
    delta = abs(samples[-1] - samples[0])

    return ContinuityCheck(
        loop_delta=delta,
        ok=delta < threshold,
        threshold=threshold,
    )


def _calculate_clamp_percentage(arr: np.ndarray, epsilon: float = 0.001) -> float:
    """Calculate percentage of samples at boundaries.

    Args:
        arr: Sample array (normalized 0-1)
        epsilon: Tolerance for boundary detection

    Returns:
        Percentage (0-100) of samples at 0 or 1
    """
    at_min = np.sum(arr <= epsilon)
    at_max = np.sum(arr >= 1.0 - epsilon)
    clamped = at_min + at_max

    return float((clamped / len(arr)) * 100 if len(arr) > 0 else 0.0)


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
