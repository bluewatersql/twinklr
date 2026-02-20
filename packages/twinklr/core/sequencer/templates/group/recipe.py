"""EffectRecipe — multi-layer composite effect specification.

Modeled on xLights .xpreset files, an EffectRecipe defines a complete
multi-layer visual effect that is directly renderable by the pipeline.

Each recipe specifies one or more RecipeLayers with blend modes, mix levels,
and effect-specific parameters (static or dynamic).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    VisualDepth,
)


class ColorSource(str):
    """Color source for a recipe layer.

    Determines where a layer gets its colors from.
    """

    PALETTE_PRIMARY = "palette_primary"
    PALETTE_ACCENT = "palette_accent"
    EXPLICIT = "explicit"
    WHITE_ONLY = "white_only"


class ParamValue(BaseModel):
    """Effect parameter value — static or dynamic.

    Static: value is set directly.
    Dynamic: expr is an expression evaluated at render time, bounded by min/max.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Any | None = Field(default=None, description="Static parameter value")
    expr: str | None = Field(
        default=None,
        description="Dynamic expression (e.g., 'energy * 0.8')",
    )
    min_val: float | None = Field(default=None, description="Minimum bound for dynamic expr")
    max_val: float | None = Field(default=None, description="Maximum bound for dynamic expr")


class PaletteSpec(BaseModel):
    """Color palette specification for a recipe.

    Defines the color strategy and which palette roles are needed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ColorMode = Field(description="Color mode (MONOCHROME, DICHROME, TRIAD, etc.)")
    palette_roles: list[str] = Field(
        description="Palette roles needed (e.g., ['primary', 'accent'])"
    )


class RecipeLayer(BaseModel):
    """Single layer in a multi-layer recipe composition.

    Defines effect type, blend mode, mix level, and parameters
    for one layer of the composite effect.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer_index: int = Field(ge=0, description="Render order (0 = bottom)")
    layer_name: str = Field(description="Human-readable layer name")
    layer_depth: VisualDepth = Field(description="Visual depth role")
    effect_type: str = Field(description="xLights effect type name")
    blend_mode: BlendMode = Field(description="Layer blending strategy")
    mix: float = Field(ge=0.0, le=1.0, description="Mix level (0.0-1.0)")
    params: dict[str, ParamValue] = Field(
        default_factory=dict,
        description="Effect-specific parameters",
    )
    motion: list[MotionVerb] = Field(
        default_factory=list,
        description="Motion verbs applied to this layer",
    )
    density: float = Field(ge=0.0, le=1.0, description="Visual density (0.0-1.0)")
    color_source: str = Field(
        default=ColorSource.PALETTE_PRIMARY,
        description="Color source for this layer",
    )
    timing_offset_beats: float | None = Field(
        default=None,
        description="Timing offset in beats from layer 0",
    )


class ModelAffinity(BaseModel):
    """Model type affinity score for a recipe.

    Indicates how well-suited this recipe is for a particular
    display model type (e.g., megatree, arch, matrix).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_type: str = Field(description="Display model type")
    score: float = Field(ge=0.0, le=1.0, description="Affinity score (0.0-1.0)")


class RecipeProvenance(BaseModel):
    """Provenance tracking for a recipe.

    Records where a recipe came from and its curation history.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["builtin", "mined", "curated", "generated"] = Field(
        description="Origin of this recipe"
    )
    mined_template_ids: list[str] = Field(
        default_factory=list,
        description="FE template UUIDs this recipe was derived from",
    )
    curator_notes: str | None = Field(
        default=None,
        description="Notes from human curation",
    )


class StyleMarkers(BaseModel):
    """Style metadata for recipe matching and filtering.

    Used by the planner to select recipes that match the section's
    energy, complexity, and style requirements.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    complexity: float = Field(
        ge=0.0,
        le=1.0,
        description="Recipe complexity (0=simple, 1=complex)",
    )
    energy_affinity: EnergyTarget = Field(
        description="Energy level this recipe is best suited for",
    )


class MotifCompatibility(BaseModel):
    """Motif compatibility score for a recipe.

    Indicates how well this recipe supports a particular motif
    (e.g., "grid", "light_trails", "wave_cascade").
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    motif_id: str = Field(description="Motif identifier")
    score: float = Field(ge=0.0, le=1.0, description="Compatibility score")
    reason: str = Field(default="", description="Why this motif matches")


class EffectRecipe(BaseModel):
    """Multi-layer composite effect specification.

    The central abstraction for renderable effects, inspired by xLights
    .xpreset files. An EffectRecipe is directly renderable by the pipeline
    and supports multi-layer composition with blend modes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity
    recipe_id: str = Field(description="Human-readable recipe identifier")
    name: str = Field(description="Display name")
    description: str = Field(description="Recipe description")
    recipe_version: str = Field(description="Semantic version")

    # Classification
    template_type: GroupTemplateType = Field(description="Template type (BASE, RHYTHM, ACCENT)")
    visual_intent: GroupVisualIntent = Field(description="Visual intent classification")
    tags: list[str] = Field(default_factory=list, description="Searchable tags")

    # Timing
    timing: TimingHints = Field(description="Timing guidance for usage")

    # Color
    palette_spec: PaletteSpec = Field(description="Color palette specification")

    # Layers (core composite structure)
    layers: tuple[RecipeLayer, ...] = Field(description="Ordered recipe layers")

    # Provenance
    provenance: RecipeProvenance = Field(description="Origin and curation history")

    # Optional enrichment
    model_affinities: list[ModelAffinity] = Field(
        default_factory=list,
        description="Model type affinity scores",
    )
    style_markers: StyleMarkers | None = Field(
        default=None,
        description="Style metadata for matching",
    )
    motif_compatibility: list[MotifCompatibility] = Field(
        default_factory=list,
        description="Motif compatibility scores",
    )
