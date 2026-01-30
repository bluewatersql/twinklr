"""Pydantic models for evaluation reports."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportFlagLevel(str, Enum):
    """Severity level for report flags."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReportFlag(BaseModel):
    """Issue or warning in the report."""

    level: ReportFlagLevel = Field(description="Severity level")
    code: str = Field(description="Machine-readable code (e.g., CLAMP_PCT, GAP)")
    message: str = Field(description="Human-readable message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    model_config = ConfigDict(frozen=True)


class RunMetadata(BaseModel):
    """Run identification and provenance."""

    run_id: str = Field(description="Unique run identifier from checkpoint")
    timestamp: str = Field(description="ISO 8601 timestamp")
    git_sha: str | None = Field(default=None, description="Git commit SHA")
    engine_version: str = Field(description="Twinklr version")
    checkpoint_path: Path = Field(description="Source checkpoint path")

    model_config = ConfigDict(frozen=True)


class SongMetadata(BaseModel):
    """Song timing and structure information."""

    bpm: float = Field(description="Beats per minute")
    time_signature: str = Field(description="Time signature (e.g., '3/4', '4/4')")
    bars_total: int = Field(description="Total number of bars in song")
    bar_duration_ms: float = Field(description="Duration of one bar in milliseconds")
    song_structure: dict[str, Any] = Field(
        default_factory=dict, description="Audio analyzer structure output"
    )

    model_config = ConfigDict(frozen=True)


class ReportSummary(BaseModel):
    """High-level report statistics."""

    sections: int = Field(description="Number of sections analyzed")
    total_warnings: int = Field(default=0, description="Total warning count across all sections")
    total_errors: int = Field(default=0, description="Total error count across all sections")
    max_concurrent_layers: int = Field(default=0, description="Maximum concurrent active steps")
    templates_used: list[str] = Field(
        default_factory=list, description="Unique template IDs used in plan"
    )
    roles_targeted: list[str] = Field(
        default_factory=list, description="Unique roles targeted in plan"
    )

    # Phase 2: Advanced metrics
    validation_errors: int = Field(default=0, description="Heuristic validation errors")
    physics_violations: int = Field(default=0, description="Physics constraint violations")
    compliance_issues: int = Field(default=0, description="Template compliance issues")
    harsh_transitions: int = Field(default=0, description="Number of harsh section transitions")

    model_config = ConfigDict(frozen=True)


class CurveStats(BaseModel):
    """Statistical analysis of a curve."""

    min: float = Field(description="Minimum value")
    max: float = Field(description="Maximum value")
    range: float = Field(description="Range (max - min)")
    mean: float = Field(description="Mean value")
    std: float = Field(description="Standard deviation")
    clamp_pct: float = Field(description="Percentage of samples at bounds (0-100)")
    energy: float = Field(description="Mean absolute derivative (movement energy)")

    model_config = ConfigDict(frozen=True)


class ContinuityCheck(BaseModel):
    """Loop continuity validation."""

    loop_delta: float = Field(description="Absolute difference between start and end values")
    ok: bool = Field(description="Whether continuity check passed")
    threshold: float = Field(default=0.05, description="Threshold for passing check")

    model_config = ConfigDict(frozen=True)


class CurveAnalysis(BaseModel):
    """Per-curve metrics and visualization."""

    role: str = Field(description="Fixture role (e.g., OUTER_LEFT)")
    channel: str = Field(description="Channel name (PAN, TILT, DIMMER)")
    space: str = Field(description="Value space: 'norm' or 'dmx'")
    plot_path: Path | None = Field(default=None, description="Path to plot PNG")
    stats: CurveStats = Field(description="Statistical metrics")
    continuity: ContinuityCheck = Field(description="Loop continuity check")

    # Metadata from FixtureSegment
    curve_type: str | None = Field(default=None, description="Curve type (e.g., SINE, LINEAR)")
    handler: str | None = Field(default=None, description="Handler that generated curve")
    base_position: float | None = Field(default=None, description="Base position (normalized)")
    static_dmx: int | None = Field(default=None, description="Static DMX value if applicable")

    # Phase 2: Physics validation
    physics_check: PhysicsCheck | None = Field(
        default=None, description="Physical constraint validation results"
    )

    model_config = ConfigDict(frozen=True)


class StepConfig(BaseModel):
    """Resolved step configuration from template."""

    step_id: str = Field(description="Step identifier")
    timing: dict[str, Any] = Field(description="Timing configuration")
    geometry: dict[str, Any] = Field(description="Geometry configuration")
    movement: dict[str, Any] = Field(description="Movement configuration")
    dimmer: dict[str, Any] = Field(description="Dimmer configuration")

    model_config = ConfigDict(frozen=True)


class TemplateSelection(BaseModel):
    """Template choice for a section or segment."""

    template_id: str = Field(description="Template identifier")
    preset_id: str | None = Field(default=None, description="Preset identifier")
    modifiers: dict[str, str] = Field(
        default_factory=dict, description="Template modifiers applied"
    )
    reasoning: str = Field(default="", description="Agent's reasoning for template choice")
    steps: list[StepConfig] = Field(
        default_factory=list, description="Resolved step configurations"
    )

    model_config = ConfigDict(frozen=True)


class SegmentSelection(BaseModel):
    """Segment within a section."""

    segment_id: str = Field(description="Segment identifier (A, B, C)")
    start_bar: float = Field(description="Start bar within song")
    end_bar: float = Field(description="End bar within song")
    template: TemplateSelection = Field(description="Template selection for this segment")

    model_config = ConfigDict(frozen=True)


class TargetResolution(BaseModel):
    """Fixture targeting resolution."""

    bindings: dict[str, str] = Field(default_factory=dict, description="Fixture ID to role mapping")
    resolved_roles: list[str] = Field(
        default_factory=list, description="All roles targeted in section"
    )

    model_config = ConfigDict(frozen=True)


class SectionReport(BaseModel):
    """Analysis for a single section."""

    section_id: str = Field(description="Section identifier")
    label: str = Field(description="Human-readable label")
    bar_range: tuple[float, float] = Field(description="(start_bar, end_bar)")
    time_range_ms: tuple[int, int] = Field(description="(start_ms, end_ms)")

    # Plan data
    selected_template: TemplateSelection | None = Field(
        default=None, description="Template selection (for non-segmented sections)"
    )
    segments: list[SegmentSelection] | None = Field(
        default=None, description="Segment selections (for segmented sections)"
    )

    # Rendering data
    targets: TargetResolution = Field(description="Fixture targeting resolution")
    curves: list[CurveAnalysis] = Field(
        default_factory=list, description="Analyzed curves for this section"
    )

    # Issues
    flags: list[ReportFlag] = Field(default_factory=list, description="Issues and warnings")

    # Phase 2: Advanced validation
    template_compliance: TemplateCompliance | None = Field(
        default=None, description="Template compliance analysis"
    )
    transition_to_next: TransitionAnalysis | None = Field(
        default=None, description="Transition analysis to next section"
    )
    validation_issues: list[str] = Field(
        default_factory=list, description="Heuristic validation issues"
    )

    model_config = ConfigDict(frozen=True)


class EvaluationReport(BaseModel):
    """Top-level evaluation report."""

    schema_version: str = Field(default="1.0.0", description="Report schema version")
    run: RunMetadata = Field(description="Run identification and provenance")
    song: SongMetadata = Field(description="Song timing and structure")
    summary: ReportSummary = Field(description="High-level statistics")
    sections: list[SectionReport] = Field(description="Per-section analysis")

    model_config = ConfigDict(frozen=True)


# =============================================================================
# Phase 2: Advanced Validation Models
# =============================================================================


class ValidationResult(BaseModel):
    """Heuristic validation results."""

    valid: bool = Field(description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    timestamp: str = Field(description="ISO 8601 timestamp of validation")

    model_config = ConfigDict(frozen=True)


class PhysicsCheck(BaseModel):
    """Physical constraint validation for a curve."""

    speed_ok: bool = Field(description="Whether speed limits were respected")
    acceleration_ok: bool = Field(description="Whether acceleration limits were respected")
    max_speed_deg_per_sec: float = Field(description="Maximum observed speed (deg/s)")
    max_accel_deg_per_sec2: float = Field(description="Maximum observed acceleration (deg/s²)")
    violations: list[str] = Field(default_factory=list, description="List of physics violations")

    model_config = ConfigDict(frozen=True)


class ModifierCompliance(BaseModel):
    """Template modifier compliance check."""

    modifier_key: str = Field(description="Modifier parameter name")
    expected_value: Any = Field(description="Expected/requested value")
    actual_impact: str = Field(description="Description of observed impact")
    compliant: bool = Field(description="Whether modifier was applied correctly")
    notes: str | None = Field(default=None, description="Additional compliance notes")

    model_config = ConfigDict(frozen=True)


class TemplateCompliance(BaseModel):
    """Template compliance analysis for a section."""

    template_id: str = Field(description="Template identifier")
    curve_type_correct: bool = Field(description="Whether curve types match expected")
    modifiers_compliant: list[ModifierCompliance] = Field(
        default_factory=list, description="Per-modifier compliance checks"
    )
    geometry_correct: bool = Field(description="Whether geometry was applied correctly")
    overall_compliant: bool = Field(description="Overall compliance status")
    issues: list[str] = Field(default_factory=list, description="Compliance issues")

    model_config = ConfigDict(frozen=True)


class TransitionAnalysis(BaseModel):
    """Transition analysis between two sections."""

    from_section: str = Field(description="Source section name")
    to_section: str = Field(description="Destination section name")
    position_delta_pan: float = Field(description="Pan position change (normalized)")
    position_delta_tilt: float = Field(description="Tilt position change (normalized)")
    velocity_delta: float = Field(description="Velocity change (normalized/sec)")
    dimmer_snap: bool = Field(description="Whether dimmer snapped abruptly")
    smooth: bool = Field(description="Overall transition smoothness")
    issues: list[str] = Field(default_factory=list, description="Transition issues")

    model_config = ConfigDict(frozen=True)


class ComparisonMetrics(BaseModel):
    """Metrics comparison between two reports."""

    metric_name: str = Field(description="Name of the metric")
    report_a_value: float = Field(description="Value in report A")
    report_b_value: float = Field(description="Value in report B")
    delta: float = Field(description="Difference (B - A)")
    delta_pct: float = Field(description="Percent change")
    improved: bool = Field(description="Whether metric improved")

    model_config = ConfigDict(frozen=True)


class ComparisonReport(BaseModel):
    """Comparison of multiple evaluation reports."""

    schema_version: str = Field(default="1.0.0", description="Comparison schema version")
    run_ids: list[str] = Field(description="Run IDs being compared")
    report_count: int = Field(description="Number of reports compared")
    metric_diffs: list[ComparisonMetrics] = Field(description="Per-metric comparison results")
    quality_trend: dict[str, list[float]] = Field(
        default_factory=dict, description="Metric values over iterations"
    )
    best_iteration_idx: int = Field(description="Index of best performing iteration")
    output_path: Path = Field(description="Path to comparison output")

    model_config = ConfigDict(frozen=True)
