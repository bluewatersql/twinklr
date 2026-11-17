"""Evaluation report generation for choreography plans."""

from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.generator import generate_evaluation_report
from twinklr.core.reporting.evaluation.models import (
    CurveAnalysis,
    CurveStats,
    EvaluationReport,
    ReportFlag,
    ReportFlagLevel,
    ReportSummary,
    RunMetadata,
    SectionReport,
    SegmentSelection,
    SongMetadata,
    TargetResolution,
    TemplateSelection,
    ValidationResult,
)
from twinklr.core.reporting.evaluation.sync_metrics import DeterministicSyncMetrics
from twinklr.core.reporting.evaluation.three_arm import ComparisonReport
from twinklr.core.reporting.evaluation.vision_evaluation import VisionEvaluationResult

__all__ = [
    "ComparisonReport",
    "CurveAnalysis",
    "CurveStats",
    "DeterministicSyncMetrics",
    "EvalConfig",
    "EvaluationReport",
    "ReportFlag",
    "ReportFlagLevel",
    "ReportSummary",
    "RunMetadata",
    "SectionReport",
    "SegmentSelection",
    "SongMetadata",
    "TargetResolution",
    "TemplateSelection",
    "ValidationResult",
    "VisionEvaluationResult",
    # Generator
    "generate_evaluation_report",
]
