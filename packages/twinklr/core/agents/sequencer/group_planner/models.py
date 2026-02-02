"""GroupPlanner models for section-level cross-group coordination.

These models implement the v3.3 specification for GroupPlanner output.
Key principles:
- Iteration unit is SECTION (not per-group)
- TimeRef is used for all authored timing (no bar-only fields)
- SEQUENCED/CALL_RESPONSE/RIPPLE use window+config (Assembler expands)
- Lane intent mirrors MacroPlan (timing_driver, target_roles, blend_mode)
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# =============================================================================
# Enums (GroupPlanner-specific, per spec v3.3)
# =============================================================================


class LaneKind(str, Enum):
    """Lane (layer) types for choreography."""

    BASE = "BASE"  # Bed / background continuity
    RHYTHM = "RHYTHM"  # Beat-driven motion / texture
    ACCENT = "ACCENT"  # Focal punctuation, hits, callouts


class CoordinationMode(str, Enum):
    """Coordination mode for cross-group choreography."""

    UNIFIED = "UNIFIED"  # Same behavior across groups simultaneously
    COMPLEMENTARY = "COMPLEMENTARY"  # Different behaviors, designed to harmonize
    SEQUENCED = "SEQUENCED"  # Ordered progression across groups
    CALL_RESPONSE = "CALL_RESPONSE"  # Alternating sets (A responds to B)
    RIPPLE = "RIPPLE"  # Propagation across ordered set with overlap


class StepUnit(str, Enum):
    """Step unit for sequenced coordination."""

    BEAT = "BEAT"
    BAR = "BAR"
    PHRASE = "PHRASE"


class SpillPolicy(str, Enum):
    """Policy for handling placements that spill outside section bounds."""

    TRUNCATE = "TRUNCATE"  # Clip to section end
    DROP = "DROP"  # Omit if extends past section
    WRAP = "WRAP"  # Wrap to next occurrence (if applicable)


class SnapRule(str, Enum):
    """Snap rule for time alignment."""

    BAR = "BAR"
    BEAT = "BEAT"
    PHRASE = "PHRASE"
    NONE = "NONE"


class TimeRefKind(str, Enum):
    """Kind of time reference."""

    BAR_BEAT = "BAR_BEAT"  # Bar/beat/beat_frac based
    MS = "MS"  # Absolute milliseconds


class SpatialIntent(str, Enum):
    """Spatial direction intent for coordination."""

    NONE = "NONE"
    L2R = "L2R"  # Left to right
    R2L = "R2L"  # Right to left
    C2O = "C2O"  # Center to outer
    O2C = "O2C"  # Outer to center
    RANDOM = "RANDOM"


class GPBlendMode(str, Enum):
    """Blend mode for GroupPlanner (distinct from core BlendMode)."""

    ADD = "add"
    MAX = "max"
    ALPHA_OVER = "alpha_over"


class GPTimingDriver(str, Enum):
    """Timing driver for GroupPlanner lanes."""

    BEATS = "BEATS"
    BARS = "BARS"
    PHRASES = "PHRASES"
    LYRICS = "LYRICS"


# =============================================================================
# TimeRef Model
# =============================================================================


class TimeRef(BaseModel):
    """Canonical time reference for all authored timing.

    Supports two modes:
    - BAR_BEAT: (bar, beat, beat_frac) with optional offset_ms nudge
    - MS: Absolute milliseconds (offset_ms required, bar/beat must be None)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TimeRefKind

    # BAR_BEAT fields
    bar: int | None = Field(default=None, ge=1)
    beat: int | None = Field(default=None, ge=1)
    beat_frac: float = Field(default=0.0, ge=0.0, le=1.0)

    # Fine nudge (BAR_BEAT) or required absolute offset (MS)
    offset_ms: int | None = None

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> TimeRef:
        """Validate fields match the kind."""
        if self.kind == TimeRefKind.BAR_BEAT:
            if self.bar is None:
                raise ValueError("TimeRef(kind=BAR_BEAT): bar is required")
            if self.beat is None:
                raise ValueError("TimeRef(kind=BAR_BEAT): beat is required")
        elif self.kind == TimeRefKind.MS:
            if self.offset_ms is None:
                raise ValueError("TimeRef(kind=MS): offset_ms is required")
            if self.bar is not None:
                raise ValueError("TimeRef(kind=MS): bar must be None")
            if self.beat is not None:
                raise ValueError("TimeRef(kind=MS): beat must be None")
        return self


# =============================================================================
# DisplayGraph Models
# =============================================================================


class GroupPosition(BaseModel):
    """Normalized spatial position for a display group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    z: float = Field(default=0.0, ge=0.0, le=1.0)
    zone: str | None = None


class DisplayGroup(BaseModel):
    """Single display group definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str
    display_name: str

    position: GroupPosition | None = None
    capabilities: list[str] = Field(default_factory=list)
    fixture_count: int = Field(default=1, ge=1)


