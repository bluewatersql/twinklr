"""Group template models for GroupPlanner agent.

These templates express choreography/intent and section-level design patterns.
Templates can optionally declare AssetSlots that are later resolved by Asset Creation Agent.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from twinklr.core.agents.taxonomy import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
    WarpHint,
)


class BackgroundMode(str, enum.Enum):
    """Background mode for assets."""

    TRANSPARENT = "transparent"
    OPAQUE = "opaque"


class MatrixAspect(str, enum.Enum):
    """Matrix aspect ratio."""

    SQUARE_1_1 = "1:1"
    WIDE_2_1 = "2:1"
    TALL_1_2 = "1:2"


# Timing + constraints


class TimingHints(BaseModel):
    """Loose timing guidance for GroupPlanner.

    GroupPlanner may override based on song features.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bars_min: int | None = Field(default=None, ge=1, le=256)
    bars_max: int | None = Field(default=None, ge=1, le=256)
    beats_per_bar: int | None = Field(default=None, ge=1, le=12)
    loop_len_ms: PositiveInt | None = None
    emphasize_downbeats: bool = True


class GroupConstraints(BaseModel):
    """Constraints that GroupPlanner should honor while instantiating a plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    no_text: bool = True
    low_detail: bool = True
    high_contrast: bool = True
    clean_edges: bool = True

    # Tree/polar constraints
    seam_safe_required: bool = False
    avoid_edges_for_subject: bool = False

    # Linting constraints
    max_layers: int = Field(default=3, ge=1, le=6)


# Projection intent


class ProjectionParams(BaseModel):
    """Projection parameters for tree/matrix mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    angle_offset_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    radius_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    seam_safe: bool = False


class ProjectionSpec(BaseModel):
    """Projection specification for template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: ProjectionIntent = ProjectionIntent.FLAT
    params: ProjectionParams | None = None
    warp_hints: list[WarpHint] = Field(default_factory=list)


# Layer recipe


class LayerRecipe(BaseModel):
    """Layer recipe defining choreography for a layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: LayerRole
    motifs: list[str] = Field(
        default_factory=list, description="e.g., snowflakes, ornaments, wreath"
    )
    visual_intent: GroupVisualIntent = GroupVisualIntent.ABSTRACT
    motion: list[MotionVerb] = Field(default_factory=lambda: [MotionVerb.NONE])
    density: float = Field(default=0.5, ge=0.0, le=1.0)
    contrast: float = Field(default=0.8, ge=0.0, le=1.0)
    color_mode: ColorMode = ColorMode.TRADITIONAL
    notes: str | None = None


# Asset slot (optional) - later resolved to AssetSpec


class AssetSlotDefaults(BaseModel):
    """Default settings for asset slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    background: BackgroundMode = BackgroundMode.OPAQUE
    aspect: MatrixAspect = MatrixAspect.SQUARE_1_1
    base_size: PositiveInt = 256
    even_dimensions: bool = True
    seam_safe: bool = False


class AssetSlot(BaseModel):
    """Asset slot in template (later resolved to AssetRequest)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    slot_type: AssetSlotType
    required: bool = True
    preferred_tags: list[str] = Field(default_factory=list)
    prompt_hint: str | None = None
    defaults: AssetSlotDefaults = Field(default_factory=AssetSlotDefaults)


# Group plan template document


class GroupPlanTemplate(BaseModel):
    """Group plan template defining choreography intent and structure."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group_plan_template.v1"
    template_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str = Field(min_length=3)
    description: str = Field(default="")
    template_type: GroupTemplateType
    visual_intent: GroupVisualIntent
    tags: list[str] = Field(default_factory=list)
    projection: ProjectionSpec = Field(default_factory=ProjectionSpec)
    timing: TimingHints = Field(default_factory=TimingHints)
    constraints: GroupConstraints = Field(default_factory=GroupConstraints)
    layer_recipe: list[LayerRecipe] = Field(default_factory=list)
    asset_slots: list[AssetSlot] = Field(default_factory=list)
    template_version: str = "1.0.0"
    author: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class GroupTemplatePack(BaseModel):
    """Collection of group plan templates."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "group_template_pack.v1"
    pack_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str
    version: str = "1.0.0"
    templates: list[GroupPlanTemplate]
