"""V1.0 feature-engineering orchestration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.adapters import GroupAdapterBuilder, MacroAdapterBuilder
from twinklr.core.feature_engineering.alignment import TemporalAlignmentEngine
from twinklr.core.feature_engineering.ann_retrieval import (
    AnnRetrievalOptions,
    AnnTemplateRetrievalIndexer,
)
from twinklr.core.feature_engineering.audio_discovery import (
    AudioAnalyzerLike,
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.clustering import (
    TemplateClusterer,
    TemplateClustererOptions,
)
from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.color_narrative import ColorNarrativeExtractor
from twinklr.core.feature_engineering.propensity import PropensityMiner
from twinklr.core.feature_engineering.style import StyleFingerprintExtractor
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
    SongColorArc,
    EffectPhrase,
    FeatureBundle,
    LayeringFeatureRow,
    PhraseTaxonomyRecord,
    PlannerChangeMode,
    QualityReport,
    SequencerAdapterBundle,
    StyleFingerprint,
    TargetRoleAssignment,
    TemplateCatalog,
    TemplateRetrievalIndex,
    TransitionGraph,
)
from twinklr.core.feature_engineering.motifs import MotifMiner, MotifMinerOptions
from twinklr.core.feature_engineering.phrase_encoder import PhraseEncoder
from twinklr.core.feature_engineering.retrieval import TemplateRetrievalRanker
from twinklr.core.feature_engineering.taxonomy import (
    LearnedTaxonomyTrainer,
    LearnedTaxonomyTrainerOptions,
    TargetRoleAssigner,
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)
from twinklr.core.feature_engineering.template_diagnostics import (
    TemplateDiagnosticsBuilder,
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
    enable_template_retrieval_ranking: bool = True
    enable_template_diagnostics: bool = True
    enable_v2_motif_mining: bool = True
    enable_v2_clustering: bool = True
    enable_v2_learned_taxonomy: bool = True
    enable_v2_ann_retrieval: bool = True
    enable_v2_adapter_contracts: bool = True
    v2_motif_min_support_count: int = 2
    v2_motif_min_distinct_pack_count: int = 1
    v2_motif_min_distinct_sequence_count: int = 2
    v2_cluster_similarity_threshold: float = 0.92
    v2_cluster_min_size: int = 2
    v2_taxonomy_min_recall_for_promotion: float = 0.55
    v2_taxonomy_min_f1_for_promotion: float = 0.60
    v2_retrieval_min_recall_at_5: float = 0.80
    v2_retrieval_max_avg_latency_ms: float = 10.0
    enable_layering_features: bool = True
    enable_color_narrative: bool = True
    enable_color_arc: bool = True
    enable_propensity: bool = True
    enable_style_fingerprint: bool = True
    enable_quality_gates: bool = True
    taxonomy_rules_path: Path | None = None
    template_min_instance_count: int = 2
    template_min_distinct_pack_count: int = 1
    quality_min_template_coverage: float = 0.80
    quality_min_taxonomy_confidence_mean: float = 0.30
    quality_max_unknown_effect_family_ratio: float = 0.02
    quality_max_unknown_motion_ratio: float = 0.02
    quality_max_single_unknown_effect_type_ratio: float = 0.01


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
        self._template_retrieval_ranker = TemplateRetrievalRanker()
        self._template_diagnostics = TemplateDiagnosticsBuilder()
        self._motif_miner = MotifMiner(
            MotifMinerOptions(
                min_support_count=self._options.v2_motif_min_support_count,
                min_distinct_pack_count=self._options.v2_motif_min_distinct_pack_count,
                min_distinct_sequence_count=self._options.v2_motif_min_distinct_sequence_count,
            )
        )
        self._template_clusterer = TemplateClusterer(
            TemplateClustererOptions(
                similarity_threshold=self._options.v2_cluster_similarity_threshold,
                min_cluster_size=self._options.v2_cluster_min_size,
            )
        )
        self._learned_taxonomy_trainer = LearnedTaxonomyTrainer(
            LearnedTaxonomyTrainerOptions(
                min_recall_for_promotion=self._options.v2_taxonomy_min_recall_for_promotion,
                min_f1_for_promotion=self._options.v2_taxonomy_min_f1_for_promotion,
            )
        )
        self._ann_retrieval_indexer = AnnTemplateRetrievalIndexer(
            AnnRetrievalOptions(
                min_same_effect_family_recall_at_5=self._options.v2_retrieval_min_recall_at_5,
                max_avg_query_latency_ms=self._options.v2_retrieval_max_avg_latency_ms,
            )
        )
        self._macro_adapter_builder = MacroAdapterBuilder()
        self._group_adapter_builder = GroupAdapterBuilder()
        self._layering = LayeringFeatureExtractor()
        self._color_narrative = ColorNarrativeExtractor()
        self._color_arc = ColorArcExtractor()
        self._propensity_miner = PropensityMiner()
        self._style_fingerprint = StyleFingerprintExtractor()
        self._quality_gates = FeatureQualityGates(
            QualityGateOptions(
                min_template_coverage=self._options.quality_min_template_coverage,
                min_taxonomy_confidence_mean=self._options.quality_min_taxonomy_confidence_mean,
                max_unknown_effect_family_ratio=self._options.quality_max_unknown_effect_family_ratio,
                max_unknown_motion_ratio=self._options.quality_max_unknown_motion_ratio,
                max_single_unknown_effect_type_ratio=self._options.quality_max_single_unknown_effect_type_ratio,
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
            bundles=tuple(bundles),
            phrases=tuple(corpus_phrases),
            taxonomy_rows=tuple(corpus_taxonomy),
            target_roles=tuple(corpus_target_roles),
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

    def _write_color_arc(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
    ) -> Path | None:
        if not self._options.enable_color_arc or not color_rows:
            return None
        arc = self._color_arc.extract(phrases=phrases, color_narrative=color_rows)
        output_path = output_root / "color_arc.json"
        self._writer._write_json(output_path, arc.model_dump(mode="json"))
        return output_path

    def _write_propensity(
        self,
        *,
        output_root: Path,
        phrases: tuple[EffectPhrase, ...],
    ) -> Path | None:
        if not self._options.enable_propensity or not phrases:
            return None
        index = self._propensity_miner.mine(phrases=phrases)
        output_path = output_root / "propensity_index.json"
        self._writer._write_json(output_path, index.model_dump(mode="json"))
        return output_path

    def _write_style_fingerprint(
        self,
        *,
        output_root: Path,
        creator_id: str,
        phrases: tuple[EffectPhrase, ...],
        layering_rows: tuple[LayeringFeatureRow, ...],
        color_rows: tuple[ColorNarrativeRow, ...],
        transition_graph: TransitionGraph | None,
    ) -> Path | None:
        if not self._options.enable_style_fingerprint or not phrases:
            return None
        fingerprint = self._style_fingerprint.extract(
            creator_id=creator_id,
            phrases=phrases,
            layering_rows=layering_rows,
            color_rows=color_rows,
            transition_graph=transition_graph,
        )
        output_path = output_root / "style_fingerprint.json"
        self._writer._write_json(output_path, fingerprint.model_dump(mode="json"))
        return output_path

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
        bundles: tuple[FeatureBundle, ...],
        phrases: tuple[EffectPhrase, ...],
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...],
        target_roles: tuple[TargetRoleAssignment, ...],
        template_catalogs: tuple[TemplateCatalog, TemplateCatalog] | None,
    ) -> None:
        manifest: dict[str, str] = {}
        retrieval_index: TemplateRetrievalIndex | None = None

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

        color_arc_path = self._write_color_arc(
            output_root=output_root, phrases=phrases, color_rows=color_rows
        )
        if color_arc_path is not None:
            manifest["color_arc"] = str(color_arc_path)

        propensity_path = self._write_propensity(output_root=output_root, phrases=phrases)
        if propensity_path is not None:
            manifest["propensity_index"] = str(propensity_path)

        # Derive a creator_id from the first bundle's package_id for corpus-level fingerprint.
        creator_id = bundles[0].package_id if bundles else "unknown"
        style_path = self._write_style_fingerprint(
            output_root=output_root,
            creator_id=creator_id,
            phrases=phrases,
            layering_rows=layering_rows,
            color_rows=color_rows,
            transition_graph=transition_graph,
        )
        if style_path is not None:
            manifest["style_fingerprint"] = str(style_path)

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

        if phrases:
            path = self._writer.write_unknown_diagnostics(
                output_root,
                self._build_unknown_diagnostics(phrases),
            )
            manifest["unknown_diagnostics"] = str(path)

        if template_catalogs is not None:
            manifest["content_templates"] = str(output_root / "content_templates.json")
            manifest["orchestration_templates"] = str(output_root / "orchestration_templates.json")
            if self._options.enable_template_retrieval_ranking:
                retrieval_index = self._template_retrieval_ranker.build_index(
                    content_catalog=template_catalogs[0],
                    orchestration_catalog=template_catalogs[1],
                    transition_graph=transition_graph,
                )
                path = self._writer.write_template_retrieval_index(output_root, retrieval_index)
                manifest["template_retrieval_index"] = str(path)
            if self._options.enable_template_diagnostics:
                diagnostics = self._template_diagnostics.build(
                    content_catalog=template_catalogs[0],
                    orchestration_catalog=template_catalogs[1],
                    taxonomy_rows=taxonomy_rows,
                )
                path = self._writer.write_template_diagnostics(output_root, diagnostics)
                manifest["template_diagnostics"] = str(path)
            if self._options.enable_v2_motif_mining:
                motif_catalog = self._motif_miner.mine(
                    phrases=phrases,
                    taxonomy_rows=taxonomy_rows,
                    content_catalog=template_catalogs[0],
                    orchestration_catalog=template_catalogs[1],
                )
                path = self._writer.write_motif_catalog(output_root, motif_catalog)
                manifest["motif_catalog"] = str(path)
            if self._options.enable_v2_clustering:
                cluster_catalog = self._template_clusterer.build_clusters(
                    content_catalog=template_catalogs[0],
                    orchestration_catalog=template_catalogs[1],
                    retrieval_index=retrieval_index,
                )
                path = self._writer.write_cluster_catalog(output_root, cluster_catalog)
                manifest["cluster_candidates"] = str(path)
                queue_path = self._writer.write_cluster_review_queue(output_root, cluster_catalog)
                manifest["cluster_review_queue"] = str(queue_path)
        if self._options.enable_v2_learned_taxonomy and phrases and taxonomy_rows:
            model, report = self._learned_taxonomy_trainer.train(
                phrases=phrases,
                taxonomy_rows=taxonomy_rows,
            )
            path = self._writer.write_learned_taxonomy_model(output_root, model)
            manifest["taxonomy_model_bundle"] = str(path)
            eval_path = self._writer.write_learned_taxonomy_eval(output_root, report)
            manifest["taxonomy_eval_report"] = str(eval_path)
        if self._options.enable_v2_ann_retrieval and retrieval_index is not None:
            ann_index = self._ann_retrieval_indexer.build_index(retrieval_index)
            path = self._writer.write_ann_retrieval_index(output_root, ann_index)
            manifest["retrieval_ann_index"] = str(path)
            eval_report = self._ann_retrieval_indexer.evaluate(
                index=ann_index,
                retrieval_index=retrieval_index,
            )
            eval_path = self._writer.write_ann_retrieval_eval(output_root, eval_report)
            manifest["retrieval_eval_report"] = str(eval_path)
        if self._options.enable_v2_adapter_contracts:
            payloads, acceptance = self._build_adapter_payloads(
                bundles=bundles,
                retrieval_index=retrieval_index,
                transition_graph=transition_graph,
                target_roles=target_roles,
            )
            payload_path = self._writer.write_planner_adapter_payloads(output_root, payloads)
            acceptance_path = self._writer.write_planner_adapter_acceptance(output_root, acceptance)
            manifest["planner_adapter_payloads"] = str(payload_path)
            manifest["planner_adapter_acceptance"] = str(acceptance_path)
        if quality_report is not None:
            manifest["quality_passed"] = str(quality_report.passed)

        self._writer.write_feature_store_manifest(output_root, manifest)

    def _build_adapter_payloads(
        self,
        *,
        bundles: tuple[FeatureBundle, ...],
        retrieval_index: TemplateRetrievalIndex | None,
        transition_graph: TransitionGraph | None,
        target_roles: tuple[TargetRoleAssignment, ...],
    ) -> tuple[tuple[SequencerAdapterBundle, ...], dict[str, object]]:
        recommendations = retrieval_index.recommendations if retrieval_index is not None else ()
        roles_by_sequence: dict[str, list[TargetRoleAssignment]] = {}
        for row in target_roles:
            roles_by_sequence.setdefault(row.sequence_file_id, []).append(row)

        payloads: list[SequencerAdapterBundle] = []
        contract_only_violations: list[str] = []
        for bundle in sorted(
            bundles,
            key=lambda item: (item.package_id, item.sequence_file_id),
        ):
            assignments = tuple(roles_by_sequence.get(bundle.sequence_file_id, []))
            macro = self._macro_adapter_builder.build(
                bundle=bundle,
                recommendations=recommendations,
                transition_graph=transition_graph,
                role_assignments=assignments,
            )
            group = self._group_adapter_builder.build(
                bundle=bundle,
                recommendations=recommendations,
                transition_graph=transition_graph,
                role_assignments=assignments,
            )
            if macro.planner_change_mode is not PlannerChangeMode.CONTRACT_ONLY:
                contract_only_violations.append(
                    f"{bundle.package_id}/{bundle.sequence_file_id}:macro"
                )
            if group.planner_change_mode is not PlannerChangeMode.CONTRACT_ONLY:
                contract_only_violations.append(
                    f"{bundle.package_id}/{bundle.sequence_file_id}:group"
                )
            payloads.append(
                SequencerAdapterBundle(
                    schema_version=macro.schema_version,
                    adapter_version=macro.adapter_version,
                    macro=macro,
                    group=group,
                )
            )

        acceptance = {
            "schema_version": "v2.4.0",
            "adapter_version": "sequencer_adapter_v1",
            "sequence_count": len(payloads),
            "macro_payload_count": len(payloads),
            "group_payload_count": len(payloads),
            "planner_change_mode_enforced": len(contract_only_violations) == 0,
            "contract_only_violations": contract_only_violations,
            "planner_runtime_changes_applied": False,
        }
        return tuple(payloads), acceptance

    @staticmethod
    def _normalize_effect_key(effect_type: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", effect_type.strip().lower())

    def _build_unknown_diagnostics(self, phrases: tuple[EffectPhrase, ...]) -> dict[str, object]:
        total = len(phrases)
        unknown_effect_rows = [row for row in phrases if row.effect_family == "unknown"]
        unknown_motion_rows = [row for row in phrases if row.motion_class.value == "unknown"]

        unknown_effect_ratio = len(unknown_effect_rows) / total if total > 0 else 0.0
        unknown_motion_ratio = len(unknown_motion_rows) / total if total > 0 else 0.0

        by_effect_type: dict[str, list[EffectPhrase]] = {}
        for row in unknown_effect_rows:
            by_effect_type.setdefault(row.effect_type, []).append(row)

        top_unknown_effect_types: list[dict[str, object]] = []
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

        alias_candidate_groups: list[dict[str, object]] = []
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

        unknown_motion_by_effect_family: list[dict[str, object]] = []
        by_motion_family: dict[str, list[EffectPhrase]] = {}
        for row in unknown_motion_rows:
            by_motion_family.setdefault(row.effect_family, []).append(row)
        for family, rows in sorted(by_motion_family.items(), key=lambda item: (-len(item[1]), item[0]))[:25]:
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
