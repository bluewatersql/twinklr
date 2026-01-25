"""Evaluation report generation for choreography plans."""

from blinkb0t.core.reporting.evaluation.config import EvalConfig
from blinkb0t.core.reporting.evaluation.generator import generate_evaluation_report
from blinkb0t.core.reporting.evaluation.models import (
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

__all__ = [
    # Generator
    "generate_evaluation_report",
    "EvalConfig",
    # Core Models
    "ContinuityCheck",
    "CurveAnalysis",
    "CurveStats",
    "EvaluationReport",
    "ReportFlag",
    "ReportFlagLevel",
    "ReportSummary",
    "RunMetadata",
    "SectionReport",
    "SegmentSelection",
    "SongMetadata",
    "StepConfig",
    "TargetResolution",
    "TemplateSelection",
    # Phase 2 Models
    "ComparisonMetrics",
    "ComparisonReport",
    "ModifierCompliance",
    "PhysicsCheck",
    "TemplateCompliance",
    "TransitionAnalysis",
    "ValidationResult",
]
