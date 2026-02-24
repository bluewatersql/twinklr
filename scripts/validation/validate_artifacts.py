#!/usr/bin/env python3
"""Unified artifact validator for moving-head and display pipelines.

Examples:
    uv run python scripts/validation/validate_artifacts.py --mode plan 11_need_a_favor
    uv run python scripts/validation/validate_artifacts.py --mode xsq --pipeline display 11_need_a_favor
    uv run python scripts/validation/validate_artifacts.py --mode all --pipeline auto 11_need_a_favor
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import pairwise
import json
from pathlib import Path
import re
import sys
from typing import Any, Literal
import xml.etree.ElementTree as ET

PipelineName = Literal["display", "mh"]
ModeName = Literal["plan", "xsq", "all"]


@dataclass(frozen=True)
class GenericXSQEffect:
    """Generic XSQ effect used for display-oriented validation."""

    element_name: str
    layer_index: int
    effect_name: str
    start_ms: int
    end_ms: int
    ref: int | None

    def overlaps(self, other: GenericXSQEffect) -> bool:
        """Return true when effect timing windows overlap."""
        return not (self.end_ms <= other.start_ms or self.start_ms >= other.end_ms)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    with path.open(encoding="utf-8") as handle:
        data: Any = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(data).__name__}")
    return data


def detect_pipeline_from_json(payload: dict[str, Any]) -> PipelineName | None:
    """Detect pipeline type from artifact JSON structure."""
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, str) and schema_version.startswith("group-plan-set."):
        return "display"

    if "section_plans" in payload:
        return "display"

    if "cross_section_issues" in payload and "score" in payload and "summary" in payload:
        return "display"

    if "overall_score" in payload or "channel_scoring" in payload:
        return "mh"

    sections = payload.get("sections")
    if isinstance(sections, list) and sections:
        first = sections[0]
        if isinstance(first, dict) and (
            "template_id" in first or "channels" in first or "instructions" in first
        ):
            return "mh"

    return None


def resolve_sequence_paths(repo_root: Path, sequence_name: str) -> dict[str, dict[str, Path]]:
    """Resolve canonical artifact paths for both pipelines."""
    artifact_dir = repo_root / "artifacts" / sequence_name
    return {
        "display": {
            "plan": artifact_dir / "group_plan_set.json",
            "evaluation": artifact_dir / "holistic_evaluation.json",
            "xsq": artifact_dir / f"{sequence_name}_display.xsq",
        },
        "mh": {
            "raw_plan": artifact_dir / f"plan_raw_{sequence_name}.json",
            "plan": artifact_dir / f"plan_{sequence_name}.json",
            "final_plan": artifact_dir / f"final_{sequence_name}.json",
            "evaluation": artifact_dir / f"evaluation_{sequence_name}.json",
            "xsq": artifact_dir / f"{sequence_name}_twinklr_mh.xsq",
        },
    }


def _effective_mh_plan_path(paths: dict[str, Path]) -> Path:
    plan_path = paths["plan"]
    if not plan_path.exists() and paths["final_plan"].exists():
        return paths["final_plan"]
    return plan_path


def validate_display_plan_structure(plan_set: dict[str, Any]) -> list[str]:
    """Validate display `group_plan_set.json` structure."""
    issues: list[str] = []
    section_plans = plan_set.get("section_plans")

    if not isinstance(section_plans, list):
        return ["❌ Missing or invalid 'section_plans' list in display plan set"]
    if not section_plans:
        return ["❌ Empty 'section_plans' list in display plan set"]

    total_placements = 0
    seen_section_ids: set[str] = set()
    section_windows: list[tuple[int, int, str]] = []
    seen_placement_ids: set[str] = set()
    for index, section in enumerate(section_plans, start=1):
        if not isinstance(section, dict):
            issues.append(f"❌ section_plans[{index - 1}] is not an object")
            continue

        section_id = str(section.get("section_id", f"section_{index}"))
        if section_id in seen_section_ids:
            issues.append(f"⚠️  Duplicate section_id '{section_id}' in display plan set")
        seen_section_ids.add(section_id)
        for key in ("start_ms", "end_ms", "lane_plans"):
            if key not in section:
                issues.append(f"❌ Section '{section_id}' missing '{key}'")

        start_ms = section.get("start_ms")
        end_ms = section.get("end_ms")
        if isinstance(start_ms, int) and isinstance(end_ms, int) and end_ms <= start_ms:
            issues.append(
                f"❌ Section '{section_id}' has invalid timing ({start_ms}ms -> {end_ms}ms)"
            )
        if isinstance(start_ms, int) and isinstance(end_ms, int):
            section_windows.append((start_ms, end_ms, section_id))

        lane_plans = section.get("lane_plans")
        if not isinstance(lane_plans, list) or not lane_plans:
            issues.append(f"⚠️  Section '{section_id}' has no lane_plans")
            continue

        seen_lanes: set[str] = set()
        for lane_plan in lane_plans:
            if not isinstance(lane_plan, dict):
                issues.append(f"⚠️  Section '{section_id}' contains non-object lane plan")
                continue
            lane_name = lane_plan.get("lane")
            if isinstance(lane_name, str):
                if lane_name in seen_lanes:
                    issues.append(
                        f"⚠️  Section '{section_id}' has duplicate lane '{lane_name}' entries"
                    )
                seen_lanes.add(lane_name)
            coordination_plans = lane_plan.get("coordination_plans", [])
            if not isinstance(coordination_plans, list):
                issues.append(f"⚠️  Section '{section_id}' has invalid coordination_plans")
                continue
            for coordination_plan in coordination_plans:
                if not isinstance(coordination_plan, dict):
                    issues.append(f"⚠️  Section '{section_id}' contains invalid coordination plan")
                    continue
                targets = coordination_plan.get("targets", [])
                target_refs: set[tuple[str, str]] = set()
                if isinstance(targets, list):
                    for target in targets:
                        if not isinstance(target, dict):
                            issues.append(
                                f"⚠️  Section '{section_id}' has non-object coordination target"
                            )
                            continue
                        target_type = target.get("type")
                        target_id = target.get("id")
                        if isinstance(target_type, str) and isinstance(target_id, str):
                            target_refs.add((target_type, target_id))
                elif targets is not None:
                    issues.append(f"⚠️  Section '{section_id}' coordination targets is not a list")
                placements = coordination_plan.get("placements", [])
                if not isinstance(placements, list):
                    issues.append(f"⚠️  Section '{section_id}' has invalid placements list")
                    continue
                for placement in placements:
                    if not isinstance(placement, dict):
                        issues.append(f"⚠️  Section '{section_id}' contains non-object placement")
                        continue
                    total_placements += 1
                    placement_id = placement.get("placement_id")
                    if not placement_id:
                        issues.append(f"❌ Section '{section_id}' placement missing 'placement_id'")
                    elif isinstance(placement_id, str):
                        if placement_id in seen_placement_ids:
                            issues.append(f"⚠️  Duplicate placement_id '{placement_id}' in display plan")
                        seen_placement_ids.add(placement_id)
                    for required_key in ("template_id", "target", "start", "duration"):
                        if required_key not in placement:
                            issues.append(
                                f"❌ Section '{section_id}' placement '{placement.get('placement_id', '?')}' "
                                f"Missing '{required_key}'"
                            )
                    placement_start = placement.get("start")
                    if placement_start is not None:
                        if not isinstance(placement_start, dict):
                            issues.append(
                                f"⚠️  Section '{section_id}' placement "
                                f"'{placement.get('placement_id', '?')}' has invalid 'start' (not an object)"
                            )
                        else:
                            bar_value = placement_start.get("bar")
                            beat_value = placement_start.get("beat")
                            if (bar_value is not None and not isinstance(bar_value, (int, float))) or (
                                beat_value is not None and not isinstance(beat_value, (int, float))
                            ):
                                issues.append(
                                    f"⚠️  Section '{section_id}' placement "
                                    f"'{placement.get('placement_id', '?')}' has invalid 'start' bar/beat values"
                                )
                    duration_value = placement.get("duration")
                    if duration_value is not None and not isinstance(duration_value, str):
                        issues.append(
                            f"⚠️  Section '{section_id}' placement "
                            f"'{placement.get('placement_id', '?')}' has invalid 'duration' (expected string)"
                        )
                    placement_target = placement.get("target")
                    if isinstance(placement_target, dict):
                        pt_type = placement_target.get("type")
                        pt_id = placement_target.get("id")
                        if (
                            isinstance(pt_type, str)
                            and isinstance(pt_id, str)
                            and target_refs
                            and (pt_type, pt_id) not in target_refs
                        ):
                            issues.append(
                                f"⚠️  Section '{section_id}' placement "
                                f"'{placement.get('placement_id', '?')}' target "
                                f"({pt_type}:{pt_id}) not listed in coordination targets"
                            )
                    elif placement_target is not None:
                        issues.append(
                            f"⚠️  Section '{section_id}' placement '{placement.get('placement_id', '?')}' "
                            "target is not an object"
                        )

    if section_windows:
        sorted_windows = sorted(section_windows, key=lambda item: item[0])
        previous_end = sorted_windows[0][1]
        previous_id = sorted_windows[0][2]
        for start_ms, end_ms, section_id in sorted_windows[1:]:
            if start_ms < previous_end:
                issues.append(
                    f"⚠️  Display sections overlap: '{previous_id}' and '{section_id}' "
                    f"({start_ms} < {previous_end})"
                )
            previous_end, previous_id = end_ms, section_id

    if total_placements == 0:
        issues.append("⚠️  No placements found across display plan sections")

    return issues


def validate_display_evaluation_structure(evaluation: dict[str, Any]) -> list[str]:
    """Validate display `holistic_evaluation.json` structure."""
    issues: list[str] = []
    required_fields = ("status", "score", "summary", "cross_section_issues", "recommendations")
    for field in required_fields:
        if field not in evaluation:
            issues.append(f"❌ Missing '{field}' in holistic evaluation")

    score = evaluation.get("score")
    if isinstance(score, (int, float)):
        if not (0 <= float(score) <= 10):
            issues.append(f"❌ Display holistic score out of range 0-10: {score}")
    elif score is not None:
        issues.append(f"❌ Invalid score type: {type(score).__name__}")

    recommendations = evaluation.get("recommendations")
    if recommendations is not None and not isinstance(recommendations, list):
        issues.append("❌ 'recommendations' must be a list")

    score_breakdown = evaluation.get("score_breakdown")
    if score_breakdown is not None:
        if not isinstance(score_breakdown, dict):
            issues.append("❌ 'score_breakdown' must be an object")
        else:
            for key, value in score_breakdown.items():
                if not isinstance(value, (int, float)):
                    issues.append(f"❌ score_breakdown.{key} must be numeric")
                    continue
                if not (0 <= float(value) <= 10):
                    issues.append(f"❌ score_breakdown.{key} out of range 0-10: {value}")

    cross_section_issues = evaluation.get("cross_section_issues")
    if cross_section_issues is not None:
        if not isinstance(cross_section_issues, list):
            issues.append("❌ 'cross_section_issues' must be a list")
        else:
            valid_severities = {"NIT", "WARN", "ERROR"}
            for entry in cross_section_issues:
                if not isinstance(entry, dict):
                    issues.append("⚠️  Invalid cross_section_issues entry (not an object)")
                    continue
                issue_id = entry.get("issue_id", "unknown")
                severity = entry.get("severity")
                if severity is not None and severity not in valid_severities:
                    issues.append(
                        f"⚠️  Invalid cross_section issue severity for '{issue_id}': {severity}"
                    )
                affected_sections = entry.get("affected_sections")
                if affected_sections is not None and not isinstance(affected_sections, list):
                    issues.append(
                        f"⚠️  cross_section issue '{issue_id}' field 'affected_sections' must be a list"
                    )
                targeted_actions = entry.get("targeted_actions")
                if targeted_actions is not None:
                    if not isinstance(targeted_actions, list):
                        issues.append(
                            f"⚠️  cross_section issue '{issue_id}' field 'targeted_actions' must be a list"
                        )
                    elif any(not isinstance(action, str) for action in targeted_actions):
                        issues.append(
                            f"⚠️  cross_section issue '{issue_id}' has non-string targeted_actions entries"
                        )

    return issues


def cross_validate_display_artifacts(
    plan_set: dict[str, Any] | None, evaluation: dict[str, Any] | None
) -> list[str]:
    """Cross-validate display plan and holistic evaluation references."""
    if plan_set is None or evaluation is None:
        return []

    issues: list[str] = []
    section_ids = {
        str(section.get("section_id"))
        for section in plan_set.get("section_plans", [])
        if isinstance(section, dict) and section.get("section_id") is not None
    }
    placement_ids = {
        str(placement.get("placement_id"))
        for section in plan_set.get("section_plans", [])
        if isinstance(section, dict)
        for lane_plan in section.get("lane_plans", [])
        if isinstance(lane_plan, dict)
        for coordination_plan in lane_plan.get("coordination_plans", [])
        if isinstance(coordination_plan, dict)
        for placement in coordination_plan.get("placements", [])
        if isinstance(placement, dict) and placement.get("placement_id") is not None
    }

    cross_section_issues = evaluation.get("cross_section_issues", [])
    if not isinstance(cross_section_issues, list):
        return ["❌ 'cross_section_issues' must be a list"]

    for item in cross_section_issues:
        if not isinstance(item, dict):
            issues.append("⚠️  Invalid cross_section_issues entry (not an object)")
            continue
        affected_sections = item.get("affected_sections", [])
        if not isinstance(affected_sections, list):
            issues.append("⚠️  cross_section_issues entry has non-list affected_sections")
            continue
        unknown = [section_id for section_id in affected_sections if section_id not in section_ids]
        if unknown:
            issue_id = item.get("issue_id", "unknown_issue")
            issues.append(
                f"⚠️  Holistic issue '{issue_id}' references unknown sections: {', '.join(unknown)}"
            )

        targeted_actions = item.get("targeted_actions", [])
        if not isinstance(targeted_actions, list):
            continue
        issue_id = item.get("issue_id", "unknown_issue")
        for action in targeted_actions:
            if not isinstance(action, str):
                continue
            section_matches = re.findall(r"\bsection\s+([a-zA-Z0-9_]+)", action)
            for matched_section in section_matches:
                if matched_section not in section_ids:
                    issues.append(
                        f"⚠️  Holistic issue '{issue_id}' targeted_action references "
                        f"unknown section '{matched_section}'"
                    )
            placement_matches = re.findall(r"\bplacement_id\s+([a-zA-Z0-9_]+)", action)
            for matched_placement in placement_matches:
                if matched_placement not in placement_ids:
                    issues.append(
                        f"⚠️  Holistic issue '{issue_id}' targeted_action references "
                        f"unknown placement_id '{matched_placement}'"
                    )

    return issues


def _parse_generic_xsq_effects(xsq_path: Path) -> tuple[list[GenericXSQEffect], int]:
    """Parse generic XSQ effects for display validation."""
    tree = ET.parse(str(xsq_path))
    root = tree.getroot()

    effectdb_count = 0
    effectdb = root.find("EffectDB")
    if effectdb is not None:
        effectdb_count = len(effectdb.findall("Effect"))

    element_effects = root.find("ElementEffects")
    if element_effects is None:
        return [], effectdb_count

    parsed: list[GenericXSQEffect] = []
    for element in element_effects.findall("Element"):
        element_name = element.get("name", "")
        for layer_index, layer in enumerate(element.findall("EffectLayer")):
            for effect in layer.findall("Effect"):
                start_ms = int(effect.get("startTime", "0"))
                end_ms = int(effect.get("endTime", "0"))
                ref_raw = effect.get("ref")
                ref = int(ref_raw) if ref_raw and ref_raw.isdigit() else None
                parsed.append(
                    GenericXSQEffect(
                        element_name=element_name,
                        layer_index=layer_index,
                        effect_name=effect.get("name", ""),
                        start_ms=start_ms,
                        end_ms=end_ms,
                        ref=ref,
                    )
                )

    return parsed, effectdb_count


def _default_display_xsq_trace_path(xsq_path: Path) -> Path:
    """Return the default sidecar path colocated with a display XSQ file."""
    return Path(f"{xsq_path}.trace.json")


def load_optional_display_xsq_trace(trace_path: Path) -> dict[str, Any] | None:
    """Load display XSQ trace sidecar if it exists and looks like an object."""
    if not trace_path.exists():
        return None
    payload = load_json(trace_path)
    if "entries" not in payload:
        return None
    return payload


def normalize_display_name(name: str) -> str:
    """Normalize display/target names for fuzzy matching across artifacts."""
    return re.sub(r"[^A-Z0-9]+", "", name.upper())


def normalize_display_target_alias_map(
    alias_map: dict[str, Any] | None,
) -> dict[str, set[str]]:
    """Normalize alias map for display target ids to XSQ element names."""
    normalized: dict[str, set[str]] = {}
    if alias_map is None:
        return normalized
    for raw_target, raw_aliases in alias_map.items():
        if not isinstance(raw_target, str):
            continue
        target_key = normalize_display_name(raw_target)
        if not target_key:
            continue
        aliases: list[str] = []
        if isinstance(raw_aliases, str):
            aliases = [raw_aliases]
        elif isinstance(raw_aliases, list):
            aliases = [item for item in raw_aliases if isinstance(item, str)]
        else:
            continue
        bucket = normalized.setdefault(target_key, set())
        bucket.add(target_key)
        for alias in aliases:
            alias_key = normalize_display_name(alias)
            if alias_key:
                bucket.add(alias_key)
    return normalized


def _extract_display_section_targets(plan_set: dict[str, Any]) -> list[tuple[str, int, int, set[str]]]:
    """Extract per-section target group ids referenced by display placements."""
    extracted: list[tuple[str, int, int, set[str]]] = []
    section_plans = plan_set.get("section_plans", [])
    if not isinstance(section_plans, list):
        return extracted

    for section in section_plans:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id", "unknown"))
        start_ms = section.get("start_ms")
        end_ms = section.get("end_ms")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int):
            continue
        targets: set[str] = set()
        lane_plans = section.get("lane_plans", [])
        if not isinstance(lane_plans, list):
            continue
        for lane_plan in lane_plans:
            if not isinstance(lane_plan, dict):
                continue
            coordination_plans = lane_plan.get("coordination_plans", [])
            if not isinstance(coordination_plans, list):
                continue
            for coordination_plan in coordination_plans:
                if not isinstance(coordination_plan, dict):
                    continue
                placements = coordination_plan.get("placements", [])
                if not isinstance(placements, list):
                    continue
                for placement in placements:
                    if not isinstance(placement, dict):
                        continue
                    target = placement.get("target")
                    if not isinstance(target, dict):
                        continue
                    if target.get("type") != "group":
                        continue
                    target_id = target.get("id")
                    if isinstance(target_id, str) and target_id:
                        targets.add(target_id)
        extracted.append((section_id, start_ms, end_ms, targets))
    return extracted


def _extract_display_plan_placements(
    plan_set: dict[str, Any],
) -> dict[str, dict[str, str | int]]:
    """Extract placement metadata keyed by placement_id from a display plan set."""
    placements: dict[str, dict[str, str | int]] = {}
    section_plans = plan_set.get("section_plans", [])
    if not isinstance(section_plans, list):
        return placements

    for section in section_plans:
        if not isinstance(section, dict):
            continue
        section_id = section.get("section_id")
        if not isinstance(section_id, str) or not section_id:
            continue
        lane_plans = section.get("lane_plans", [])
        if not isinstance(lane_plans, list):
            continue
        for lane_plan in lane_plans:
            if not isinstance(lane_plan, dict):
                continue
            lane_value = lane_plan.get("lane")
            lane = lane_value if isinstance(lane_value, str) else ""
            coordination_plans = lane_plan.get("coordination_plans", [])
            if not isinstance(coordination_plans, list):
                continue
            for coordination_plan in coordination_plans:
                if not isinstance(coordination_plan, dict):
                    continue
                placements_list = coordination_plan.get("placements", [])
                if not isinstance(placements_list, list):
                    continue
                for placement in placements_list:
                    if not isinstance(placement, dict):
                        continue
                    placement_id = placement.get("placement_id")
                    if not isinstance(placement_id, str) or not placement_id:
                        continue
                    target = placement.get("target")
                    target_id = ""
                    if isinstance(target, dict):
                        raw_target_id = target.get("id")
                        if isinstance(raw_target_id, str):
                            target_id = raw_target_id
                    template_id = placement.get("template_id")
                    placements[placement_id] = {
                        "section_id": section_id,
                        "lane": lane,
                        "target_id": target_id,
                        "template_id": template_id if isinstance(template_id, str) else "",
                    }
    return placements


def validate_display_xsq_target_coverage(
    effects: list[GenericXSQEffect],
    plan_set: dict[str, Any],
    *,
    alias_map: dict[str, Any] | None = None,
) -> list[str]:
    """Validate that planned display group targets receive effects in each section."""
    issues: list[str] = []
    if not effects:
        return issues

    element_names_by_norm: dict[str, set[str]] = {}
    for effect in effects:
        normalized = normalize_display_name(effect.element_name)
        if not normalized:
            continue
        element_names_by_norm.setdefault(normalized, set()).add(effect.element_name)
    normalized_aliases = normalize_display_target_alias_map(alias_map)

    for section_id, start_ms, end_ms, target_ids in _extract_display_section_targets(plan_set):
        if not target_ids:
            continue
        overlapping_effects = [
            effect
            for effect in effects
            if not (effect.end_ms <= start_ms or effect.start_ms >= end_ms)
        ]
        overlapping_norms = {normalize_display_name(effect.element_name) for effect in overlapping_effects}
        missing_targets: list[str] = []
        for target_id in sorted(target_ids):
            normalized_target = normalize_display_name(target_id)
            if not normalized_target:
                continue
            acceptable_names = normalized_aliases.get(normalized_target, {normalized_target})
            if overlapping_norms.isdisjoint(acceptable_names):
                missing_targets.append(target_id)
        if missing_targets:
            issues.append(
                f"⚠️  Display section '{section_id}' has no XSQ effect coverage for targets: "
                f"{', '.join(missing_targets)}"
            )
    return issues


def validate_display_xsq_trace_placement_coverage(
    plan_set: dict[str, Any],
    trace_payload: dict[str, Any],
    *,
    alias_map: dict[str, Any] | None = None,
) -> list[str]:
    """Validate placement-level render coverage using display XSQ sidecar metadata."""
    issues: list[str] = []
    plan_placements = _extract_display_plan_placements(plan_set)
    if not plan_placements:
        return issues

    raw_entries = trace_payload.get("entries", [])
    if not isinstance(raw_entries, list):
        return ["❌ Display XSQ trace sidecar field 'entries' must be a list"]

    normalized_aliases = normalize_display_target_alias_map(alias_map)
    seen_placement_ids: set[str] = set()
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            issues.append(f"⚠️  Display XSQ trace entry {index} is not an object")
            continue
        placement_id = entry.get("placement_id")
        if not isinstance(placement_id, str) or not placement_id:
            continue
        seen_placement_ids.add(placement_id)
        plan_meta = plan_placements.get(placement_id)
        if plan_meta is None:
            issues.append(
                f"⚠️  Display XSQ trace entry references unknown placement_id '{placement_id}'"
            )
            continue

        section_id = entry.get("section_id")
        expected_section = plan_meta["section_id"]
        if isinstance(section_id, str) and section_id != expected_section:
            issues.append(
                f"⚠️  Display XSQ trace placement '{placement_id}' section mismatch: "
                f"{section_id} != {expected_section}"
            )

        lane = entry.get("lane")
        expected_lane = plan_meta["lane"]
        if isinstance(lane, str) and expected_lane and lane != expected_lane:
            issues.append(
                f"⚠️  Display XSQ trace placement '{placement_id}' lane mismatch: "
                f"{lane} != {expected_lane}"
            )

        template_id = entry.get("template_id")
        expected_template_id = plan_meta["template_id"]
        if isinstance(template_id, str) and expected_template_id and template_id != expected_template_id:
            issues.append(
                f"⚠️  Display XSQ trace placement '{placement_id}' template mismatch: "
                f"{template_id} != {expected_template_id}"
            )

        expected_target_id = plan_meta["target_id"]
        if not isinstance(expected_target_id, str) or not expected_target_id:
            continue
        expected_target_norm = normalize_display_name(expected_target_id)
        acceptable_names = normalized_aliases.get(expected_target_norm, {expected_target_norm})

        group_id = entry.get("group_id")
        group_norm = normalize_display_name(group_id) if isinstance(group_id, str) else ""
        element_name = entry.get("element_name")
        element_norm = normalize_display_name(element_name) if isinstance(element_name, str) else ""
        if group_norm and group_norm not in acceptable_names:
            issues.append(
                f"⚠️  Display XSQ trace placement '{placement_id}' group target mismatch: "
                f"{group_id} != {expected_target_id}"
            )
        if element_norm and element_norm not in acceptable_names:
            issues.append(
                f"⚠️  Display XSQ trace placement '{placement_id}' element '{element_name}' "
                f"does not match planned target '{expected_target_id}'"
            )

    for placement_id in sorted(plan_placements):
        if placement_id not in seen_placement_ids:
            issues.append(
                f"⚠️  Display placement '{placement_id}' has no sidecar trace coverage in display XSQ"
            )

    return issues


def validate_display_xsq(
    xsq_path: Path,
    plan_set: dict[str, Any] | None = None,
    *,
    display_target_alias_map: dict[str, Any] | None = None,
    display_xsq_trace_payload: dict[str, Any] | None = None,
    quality_only: bool = False,
) -> list[str]:
    """Validate a display XSQ file using generic effect checks."""
    if not xsq_path.exists():
        return [f"❌ XSQ file not found: {xsq_path}"]

    issues: list[str] = []
    effects, effectdb_count = _parse_generic_xsq_effects(xsq_path)
    if not effects:
        return [f"❌ No effects found in XSQ: {xsq_path.name}"]

    for effect in effects:
        if effect.end_ms <= effect.start_ms:
            issues.append(
                f"❌ Invalid effect timing for {effect.element_name}/{effect.effect_name}: "
                f"{effect.start_ms}->{effect.end_ms}"
            )
        if effect.ref is not None and effect.ref > effectdb_count:
            issues.append(
                f"⚠️  Invalid effect ref {effect.ref} on {effect.element_name}/{effect.effect_name}"
            )

    grouped: dict[tuple[str, int], list[GenericXSQEffect]] = {}
    for effect in effects:
        key = (effect.element_name, effect.layer_index)
        grouped.setdefault(key, []).append(effect)

    for (element_name, layer_index), layer_effects in grouped.items():
        sorted_effects = sorted(layer_effects, key=lambda item: (item.start_ms, item.end_ms))
        for prev, current in pairwise(sorted_effects):
            if prev.overlaps(current):
                issues.append(
                    f"⚠️  Overlap in XSQ element '{element_name}' layer {layer_index}: "
                    f"{prev.start_ms}-{prev.end_ms} vs {current.start_ms}-{current.end_ms}"
                )

    if quality_only or plan_set is None:
        return issues

    section_plans = plan_set.get("section_plans", [])
    if not isinstance(section_plans, list):
        return issues

    effect_windows = [(effect.start_ms, effect.end_ms) for effect in effects]
    for section in section_plans:
        if not isinstance(section, dict):
            continue
        section_id = section.get("section_id", "unknown")
        start_ms = section.get("start_ms")
        end_ms = section.get("end_ms")
        if not isinstance(start_ms, int) or not isinstance(end_ms, int):
            continue
        covered = any(not (window_end <= start_ms or window_start >= end_ms) for window_start, window_end in effect_windows)
        if not covered:
            issues.append(f"⚠️  No XSQ effects overlap display section '{section_id}'")

    issues.extend(
        validate_display_xsq_target_coverage(
            effects,
            plan_set,
            alias_map=display_target_alias_map,
        )
    )
    if display_xsq_trace_payload is not None:
        issues.extend(
            validate_display_xsq_trace_placement_coverage(
                plan_set,
                display_xsq_trace_payload,
                alias_map=display_target_alias_map,
            )
        )

    return issues


def _guess_pipeline_from_files(
    *,
    requested_pipeline: str,
    sequence_name: str,
    repo_root: Path,
    plan_path: Path | None,
    raw_plan_path: Path | None,
    evaluation_path: Path | None,
    xsq_path: Path | None,
) -> PipelineName:
    if requested_pipeline in {"display", "mh"}:
        return requested_pipeline  # type: ignore[return-value]

    candidate_paths: list[Path] = []
    for path in (plan_path, raw_plan_path, evaluation_path):
        if path is not None and path.exists():
            candidate_paths.append(path)

    paths = resolve_sequence_paths(repo_root, sequence_name)
    candidate_paths.extend(
        path
        for path in (
            paths["display"]["plan"],
            paths["display"]["evaluation"],
            paths["mh"]["raw_plan"],
            _effective_mh_plan_path(paths["mh"]),
            paths["mh"]["evaluation"],
        )
        if path.exists()
    )

    for path in candidate_paths:
        try:
            detected = detect_pipeline_from_json(load_json(path))
        except Exception:
            continue
        if detected is not None:
            return detected

    if xsq_path is not None:
        if xsq_path.name.endswith("_display.xsq"):
            return "display"
        if xsq_path.name.endswith("_twinklr_mh.xsq"):
            return "mh"

    if paths["display"]["plan"].exists() or paths["display"]["xsq"].exists():
        return "display"
    return "mh"


def _summarize_issues(issues: list[str], title: str) -> int:
    print(f"\n=== {title} ===")
    if not issues:
        print("PASS")
        return 0
    critical = [issue for issue in issues if issue.startswith("❌")]
    warnings = [issue for issue in issues if issue.startswith("⚠️")]
    infos = [issue for issue in issues if issue not in critical and issue not in warnings]
    for issue in issues:
        print(issue)
    print(f"\nSummary: critical={len(critical)} warnings={len(warnings)} info={len(infos)}")
    return 1 if critical else 0


def _run_display_plan_mode(
    *,
    sequence_name: str,
    repo_root: Path,
    plan_path: Path | None,
    evaluation_path: Path | None,
) -> int:
    paths = resolve_sequence_paths(repo_root, sequence_name)["display"]
    effective_plan_path = plan_path or paths["plan"]
    effective_eval_path = evaluation_path or paths["evaluation"]

    issues: list[str] = []
    plan_payload: dict[str, Any] | None = None
    eval_payload: dict[str, Any] | None = None

    if not effective_plan_path.exists():
        issues.append(f"❌ Display plan set not found: {effective_plan_path}")
    else:
        plan_payload = load_json(effective_plan_path)
        issues.extend(validate_display_plan_structure(plan_payload))

    if not effective_eval_path.exists():
        issues.append(f"❌ Holistic evaluation not found: {effective_eval_path}")
    else:
        eval_payload = load_json(effective_eval_path)
        issues.extend(validate_display_evaluation_structure(eval_payload))

    issues.extend(cross_validate_display_artifacts(plan_payload, eval_payload))
    return _summarize_issues(issues, "Display Plan Validation")


def _run_display_xsq_mode(
    *,
    sequence_name: str,
    repo_root: Path,
    xsq_path: Path | None,
    plan_path: Path | None,
    display_target_map_path: Path | None,
    display_xsq_trace_path: Path | None,
    quality_only: bool,
) -> int:
    paths = resolve_sequence_paths(repo_root, sequence_name)["display"]
    effective_xsq_path = xsq_path or paths["xsq"]
    effective_plan_path = plan_path or paths["plan"]

    plan_payload: dict[str, Any] | None = None
    if effective_plan_path.exists():
        plan_payload = load_json(effective_plan_path)
    alias_map_payload: dict[str, Any] | None = None
    if display_target_map_path is not None and display_target_map_path.exists():
        alias_map_payload = load_json(display_target_map_path)
    trace_payload: dict[str, Any] | None = None
    effective_trace_path = display_xsq_trace_path or _default_display_xsq_trace_path(effective_xsq_path)
    trace_payload = load_optional_display_xsq_trace(effective_trace_path)

    issues = validate_display_xsq(
        effective_xsq_path,
        plan_payload,
        display_target_alias_map=alias_map_payload,
        display_xsq_trace_payload=trace_payload,
        quality_only=quality_only,
    )
    return _summarize_issues(issues, "Display XSQ Validation")


def _run_mh_plan_mode(*, sequence_name: str, repo_root: Path) -> int:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts.validation._core.mh_plan_validation import (
        MHPlanValidationPaths,
        run_mh_plan_validation,
    )
    from scripts.validation._core.reporting import print_text_summary

    paths = resolve_sequence_paths(repo_root, sequence_name)["mh"]
    result = run_mh_plan_validation(
        MHPlanValidationPaths(
            raw_plan_path=paths["raw_plan"],
            implementation_path=_effective_mh_plan_path(paths),
            evaluation_path=paths["evaluation"],
        )
    )
    print_text_summary("MH Plan Validation", result)
    return result.exit_code


def _run_mh_plan_mode_with_paths(
    *,
    sequence_name: str,
    repo_root: Path,
    raw_plan_path: Path | None,
    plan_path: Path | None,
    evaluation_path: Path | None,
) -> int:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts.validation._core.mh_plan_validation import (
        MHPlanValidationPaths,
        run_mh_plan_validation,
    )
    from scripts.validation._core.reporting import print_text_summary

    paths = resolve_sequence_paths(repo_root, sequence_name)["mh"]
    result = run_mh_plan_validation(
        MHPlanValidationPaths(
            raw_plan_path=raw_plan_path or paths["raw_plan"],
            implementation_path=plan_path or _effective_mh_plan_path(paths),
            evaluation_path=evaluation_path or paths["evaluation"],
        )
    )
    print_text_summary("MH Plan Validation", result)
    return result.exit_code


def _run_mh_xsq_mode(
    *,
    sequence_name: str,
    repo_root: Path,
    xsq_path: Path | None,
    plan_path: Path | None,
    raw_plan_path: Path | None,
    fixture_config_path: Path | None,
    quality_only: bool,
    output_json: Path | None,
) -> int:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from scripts.validation._core.mh_xsq_validation import (
        MHXSQValidationPaths,
        run_mh_xsq_validation,
    )
    from scripts.validation._core.reporting import print_text_summary

    paths = resolve_sequence_paths(repo_root, sequence_name)["mh"]
    result = run_mh_xsq_validation(
        MHXSQValidationPaths(
            xsq_path=xsq_path or paths["xsq"],
            implementation_path=plan_path or _effective_mh_plan_path(paths),
            raw_plan_path=raw_plan_path or paths["raw_plan"],
            fixture_config_path=fixture_config_path,
            output_json_path=output_json,
        ),
        quality_only=quality_only,
    )
    print_text_summary("MH XSQ Validation", result)
    return result.exit_code


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Unified artifact validation for MH/display")
    parser.add_argument(
        "sequence_name",
        nargs="?",
        default="need_a_favor",
        help="Artifact sequence directory name (default: need_a_favor)",
    )
    parser.add_argument(
        "--mode",
        choices=("plan", "xsq", "all"),
        default="all",
        help="Validation mode to run",
    )
    parser.add_argument(
        "--pipeline",
        choices=("auto", "display", "mh"),
        default="auto",
        help="Pipeline artifact format (auto-detect by default)",
    )
    parser.add_argument("--plan-path", type=Path, help="Explicit implementation/group-plan path")
    parser.add_argument("--raw-plan-path", type=Path, help="Explicit raw MH plan path")
    parser.add_argument("--evaluation-path", type=Path, help="Explicit evaluation path")
    parser.add_argument("--xsq-path", type=Path, help="Explicit XSQ path")
    parser.add_argument("--fixture-config-path", type=Path, help="MH fixture config path")
    parser.add_argument(
        "--display-target-map",
        type=Path,
        help="Optional JSON map of display target ids to XSQ element aliases",
    )
    parser.add_argument(
        "--display-xsq-trace-path",
        type=Path,
        help="Optional display XSQ trace sidecar JSON (defaults to <xsq>.trace.json)",
    )
    parser.add_argument("--quality-only", action="store_true", help="Skip deeper plan-vs-XSQ checks")
    parser.add_argument("--output-json", type=Path, help="MH XSQ issue JSON output path")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    pipeline = _guess_pipeline_from_files(
        requested_pipeline=args.pipeline,
        sequence_name=args.sequence_name,
        repo_root=repo_root,
        plan_path=args.plan_path,
        raw_plan_path=args.raw_plan_path,
        evaluation_path=args.evaluation_path,
        xsq_path=args.xsq_path,
    )

    print(f"Pipeline: {pipeline}")
    print(f"Mode: {args.mode}")
    exit_code = 0

    if args.mode in {"plan", "all"}:
        if pipeline == "display":
            result = _run_display_plan_mode(
                sequence_name=args.sequence_name,
                repo_root=repo_root,
                plan_path=args.plan_path,
                evaluation_path=args.evaluation_path,
            )
        else:
            result = _run_mh_plan_mode_with_paths(
                sequence_name=args.sequence_name,
                repo_root=repo_root,
                raw_plan_path=args.raw_plan_path,
                plan_path=args.plan_path,
                evaluation_path=args.evaluation_path,
            )
        exit_code = max(exit_code, result)

    if args.mode in {"xsq", "all"}:
        if pipeline == "display":
            result = _run_display_xsq_mode(
                sequence_name=args.sequence_name,
                repo_root=repo_root,
                xsq_path=args.xsq_path,
                plan_path=args.plan_path,
                display_target_map_path=args.display_target_map,
                display_xsq_trace_path=args.display_xsq_trace_path,
                quality_only=args.quality_only,
            )
        else:
            result = _run_mh_xsq_mode(
                sequence_name=args.sequence_name,
                repo_root=repo_root,
                xsq_path=args.xsq_path,
                plan_path=args.plan_path,
                raw_plan_path=args.raw_plan_path,
                fixture_config_path=args.fixture_config_path,
                quality_only=args.quality_only,
                output_json=args.output_json,
            )
        exit_code = max(exit_code, result)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
