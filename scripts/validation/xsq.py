"""Consolidated XSQ Validation.

Validates XSQ output against plan specifications and performs quality checks.

VALIDATION AREAS:
================

1. Quality Checks:
   - Missing refs (effects with no EffectDB entry)
   - Overlapping effects (within same layer)
   - Duplicate effects (same timing/settings)
   - Gap analysis

2. DMX Channel Data:
   - Channel data presence and validity
   - Value curve application
   - Channel value ranges

3. Plan Comparison:
   - Section coverage (all plan sections have XSQ effects)
   - Timing accuracy (XSQ effects match plan timing)
   - Channel usage vs plan specifications (shutter/color/gobo)

4. Analysis:
   - Effect density and distribution
   - Render mode analysis (movement patterns, strobes, color changes)
   - Template choreography validation
   - Fixture coverage (all fixtures + groups)
   - Channel usage statistics
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import sys
from typing import Any
import xml.etree.ElementTree as ET

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class XSQEffect:
    """Represents a single effect in XSQ."""

    element_name: str
    effect_type: str
    start_ms: int
    end_ms: int
    ref: int | None
    label: str
    layer_index: int = 0
    dmx_channels: dict[int, int] = field(default_factory=dict)
    dmx_curves: dict[int, str] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def overlaps(self, other: XSQEffect) -> bool:
        """Check if this effect overlaps with another."""
        return not (self.end_ms <= other.start_ms or self.start_ms >= other.end_ms)

    def __hash__(self) -> int:
        return hash((self.element_name, self.start_ms, self.end_ms, self.ref))


@dataclass
class ValidationIssue:
    """Represents a validation issue."""

    severity: str  # ERROR, WARNING, INFO
    category: str  # MISSING_REF, OVERLAP, DUPLICATE, GAP, COVERAGE, etc.
    message: str
    element_name: str | None = None
    effects: list[XSQEffect] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with path.open(encoding="utf-8") as f:
        data: Any = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        return data


def parse_dmx_settings(settings_str: str) -> tuple[dict[int, int], dict[int, str]]:
    """Parse DMX settings string to dicts of values and curves.

    Example: "E_SLIDER_DMX1=128,E_VALUECURVE_DMX2=Active=TRUE|..."
             -> ({1: 128}, {2: "Active=TRUE|..."})

    Returns:
        Tuple of (channel_values, channel_curves)
    """
    settings: dict[int, int] = {}
    curves: dict[int, str] = {}

    if not settings_str:
        return settings, curves

    for part in settings_str.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)

        # Extract channel values (E_SLIDER_DMX or E_TEXTCTRL_DMX)
        if "DMX" in key and "VALUECURVE" not in key:
            try:
                channel_num = int(key.split("DMX")[1].split("_")[0])  # Handle E_SLIDER_DMX1_foo
                settings[channel_num] = int(value)
            except (ValueError, IndexError):
                continue

        # Extract value curves (E_VALUECURVE_DMX)
        elif "E_VALUECURVE_DMX" in key:
            try:
                channel_num = int(key.split("DMX")[1])
                curves[channel_num] = value
            except (ValueError, IndexError):
                continue

    return settings, curves


def load_xsq_effects(
    xsq_path: Path, fixture_config: dict[str, Any] | None = None
) -> dict[str, list[XSQEffect]]:
    """Load XSQ file and extract DMX effects.

    Args:
        xsq_path: Path to XSQ file
        fixture_config: Optional fixture config to filter by configured models

    Returns:
        Dict mapping model name to list of XSQEffect objects
    """
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()

    # Load EffectDB
    effectdb: list[str] = []
    edb_el = root.find("EffectDB")
    if edb_el is not None:
        effectdb = [e.text or "" for e in edb_el.findall("Effect")]

    console.print(f"[dim]✓ Loaded {len(effectdb)} EffectDB entries[/dim]")

    # Get configured models if fixture_config provided
    configured_models: set[str] | None = None
    if fixture_config:
        configured_models = {f["xlights_model_name"] for f in fixture_config.get("fixtures", [])}
        if fixture_config.get("xlights_group"):
            configured_models.add(fixture_config["xlights_group"])
        for group_name in fixture_config.get("xlights_semantic_groups", {}).values():
            configured_models.add(group_name)

    # Extract effects for each element
    effects_by_model: dict[str, list[XSQEffect]] = defaultdict(list)

    element_effects_el = root.find("ElementEffects")
    if element_effects_el is None:
        logger.warning("No ElementEffects found in XSQ")
        return dict(effects_by_model)

    for el in element_effects_el.findall("Element"):
        element_name = el.get("name", "")

        # Filter by configured models if provided
        if configured_models and element_name not in configured_models:
            continue

        layer_el = el.find("EffectLayer")
        if layer_el is None:
            continue

        for effect_el in layer_el.findall("Effect"):
            effect_type = effect_el.get("name", "")
            if effect_type != "DMX":
                continue

            start_ms = int(effect_el.get("startTime", 0))
            end_ms = int(effect_el.get("endTime", 0))
            label = effect_el.get("label", "")
            ref_str = effect_el.get("ref")
            ref = int(ref_str) if ref_str and ref_str != "0" else None

            if end_ms <= start_ms:
                logger.warning(
                    f"Skipping invalid effect: {element_name} {start_ms}-{end_ms}ms (end <= start)"
                )
                continue

            # Parse DMX settings from EffectDB
            dmx_channels: dict[int, int] = {}
            dmx_curves: dict[int, str] = {}
            if ref is not None and 0 <= ref < len(effectdb):
                settings_str = effectdb[ref]
                dmx_channels, dmx_curves = parse_dmx_settings(settings_str)

            effect = XSQEffect(
                element_name=element_name,
                effect_type=effect_type,
                start_ms=start_ms,
                end_ms=end_ms,
                ref=ref,
                label=label,
                layer_index=0,
                dmx_channels=dmx_channels,
                dmx_curves=dmx_curves,
            )

            effects_by_model[element_name].append(effect)

    return dict(effects_by_model)


# ══════════════════════════════════════════════════════════════════════════════
# QUALITY CHECKS
# ══════════════════════════════════════════════════════════════════════════════


def check_missing_refs(
    effects_by_model: dict[str, list[XSQEffect]], effectdb: dict[int, str]
) -> list[ValidationIssue]:
    """Check for effects with missing or invalid refs."""
    issues: list[ValidationIssue] = []
    missing_ref_effects: list[XSQEffect] = []

    for effects in effects_by_model.values():
        for effect in effects:
            if effect.effect_type != "DMX":
                continue

            if effect.ref is None or effect.ref == 0:
                missing_ref_effects.append(effect)
            elif effect.ref not in effectdb:
                issues.append(
                    ValidationIssue(
                        severity="ERROR",
                        category="MISSING_REF",
                        message=f"Effect has ref={effect.ref} but EffectDB entry not found",
                        element_name=effect.element_name,
                        effects=[effect],
                        details={
                            "ref": effect.ref,
                            "timing": f"{effect.start_ms}-{effect.end_ms}ms",
                        },
                    )
                )

    if missing_ref_effects:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                category="MISSING_REF",
                message=f"Found {len(missing_ref_effects)} DMX effects with missing refs (ref=0 or None)",
                effects=missing_ref_effects,
            )
        )

    return issues


def check_overlaps_within_layer(
    effects_by_model: dict[str, list[XSQEffect]],
) -> list[ValidationIssue]:
    """Check for overlapping effects within the same element/layer."""
    issues: list[ValidationIssue] = []

    for element_name, effects in effects_by_model.items():
        # Sort by start time
        sorted_effects = sorted(effects, key=lambda e: e.start_ms)

        for i, effect1 in enumerate(sorted_effects):
            for effect2 in sorted_effects[i + 1 :]:
                if effect1.overlaps(effect2):
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            category="OVERLAP",
                            message=f"Overlapping effects in {element_name}",
                            element_name=element_name,
                            effects=[effect1, effect2],
                            details={
                                "overlap_ms": min(effect1.end_ms, effect2.end_ms)
                                - max(effect1.start_ms, effect2.start_ms),
                                "effect1_timing": f"{effect1.start_ms}-{effect1.end_ms}ms",
                                "effect2_timing": f"{effect2.start_ms}-{effect2.end_ms}ms",
                            },
                        )
                    )
                else:
                    # Since sorted, no more overlaps possible
                    break

    return issues


def check_duplicates(effects_by_model: dict[str, list[XSQEffect]]) -> list[ValidationIssue]:
    """Check for duplicate effects (same timing, same element)."""
    issues: list[ValidationIssue] = []

    for element_name, effects in effects_by_model.items():
        # Group by timing
        timing_groups: dict[tuple[int, int], list[XSQEffect]] = defaultdict(list)

        for effect in effects:
            key = (effect.start_ms, effect.end_ms)
            timing_groups[key].append(effect)

        # Report timing groups with multiple effects
        for (start_ms, end_ms), group_effects in timing_groups.items():
            if len(group_effects) > 1:
                refs = [e.ref for e in group_effects]
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        category="DUPLICATE",
                        message=f"Found {len(group_effects)} effects with identical timing in {element_name}",
                        element_name=element_name,
                        effects=group_effects,
                        details={
                            "timing": f"{start_ms}-{end_ms}ms",
                            "refs": refs,
                            "count": len(group_effects),
                        },
                    )
                )

    return issues


def check_gaps(effects_by_model: dict[str, list[XSQEffect]]) -> list[ValidationIssue]:
    """Check for gaps in timeline (informational)."""
    issues: list[ValidationIssue] = []

    for element_name, effects in effects_by_model.items():
        # Sort by start time
        sorted_effects = sorted(effects, key=lambda e: e.start_ms)

        prev_end = 0
        for effect in sorted_effects:
            if effect.start_ms > prev_end:
                gap_ms = effect.start_ms - prev_end
                if gap_ms > 100:  # Only report gaps > 100ms
                    issues.append(
                        ValidationIssue(
                            severity="INFO",
                            category="GAP",
                            message=f"Gap of {gap_ms}ms in {element_name}",
                            element_name=element_name,
                            details={
                                "gap_start_ms": prev_end,
                                "gap_end_ms": effect.start_ms,
                                "gap_duration_ms": gap_ms,
                            },
                        )
                    )
            prev_end = max(prev_end, effect.end_ms)

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# DMX CHANNEL DATA VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_dmx_data_presence(
    effects_by_model: dict[str, list[XSQEffect]],
) -> list[str]:
    """Validate that DMX channel data exists AND has meaningful content."""
    issues = []

    total_effects = sum(len(effects) for effects in effects_by_model.values())
    effects_with_data = sum(
        1 for effects in effects_by_model.values() for e in effects if e.dmx_channels
    )

    if total_effects == 0:
        issues.append("❌ CRITICAL: No DMX effects found")
    elif effects_with_data == 0:
        issues.append("❌ CRITICAL: No effects have DMX channel data (all ref=0)")
    else:
        percentage = (effects_with_data / total_effects) * 100
        console.print(
            f"[dim]✓ {effects_with_data}/{total_effects} effects have DMX data ({percentage:.1f}%)[/dim]"
        )

        # Validate channel values
        invalid_values = 0
        all_zero_effects = 0
        total_non_zero_values = 0

        for effects in effects_by_model.values():
            for effect in effects:
                channels = effect.dmx_channels
                curves = effect.dmx_curves

                # Count non-zero slider values AND value curve channels as "active"
                non_zero_slider_count = sum(1 for v in channels.values() if v != 0)
                curve_channel_count = len(curves)
                total_active_channels = non_zero_slider_count + curve_channel_count

                # Check if effect has ALL zero values AND no curves (static, no movement)
                if total_active_channels == 0 and channels:
                    all_zero_effects += 1

                total_non_zero_values += total_active_channels

                for value in channels.values():
                    if not (0 <= value <= 255):
                        invalid_values += 1

        if invalid_values > 0:
            issues.append(f"❌ {invalid_values} channel values outside 0-255 range")

        # CRITICAL: Check if most effects are all zeros (no actual movement)
        if effects_with_data > 0:
            zero_percentage = (all_zero_effects / effects_with_data) * 100
            if zero_percentage > 50:
                issues.append(
                    f"❌ CRITICAL: {zero_percentage:.1f}% of effects have ALL ZERO values "
                    f"({all_zero_effects}/{effects_with_data}) - NO ACTUAL MOVEMENT IMPLEMENTED"
                )
            elif all_zero_effects > 0:
                console.print(
                    f"[yellow]⚠️  {all_zero_effects} effects have all zero values ({zero_percentage:.1f}%)[/yellow]"
                )

            # Average non-zero values per effect (quality indicator)
            avg_non_zero = total_non_zero_values / effects_with_data
            if avg_non_zero < 2:
                issues.append(
                    f"❌ CRITICAL: Average {avg_non_zero:.1f} non-zero channels per effect "
                    f"(expected 3+ for pan/tilt/dimmer) - SEVERELY UNDER-IMPLEMENTED"
                )
            else:
                console.print(
                    f"[dim]✓ Average {avg_non_zero:.1f} non-zero channels per effect[/dim]"
                )

    return issues


def validate_value_curves(
    effects_by_model: dict[str, list[XSQEffect]], implementation: dict[str, Any]
) -> list[str]:
    """Validate that value curves are present for dynamic movements."""
    issues: list[str] = []

    # Count effects with curves
    total_effects = sum(len(effects) for effects in effects_by_model.values())
    effects_with_curves = sum(
        1 for effects in effects_by_model.values() for e in effects if e.dmx_curves
    )

    if total_effects == 0:
        return issues

    # Count sections with dynamic templates (should have curves)
    dynamic_templates = {
        "sweep",
        "circle",
        "figure8",
        "bounce",
        "pulse",
        "breathe",
        "wave",
        "zigzag",
        "spiral",
        "fan",
        "crescendo",
        "explosive",
    }

    dynamic_section_count = 0
    static_section_count = 0

    for section in implementation.get("sections", []):
        template_id = section.get("template_id", "").lower()
        if any(pattern in template_id for pattern in dynamic_templates):
            dynamic_section_count += 1
        elif "hold" in template_id or "static" in template_id:
            static_section_count += 1

    curve_percentage = (effects_with_curves / total_effects) * 100 if total_effects > 0 else 0

    console.print(
        f"[dim]✓ {effects_with_curves}/{total_effects} effects have value curves ({curve_percentage:.1f}%)[/dim]"
    )

    # If we have dynamic sections but NO curves, that's CRITICAL
    if dynamic_section_count > 0 and effects_with_curves == 0:
        issues.append(
            f"❌ CRITICAL: {dynamic_section_count} dynamic template sections but "
            f"NO VALUE CURVES found in XSQ - movement not implemented"
        )
    elif dynamic_section_count > 0 and curve_percentage < 30:
        issues.append(
            f"⚠️  Only {curve_percentage:.1f}% of effects have value curves "
            f"despite {dynamic_section_count} dynamic sections - likely under-implemented"
        )

    # Show curve usage breakdown
    curve_by_channel: dict[int, int] = {}
    for effects in effects_by_model.values():
        for effect in effects:
            for channel_num in effect.dmx_curves:
                curve_by_channel[channel_num] = curve_by_channel.get(channel_num, 0) + 1

    if curve_by_channel:
        console.print(f"[dim]  Curves by channel: {curve_by_channel}[/dim]")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# PLAN COMPARISON VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def validate_section_coverage(
    plan: dict[str, Any],
    effects_by_model: dict[str, list[XSQEffect]],
    configured_models: set[str],
    group_models: set[str],
) -> list[str]:
    """Validate that all plan sections have corresponding XSQ effects."""
    issues = []
    sections = plan.get("sections", [])

    if not sections:
        issues.append("❌ No sections found in plan")
        return issues

    # Calculate individual fixture count (exclude groups)
    individual_fixtures = configured_models - group_models
    num_individual_fixtures = len(individual_fixtures)

    # Build timeline of XSQ effects
    all_effects: list[tuple[int, int, str]] = []
    for model_name, effects in effects_by_model.items():
        for effect in effects:
            all_effects.append((effect.start_ms, effect.end_ms, model_name))

    all_effects.sort()

    missing_coverage = []
    partial_coverage = []

    for i, section in enumerate(sections, start=1):
        section_name = section.get("name", f"Section {i}")
        start_ms = section.get("start_ms", 0)
        end_ms = section.get("end_ms", 0)

        # Check if any effects cover this section
        covering_effects = [
            (s, e, m)
            for s, e, m in all_effects
            if not (e <= start_ms or s >= end_ms)  # Overlaps section
        ]

        if not covering_effects:
            missing_coverage.append(f"{section_name}")
            continue

        # Get unique models covering this section
        covering_models = {m for _, _, m in covering_effects}

        # Check if a group model covers this section (counts as full coverage)
        has_group_coverage = bool(covering_models & group_models)

        # Count individual fixtures covered
        individual_coverage = covering_models & individual_fixtures
        num_covered = len(individual_coverage)

        # If group covers it, that's full coverage
        if has_group_coverage:
            continue

        # Otherwise check individual fixture coverage
        if num_covered == 0:
            missing_coverage.append(f"{section_name}")
        elif num_covered < num_individual_fixtures:
            partial_coverage.append(
                f"{section_name}: "
                f"Only {num_covered}/{num_individual_fixtures} individual fixtures "
                f"(missing: {', '.join(sorted(individual_fixtures - individual_coverage))})"
            )

    if missing_coverage:
        issues.append(f"❌ Sections with NO XSQ effects: {', '.join(missing_coverage)}")

    if partial_coverage:
        issues.append("⚠️  Sections with partial coverage:\n    " + "\n    ".join(partial_coverage))

    if not issues:
        issues.append(f"✅ All {len(sections)} sections have XSQ effect coverage")

    return issues


def validate_channel_usage_vs_plan(
    raw_plan: dict[str, Any],
    implementation: dict[str, Any],
    effects_by_model: dict[str, list[XSQEffect]],
    fixture_config: dict[str, Any],
) -> list[str]:
    """Validate that XSQ channel usage matches plan specifications."""
    issues = []

    # Build DMX channel mapping for each fixture
    dmx_mapping_by_fixture = {}
    for fixture in fixture_config.get("fixtures", []):
        fixture_name = fixture["xlights_model_name"]
        dmx_map = fixture["config"]["dmx_mapping"]
        dmx_mapping_by_fixture[fixture_name] = {
            "shutter": dmx_map.get("shutter_channel"),
            "color": dmx_map.get("color_channel"),
            "gobo": dmx_map.get("gobo_channel"),
            "shutter_map": dmx_map.get("shutter_map", {}),
            "color_map": dmx_map.get("color_map", {}),
            "gobo_map": dmx_map.get("gobo_map", {}),
        }

    sections_validated = 0
    channel_mismatches = []

    for section in raw_plan.get("sections", []):
        section_name = section.get("name", "Unknown")
        channels = section.get("channels")

        if not channels:
            continue

        # Get timing from implementation
        impl_section = next(
            (s for s in implementation.get("sections", []) if s.get("name") == section_name),
            None,
        )
        if not impl_section:
            continue

        start_ms = impl_section.get("start_ms")
        end_ms = impl_section.get("end_ms")
        if start_ms is None or end_ms is None:
            continue

        sections_validated += 1

        # Check each fixture/model
        for model_name, effects in effects_by_model.items():
            if model_name not in dmx_mapping_by_fixture:
                continue  # Skip group models for now

            dmx_map = dmx_mapping_by_fixture[model_name]

            # Find effects in this section
            section_effects = [
                e for e in effects if not (e.end_ms <= start_ms or e.start_ms >= end_ms)
            ]

            if not section_effects:
                continue

            # Validate SHUTTER
            if channels.get("shutter"):
                expected = channels["shutter"]
                shutter_ch = dmx_map["shutter"]
                if shutter_ch:
                    actual_values = [
                        e.dmx_channels.get(shutter_ch)
                        for e in section_effects
                        if shutter_ch in e.dmx_channels
                    ]
                    if not actual_values:
                        channel_mismatches.append(
                            f"Section '{section_name}': Plan specifies shutter='{expected}' "
                            f"but {model_name} has no shutter data"
                        )

            # Validate COLOR
            if channels.get("color"):
                expected = channels["color"]
                color_ch = dmx_map["color"]
                if color_ch:
                    actual_values = [
                        e.dmx_channels.get(color_ch)
                        for e in section_effects
                        if color_ch in e.dmx_channels
                    ]
                    if not actual_values:
                        channel_mismatches.append(
                            f"Section '{section_name}': Plan specifies color='{expected}' "
                            f"but {model_name} has no color data"
                        )

            # Validate GOBO
            if channels.get("gobo") and channels["gobo"] != "open":
                expected = channels["gobo"]
                gobo_ch = dmx_map["gobo"]
                if gobo_ch:
                    actual_values = [
                        e.dmx_channels.get(gobo_ch)
                        for e in section_effects
                        if gobo_ch in e.dmx_channels
                    ]
                    if not actual_values:
                        channel_mismatches.append(
                            f"Section '{section_name}': Plan specifies gobo='{expected}' "
                            f"but {model_name} has no gobo data"
                        )

    if sections_validated > 0:
        console.print(f"[dim]✓ Validated channel usage for {sections_validated} sections[/dim]")

    if channel_mismatches:
        issues.append(f"⚠️  {len(channel_mismatches)} channel specification mismatches")
        for mismatch in channel_mismatches[:5]:  # Show first 5
            issues.append(f"  {mismatch}")
        if len(channel_mismatches) > 5:
            issues.append(f"  ... and {len(channel_mismatches) - 5} more")

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS & DISPLAY
# ══════════════════════════════════════════════════════════════════════════════


def analyze_effect_density(effects_by_model: dict[str, list[XSQEffect]]) -> None:
    """Analyze effect density and distribution."""
    if not effects_by_model:
        console.print("\n⚠️  No effects found")
        return

    table = Table(title="Effect Density Analysis", show_header=True)
    table.add_column("Model", style="cyan", width=25)
    table.add_column("Effects", style="green", width=10)
    table.add_column("Total Duration", style="yellow", width=15)
    table.add_column("Avg Duration", style="magenta", width=15)
    table.add_column("Density", style="white", width=30)

    for model_name, effects in sorted(effects_by_model.items()):
        if not effects:
            continue

        total_duration_ms = sum(e.duration_ms for e in effects)
        avg_duration_ms = total_duration_ms / len(effects)

        # Calculate density (effects per second)
        if effects:
            timeline_start = min(e.start_ms for e in effects)
            timeline_end = max(e.end_ms for e in effects)
            timeline_duration_s = (timeline_end - timeline_start) / 1000.0
            density = len(effects) / timeline_duration_s if timeline_duration_s > 0 else 0
        else:
            density = 0

        # Create density bar
        bar_length = min(int(density * 5), 30)
        bar = "█" * bar_length

        table.add_row(
            model_name,
            str(len(effects)),
            f"{total_duration_ms / 1000:.1f}s",
            f"{avg_duration_ms:.0f}ms",
            f"{bar} ({density:.1f} eff/s)",
        )

    console.print()
    console.print(table)

    # Summary
    total_effects = sum(len(effects) for effects in effects_by_model.values())
    console.print("\n[bold]Effect Summary:[/bold]")
    console.print(f"  Total effects: {total_effects}")
    console.print(f"  Models with effects: {len(effects_by_model)}")


def display_channel_statistics(
    effects_by_model: dict[str, list[XSQEffect]], fixture_config: dict[str, Any]
) -> None:
    """Display detailed channel usage statistics."""
    # Build channel purpose mapping
    purpose_map: dict[int, str] = {}
    for fixture in fixture_config.get("fixtures", []):
        dmx_map = fixture["config"]["dmx_mapping"]
        if dmx_map.get("pan_channel"):
            purpose_map[dmx_map["pan_channel"]] = "Pan"
        if dmx_map.get("tilt_channel"):
            purpose_map[dmx_map["tilt_channel"]] = "Tilt"
        if dmx_map.get("dimmer_channel"):
            purpose_map[dmx_map["dimmer_channel"]] = "Dimmer"
        if dmx_map.get("shutter_channel"):
            purpose_map[dmx_map["shutter_channel"]] = "Shutter"
        if dmx_map.get("color_channel"):
            purpose_map[dmx_map["color_channel"]] = "Color"
        if dmx_map.get("gobo_channel"):
            purpose_map[dmx_map["gobo_channel"]] = "Gobo"

    # Aggregate channel usage
    channel_stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "values": [], "purpose": "Unknown"}
    )

    for effects in effects_by_model.values():
        for effect in effects:
            for channel_num, value in effect.dmx_channels.items():
                channel_stats[channel_num]["count"] += 1
                channel_stats[channel_num]["values"].append(value)
                if channel_num in purpose_map:
                    channel_stats[channel_num]["purpose"] = purpose_map[channel_num]

    if not channel_stats:
        console.print("[yellow]⚠️  No channel usage data available[/yellow]")
        return

    # Display table
    table = Table(title="DMX Channel Usage", show_header=True)
    table.add_column("Channel", style="cyan")
    table.add_column("Purpose", style="magenta")
    table.add_column("Usage", style="green", justify="right")
    table.add_column("Value Range", style="yellow")

    for channel_num in sorted(channel_stats.keys()):
        stats = channel_stats[channel_num]
        values = stats["values"]
        min_val = min(values)
        max_val = max(values)

        table.add_row(
            f"CH{channel_num}",
            stats["purpose"],
            str(stats["count"]),
            f"{min_val}-{max_val}",
        )

    console.print(table)


def display_validation_summary(issues: list[ValidationIssue]) -> None:
    """Display validation summary."""
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]
    infos = [i for i in issues if i.severity == "INFO"]

    console.print("\n" + "=" * 80)
    console.print("VALIDATION SUMMARY")
    console.print("=" * 80)
    console.print(f"Total Issues: {len(issues)}")
    console.print(f"  Errors:   {len(errors)}")
    console.print(f"  Warnings: {len(warnings)}")
    console.print(f"  Info:     {len(infos)}")

    # Group by category
    by_category: dict[str, list[ValidationIssue]] = defaultdict(list)
    for issue in issues:
        by_category[issue.category].append(issue)

    console.print("\nBy Category:")
    for category, category_issues in sorted(by_category.items()):
        console.print(f"  {category}: {len(category_issues)}")

    # Print detailed issues
    if issues:
        console.print("\n" + "=" * 80)
        console.print("DETAILED ISSUES")
        console.print("=" * 80)

        for _, issue in enumerate(issues[:20], 1):  # Limit to first 20
            console.print(f"\n[{issue.severity}] {issue.category}: {issue.message}")
            if issue.element_name:
                console.print(f"  Element: {issue.element_name}")
            if issue.details:
                console.print(f"  Details: {json.dumps(issue.details, indent=4)}")

        if len(issues) > 20:
            console.print(f"\n... and {len(issues) - 20} more issues")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VALIDATION
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Main validation entry point."""
    parser = argparse.ArgumentParser(description="Validate XSQ sequence files")
    parser.add_argument(
        "sequence_name",
        nargs="?",
        default="need_a_favor",
        help="Sequence name (default: need_a_favor)",
    )
    parser.add_argument("--xsq-path", help="Explicit path to XSQ file", type=Path)
    parser.add_argument("--plan-path", help="Explicit path to plan file", type=Path)
    parser.add_argument("--raw-plan-path", help="Explicit path to raw plan file", type=Path)
    parser.add_argument("--fixture-config-path", help="Explicit path to fixture config", type=Path)
    parser.add_argument("--quality-only", action="store_true", help="Run quality checks only")
    parser.add_argument("--output-json", help="Output issues to JSON file", type=Path)

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    # Determine paths
    if args.xsq_path:
        xsq_path = args.xsq_path
        sequence_name = args.sequence_name
    else:
        sequence_name = args.sequence_name
        xsq_path = repo_root / f"artifacts/{sequence_name}/{sequence_name}_twinklr_mh.xsq"

    if args.plan_path:
        impl_plan_path = args.plan_path
    else:
        impl_plan_path = repo_root / f"artifacts/{sequence_name}/plan_{sequence_name}.json"
        final_impl_path = repo_root / f"artifacts/{sequence_name}/final_{sequence_name}.json"
        if not impl_plan_path.exists() and final_impl_path.exists():
            impl_plan_path = final_impl_path

    if args.raw_plan_path:
        raw_plan_path = args.raw_plan_path
    else:
        raw_plan_path = repo_root / f"artifacts/{sequence_name}/plan_raw_{sequence_name}.json"

    if args.fixture_config_path:
        fixture_config_path = args.fixture_config_path
    else:
        job_config_path = repo_root / "job_config.json"
        if job_config_path.exists():
            job_config = load_json(job_config_path)
            fixture_config_path = repo_root / job_config.get(
                "fixture_config_path", "fixture_config.json"
            )
        else:
            fixture_config_path = repo_root / "fixture_config.json"

    console.print("\n[bold cyan]═══════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]XSQ Validation (Consolidated)[/bold cyan]")
    console.print(f"[bold cyan]Sequence: {sequence_name}[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════[/bold cyan]\n")

    all_issues: list[str] = []
    quality_issues: list[ValidationIssue] = []

    # Load XSQ file
    try:
        console.print("[dim]Loading XSQ file...[/dim]")
        fixture_config = load_json(fixture_config_path) if fixture_config_path.exists() else {}
        effects_by_model = load_xsq_effects(xsq_path, fixture_config)
        console.print()
    except FileNotFoundError as e:
        console.print(f"[red]❌ {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Error loading XSQ: {e}[/red]")
        sys.exit(1)

    # Load EffectDB for quality checks
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()
    effectdb: dict[int, str] = {}
    edb_el = root.find("EffectDB")
    if edb_el is not None:
        for idx, effect_el in enumerate(edb_el.findall("Effect"), start=1):
            settings = effect_el.text or ""
            effectdb[idx] = settings

    # ──────────────────────────────────────────────────────────────────────────
    # QUALITY CHECKS
    # ──────────────────────────────────────────────────────────────────────────
    console.print("[bold underline]1. Quality Checks[/bold underline]\n")

    quality_issues.extend(check_missing_refs(effects_by_model, effectdb))
    quality_issues.extend(check_overlaps_within_layer(effects_by_model))
    quality_issues.extend(check_duplicates(effects_by_model))
    quality_issues.extend(check_gaps(effects_by_model))

    if not quality_issues:
        console.print("[green]✓ Quality checks passed[/green]")
    else:
        display_validation_summary(quality_issues)

    console.print()

    # ──────────────────────────────────────────────────────────────────────────
    # DMX CHANNEL DATA VALIDATION
    # ──────────────────────────────────────────────────────────────────────────
    if not args.quality_only:
        console.print("[bold underline]2. DMX Channel Data Validation[/bold underline]\n")

        issues = validate_dmx_data_presence(effects_by_model)
        all_issues.extend(issues)
        if not issues:
            console.print("[green]✓ DMX channel data validation passed[/green]")
        console.print()

        # Load implementation for value curve validation
        if impl_plan_path.exists():
            console.print("[bold underline]2B. Value Curve Validation[/bold underline]\n")
            implementation = load_json(impl_plan_path)
            issues = validate_value_curves(effects_by_model, implementation)
            all_issues.extend(issues)
            if not issues:
                console.print("[green]✓ Value curve validation passed[/green]")
            console.print()

        # ──────────────────────────────────────────────────────────────────────────
        # PLAN COMPARISON VALIDATION
        # ──────────────────────────────────────────────────────────────────────────
        if impl_plan_path.exists() and raw_plan_path.exists():
            console.print("[bold underline]3. Plan Comparison Validation[/bold underline]\n")

            implementation = load_json(impl_plan_path)
            raw_plan = load_json(raw_plan_path)

            # Get configured models
            configured_models = {
                f["xlights_model_name"] for f in fixture_config.get("fixtures", [])
            }
            group_models = set()
            if fixture_config.get("xlights_group"):
                group_models.add(fixture_config["xlights_group"])
            for group_name in fixture_config.get("xlights_semantic_groups", {}).values():
                group_models.add(group_name)

            # Section coverage
            issues = validate_section_coverage(
                implementation, effects_by_model, configured_models, group_models
            )
            all_issues.extend(issues)
            console.print()

            # Channel usage vs plan
            issues = validate_channel_usage_vs_plan(
                raw_plan, implementation, effects_by_model, fixture_config
            )
            all_issues.extend(issues)
            if not issues:
                console.print("[green]✓ Channel usage matches plan specifications[/green]")
            console.print()

        # ──────────────────────────────────────────────────────────────────────────
        # ANALYSIS
        # ──────────────────────────────────────────────────────────────────────────
        console.print("[bold underline]4. Analysis[/bold underline]\n")
        analyze_effect_density(effects_by_model)
        if fixture_config_path.exists():
            display_channel_statistics(effects_by_model, fixture_config)
        console.print()

    # ──────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    console.print("═" * 60)

    # Convert quality issues to strings for summary
    critical_quality = [i for i in quality_issues if i.severity == "ERROR"]
    warning_quality = [i for i in quality_issues if i.severity == "WARNING"]

    critical_issues = [i for i in all_issues if i.startswith("❌") or "CRITICAL" in i]
    warning_issues = [i for i in all_issues if i.startswith("⚠️")]

    total_critical = len(critical_quality) + len(critical_issues)
    total_warnings = len(warning_quality) + len(warning_issues)

    if total_critical == 0 and total_warnings == 0:
        console.print(Panel("[bold green]✅ ALL VALIDATIONS PASSED[/bold green]"))
        sys.exit(0)
    else:
        console.print(
            Panel(
                f"[bold yellow]⚠️  VALIDATION ISSUES[/bold yellow]\n\n"
                f"Critical: {total_critical}\nWarnings: {total_warnings}",
                title="Summary",
            )
        )

        if critical_quality or critical_issues:
            console.print("\n[bold red]Critical Issues:[/bold red]")
            for issue in critical_quality:
                console.print(f"  [{issue.severity}] {issue.message}")
            for issue in critical_issues:
                console.print(f"  {issue}")

        if warning_quality or warning_issues:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for issue in warning_quality[:10]:
                console.print(f"  [{issue.severity}] {issue.message}")
            for issue in warning_issues[:10]:
                console.print(f"  {issue}")

        # Export to JSON if requested
        if args.output_json:
            issues_data = [
                {
                    "severity": issue.severity,
                    "category": issue.category,
                    "message": issue.message,
                    "element_name": issue.element_name,
                    "details": issue.details,
                    "effect_count": len(issue.effects),
                }
                for issue in quality_issues
            ]
            args.output_json.write_text(json.dumps(issues_data, indent=2))
            console.print(f"\nExported issues to: {args.output_json}")

        sys.exit(1 if total_critical > 0 else 0)


if __name__ == "__main__":
    main()
