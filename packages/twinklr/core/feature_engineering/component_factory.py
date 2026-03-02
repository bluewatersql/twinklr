"""Lazy component factory for the feature-engineering pipeline — CQ-01 / PERF-20.

All sub-components are constructed via ``@cached_property`` so they are
only instantiated when first accessed. Components that are never accessed
incur zero construction cost.
"""

from __future__ import annotations

from functools import cached_property

from twinklr.core.feature_engineering.adapters import GroupAdapterBuilder, MacroAdapterBuilder
from twinklr.core.feature_engineering.alignment import TemporalAlignmentEngine
from twinklr.core.feature_engineering.ann_retrieval import (
    AnnRetrievalOptions,
    AnnTemplateRetrievalIndexer,
)
from twinklr.core.feature_engineering.clustering import (
    TemplateClusterer,
    TemplateClustererOptions,
)
from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.color_discovery import ColorFamilyDiscoverer
from twinklr.core.feature_engineering.color_narrative import ColorNarrativeExtractor
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.datasets.quality import (
    FeatureQualityGates,
    QualityGateOptions,
)
from twinklr.core.feature_engineering.layering import LayeringFeatureExtractor
from twinklr.core.feature_engineering.metadata_profiles import EffectMetadataProfileBuilder
from twinklr.core.feature_engineering.motifs import MotifMiner, MotifMinerOptions
from twinklr.core.feature_engineering.phrase_encoder import PhraseEncoder
from twinklr.core.feature_engineering.propensity import PropensityMiner
from twinklr.core.feature_engineering.retrieval import TemplateRetrievalRanker
from twinklr.core.feature_engineering.stack_detector import EffectStackDetector
from twinklr.core.feature_engineering.style import StyleFingerprintExtractor
from twinklr.core.feature_engineering.taxonomy import (
    LearnedTaxonomyTrainer,
    LearnedTaxonomyTrainerOptions,
    TargetRoleAssigner,
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)
from twinklr.core.feature_engineering.template_diagnostics import TemplateDiagnosticsBuilder
from twinklr.core.feature_engineering.templates import TemplateMiner, TemplateMinerOptions
from twinklr.core.feature_engineering.transitions import TransitionModeler
from twinklr.core.feature_engineering.vocabulary_expander import VocabularyExpander


