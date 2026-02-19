"""V1.0 feature-engineering orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.alignment import TemporalAlignmentEngine
from twinklr.core.feature_engineering.audio_discovery import (
    AudioAnalyzerLike,
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.color_narrative import ColorNarrativeExtractor
from twinklr.core.feature_engineering.constants import FEATURE_BUNDLE_SCHEMA_VERSION
from twinklr.core.feature_engineering.datasets.quality import (
    FeatureQualityGates,
    QualityGateOptions,
)
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.layering import LayeringFeatureExtractor
from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    ColorNarrativeRow,
    EffectPhrase,
    FeatureBundle,
    LayeringFeatureRow,
    PhraseTaxonomyRecord,
    QualityReport,
    TargetRoleAssignment,
    TemplateCatalog,
    TransitionGraph,
)
from twinklr.core.feature_engineering.phrase_encoder import PhraseEncoder
from twinklr.core.feature_engineering.taxonomy import (
    TargetRoleAssigner,
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)
from twinklr.core.feature_engineering.templates import TemplateMiner, TemplateMinerOptions
from twinklr.core.feature_engineering.transitions import TransitionModeler


@dataclass(frozen=True)
class FeatureEngineeringPipelineOptions:
    """V1.0 pipeline runtime options."""

    audio_required: bool = False
    confidence_threshold: float = 0.85
    extracted_search_roots: tuple[Path, ...] = (Path("data/vendor_packages"),)
    music_repo_roots: tuple[Path, ...] = (Path("data/music"),)
    analyzer_version: str = "AudioAnalyzer"
    force_reprocess_audio: bool = False
    enable_alignment: bool = True
    enable_phrase_encoding: bool = True
    enable_taxonomy: bool = True
    enable_target_roles: bool = True
    enable_template_mining: bool = True
    enable_transition_modeling: bool = True
    enable_layering_features: bool = True
    enable_color_narrative: bool = True
    enable_quality_gates: bool = True
    taxonomy_rules_path: Path | None = None
    template_min_instance_count: int = 2
    template_min_distinct_pack_count: int = 1
    quality_min_template_coverage: float = 0.80
    quality_min_taxonomy_confidence_mean: float = 0.30
    quality_max_unknown_effect_family_ratio: float = 0.85
    quality_max_unknown_motion_ratio: float = 0.85


@dataclass(frozen=True)
class _ProfileOutputs:
    bundle: FeatureBundle
    phrases: tuple[EffectPhrase, ...]
    taxonomy_rows: tuple[PhraseTaxonomyRecord, ...]
    target_roles: tuple[TargetRoleAssignment, ...]


class FeatureEngineeringPipeline:
    """Execute V1.0 contracts and audio discovery/analysis."""

    def __init__(
        self,
        *,
        options: FeatureEngineeringPipelineOptions | None = None,
        analyzer: AudioAnalyzerLike | None = None,
        writer: FeatureEngineeringWriter | None = None,
    ) -> None:
        self._options = options or FeatureEngineeringPipelineOptions()
        self._discovery = AudioDiscoveryService(
            AudioDiscoveryOptions(
                confidence_threshold=self._options.confidence_threshold,
                extracted_search_roots=self._options.extracted_search_roots,
                music_repo_roots=self._options.music_repo_roots,
            )
        )
        self._analyzer = analyzer
        self._writer = writer or FeatureEngineeringWriter()
        self._alignment = TemporalAlignmentEngine()
        self._phrase_encoder = PhraseEncoder()
        self._taxonomy_classifier = TaxonomyClassifier(
            TaxonomyClassifierOptions(rules_path=self._options.taxonomy_rules_path)
        )
        self._target_roles = TargetRoleAssigner()
        self._template_miner = TemplateMiner(
            TemplateMinerOptions(
                min_instance_count=self._options.template_min_instance_count,
                min_distinct_pack_count=self._options.template_min_distinct_pack_count,
            )
        )
        self._transition_modeler = TransitionModeler()
        self._layering = LayeringFeatureExtractor()
        self._color_narrative = ColorNarrativeExtractor()
        self._quality_gates = FeatureQualityGates(
            QualityGateOptions(
                min_template_coverage=self._options.quality_min_template_coverage,
                min_taxonomy_confidence_mean=self._options.quality_min_taxonomy_confidence_mean,
                max_unknown_effect_family_ratio=self._options.quality_max_unknown_effect_family_ratio,
                max_unknown_motion_ratio=self._options.quality_max_unknown_motion_ratio,
            )
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object at {path}")
        return data

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object line in {path}")
            rows.append(value)
        return rows

    def run_profile(self, profile_dir: Path, output_dir: Path) -> FeatureBundle:
        outputs = self._run_profile_internal(profile_dir, output_dir)
        return outputs.bundle

    def _run_profile_internal(self, profile_dir: Path, output_dir: Path) -> _ProfileOutputs:
        metadata = self._read_json(profile_dir / "sequence_metadata.json")
        lineage = self._read_json(profile_dir / "lineage_index.json")

        discovery = self._discovery.discover_audio(
            AudioDiscoveryContext(
                profile_dir=profile_dir,
                media_file=str(metadata.get("media_file") or ""),
                song=str(metadata.get("song") or ""),
                sequence_filename=str(lineage.get("sequence_file", {}).get("filename") or ""),
            )
        )
        discovery = self._discovery.run_audio_analysis(
            discovery,
            analyzer=self._analyzer,
            analyzer_version=self._options.analyzer_version,
            force_reprocess=self._options.force_reprocess_audio,
            audio_required=self._options.audio_required,
        )

        bundle = FeatureBundle(
            schema_version=FEATURE_BUNDLE_SCHEMA_VERSION,
            source_profile_path=str(profile_dir),
            package_id=str(metadata.get("package_id")),
            sequence_file_id=str(metadata.get("sequence_file_id")),
            sequence_sha256=str(metadata.get("sequence_sha256")),
            song=str(metadata.get("song") or ""),
            artist=str(metadata.get("artist") or ""),
            audio=discovery,
        )

        self._writer.write_audio_discovery_json(output_dir, discovery)
        self._writer.write_feature_bundle_json(output_dir, bundle)
        aligned_events, enriched_events = self._write_aligned_events(
            profile_dir=profile_dir,
            output_dir=output_dir,
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            audio_path=discovery.audio_path,
            analyzer_error=discovery.analyzer_error,
        )
        phrases = self._write_effect_phrases(
            output_dir=output_dir,
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            aligned_events=aligned_events,
            enriched_events=enriched_events,
        )
        taxonomy_rows = self._write_phrase_taxonomy(
            output_dir=output_dir,
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            phrases=phrases,
        )
        target_roles = self._write_target_roles(
            output_dir=output_dir,
            package_id=bundle.package_id,
            sequence_file_id=bundle.sequence_file_id,
            enriched_events=enriched_events,
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
        )
        return _ProfileOutputs(
            bundle=bundle,
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
        )

    def run_corpus(self, corpus_dir: Path, output_root: Path) -> list[FeatureBundle]:
        rows = self._read_jsonl(corpus_dir / "sequence_index.jsonl")
        bundles: list[FeatureBundle] = []
        corpus_phrases: list[EffectPhrase] = []
        corpus_taxonomy: list[PhraseTaxonomyRecord] = []
        corpus_target_roles: list[TargetRoleAssignment] = []
        for row in rows:
            profile_dir = Path(str(row.get("profile_path")))
            package_id = str(row.get("package_id"))
            sequence_file_id = str(row.get("sequence_file_id"))
            output_dir = output_root / package_id / sequence_file_id
            outputs = self._run_profile_internal(profile_dir, output_dir)
            bundles.append(outputs.bundle)
            corpus_phrases.extend(outputs.phrases)
            corpus_taxonomy.extend(outputs.taxonomy_rows)
            corpus_target_roles.extend(outputs.target_roles)
        template_catalogs = self._write_template_catalogs(
            output_root=output_root,
            phrases=tuple(corpus_phrases),
            taxonomy_rows=tuple(corpus_taxonomy),
            target_roles=tuple(corpus_target_roles),
        )
        self._write_v1_tail_artifacts(
            output_root=output_root,
            phrases=tuple(corpus_phrases),
            taxonomy_rows=tuple(corpus_taxonomy),
            template_catalogs=template_catalogs,
        )
        return bundles

    def _write_aligned_events(
        self,
        *,
        profile_dir: Path,
        output_dir: Path,
        package_id: str,
        sequence_file_id: str,
        audio_path: str | None,
        analyzer_error: str | None,
    ) -> tuple[tuple[AlignedEffectEvent, ...], list[dict[str, Any]]]:
        if not self._options.enable_alignment:
            return (), []

        enriched_events_path = profile_dir / "enriched_effect_events.json"
        if not enriched_events_path.exists():
            return (), []
        enriched_events = json.loads(enriched_events_path.read_text(encoding="utf-8"))
        if not isinstance(enriched_events, list):
            raise ValueError(f"Expected list in {enriched_events_path}")

        aligned_events: tuple[AlignedEffectEvent, ...]
        if audio_path is None or analyzer_error is not None or self._analyzer is None:
            aligned_events = self._alignment.align_events(
                package_id=package_id,
                sequence_file_id=sequence_file_id,
                events=enriched_events,
                audio_features=None,
            )
        else:
            bundle = self._analyzer.analyze_sync(
                audio_path,
                force_reprocess=self._options.force_reprocess_audio,
            )
            features = getattr(bundle, "features", None)
            if not isinstance(features, dict):
                raise ValueError("Audio analyzer returned invalid bundle without features")
            aligned_events = self._alignment.align_events(
                package_id=package_id,
                sequence_file_id=sequence_file_id,
                events=enriched_events,
                audio_features=features,
            )

        self._writer.write_aligned_events(output_dir, aligned_events)
        return aligned_events, enriched_events

    def _write_effect_phrases(
        self,
        *,
        output_dir: Path,
        package_id: str,
        sequence_file_id: str,
        aligned_events: tuple[AlignedEffectEvent, ...],
        enriched_events: list[dict[str, Any]],
    ) -> tuple[EffectPhrase, ...]:
        if not self._options.enable_phrase_encoding or not aligned_events:
            return ()
        phrases = self._phrase_encoder.encode(
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            aligned_events=aligned_events,
            enriched_events=enriched_events,
        )
        self._writer.write_effect_phrases(output_dir, phrases)
        return phrases

    def _write_phrase_taxonomy(
        self,
        *,
        output_dir: Path,
        package_id: str,
        sequence_file_id: str,
        phrases: tuple[EffectPhrase, ...],
    ) -> tuple[PhraseTaxonomyRecord, ...]:
        if not self._options.enable_taxonomy or not phrases:
            return ()
        rows = self._taxonomy_classifier.classify(
            phrases=phrases,
            package_id=package_id,
            sequence_file_id=sequence_file_id,
        )
        self._writer.write_phrase_taxonomy(output_dir, rows)
        return rows

    def _write_target_roles(
        self,
        *,
        output_dir: Path,
        package_id: str,
        sequence_file_id: str,
        enriched_events: list[dict[str, Any]],
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
    ) -> tuple[TargetRoleAssignment, ...]:
        if not self._options.enable_target_roles or not enriched_events:
            return ()
        rows = self._target_roles.assign(
            package_id=package_id,
            sequence_file_id=sequence_file_id,
            enriched_events=enriched_events,
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
        )
        self._writer.write_target_roles(output_dir, rows)
        return rows

    def _write_template_catalogs(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        target_roles: tuple[TargetRoleAssignment, ...],
    ) -> tuple[TemplateCatalog, TemplateCatalog] | None:
        if not self._options.enable_template_mining or not phrases:
            return None
        content_catalog, orchestration_catalog = self._template_miner.mine(
            phrases=phrases,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
        )
        self._writer.write_content_templates(output_root, content_catalog)
        self._writer.write_orchestration_templates(output_root, orchestration_catalog)
        return content_catalog, orchestration_catalog

    def _write_v1_tail_artifacts(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        template_catalogs: tuple[TemplateCatalog, TemplateCatalog] | None,
    ) -> None:
        manifest: dict[str, str] = {}

        transition_graph: TransitionGraph | None = None
        if self._options.enable_transition_modeling and template_catalogs is not None:
            transition_graph = self._transition_modeler.build_graph(
                phrases=phrases,
                orchestration_catalog=template_catalogs[1],
            )
            path = self._writer.write_transition_graph(output_root, transition_graph)
            manifest["transition_graph"] = str(path)

        layering_rows: tuple[LayeringFeatureRow, ...] = ()
        if self._options.enable_layering_features and phrases:
            layering_rows = self._layering.extract(phrases)
            path = self._writer.write_layering_features(output_root, layering_rows)
            manifest["layering_features"] = str(path)

        color_rows: tuple[ColorNarrativeRow, ...] = ()
        if self._options.enable_color_narrative and phrases:
            color_rows = self._color_narrative.extract(phrases)
            path = self._writer.write_color_narrative(output_root, color_rows)
            manifest["color_narrative"] = str(path)

        quality_report: QualityReport | None = None
        if (
            self._options.enable_quality_gates
            and transition_graph is not None
            and template_catalogs is not None
        ):
            quality_report = self._quality_gates.evaluate(
                phrases=phrases,
                taxonomy_rows=taxonomy_rows,
                orchestration_catalog=template_catalogs[1],
                transition_graph=transition_graph,
            )
            path = self._writer.write_quality_report(output_root, quality_report)
            manifest["quality_report"] = str(path)

        if template_catalogs is not None:
            manifest["content_templates"] = str(output_root / "content_templates.json")
            manifest["orchestration_templates"] = str(output_root / "orchestration_templates.json")
        if quality_report is not None:
            manifest["quality_passed"] = str(quality_report.passed)

        self._writer.write_feature_store_manifest(output_root, manifest)
