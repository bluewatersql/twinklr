"""Cross-section continuity analysis for evaluation reports.

Analyzes transitions between sections to detect:
- Position discontinuities (sudden jumps)
- Velocity discontinuities (sudden speed changes)
- Dimmer snaps (abrupt brightness changes)
"""

from __future__ import annotations

import logging

import numpy as np

from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.models import TransitionAnalysis

logger = logging.getLogger(__name__)


def analyze_section_transition(
    from_section_name: str,
    to_section_name: str,
    from_curves: dict[str, dict[str, list[float]]],  # role -> channel -> samples
    to_curves: dict[str, dict[str, list[float]]],
    config: EvalConfig,
) -> TransitionAnalysis:
    """Analyze transition between two sections.

    Args:
        from_section_name: Name of source section
        to_section_name: Name of destination section
        from_curves: Curves from end of source section (by role and channel)
        to_curves: Curves from start of destination section (by role and channel)
        config: Evaluation configuration

    Returns:
        TransitionAnalysis with discontinuity metrics

    Example:
        >>> transition = analyze_section_transition(
        ...     "verse_1",
        ...     "chorus_1",
        ...     {"OUTER_LEFT": {"pan": [10, 20, 30], "tilt": [50, 50, 50]}},
        ...     {"OUTER_LEFT": {"pan": [30, 40, 50], "tilt": [50, 60, 70]}},
        ...     config
        ... )
        >>> transition.smooth
        True
    """
    issues: list[str] = []

    # Get common roles between sections
    common_roles = set(from_curves.keys()) & set(to_curves.keys())

    if not common_roles:
        # No common roles to check
        return TransitionAnalysis(
            from_section=from_section_name,
            to_section=to_section_name,
            position_delta_pan=0.0,
            position_delta_tilt=0.0,
            velocity_delta=0.0,
            dimmer_snap=False,
            smooth=True,
            issues=["No common fixtures between sections"],
        )

    # Analyze each role
    max_pan_delta = 0.0
    max_tilt_delta = 0.0
    max_velocity_delta = 0.0
    dimmer_snap_detected = False

    for role in common_roles:
        from_role_curves = from_curves[role]
        to_role_curves = to_curves[role]

        # Check pan position continuity
        if "pan" in from_role_curves and "pan" in to_role_curves:
            pan_delta = _check_position_continuity(
                from_role_curves["pan"],
                to_role_curves["pan"],
                "pan",
                role,
                config,
                issues,
            )
            max_pan_delta = max(max_pan_delta, pan_delta)

            # Check pan velocity continuity
            velocity_delta = _check_velocity_continuity(
                from_role_curves["pan"],
                to_role_curves["pan"],
                "pan",
                role,
                config,
                issues,
            )
            max_velocity_delta = max(max_velocity_delta, velocity_delta)

        # Check tilt position continuity
        if "tilt" in from_role_curves and "tilt" in to_role_curves:
            tilt_delta = _check_position_continuity(
                from_role_curves["tilt"],
                to_role_curves["tilt"],
                "tilt",
                role,
                config,
                issues,
            )
            max_tilt_delta = max(max_tilt_delta, tilt_delta)

            # Check tilt velocity continuity
            velocity_delta = _check_velocity_continuity(
                from_role_curves["tilt"],
                to_role_curves["tilt"],
                "tilt",
                role,
                config,
                issues,
            )
            max_velocity_delta = max(max_velocity_delta, velocity_delta)

        # Check dimmer snap
        if "dimmer" in from_role_curves and "dimmer" in to_role_curves:
            snap = _check_dimmer_snap(
                from_role_curves["dimmer"],
                to_role_curves["dimmer"],
                role,
                config,
                issues,
            )
            dimmer_snap_detected = dimmer_snap_detected or snap

    # Overall smoothness assessment
    smooth = len(issues) == 0

    logger.debug(
        "Transition %s -> %s: pan_Δ=%.3f, tilt_Δ=%.3f, vel_Δ=%.3f, dimmer_snap=%s, smooth=%s",
        from_section_name,
        to_section_name,
        max_pan_delta,
        max_tilt_delta,
        max_velocity_delta,
        dimmer_snap_detected,
        smooth,
    )

    return TransitionAnalysis(
        from_section=from_section_name,
        to_section=to_section_name,
        position_delta_pan=max_pan_delta,
        position_delta_tilt=max_tilt_delta,
        velocity_delta=max_velocity_delta,
        dimmer_snap=dimmer_snap_detected,
        smooth=smooth,
        issues=issues,
    )


