"""Coordination models for group template placement.

Models for group placement, coordination configuration, and coordination plans.
These define how templates are placed and coordinated across groups.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
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


__all__ = [
    "CoordinationConfig",
    "CoordinationPlan",
    "GroupPlacement",
    "PlacementWindow",
]
