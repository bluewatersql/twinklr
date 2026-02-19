"""Feature engineering package."""

from twinklr.core.feature_engineering.alignment import (
    TemporalAlignmentEngine,
    TemporalAlignmentOptions,
)
from twinklr.core.feature_engineering.audio_discovery import (
    AudioDiscoveryContext,
    AudioDiscoveryOptions,
    AudioDiscoveryService,
)
from twinklr.core.feature_engineering.color_narrative import ColorNarrativeExtractor
from twinklr.core.feature_engineering.datasets.quality import (
    FeatureQualityGates,
    QualityGateOptions,
)
from twinklr.core.feature_engineering.datasets.writer import FeatureEngineeringWriter
from twinklr.core.feature_engineering.layering import LayeringFeatureExtractor
from twinklr.core.feature_engineering.models import (
    AlignedEffectEvent,
    AlignmentStatus,
    AudioCandidate,
    AudioCandidateOrigin,
    AudioDiscoveryResult,
    AudioStatus,
    ColorClass,
    ColorNarrativeRow,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    FeatureBundle,
    LayeringFeatureRow,
    MotionClass,
    PhraseSource,
    PhraseTaxonomyRecord,
    QualityCheckResult,
    QualityReport,
    SpatialClass,
    TargetRole,
    TargetRoleAssignment,
    TaxonomyLabel,
    TaxonomyLabelScore,
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
    TemplateProvenance,
    TransitionAnomaly,
    TransitionEdge,
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)
from twinklr.core.feature_engineering.phrase_encoder import PhraseEncoder, PhraseEncoderOptions
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)
from twinklr.core.feature_engineering.taxonomy import (
    TargetRoleAssigner,
    TargetRoleAssignerOptions,
    TaxonomyClassifier,
    TaxonomyClassifierOptions,
)
from twinklr.core.feature_engineering.templates import TemplateMiner, TemplateMinerOptions
from twinklr.core.feature_engineering.transitions import (
    TransitionModeler,
    TransitionModelerOptions,
)

__all__ = [
    "AlignedEffectEvent",
    "AlignmentStatus",
    "AudioCandidate",
    "AudioCandidateOrigin",
    "AudioDiscoveryContext",
    "AudioDiscoveryOptions",
    "AudioDiscoveryResult",
    "AudioDiscoveryService",
    "AudioStatus",
    "ColorClass",
    "ColorNarrativeExtractor",
    "ColorNarrativeRow",
    "ContinuityClass",
    "EffectPhrase",
    "EnergyClass",
    "FeatureBundle",
    "FeatureEngineeringPipeline",
    "FeatureEngineeringPipelineOptions",
    "FeatureEngineeringWriter",
    "FeatureQualityGates",
    "LayeringFeatureExtractor",
    "LayeringFeatureRow",
    "MotionClass",
    "PhraseEncoder",
    "PhraseEncoderOptions",
    "PhraseSource",
    "PhraseTaxonomyRecord",
    "QualityCheckResult",
    "QualityGateOptions",
    "QualityReport",
    "SpatialClass",
    "TargetRole",
    "TargetRoleAssigner",
    "TargetRoleAssignerOptions",
    "TargetRoleAssignment",
    "TaxonomyClassifier",
    "TaxonomyClassifierOptions",
    "TaxonomyLabel",
    "TaxonomyLabelScore",
    "TemplateAssignment",
    "TemplateCatalog",
    "TemplateKind",
    "TemplateMiner",
    "TemplateMinerOptions",
    "TemplateProvenance",
    "TemporalAlignmentEngine",
    "TemporalAlignmentOptions",
    "TransitionAnomaly",
    "TransitionEdge",
    "TransitionGraph",
    "TransitionModeler",
    "TransitionModelerOptions",
    "TransitionRecord",
    "TransitionType",
]

