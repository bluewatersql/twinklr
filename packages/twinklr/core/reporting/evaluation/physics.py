"""Physical constraint validation for DMX curves.

Validates curves against real-world moving head limitations:
- Maximum pan/tilt speed
- Maximum acceleration
- Minimum settle time
- DMX update rate resolution
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.models import PhysicsCheck

logger = logging.getLogger(__name__)


def check_physics_constraints(
    samples: list[float],
    channel: Literal["pan", "tilt", "dimmer"],
    duration_ms: float,
    config: EvalConfig,
    pan_range_deg: float = 540.0,
    tilt_range_deg: float = 270.0,
) -> PhysicsCheck:
    """Check physical constraints for a curve.

    Args:
        samples: DMX values (0-255) sampled at regular intervals
        channel: Channel type (pan, tilt, dimmer)
        duration_ms: Total duration of the curve in milliseconds
        config: Evaluation configuration with physics limits
        pan_range_deg: Physical pan range in degrees (default: 540°)
        tilt_range_deg: Physical tilt range in degrees (default: 270°)

    Returns:
        PhysicsCheck with validation results

    Example:
        >>> samples = [0, 127, 255, 127, 0]
        >>> check = check_physics_constraints(samples, "pan", 1000, config)
        >>> check.speed_ok
        True
    """
    if len(samples) < 2:
        # Not enough samples to compute derivatives
        return PhysicsCheck(
            speed_ok=True,
            acceleration_ok=True,
            max_speed_deg_per_sec=0.0,
            max_accel_deg_per_sec2=0.0,
            violations=[],
        )

    # Convert to numpy for numerical operations
    dmx_values = np.array(samples)
    n_samples = len(samples)
    dt_ms = duration_ms / (n_samples - 1)  # Time between samples
    dt_sec = dt_ms / 1000.0

    # Convert DMX (0-255) to normalized (0-1) to degrees
    if channel == "pan":
        range_deg = pan_range_deg
        max_speed_limit = config.max_pan_speed_deg_per_sec
    elif channel == "tilt":
        range_deg = tilt_range_deg
        max_speed_limit = config.max_tilt_speed_deg_per_sec
    else:  # dimmer
        # Dimmer doesn't have physical movement constraints
        return PhysicsCheck(
            speed_ok=True,
            acceleration_ok=True,
            max_speed_deg_per_sec=0.0,
            max_accel_deg_per_sec2=0.0,
            violations=[],
        )

    # Normalize DMX to 0-1, then scale to degrees
    normalized = dmx_values / 255.0  # type: ignore[operator]
    position_deg = normalized * range_deg

    # Compute velocity (degrees/second)
    velocity = np.diff(position_deg) / dt_sec  # type: ignore[operator]
    max_speed = float(np.max(np.abs(velocity)))

    # Compute acceleration (degrees/second²)
    acceleration = np.diff(velocity) / dt_sec  # type: ignore[operator]
    max_accel = float(np.max(np.abs(acceleration))) if len(acceleration) > 0 else 0.0

    # Check constraints
    violations: list[str] = []
    speed_ok = True
    acceleration_ok = True

    if max_speed > max_speed_limit:
        speed_ok = False
        violations.append(f"Speed {max_speed:.1f}°/s exceeds limit {max_speed_limit:.1f}°/s")

    if max_accel > config.max_acceleration_deg_per_sec2:
        acceleration_ok = False
        violations.append(
            f"Acceleration {max_accel:.1f}°/s² exceeds limit {config.max_acceleration_deg_per_sec2:.1f}°/s²"
        )

    logger.debug(
        "Physics check %s: speed=%.1f°/s (limit=%.1f), accel=%.1f°/s² (limit=%.1f)",
        channel,
        max_speed,
        max_speed_limit,
        max_accel,
        config.max_acceleration_deg_per_sec2,
    )

    return PhysicsCheck(
        speed_ok=speed_ok,
        acceleration_ok=acceleration_ok,
        max_speed_deg_per_sec=max_speed,
        max_accel_deg_per_sec2=max_accel,
        violations=violations,
    )


def check_settle_time(
    samples: list[float],
    duration_ms: float,
    config: EvalConfig,
) -> list[str]:
    """Check if positions are held long enough to settle.

    Args:
        samples: DMX values (0-255)
        duration_ms: Total duration
        config: Evaluation configuration

    Returns:
        List of settle time warnings

    Example:
        >>> warnings = check_settle_time([0, 0, 255, 255], 100, config)
        >>> len(warnings)
        0
    """
    if len(samples) < 2:
        return []

    dmx_values = np.array(samples)
    n_samples = len(samples)
    dt_ms = duration_ms / (n_samples - 1)

    warnings: list[str] = []

    # Find runs of identical values (settled positions)
    diff = np.diff(dmx_values)
    is_static = np.abs(diff) < 1.0  # Within 1 DMX unit = settled

    # Find continuous settled regions
    settled_start = None
    for i, static in enumerate(is_static):
        if static and settled_start is None:
            settled_start = i
        elif not static and settled_start is not None:
            # End of settled region
            settled_duration_ms = (i - settled_start) * dt_ms
            if settled_duration_ms < config.min_settle_time_ms:
                warnings.append(
                    f"Position held for only {settled_duration_ms:.1f}ms (minimum: {config.min_settle_time_ms:.1f}ms)"
                )
            settled_start = None

    return warnings


def check_dmx_resolution(
    samples: list[float],
    sample_rate_hz: float,
    config: EvalConfig,
) -> list[str]:
    """Check if curve changes are too fast for DMX update rate.

    Standard DMX refresh rate is ~44Hz. Curves changing faster than this
    may experience aliasing or choppy movement.

    Args:
        samples: DMX values
        sample_rate_hz: Sampling rate of the curve data
        config: Evaluation configuration

    Returns:
        List of resolution warnings
    """
    warnings: list[str] = []

    dmx_update_rate = 44.0  # Standard DMX512 refresh rate

    if sample_rate_hz > dmx_update_rate * 2:
        # Nyquist: need 2x sampling rate to avoid aliasing
        warnings.append(
            f"Curve sampled at {sample_rate_hz:.1f}Hz may alias with DMX rate ({dmx_update_rate:.1f}Hz)"
        )

    return warnings
