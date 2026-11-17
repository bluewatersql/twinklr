"""Write report outputs (JSON and Markdown).

This module handles serialization of the EvaluationReport to various formats.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from twinklr.core.reporting.evaluation.models import (
    EvaluationReport,
    PhysicalRenderSummary,
    SectionReport,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from twinklr.core.reporting.evaluation.three_arm import ComparisonReport

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

    logger.debug(f"Wrote report JSON: {output_path}")


def write_vision_evaluation_json(result: BaseModel, output_path: Path) -> None:
    """Write the vision+deterministic producer through the evaluation writer seam."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    logger.debug("Wrote vision evaluation JSON: %s", output_path)


def write_comparison_report_json(report: ComparisonReport, output_path: Path) -> None:
    """Serialize the typed P2P-T13 comparison through the evaluation writer seam."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.model_dump(mode="json", exclude_computed_fields=True), indent=2),
        encoding="utf-8",
    )
    logger.debug("Wrote comparison report JSON: %s", output_path)


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

    # Add note about which roles have curves plotted
    roles_with_curves = set()
    for section in report.sections:
        for curve in section.curves:
            roles_with_curves.add(curve.role)
    if roles_with_curves:
        if len(roles_with_curves) < len(report.summary.roles_targeted):
            lines.append(
                f"- **Curves Plotted For**: {', '.join(sorted(roles_with_curves))} *(showing subset of roles)*"
            )
        else:
            lines.append("- **Curves Plotted For**: All roles")

    lines.append(f"- **Max Concurrent Layers**: {report.summary.max_concurrent_layers}")

    # Phase 2: Advanced metrics
    if report.summary.validation_errors > 0:
        lines.append(f"- **Validation Errors**: {report.summary.validation_errors} ❌")

    lines.append("")

    lines.extend(_render_physical_markdown(report.physical))

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

    logger.debug(f"Wrote report Markdown: {output_path}")


def _render_physical_markdown(physical: PhysicalRenderSummary) -> list[str]:
    """The physical render block: identity and the gate's facts."""
    lines = ["## Physical render", ""]
    if physical.fingerprint_matches:
        lines.append(f"- **Render fingerprint**: `{physical.rerender_fingerprint}` (the run's) ✓")
    else:
        lines.append(
            f"- **Render fingerprint**: ❌ the re-render's `{physical.rerender_fingerprint}` "
            f"does not match the run's `{physical.run_fingerprint}`; the metrics describe the "
            "re-render, not the delivered sequence"
        )
        for input_name in physical.mismatched_inputs:
            lines.append(f"  - differs: {input_name}")
    if physical.dark_spans:
        lines.append(
            f"- **Dark spans**: {len(physical.dark_spans)}, {physical.dark_span_ms} ms in all: "
            "the show's coordination rests the heads there while another target plays; "
            "they keep moving on their authored paths, commanded dark, so `lit` figures "
            "leave those frames out and the others count them"
        )
    for exclusion in physical.admission_exclusions:
        lines.append(f"- **Not offered**: `{exclusion['template_id']}`: {exclusion['reason']}")
    for exclusion in physical.admission_preset_exclusions:
        variant = exclusion["preset_id"] or "base"
        lines.append(
            f"- **Variant not admitted**: `{exclusion['template_id']}` {variant}: "
            f"{exclusion['reason']}"
        )
    for template_id, preset_id in physical.admission_effective_presets.items():
        lines.append(f"- **Effective variant**: `{template_id}` plays preset `{preset_id}`")
    for code, total in physical.unplayable_totals.items():
        lines.append(
            f"- **Kept dark as unplayable** ({code}): {total['cues']} cue(s), "
            f"{total['frames']} frame(s)"
        )
    lines.append("")
    lines.append(
        "Values are read from the encoded frames: pan, tilt and zoom in degrees; `dimmer` "
        "is the emitted intensity, the dimmer's value or 0 where the shutter extinguishes; "
        "`rate` is the mean rate of change per second. Range and rate count every frame, "
        "so they include the heads' dark repositioning; `lit range` and `lit rate` count "
        "only lit frames (intensity above 0), the motion an audience sees. Each section "
        "lists every head's largest step between two frames (lit frames for pan, tilt "
        "and zoom) and, for a head that plays through the boundary (entry `skipped`), the "
        "change from its last lit frame before the section; a lit step beyond the head's "
        "travel speed plus one DMX word is flagged `LIT_STEP_EXCEEDS_TRAVEL`. That bound is "
        "per frame on commanded values, so it is necessary, not sufficient: it does not "
        "detect sustained overspeed of up to one word per frame, nor a reveal before the "
        "head has finished travelling or settling."
    )
    lines.append("")
    return lines


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
                # Values in the channel's unit, rate per second.
                unit = "°" if curve.space == "degree" else ""
                lines.append(
                    f"- {curve.channel} ({curve.space}): min={s.min:.2f}{unit}, "
                    f"max={s.max:.2f}{unit}, range={s.range:.2f}{unit}, "
                    f"mean={s.mean:.3f}{unit}, std={s.std:.3f}{unit}, "
                    f"rate={s.energy:.3f}{unit}/s"
                    + (
                        f", lit range={curve.lit_range:.2f}{unit}, "
                        f"lit rate={curve.lit_rate:.3f}{unit}/s"
                        if curve.lit_range is not None and curve.lit_rate is not None
                        else ""
                    )
                )
            lines.append("")

    facts = section.render_facts
    lines.append("**Render facts**:")
    for window in facts.entry_windows:
        lines.append(
            f"- Entry {window['fixture_id']}: {window['action']}"
            + (f", dark for {window['window_ms']} ms" if window["window_ms"] is not None else "")
        )
    transactions = ", ".join(f"{status}: {n}" for status, n in facts.transactions.items())
    lines.append(f"- Transactions: {transactions or 'none'}")
    for cue in facts.dropped_cues:
        lines.append(
            f"- Kept dark: {cue['fixture_id']} step {cue.get('step_id')!r} "
            f"({cue['reason']}{', ' + str(cue['code']) if 'code' in cue else ''})"
        )
    for label, steps in (
        ("Largest step", facts.lit_steps),
        ("Across the boundary", facts.boundary_steps),
    ):
        for step in steps:
            unit = "" if step.channel == "dimmer" else "°"
            allowed = (
                ""
                if step.allowed is None
                else f" (travel plus one DMX word allows {step.allowed:.2f}°)"
            )
            lines.append(
                f"- {label}: {step.fixture_id} {step.channel} {step.change:+.2f}{unit} "
                f"from {step.from_ms} to {step.to_ms} ms"
                + ("" if step.lit else ", not lit at both ends")
                + allowed
            )
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

    lines.append("---")
    lines.append("")

    return lines