class ComponentFactory:
    """Lazy factory for all feature-engineering sub-components.

    Each component is constructed the first time its property is accessed and
    then cached for subsequent calls. Construction is driven by the options
    object supplied at factory creation time.

    Args:
        options: Pipeline options that control component configuration.

    Example::

        factory = ComponentFactory(FeatureEngineeringPipelineOptions())
        encoder = factory.phrase_encoder   # constructed here
        encoder2 = factory.phrase_encoder  # same instance, no re-construction
    """

    def __init__(self, options: FeatureEngineeringPipelineOptions) -> None:
        self._options = options

    # ------------------------------------------------------------------
    # Alignment & encoding
    # ------------------------------------------------------------------

    @cached_property
    def alignment(self) -> TemporalAlignmentEngine:
        """Temporal alignment engine (lazy).

        Returns:
            A ``TemporalAlignmentEngine`` instance.
        """
        return TemporalAlignmentEngine()

    @cached_property
    def phrase_encoder(self) -> PhraseEncoder:
        """Phrase encoder (lazy).

        Returns:
            A ``PhraseEncoder`` instance.
        """
        return PhraseEncoder()

    # ------------------------------------------------------------------
    # Taxonomy & roles
    # ------------------------------------------------------------------

    @cached_property
    def taxonomy_classifier(self) -> TaxonomyClassifier:
        """Taxonomy classifier (lazy).

        Returns:
            A ``TaxonomyClassifier`` configured with the pipeline options.
        """
        return TaxonomyClassifier(
            TaxonomyClassifierOptions(rules_path=self._options.taxonomy_rules_path)
        )

    @cached_property
    def target_roles(self) -> TargetRoleAssigner:
        """Target-role assigner (lazy).

        Returns:
            A ``TargetRoleAssigner`` instance.
        """
        return TargetRoleAssigner()

    @cached_property
    def learned_taxonomy_trainer(self) -> LearnedTaxonomyTrainer:
        """Learned taxonomy trainer (lazy).

        Returns:
            A ``LearnedTaxonomyTrainer`` configured with the pipeline options.
        """
        return LearnedTaxonomyTrainer(
            LearnedTaxonomyTrainerOptions(
                min_recall_for_promotion=self._options.v2_taxonomy_min_recall_for_promotion,
                min_f1_for_promotion=self._options.v2_taxonomy_min_f1_for_promotion,
            )
        )

    # ------------------------------------------------------------------
    # Template mining & retrieval
    # ------------------------------------------------------------------

    @cached_property
    def template_miner(self) -> TemplateMiner:
        """Template miner (lazy).

        Returns:
            A ``TemplateMiner`` configured with the pipeline options.
        """
        return TemplateMiner(
            TemplateMinerOptions(
                min_instance_count=self._options.template_min_instance_count,
                min_distinct_pack_count=self._options.template_min_distinct_pack_count,
            )
        )

    @cached_property
    def transition_modeler(self) -> TransitionModeler:
        """Transition modeller (lazy).

        Returns:
            A ``TransitionModeler`` instance.
        """
        return TransitionModeler()

    @cached_property
    def template_retrieval_ranker(self) -> TemplateRetrievalRanker:
        """Template retrieval ranker (lazy).

        Returns:
            A ``TemplateRetrievalRanker`` instance.
        """
        return TemplateRetrievalRanker()

    @cached_property
    def template_diagnostics(self) -> TemplateDiagnosticsBuilder:
        """Template diagnostics builder (lazy).

        Returns:
            A ``TemplateDiagnosticsBuilder`` instance.
        """
        return TemplateDiagnosticsBuilder()

    # ------------------------------------------------------------------
    # V2 mining & clustering
    # ------------------------------------------------------------------

    @cached_property
    def motif_miner(self) -> MotifMiner:
        """Motif miner (lazy).

        Returns:
            A ``MotifMiner`` configured with the pipeline options.
        """
        return MotifMiner(
            MotifMinerOptions(
                min_support_count=self._options.v2_motif_min_support_count,
                min_distinct_pack_count=self._options.v2_motif_min_distinct_pack_count,
                min_distinct_sequence_count=self._options.v2_motif_min_distinct_sequence_count,
            )
        )

    @cached_property
    def template_clusterer(self) -> TemplateClusterer:
        """Template clusterer (lazy).

        Returns:
            A ``TemplateClusterer`` configured with the pipeline options.
        """
        return TemplateClusterer(
            TemplateClustererOptions(
                similarity_threshold=self._options.v2_cluster_similarity_threshold,
                min_cluster_size=self._options.v2_cluster_min_size,
            )
        )

    @cached_property
    def ann_retrieval_indexer(self) -> AnnTemplateRetrievalIndexer:
        """ANN retrieval indexer (lazy).

        Returns:
            An ``AnnTemplateRetrievalIndexer`` configured with the pipeline options.
        """
        return AnnTemplateRetrievalIndexer(
            AnnRetrievalOptions(
                min_same_effect_family_recall_at_5=self._options.v2_retrieval_min_recall_at_5,
                max_avg_query_latency_ms=self._options.v2_retrieval_max_avg_latency_ms,
            )
        )

    # ------------------------------------------------------------------
    # Stack detection & adapters
    # ------------------------------------------------------------------

    @cached_property
    def stack_detector(self) -> EffectStackDetector:
        """Effect stack detector (lazy).

        Returns:
            An ``EffectStackDetector`` instance.
        """
        return EffectStackDetector()

    @cached_property
    def macro_adapter_builder(self) -> MacroAdapterBuilder:
        """Macro adapter builder (lazy).

        Returns:
            A ``MacroAdapterBuilder`` instance.
        """
        return MacroAdapterBuilder()

    @cached_property
    def group_adapter_builder(self) -> GroupAdapterBuilder:
        """Group adapter builder (lazy).

        Returns:
            A ``GroupAdapterBuilder`` instance.
        """
        return GroupAdapterBuilder()

    # ------------------------------------------------------------------
    # Feature extractors
    # ------------------------------------------------------------------

    @cached_property
    def layering(self) -> LayeringFeatureExtractor:
        """Layering feature extractor (lazy).

        Returns:
            A ``LayeringFeatureExtractor`` instance.
        """
        return LayeringFeatureExtractor()

    @cached_property
    def color_narrative(self) -> ColorNarrativeExtractor:
        """Colour narrative extractor (lazy).

        Returns:
            A ``ColorNarrativeExtractor`` instance.
        """
        return ColorNarrativeExtractor()

    @cached_property
    def color_arc(self) -> ColorArcExtractor:
        """Colour arc extractor (lazy).

        Returns:
            A ``ColorArcExtractor`` instance.
        """
        return ColorArcExtractor(
            palette_library_path=self._options.color_palette_library_path
        )

    @cached_property
    def propensity_miner(self) -> PropensityMiner:
        """Propensity miner (lazy).

        Returns:
            A ``PropensityMiner`` instance.
        """
        return PropensityMiner()

    @cached_property
    def style_fingerprint(self) -> StyleFingerprintExtractor:
        """Style fingerprint extractor (lazy).

        Returns:
            A ``StyleFingerprintExtractor`` instance.
        """
        return StyleFingerprintExtractor()

    @cached_property
    def quality_gates(self) -> FeatureQualityGates:
        """Feature quality gates (lazy).

        Returns:
            A ``FeatureQualityGates`` instance configured with the pipeline options.
        """
        return FeatureQualityGates(
            QualityGateOptions(
                min_template_coverage=self._options.quality_min_template_coverage,
                min_taxonomy_confidence_mean=self._options.quality_min_taxonomy_confidence_mean,
                max_unknown_effect_family_ratio=self._options.quality_max_unknown_effect_family_ratio,
                max_unknown_motion_ratio=self._options.quality_max_unknown_motion_ratio,
                max_single_unknown_effect_type_ratio=self._options.quality_max_single_unknown_effect_type_ratio,
            )
        )

    # ------------------------------------------------------------------
    # Enrichment components
    # ------------------------------------------------------------------

    @cached_property
    def color_family_discoverer(self) -> ColorFamilyDiscoverer:
        """Color family discoverer (lazy).

        Returns:
            A ``ColorFamilyDiscoverer`` instance.
        """
        return ColorFamilyDiscoverer()

    @cached_property
    def effect_metadata_builder(self) -> EffectMetadataProfileBuilder:
        """Effect metadata profile builder (lazy).

        Returns:
            An ``EffectMetadataProfileBuilder`` instance.
        """
        return EffectMetadataProfileBuilder()

    @cached_property
    def vocabulary_expander(self) -> VocabularyExpander:
        """Vocabulary expander (lazy).

        Returns:
            A ``VocabularyExpander`` instance.
        """
        return VocabularyExpander()


__all__ = ["ComponentFactory"]
