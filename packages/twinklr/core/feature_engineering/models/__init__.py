"""Public feature engineering model contracts."""

from twinklr.core.feature_engineering.models.alignment import (
    AlignedEffectEvent,
    AlignmentStatus,
)
from twinklr.core.feature_engineering.models.bundle import (
    AudioCandidate,
    AudioCandidateOrigin,
    AudioDiscoveryResult,
    AudioStatus,
    FeatureBundle,
)
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
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
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRole,
    TargetRoleAssignment,
    TaxonomyLabel,
    TaxonomyLabelScore,
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
    "AudioCandidate",
    "AudioCandidateOrigin",
    "AudioDiscoveryResult",
    "AudioStatus",
    "ColorClass",
    "ContinuityClass",
    "EffectPhrase",
    "EnergyClass",
    "FeatureBundle",
    "MotionClass",
    "PhraseSource",
    "PhraseTaxonomyRecord",
    "SpatialClass",
    "TargetRole",
    "TargetRoleAssignment",
    "TaxonomyLabel",
    "TaxonomyLabelScore",
    "MinedTemplate",
    "TemplateAssignment",
    "TemplateCatalog",
    "TemplateKind",
    "TemplateProvenance",
    "TransitionAnomaly",
    "TransitionEdge",
    "TransitionGraph",
    "TransitionRecord",
    "TransitionType",
    "LayeringFeatureRow",
    "ColorNarrativeRow",
    "QualityCheckResult",
    "QualityReport",
]
