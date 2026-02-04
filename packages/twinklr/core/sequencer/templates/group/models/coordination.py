"""Coordination and planning models.

Models for group placement, coordination, and section planning.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    GPBlendMode,
    GPTimingDriver,
    LaneKind,
    SnapRule,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
)


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
    theme: ThemeRef
    motif_tags: list[str] = Field(default_factory=list)

    lane_plans: list[LanePlan] = Field(min_length=1)
    deviations: list[Deviation] = Field(default_factory=list)

    # Optional notes for debugging/tracing
    planning_notes: str | None = None


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


__all__ = [
    "CoordinationConfig",
    "CoordinationPlan",
    "Deviation",
    "GroupPlacement",
    "GroupPlanSet",
    "LanePlan",
    "PlacementWindow",
    "SectionCoordinationPlan",
    "ThemeRef",
    "TimeRef",
]
