"""Planning models - macro-level choreography planning.

Models for strategic planning at the macro (song/section) level.
"""

from pydantic import BaseModel, Field, field_validator

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ChoreographyStyle,
    EnergyTarget,
    LayerRole,
    MotionDensity,
    TimingDriver,
)
from twinklr.core.sequencer.vocabulary.visual import PaletteRole


class PaletteRef(BaseModel):
    model_config = {"extra": "forbid"}

    palette_id: str = Field(..., description="Palette ID")

    role: PaletteRole | None = Field(
        default=None,
        description="Optional usage role (e.g. PRIMARY, ACCENT, WARM, COOL)",
    )
    intensity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional global intensity scaler for this palette usage",
    )
    variant: str | None = Field(
        default=None,
        description="Optional palette variant key (e.g. 'a', 'b', 'night', 'day')",
    )


class PalettePlan(BaseModel):
    model_config = {"extra": "forbid"}

    # Primary palette for the show
    primary: PaletteRef = Field(..., description="Default palette for the song")

    # Optional alternates allowed for variation (still theme-consistent)
    alternates: list[PaletteRef] = Field(default_factory=list, max_length=6)

    # Simple transition intent (kept minimal but structured)
    transition_notes: str = Field(
        default="",
        description="Rules for when/how to shift palette usage across song/sections",
    )


class MotifSpec(BaseModel):
    model_config = {"extra": "forbid"}

    motif_id: str = Field(..., description="Stable id e.g. 'candy_cane_swirl'")
    tags: list[str] = Field(default_factory=list, max_length=8)  # used for template matching
    description: str = Field(..., min_length=10, max_length=300)

    # Optional: where it should appear
    preferred_energy: list[EnergyTarget] = Field(default_factory=list)
    usage_notes: str = Field(default="", max_length=500)


class GlobalStory(BaseModel):
    """Global story arc for entire sequence.

    Defines the overarching theme, recurring motifs, pacing strategy,
    and color palette for the complete Christmas light show.
    """

    model_config = {"extra": "forbid"}

    theme: ThemeRef = Field(..., description="Global default theme reference for the song")
    story_notes: str = Field(
        ..., description="Overarching narrative/theme notes (prose)", min_length=10
    )
    motifs: list[MotifSpec] = Field(
        ...,
        description="3-5 recurring visual/musical motifs throughout the show",
        min_length=3,
        max_length=10,
    )
    pacing_notes: str = Field(
        ..., description="How energy builds/releases across the song", min_length=20
    )
    palette_plan: PalettePlan = Field(
        ..., description="Global palette plan with primary and optional alternates"
    )

    @field_validator("theme")
    @classmethod
    def validate_theme_scope(cls, v: ThemeRef) -> ThemeRef:
        # GlobalStory theme must always be SONG scoped
        if v.scope != ThemeScope.SONG:
            raise ValueError("GlobalStory.theme.scope must be ThemeScope.SONG")
        # keep global tags tight
        if len(v.tags) > 5:
            raise ValueError("GlobalStory.theme.tags must have at most 5 items")

        if len(set(v.tags)) != len(v.tags):
            raise ValueError("GlobalStory.theme.tags must not contain duplicates")

        return v


