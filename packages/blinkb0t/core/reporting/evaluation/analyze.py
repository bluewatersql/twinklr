"""Analyze curves and generate metrics/flags.

This module computes statistical metrics on curve samples and generates
flags for issues like clamping, discontinuities, and limited range.
"""

from __future__ import annotations

import logging

import numpy as np

from blinkb0t.core.reporting.evaluation.config import EvalConfig
from blinkb0t.core.reporting.evaluation.models import (
    ContinuityCheck,
    CurveStats,
    ReportFlag,
    ReportFlagLevel,
)

logger = logging.getLogger(__name__)


def analyze_curve(
    samples: list[float],
    config: EvalConfig,
) -> tuple[CurveStats, list[ReportFlag]]:
    """Analyze curve samples and generate flags.

    Computes statistical metrics and checks for issues based on
    configuration thresholds.

    Args:
        samples: Curve sample values (normalized 0-1)
        config: Configuration with thresholds

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
    stats = CurveStats(
        min=float(arr.min()),
        max=float(arr.max()),
        range=float(arr.max() - arr.min()),
        mean=float(arr.mean()),
        std=float(arr.std()),
        clamp_pct=_calculate_clamp_percentage(arr),
        energy=_calculate_energy(arr),
    )

    # Generate flags
    flags = []

    # Clamp warnings/errors
    if stats.clamp_pct > config.clamp_error_threshold * 100:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.ERROR,
                code="CLAMP_PCT_HIGH",
                message=f"Curve clamps {stats.clamp_pct:.1f}% of samples",
                details={
                    "clamp_pct": stats.clamp_pct,
                    "threshold": config.clamp_error_threshold * 100,
                },
            )
        )
    elif stats.clamp_pct > config.clamp_warning_threshold * 100:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.WARNING,
                code="CLAMP_PCT",
                message=f"Curve clamps {stats.clamp_pct:.1f}% of samples",
                details={
                    "clamp_pct": stats.clamp_pct,
                    "threshold": config.clamp_warning_threshold * 100,
                },
            )
        )

    # Limited range
    if stats.range < 0.1:
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
    if stats.energy < 0.001 and stats.range < 0.01 and len(samples) > 1:
        flags.append(
            ReportFlag(
                level=ReportFlagLevel.INFO,
                code="STATIC_CURVE",
                message="Curve appears static or nearly static",
                details={"energy": stats.energy, "range": stats.range},
            )
        )

    return stats, flags


def check_loop_continuity(
    samples: list[float],
    threshold: float = 0.05,
) -> ContinuityCheck:
    """Check if curve is continuous at loop boundary.

    For repeatable templates, the curve should start and end at similar
    values to avoid discontinuities when looping.

    Args:
        samples: Curve sample values
        threshold: Maximum acceptable difference (normalized)

    Returns:
        ContinuityCheck with loop_delta and pass/fail status

    Example:
        >>> samples = [0.5, 0.6, 0.7, 0.51]  # Close loop
        >>> check = check_loop_continuity(samples, threshold=0.05)
        >>> check.ok
        True
    """
    if len(samples) < 2:
        return ContinuityCheck(loop_delta=0.0, ok=True, threshold=threshold)

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

    return (clamped / len(arr)) * 100 if len(arr) > 0 else 0.0


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
