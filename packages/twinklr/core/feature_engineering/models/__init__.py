"""Public feature engineering model contracts."""

from twinklr.core.feature_engineering.models.adapters import (
    GroupPlannerAdapterPayload,
    MacroPlannerAdapterPayload,
    PlannerChangeMode,
    RoleBindingContext,
    SequenceAdapterContext,
    SequencerAdapterBundle,
    SequencerAdapterScope,
    TemplateConstraint,
    TransitionConstraint,
)
from twinklr.core.feature_engineering.models.alignment import (
    AlignedEffectEvent,
    AlignmentStatus,
)
from twinklr.core.feature_engineering.models.ann_retrieval import (
    AnnIndexEntry,
    AnnRetrievalEvalReport,
    AnnRetrievalIndex,
)
from twinklr.core.feature_engineering.models.bundle import (
    AudioCandidate,
    AudioCandidateOrigin,
    AudioDiscoveryResult,
    AudioStatus,
    FeatureBundle,
)
from twinklr.core.feature_engineering.models.clustering import (
    ClusterMember,
    ClusterReviewQueueRow,
    TemplateClusterCandidate,
    TemplateClusterCatalog,
)
from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    ColorTransitionRule,
    NamedPalette,
    SectionColorAssignment,
    SongColorArc,
)
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.learned_taxonomy import (
    LearnedTaxonomyEvalReport,
    LearnedTaxonomyModel,
)
from twinklr.core.feature_engineering.models.metadata import (
    DurationDistribution,
    EffectMetadataProfile,
    EffectMetadataProfiles,
    LayeringBehavior,
    ParamFrequency,
    ParamProfile,
    SectionPlacement,
)
from twinklr.core.feature_engineering.models.motifs import (
    MinedMotif,
    MotifCatalog,
    MotifOccurrence,
)
from twinklr.core.feature_engineering.models.music_library import (
    MusicLibraryEntry,
    MusicLibraryIndex,
)
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    EffectModelAntiAffinity,
    PropensityIndex,
)
from twinklr.core.feature_engineering.models.quality import (
    QualityCheckResult,
    QualityReport,
)
from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
)
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackCatalog,
    EffectStackLayer,
)
from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleBlend,
    StyleEvolution,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRole,
    TargetRoleAssignment,
    TaxonomyLabel,
    TaxonomyLabelScore,
)
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
    TemplateKind,
    TemplateProvenance,
)
from twinklr.core.feature_engineering.models.temporal_motifs import (
    TemporalMotif,
    TemporalMotifCatalog,
    TemporalMotifStep,
)
from twinklr.core.feature_engineering.models.transitions import (
    TransitionAnomaly,
    TransitionEdge,
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)
from twinklr.core.feature_engineering.models.vocabulary import (
    CompoundEnergyTerm,
    CompoundMotionTerm,
    VocabularyExtensions,
)

__all__ = [
    "AlignedEffectEvent",
    "AlignmentStatus",
    "AnnIndexEntry",
    "AnnRetrievalEvalReport",
    "AnnRetrievalIndex",
    "ArcKeyframe",
    "AudioCandidate",
    "AudioCandidateOrigin",
    "AudioDiscoveryResult",
    "AudioStatus",
    "ClusterMember",
    "ClusterReviewQueueRow",
    "ColorClass",
    "ColorNarrativeRow",
    "ColorStyleProfile",
    "ColorTransitionRule",
    # vocabulary extensions
    "CompoundEnergyTerm",
    "CompoundMotionTerm",
    "ContinuityClass",
    # metadata profiles
    "DurationDistribution",
    "EffectMetadataProfile",
    "EffectMetadataProfiles",
    "EffectModelAffinity",
    "EffectModelAntiAffinity",
    "EffectPhrase",
    "EffectStack",
    "EffectStackCatalog",
    "EffectStackLayer",
    "EnergyClass",
    "FeatureBundle",
    "GroupPlannerAdapterPayload",
    "LayeringBehavior",
    "LayeringFeatureRow",
    "LayeringStyleProfile",
    "LearnedTaxonomyEvalReport",
    "LearnedTaxonomyModel",
    "MacroPlannerAdapterPayload",
    "MinedMotif",
    "MinedTemplate",
    "MotifCatalog",
    "MotifOccurrence",
    "MotionClass",
    "MusicLibraryEntry",
    "MusicLibraryIndex",
    "NamedPalette",
    "ParamFrequency",
    "ParamProfile",
    "PhraseSource",
    "PhraseTaxonomyRecord",
    "PlannerChangeMode",
    "PropensityIndex",
    "QualityCheckResult",
    "QualityReport",
    "RoleBindingContext",
    "SectionColorAssignment",
    "SectionPlacement",
    "SequenceAdapterContext",
    "SequencerAdapterBundle",
    "SequencerAdapterScope",
    "SongColorArc",
    "SpatialClass",
    "StyleBlend",
    "StyleEvolution",
    "StyleFingerprint",
    "TargetRole",
    "TargetRoleAssignment",
    "TaxonomyLabel",
    "TaxonomyLabelScore",
    "TemplateAssignment",
    "TemplateCatalog",
    "TemplateClusterCandidate",
    "TemplateClusterCatalog",
    "TemplateConstraint",
    "TemplateDiagnosticFlag",
    "TemplateDiagnosticRow",
    "TemplateDiagnosticThresholds",
    "TemplateDiagnosticsReport",
    "TemplateKind",
    "TemplateProvenance",
    "TemplateRecommendation",
    "TemplateRetrievalIndex",
    # temporal motifs
    "TemporalMotif",
    "TemporalMotifCatalog",
    "TemporalMotifStep",
    "TimingStyleProfile",
    "TransitionAnomaly",
    "TransitionConstraint",
    "TransitionEdge",
    "TransitionGraph",
    "TransitionRecord",
    "TransitionStyleProfile",
    "TransitionType",
    "VocabularyExtensions",
]
