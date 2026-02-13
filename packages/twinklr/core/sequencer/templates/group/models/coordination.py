"""Coordination models for group template placement.

Models for group placement, coordination configuration, and coordination plans.
These define how templates are placed and coordinated across groups.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    IntensityLevel,
    PlanningTimeRef,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
)


class GroupPlacement(BaseModel):
    """Individual placement of a template on a group.

    Uses categorical planning values:
    - PlanningTimeRef for start timing (bar + beat only)
    - EffectDuration for duration (categorical, renderer calculates end)
    - IntensityLevel for intensity (categorical, renderer resolves to numeric)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    placement_id: str
    group_id: str
    template_id: str
    start: PlanningTimeRef
    duration: EffectDuration = Field(
        default=EffectDuration.PHRASE,
        description="Categorical duration - renderer calculates end time",
    )

    # Optional overrides
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    intensity: IntensityLevel = Field(
        default=IntensityLevel.MED,
        description="Categorical intensity - renderer resolves to lane-appropriate value",
    )

    # Asset resolution — populated by resolve_plan_assets(), not by LLM
    resolved_asset_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Catalog asset_ids resolved for this placement. "
            "Populated by the asset resolution step pre-render. "
            "Empty means no asset match (procedural-only rendering)."
        ),
    )


class PlacementWindow(BaseModel):
    """Window for sequenced/ripple/call-response expansion.

    Defines the overall time window and template for Assembler expansion.
    Uses explicit start/end PlanningTimeRef (not duration) because the
    expansion logic needs to know the exact window bounds.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: PlanningTimeRef
    end: PlanningTimeRef
    template_id: str
    param_overrides: dict[str, Any] = Field(default_factory=dict)
    intensity: IntensityLevel = Field(
        default=IntensityLevel.MED,
        description="Categorical intensity for expanded placements",
    )


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


__all__ = [
    "CoordinationConfig",
    "CoordinationPlan",
    "GroupPlacement",
    "PlacementWindow",
]
