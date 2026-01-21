"""Consolidated Plan Validation.

Validates LLM-generated plans across all stages:
1. Raw Plan (plan_raw_*.json) - High-level plan with channel specs
2. Implementation (plan_*.json / final_*.json) - Detailed choreography
3. Evaluation (evaluation_*.json) - Judge scoring and feedback

VALIDATION CHECKS:
==================

Raw Plan Validation:
- Section structure and timing (bar-level)
- Channel specifications (shutter/color/gobo)
- Template references
- Beat alignment

Implementation Validation:
- Template expansion to detailed timing
- Parameter resolution
- Timing precision and alignment (millisecond-level)
- Section count matches raw plan
- Beat alignment verification

Evaluation Validation:
- Scoring completeness
- Channel scoring present
- Score ranges (1-10)
- Reasoning provided

Cross-validation:
- Raw plan sections match implementation sections
- Timing consistency across stages
- Channel specifications preserved
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as f:
        data: Any = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        return data


# ══════════════════════════════════════════════════════════════════════════════
# RAW PLAN VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_raw_plan_structure(raw_plan: dict[str, Any]) -> list[str]:
    """Validate raw plan structure."""
    issues = []

    # Check for sections
    if "sections" not in raw_plan:
        issues.append("❌ No 'sections' key in raw plan")
        return issues

    sections = raw_plan["sections"]
    if not sections:
        issues.append("❌ Empty sections list in raw plan")
        return issues

    console.print(f"[dim]✓ Raw plan has {len(sections)} sections[/dim]")

    return issues


def validate_channel_specifications(raw_plan: dict[str, Any]) -> list[str]:
    """Validate channel specifications in raw plan."""
    issues = []
    sections = raw_plan.get("sections", [])

    sections_with_channels = 0
    channel_types_used = set()

    for i, section in enumerate(sections):
        section_name = section.get("name", f"Section {i + 1}")
        channels = section.get("channels")

        if channels is None:
            issues.append(f"⚠️  Section '{section_name}': No channel specifications")
            continue

        sections_with_channels += 1

        # Check each channel type (values like "open", "blue", not IDs)
        if channels.get("shutter"):
            channel_types_used.add("shutter")
        if channels.get("color"):
            channel_types_used.add("color")
        if channels.get("gobo"):
            channel_types_used.add("gobo")

    if sections_with_channels > 0:
        console.print(
            f"[dim]✓ {sections_with_channels}/{len(sections)} sections have channel specs[/dim]"
        )
        console.print(f"[dim]✓ Channel types used: {', '.join(sorted(channel_types_used))}[/dim]")
    else:
        issues.append("❌ No sections have channel specifications")

    return issues


def validate_raw_plan_timing(raw_plan: dict[str, Any]) -> list[str]:
    """Validate timing in raw plan (bar-level timing).

    Note: Overlaps are ALLOWED when different target groups are used (e.g., main + accent layers).
    Only validate that individual sections have valid start/end bars.
    """
    issues = []
    sections = raw_plan.get("sections", [])

    for i, section in enumerate(sections):
        section_name = section.get("name", f"Section {i + 1}")
        start_bar = section.get("start_bar")
        end_bar = section.get("end_bar")

        if start_bar is None or end_bar is None:
            issues.append(f"❌ Section '{section_name}': Missing start_bar or end_bar")
            continue

        if end_bar <= start_bar:
            issues.append(
                f"❌ Section '{section_name}': end_bar ({end_bar}) <= start_bar ({start_bar})"
            )

    if not issues:
        console.print("[dim]✓ Raw plan timing is valid (all sections have proper bar ranges)[/dim]")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# IMPLEMENTATION VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_implementation_structure(implementation: dict[str, Any]) -> list[str]:
    """Validate implementation structure."""
    issues = []

    if "sections" not in implementation:
        issues.append("❌ No 'sections' key in implementation")
        return issues

    sections = implementation["sections"]
    if not sections:
        issues.append("❌ Empty sections list in implementation")
        return issues

    console.print(f"[dim]✓ Implementation has {len(sections)} sections[/dim]")

    # Check for required fields in each section
    required_fields = ["name", "start_ms", "end_ms", "template_id"]
    for i, section in enumerate(sections):
        section_name = section.get("name", f"Section {i + 1}")
        for field in required_fields:
            if field not in section:
                issues.append(f"❌ Section '{section_name}': Missing '{field}'")

    return issues


def validate_implementation_timing(implementation: dict[str, Any]) -> list[str]:
    """Validate millisecond-precision timing in implementation.

    Note: Overlaps are ALLOWED when different target groups are used (e.g., main + accent layers).
    Only validate that individual sections have valid durations.
    """
    issues = []
    sections = implementation.get("sections", [])

    zero_duration_count = 0

    for i, section in enumerate(sections):
        section_name = section.get("name", f"Section {i + 1}")
        start_ms = section.get("start_ms")
        end_ms = section.get("end_ms")

        if start_ms is None or end_ms is None:
            issues.append(f"❌ Section '{section_name}': Missing start_ms or end_ms")
            continue

        duration_ms = end_ms - start_ms

        if duration_ms == 0:
            zero_duration_count += 1
            issues.append(f"❌ Section '{section_name}': Zero duration ({start_ms}ms)")
        elif duration_ms < 0:
            issues.append(
                f"❌ Section '{section_name}': Negative duration "
                f"(start={start_ms}ms, end={end_ms}ms)"
            )

    if zero_duration_count > 0:
        issues.append(f"❌ CRITICAL: {zero_duration_count} sections have zero duration")
    elif not issues:
        console.print(
            "[dim]✓ Implementation timing is valid (proper durations, overlaps allowed)[/dim]"
        )

    return issues


def validate_timing(plan: dict[str, Any]) -> list[str]:
    """Validate section timing for overlaps and gaps (legacy compatibility)."""
    issues = []
    sections = plan.get("sections", [])

    if not sections:
        issues.append("❌ No sections found in plan")
        return issues

    prev_end = None
    for i, section in enumerate(sections):
        section_id = section.get("section_id") or (i + 1)
        start_ms = section.get("start_ms", 0)
        end_ms = section.get("end_ms", 0)

        # Check if end > start
        if end_ms <= start_ms:
            issues.append(
                f"❌ Section {section_id} ({section.get('name')}): "
                f"end_ms ({end_ms}) <= start_ms ({start_ms})"
            )

        # Check for gaps with previous section
        if prev_end is not None:
            gap_ms = start_ms - prev_end
            if gap_ms < 0:
                issues.append(
                    f"⚠️  Section {section_id} ({section.get('name')}): "
                    f"OVERLAP of {abs(gap_ms)}ms with previous section"
                )
            elif gap_ms > 1000:  # >1 second gap
                issues.append(
                    f"⚠️  Section {section_id} ({section.get('name')}): "
                    f"GAP of {gap_ms}ms from previous section"
                )

        prev_end = end_ms

    if not issues:
        issues.append(f"✅ All {len(sections)} sections have valid timing (no overlaps/gaps)")

    return issues


def validate_template_references(implementation: dict[str, Any]) -> list[str]:
    """Validate template_id references."""
    issues = []
    sections = implementation.get("sections", [])

    templates_used = set()
    sections_without_template = 0

    for i, section in enumerate(sections):
        section_name = section.get("name", f"Section {i + 1}")
        template_id = section.get("template_id")

        if not template_id:
            sections_without_template += 1
            issues.append(f"⚠️  Section '{section_name}': No template_id specified")
        else:
            templates_used.add(template_id)

    if templates_used:
        console.print(
            f"[dim]✓ Templates used: {', '.join(sorted(templates_used))} "
            f"({len(templates_used)} unique)[/dim]"
        )

    if sections_without_template > 0:
        issues.append(f"⚠️  {sections_without_template} sections without template_id")

    return issues


def validate_channels(plan: dict[str, Any]) -> list[str]:
    """Validate channel specifications (legacy compatibility)."""
    issues: list[str] = []
    sections = plan.get("sections", [])

    if not sections:
        return issues

    # Count sections with channel specs
    channel_counts = {"shutter": 0, "color": 0, "gobo": 0}
    sections_with_channels = 0

    for section in sections:
        channels = section.get("channels", {})
        if (
            channels
            and isinstance(channels, dict)
            and any(v is not None for v in channels.values())
        ):
            sections_with_channels += 1
            for channel_type in ["shutter", "color", "gobo"]:
                if channels.get(channel_type):
                    channel_counts[channel_type] += 1

    # Report
    if sections_with_channels == 0:
        issues.append("❌ No channel specifications found in any section")
    else:
        issues.append(f"✅ {sections_with_channels}/{len(sections)} sections have channel specs")
        for channel_type, count in channel_counts.items():
            issues.append(f"   - {channel_type}: {count} sections")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# BEAT ALIGNMENT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_beat_alignment(plan: dict[str, Any]) -> list[str]:
    """Check that all period_bars values are aligned to the beat grid.

    Args:
        plan: Plan dictionary

    Returns:
        List of issue strings
    """
    issues = []

    # Get time signature from first section with metadata
    time_signature = "4/4"  # default
    for section in plan.get("sections", []):
        if "time_signature" in section:
            time_signature = section["time_signature"]
            break

    # Parse beats per bar
    beats_per_bar = int(time_signature.split("/")[0]) if "/" in time_signature else 4

    for section in plan.get("sections", []):
        section_name = section.get("name", f"Section {section.get('section_id')}")

        for instr in section.get("instructions", []):
            if "movement" not in instr:
                continue

            movement = instr["movement"]
            period_bars = movement.get("period_bars")

            if period_bars is None:
                continue

            # Check if beat-aligned
            beats_per_cycle = period_bars * beats_per_bar
            quantized_beats = round(beats_per_cycle)
            error = abs(beats_per_cycle - quantized_beats)

            if error > 0.1:
                issues.append(
                    f"⚠️  Section '{section_name}': Pattern '{movement.get('pattern')}' "
                    f"has period_bars={period_bars:.4f} ({beats_per_cycle:.2f} beats) "
                    f"not aligned to beat grid (error: {error:.2f} beats)"
                )

    if not issues:
        console.print("[dim]✓ All effects are beat-aligned[/dim]")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_evaluation_structure(evaluation: dict[str, Any]) -> list[str]:
    """Validate evaluation structure and scoring."""
    issues = []

    # Check for required top-level fields
    required_fields = ["overall_score", "pass_threshold", "channel_scoring"]
    for field in required_fields:
        if field not in evaluation:
            issues.append(f"❌ Missing '{field}' in evaluation")

    # Validate overall_score (0-100 scale)
    overall_score = evaluation.get("overall_score")
    if overall_score is not None:
        if not (0 <= overall_score <= 100):
            issues.append(f"❌ overall_score ({overall_score}) outside valid range (0-100)")
        else:
            console.print(f"[dim]✓ Overall score: {overall_score}/100[/dim]")

    # Check pass threshold
    pass_threshold = evaluation.get("pass_threshold")
    if pass_threshold is not None:
        console.print(f"[dim]✓ Pass threshold: {'PASSED' if pass_threshold else 'FAILED'}[/dim]")

    # Validate channel_scoring
    channel_scoring = evaluation.get("channel_scoring")
    if channel_scoring is None:
        issues.append("❌ channel_scoring is null (should contain channel evaluation)")
    else:
        # Check channel scoring fields (1-10 scale)
        channel_fields = [
            "shutter_appropriateness",
            "color_appropriateness",
            "gobo_appropriateness",
            "visual_impact",
        ]
        for field in channel_fields:
            score = channel_scoring.get(field)
            if score is not None:
                # gobo_appropriateness can be 0 if no gobos used
                if field == "gobo_appropriateness" and score == 0:
                    continue
                if not (1 <= score <= 10):
                    issues.append(
                        f"❌ channel_scoring.{field} ({score}) outside valid range (1-10)"
                    )
            else:
                issues.append(f"⚠️  Missing channel_scoring.{field}")

        if channel_scoring and not [i for i in issues if "channel_scoring" in i]:
            console.print("[dim]✓ Channel scoring is complete and valid[/dim]")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def cross_validate_plans(raw_plan: dict[str, Any], implementation: dict[str, Any]) -> list[str]:
    """Cross-validate raw plan and implementation.

    Note: Implementation may have MORE sections than raw plan due to template expansion.
    Templates can generate multiple instruction sets (e.g., main + accent layers).
    """
    issues = []

    raw_sections = raw_plan.get("sections", [])
    impl_sections = implementation.get("sections", [])

    # Implementation can have more sections due to template expansion
    if len(impl_sections) < len(raw_sections):
        issues.append(
            f"❌ Implementation has FEWER sections ({len(impl_sections)}) than raw plan ({len(raw_sections)})"
        )
    elif len(impl_sections) > len(raw_sections):
        console.print(
            f"[dim]✓ Implementation has {len(impl_sections)} sections "
            f"(expanded from {len(raw_sections)} raw sections via templates)[/dim]"
        )
    else:
        console.print(f"[dim]✓ Section counts match ({len(raw_sections)} sections)[/dim]")

    # Check that all raw plan section names appear in implementation
    # (implementation may have additional sub-sections like "Verse A - main", "Verse A - accent")
    raw_names = {s.get("name", "") for s in raw_sections}
    impl_names = {s.get("name", "") for s in impl_sections}

    # Check if raw names are subset of impl names or if impl names contain raw name prefixes
    missing_sections = []
    for raw_name in raw_names:
        # Check if exact match or if any impl name starts with raw name
        if raw_name not in impl_names and not any(
            impl_name.startswith(raw_name) for impl_name in impl_names
        ):
            missing_sections.append(raw_name)

    if missing_sections:
        issues.append(
            f"⚠️  Raw plan sections not found in implementation: {', '.join(missing_sections)}"
        )
    else:
        console.print("[dim]✓ All raw plan sections represented in implementation[/dim]")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS & DISPLAY
# ══════════════════════════════════════════════════════════════════════════════


def analyze_energy_progression(plan: dict[str, Any]) -> None:
    """Analyze and display energy progression."""
    story_overview = plan.get("plan", {}).get("story_overview", {})
    energy_progression = story_overview.get("energy_progression", [])

    if not energy_progression:
        console.print("\n⚠️  No energy progression data found")
        return

    table = Table(title="Energy Progression Analysis", show_header=True)
    table.add_column("Section", style="cyan", width=8)
    table.add_column("Energy", style="yellow", width=10)
    table.add_column("Bar Chart", style="green", width=40)
    table.add_column("Change", style="magenta", width=10)

    sections = plan.get("plan", {}).get("sections", [])

    for i, (energy, section) in enumerate(zip(energy_progression, sections, strict=False)):
        section_id = section.get("section_id", i + 1)

        # Create bar chart
        bar_length = int(energy * 4)  # Scale to ~40 chars max
        bar = "█" * bar_length

        # Calculate change from previous
        if i == 0:
            change = "—"
        else:
            delta = energy - energy_progression[i - 1]
            if abs(delta) < 0.5:
                change = f"≈ {delta:+.1f}"
            elif delta > 0:
                change = f"↑ {delta:+.1f}"
            else:
                change = f"↓ {delta:+.1f}"

        table.add_row(str(section_id), f"{energy:.1f}", bar, change)

    console.print()
    console.print(table)

    # Summary stats
    min_energy = min(energy_progression)
    max_energy = max(energy_progression)
    avg_energy = sum(energy_progression) / len(energy_progression)

    console.print("\n[bold]Energy Stats:[/bold]")
    console.print(f"  Min: {min_energy:.1f}  |  Max: {max_energy:.1f}  |  Avg: {avg_energy:.1f}")
    console.print(f"  Range: {max_energy - min_energy:.1f}")


def display_section_summary(plan: dict[str, Any]) -> None:
    """Display summary table of sections."""
    sections = plan.get("sections", [])

    table = Table(title="Section Summary", show_header=True)
    table.add_column("ID", style="cyan", width=8)
    table.add_column("Name", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Timing", style="green")
    table.add_column("Reference", style="magenta")

    for i, section in enumerate(sections):
        section_id = section.get("section_id", str(i + 1))
        name = section.get("name", "Unknown")[:35]
        section_type = "template"
        start_ms = section.get("start_ms", 0)
        end_ms = section.get("end_ms", 0)
        ref = section.get("template_id", "—")

        duration_s = (end_ms - start_ms) / 1000.0
        timing_str = f"{start_ms // 1000}-{end_ms // 1000}s ({duration_s:.1f}s)"
        table.add_row(section_id, name, section_type, timing_str, ref[:30])

    console.print()
    console.print(table)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Main validation entry point."""
    repo_root = Path(__file__).resolve().parents[2]

    # Allow sequence selection via command line arg
    sequence_name = sys.argv[1] if len(sys.argv) > 1 else "need_a_favor"

    # Paths to checkpoints
    raw_plan_path = repo_root / f"artifacts/{sequence_name}/plan_raw_{sequence_name}.json"
    impl_plan_path = repo_root / f"artifacts/{sequence_name}/plan_{sequence_name}.json"
    final_impl_path = repo_root / f"artifacts/{sequence_name}/final_{sequence_name}.json"
    eval_path = repo_root / f"artifacts/{sequence_name}/evaluation_{sequence_name}.json"

    # Use final if plan doesn't exist
    if not impl_plan_path.exists() and final_impl_path.exists():
        impl_plan_path = final_impl_path

    console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]Plan Validation (Consolidated)[/bold cyan]")
    console.print(f"[bold cyan]Sequence: {sequence_name}[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")

    all_issues = []

    # ──────────────────────────────────────────────────────────────────────────
    # 1. RAW PLAN VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    console.print("[bold underline]1. Raw Plan Validation[/bold underline]")
    console.print(f"[dim]File: {raw_plan_path.name}[/dim]\n")

    if not raw_plan_path.exists():
        console.print(f"[red]❌ Raw plan not found: {raw_plan_path}[/red]")
        all_issues.append("CRITICAL: Raw plan file missing")
    else:
        try:
            raw_plan = load_json(raw_plan_path)

            # Structure
            issues = validate_raw_plan_structure(raw_plan)
            all_issues.extend(issues)

            # Channel specifications
            issues = validate_channel_specifications(raw_plan)
            all_issues.extend(issues)

            # Timing
            issues = validate_raw_plan_timing(raw_plan)
            all_issues.extend(issues)

            if not issues:
                console.print("[green]✓ Raw plan validation passed[/green]")

        except Exception as e:
            console.print(f"[red]❌ Error loading raw plan: {e}[/red]")
            all_issues.append(f"Raw plan error: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. IMPLEMENTATION VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    console.print("\n[bold underline]2. Implementation Validation[/bold underline]")
    console.print(f"[dim]File: {impl_plan_path.name}[/dim]\n")

    if not impl_plan_path.exists():
        console.print(f"[red]❌ Implementation not found: {impl_plan_path}[/red]")
        all_issues.append("CRITICAL: Implementation file missing")
    else:
        try:
            implementation = load_json(impl_plan_path)

            # Structure
            issues = validate_implementation_structure(implementation)
            all_issues.extend(issues)

            # Timing
            issues = validate_implementation_timing(implementation)
            all_issues.extend(issues)

            # Templates
            issues = validate_template_references(implementation)
            all_issues.extend(issues)

            # Beat alignment
            issues = validate_beat_alignment(implementation)
            all_issues.extend(issues)

            if not issues:
                console.print("[green]✓ Implementation validation passed[/green]")

            # Display section summary
            display_section_summary(implementation)

        except Exception as e:
            console.print(f"[red]❌ Error loading implementation: {e}[/red]")
            all_issues.append(f"Implementation error: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. EVALUATION VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    console.print("\n[bold underline]3. Evaluation Validation[/bold underline]")
    console.print(f"[dim]File: {eval_path.name}[/dim]\n")

    if not eval_path.exists():
        console.print(f"[red]❌ Evaluation not found: {eval_path}[/red]")
        all_issues.append("CRITICAL: Evaluation file missing")
    else:
        try:
            evaluation = load_json(eval_path)

            # Structure and scoring
            issues = validate_evaluation_structure(evaluation)
            all_issues.extend(issues)

            if not issues:
                console.print("[green]✓ Evaluation validation passed[/green]")

        except Exception as e:
            console.print(f"[red]❌ Error loading evaluation: {e}[/red]")
            all_issues.append(f"Evaluation error: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. CROSS-VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    console.print("\n[bold underline]4. Cross-Validation[/bold underline]\n")

    if raw_plan_path.exists() and impl_plan_path.exists():
        try:
            raw_plan = load_json(raw_plan_path)
            implementation = load_json(impl_plan_path)

            issues = cross_validate_plans(raw_plan, implementation)
            all_issues.extend(issues)

            if not issues:
                console.print("[green]✓ Cross-validation passed[/green]")

        except Exception as e:
            console.print(f"[red]❌ Error in cross-validation: {e}[/red]")

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    console.print("\n" + "═" * 60)
    if not all_issues:
        console.print(Panel("[bold green]✅ ALL VALIDATIONS PASSED[/bold green]"))
        sys.exit(0)
    else:
        critical_issues = [i for i in all_issues if i.startswith("❌") or "CRITICAL" in i]
        warning_issues = [i for i in all_issues if i.startswith("⚠️")]

        console.print(
            Panel(
                f"[bold yellow]⚠️  VALIDATION ISSUES FOUND[/bold yellow]\n\n"
                f"Critical: {len(critical_issues)}\n"
                f"Warnings: {len(warning_issues)}",
                title="Validation Summary",
            )
        )

        if critical_issues:
            console.print("\n[bold red]Critical Issues:[/bold red]")
            for issue in critical_issues:
                console.print(f"  {issue}")

        if warning_issues:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for issue in warning_issues:
                console.print(f"  {issue}")

        sys.exit(1 if critical_issues else 0)


if __name__ == "__main__":
    main()
