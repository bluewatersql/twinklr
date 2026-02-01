"""Asset template models for Asset Creation Agent.

These templates produce prompts for PNG/GIF generation with matrix-safe constraints.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class TemplateType(str, enum.Enum):
    """Asset template type."""

    PROMPT_ONLY = "prompt_only"
    PNG_PROMPT = "png_prompt"
    GIF_FROM_PNG_OVERLAY = "gif_from_png_overlay"


class PromptStyle(str, enum.Enum):
    """Prompt style for asset generation."""

    LED_MATRIX_SAFE = "led_matrix_safe"
    FLAT_ILLUSTRATION = "flat_illustration"
    STORYBOOK = "storybook"
    PIXEL_ART = "pixel_art"
    SILHOUETTE = "silhouette"


class OverlayEffect(str, enum.Enum):
    """Procedural overlay effect for GIF generation."""

    NONE = "none"
    SNOW = "snow"
    TWINKLE = "twinkle"
    PULSE = "pulse"


class TemplateProjectionHint(str, enum.Enum):
    """Projection hint for asset templates."""

    AUTO = "auto"
    FLAT = "proj_flat"
    TREE_POLAR = "proj_tree_polar"
    TREE_RADIAL = "proj_tree_radial_focus"
    TREE_SPIRAL = "proj_tree_spiral_bias"
    TREE_BAND_SAFE = "proj_tree_band_safe"


class BackgroundMode(str, enum.Enum):
    """Background mode for assets."""

    TRANSPARENT = "transparent"
    OPAQUE = "opaque"


# Prompt template parts


class PromptParts(BaseModel):
    """Structured prompt parts for assembly.

    Prompt = preamble + subject + style_block + composition + constraints + output_intent
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    preamble: str = Field(default="")
    subject: str = Field(min_length=1)
    style_block: str = Field(default="")
    composition: str = Field(default="")
    background: str = Field(default="")
    lighting: str = Field(default="")
    constraints: str = Field(default="")
    output_intent: str = Field(default="")


class PromptPolicy(BaseModel):
    """Guardrails to keep outputs usable for LED matrices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    require_no_text: bool = True
    require_no_logos: bool = True
    require_no_watermarks: bool = True
    require_low_detail: bool = True
    require_high_contrast: bool = True
    require_clean_edges: bool = True
    require_seam_safe_when_tree: bool = True


# Default knobs for asset generation


class PngDefaults(BaseModel):
    """PNG generation defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    background: BackgroundMode = BackgroundMode.TRANSPARENT
    compression_level: int = Field(default=6, ge=0, le=9)
    optimize: bool = True


class GifDefaults(BaseModel):
    """GIF generation defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    duration_ms: PositiveInt = 2000
    fps: int = Field(default=12, ge=5, le=30)
    loop: bool = True
    overlay_effect: OverlayEffect = OverlayEffect.SNOW


class MatrixDefaults(BaseModel):
    """Matrix sizing defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_size: PositiveInt = 256
    aspect: Literal["1:1", "2:1", "1:2"] = "1:1"
    even_dimensions: bool = True


class ProjectionDefaults(BaseModel):
    """Projection defaults for asset templates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: TemplateProjectionHint = TemplateProjectionHint.AUTO
    seam_safe: bool = False
    center_x: float = Field(default=0.5, ge=0.0, le=1.0)
    center_y: float = Field(default=0.5, ge=0.0, le=1.0)
    angle_offset_deg: float = Field(default=0.0, ge=-180.0, le=180.0)
    radius_bias: float = Field(default=0.5, ge=0.0, le=1.0)


# Template document


class AssetTemplate(BaseModel):
    """Asset template for PNG/GIF generation with prompt assembly."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "asset_template.v1"
    template_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str = Field(min_length=3)
    description: str = Field(default="")
    template_type: TemplateType
    tags: list[str] = Field(default_factory=list)
    prompt_style: PromptStyle = PromptStyle.LED_MATRIX_SAFE
    prompt_parts: PromptParts
    prompt_policy: PromptPolicy = Field(default_factory=PromptPolicy)
    matrix_defaults: MatrixDefaults = Field(default_factory=MatrixDefaults)
    projection_defaults: ProjectionDefaults = Field(default_factory=ProjectionDefaults)
    png_defaults: PngDefaults | None = None
    gif_defaults: GifDefaults | None = None
    negative_hints: list[str] = Field(default_factory=list)
    author: str | None = None
    template_version: str = "1.0.0"


class AssetTemplatePack(BaseModel):
    """Collection of asset templates."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "asset_template_pack.v1"
    pack_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str
    version: str = "1.0.0"
    templates: list[AssetTemplate]
