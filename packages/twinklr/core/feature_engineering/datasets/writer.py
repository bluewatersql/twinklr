"""Artifact writers for feature engineering outputs."""

from __future__ import annotations

import json
from pathlib import Path

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
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.models.template_diagnostics import (
    TemplateDiagnosticsReport,
)
from twinklr.core.feature_engineering.models.templates import TemplateCatalog
from twinklr.core.feature_engineering.models.transitions import TransitionGraph
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


class FeatureEngineeringWriter:
    """Write V1 feature-engineering JSON artifacts."""

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_audio_discovery_json(self, output_dir: Path, result: AudioDiscoveryResult) -> None:
        self._write_json(output_dir / "audio_discovery.json", result.model_dump(mode="json"))

    def write_feature_bundle_json(self, output_dir: Path, bundle: FeatureBundle) -> None:
        self._write_json(output_dir / "feature_bundle.json", bundle.model_dump(mode="json"))

    def write_aligned_events(
        self, output_dir: Path, aligned_events: tuple[AlignedEffectEvent, ...]
    ) -> Path:
        """Write aligned events as parquet when available, else JSONL."""
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = [event.model_dump(mode="json") for event in aligned_events]

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_dir / "aligned_events.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_dir / "aligned_events.parquet"
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, output_path)
        return output_path

    def write_effect_phrases(self, output_dir: Path, phrases: tuple[EffectPhrase, ...]) -> Path:
        """Write effect phrases as parquet when available, else JSONL."""
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = [phrase.model_dump(mode="json") for phrase in phrases]
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_dir / "effect_phrases.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_dir / "effect_phrases.parquet"
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, output_path)
        return output_path

    def write_phrase_taxonomy(
        self, output_dir: Path, rows: tuple[PhraseTaxonomyRecord, ...]
    ) -> Path:
        """Write phrase taxonomy rows as parquet when available, else JSONL."""
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = [row.model_dump(mode="json") for row in rows]
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_dir / "phrase_taxonomy.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in payload:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_dir / "phrase_taxonomy.parquet"
        table = pa.Table.from_pylist(payload)
        pq.write_table(table, output_path)
        return output_path

    def write_target_roles(self, output_dir: Path, rows: tuple[TargetRoleAssignment, ...]) -> Path:
        """Write target-role rows as parquet when available, else JSONL."""
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = [row.model_dump(mode="json") for row in rows]
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_dir / "target_roles.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in payload:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_dir / "target_roles.parquet"
        table = pa.Table.from_pylist(payload)
        pq.write_table(table, output_path)
        return output_path

    def write_content_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        output_path = output_root / "content_templates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_orchestration_templates(self, output_root: Path, catalog: TemplateCatalog) -> Path:
        output_path = output_root / "orchestration_templates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_transition_graph(self, output_root: Path, graph: TransitionGraph) -> Path:
        output_path = output_root / "transition_graph.json"
        self._write_json(output_path, graph.model_dump(mode="json"))
        return output_path

    def write_layering_features(
        self, output_root: Path, rows: tuple[LayeringFeatureRow, ...]
    ) -> Path:
        output_root.mkdir(parents=True, exist_ok=True)
        payload = [row.model_dump(mode="json") for row in rows]
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_root / "layering_features.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in payload:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_root / "layering_features.parquet"
        table = pa.Table.from_pylist(payload)
        pq.write_table(table, output_path)
        return output_path

    def write_color_narrative(self, output_root: Path, rows: tuple[ColorNarrativeRow, ...]) -> Path:
        output_root.mkdir(parents=True, exist_ok=True)
        payload = [row.model_dump(mode="json") for row in rows]
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:  # noqa: BLE001
            output_path = output_root / "color_narrative.jsonl"
            with output_path.open("w", encoding="utf-8") as handle:
                for row in payload:
                    handle.write(json.dumps(row, ensure_ascii=False))
                    handle.write("\n")
            return output_path

        output_path = output_root / "color_narrative.parquet"
        table = pa.Table.from_pylist(payload)
        pq.write_table(table, output_path)
        return output_path

    def write_quality_report(self, output_root: Path, report: QualityReport) -> Path:
        output_path = output_root / "quality_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_unknown_diagnostics(self, output_root: Path, payload: dict[str, object]) -> Path:
        output_path = output_root / "unknown_diagnostics.json"
        self._write_json(output_path, payload)
        return output_path

    def write_template_retrieval_index(
        self, output_root: Path, index: TemplateRetrievalIndex
    ) -> Path:
        output_path = output_root / "template_retrieval_index.json"
        self._write_json(output_path, index.model_dump(mode="json"))
        return output_path

    def write_template_diagnostics(
        self, output_root: Path, diagnostics: TemplateDiagnosticsReport
    ) -> Path:
        output_path = output_root / "template_diagnostics.json"
        self._write_json(output_path, diagnostics.model_dump(mode="json"))
        return output_path

    def write_feature_store_manifest(self, output_root: Path, manifest: dict[str, str]) -> Path:
        output_path = output_root / "feature_store_manifest.json"
        self._write_json(output_path, manifest)
        return output_path

    def write_motif_catalog(self, output_root: Path, catalog: MotifCatalog) -> Path:
        output_path = output_root / "motif_catalog.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_cluster_catalog(self, output_root: Path, catalog: TemplateClusterCatalog) -> Path:
        output_path = output_root / "cluster_candidates.json"
        self._write_json(output_path, catalog.model_dump(mode="json"))
        return output_path

    def write_cluster_review_queue(
        self, output_root: Path, catalog: TemplateClusterCatalog
    ) -> Path:
        output_path = output_root / "cluster_review_queue.jsonl"
        output_root.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for row in catalog.review_queue:
                handle.write(json.dumps(row.model_dump(mode="json"), ensure_ascii=False))
                handle.write("\n")
        return output_path

    def write_learned_taxonomy_model(self, output_root: Path, model: LearnedTaxonomyModel) -> Path:
        output_path = output_root / "taxonomy_model_bundle.json"
        self._write_json(output_path, model.model_dump(mode="json"))
        return output_path

    def write_learned_taxonomy_eval(
        self, output_root: Path, report: LearnedTaxonomyEvalReport
    ) -> Path:
        output_path = output_root / "taxonomy_eval_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_ann_retrieval_index(self, output_root: Path, index: AnnRetrievalIndex) -> Path:
        output_path = output_root / "retrieval_ann_index.json"
        self._write_json(output_path, index.model_dump(mode="json"))
        return output_path

    def write_ann_retrieval_eval(self, output_root: Path, report: AnnRetrievalEvalReport) -> Path:
        output_path = output_root / "retrieval_eval_report.json"
        self._write_json(output_path, report.model_dump(mode="json"))
        return output_path

    def write_recipe_catalog(self, output_root: Path, recipes: list[EffectRecipe]) -> Path:
        """Write promoted recipe catalog as JSON."""
        output_path = output_root / "recipe_catalog.json"
        payload = [r.model_dump(mode="json") for r in recipes]
        self._write_json(output_path, {"schema_version": "1", "recipes": payload})
        return output_path

    def write_planner_adapter_payloads(
        self, output_root: Path, payloads: tuple[SequencerAdapterBundle, ...]
    ) -> Path:
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
        output_path = output_root / "planner_adapter_acceptance.json"
        self._write_json(output_path, payload)
        return output_path
