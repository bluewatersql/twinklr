#!/usr/bin/env python3
"""Audit built-in templates for categorical parameter usage.

This script analyzes all built-in templates to understand how they use
categorical parameters (amplitude, frequency, center_offset) and identifies
templates that might benefit from overrides.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ruff: noqa: E402 - Module imports after sys.path modification for standalone script
from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.moving_heads.libraries.movement import (
    MovementLibrary,
    MovementType,
)

if TYPE_CHECKING:
    from twinklr.core.sequencer.models.template import Movement, TemplateDoc


def get_curve_for_movement(movement_type: MovementType) -> CurveLibrary:
    """Get the primary curve used by a movement type.

    Args:
        movement_type: Movement type to look up

    Returns:
        Primary curve library ID (pan curve)
    """
    if movement_type in MovementLibrary.PATTERNS:
        pattern = MovementLibrary.PATTERNS[movement_type]
        return pattern.pan_curve
    return CurveLibrary.MOVEMENT_HOLD  # Default fallback


def analyze_movement(movement: Movement, step_id: str, template_id: str) -> dict[str, Any]:
    """Analyze a movement for categorical parameter usage.

    Args:
        movement: Movement to analyze
        step_id: Step identifier
        template_id: Template identifier

    Returns:
        Analysis results dictionary
    """
    # Get the curve this movement uses
    curve_id = get_curve_for_movement(movement.movement_type)

    # Get the categorical params that would be used
    params = movement.get_categorical_params(curve_id)

    # Check if any overrides are set
    has_overrides = (
        movement.amplitude_override is not None
        or movement.frequency_override is not None
        or movement.center_offset_override is not None
    )

    return {
        "template_id": template_id,
        "step_id": step_id,
        "movement_type": movement.movement_type.value,
        "intensity": movement.intensity.value,
        "curve_id": curve_id.value,
        "amplitude": params.amplitude,
        "frequency": params.frequency,
        "center_offset": params.center_offset,
        "has_overrides": has_overrides,
        "amplitude_override": movement.amplitude_override,
        "frequency_override": movement.frequency_override,
        "center_offset_override": movement.center_offset_override,
        "cycles": movement.cycles,
    }


def audit_template(template_doc: TemplateDoc) -> list[dict[str, Any]]:
    """Audit a single template for categorical parameter usage.

    Args:
        template_doc: Template document to audit

    Returns:
        List of movement analysis results
    """
    template = template_doc.template
    results = []

    for step in template.steps:
        if step.movement.movement_type != MovementType.NONE:
            result = analyze_movement(step.movement, step.step_id, template.template_id)
            results.append(result)

    return results


def generate_report(all_results: list[dict[str, Any]]) -> str:
    """Generate markdown report from audit results.

    Args:
        all_results: All movement analysis results

    Returns:
        Markdown report string
    """
    report = []
    report.append("# Built-in Template Categorical Parameters Audit")
    report.append("")
    report.append("## Overview")
    report.append("")

    # Summary statistics
    total_movements = len(all_results)
    total_templates = len({r["template_id"] for r in all_results})
    movements_with_overrides = sum(1 for r in all_results if r["has_overrides"])

    report.append(f"- **Total Templates**: {total_templates}")
    report.append(f"- **Total Movements**: {total_movements}")
    report.append(
        f"- **Movements with Overrides**: {movements_with_overrides} "
        f"({100 * movements_with_overrides / total_movements:.1f}%)"
    )
    report.append("")

    # Intensity distribution
    report.append("## Intensity Distribution")
    report.append("")
    intensity_counts = {}
    for result in all_results:
        intensity = result["intensity"]
        intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

    report.append("| Intensity | Count | Percentage |")
    report.append("|-----------|-------|------------|")
    for intensity in sorted(intensity_counts.keys()):
        count = intensity_counts[intensity]
        pct = 100 * count / total_movements
        report.append(f"| {intensity} | {count} | {pct:.1f}% |")
    report.append("")

    # Movement type distribution
    report.append("## Movement Type Distribution")
    report.append("")
    movement_counts = {}
    for result in all_results:
        movement = result["movement_type"]
        movement_counts[movement] = movement_counts.get(movement, 0) + 1

    report.append("| Movement Type | Count | Percentage |")
    report.append("|---------------|-------|------------|")
    for movement in sorted(movement_counts.keys(), key=lambda x: movement_counts[x], reverse=True)[
        :10
    ]:
        count = movement_counts[movement]
        pct = 100 * count / total_movements
        report.append(f"| {movement} | {count} | {pct:.1f}% |")
    report.append("")
    if len(movement_counts) > 10:
        report.append(f"_... and {len(movement_counts) - 10} more movement types_")
        report.append("")

    # Curve usage
    report.append("## Curve Usage")
    report.append("")
    curve_counts = {}
    for result in all_results:
        curve = result["curve_id"]
        curve_counts[curve] = curve_counts.get(curve, 0) + 1

    report.append("| Curve | Count | Percentage |")
    report.append("|-------|-------|------------|")
    for curve in sorted(curve_counts.keys(), key=lambda x: curve_counts[x], reverse=True):
        count = curve_counts[curve]
        pct = 100 * count / total_movements
        report.append(f"| {curve} | {count} | {pct:.1f}% |")
    report.append("")

    # Parameter ranges
    report.append("## Parameter Ranges")
    report.append("")

    amplitudes = [r["amplitude"] for r in all_results]
    frequencies = [r["frequency"] for r in all_results]

    report.append(
        f"- **Amplitude**: min={min(amplitudes):.2f}, max={max(amplitudes):.2f}, avg={sum(amplitudes) / len(amplitudes):.2f}"
    )
    report.append(
        f"- **Frequency**: min={min(frequencies):.2f}, max={max(frequencies):.2f}, avg={sum(frequencies) / len(frequencies):.2f}"
    )
    report.append("")

    # Detailed results by template
    report.append("## Detailed Results by Template")
    report.append("")

    # Group by template
    by_template = {}
    for result in all_results:
        template_id = result["template_id"]
        if template_id not in by_template:
            by_template[template_id] = []
        by_template[template_id].append(result)

    for template_id in sorted(by_template.keys()):
        results = by_template[template_id]
        report.append(f"### {template_id}")
        report.append("")

        report.append("| Step | Movement | Intensity | Curve | Amplitude | Frequency | Overrides |")
        report.append("|------|----------|-----------|-------|-----------|-----------|-----------|")

        for result in results:
            overrides = []
            if result["amplitude_override"] is not None:
                overrides.append(f"A={result['amplitude_override']:.2f}")
            if result["frequency_override"] is not None:
                overrides.append(f"F={result['frequency_override']:.2f}")
            if result["center_offset_override"] is not None:
                overrides.append(f"C={result['center_offset_override']:.2f}")
            override_str = ", ".join(overrides) if overrides else "None"

            report.append(
                f"| {result['step_id']} "
                f"| {result['movement_type']} "
                f"| {result['intensity']} "
                f"| {result['curve_id'].replace('MOVEMENT_', '')} "
                f"| {result['amplitude']:.2f} "
                f"| {result['frequency']:.2f} "
                f"| {override_str} |"
            )

        report.append("")

    # Recommendations
    report.append("## Recommendations")
    report.append("")

    if movements_with_overrides == 0:
        report.append("✅ **No templates currently use overrides**")
        report.append("")
        report.append("This is expected since overrides were just added. Consider:")
        report.append("- Testing templates at all intensity levels")
        report.append("- Identifying templates that might benefit from fine-tuning")
        report.append("- Adding overrides where needed for artistic intent")
    else:
        report.append(f"✅ **{movements_with_overrides} movements already use overrides**")
        report.append("")
        report.append("Review these templates to ensure overrides are appropriate.")

    report.append("")
    report.append("### Next Steps")
    report.append("")
    report.append("1. **Visual Testing**: Test templates at each intensity level")
    report.append("2. **Parameter Validation**: Verify params produce desired effects")
    report.append("3. **Override Candidates**: Identify templates needing fine-tuning")
    report.append("4. **Documentation**: Document override rationale")
    report.append("")

    return "\n".join(report)


def main():
    """Run the audit on all built-in templates."""
    print("Auditing built-in templates...")
    print()

    # Import all built-in templates to trigger registration
    from twinklr.core.sequencer.moving_heads.templates import builtins  # noqa: F401

    # Get all registered templates
    from twinklr.core.sequencer.moving_heads.templates.library import (
        get_template,
        list_templates,
    )

    all_results = []

    for template_info in sorted(list_templates(), key=lambda x: x.template_id):
        template_id = template_info.template_id
        print(f"Analyzing: {template_id}")
        try:
            template_doc = get_template(template_id)
            results = audit_template(template_doc)
            all_results.extend(results)
        except Exception as e:
            print(f"  ERROR: {e}")

    print()
    print(
        f"Analyzed {len(all_results)} movements from {len({r['template_id'] for r in all_results})} templates"
    )
    print()

    # Generate report
    report = generate_report(all_results)

    # Write to file
    output_path = (
        Path(__file__).parent.parent / "changes" / "vnext" / "optimization" / "TEMPLATE_AUDIT.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)

    print(f"Report written to: {output_path}")
    print()
    print("Summary:")
    print(f"- Total templates: {len({r['template_id'] for r in all_results})}")
    print(f"- Total movements: {len(all_results)}")
    print(f"- Movements with overrides: {sum(1 for r in all_results if r['has_overrides'])}")


if __name__ == "__main__":
    main()
