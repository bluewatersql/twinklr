"""Public feature engineering model contracts."""

from twinklr.core.feature_engineering.models.alignment import (
    AlignedEffectEvent,
    AlignmentStatus,
)
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
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    EffectModelAntiAffinity,
    PropensityIndex,
)
from twinklr.core.feature_engineering.models.learned_taxonomy import (
    LearnedTaxonomyEvalReport,
    LearnedTaxonomyModel,
)
from twinklr.core.feature_engineering.models.motifs import (
    MinedMotif,
    MotifCatalog,
    MotifOccurrence,
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
from twinklr.core.feature_engineering.models.quality import (
    QualityCheckResult,
    QualityReport,
)
from twinklr.core.feature_engineering.models.retrieval import (
    TemplateRecommendation,
    TemplateRetrievalIndex,
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
from twinklr.core.feature_engineering.models.transitions import (
    TransitionAnomaly,
    TransitionEdge,
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)

__all__ = [
    "AlignedEffectEvent",
    "AlignmentStatus",
    "GroupPlannerAdapterPayload",
    "MacroPlannerAdapterPayload",
    "PlannerChangeMode",
    "RoleBindingContext",
    "SequenceAdapterContext",
    "SequencerAdapterBundle",
    "SequencerAdapterScope",
    "AudioCandidate",
    "AudioCandidateOrigin",
    "AudioDiscoveryResult",
    "AudioStatus",
    "AnnIndexEntry",
    "AnnRetrievalEvalReport",
    "AnnRetrievalIndex",
    "ClusterMember",
    "ClusterReviewQueueRow",
    "ArcKeyframe",
    "ColorTransitionRule",
    "NamedPalette",
    "SectionColorAssignment",
    "SongColorArc",
    "ColorClass",
    "ContinuityClass",
    "EffectModelAffinity",
    "EffectModelAntiAffinity",
    "EffectPhrase",
    "EnergyClass",
    "FeatureBundle",
    "LearnedTaxonomyEvalReport",
    "LearnedTaxonomyModel",
    "MinedMotif",
    "MotionClass",
    "MotifCatalog",
    "MotifOccurrence",
    "PhraseSource",
    "PhraseTaxonomyRecord",
    "PropensityIndex",
    "SpatialClass",
    "TargetRole",
    "TargetRoleAssignment",
    "TaxonomyLabel",
    "TaxonomyLabelScore",
    "MinedTemplate",
    "TemplateAssignment",
    "TemplateCatalog",
    "TemplateClusterCandidate",
    "TemplateClusterCatalog",
    "TemplateConstraint",
    "TemplateKind",
    "TemplateProvenance",
    "TransitionAnomaly",
    "TransitionEdge",
    "TransitionGraph",
    "TransitionConstraint",
    "TransitionRecord",
    "TransitionType",
    "LayeringFeatureRow",
    "ColorNarrativeRow",
    "QualityCheckResult",
    "QualityReport",
    "TemplateRecommendation",
    "TemplateRetrievalIndex",
    "TemplateDiagnosticFlag",
    "TemplateDiagnosticRow",
    "TemplateDiagnosticsReport",
    "TemplateDiagnosticThresholds",
]
