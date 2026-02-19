"""Template diagnostics for mined catalog quality visibility (V1 follow-up)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from twinklr.core.feature_engineering.models.taxonomy import PhraseTaxonomyRecord
from twinklr.core.feature_engineering.models.template_diagnostics import (
    TemplateDiagnosticFlag,
    TemplateDiagnosticRow,
    TemplateDiagnosticsReport,
    TemplateDiagnosticThresholds,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateAssignment,
    TemplateCatalog,
)


@dataclass(frozen=True)
class TemplateDiagnosticsOptions:
    schema_version: str = "v1.0.0"
    diagnostics_version: str = "template_diagnostics_v1"
    low_support_max_count: int = 3
    high_concentration_min_ratio: float = 0.8
    high_variance_min_score: float = 0.65
    over_generic_min_support_count: int = 50
    over_generic_max_dominant_taxonomy_ratio: float = 0.35


class TemplateDiagnosticsBuilder:
    """Build deterministic template diagnostics from mined catalogs."""

    def __init__(self, options: TemplateDiagnosticsOptions | None = None) -> None:
        self._options = options or TemplateDiagnosticsOptions()

    def build(
        self,
        *,
        content_catalog: TemplateCatalog,
        orchestration_catalog: TemplateCatalog,
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    ) -> TemplateDiagnosticsReport:
        taxonomy_by_phrase = {row.phrase_id: row for row in taxonomy_rows}

        rows: list[TemplateDiagnosticRow] = []
        rows.extend(
            self._build_rows_for_catalog(
                catalog=content_catalog,
                taxonomy_by_phrase=taxonomy_by_phrase,
            )
        )
        rows.extend(
            self._build_rows_for_catalog(
                catalog=orchestration_catalog,
                taxonomy_by_phrase=taxonomy_by_phrase,
            )
        )

        rows.sort(key=lambda row: (row.template_kind.value, row.template_id))
        low_support = tuple(
            row.template_id for row in rows if TemplateDiagnosticFlag.LOW_SUPPORT in row.flags
        )
        high_concentration = tuple(
            row.template_id
            for row in rows
            if TemplateDiagnosticFlag.HIGH_CONCENTRATION in row.flags
        )
        high_variance = tuple(
            row.template_id for row in rows if TemplateDiagnosticFlag.HIGH_VARIANCE in row.flags
        )
        over_generic = tuple(
            row.template_id for row in rows if TemplateDiagnosticFlag.OVER_GENERIC in row.flags
        )

        flagged = {
            *low_support,
            *high_concentration,
            *high_variance,
            *over_generic,
        }

        return TemplateDiagnosticsReport(
            schema_version=self._options.schema_version,
            diagnostics_version=self._options.diagnostics_version,
            thresholds=TemplateDiagnosticThresholds(
                low_support_max_count=self._options.low_support_max_count,
                high_concentration_min_ratio=self._options.high_concentration_min_ratio,
                high_variance_min_score=self._options.high_variance_min_score,
                over_generic_min_support_count=self._options.over_generic_min_support_count,
                over_generic_max_dominant_taxonomy_ratio=self._options.over_generic_max_dominant_taxonomy_ratio,
            ),
            total_templates=len(rows),
            flagged_template_count=len(flagged),
            low_support_templates=low_support,
            high_concentration_templates=high_concentration,
            high_variance_templates=high_variance,
            over_generic_templates=over_generic,
            rows=tuple(rows),
        )

    def _build_rows_for_catalog(
        self,
        *,
        catalog: TemplateCatalog,
        taxonomy_by_phrase: dict[str, PhraseTaxonomyRecord],
    ) -> list[TemplateDiagnosticRow]:
        assignments_by_template: dict[str, list[TemplateAssignment]] = defaultdict(list)
        for assignment in catalog.assignments:
            assignments_by_template[assignment.template_id].append(assignment)

        rows: list[TemplateDiagnosticRow] = []
        for template in catalog.templates:
            assignments = assignments_by_template.get(template.template_id, [])
            rows.append(
                self._build_row(
                    template=template,
                    assignments=assignments,
                    taxonomy_by_phrase=taxonomy_by_phrase,
                )
            )
        return rows

    def _build_row(
        self,
        *,
        template: MinedTemplate,
        assignments: list[TemplateAssignment],
        taxonomy_by_phrase: dict[str, PhraseTaxonomyRecord],
    ) -> TemplateDiagnosticRow:
        support_count = template.support_count
        sequence_counts: dict[str, int] = defaultdict(int)
        packs: set[str] = set()

        taxonomy_label_counts: dict[str, int] = defaultdict(int)

        for assignment in assignments:
            packs.add(assignment.package_id)
            sequence_key = f"{assignment.package_id}:{assignment.sequence_file_id}"
            sequence_counts[sequence_key] += 1

            taxonomy = taxonomy_by_phrase.get(assignment.phrase_id)
            if taxonomy is None or not taxonomy.labels:
                taxonomy_label_counts["unknown"] += 1
            else:
                taxonomy_label_counts[taxonomy.labels[0].value] += 1

        max_sequence_count = max(sequence_counts.values()) if sequence_counts else 0
        concentration_ratio = (
            max_sequence_count / support_count if support_count > 0 else 0.0
        )

        if taxonomy_label_counts:
            dominant_label = sorted(
                taxonomy_label_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            dominant_label_name = dominant_label[0]
            dominant_ratio = dominant_label[1] / support_count if support_count > 0 else 0.0
        else:
            dominant_label_name = "unknown"
            dominant_ratio = 0.0

        variance_score = 1.0 - dominant_ratio

        flags: list[TemplateDiagnosticFlag] = []
        if support_count <= self._options.low_support_max_count:
            flags.append(TemplateDiagnosticFlag.LOW_SUPPORT)
        if concentration_ratio >= self._options.high_concentration_min_ratio:
            flags.append(TemplateDiagnosticFlag.HIGH_CONCENTRATION)
        if variance_score >= self._options.high_variance_min_score:
            flags.append(TemplateDiagnosticFlag.HIGH_VARIANCE)
        if (
            support_count >= self._options.over_generic_min_support_count
            and dominant_ratio <= self._options.over_generic_max_dominant_taxonomy_ratio
        ):
            flags.append(TemplateDiagnosticFlag.OVER_GENERIC)

        return TemplateDiagnosticRow(
            template_id=template.template_id,
            template_kind=template.template_kind,
            effect_family=template.effect_family,
            role=template.role,
            support_count=support_count,
            distinct_pack_count=len(packs),
            distinct_sequence_count=len(sequence_counts),
            concentration_ratio=round(concentration_ratio, 6),
            dominant_taxonomy_label=dominant_label_name,
            dominant_taxonomy_ratio=round(dominant_ratio, 6),
            variance_score=round(variance_score, 6),
            flags=tuple(flags),
        )
