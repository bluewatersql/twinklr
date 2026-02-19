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
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.quality import QualityReport
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.models.templates import TemplateCatalog
from twinklr.core.feature_engineering.models.transitions import TransitionGraph


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

    def write_target_roles(
        self, output_dir: Path, rows: tuple[TargetRoleAssignment, ...]
    ) -> Path:
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

    def write_color_narrative(
        self, output_root: Path, rows: tuple[ColorNarrativeRow, ...]
    ) -> Path:
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

    def write_feature_store_manifest(self, output_root: Path, manifest: dict[str, str]) -> Path:
        output_path = output_root / "feature_store_manifest.json"
        self._write_json(output_path, manifest)
        return output_path
