"""Pydantic models for evaluation reports."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportFlagLevel(StrEnum):
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

    validation_errors: int = Field(default=0, description="Heuristic validation errors")

    model_config = ConfigDict(frozen=True)


class CurveStats(BaseModel):
    """Statistical analysis of a channel's values over the encoded frames."""

    min: float = Field(description="Minimum value")
    max: float = Field(description="Maximum value")
    range: float = Field(description="Range (max - min)")
    mean: float = Field(description="Mean value")
    std: float = Field(description="Standard deviation")
    energy: float = Field(description="Mean absolute rate of change per second")

    model_config = ConfigDict(frozen=True)


class CurveAnalysis(BaseModel):
    """Per-curve metrics and visualization."""

    role: str = Field(description="Fixture role (e.g., OUTER_LEFT)")
    channel: str = Field(description="Channel name (PAN, TILT, DIMMER)")
    space: str = Field(
        description="The unit: 'degree' (pan, tilt, zoom) or 'normalized' (emitted intensity)"
    )
    plot_path: Path | None = Field(default=None, description="Path to plot PNG")
    stats: CurveStats = Field(description="Statistical metrics")
    lit_range: float | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Pan, tilt or zoom only: range over the lit frames (emitted intensity "
            "above 0), leaving out dark repositioning; `stats.range` counts every frame"
        ),
    )
    lit_rate: float | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Pan, tilt or zoom only: mean rate of change per second between "
            "consecutive lit frames; `stats.energy` counts every frame"
        ),
    )

    model_config = ConfigDict(frozen=True)


class TemplateSelection(BaseModel):
    """Template choice for a section or segment."""

    template_id: str = Field(description="Template identifier")
    preset_id: str | None = Field(default=None, description="Preset identifier")
    modifiers: dict[str, str] = Field(
        default_factory=dict, description="Template modifiers applied"
    )
    reasoning: str = Field(default="", description="Agent's reasoning for template choice")

    model_config = ConfigDict(frozen=True)


class SegmentSelection(BaseModel):
    """Segment within a section."""

    segment_id: str = Field(description="Segment identifier (A, B, C)")
    start_bar: float = Field(description="Start bar within song")
    end_bar: float = Field(description="End bar within song")
    template: TemplateSelection = Field(description="Template selection for this segment")

    model_config = ConfigDict(frozen=True)


class SongIntentReport(BaseModel):
    """The planner's song intent for a section or part, as planned.

    Null fields and empty lists are "as the template is authored". `not_rendered` names
    the fields the planner set that the renderer does not render yet (a known regression,
    `changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md`); `played`, what the
    render made of the colour and gobo (`song_intent.describe_look`).
    """

    intensity: str | None = Field(description="Intensity, or null for as authored")
    color: str | None = Field(description="Colour (palette role or named), or null")
    gobo: str | None = Field(description="Gobo pattern, or null")
    moment_cues: list[str] = Field(description="Lyric moment cue ids the section answers")
    events: list[str] = Field(description="Timed accents, one line each")
    motif_id: str | None = Field(description="The macro motif carried, or null")
    variation: str = Field(description="Variation of the motif")
    density: str = Field(description="Movement density")
    entry: str | None = Field(description="Transition into the section, or null")
    exit: str | None = Field(description="Transition out of the section, or null")
    not_rendered: list[str] = Field(description="Fields set that are not rendered yet")
    played: list[str] = Field(
        default_factory=list,
        description="What the render played for the colour and gobo, one line each",
    )

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
    song_intent: SongIntentReport | None = Field(
        default=None, description="The planner's song intent for this section"
    )

    # Rendering data
    targets: TargetResolution = Field(description="Fixture targeting resolution")
    curves: list[CurveAnalysis] = Field(
        default_factory=list, description="Analyzed curves for this section"
    )

    # Issues
    flags: list[ReportFlag] = Field(default_factory=list, description="Issues and warnings")

    validation_issues: list[str] = Field(
        default_factory=list, description="Heuristic validation issues"
    )
    render_facts: SectionRenderFacts = Field(
        description="The renderer's trace facts for this section"
    )

    model_config = ConfigDict(frozen=True)


