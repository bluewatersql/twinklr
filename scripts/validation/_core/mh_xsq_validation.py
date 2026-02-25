from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from scripts.validation._core.io import load_json
from scripts.validation._core.models import ValidationIssue as CoreIssue
from scripts.validation._core.models import ValidationResult
from scripts.validation._core.reporting import write_result_json


@dataclass(frozen=True)
class MHXSQValidationPaths:
    """Artifact paths for MH XSQ validation."""

    xsq_path: Path
    implementation_path: Path | None = None
    raw_plan_path: Path | None = None
    fixture_config_path: Path | None = None
    output_json_path: Path | None = None


@dataclass
class MHXSQEffect:
    """Represents a single XSQ effect for MH validation."""

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

    def overlaps(self, other: MHXSQEffect) -> bool:
        return not (self.end_ms <= other.start_ms or self.start_ms >= other.end_ms)


@dataclass
class ValidationIssue:
    """Legacy-style XSQ validation issue."""

    severity: str
    category: str
    message: str
    element_name: str | None = None
    effects: list[MHXSQEffect] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def parse_dmx_settings(settings_str: str) -> tuple[dict[int, int], dict[int, str]]:
    """Parse DMX settings string into slider values and value curves."""
    settings: dict[int, int] = {}
    curves: dict[int, str] = {}
    if not settings_str:
        return settings, curves

    for part in settings_str.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if "DMX" in key and "VALUECURVE" not in key:
            try:
                channel_num = int(key.split("DMX")[1].split("_")[0])
                settings[channel_num] = int(value)
            except (ValueError, IndexError):
                continue
        elif "E_VALUECURVE_DMX" in key:
            try:
                channel_num = int(key.split("DMX")[1])
                curves[channel_num] = value
            except (ValueError, IndexError):
                continue
    return settings, curves


def _load_effectdb(xsq_path: Path) -> dict[int, str]:
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()
    effectdb: dict[int, str] = {}
    edb_el = root.find("EffectDB")
    if edb_el is not None:
        for index, effect_el in enumerate(edb_el.findall("Effect"), start=1):
            effectdb[index] = effect_el.text or ""
    return effectdb


def load_xsq_effects(
    xsq_path: Path, fixture_config: dict[str, Any] | None = None
) -> dict[str, list[MHXSQEffect]]:
    """Load DMX effects from XSQ, optionally filtering to configured models."""
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()
    effectdb = _load_effectdb(xsq_path)

    configured_models: set[str] | None = None
    if fixture_config:
        configured_models = {f["xlights_model_name"] for f in fixture_config.get("fixtures", [])}
        if fixture_config.get("xlights_group"):
            configured_models.add(fixture_config["xlights_group"])
        for group_name in fixture_config.get("xlights_semantic_groups", {}).values():
            configured_models.add(group_name)

    effects_by_model: dict[str, list[MHXSQEffect]] = defaultdict(list)
    element_effects_el = root.find("ElementEffects")
    if element_effects_el is None:
        return dict(effects_by_model)

    for el in element_effects_el.findall("Element"):
        element_name = el.get("name", "")
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
            if end_ms <= start_ms:
                continue
            ref_raw = effect_el.get("ref")
            ref = int(ref_raw) if ref_raw and ref_raw != "0" else None
            dmx_channels: dict[int, int] = {}
            dmx_curves: dict[int, str] = {}
            if ref is not None and 0 <= ref < len(effectdb):
                dmx_channels, dmx_curves = parse_dmx_settings(effectdb[ref])
            effects_by_model[element_name].append(
                MHXSQEffect(
                    element_name=element_name,
                    effect_type=effect_type,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    ref=ref,
                    label=effect_el.get("label", ""),
                    dmx_channels=dmx_channels,
                    dmx_curves=dmx_curves,
                )
            )
    return dict(effects_by_model)


def check_missing_refs(
    effects_by_model: dict[str, list[MHXSQEffect]], effectdb: dict[int, str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    missing_ref_effects: list[MHXSQEffect] = []
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
                        details={"ref": effect.ref},
                    )
                )
    if missing_ref_effects:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                category="MISSING_REF",
                message=(
                    f"Found {len(missing_ref_effects)} DMX effects with missing refs "
                    "(ref=0 or None)"
                ),
                effects=missing_ref_effects,
            )
        )
    return issues


