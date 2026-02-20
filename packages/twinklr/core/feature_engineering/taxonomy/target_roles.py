"""Deterministic target-role abstraction engine (V1.4)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRole,
    TargetRoleAssignment,
)


@dataclass(frozen=True)
class TargetRoleAssignerOptions:
    """Runtime options for role assignment heuristics."""

    engine_version: str = "target_roles_v1"
    schema_version: str = "v1.4.0"


class TargetRoleAssigner:
    """Assign target semantic roles from layout and phrase context."""

    _ROLE_ORDER: tuple[TargetRole, ...] = (
        TargetRole.LEAD,
        TargetRole.IMPACT,
        TargetRole.MOTION,
        TargetRole.ACCENT,
        TargetRole.SUPPORT,
        TargetRole.BACKGROUND,
        TargetRole.FALLBACK,
    )

    def __init__(self, options: TargetRoleAssignerOptions | None = None) -> None:
        self._options = options or TargetRoleAssignerOptions()

    def assign(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        enriched_events: list[dict[str, Any]],
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    ) -> tuple[TargetRoleAssignment, ...]:
        phrase_by_event = {phrase.effect_event_id: phrase for phrase in phrases}
        taxonomy_by_event = {row.effect_event_id: row for row in taxonomy_rows}

        aggregates: dict[str, dict[str, Any]] = {}
        for event in enriched_events:
            if not isinstance(event, dict):
                continue
            target_name = str(event.get("target_name") or "")
            if not target_name:
                continue
            current = aggregates.get(target_name)
            if current is None:
                current = {
                    "target_name": target_name,
                    "target_kind": str(event.get("target_kind") or "unknown"),
                    "target_layout_group": event.get("target_layout_group"),
                    "target_category": event.get("target_category"),
                    "target_semantic_tags": set(),
                    "pixel_count": event.get("target_pixel_count"),
                    "event_count": 0,
                    "active_duration_ms": 0,
                    "high_energy": 0,
                    "accent": 0,
                    "motion": 0,
                    "sustained": 0,
                }
                aggregates[target_name] = current

            current["event_count"] += 1
            start_ms = int(event.get("start_ms") or 0)
            end_ms = int(event.get("end_ms") or start_ms)
            current["active_duration_ms"] += max(0, end_ms - start_ms)

            pixel_count = event.get("target_pixel_count")
            if isinstance(pixel_count, int):
                prior_pixels = current.get("pixel_count")
                if not isinstance(prior_pixels, int) or pixel_count > prior_pixels:
                    current["pixel_count"] = pixel_count

            tags = event.get("target_semantic_tags") or []
            if isinstance(tags, list):
                current["target_semantic_tags"].update(str(tag).lower() for tag in tags)

            event_id = str(event.get("effect_event_id") or "")
            phrase = phrase_by_event.get(event_id)
            if phrase is not None:
                if phrase.energy_class.value in {"high", "burst"}:
                    current["high_energy"] += 1
                if phrase.continuity_class.value == "sustained":
                    current["sustained"] += 1

            taxonomy = taxonomy_by_event.get(event_id)
            if taxonomy is not None:
                labels = {label.value for label in taxonomy.labels}
                if "accent_hit" in labels:
                    current["accent"] += 1
                if "rhythm_driver" in labels or "motion_driver" in labels:
                    current["motion"] += 1

        if not aggregates:
            return ()

        event_counts = [int(row["event_count"]) for row in aggregates.values()]
        high_activity_threshold = self._percentile(event_counts, 80.0)

        rows: list[TargetRoleAssignment] = []
        for target_name in sorted(aggregates.keys()):
            row = aggregates[target_name]
            assignment = self._assign_one(
                package_id=package_id,
                sequence_file_id=sequence_file_id,
                row=row,
                high_activity_threshold=high_activity_threshold,
            )
            rows.append(assignment)
        return tuple(rows)

    def _assign_one(
        self,
        *,
        package_id: str,
        sequence_file_id: str,
        row: dict[str, Any],
        high_activity_threshold: float,
    ) -> TargetRoleAssignment:
        tags = set(row["target_semantic_tags"])
        event_count = int(row["event_count"])
        pixel_count = row.get("pixel_count")
        high_energy = int(row["high_energy"])
        accent = int(row["accent"])
        motion = int(row["motion"])
        sustained = int(row["sustained"])

        scores: dict[TargetRole, float] = defaultdict(float)
        reasons: dict[TargetRole, list[str]] = defaultdict(list)

        if event_count >= 2 and event_count >= high_activity_threshold:
            scores[TargetRole.LEAD] += 0.40
            reasons[TargetRole.LEAD].append("high_activity")

        if isinstance(pixel_count, int) and pixel_count >= 500:
            scores[TargetRole.LEAD] += 0.35
            reasons[TargetRole.LEAD].append("large_pixel_count")

        if {"tree", "matrix", "main", "center"} & tags:
            scores[TargetRole.LEAD] += 0.30
            reasons[TargetRole.LEAD].append("semantic_main_fixture")

        if high_energy >= max(1, event_count // 3):
            scores[TargetRole.IMPACT] += 0.45
            reasons[TargetRole.IMPACT].append("high_energy_ratio")

        if accent >= max(1, event_count // 3):
            scores[TargetRole.ACCENT] += 0.45
            reasons[TargetRole.ACCENT].append("accent_taxonomy_density")

        if motion >= max(1, event_count // 3):
            scores[TargetRole.MOTION] += 0.45
            reasons[TargetRole.MOTION].append("motion_taxonomy_density")

        if sustained >= max(1, event_count // 2):
            scores[TargetRole.BACKGROUND] += 0.40
            reasons[TargetRole.BACKGROUND].append("sustained_continuity")

        if event_count > 0:
            scores[TargetRole.SUPPORT] += 0.20
            reasons[TargetRole.SUPPORT].append("active_target")

        role = TargetRole.FALLBACK
        role_score = 0.0
        role_reason_keys: tuple[str, ...] = ("fallback_default",)

        ranked = sorted(
            scores.items(),
            key=lambda item: (
                item[1],
                -self._ROLE_ORDER.index(item[0]),
            ),
            reverse=True,
        )
        if ranked and ranked[0][1] >= 0.35:
            role, role_score = ranked[0]
            role_reason_keys = tuple(sorted(reasons.get(role, [])))

        target_name = str(row["target_name"])
        target_kind = str(row["target_kind"])
        target_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{package_id}:{sequence_file_id}:{target_kind}:{target_name}:v1.4",
            )
        )

        semantic_tags = tuple(sorted(str(tag) for tag in tags))
        role_binding_key = f"{role.value}:{target_kind}:{target_name}"

        return TargetRoleAssignment(
            schema_version=self._options.schema_version,
            role_engine_version=self._options.engine_version,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            target_id=target_id,
            target_name=target_name,
            target_kind=target_kind,
            role=role,
            role_confidence=max(0.0, min(1.0, role_score)),
            reason_keys=role_reason_keys,
            event_count=event_count,
            active_duration_ms=int(row["active_duration_ms"]),
            pixel_count=pixel_count if isinstance(pixel_count, int) else None,
            target_layout_group=(
                str(row["target_layout_group"])
                if row.get("target_layout_group") is not None
                else None
            ),
            target_category=(
                str(row["target_category"]) if row.get("target_category") is not None else None
            ),
            target_semantic_tags=semantic_tags,
            role_binding_key=role_binding_key,
        )

    @staticmethod
    def _percentile(values: list[int], pct: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return float(sorted_values[0])
        idx = (len(sorted_values) - 1) * max(0.0, min(100.0, pct)) / 100.0
        lower = int(idx)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = idx - lower
        return (1.0 - weight) * sorted_values[lower] + weight * sorted_values[upper]
