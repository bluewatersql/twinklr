"""Write report outputs (JSON and Markdown).

This module handles serialization of the EvaluationReport to various formats.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from blinkb0t.core.reporting.evaluation.models import EvaluationReport, SectionReport

logger = logging.getLogger(__name__)


def write_report_json(report: EvaluationReport, output_path: Path) -> None:
    """Write report as JSON file.

    Args:
        report: EvaluationReport to serialize
        output_path: Path to write JSON file

    Example:
        >>> write_report_json(report, Path("output/report.json"))
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize with Path handling
    data = report.model_dump(mode="json")

    output_path.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )

    logger.info(f"Wrote report JSON: {output_path}")


def write_report_markdown(report: EvaluationReport, output_path: Path) -> None:
    """Write report as Markdown file.

    Args:
        report: EvaluationReport to render
        output_path: Path to write Markdown file

    Example:
        >>> write_report_markdown(report, Path("output/report.md"))
    """
    lines = []

    # Header
    lines.append(f"# Evaluation Report: {report.run.run_id}")
    lines.append("")
    lines.append(f"**Timestamp**: {report.run.timestamp}  ")
    lines.append(f"**Engine Version**: {report.run.engine_version}  ")
    lines.append(f"**Git SHA**: {report.run.git_sha or 'N/A'}  ")
    lines.append(
        f"**Status**: {report.summary.total_errors} errors, {report.summary.total_warnings} warnings"
    )
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Sections**: {report.summary.sections}")
    lines.append(f"- **Templates Used**: {', '.join(report.summary.templates_used)}")
    lines.append(f"- **Roles Targeted**: {', '.join(report.summary.roles_targeted)}")
    lines.append(f"- **Max Concurrent Layers**: {report.summary.max_concurrent_layers}")

    # Phase 2: Advanced metrics
    if report.summary.validation_errors > 0:
        lines.append(f"- **Validation Errors**: {report.summary.validation_errors} ❌")
    if report.summary.physics_violations > 0:
        lines.append(f"- **Physics Violations**: {report.summary.physics_violations} ⚠️")
    if report.summary.compliance_issues > 0:
        lines.append(f"- **Compliance Issues**: {report.summary.compliance_issues} ⚠️")
    if report.summary.harsh_transitions > 0:
        lines.append(f"- **Harsh Transitions**: {report.summary.harsh_transitions} ⚠️")

    lines.append("")

    # Song metadata
    lines.append("## Song Metadata")
    lines.append("")
    lines.append(f"- **BPM**: {report.song.bpm}")
    lines.append(f"- **Time Signature**: {report.song.time_signature}")
    lines.append(f"- **Total Bars**: {report.song.bars_total}")
    lines.append(f"- **Bar Duration**: {report.song.bar_duration_ms:.1f}ms")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    lines.append("## Section Analysis")
    lines.append("")

    for section in report.sections:
        lines.extend(_render_section_markdown(section))

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    logger.info(f"Wrote report Markdown: {output_path}")


