"""Group template definition models.

Core models for defining group choreography templates.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.templates.assets.models import AssetRequest
from twinklr.core.sequencer.vocabulary import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    ProjectionIntent,
    VisualDepth,
    WarpHint,
)

# Alias for backward compatibility in templates
LayerRole = VisualDepth


class TimingHints(BaseModel):
    """Loose timing guidance for template usage.

    Planner may override these hints based on musical context.

    Attributes:
        bars_min: Minimum recommended bars for this template.
        bars_max: Maximum recommended bars for this template.
        beats_per_bar: Expected beats per bar (e.g., 4 for 4/4 time).
        loop_len_ms: Optional loop length in milliseconds.
        emphasize_downbeats: Whether to emphasize downbeats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    bars_min: int | None = Field(default=None, ge=1, le=256)
    bars_max: int | None = Field(default=None, ge=1, le=256)
    beats_per_bar: int | None = Field(default=None, ge=1, le=12)
    loop_len_ms: int | None = Field(default=None, gt=0)
    emphasize_downbeats: bool = True

    @model_validator(mode="after")
    def _validate_bar_range(self) -> TimingHints:
        """Validate bars_min <= bars_max if both specified."""
        if (
            self.bars_min is not None
            and self.bars_max is not None
            and self.bars_min > self.bars_max
        ):
            raise ValueError(f"bars_min ({self.bars_min}) must be <= bars_max ({self.bars_max})")
        return self


class GroupConstraints(BaseModel):
    """Aesthetic and technical constraints for template.

    Attributes:
        no_text: Prohibit text/letters in visual content.
        low_detail: Prefer low-detail, high-contrast visuals.
        high_contrast: Require high-contrast visuals.
        clean_edges: Require clean, crisp edges (no blur).
        seam_safe_required: Content must tile seamlessly.
        avoid_edges_for_subject: Keep focal subjects away from edges.
        max_layers: Maximum number of composited layers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    no_text: bool = True
    low_detail: bool = True
    high_contrast: bool = True
    clean_edges: bool = True
    seam_safe_required: bool = False
    avoid_edges_for_subject: bool = False
    max_layers: int = Field(default=3, ge=1, le=6)


class ProjectionParams(BaseModel):
    """Projection mapping parameters.

    Attributes:
        center_x: Horizontal center point (0.0 = left, 1.0 = right).
        center_y: Vertical center point (0.0 = bottom, 1.0 = top).
        angle_offset_deg: Rotation offset in degrees.
        radius_bias: Radial distance bias (0.0 = center, 1.0 = edge).
        seam_safe: Whether content tiles seamlessly at polar seam.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    angle_offset_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    radius_bias: float = Field(default=0.5, ge=0.0, le=1.0)
    seam_safe: bool = False


class ProjectionSpec(BaseModel):
    """Complete projection specification.

    Attributes:
        intent: Projection mapping intent.
        params: Optional projection parameters.
        warp_hints: List of warp hints for special requirements.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: ProjectionIntent
    params: ProjectionParams | None = None
    warp_hints: list[WarpHint] = Field(default_factory=list)


class LayerRecipe(BaseModel):
    """Layer composition recipe.

    Defines a single layer in the template's visual composition.

    Attributes:
        layer: Layer role (depth/ordering).
        motifs: List of visual motifs (e.g., ["stars", "sparkles"]).
        visual_intent: Visual intent classification.
        motion: List of motion verbs applied to this layer.
        density: Visual density (0.0 = sparse, 1.0 = dense).
        contrast: Contrast level (0.0 = low, 1.0 = high).
        color_mode: Color strategy for this layer.
        notes: Optional notes for template authors.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: LayerRole
    motifs: list[str] = Field(default_factory=list)
    visual_intent: GroupVisualIntent
    motion: list[MotionVerb] = Field(default_factory=lambda: [MotionVerb.NONE])
    density: float = Field(ge=0.0, le=1.0)
    contrast: float = Field(ge=0.0, le=1.0)
    color_mode: ColorMode
    notes: str | None = None