class MacroSectionPlan(BaseModel):
    """Strategic plan for one song section.

    Defines energy target, choreography style, motion density, and target
    selection for a single section of the song.
    """

    model_config = {"extra": "forbid"}

    section: SongSectionRef = Field(..., description="Reference to audio section")
    theme: ThemeRef = Field(..., description="Section theme reference")
    energy_target: EnergyTarget = Field(..., description="Target energy level for section")
    primary_focus_targets: list[PlanTarget] = Field(
        ...,
        description=(
            "Main display targets for section intent using typed targets "
            "(group/zone/split). At least one target is required."
        ),
        min_length=1,
        max_length=8,
    )
    secondary_targets: list[PlanTarget] = Field(
        default_factory=list,
        description="Supporting typed targets (group/zone/split)",
        max_length=12,
    )
    choreography_style: ChoreographyStyle = Field(
        ..., description="Visual approach (IMAGERY, ABSTRACT, HYBRID)"
    )

    palette: PaletteRef | None = Field(
        default=None,
        description="Optional palette override for this section; if None use global primary",
    )

    motif_ids: list[str] = Field(
        default_factory=list,
        description="Motifs to emphasize in this section (references GlobalStory.motifs[*].motif_id)",
        max_length=5,
    )

    motion_density: MotionDensity = Field(..., description="Activity level (SPARSE, MED, BUSY)")
    notes: str = Field(..., description="Strategic notes for this section", min_length=20)

    @field_validator("primary_focus_targets", "secondary_targets")
    @classmethod
    def validate_focus_targets(cls, v: list[PlanTarget]) -> list[PlanTarget]:
        """Validate typed focus targets are unique by (type,id)."""
        seen: set[tuple[str, str]] = set()
        for target in v:
            key = (target.type.value, target.id)
            if key in seen:
                raise ValueError(f"Duplicate focus target: {target.type.value}:{target.id}")
            seen.add(key)
        return v

    @field_validator("theme")
    @classmethod
    def validate_section_theme_scope(cls, v: ThemeRef) -> ThemeRef:
        if v.scope != ThemeScope.SECTION:
            raise ValueError("MacroSectionPlan.theme.scope must be ThemeScope.SECTION")
        if len(v.tags) > 5:
            raise ValueError("MacroSectionPlan.theme.tags must have at most 5 items")
        if len(set(v.tags)) != len(v.tags):
            raise ValueError("MacroSectionPlan.theme.tags must not contain duplicates")
        return v


class TargetSelector(BaseModel):
    """Defines which targets a layer should affect.

    Supports multiple targets for coordinated impact (not 1:1).
    """

    model_config = {"extra": "forbid"}

    roles: list[str] = Field(
        ...,
        description="Concrete display group IDs (e.g. OUTLINE, MEGA_TREE, WREATHS, MATRIX)",
        min_length=1,
        max_length=10,
    )
    coordination: str = Field(
        default="unified",
        description="How targets work together (unified, complementary, independent)",
    )

    @field_validator("roles")
    @classmethod
    def validate_roles_non_empty(cls, v: list[str]) -> list[str]:
        """Validate role ids are non-empty strings."""
        cleaned = [role.strip() for role in v if role and role.strip()]
        if len(cleaned) != len(v):
            raise ValueError("roles must not contain empty values")
        return cleaned


class LayerSpec(BaseModel):
    """Specification for a single layer in composition.

    Defines the role, targets, blend mode, timing, and intensity for one
    layer in the choreography architecture.
    """

    model_config = {"extra": "forbid"}

    layer_index: int = Field(..., ge=0, le=4, description="Layer index (0-4, lower = back)")
    layer_role: LayerRole = Field(
        ..., description="Layer role (BASE, RHYTHM, ACCENT, FILL, TEXTURE)"
    )
    target_selector: TargetSelector = Field(
        ..., description="Which display groups this layer affects"
    )
    blend_mode: BlendMode = Field(..., description="How layer combines with others (NORMAL, ADD)")
    timing_driver: TimingDriver = Field(..., description="Musical timing this layer follows")
    intensity_bias: float = Field(
        default=1.0, ge=0.0, le=1.5, description="Global intensity multiplier for this layer"
    )
    usage_notes: str = Field(..., description="Strategic guidance for GroupPlanner", min_length=10)


