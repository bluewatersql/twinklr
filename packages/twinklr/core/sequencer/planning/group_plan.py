"""Group planning output models.

Models for GroupPlanner agent output - section coordination plans
and aggregated plan sets. These represent what the GroupPlanner
agent produces, not template definitions.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.templates.group.models.coordination import CoordinationPlan
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import GPBlendMode, GPTimingDriver, LaneKind


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
    motif_ids: list[str] = Field(default_factory=list)
    palette: PaletteRef | None = Field(
        default=None,
        description="Optional palette override for this section; if None use global primary",
    )

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
    "Deviation",
    "GroupPlanSet",
    "LanePlan",
    "SectionCoordinationPlan",
]
