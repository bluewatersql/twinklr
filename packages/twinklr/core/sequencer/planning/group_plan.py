"""Group planning output models.

Models for GroupPlanner agent output - section coordination plans,
narrative asset directives, and aggregated plan sets. These represent
what the GroupPlanner agent produces, not template definitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GPBlendMode,
    GPTimingDriver,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    SpatialIntent,
    SpillPolicy,
    StepUnit,
)

if TYPE_CHECKING:
    # Runtime import would create a circular dependency: holistic.py imports
    # GroupPlanSet from this module. Deferred here; model_rebuild() resolves the
    # forward reference (see P0-T3 escalation — a bulk TC004 fix broke this at
    # import time).
    from twinklr.core.agents.sequencer.group_planner.holistic import (  # noqa: TC004
        HolisticEvaluation,
    )


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


class CorrectionResult(BaseModel):
    """Result of holistic correction -- only modified sections.

    The corrector returns ONLY the sections it changed, not the entire
    plan set.  The corrector stage splices these back into the original
    GroupPlanSet by matching ``section_id``.
    """

    model_config = ConfigDict(extra="forbid")

    corrected_sections: list[SectionCoordinationPlan] = Field(min_length=1)


class ParameterOverrideEntry(BaseModel):
    """Compatibility constructor for one template parameter override.

    Strict response DTOs use parallel key/value arrays to stay within OpenAI's
    ten-level schema-depth ceiling. This model remains available to deterministic
    callers, but is not nested in the provider schema.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1)
    value: str | int | float | bool | None


class GroupPlacementResponse(BaseModel):
    """Strict LLM form of a group placement (framework asset IDs excluded)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    placement_id: str
    target: PlanTarget
    template_id: str
    start: PlanningTimeRef
    duration: EffectDuration
    param_override_keys: list[str]
    param_overrides: list[str | int | float | bool | None]
    intensity: IntensityLevel

    @model_validator(mode="after")
    def validate_override_lengths(self) -> GroupPlacementResponse:
        """Keep the parallel strict arrays losslessly pairable."""
        if len(self.param_override_keys) != len(self.param_overrides):
            raise ValueError("param_override_keys and param_overrides must have equal length")
        return self

    def to_domain(self) -> GroupPlacement:
        """Convert to the renderer-facing domain model."""
        return GroupPlacement(
            placement_id=self.placement_id,
            target=self.target,
            template_id=self.template_id,
            start=self.start,
            duration=self.duration,
            param_overrides=dict(zip(self.param_override_keys, self.param_overrides, strict=True)),
            intensity=self.intensity,
            resolved_asset_ids=[],
        )


class PlacementWindowResponse(BaseModel):
    """Strict LLM form of a sequenced placement window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: PlanningTimeRef
    end: PlanningTimeRef
    template_id: str
    param_override_keys: list[str]
    param_overrides: list[str | int | float | bool | None]
    intensity: IntensityLevel

    @model_validator(mode="after")
    def validate_override_lengths(self) -> PlacementWindowResponse:
        """Keep the parallel strict arrays losslessly pairable."""
        if len(self.param_override_keys) != len(self.param_overrides):
            raise ValueError("param_override_keys and param_overrides must have equal length")
        return self

    def to_domain(self) -> PlacementWindow:
        return PlacementWindow(
            start=self.start,
            end=self.end,
            template_id=self.template_id,
            param_overrides=dict(zip(self.param_override_keys, self.param_overrides, strict=True)),
            intensity=self.intensity,
        )


class CoordinationConfigResponse(BaseModel):
    """Strict LLM form of deterministic coordination configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_order: list[str]
    step_unit: StepUnit
    step_duration: int = Field(ge=1)
    phase_offset: float = Field(ge=0.0, le=1.0)
    spill_policy: SpillPolicy
    spatial_intent: SpatialIntent

    def to_domain(self) -> CoordinationConfig:
        return CoordinationConfig(**self.model_dump())


class CoordinationPlanResponse(BaseModel):
    """Strict LLM form of a coordination plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coordination_mode: CoordinationMode
    targets: list[PlanTarget] = Field(min_length=1)
    placements: list[GroupPlacementResponse]
    window: PlacementWindowResponse | None
    config: CoordinationConfigResponse | None

    def to_domain(self) -> CoordinationPlan:
        return CoordinationPlan(
            coordination_mode=self.coordination_mode,
            targets=self.targets,
            placements=[placement.to_domain() for placement in self.placements],
            window=self.window.to_domain() if self.window is not None else None,
            config=self.config.to_domain() if self.config is not None else None,
        )


