"""Deterministic quality gates for feature engineering outputs (V1.9)."""

from __future__ import annotations

from dataclasses import dataclass

from twinklr.core.feature_engineering.models import (
    EffectPhrase,
    PhraseTaxonomyRecord,
    TemplateCatalog,
)
from twinklr.core.feature_engineering.models.quality import QualityCheckResult, QualityReport
from twinklr.core.feature_engineering.models.transitions import TransitionGraph


@dataclass(frozen=True)
class QualityGateOptions:
    """Threshold options for quality checks."""

    min_template_coverage: float = 0.80
    min_taxonomy_confidence_mean: float = 0.30
    max_unknown_effect_family_ratio: float = 0.02
    max_unknown_motion_ratio: float = 0.02
    max_single_unknown_effect_type_ratio: float = 0.01


class FeatureQualityGates:
    """Run deterministic in-scope quality checks."""

    def __init__(self, options: QualityGateOptions | None = None) -> None:
        self._options = options or QualityGateOptions()

    def evaluate(
        self,
        *,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        orchestration_catalog: TemplateCatalog,
        transition_graph: TransitionGraph,
    ) -> QualityReport:
        checks: list[QualityCheckResult] = []

        alignment_ok = len(phrases) > 0
        checks.append(
            QualityCheckResult(
                check_id="alignment_completeness",
                passed=alignment_ok,
                value=len(phrases),
                threshold=1,
                message="At least one aligned phrase must exist.",
            )
        )

        coverage = orchestration_catalog.assignment_coverage
        checks.append(
            QualityCheckResult(
                check_id="template_assignment_coverage",
                passed=coverage >= self._options.min_template_coverage,
                value=coverage,
                threshold=self._options.min_template_coverage,
                message="Orchestration template assignment coverage threshold.",
            )
        )

        conf_values = [
            conf
            for row in taxonomy_rows
            for conf in row.label_confidences
            if isinstance(conf, float)
        ]
        conf_mean = (sum(conf_values) / len(conf_values)) if conf_values else 0.0
        checks.append(
            QualityCheckResult(
                check_id="taxonomy_confidence_mean",
                passed=conf_mean >= self._options.min_taxonomy_confidence_mean,
                value=round(conf_mean, 6),
                threshold=self._options.min_taxonomy_confidence_mean,
                message="Average taxonomy label confidence.",
            )
        )

        unique_phrase_ids = {phrase.phrase_id for phrase in phrases}
        deterministic_ok = len(unique_phrase_ids) == len(phrases)
        checks.append(
            QualityCheckResult(
                check_id="deterministic_phrase_ids_unique",
                passed=deterministic_ok,
                value=len(unique_phrase_ids),
                threshold=len(phrases),
                message="Phrase IDs must be unique.",
            )
        )

        unknown_effect_family_count = sum(
            1 for phrase in phrases if phrase.effect_family == "unknown"
        )
        unknown_effect_family_ratio = unknown_effect_family_count / len(phrases) if phrases else 0.0
        checks.append(
            QualityCheckResult(
                check_id="unknown_effect_family_ratio",
                passed=unknown_effect_family_ratio <= self._options.max_unknown_effect_family_ratio,
                value=round(unknown_effect_family_ratio, 6),
                threshold=self._options.max_unknown_effect_family_ratio,
                message="Unknown effect-family ratio should remain under threshold.",
            )
        )

        unknown_motion_count = sum(
            1 for phrase in phrases if phrase.motion_class.value == "unknown"
        )
        unknown_motion_ratio = unknown_motion_count / len(phrases) if phrases else 0.0
        checks.append(
            QualityCheckResult(
                check_id="unknown_motion_ratio",
                passed=unknown_motion_ratio <= self._options.max_unknown_motion_ratio,
                value=round(unknown_motion_ratio, 6),
                threshold=self._options.max_unknown_motion_ratio,
                message="Unknown motion-class ratio should remain under threshold.",
            )
        )

        unknown_by_effect_type: dict[str, int] = {}
        for phrase in phrases:
            if phrase.effect_family != "unknown":
                continue
            unknown_by_effect_type[phrase.effect_type] = (
                unknown_by_effect_type.get(phrase.effect_type, 0) + 1
            )
        max_single_unknown_effect_type_count = max(unknown_by_effect_type.values(), default=0)
        max_single_unknown_effect_type_ratio = (
            max_single_unknown_effect_type_count / len(phrases) if phrases else 0.0
        )
        checks.append(
            QualityCheckResult(
                check_id="single_unknown_effect_type_ratio",
                passed=max_single_unknown_effect_type_ratio
                <= self._options.max_single_unknown_effect_type_ratio,
                value=round(max_single_unknown_effect_type_ratio, 6),
                threshold=self._options.max_single_unknown_effect_type_ratio,
                message="Largest unknown effect-type ratio should remain under threshold.",
            )
        )

        graph_integrity_ok = transition_graph.total_edges >= 0 and transition_graph.total_nodes >= 0
        checks.append(
            QualityCheckResult(
                check_id="transition_graph_integrity",
                passed=graph_integrity_ok,
                value=transition_graph.total_edges,
                threshold=0,
                message="Transition graph metadata integrity.",
            )
        )

        passed = all(row.passed for row in checks)
        return QualityReport(
            schema_version="v1.9.0",
            report_version="quality_v1",
            passed=passed,
            checks=tuple(checks),
            metadata={
                "phrase_count": str(len(phrases)),
                "taxonomy_rows": str(len(taxonomy_rows)),
                "transition_edges": str(transition_graph.total_edges),
                "unknown_effect_family_count": str(unknown_effect_family_count),
                "unknown_motion_count": str(unknown_motion_count),
                "max_single_unknown_effect_type_count": str(max_single_unknown_effect_type_count),
            },
        )