def _render_section_markdown(section: SectionReport) -> list[str]:
    """Render single section as markdown lines.

    Args:
        section: SectionReport to render

    Returns:
        List of markdown lines
    """
    lines = []

    # Header
    start, end = section.bar_range
    lines.append(f"### {section.label} (bars {start:.1f}–{end:.1f})")
    lines.append("")

    # Template info
    if section.selected_template:
        t = section.selected_template
        preset_str = f" (preset: {t.preset_id})" if t.preset_id else ""
        lines.append(f"**Template**: `{t.template_id}`{preset_str}")
        lines.append("")

        if t.modifiers:
            lines.append("**Modifiers**:")
            for key, val in t.modifiers.items():
                lines.append(f"- {key}: {val}")
            lines.append("")

        if t.reasoning:
            lines.append(f"**Reasoning**: {t.reasoning}")
            lines.append("")

    # Segments
    if section.segments:
        lines.append(f"**Segments**: {len(section.segments)}")
        for seg in section.segments:
            preset_str = f" (preset: {seg.template.preset_id})" if seg.template.preset_id else ""
            lines.append(
                f"- Segment {seg.segment_id}: `{seg.template.template_id}`{preset_str} "
                f"(bars {seg.start_bar:.1f}–{seg.end_bar:.1f})"
            )
        lines.append("")

    # Curves
    if section.curves:
        # Group by role
        by_role: dict[str, list] = {}
        for curve in section.curves:
            by_role.setdefault(curve.role, []).append(curve)

        for role, curves in by_role.items():
            lines.append(f"**Curves ({role})**:")
            lines.append("")

            # Embed plots
            for curve in curves:
                if curve.plot_path:
                    # Make path relative to report.md location
                    try:
                        rel_path = Path(curve.plot_path).relative_to(
                            Path(curve.plot_path).parent.parent
                        )
                        lines.append(f"![{curve.channel}]({rel_path})")
                    except ValueError:
                        # Fallback to absolute
                        lines.append(f"![{curve.channel}]({curve.plot_path})")
            lines.append("")

            # Metrics table
            lines.append("**Metrics**:")
            for curve in curves:
                s = curve.stats
                cont = "✓" if curve.continuity.ok else f"✗ ({curve.continuity.loop_delta:.3f})"

                # Build metric line with curve metadata
                metric_parts = [
                    f"{curve.channel}",
                ]

                # Add curve type if available
                if curve.curve_type:
                    curve_display = curve.curve_type.replace("CurveKind.", "")
                    metric_parts.append(f"[{curve_display}]")

                # Add handler if available
                if curve.handler:
                    metric_parts.append(f"({curve.handler})")

                metric_line = " ".join(metric_parts) + ": "
                metric_line += (
                    f"min={s.min:.2f}, max={s.max:.2f}, range={s.range:.2f}, "
                    f"clamp={s.clamp_pct:.1f}%, energy={s.energy:.3f}, "
                    f"loop={cont}"
                )

                # Add base position for pan/tilt
                if curve.base_position is not None:
                    metric_line += f", base={curve.base_position:.2f}"

                # Add static DMX if applicable
                if curve.static_dmx is not None:
                    metric_line += f", static={curve.static_dmx}"

                # Phase 2: Add physics metrics
                if curve.physics_check:
                    pc = curve.physics_check
                    if not pc.speed_ok or not pc.acceleration_ok:
                        metric_line += " ⚠️"
                    metric_line += f", speed={pc.max_speed_deg_per_sec:.1f}°/s"
                    if pc.max_accel_deg_per_sec2 > 0:
                        metric_line += f", accel={pc.max_accel_deg_per_sec2:.0f}°/s²"

                lines.append(f"- {metric_line}")
            lines.append("")

    # Phase 2: Template compliance
    if section.template_compliance:
        tc = section.template_compliance
        lines.append("**Template Compliance**:")
        status = "✓ Compliant" if tc.overall_compliant else "✗ Issues Detected"
        lines.append(f"- Overall: {status}")
        lines.append(f"- Curve types: {'✓' if tc.curve_type_correct else '✗'}")
        lines.append(f"- Geometry: {'✓' if tc.geometry_correct else '✗'}")

        if tc.modifiers_compliant:
            compliant_count = sum(1 for m in tc.modifiers_compliant if m.compliant)
            lines.append(f"- Modifiers: {compliant_count}/{len(tc.modifiers_compliant)} compliant")

            # Show modifier details
            for mod in tc.modifiers_compliant:
                icon = "✓" if mod.compliant else "✗"
                lines.append(
                    f"  - {icon} `{mod.modifier_key}={mod.expected_value}`: {mod.actual_impact}"
                )

        if tc.issues:
            lines.append("")
            lines.append("**Compliance Issues**:")
            for issue in tc.issues:
                lines.append(f"- ⚠️ {issue}")

        lines.append("")

    # Validation issues
    if section.validation_issues:
        lines.append("**Validation Issues**:")
        for issue in section.validation_issues:
            lines.append(f"- ❌ {issue}")
        lines.append("")

    # Flags
    if section.flags:
        lines.append("**Flags**:")
        for flag in section.flags:
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(flag.level.value, "•")
            lines.append(f"- {icon} **{flag.code}**: {flag.message}")
        lines.append("")
    else:
        lines.append("**Flags**: None")
        lines.append("")

    # Phase 2: Transition to next section
    if section.transition_to_next:
        trans = section.transition_to_next
        lines.append(f"**Transition to {trans.to_section.replace('_', ' ').title()}**:")
        status = "✓ Smooth" if trans.smooth else "⚠️ Issues"
        lines.append(f"- Status: {status}")
        lines.append(
            f"- Position delta: pan={trans.position_delta_pan:.3f}, tilt={trans.position_delta_tilt:.3f}"
        )
        lines.append(f"- Velocity delta: {trans.velocity_delta:.3f}")
        if trans.dimmer_snap:
            lines.append("- Dimmer: ⚠️ Snap detected")

        if trans.issues:
            lines.append("")
            lines.append("**Transition Issues**:")
            for issue in trans.issues:
                lines.append(f"- ⚠️ {issue}")

        lines.append("")

    lines.append("---")
    lines.append("")

    return lines