class LanePlanResponse(BaseModel):
    """Strict LLM form of one display lane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: LaneKind
    target_roles: list[str] = Field(min_length=1)
    timing_driver: GPTimingDriver
    blend_mode: GPBlendMode
    coordination_plans: list[CoordinationPlanResponse]

    def to_domain(self) -> LanePlan:
        return LanePlan(
            lane=self.lane,
            target_roles=self.target_roles,
            timing_driver=self.timing_driver,
            blend_mode=self.blend_mode,
            coordination_plans=[plan.to_domain() for plan in self.coordination_plans],
        )


class DeviationResponse(BaseModel):
    """Strict LLM form of a documented macro-plan deviation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deviation_id: str
    intent_field: str
    reason: str
    mitigation: str | None

    def to_domain(self) -> Deviation:
        return Deviation(**self.model_dump())


class NarrativeAssetDirectiveResponse(BaseModel):
    """Strict LLM form of a narrative asset (aggregator fields excluded)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    directive_id: str = Field(min_length=1)
    subject: str = Field(min_length=5)
    category: str = Field(min_length=1)
    visual_description: str = Field(min_length=10)
    story_context: str = Field(min_length=5)
    emphasis: str
    color_guidance: str | None
    mood: str | None

    def to_domain(self) -> NarrativeAssetDirective:
        return NarrativeAssetDirective(**self.model_dump(), section_ids=[])


class SectionCoordinationResponse(BaseModel):
    """Strict LLM response for one section coordination plan.

    Framework-populated ``schema_version``, ``start_ms``, ``end_ms`` and
    narrative ``section_ids`` do not appear in this contract.  The adapter adds
    them only after strict server-side validation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    theme: ThemeRef
    motif_ids: list[str]
    palette: PaletteRef | None
    lane_plans: list[LanePlanResponse] = Field(min_length=1)
    deviations: list[DeviationResponse]
    narrative_assets: list[NarrativeAssetDirectiveResponse]
    planning_notes: str | None

    def to_domain(self) -> SectionCoordinationPlan:
        return SectionCoordinationPlan(
            section_id=self.section_id,
            theme=self.theme,
            motif_ids=self.motif_ids,
            palette=self.palette,
            lane_plans=[lane.to_domain() for lane in self.lane_plans],
            deviations=[deviation.to_domain() for deviation in self.deviations],
            narrative_assets=[asset.to_domain() for asset in self.narrative_assets],
            planning_notes=self.planning_notes,
            start_ms=None,
            end_ms=None,
        )


class CorrectionResponse(BaseModel):
    """Strict LLM response containing only corrected section contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corrected_sections: list[SectionCoordinationResponse] = Field(min_length=1)

    def to_domain(self) -> CorrectionResult:
        return CorrectionResult(
            corrected_sections=[section.to_domain() for section in self.corrected_sections]
        )


def adapt_section_coordination_response(
    value: SectionCoordinationResponse,
) -> SectionCoordinationPlan:
    """AgentSpec response adapter for group-planner output."""
    return value.to_domain()


def adapt_correction_response(value: CorrectionResponse) -> CorrectionResult:
    """AgentSpec response adapter for corrector output."""
    return value.to_domain()


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

    holistic_evaluation: HolisticEvaluation | None = Field(
        default=None,
        description="Cross-section quality evaluation (populated by holistic stage)",
    )


__all__ = [
    "CoordinationConfigResponse",
    "CoordinationPlanResponse",
    "CorrectionResponse",
    "CorrectionResult",
    "Deviation",
    "DeviationResponse",
    "GroupPlacementResponse",
    "GroupPlanSet",
    "LanePlan",
    "LanePlanResponse",
    "NarrativeAssetDirective",
    "NarrativeAssetDirectiveResponse",
    "ParameterOverrideEntry",
    "PlacementWindowResponse",
    "SectionCoordinationPlan",
    "SectionCoordinationResponse",
    "adapt_correction_response",
    "adapt_section_coordination_response",
]
