"""Coordination models for group template placement.

Models for group placement, coordination configuration, and coordination plans.
These define how templates are placed and coordinated across groups.

Targets use the typed ``PlanTarget`` model to unambiguously specify whether
a placement targets an individual group, a display zone, or a split
partition.  The composition engine expands zone/split targets to concrete
group IDs at render time.
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
    TargetType,
)


class PlanTarget(BaseModel):
    """Typed target for choreography coordination.

    Enables the LLM to target groups, zones, or splits without
    ambiguity.  The composition engine expands zone/split targets
    to concrete group IDs at render time.

    Examples::

        PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
        PlanTarget(type=TargetType.ZONE, id="HOUSE")
        PlanTarget(type=TargetType.SPLIT, id="HALVES_LEFT")

    Attributes:
        type: Target type discriminator (group, zone, split).
        id: Target identifier.  Interpretation depends on ``type``:
            - group: ``ChoreoGroup.id`` (e.g., ``"ARCHES"``).
            - zone: ``ChoreoTag`` value (e.g., ``"HOUSE"``).
            - split: ``SplitDimension`` value (e.g., ``"HALVES_LEFT"``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: TargetType
    id: str = Field(min_length=1)


class GroupPlacement(BaseModel):
    """Individual placement of a template on a target.

    Uses categorical planning values:
    - PlanningTimeRef for start timing (bar + beat only)
    - EffectDuration for duration (categorical, renderer calculates end)
    - IntensityLevel for intensity (categorical, renderer resolves to numeric)

    The ``target`` field specifies what this placement targets.
    After target expansion, ``target.type`` is always ``GROUP`` and
    ``target.id`` is the concrete ``ChoreoGroup.id``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    placement_id: str
    target: PlanTarget
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
    ``group_order`` may be empty when using zone/split targets — the
    target expansion engine populates it using spatial sorting.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_order: list[str] = Field(default_factory=list)
    step_unit: StepUnit = StepUnit.BEAT
    step_duration: int = Field(default=1, ge=1)
    phase_offset: float = Field(default=0.0, ge=0.0, le=1.0)
    spill_policy: SpillPolicy = SpillPolicy.TRUNCATE
    spatial_intent: SpatialIntent = SpatialIntent.NONE


class CoordinationPlan(BaseModel):
    """Coordination plan for a set of targets within a lane.

    Targets can be individual groups, zones, or splits.  The
    composition engine resolves zone/split targets to concrete
    group IDs via :class:`TargetExpander` before rendering.

    For UNIFIED/COMPLEMENTARY: placements are provided directly.
    For SEQUENCED/CALL_RESPONSE/RIPPLE: window + config provided, Assembler expands.
    """

    model_config = ConfigDict(extra="forbid")

    coordination_mode: CoordinationMode

    # Typed targets — sole source of truth for what this plan targets
    targets: list[PlanTarget] = Field(min_length=1)

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
    "PlanTarget",
]