class LayeringPlan(BaseModel):
    """Complete layering architecture for the sequence.

    Validates the collection of layers with composition rules:
    - Exactly one BASE layer required
    - No duplicate layer indices
    - BASE layer must use NORMAL blend
    - 1-5 layers total
    """

    model_config = {"extra": "forbid"}

    layers: list[LayerSpec] = Field(
        ..., description="Layer specifications", min_length=1, max_length=5
    )
    strategy_notes: str = Field(..., description="High-level layering strategy", min_length=20)

    @field_validator("layers")
    @classmethod
    def validate_layer_composition(cls, v: list[LayerSpec]) -> list[LayerSpec]:
        """Validate layer composition rules."""
        # Check for exactly one BASE layer
        base_layers = [layer for layer in v if layer.layer_role == LayerRole.BASE]
        if len(base_layers) != 1:
            raise ValueError("Must have exactly one BASE layer")

        # Check for duplicate indices
        indices = [layer.layer_index for layer in v]
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate layer index found")

        # Validate BASE layer uses NORMAL blend
        base_layer = base_layers[0]
        if base_layer.blend_mode != BlendMode.NORMAL:
            raise ValueError("BASE layer must use NORMAL blend mode")

        return v


class MacroPlan(BaseModel):
    """Complete strategic plan for entire sequence.

    Root schema that ties together global story, layering architecture,
    per-section plans, and asset requirements.

    Validates:
    - No gaps or overlaps between sections
    - Sections sorted by start_ms
    - No duplicate section IDs
    """

    model_config = {"extra": "forbid"}

    global_story: GlobalStory = Field(..., description="Overarching theme and narrative")
    layering_plan: LayeringPlan = Field(..., description="Complete layering architecture")
    section_plans: list[MacroSectionPlan] = Field(
        ..., description="Per-section strategic plans", min_length=1
    )
    asset_requirements: list[str] = Field(
        default_factory=list,
        description="Required visual assets (PNG/GIF filenames)",
        max_length=50,
    )

    @field_validator("asset_requirements")
    @classmethod
    def validate_asset_requirements(cls, v: list[str]) -> list[str]:
        """Validate asset requirement filenames."""
        for asset in v:
            if len(asset) < 1:
                raise ValueError("Asset requirement must have at least 1 character")
        return v

    @field_validator("section_plans")
    @classmethod
    def validate_section_coverage(cls, v: list[MacroSectionPlan]) -> list[MacroSectionPlan]:
        """Validate section timing coverage.

        Ensures:
        - No duplicate section IDs
        - Sections sorted by start_ms
        - No gaps between sections
        - No overlaps between sections
        """
        if len(v) == 0:
            return v

        # Check for duplicate section IDs
        section_ids = [plan.section.section_id for plan in v]
        seen: set[str] = set()
        duplicates: list[str] = []
        for sid in section_ids:
            if sid in seen:
                duplicates.append(sid)
            seen.add(sid)
        if duplicates:
            raise ValueError(
                f"Duplicate section_id found: {duplicates}. "
                f"Each section_id must be unique (e.g., 'chorus_1', 'chorus_2', not 'chorus')."
            )

        # Check sections are sorted by start_ms
        start_times = [plan.section.start_ms for plan in v]
        if start_times != sorted(start_times):
            raise ValueError("Sections not sorted by start_ms")

        # Check for gaps and overlaps
        for i in range(len(v) - 1):
            current = v[i]
            next_section = v[i + 1]

            current_end = current.section.end_ms
            next_start = next_section.section.start_ms

            if current_end < next_start:
                raise ValueError(
                    f"Gap detected between sections '{current.section.section_id}' "
                    f"and '{next_section.section.section_id}': "
                    f"{current_end}ms to {next_start}ms"
                )
            elif current_end > next_start:
                raise ValueError(
                    f"Overlap detected between sections '{current.section.section_id}' "
                    f"and '{next_section.section.section_id}': "
                    f"current ends at {current_end}ms, next starts at {next_start}ms"
                )

        return v


__all__ = [
    "GlobalStory",
    "LayeringPlan",
    "LayerSpec",
    "MacroPlan",
    "MacroSectionPlan",
    "TargetSelector",
]
