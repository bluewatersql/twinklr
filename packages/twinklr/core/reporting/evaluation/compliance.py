"""Template compliance verification for evaluation reports.

Verifies that rendered curves match expected template behavior:
- Curve types match template definitions
- Modifiers were applied correctly
- Geometry was applied as specified
"""

from __future__ import annotations

import logging
from typing import Any

from twinklr.core.reporting.evaluation.models import (
    CurveAnalysis,
    ModifierCompliance,
    TemplateCompliance,
)

logger = logging.getLogger(__name__)


def verify_template_compliance(
    template_id: str,
    modifiers: dict[str, str],
    curves: list[CurveAnalysis],
    metadata: dict[str, Any],
) -> TemplateCompliance:
    """Verify template compliance for a section.

    Args:
        template_id: Template identifier
        modifiers: Applied modifiers
        curves: Analyzed curves for the section
        metadata: Template and rendering metadata

    Returns:
        TemplateCompliance with verification results

    Example:
        >>> compliance = verify_template_compliance(
        ...     template_id="inner_pendulum_breathe",
        ...     modifiers={"tilt_range": "compact", "dimmer": "soft_breathe_3-4"},
        ...     curves=curves,
        ...     metadata={}
        ... )
        >>> compliance.overall_compliant
        True
    """
    issues: list[str] = []
    modifier_checks: list[ModifierCompliance] = []

    # 1. Verify curve types match expected
    curve_type_correct = _verify_curve_types(template_id, curves, issues)

    # 2. Verify modifiers were applied
    for modifier_key, modifier_value in modifiers.items():
        compliance = _verify_modifier(modifier_key, modifier_value, curves, issues)
        modifier_checks.append(compliance)

    # 3. Verify geometry application
    geometry_correct = _verify_geometry(curves, issues)

    # Overall compliance: all checks passed
    overall_compliant = (
        curve_type_correct
        and geometry_correct
        and all(m.compliant for m in modifier_checks)
        and len(issues) == 0
    )

    logger.debug(
        "Template compliance for %s: curve_types=%s, geometry=%s, modifiers=%d/%d, overall=%s",
        template_id,
        curve_type_correct,
        geometry_correct,
        sum(1 for m in modifier_checks if m.compliant),
        len(modifier_checks),
        overall_compliant,
    )

    return TemplateCompliance(
        template_id=template_id,
        curve_type_correct=curve_type_correct,
        modifiers_compliant=modifier_checks,
        geometry_correct=geometry_correct,
        overall_compliant=overall_compliant,
        issues=issues,
    )


