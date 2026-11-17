"""Structural checks of a moving-head `.xsq`.

Each fixture's effects are constant DMX effects, one per run of identical 20 ms frames,
whose settings set every channel of the head's profile footprint. These checks read the
`.xsq` alone (and, optionally, the fixture config to pick the fixtures' models): missing
EffectDB refs, overlaps, identical timings, gaps and whether the effects carry DMX data.
What the render planned and why is in its `.xsq.trace.json`; `twinklr eval-report`
re-renders and measures it.
"""

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
    """One check's finding, converted to the shared issue model by `_to_core_issue`."""

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
    """Map each EffectDB entry to the `ref` that names it: its zero-based position."""
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()
    effectdb: dict[int, str] = {}
    edb_el = root.find("EffectDB")
    if edb_el is not None:
        for index, effect_el in enumerate(edb_el.findall("Effect")):
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
            if ref is not None and ref in effectdb:
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


def _to_core_issue(issue: ValidationIssue) -> CoreIssue:
    return CoreIssue(
        severity=issue.severity,
        category=issue.category,
        message=issue.message,
        element_name=issue.element_name,
        details=issue.details,
    )


def run_mh_xsq_validation(paths: MHXSQValidationPaths) -> ValidationResult:
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

    result.stats["models_with_effects"] = len(effects_by_model)
    result.stats["total_effects"] = sum(len(effects) for effects in effects_by_model.values())
    if paths.output_json_path is not None:
        write_result_json(paths.output_json_path, "MH XSQ Validation", result)
    return result
