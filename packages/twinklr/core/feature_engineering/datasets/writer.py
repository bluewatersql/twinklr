"""Artifact writers for feature engineering outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    AudioDiscoveryResult,
    EffectPhrase,
    FeatureBundle,
)
from twinklr.core.feature_engineering.models.adapters import SequencerAdapterBundle
from twinklr.core.feature_engineering.models.ann_retrieval import (
    AnnRetrievalEvalReport,
    AnnRetrievalIndex,
)
from twinklr.core.feature_engineering.models.clustering import TemplateClusterCatalog
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.learned_taxonomy import (
    LearnedTaxonomyEvalReport,
    LearnedTaxonomyModel,
)
from twinklr.core.feature_engineering.models.motifs import MotifCatalog
from twinklr.core.feature_engineering.models.quality import QualityReport
from twinklr.core.feature_engineering.models.retrieval import TemplateRetrievalIndex
from twinklr.core.feature_engineering.models.stacks import EffectStack, EffectStackCatalog
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.models.template_diagnostics import (
    TemplateDiagnosticsReport,
)
from twinklr.core.feature_engineering.models.templates import TemplateCatalog
from twinklr.core.feature_engineering.models.temporal_motifs import TemporalMotifCatalog
from twinklr.core.feature_engineering.models.transitions import TransitionGraph
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe

if TYPE_CHECKING:
    import pyarrow as pa
    import pyarrow.parquet as pq

try:
    import pyarrow as pa  # type: ignore[assignment]
    import pyarrow.parquet as pq  # type: ignore[assignment]

    _HAS_PYARROW = True
except ImportError:
    _HAS_PYARROW = False


class FeatureEngineeringWriter:
    """Write V1 feature-engineering JSON artifacts."""

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_dataset(
        self, output_dir: Path, filename_stem: str, rows: list[dict[str, Any]]
    ) -> Path:
        """Write dataset rows as parquet (preferred) or JSONL (fallback).

        Args:
            output_dir: Directory in which to create the output file.
            filename_stem: Base filename without extension.
            rows: List of JSON-serialisable dicts to write.

        Returns:
            Path to the written file (.parquet or .jsonl).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        if _HAS_PYARROW:
            output_path = output_dir / f"{filename_stem}.parquet"
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, output_path)
        else:
            output_path = output_dir / f"{filename_stem}.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return output_path

    def write_audio_discovery_json(self, output_dir: Path, result: AudioDiscoveryResult) -> None:
        """Write audio discovery result as JSON.

        Args:
            output_dir: Directory for the output file.
            result: Audio discovery result to serialise.
        """
        self._write_json(output_dir / "audio_discovery.json", result.model_dump(mode="json"))

    def write_feature_bundle_json(self, output_dir: Path, bundle: FeatureBundle) -> None:
        """Write feature bundle as JSON.

        Args:
            output_dir: Directory for the output file.
            bundle: Feature bundle to serialise.
        """
        self._write_json(output_dir / "feature_bundle.json", bundle.model_dump(mode="json"))

    def write_aligned_events(
        self, output_dir: Path, aligned_events: tuple[AlignedEffectEvent, ...]
    ) -> Path:
        """Write aligned events as parquet when available, else JSONL.

        Args:
            output_dir: Directory for the output file.
            aligned_events: Aligned effect events to write.

        Returns:
            Path to the written file.
        """
        rows = [event.model_dump(mode="json") for event in aligned_events]
        return self._write_dataset(output_dir, "aligned_events", rows)

    def write_effect_phrases(self, output_dir: Path, phrases: tuple[EffectPhrase, ...]) -> Path:
        """Write effect phrases as parquet when available, else JSONL.

        Args:
            output_dir: Directory for the output file.
            phrases: Effect phrases to write.

        Returns:
            Path to the written file.
        """
        rows = [phrase.model_dump(mode="json") for phrase in phrases]
        return self._write_dataset(output_dir, "effect_phrases", rows)

    def write_phrase_taxonomy(
        self, output_dir: Path, rows: tuple[PhraseTaxonomyRecord, ...]
    ) -> Path:
        """Write phrase taxonomy rows as parquet when available, else JSONL.

        Args:
            output_dir: Directory for the output file.
            rows: Phrase taxonomy records to write.

        Returns:
            Path to the written file.
        """
        payload = [row.model_dump(mode="json") for row in rows]
        return self._write_dataset(output_dir, "phrase_taxonomy", payload)

    def write_target_roles(self, output_dir: Path, rows: tuple[TargetRoleAssignment, ...]) -> Path:
        """Write target-role rows as parquet when available, else JSONL.

        Args:
            output_dir: Directory for the output file.
            rows: Target role assignment records to write.

        Returns:
            Path to the written file.
        """
        payload = [row.model_dump(mode="json") for row in rows]
        return self._write_dataset(output_dir, "target_roles", payload)

    def write_content_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        """Write content template catalog as JSON.

        Args:
            output_root: Directory for the output file.
            catalog: Template catalog to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "content_templates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_orchestration_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        """Write orchestration template catalog as JSON.

        Args:
            output_root: Directory for the output file.
            catalog: Template catalog to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "orchestration_templates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_transition_graph(self, output_root: Path, graph: TransitionGraph) -> Path:
        """Write transition graph as JSON.

        Args:
            output_root: Directory for the output file.
            graph: Transition graph to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "transition_graph.json"
        self._write_json(output_path, graph.model_dump(mode="json"))
        return output_path

    def write_layering_features(
        self, output_root: Path, rows: tuple[LayeringFeatureRow, ...]
    ) -> Path:
        """Write layering feature rows as parquet when available, else JSONL.

        Args:
            output_root: Directory for the output file.
            rows: Layering feature rows to write.

        Returns:
            Path to the written file.
        """
        payload = [row.model_dump(mode="json") for row in rows]
        return self._write_dataset(output_root, "layering_features", payload)

    def write_color_narrative(self, output_root: Path, rows: tuple[ColorNarrativeRow, ...]) -> Path:
        """Write color narrative rows as parquet when available, else JSONL.

        Args:
            output_root: Directory for the output file.
            rows: Color narrative rows to write.

        Returns:
            Path to the written file.
        """
        payload = [row.model_dump(mode="json") for row in rows]
        return self._write_dataset(output_root, "color_narrative", payload)

    def write_quality_report(self, output_root: Path, report: QualityReport) -> Path:
        """Write quality report as JSON.

        Args:
            output_root: Directory for the output file.
            report: Quality report to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "quality_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_unknown_diagnostics(self, output_root: Path, payload: dict[str, object]) -> Path:
        """Write unknown diagnostics payload as JSON.

        Args:
            output_root: Directory for the output file.
            payload: Diagnostics payload to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "unknown_diagnostics.json"
        self._write_json(output_path, payload)
        return output_path

    def write_template_retrieval_index(
        self, output_root: Path, index: TemplateRetrievalIndex
    ) -> Path:
        """Write template retrieval index as JSON.

        Args:
            output_root: Directory for the output file.
            index: Template retrieval index to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "template_retrieval_index.json"
        self._write_json(output_path, index.model_dump(mode="json"))
        return output_path

    def write_template_diagnostics(
        self, output_root: Path, diagnostics: TemplateDiagnosticsReport
    ) -> Path:
        """Write template diagnostics report as JSON.

        Args:
            output_root: Directory for the output file.
            diagnostics: Template diagnostics report to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "template_diagnostics.json"
        self._write_json(output_path, diagnostics.model_dump(mode="json"))
        return output_path

    def write_feature_store_manifest(self, output_root: Path, manifest: dict[str, str]) -> Path:
        """Write feature store manifest as JSON.

        Args:
            output_root: Directory for the output file.
            manifest: Manifest mapping to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "feature_store_manifest.json"
        self._write_json(output_path, manifest)
        return output_path

    def write_motif_catalog(self, output_root: Path, catalog: MotifCatalog) -> Path:
        """Write motif catalog as JSON.

        Args:
            output_root: Directory for the output file.
            catalog: Motif catalog to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "motif_catalog.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_temporal_motif_catalog(
        self, output_root: Path, catalog: TemporalMotifCatalog
    ) -> None:
        """Write temporal motif catalog as JSON.

        Args:
            output_root: Directory for the output file.
            catalog: Temporal motif catalog to serialise.
        """
        self._write_json(
            output_root / "temporal_motif_catalog.json",
            catalog.model_dump(mode="json"),
        )

    def write_cluster_catalog(self, output_root: Path, catalog: TemplateClusterCatalog) -> Path:
        """Write cluster candidate catalog as JSON.

        Args:
            output_root: Directory for the output file.
            catalog: Template cluster catalog to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "cluster_candidates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_cluster_review_queue(
        self, output_root: Path, catalog: TemplateClusterCatalog
    ) -> Path:
        """Write cluster review queue as JSONL.

        Args:
            output_root: Directory for the output file.
            catalog: Template cluster catalog whose review_queue to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "cluster_review_queue.jsonl"
        output_root.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for row in catalog.review_queue:
                handle.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")
        return output_path

    def write_learned_taxonomy_model(self, output_root: Path, model: LearnedTaxonomyModel) -> Path:
        """Write learned taxonomy model bundle as JSON.

        Args:
            output_root: Directory for the output file.
            model: Learned taxonomy model to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "taxonomy_model_bundle.json"
        self._write_json(output_path, model.model_dump(mode="json"))
        return output_path

    def write_learned_taxonomy_eval(
        self, output_root: Path, report: LearnedTaxonomyEvalReport
    ) -> Path:
        """Write learned taxonomy evaluation report as JSON.

        Args:
            output_root: Directory for the output file.
            report: Evaluation report to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "taxonomy_eval_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_ann_retrieval_index(self, output_root: Path, index: AnnRetrievalIndex) -> Path:
        """Write ANN retrieval index as JSON.

        Args:
            output_root: Directory for the output file.
            index: ANN retrieval index to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "retrieval_ann_index.json"
        self._write_json(output_path, index.model_dump(mode="json"))
        return output_path

    def write_ann_retrieval_eval(self, output_root: Path, report: AnnRetrievalEvalReport) -> Path:
        """Write ANN retrieval evaluation report as JSON.

        Args:
            output_root: Directory for the output file.
            report: Evaluation report to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "retrieval_eval_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_stack_catalog(self, output_root: Path, stacks: tuple[EffectStack, ...]) -> Path:
        """Write detected stack catalog as JSON.

        Args:
            output_root: Directory for the output file.
            stacks: Effect stacks to include in the catalog.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "stack_catalog.json"
        single_count = sum(1 for s in stacks if s.layer_count == 1)
        multi_count = sum(1 for s in stacks if s.layer_count > 1)
        max_layers = max((s.layer_count for s in stacks), default=0)
        catalog = EffectStackCatalog(
            total_phrase_count=sum(s.layer_count for s in stacks),
            total_stack_count=len(stacks),
            single_layer_count=single_count,
            multi_layer_count=multi_count,
            max_layer_count=max_layers,
            stacks=stacks,
        )
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_recipe_catalog(self, output_root: Path, recipes: list[EffectRecipe]) -> Path:
        """Write promoted recipe catalog as JSON.

        Args:
            output_root: Directory for the output file.
            recipes: Effect recipes to include in the catalog.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "recipe_catalog.json"
        payload = [r.model_dump(mode="json") for r in recipes]
        self._write_json(output_path, {"schema_version": "1", "recipes": payload})
        return output_path

    def write_planner_adapter_payloads(
        self, output_root: Path, payloads: tuple[SequencerAdapterBundle, ...]
    ) -> Path:
        """Write planner adapter payloads as JSONL.

        Args:
            output_root: Root directory; output is written into a subdirectory.
            payloads: Sequencer adapter bundles to write.

        Returns:
            Path to the written file.
        """
        payload_dir = output_root / "planner_adapter_payloads"
        payload_dir.mkdir(parents=True, exist_ok=True)
        output_path = payload_dir / "sequencer_adapter_payloads.jsonl"
        with output_path.open("w", encoding="utf-8") as handle:
            for payload in payloads:
                handle.write(json.dumps(payload.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")
        return output_path

    def write_planner_adapter_acceptance(
        self, output_root: Path, payload: dict[str, object]
    ) -> Path:
        """Write planner adapter acceptance report as JSON.

        Args:
            output_root: Directory for the output file.
            payload: Acceptance payload to serialise.

        Returns:
            Path to the written file.
        """
        output_path = output_root / "planner_adapter_acceptance.json"
        self._write_json(output_path, payload)
        return output_path