class DisplayGraph(BaseModel):
    """Complete display configuration with group-to-role mapping.

    Provides groups_by_role computed property for role expansion.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "display-graph.v1"
    display_id: str
    display_name: str
    groups: list[DisplayGroup] = Field(min_length=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def groups_by_role(self) -> dict[str, list[str]]:
        """Map role -> list of group_ids."""
        result: dict[str, list[str]] = {}
        for g in self.groups:
            result.setdefault(g.role, []).append(g.group_id)
        return result

    def get_group(self, group_id: str) -> DisplayGroup | None:
        """Get group by ID, or None if not found."""
        return next((g for g in self.groups if g.group_id == group_id), None)


# =============================================================================
# Template Catalog (Lightweight)
# =============================================================================
# NOTE: TemplateCatalog models are now imported from catalog at top of file
# for backward compatibility. See import section above.


# =============================================================================
# GroupPlacement and Coordination Models
# =============================================================================


class GroupPlacement(BaseModel):
    """Individual placement of a template on a group.

    Uses TimeRef for start/end timing (no bar-only fields).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    placement_id: str
    group_id: str
    template_id: str
    start: TimeRef
    end: TimeRef

    # Optional overrides
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    intensity: float = Field(default=1.0, ge=0.0, le=1.5)
    snap_rule: SnapRule = SnapRule.BEAT


class PlacementWindow(BaseModel):
    """Window for sequenced/ripple/call-response expansion.

    Defines the overall time window and template for Assembler expansion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: TimeRef
    end: TimeRef
    template_id: str
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    snap_rule: SnapRule = SnapRule.BEAT


class CoordinationConfig(BaseModel):
    """Configuration for SEQUENCED/CALL_RESPONSE/RIPPLE modes.

    Assembler uses this to expand to per-group placements deterministically.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_order: list[str] = Field(min_length=1)
    step_unit: StepUnit = StepUnit.BEAT
    step_duration: int = Field(default=1, ge=1)
    phase_offset: float = Field(default=0.0, ge=0.0, le=1.0)
    spill_policy: SpillPolicy = SpillPolicy.TRUNCATE
    spatial_intent: SpatialIntent = SpatialIntent.NONE


class CoordinationPlan(BaseModel):
    """Coordination plan for a set of groups within a lane.

    For UNIFIED/COMPLEMENTARY: placements are provided directly.
    For SEQUENCED/CALL_RESPONSE/RIPPLE: window + config provided, Assembler expands.
    """

    model_config = ConfigDict(extra="forbid")

    coordination_mode: CoordinationMode
    group_ids: list[str] = Field(min_length=1)

    # For UNIFIED/COMPLEMENTARY modes
    placements: list[GroupPlacement] = Field(default_factory=list)

    # For SEQUENCED/CALL_RESPONSE/RIPPLE modes
    window: PlacementWindow | None = None
    config: CoordinationConfig | None = None


# =============================================================================
# Lane and Section Plans
# =============================================================================


class LanePlan(BaseModel):
    """Plan for a single lane (BASE/RHYTHM/ACCENT) in a section.

    Mirrors MacroPlan lane intent (timing_driver, target_roles, blend_mode).
    """

    model_config = ConfigDict(extra="forbid")

    lane: LaneKind
    target_roles: list[str] = Field(min_length=1)
    timing_driver: GPTimingDriver = GPTimingDriver.BEATS
    blend_mode: GPBlendMode = GPBlendMode.ADD

    coordination_plans: list[CoordinationPlan] = Field(default_factory=list)


class Deviation(BaseModel):
    """Explicit deviation from MacroPlan intent.

    If GroupPlanner cannot satisfy a MacroPlan intent, it must
    document the deviation explicitly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    deviation_id: str
    intent_field: str  # Which MacroPlan field was not honored
    reason: str
    mitigation: str | None = None


class SectionCoordinationPlan(BaseModel):
    """Complete coordination plan for a single section.

    This is the output of one GroupPlanner invocation.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "section-coordination-plan.v1"
    section_id: str

    lane_plans: list[LanePlan] = Field(min_length=1)
    deviations: list[Deviation] = Field(default_factory=list)

    # Optional notes for debugging/tracing
    planning_notes: str | None = None


# =============================================================================
# Aggregated Output
# =============================================================================


class AssetRequest(BaseModel):
    """Asset request from GroupPlanner to Asset Creation Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    kind: str  # "image_png", "image_gif", "texture"
    use_case: str  # "matrix_texture", "sprite", "gobo", etc.
    style_tags: list[str] = Field(default_factory=list)
    content_tags: list[str] = Field(default_factory=list)
    fallback_strategy: str = "use_builtin_if_missing"


class GroupPlanSet(BaseModel):
    """Aggregated coordination plans for all sections.

    This is the final output of the GroupPlanner orchestration.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group-plan-set.v1"
    plan_set_id: str

    section_plans: list[SectionCoordinationPlan] = Field(min_length=1)
    asset_requests: list[AssetRequest] = Field(default_factory=list)

    # Holistic evaluation result (populated after holistic judge)
    # holistic_evaluation: HolisticEvaluation | None = None  # Added in Phase 3