def _verify_curve_types(
    template_id: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> bool:
    """Verify curves have expected types for the template.

    Args:
        template_id: Template identifier
        curves: Analyzed curves
        issues: List to append issues to

    Returns:
        True if curve types are correct
    """
    # Check that curves have curve_type metadata
    for curve in curves:
        if not curve.curve_type:
            issues.append(f"Missing curve type metadata for {curve.channel}")
            return False

        # Verify curve type is valid (not NONE or UNKNOWN)
        if "NONE" in curve.curve_type.upper() or "UNKNOWN" in curve.curve_type.upper():
            issues.append(f"Invalid curve type for {curve.channel}: {curve.curve_type}")
            return False

    return True


def _verify_modifier(
    modifier_key: str,
    modifier_value: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> ModifierCompliance:
    """Verify a modifier was applied correctly.

    Args:
        modifier_key: Modifier parameter name
        modifier_value: Expected value
        curves: Analyzed curves
        issues: List to append issues to

    Returns:
        ModifierCompliance with verification results
    """
    # Common modifier patterns
    if modifier_key in ["tilt_range", "pan_range"]:
        return _verify_range_modifier(modifier_key, modifier_value, curves, issues)
    elif modifier_key == "intensity":
        return _verify_intensity_modifier(modifier_value, curves, issues)
    elif modifier_key == "dimmer":
        return _verify_dimmer_modifier(modifier_value, curves, issues)
    elif modifier_key == "focus":
        return _verify_focus_modifier(modifier_value, curves, issues)
    else:
        # Generic modifier - just check it exists in metadata
        return ModifierCompliance(
            modifier_key=modifier_key,
            expected_value=modifier_value,
            actual_impact="Unknown modifier type",
            compliant=True,  # Don't fail on unknown modifiers
            notes=f"Modifier '{modifier_key}' not validated (unknown type)",
        )


def _verify_range_modifier(
    modifier_key: str,
    modifier_value: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> ModifierCompliance:
    """Verify tilt_range or pan_range modifier was applied.

    Expected: 'compact' -> smaller range, 'wide' -> larger range
    """
    channel = "tilt" if "tilt" in modifier_key else "pan"
    channel_curves = [c for c in curves if c.channel.lower() == channel]

    if not channel_curves:
        return ModifierCompliance(
            modifier_key=modifier_key,
            expected_value=modifier_value,
            actual_impact="No curves found for channel",
            compliant=False,
            notes=f"No {channel} curves to validate",
        )

    # Get average range across fixtures
    avg_range = sum(c.stats.range for c in channel_curves) / len(channel_curves)

    # Thresholds (normalized 0-1)
    if modifier_value == "compact":
        expected = "Small range (≤0.3)"
        compliant = avg_range <= 0.3
        actual_impact = f"Range={avg_range:.2f}"
    elif modifier_value == "wide":
        expected = "Large range (≥0.5)"
        compliant = avg_range >= 0.5
        actual_impact = f"Range={avg_range:.2f}"
    else:
        expected = f"Range appropriate for '{modifier_value}'"
        compliant = True  # Unknown range type, assume OK
        actual_impact = f"Range={avg_range:.2f}"

    if not compliant:
        issues.append(f"Range modifier '{modifier_value}' not applied: {actual_impact}")

    return ModifierCompliance(
        modifier_key=modifier_key,
        expected_value=modifier_value,
        actual_impact=actual_impact,
        compliant=compliant,
        notes=expected,
    )


def _verify_intensity_modifier(
    modifier_value: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> ModifierCompliance:
    """Verify intensity modifier affects movement energy.

    Expected: SMOOTH -> low energy, DYNAMIC -> high energy
    """
    # Get pan/tilt curves
    movement_curves = [c for c in curves if c.channel.lower() in ["pan", "tilt"]]

    if not movement_curves:
        return ModifierCompliance(
            modifier_key="intensity",
            expected_value=modifier_value,
            actual_impact="No movement curves found",
            compliant=False,
        )

    # Average energy
    avg_energy = sum(c.stats.energy for c in movement_curves) / len(movement_curves)

    # Thresholds for energy (mean absolute derivative)
    if modifier_value.upper() == "SMOOTH":
        expected = "Low energy (≤0.002)"
        compliant = avg_energy <= 0.002
        actual_impact = f"Energy={avg_energy:.4f}"
    elif modifier_value.upper() == "DYNAMIC":
        expected = "High energy (≥0.005)"
        compliant = avg_energy >= 0.005
        actual_impact = f"Energy={avg_energy:.4f}"
    else:
        expected = f"Energy appropriate for '{modifier_value}'"
        compliant = True
        actual_impact = f"Energy={avg_energy:.4f}"

    if not compliant:
        issues.append(f"Intensity '{modifier_value}' not reflected in energy: {actual_impact}")

    return ModifierCompliance(
        modifier_key="intensity",
        expected_value=modifier_value,
        actual_impact=actual_impact,
        compliant=compliant,
        notes=expected,
    )


def _verify_dimmer_modifier(
    modifier_value: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> ModifierCompliance:
    """Verify dimmer modifier was applied.

    Expected: dimmer curve type matches the modifier pattern
    """
    dimmer_curves = [c for c in curves if c.channel.lower() == "dimmer"]

    if not dimmer_curves:
        return ModifierCompliance(
            modifier_key="dimmer",
            expected_value=modifier_value,
            actual_impact="No dimmer curves found",
            compliant=False,
        )

    # Check curve type contains expected pattern
    curve_types = [c.curve_type for c in dimmer_curves if c.curve_type]

    if not curve_types:
        return ModifierCompliance(
            modifier_key="dimmer",
            expected_value=modifier_value,
            actual_impact="Missing dimmer curve type",
            compliant=False,
        )

    # Look for key pattern in modifier value (e.g., "breathe", "pulse", "strobe")
    patterns = ["breathe", "pulse", "strobe", "fade", "hold"]
    expected_pattern = next((p for p in patterns if p in modifier_value.lower()), None)

    if expected_pattern:
        found = any(expected_pattern.upper() in ct.upper() for ct in curve_types)
        compliant = found
        actual_impact = f"Curve types: {', '.join(curve_types)}"

        if not compliant:
            issues.append(
                f"Dimmer pattern '{expected_pattern}' not found in curve types: {curve_types}"
            )
    else:
        # No recognizable pattern, assume OK
        compliant = True
        actual_impact = f"Curve types: {', '.join(curve_types)}"

    return ModifierCompliance(
        modifier_key="dimmer",
        expected_value=modifier_value,
        actual_impact=actual_impact,
        compliant=compliant,
        notes=f"Expected pattern: {expected_pattern}" if expected_pattern else "No pattern check",
    )


def _verify_focus_modifier(
    modifier_value: str,
    curves: list[CurveAnalysis],
    issues: list[str],
) -> ModifierCompliance:
    """Verify focus modifier (e.g., 'center-weighted', 'audience-facing').

    This affects geometry/base positions.
    """
    # Check base positions are reasonable
    pan_curves = [c for c in curves if c.channel.lower() == "pan" and c.base_position is not None]

    if not pan_curves:
        return ModifierCompliance(
            modifier_key="focus",
            expected_value=modifier_value,
            actual_impact="No pan base positions found",
            compliant=True,  # Don't fail if no base position data
            notes="Unable to verify focus (no base positions)",
        )

    avg_base_pan = sum(c.base_position for c in pan_curves if c.base_position) / len(pan_curves)

    # Rough heuristics
    if "center" in modifier_value.lower():
        expected = "Center position (0.4-0.6)"
        compliant = 0.4 <= avg_base_pan <= 0.6
        actual_impact = f"Base pan={avg_base_pan:.2f}"
    else:
        expected = f"Position appropriate for '{modifier_value}'"
        compliant = True
        actual_impact = f"Base pan={avg_base_pan:.2f}"

    if not compliant:
        issues.append(f"Focus '{modifier_value}' not reflected in positions: {actual_impact}")

    return ModifierCompliance(
        modifier_key="focus",
        expected_value=modifier_value,
        actual_impact=actual_impact,
        compliant=compliant,
        notes=expected,
    )


def _verify_geometry(
    curves: list[CurveAnalysis],
    issues: list[str],
) -> bool:
    """Verify geometry was applied (fixtures have handlers and base positions).

    Args:
        curves: Analyzed curves
        issues: List to append issues to

    Returns:
        True if geometry appears correctly applied
    """
    # Check that movement curves have handlers
    movement_curves = [c for c in curves if c.channel.lower() in ["pan", "tilt"]]

    if not movement_curves:
        return True  # No movement curves to check

    # All movement curves should have a handler
    missing_handler = [c for c in movement_curves if not c.handler]
    if missing_handler:
        issues.append(f"{len(missing_handler)} curves missing handler metadata")
        return False

    # Pan/tilt curves should have base positions
    missing_base = [
        c
        for c in movement_curves
        if c.channel.lower() in ["pan", "tilt"] and c.base_position is None
    ]
    if missing_base:
        issues.append(f"{len(missing_base)} curves missing base position")
        return False

    return True
