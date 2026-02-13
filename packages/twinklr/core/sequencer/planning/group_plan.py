"""Group planning output models.

Models for GroupPlanner agent output - section coordination plans,
narrative asset directives, and aggregated plan sets. These represent
what the GroupPlanner agent produces, not template definitions.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import CoordinationPlan
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import GPBlendMode, GPTimingDriver, LaneKind


class NarrativeAssetDirective(BaseModel):
    """A directive for a figurative/narrative asset to be created.

    Produced by the group planner per section alongside coordination plans.
    Each directive describes a concrete visual subject (not an abstract pattern).
    Directives are section-scoped: each section declares what imagery it needs.
    The aggregator deduplicates across sections by directive_id.

    Metadata is song-agnostic to allow future cross-song reuse and
    semantic similarity matching in the asset catalog.

    Attributes:
        directive_id: Semantic slug for this directive (e.g. "rudolph_glowing_nose").
        subject: What to depict — concrete visual subject description.
        category: IMAGE_CUTOUT for characters/objects, IMAGE_TEXTURE for scenes.
        visual_description: Rich visual description (2-4 sentences), LED-optimized.
        story_context: Why this asset matters to the section's narrative moment.
        emphasis: How prominent in this section (LOW, MED, HIGH).
        color_guidance: Optional palette/color hints from the narrative.
        mood: Optional emotional tone (warm, cold, triumphant, lonely).
        section_ids: Populated by aggregator — which sections reference this directive.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    directive_id: str = Field(min_length=1)
    subject: str = Field(min_length=5, description="What to depict")
    category: str = Field(
        min_length=1,
        description="Asset category: 'image_cutout' or 'image_texture'",
    )
    visual_description: str = Field(
        min_length=10,
        description="Rich visual description, LED-optimized (2-4 sentences)",
    )
    story_context: str = Field(
        min_length=5,
        description="Why this asset matters to the narrative moment",
    )
    emphasis: str = Field(
        default="MED",
        description="Prominence: LOW, MED, or HIGH",
    )
    color_guidance: str | None = Field(
        default=None,
        description="Palette/color hints from the narrative",
    )
    mood: str | None = Field(
        default=None,
        description="Emotional tone (warm, cold, triumphant, lonely, etc.)",
    )
    # Populated by aggregator — empty in per-section output
    section_ids: list[str] = Field(
        default_factory=list,
        description="Sections referencing this directive (set by aggregator)",
    )


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

    The ``start_ms`` and ``end_ms`` fields are NOT produced by the LLM —
    they are populated by the pipeline from the audio profile's section
    timing data, providing concrete section boundaries for the renderer.
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

    # Narrative asset directives for this section (per-section, ≤10)
    narrative_assets: list[NarrativeAssetDirective] = Field(default_factory=list)

    # Optional notes for debugging/tracing
    planning_notes: str | None = None

    # Section timing — populated by pipeline from audio profile, NOT by LLM
    start_ms: int | None = Field(
        default=None,
        ge=0,
        description="Section start time in ms (from audio profile, not LLM)",
    )
    end_ms: int | None = Field(
        default=None,
        gt=0,
        description="Section end time in ms (from audio profile, not LLM)",
    )


class GroupPlanSet(BaseModel):
    """Aggregated coordination plans for all sections.

    This is the final output of the GroupPlanner orchestration.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group-plan-set.v1"
    plan_set_id: str

    section_plans: list[SectionCoordinationPlan] = Field(min_length=1)

    # Aggregated + deduplicated narrative asset directives across all sections
    narrative_assets: list[NarrativeAssetDirective] = Field(default_factory=list)

    # Holistic evaluation result (populated after holistic judge)
    # holistic_evaluation: HolisticEvaluation | None = None  # Added in Phase 3


__all__ = [
    "Deviation",
    "GroupPlanSet",
    "LanePlan",
    "NarrativeAssetDirective",
    "SectionCoordinationPlan",
]
