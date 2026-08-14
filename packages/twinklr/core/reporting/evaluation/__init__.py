"""Evaluation report generation for choreography plans."""

from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.models import (
    ComparisonMetrics,
    ComparisonReport,
    ContinuityCheck,
    CurveAnalysis,
    CurveStats,
    EvaluationReport,
    ModifierCompliance,
    PhysicsCheck,
    ReportFlag,
    ReportFlagLevel,
    ReportSummary,
    RunMetadata,
    SectionReport,
    SegmentSelection,
    SongMetadata,
    StepConfig,
    TargetResolution,
    TemplateCompliance,
    TemplateSelection,
    TransitionAnalysis,
    ValidationResult,
)
from twinklr.core.reporting.evaluation.sync_metrics import DeterministicSyncMetrics
from twinklr.core.reporting.evaluation.vision_evaluation import VisionEvaluationResult

__all__ = [
    # Phase 2 Models
    "ComparisonMetrics",
    "ComparisonReport",
    # Core Models
    "ContinuityCheck",
    "CurveAnalysis",
    "CurveStats",
    "DeterministicSyncMetrics",
    "EvalConfig",
    "EvaluationReport",
    "ModifierCompliance",
    "PhysicsCheck",
    "ReportFlag",
    "ReportFlagLevel",
    "ReportSummary",
    "RunMetadata",
    "SectionReport",
    "SegmentSelection",
    "SongMetadata",
    "StepConfig",
    "TargetResolution",
    "TemplateCompliance",
    "TemplateSelection",
    "TransitionAnalysis",
    "ValidationResult",
    "VisionEvaluationResult",
    # Generator
    "generate_evaluation_report",
]