class EvaluationReport(BaseModel):
    """Top-level evaluation report."""

    schema_version: str = Field(default="2.0.0", description="Report schema version")
    run: RunMetadata = Field(description="Run identification and provenance")
    song: SongMetadata = Field(description="Song timing and structure")
    summary: ReportSummary = Field(description="High-level statistics")
    sections: list[SectionReport] = Field(description="Per-section analysis")
    render: RenderSummary = Field(description="The render's identity and the gate's facts")

    model_config = ConfigDict(frozen=True)


class LitStep(BaseModel):
    """One fixture's change in one channel between two encoded frames."""

    fixture_id: str = Field(description="Fixture")
    channel: str = Field(description="pan, tilt, zoom (degrees) or dimmer (emitted intensity)")
    from_ms: int = Field(description="Start of the earlier frame")
    to_ms: int = Field(description="Start of the later frame")
    change: float = Field(description="Value at `to_ms` minus value at `from_ms`")
    lit: bool = Field(description="Whether both frames emit light")
    allowed: float | None = Field(
        description=(
            "Largest change the fixture's configured travel speed allows over the interval, "
            "plus one DMX word; None for the dimmer or an axis without a travel speed"
        )
    )
    beyond_travel: bool = Field(
        default=False,
        description=(
            "Whether the change exceeds `allowed`, decided exactly in DMX words. The bound "
            "is necessary, not sufficient: it does not detect sustained overspeed of up to "
            "one word per frame, nor a reveal before the head has finished travelling or "
            "settling"
        ),
    )

    model_config = ConfigDict(frozen=True)


class SectionRenderFacts(BaseModel):
    """What a render's trace records about one section, and the motion its
    encoded frames show there."""

    entry_windows: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The section's `entry_windows` records: each fixture's dark entry",
    )
    dropped_cues: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The section's `dropped_cues` records: cues kept dark, with the reason",
    )
    transactions: dict[str, int] = Field(
        default_factory=dict,
        description="Reposition transactions of cues starting in the section, by status",
    )
    diagnostics: list[dict[str, Any]] = Field(
        default_factory=list, description="Render diagnostics naming the section"
    )
    lit_steps: list[LitStep] = Field(
        default_factory=list,
        description=(
            "Per fixture and channel, the largest frame-to-frame step inside the section: "
            "between two lit frames for pan, tilt and zoom, between any two for the dimmer"
        ),
    )
    boundary_steps: list[LitStep] = Field(
        default_factory=list,
        description=(
            "Per fixture whose entry is `skipped` (it plays through the boundary) and "
            "channel, the change from its last lit frame before the section to the "
            "section's first frame"
        ),
    )

    model_config = ConfigDict(frozen=True)


class RenderSummary(BaseModel):
    """A report's render identity and the gate's facts."""

    run_fingerprint: str = Field(description="Render fingerprint the run recorded")
    rerender_fingerprint: str = Field(description="Render fingerprint of the re-render")
    fingerprint_matches: bool = Field(description="Whether the re-render is the run's render")
    mismatched_inputs: list[str] = Field(
        default_factory=list,
        description=(
            "On a mismatch, each recorded input that differs from the re-render's "
            "(fixture profile or model name, the rig's fields, template, beat grid, dark "
            "spans, revisions)"
        ),
    )
    dark_spans: list[list[int]] = Field(
        default_factory=list,
        description=(
            "`[start_ms, end_ms)` spans every head is commanded dark over by a show's "
            "coordination (it rests while another target plays), as rendered"
        ),
    )
    dark_span_ms: int = Field(default=0, description="Total time in the dark spans, in ms")
    admission_exclusions: list[dict[str, Any]] = Field(
        default_factory=list, description="Templates the gate left out of the offer, and why"
    )
    admission_preset_exclusions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Variants of admitted templates the gate did not admit, and why",
    )
    admission_effective_presets: dict[str, str] = Field(
        default_factory=dict,
        description="Each admitted template's effective variant, where not its base",
    )
    unplayable_totals: dict[str, dict[str, int]] = Field(
        default_factory=dict, description="Cues and frames kept dark as unplayable, by code"
    )
    plan_repairs: list[dict[str, str]] = Field(
        default_factory=list,
        description="Items repair dropped, adjusted or recorded in the planner's response",
    )

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
