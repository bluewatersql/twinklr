"""Pipeline configuration dataclass — CQ-01 extraction from pipeline.py.

``FeatureEngineeringPipelineOptions`` is defined here and re-exported from
``pipeline.py`` for backward compatibility. ``PipelineConfig`` is an alias
used within the decomposed implementation classes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from twinklr.core.feature_store.models import FeatureStoreConfig


@dataclass(frozen=True)
class FeatureEngineeringPipelineOptions:
    """V1.0 pipeline runtime options.

    All fields are keyword-only and immutable. Constructed with defaults
    that match the original pipeline behaviour so existing callers require
    no changes.

    Args:
        audio_required: Raise if no audio analyzer is configured.
        confidence_threshold: Minimum confidence for audio discovery.
        extracted_search_roots: Directories to search for extracted audio.
        music_repo_roots: Directories to search for music files.
        analyzer_version: Identifier for the audio-analyzer implementation.
        force_reprocess_audio: Re-run analysis even if cached results exist.
        enable_alignment: Run temporal alignment stage.
        enable_phrase_encoding: Run phrase encoding stage.
        enable_taxonomy: Run taxonomy classification stage.
        enable_target_roles: Run target-role assignment stage.
        enable_template_mining: Run template mining stage.
        enable_transition_modeling: Run transition modelling stage.
        enable_template_retrieval_ranking: Build retrieval ranking index.
        enable_template_diagnostics: Generate template diagnostics report.
        enable_v2_motif_mining: Run V2 motif mining.
        enable_v2_temporal_motif_mining: Run V2 temporal motif mining.
        enable_v2_clustering: Run V2 template clustering.
        enable_v2_learned_taxonomy: Run learned taxonomy training.
        enable_v2_ann_retrieval: Build ANN retrieval index.
        enable_v2_adapter_contracts: Build sequencer adapter payloads.
        v2_motif_min_support_count: Minimum support count for motifs.
        v2_motif_min_distinct_pack_count: Minimum distinct pack count for motifs.
        v2_motif_min_distinct_sequence_count: Minimum distinct sequence count for motifs.
        v2_cluster_similarity_threshold: Similarity threshold for clustering.
        v2_cluster_min_size: Minimum cluster size.
        v2_taxonomy_min_recall_for_promotion: Recall threshold for taxonomy promotion.
        v2_taxonomy_min_f1_for_promotion: F1 threshold for taxonomy promotion.
        v2_retrieval_min_recall_at_5: Minimum recall@5 for retrieval index.
        v2_retrieval_max_avg_latency_ms: Maximum average query latency.
        enable_layering_features: Extract layering features.
        enable_color_narrative: Extract colour-narrative features.
        enable_color_arc: Extract colour-arc features.
        enable_propensity: Mine propensity index.
        enable_style_fingerprint: Extract style fingerprint.
        enable_stack_detection: Run effect-stack detection.
        enable_quality_gates: Evaluate quality gates.
        enable_recipe_promotion: Run recipe promotion pipeline.
        enable_color_discovery: Run corpus color palette discovery.
        enable_effect_metadata: Build per-family effect metadata profiles.
        enable_vocabulary_expansion: Run compound vocabulary expansion.
        color_palette_library_path: Path to pre-existing color palette library.
        recipe_promotion_min_support: Minimum support count for recipe promotion.
        recipe_promotion_min_stability: Minimum stability score for recipes.
        recipe_promotion_adaptive_stability: Use adaptive stability thresholds.
        recipe_promotion_max_per_family: Maximum recipes promoted per effect family.
        recipe_promotion_param_profiles: Named parameter profiles for promotion.
        taxonomy_rules_path: Path to custom taxonomy rules file.
        feature_store_config: Configuration for the feature store backend.
        fail_fast: Re-raise the first profile error instead of continuing.
        template_min_instance_count: Minimum instances for template mining.
        template_min_distinct_pack_count: Minimum distinct packs for templates.
        quality_min_template_coverage: Minimum template coverage ratio.
        quality_min_taxonomy_confidence_mean: Minimum mean taxonomy confidence.
        quality_max_unknown_effect_family_ratio: Maximum unknown effect-family ratio.
        quality_max_unknown_motion_ratio: Maximum unknown motion ratio.
        quality_max_single_unknown_effect_type_ratio: Maximum single unknown type ratio.
    """

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
    enable_v2_temporal_motif_mining: bool = True
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
    enable_stack_detection: bool = True
    enable_quality_gates: bool = True
    enable_recipe_promotion: bool = True
    enable_color_discovery: bool = True
    enable_effect_metadata: bool = True
    enable_vocabulary_expansion: bool = True
    color_palette_library_path: Path | None = None
    recipe_promotion_min_support: int = 5
    recipe_promotion_min_stability: float = 0.05
    recipe_promotion_adaptive_stability: bool = True
    recipe_promotion_max_per_family: int = 10
    recipe_promotion_param_profiles: dict[str, dict[str, object]] | None = None
    taxonomy_rules_path: Path | None = None
    feature_store_config: FeatureStoreConfig | None = None
    fail_fast: bool = True
    template_min_instance_count: int = 2
    template_min_distinct_pack_count: int = 1
    quality_min_template_coverage: float = 0.80
    quality_min_taxonomy_confidence_mean: float = 0.30
    quality_max_unknown_effect_family_ratio: float = 0.02
    quality_max_unknown_motion_ratio: float = 0.02
    quality_max_single_unknown_effect_type_ratio: float = 0.01


# Alias for use within the decomposed implementation classes.
PipelineConfig = FeatureEngineeringPipelineOptions

__all__ = [
    "FeatureEngineeringPipelineOptions",
    "PipelineConfig",
]
