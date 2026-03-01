"""Artifact writer for the feature-engineering pipeline — CQ-01.

All ``_write_*`` logic that was embedded in ``FeatureEngineeringPipeline``
is extracted here. ``ArtifactWriter`` accepts data and output paths as
parameters; it has no dependency on pipeline state.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    AudioDiscoveryResult,
    ColorNarrativeRow,
    EffectPhrase,
    FeatureBundle,
    LayeringFeatureRow,
    PhraseTaxonomyRecord,
    QualityReport,
    SequencerAdapterBundle,
    TargetRoleAssignment,
    TemplateCatalog,
    TemplateRetrievalIndex,
    TransitionGraph,
)
from twinklr.core.feature_engineering.models.ann_retrieval import (
    AnnRetrievalEvalReport,
    AnnRetrievalIndex,
)
from twinklr.core.feature_engineering.models.clustering import TemplateClusterCatalog
from twinklr.core.feature_engineering.models.learned_taxonomy import (
    LearnedTaxonomyEvalReport,
    LearnedTaxonomyModel,
)
from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.stacks import EffectStack
from twinklr.core.feature_engineering.models.template_diagnostics import (
    TemplateDiagnosticsReport,
)
from twinklr.core.feature_engineering.models.temporal_motifs import TemporalMotifCatalog
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


class ArtifactWriter:
    """Write all file-system artifacts produced by the feature-engineering pipeline.

    This class is a thin coordinator that delegates to
    ``FeatureEngineeringWriter`` for structured dataset files. It also
    contains the diagnostics-building logic that was previously embedded
    in ``FeatureEngineeringPipeline``.

    All public methods accept data and output paths as parameters. There is
    no dependency on pipeline state; callers pass exactly what they have.

    Args:
        writer: Optional ``FeatureEngineeringWriter`` to use for structured
            dataset output. A default instance is created if not supplied.

    Example::

        aw = ArtifactWriter()
        aw.write_aligned_events(output_dir, aligned_events)
    """

    def __init__(self, *, writer: FeatureEngineeringWriter | None = None) -> None:
        self._writer = writer or FeatureEngineeringWriter()

    # ------------------------------------------------------------------
    # Per-profile artifact writers
    # ------------------------------------------------------------------

    def write_audio_discovery_json(self, output_dir: Path, result: AudioDiscoveryResult) -> None:
        """Write audio discovery result as JSON."""
        self._writer.write_audio_discovery_json(output_dir, result)

    def write_feature_bundle_json(self, output_dir: Path, bundle: FeatureBundle) -> None:
        """Write feature bundle as JSON."""
        self._writer.write_feature_bundle_json(output_dir, bundle)

    def write_aligned_events(
        self, output_dir: Path, aligned_events: tuple[AlignedEffectEvent, ...]
    ) -> Path:
        """Write aligned-events dataset."""
        return self._writer.write_aligned_events(output_dir, aligned_events)

    def write_effect_phrases(self, output_dir: Path, phrases: tuple[EffectPhrase, ...]) -> Path:
        """Write effect-phrases dataset."""
        return self._writer.write_effect_phrases(output_dir, phrases)

    def write_phrase_taxonomy(
        self, output_dir: Path, rows: tuple[PhraseTaxonomyRecord, ...]
    ) -> Path:
        """Write phrase-taxonomy dataset."""
        return self._writer.write_phrase_taxonomy(output_dir, rows)

    def write_target_roles(self, output_dir: Path, rows: tuple[TargetRoleAssignment, ...]) -> Path:
        """Write target-role assignment dataset."""
        return self._writer.write_target_roles(output_dir, rows)

    # ------------------------------------------------------------------
    # Corpus-level artifact writers (delegate to inner writer)
    # ------------------------------------------------------------------

    def write_content_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        """Write content template catalog as JSON."""
        return self._writer.write_content_templates(output_root, catalog)

    def write_orchestration_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        """Write orchestration template catalog as JSON."""
        return self._writer.write_orchestration_templates(output_root, catalog)

    def write_transition_graph(self, output_root: Path, graph: TransitionGraph) -> Path:
        """Write transition graph as JSON."""
        return self._writer.write_transition_graph(output_root, graph)

    def write_layering_features(
        self, output_root: Path, rows: tuple[LayeringFeatureRow, ...]
    ) -> Path:
        """Write layering-features dataset."""
        return self._writer.write_layering_features(output_root, rows)

    def write_color_narrative(self, output_root: Path, rows: tuple[ColorNarrativeRow, ...]) -> Path:
        """Write colour-narrative dataset."""
        return self._writer.write_color_narrative(output_root, rows)

    def write_quality_report(self, output_root: Path, report: QualityReport) -> Path:
        """Write quality report as JSON."""
        return self._writer.write_quality_report(output_root, report)

    def write_template_retrieval_index(
        self, output_root: Path, index: TemplateRetrievalIndex
    ) -> Path:
        """Write template retrieval index as JSON."""
        return self._writer.write_template_retrieval_index(output_root, index)

    def write_template_diagnostics(
        self, output_root: Path, diagnostics: TemplateDiagnosticsReport
    ) -> Path:
        """Write template diagnostics report as JSON."""
        return self._writer.write_template_diagnostics(output_root, diagnostics)

    def write_feature_store_manifest(self, output_root: Path, manifest: dict[str, str]) -> Path:
        """Write feature store manifest as JSON."""
        return self._writer.write_feature_store_manifest(output_root, manifest)

    def write_motif_catalog(self, output_root: Path, catalog: MotifCatalog) -> Path:
        """Write motif catalog as JSON."""
        return self._writer.write_motif_catalog(output_root, catalog)

    def write_temporal_motif_catalog(
        self, output_root: Path, catalog: TemporalMotifCatalog
    ) -> None:
        """Write temporal motif catalog as JSON."""
        self._writer.write_temporal_motif_catalog(output_root, catalog)

    def write_cluster_catalog(self, output_root: Path, catalog: TemplateClusterCatalog) -> Path:
        """Write cluster candidate catalog as JSON."""
        return self._writer.write_cluster_catalog(output_root, catalog)

    def write_cluster_review_queue(
        self, output_root: Path, catalog: TemplateClusterCatalog
    ) -> Path:
        """Write cluster review queue as JSONL."""
        return self._writer.write_cluster_review_queue(output_root, catalog)

    def write_learned_taxonomy_model(self, output_root: Path, model: LearnedTaxonomyModel) -> Path:
        """Write learned taxonomy model bundle as JSON."""
        return self._writer.write_learned_taxonomy_model(output_root, model)

    def write_learned_taxonomy_eval(
        self, output_root: Path, report: LearnedTaxonomyEvalReport
    ) -> Path:
        """Write learned taxonomy evaluation report as JSON."""
        return self._writer.write_learned_taxonomy_eval(output_root, report)

    def write_ann_retrieval_index(self, output_root: Path, index: AnnRetrievalIndex) -> Path:
        """Write ANN retrieval index as JSON."""
        return self._writer.write_ann_retrieval_index(output_root, index)

    def write_ann_retrieval_eval(self, output_root: Path, report: AnnRetrievalEvalReport) -> Path:
        """Write ANN retrieval evaluation report as JSON."""
        return self._writer.write_ann_retrieval_eval(output_root, report)

    def write_stack_catalog(self, output_root: Path, stacks: tuple[EffectStack, ...]) -> Path:
        """Write detected stack catalog as JSON."""
        return self._writer.write_stack_catalog(output_root, stacks)

    def write_recipe_catalog(self, output_root: Path, recipes: list[EffectRecipe]) -> Path:
        """Write promoted recipe catalog as JSON."""
        return self._writer.write_recipe_catalog(output_root, recipes)

    def write_planner_adapter_payloads(
        self, output_root: Path, payloads: tuple[SequencerAdapterBundle, ...]
    ) -> Path:
        """Write planner adapter payloads as JSONL."""
        return self._writer.write_planner_adapter_payloads(output_root, payloads)

    def write_planner_adapter_acceptance(
        self, output_root: Path, payload: dict[str, object]
    ) -> Path:
        """Write planner adapter acceptance report as JSON."""
        return self._writer.write_planner_adapter_acceptance(output_root, payload)

    # ------------------------------------------------------------------
    # Unknown diagnostics — higher-level write
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_effect_key(effect_type: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", effect_type.strip().lower())

    def build_unknown_diagnostics(self, phrases: tuple[EffectPhrase, ...]) -> dict[str, Any]:
        """Build the unknown-diagnostics summary dict from a phrase corpus.

        Args:
            phrases: All effect phrases in the corpus.

        Returns:
            Dictionary suitable for JSON serialisation containing counts,
            ratios, and sample data for unknown effect families and motions.
        """
        total = len(phrases)
        unknown_effect_rows = [row for row in phrases if row.effect_family == "unknown"]
        unknown_motion_rows = [row for row in phrases if row.motion_class.value == "unknown"]

        unknown_effect_ratio = len(unknown_effect_rows) / total if total > 0 else 0.0
        unknown_motion_ratio = len(unknown_motion_rows) / total if total > 0 else 0.0

        by_effect_type: dict[str, list[EffectPhrase]] = {}
        for row in unknown_effect_rows:
            by_effect_type.setdefault(row.effect_type, []).append(row)

        top_unknown_effect_types: list[dict[str, Any]] = []
        sorted_unknown = sorted(
            by_effect_type.items(),
            key=lambda item: (-len(item[1]), self._normalize_effect_key(item[0]), item[0]),
        )
        for effect_type, rows in sorted_unknown[:25]:
            top_unknown_effect_types.append(
                {
                    "effect_type": effect_type,
                    "normalized_key": self._normalize_effect_key(effect_type),
                    "count": len(rows),
                    "distinct_package_count": len({row.package_id for row in rows}),
                    "distinct_sequence_count": len({row.sequence_file_id for row in rows}),
                    "sample_rows": [
                        {
                            "phrase_id": row.phrase_id,
                            "package_id": row.package_id,
                            "sequence_file_id": row.sequence_file_id,
                            "target_name": row.target_name,
                            "start_ms": row.start_ms,
                            "duration_ms": row.duration_ms,
                            "map_confidence": row.map_confidence,
                            "effect_family": row.effect_family,
                            "motion_class": row.motion_class.value,
                        }
                        for row in rows[:3]
                    ],
                }
            )

        alias_candidate_groups: list[dict[str, Any]] = []
        by_normalized_key: dict[str, list[str]] = {}
        for effect_type in by_effect_type:
            normalized = self._normalize_effect_key(effect_type)
            by_normalized_key.setdefault(normalized, []).append(effect_type)
        for normalized_key, names in sorted(by_normalized_key.items()):
            distinct = sorted(set(names))
            if len(distinct) <= 1:
                continue
            alias_candidate_groups.append(
                {
                    "normalized_key": normalized_key,
                    "raw_effect_types": distinct,
                }
            )

        unknown_motion_by_effect_family: list[dict[str, Any]] = []
        by_motion_family: dict[str, list[EffectPhrase]] = {}
        for row in unknown_motion_rows:
            by_motion_family.setdefault(row.effect_family, []).append(row)
        for family, rows in sorted(
            by_motion_family.items(), key=lambda item: (-len(item[1]), item[0])
        )[:25]:
            unknown_motion_by_effect_family.append(
                {
                    "effect_family": family,
                    "count": len(rows),
                    "distinct_package_count": len({row.package_id for row in rows}),
                    "distinct_sequence_count": len({row.sequence_file_id for row in rows}),
                    "sample_effect_types": sorted({row.effect_type for row in rows})[:5],
                }
            )

        return {
            "schema_version": "v1.0.0",
            "total_phrase_count": total,
            "unknown_effect_family_count": len(unknown_effect_rows),
            "unknown_effect_family_ratio": round(unknown_effect_ratio, 6),
            "unknown_motion_count": len(unknown_motion_rows),
            "unknown_motion_ratio": round(unknown_motion_ratio, 6),
            "top_unknown_effect_types": top_unknown_effect_types,
            "alias_candidate_groups": alias_candidate_groups,
            "unknown_motion_by_effect_family": unknown_motion_by_effect_family,
        }

    def write_unknown_diagnostics(
        self, output_root: Path, phrases: tuple[EffectPhrase, ...]
    ) -> Path:
        """Build and write the unknown-diagnostics JSON artifact.

        Args:
            output_root: Root output directory.
            phrases: All effect phrases used to build the diagnostics.

        Returns:
            Path to the written ``unknown_diagnostics.json`` file.
        """
        data = self.build_unknown_diagnostics(phrases)
        return self._writer.write_unknown_diagnostics(output_root, data)

    # ------------------------------------------------------------------
    # Pass-through to inner writer (for pipeline delegation)
    # ------------------------------------------------------------------

    @property
    def inner(self) -> FeatureEngineeringWriter:
        """The underlying ``FeatureEngineeringWriter`` instance."""
        return self._writer


__all__ = ["ArtifactWriter"]