def _check_position_continuity(
    from_samples: list[float],
    to_samples: list[float],
    channel: str,
    role: str,
    config: EvalConfig,
    issues: list[str],
) -> float:
    """Check position continuity at section boundary.

    Args:
        from_samples: DMX samples from end of first section
        to_samples: DMX samples from start of second section
        channel: Channel name (pan/tilt)
        role: Fixture role
        config: Configuration
        issues: List to append issues to

    Returns:
        Position delta (normalized 0-1)
    """
    if not from_samples or not to_samples:
        return 0.0

    # Get last position of first section and first position of second section
    last_pos_dmx = from_samples[-1]
    first_pos_dmx = to_samples[0]

    # Normalize to 0-1
    last_pos_norm = last_pos_dmx / 255.0
    first_pos_norm = first_pos_dmx / 255.0

    delta = abs(first_pos_norm - last_pos_norm)

    if delta > config.position_discontinuity_threshold:
        issues.append(
            f"{role} {channel} discontinuity: {delta:.3f} (threshold: {config.position_discontinuity_threshold:.3f})"
        )

    return delta


def _check_velocity_continuity(
    from_samples: list[float],
    to_samples: list[float],
    channel: str,
    role: str,
    config: EvalConfig,
    issues: list[str],
) -> float:
    """Check velocity continuity at section boundary.

    Args:
        from_samples: DMX samples from end of first section
        to_samples: DMX samples from start of second section
        channel: Channel name
        role: Fixture role
        config: Configuration
        issues: List to append issues to

    Returns:
        Velocity delta (normalized per second)
    """
    if len(from_samples) < 2 or len(to_samples) < 2:
        return 0.0

    # Estimate velocity at boundary (slope of last/first few points)
    from_velocity = _estimate_velocity(from_samples[-5:])  # Last 5 samples
    to_velocity = _estimate_velocity(to_samples[:5])  # First 5 samples

    delta = abs(to_velocity - from_velocity)

    if delta > config.velocity_discontinuity_threshold:
        issues.append(
            f"{role} {channel} velocity change: {delta:.3f}/s (threshold: {config.velocity_discontinuity_threshold:.3f})"
        )

    return delta


def _estimate_velocity(samples: list[float]) -> float:
    """Estimate velocity from samples using linear regression.

    Args:
        samples: DMX samples

    Returns:
        Velocity estimate (normalized per sample)
    """
    if len(samples) < 2:
        return 0.0

    # Normalize to 0-1
    normalized = np.array(samples) / 255.0

    # Linear fit: y = mx + b, where m is velocity
    x = np.arange(len(normalized))
    if len(x) > 1:
        coeffs = np.polyfit(x, normalized, deg=1)
        velocity = float(coeffs[0])  # Slope
        return abs(velocity)

    return 0.0


def _check_dimmer_snap(
    from_samples: list[float],
    to_samples: list[float],
    role: str,
    config: EvalConfig,
    issues: list[str],
) -> bool:
    """Check for dimmer snap at boundary.

    Args:
        from_samples: DMX samples from end of first section
        to_samples: DMX samples from start of second section
        role: Fixture role
        config: Configuration
        issues: List to append issues to

    Returns:
        True if snap detected
    """
    if not from_samples or not to_samples:
        return False

    last_dimmer_dmx = from_samples[-1]
    first_dimmer_dmx = to_samples[0]

    # Normalize
    last_dimmer_norm = last_dimmer_dmx / 255.0
    first_dimmer_norm = first_dimmer_dmx / 255.0

    delta = abs(first_dimmer_norm - last_dimmer_norm)

    if delta > config.dimmer_snap_threshold:
        issues.append(
            f"{role} dimmer snap: {delta:.3f} (threshold: {config.dimmer_snap_threshold:.3f})"
        )
        return True

    return False