def check_overlaps_within_layer(
    effects_by_model: dict[str, list[MHXSQEffect]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for element_name, effects in effects_by_model.items():
        sorted_effects = sorted(effects, key=lambda effect: effect.start_ms)
        for index, effect1 in enumerate(sorted_effects):
            for effect2 in sorted_effects[index + 1 :]:
                if effect1.overlaps(effect2):
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            category="OVERLAP",
                            message=f"Overlapping effects in {element_name}",
                            element_name=element_name,
                            effects=[effect1, effect2],
                        )
                    )
                else:
                    break
    return issues


def check_duplicates(effects_by_model: dict[str, list[MHXSQEffect]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for element_name, effects in effects_by_model.items():
        timing_groups: dict[tuple[int, int], list[MHXSQEffect]] = defaultdict(list)
        for effect in effects:
            timing_groups[(effect.start_ms, effect.end_ms)].append(effect)
        for (start_ms, end_ms), group in timing_groups.items():
            if len(group) > 1:
                issues.append(
                    ValidationIssue(
                        severity="WARNING",
                        category="DUPLICATE",
                        message=f"Found {len(group)} effects with identical timing in {element_name}",
                        element_name=element_name,
                        effects=group,
                        details={"timing": f"{start_ms}-{end_ms}ms"},
                    )
                )
    return issues


def check_gaps(effects_by_model: dict[str, list[MHXSQEffect]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for element_name, effects in effects_by_model.items():
        sorted_effects = sorted(effects, key=lambda effect: effect.start_ms)
        prev_end = 0
        for effect in sorted_effects:
            if effect.start_ms > prev_end:
                gap_ms = effect.start_ms - prev_end
                if gap_ms > 100:
                    issues.append(
                        ValidationIssue(
                            severity="INFO",
                            category="GAP",
                            message=f"Gap of {gap_ms}ms in {element_name}",
                            element_name=element_name,
                            details={"gap_duration_ms": gap_ms},
                        )
                    )
            prev_end = max(prev_end, effect.end_ms)
    return issues


def validate_dmx_data_presence(
    effects_by_model: dict[str, list[MHXSQEffect]],
) -> list[str]:
    """Validate that DMX channel data exists and looks meaningful."""
    issues: list[str] = []
    total_effects = sum(len(effects) for effects in effects_by_model.values())
    effects_with_data = sum(
        1 for effects in effects_by_model.values() for effect in effects if effect.dmx_channels
    )
    if total_effects == 0:
        return ["❌ CRITICAL: No DMX effects found"]
    if effects_with_data == 0:
        return ["❌ CRITICAL: No effects have DMX channel data (all ref=0)"]

    invalid_values = 0
    all_zero_effects = 0
    total_non_zero_values = 0
    for effects in effects_by_model.values():
        for effect in effects:
            channels = effect.dmx_channels
            curves = effect.dmx_curves
            non_zero_slider_count = sum(1 for value in channels.values() if value != 0)
            total_active_channels = non_zero_slider_count + len(curves)
            if total_active_channels == 0 and channels:
                all_zero_effects += 1
            total_non_zero_values += total_active_channels
            for value in channels.values():
                if not (0 <= value <= 255):
                    invalid_values += 1
    if invalid_values > 0:
        issues.append(f"❌ {invalid_values} channel values outside 0-255 range")
    zero_percentage = (all_zero_effects / effects_with_data) * 100 if effects_with_data else 0
    if zero_percentage > 50:
        issues.append(
            f"❌ CRITICAL: {zero_percentage:.1f}% of effects have ALL ZERO values "
            f"({all_zero_effects}/{effects_with_data}) - NO ACTUAL MOVEMENT IMPLEMENTED"
        )
    avg_non_zero = total_non_zero_values / effects_with_data if effects_with_data else 0
    if avg_non_zero < 2:
        issues.append(
            f"❌ CRITICAL: Average {avg_non_zero:.1f} non-zero channels per effect "
            "(expected 3+ for pan/tilt/dimmer) - SEVERELY UNDER-IMPLEMENTED"
        )
    return issues


def validate_value_curves(
    effects_by_model: dict[str, list[MHXSQEffect]], implementation: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    total_effects = sum(len(effects) for effects in effects_by_model.values())
    if total_effects == 0:
        return issues
    effects_with_curves = sum(
        1 for effects in effects_by_model.values() for effect in effects if effect.dmx_curves
    )
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
    for section in implementation.get("sections", []):
        if not isinstance(section, dict):
            continue
        template_id = str(section.get("template_id", "")).lower()
        if any(pattern in template_id for pattern in dynamic_templates):
            dynamic_section_count += 1
    curve_percentage = (effects_with_curves / total_effects) * 100
    if dynamic_section_count > 0 and effects_with_curves == 0:
        issues.append(
            f"❌ CRITICAL: {dynamic_section_count} dynamic template sections but "
            "NO VALUE CURVES found in XSQ - movement not implemented"
        )
    elif dynamic_section_count > 0 and curve_percentage < 30:
        issues.append(
            f"⚠️  Only {curve_percentage:.1f}% of effects have value curves "
            f"despite {dynamic_section_count} dynamic sections - likely under-implemented"
        )
    return issues


def validate_section_coverage(
    plan: dict[str, Any],
    effects_by_model: dict[str, list[MHXSQEffect]],
    configured_models: set[str],
    group_models: set[str],
) -> list[str]:
    issues: list[str] = []
    sections = plan.get("sections", [])
    if not sections:
        return ["❌ No sections found in plan"]
    individual_fixtures = configured_models - group_models
    num_individual_fixtures = len(individual_fixtures)

    all_effects: list[tuple[int, int, str]] = []
    for model_name, effects in effects_by_model.items():
        for effect in effects:
            all_effects.append((effect.start_ms, effect.end_ms, model_name))
    all_effects.sort()

    missing_coverage: list[str] = []
    partial_coverage: list[str] = []
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", f"Section {index}"))
        start_ms = int(section.get("start_ms", 0))
        end_ms = int(section.get("end_ms", 0))
        covering_effects = [
            (start, end, model)
            for start, end, model in all_effects
            if not (end <= start_ms or start >= end_ms)
        ]
        if not covering_effects:
            missing_coverage.append(section_name)
            continue
        covering_models = {model for _, _, model in covering_effects}
        if covering_models & group_models:
            continue
        individual_coverage = covering_models & individual_fixtures
        num_covered = len(individual_coverage)
        if num_covered == 0:
            missing_coverage.append(section_name)
        elif num_covered < num_individual_fixtures:
            partial_coverage.append(
                f"{section_name}: Only {num_covered}/{num_individual_fixtures} individual fixtures"
            )

    if missing_coverage:
        issues.append(f"❌ Sections with NO XSQ effects: {', '.join(missing_coverage)}")
    if partial_coverage:
        issues.append("⚠️  Sections with partial coverage:\n    " + "\n    ".join(partial_coverage))
    return issues


def validate_channel_usage_vs_plan(
    raw_plan: dict[str, Any],
    implementation: dict[str, Any],
    effects_by_model: dict[str, list[MHXSQEffect]],
    fixture_config: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    dmx_mapping_by_fixture: dict[str, dict[str, Any]] = {}
    for fixture in fixture_config.get("fixtures", []):
        fixture_name = fixture["xlights_model_name"]
        dmx_map = fixture["config"]["dmx_mapping"]
        dmx_mapping_by_fixture[fixture_name] = {
            "shutter": dmx_map.get("shutter_channel"),
            "color": dmx_map.get("color_channel"),
            "gobo": dmx_map.get("gobo_channel"),
        }

    channel_mismatches: list[str] = []
    for section in raw_plan.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("name", "Unknown"))
        channels = section.get("channels")
        if not isinstance(channels, dict) or not channels:
            continue
        impl_section = next(
            (
                candidate
                for candidate in implementation.get("sections", [])
                if isinstance(candidate, dict) and candidate.get("name") == section_name
            ),
            None,
        )
        if not isinstance(impl_section, dict):
            continue
        start_ms = impl_section.get("start_ms")
        end_ms = impl_section.get("end_ms")
        if not isinstance(start_ms, (int, float)) or not isinstance(end_ms, (int, float)):
            continue
        for model_name, effects in effects_by_model.items():
            if model_name not in dmx_mapping_by_fixture:
                continue
            dmx_map = dmx_mapping_by_fixture[model_name]
            section_effects = [
                effect
                for effect in effects
                if not (effect.end_ms <= start_ms or effect.start_ms >= end_ms)
            ]
            if not section_effects:
                continue
            for channel_name in ("shutter", "color", "gobo"):
                expected = channels.get(channel_name)
                if not expected or (channel_name == "gobo" and expected == "open"):
                    continue
                channel_num = dmx_map[channel_name]
                if channel_num:
                    actual_values = [
                        effect.dmx_channels.get(channel_num)
                        for effect in section_effects
                        if channel_num in effect.dmx_channels
                    ]
                    if not actual_values:
                        channel_mismatches.append(
                            f"Section '{section_name}': Plan specifies {channel_name}='{expected}' "
                            f"but {model_name} has no {channel_name} data"
                        )
    if channel_mismatches:
        issues.append(f"⚠️  {len(channel_mismatches)} channel specification mismatches")
        issues.extend(f"  {mismatch}" for mismatch in channel_mismatches[:5])
        if len(channel_mismatches) > 5:
            issues.append(f"  ... and {len(channel_mismatches) - 5} more")
    return issues


def _to_core_issue(issue: ValidationIssue) -> CoreIssue:
    return CoreIssue(
        severity=issue.severity,
        category=issue.category,
        message=issue.message,
        element_name=issue.element_name,
        details=issue.details,
    )


def run_mh_xsq_validation(
    paths: MHXSQValidationPaths,
    *,
    quality_only: bool = False,
) -> ValidationResult:
    """Run MH XSQ validation in-process."""
    result = ValidationResult()
    if not paths.xsq_path.exists():
        result.issues.append(
            CoreIssue(
                severity="ERROR",
                category="FILE_MISSING",
                message=f"XSQ file not found: {paths.xsq_path}",
                artifact="xsq",
            )
        )
        return result

    fixture_config: dict[str, Any] = {}
    if paths.fixture_config_path and paths.fixture_config_path.exists():
        fixture_config = load_json(paths.fixture_config_path)

    effectdb = _load_effectdb(paths.xsq_path)
    effects_by_model = load_xsq_effects(paths.xsq_path, fixture_config)
    result.artifacts_checked.append(str(paths.xsq_path))

    quality_issues = []
    quality_issues.extend(check_missing_refs(effects_by_model, effectdb))
    quality_issues.extend(check_overlaps_within_layer(effects_by_model))
    quality_issues.extend(check_duplicates(effects_by_model))
    quality_issues.extend(check_gaps(effects_by_model))
    result.extend([_to_core_issue(issue) for issue in quality_issues])

    for issue in validate_dmx_data_presence(effects_by_model):
        severity = (
            "ERROR" if issue.startswith("❌") else "WARNING" if issue.startswith("⚠️") else "INFO"
        )
        result.issues.append(CoreIssue(severity=severity, category="DMX_DATA", message=issue))

    implementation: dict[str, Any] | None = None
    if not quality_only and paths.implementation_path and paths.implementation_path.exists():
        implementation = load_json(paths.implementation_path)
        result.artifacts_checked.append(str(paths.implementation_path))
        for issue in validate_value_curves(effects_by_model, implementation):
            severity = (
                "ERROR"
                if issue.startswith("❌")
                else "WARNING"
                if issue.startswith("⚠️")
                else "INFO"
            )
            result.issues.append(
                CoreIssue(severity=severity, category="VALUE_CURVES", message=issue)
            )

    raw_plan: dict[str, Any] | None = None
    if not quality_only and paths.raw_plan_path and paths.raw_plan_path.exists():
        raw_plan = load_json(paths.raw_plan_path)
        result.artifacts_checked.append(str(paths.raw_plan_path))

    if not quality_only and implementation is not None and raw_plan is not None and fixture_config:
        configured_models = {
            fixture["xlights_model_name"] for fixture in fixture_config.get("fixtures", [])
        }
        group_models: set[str] = set()
        if fixture_config.get("xlights_group"):
            group_models.add(fixture_config["xlights_group"])
        for group_name in fixture_config.get("xlights_semantic_groups", {}).values():
            group_models.add(group_name)

        for issue in validate_section_coverage(
            implementation, effects_by_model, configured_models, group_models
        ):
            severity = (
                "ERROR"
                if issue.startswith("❌")
                else "WARNING"
                if issue.startswith("⚠️")
                else "INFO"
            )
            result.issues.append(
                CoreIssue(severity=severity, category="SECTION_COVERAGE", message=issue)
            )
        for issue in validate_channel_usage_vs_plan(
            raw_plan, implementation, effects_by_model, fixture_config
        ):
            severity = (
                "ERROR"
                if issue.startswith("❌")
                else "WARNING"
                if issue.startswith("⚠️")
                else "INFO"
            )
            result.issues.append(
                CoreIssue(severity=severity, category="CHANNEL_USAGE", message=issue)
            )

    result.stats["models_with_effects"] = len(effects_by_model)
    result.stats["total_effects"] = sum(len(effects) for effects in effects_by_model.values())
    if paths.output_json_path is not None:
        write_result_json(paths.output_json_path, "MH XSQ Validation", result)
    return result