class AssetSlotDefaults(BaseModel):
    """Asset generation defaults for slot.

    Attributes:
        background: Background mode (transparent or opaque).
        aspect: Aspect ratio for generated asset.
        base_size: Base size in pixels (e.g., 256, 512).
        even_dimensions: Whether dimensions must be even numbers.
        seam_safe: Whether asset must tile seamlessly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    background: Literal["transparent", "opaque"] = "transparent"
    aspect: Literal["1:1", "2:1", "1:2", "16:9", "4:3"] = "1:1"
    base_size: int = Field(default=256, gt=0)
    even_dimensions: bool = True
    seam_safe: bool = False


class AssetSlot(BaseModel):
    """Asset requirement slot.

    Defines a required or optional asset for this template.

    Attributes:
        slot_id: Unique identifier for this slot.
        slot_type: Type of asset required.
        required: Whether this asset is required.
        preferred_tags: Tags for future asset matching.
        prompt_hint: Hint for LLM-guided asset selection.
        defaults: Asset generation defaults.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    slot_type: AssetSlotType
    required: bool = True
    preferred_tags: list[str] = Field(default_factory=list)
    prompt_hint: str | None = None
    defaults: AssetSlotDefaults = Field(default_factory=AssetSlotDefaults)


class GroupPlanTemplate(BaseModel):
    """Complete group choreography template.

    Top-level model for group templates. Defines high-level cross-group
    coordination patterns for Christmas light displays.

    Attributes:
        schema_version: Schema version identifier.
        template_id: Unique template identifier (lowercase, alphanumeric).
        name: Human-readable template name.
        description: Template description.
        template_type: Template type (lane classification).
        visual_intent: Visual intent classification.
        tags: List of tags for categorization.
        projection: Projection specification.
        timing: Timing hints for template usage.
        constraints: Aesthetic and technical constraints.
        layer_recipe: List of layer recipes for composition.
        asset_slots: List of asset requirement slots.
        template_version: Template version string.
        author: Optional template author.
        extras: Extra data (extension point).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["group_plan_template.v1"] = "group_plan_template.v1"
    template_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str = Field(min_length=1)
    description: str = Field(default="")
    template_type: GroupTemplateType
    visual_intent: GroupVisualIntent
    tags: list[str] = Field(default_factory=list)

    projection: ProjectionSpec
    timing: TimingHints = Field(default_factory=TimingHints)
    constraints: GroupConstraints = Field(default_factory=GroupConstraints)
    layer_recipe: list[LayerRecipe] = Field(default_factory=list)
    asset_slots: list[AssetSlot] = Field(default_factory=list)

    template_version: str = "1.0.0"
    author: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)

    affinity_tags: list[str] = []
    avoid_tags: list[str] = []

    @model_validator(mode="after")
    def _validate_constraints(self) -> GroupPlanTemplate:
        """Validate cross-field constraints."""
        # Validate max_layers >= len(layer_recipe)
        if len(self.layer_recipe) > self.constraints.max_layers:
            raise ValueError(
                f"layer_recipe count ({len(self.layer_recipe)}) exceeds "
                f"constraints.max_layers ({self.constraints.max_layers})"
            )

        # Validate seam_safe consistency
        if self.constraints.seam_safe_required:
            has_seam_safe = WarpHint.SEAM_SAFE in self.projection.warp_hints or (
                self.projection.params and self.projection.params.seam_safe
            )
            if not has_seam_safe:
                raise ValueError(
                    "constraints.seam_safe_required=True but projection lacks seam-safe hints"
                )

        # Validate unique slot_ids
        slot_ids = [s.slot_id for s in self.asset_slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("Duplicate slot_id in asset_slots")

        # Dedupe and normalize tags
        self.tags = sorted({tag.strip().lower() for tag in self.tags if tag.strip()})

        return self


# Re-export AssetRequest for backward compatibility (imported from assets.models)
__all__ = [
    "AssetRequest",
    "AssetSlot",
    "AssetSlotDefaults",
    "GroupConstraints",
    "GroupPlanTemplate",
    "LayerRecipe",
    "ProjectionParams",
    "ProjectionSpec",
    "TimingHints",
]
