"""Deterministic support-based template miner (V1.5)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models import EffectPhrase
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
    TemplateProvenance,
)


@dataclass(frozen=True)
class TemplateMinerOptions:
    """Runtime options for deterministic template mining."""

    schema_version: str = "v1.5.0"
    miner_version: str = "template_miner_v1"
    min_instance_count: int = 2
    min_distinct_pack_count: int = 1
    max_provenance_per_template: int = 100


class TemplateMiner:
    """Mine content and orchestration template catalogs from phrase corpora."""

    def __init__(self, options: TemplateMinerOptions | None = None) -> None:
        self._options = options or TemplateMinerOptions()

    def mine(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        target_roles: tuple[TargetRoleAssignment, ...],
    ) -> tuple[TemplateCatalog, TemplateCatalog]:
        taxonomy_by_phrase = {row.phrase_id: row for row in taxonomy_rows}
        role_by_target = {
            (row.package_id, row.sequence_file_id, row.target_name): row.role.value
            for row in target_roles
        }
        total_phrase_count = len(phrases)
        total_distinct_packs = max(1, len({phrase.package_id for phrase in phrases}))

        content_groups: dict[str, list[EffectPhrase]] = defaultdict(list)
        orchestration_groups: dict[str, list[EffectPhrase]] = defaultdict(list)
        content_assignment: dict[str, str] = {}
        orchestration_assignment: dict[str, str] = {}

        for phrase in phrases:
            taxonomy = taxonomy_by_phrase.get(phrase.phrase_id)
            labels = tuple(sorted(label.value for label in (taxonomy.labels if taxonomy else ())))
            role = role_by_target.get(
                (phrase.package_id, phrase.sequence_file_id, phrase.target_name), "fallback"
            )

            content_sig = self._content_signature(phrase, labels)
            orchestration_sig = self._orchestration_signature(phrase, labels, role)
            content_groups[content_sig].append(phrase)
            orchestration_groups[orchestration_sig].append(phrase)

        content_templates, content_assignment = self._finalize_groups(
            groups=content_groups,
            taxonomy_by_phrase=taxonomy_by_phrase,
            role_by_target=role_by_target,
            template_kind=TemplateKind.CONTENT,
            total_phrase_count=total_phrase_count,
            total_distinct_packs=total_distinct_packs,
        )
        orchestration_templates, orchestration_assignment = self._finalize_groups(
            groups=orchestration_groups,
            taxonomy_by_phrase=taxonomy_by_phrase,
            role_by_target=role_by_target,
            template_kind=TemplateKind.ORCHESTRATION,
            total_phrase_count=total_phrase_count,
            total_distinct_packs=total_distinct_packs,
        )

        content_catalog = self._build_catalog(
            template_kind=TemplateKind.CONTENT,
            phrases=phrases,
            templates=content_templates,
            assignment_map=content_assignment,
            total_phrase_count=total_phrase_count,
        )
        orchestration_catalog = self._build_catalog(
            template_kind=TemplateKind.ORCHESTRATION,
            phrases=phrases,
            templates=orchestration_templates,
            assignment_map=orchestration_assignment,
            total_phrase_count=total_phrase_count,
        )
        return content_catalog, orchestration_catalog

    def _finalize_groups(
        self,
        *,
        groups: dict[str, list[EffectPhrase]],
        taxonomy_by_phrase: dict[str, PhraseTaxonomyRecord],
        role_by_target: dict[tuple[str, str, str], str],
        template_kind: TemplateKind,
        total_phrase_count: int,
        total_distinct_packs: int,
    ) -> tuple[tuple[MinedTemplate, ...], dict[str, str]]:
        templates: list[MinedTemplate] = []
        assignments: dict[str, str] = {}

        for signature in sorted(groups.keys()):
            rows = groups[signature]
            if len(rows) < self._options.min_instance_count:
                continue

            distinct_packs = {row.package_id for row in rows}
            if len(distinct_packs) < self._options.min_distinct_pack_count:
                continue

            template_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{template_kind.value}:{signature}:{self._options.miner_version}",
                )
            )
            for row in rows:
                assignments[row.phrase_id] = template_id

            first = rows[0]
            onset_values = [
                row.onset_sync_score
                for row in rows
                if row.onset_sync_score is not None and 0.0 <= row.onset_sync_score <= 1.0
            ]
            onset_sync_mean = (
                round(sum(onset_values) / len(onset_values), 6) if onset_values else None
            )

            taxonomy_labels: set[str] = set()
            for row in rows:
                tax = taxonomy_by_phrase.get(row.phrase_id)
                if tax is not None:
                    taxonomy_labels.update(label.value for label in tax.labels)

            role: str | None = None
            if template_kind is TemplateKind.ORCHESTRATION:
                role_counts: dict[str, int] = defaultdict(int)
                for row in rows:
                    key = (row.package_id, row.sequence_file_id, row.target_name)
                    role_counts[role_by_target.get(key, "fallback")] += 1
                ranked_roles = sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
                role = ranked_roles[0][0] if ranked_roles else "fallback"

            support_count = len(rows)
            support_ratio = round(support_count / max(1, total_phrase_count), 6)
            cross_pack_stability = round(len(distinct_packs) / max(1, total_distinct_packs), 6)

            provenance = tuple(
                TemplateProvenance(
                    package_id=row.package_id,
                    sequence_file_id=row.sequence_file_id,
                    phrase_id=row.phrase_id,
                    effect_event_id=row.effect_event_id,
                )
                for row in sorted(
                    rows,
                    key=lambda item: (
                        item.package_id,
                        item.sequence_file_id,
                        item.phrase_id,
                    ),
                )[: self._options.max_provenance_per_template]
            )

            templates.append(
                MinedTemplate(
                    template_id=template_id,
                    template_kind=template_kind,
                    template_signature=signature,
                    support_count=support_count,
                    distinct_pack_count=len(distinct_packs),
                    support_ratio=support_ratio,
                    cross_pack_stability=cross_pack_stability,
                    onset_sync_mean=onset_sync_mean,
                    role=role,
                    taxonomy_labels=tuple(sorted(taxonomy_labels)),
                    effect_family=first.effect_family,
                    motion_class=first.motion_class.value,
                    color_class=first.color_class.value,
                    energy_class=first.energy_class.value,
                    continuity_class=first.continuity_class.value,
                    spatial_class=first.spatial_class.value,
                    provenance=provenance,
                )
            )

        templates.sort(key=lambda row: row.template_id)
        return tuple(templates), assignments

    def _build_catalog(
        self,
        *,
        template_kind: TemplateKind,
        phrases: tuple[EffectPhrase, ...],
        templates: tuple[MinedTemplate, ...],
        assignment_map: dict[str, str],
        total_phrase_count: int,
    ) -> TemplateCatalog:
        assignments = tuple(
            TemplateAssignment(
                package_id=phrase.package_id,
                sequence_file_id=phrase.sequence_file_id,
                phrase_id=phrase.phrase_id,
                effect_event_id=phrase.effect_event_id,
                template_id=assignment_map[phrase.phrase_id],
            )
            for phrase in sorted(
                phrases,
                key=lambda item: (item.package_id, item.sequence_file_id, item.phrase_id),
            )
            if phrase.phrase_id in assignment_map
        )
        assigned_phrase_count = len(assignments)
        coverage = (
            round(assigned_phrase_count / total_phrase_count, 6) if total_phrase_count else 0.0
        )

        return TemplateCatalog(
            schema_version=self._options.schema_version,
            miner_version=self._options.miner_version,
            template_kind=template_kind,
            total_phrase_count=total_phrase_count,
            assigned_phrase_count=assigned_phrase_count,
            assignment_coverage=coverage,
            min_instance_count=self._options.min_instance_count,
            min_distinct_pack_count=self._options.min_distinct_pack_count,
            templates=templates,
            assignments=assignments,
        )

    @staticmethod
    def _content_signature(phrase: EffectPhrase, labels: tuple[str, ...]) -> str:
        return "|".join(
            (
                phrase.effect_family,
                phrase.motion_class.value,
                phrase.color_class.value,
                phrase.energy_class.value,
                phrase.continuity_class.value,
                phrase.spatial_class.value,
                ",".join(labels),
            )
        )

    @staticmethod
    def _orchestration_signature(phrase: EffectPhrase, labels: tuple[str, ...], role: str) -> str:
        return "|".join(
            (
                TemplateMiner._content_signature(phrase, labels),
                role,
                str(phrase.layer_index),
                phrase.section_label or "",
            )
        )
