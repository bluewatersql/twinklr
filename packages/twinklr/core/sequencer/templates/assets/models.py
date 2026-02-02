"""Asset template models.

Asset templates define prompt-driven PNG/GIF generation specifications
for visual content used in group choreography.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.templates.assets.enums import (
    AssetTemplateType,
    BackgroundMode,
    MatrixAspect,
    TemplateProjectionHint,
)


class PromptParts(BaseModel):
    """Structured prompt components for asset generation.

    Attributes:
        preamble: Optional preamble/context setter.
        subject: Main subject description (REQUIRED).
        style_block: Style guidance (art style, technique).
        composition: Composition guidance (layout, framing).
        background: Background description.
        lighting: Lighting guidance.
        constraints: Additional constraints.
        output_intent: Output intent/usage description.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    preamble: str | None = None
    subject: str = Field(min_length=3)  # REQUIRED
    style_block: str | None = None
    composition: str | None = None
    background: str | None = None
    lighting: str | None = None
    constraints: str | None = None
    output_intent: str | None = None


class PromptPolicy(BaseModel):
    """Constraint policy flags for asset generation.

    Attributes:
        require_high_contrast: Require high contrast visuals.
        require_low_detail: Prefer low detail, simple shapes.
        require_clean_edges: Require clean, crisp edges.
        require_no_text: Prohibit text/letters.
        require_no_logos: Prohibit brand logos.
        require_no_watermarks: Prohibit watermarks.
        require_seam_safe: Require seamless tiling.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    require_high_contrast: bool = True
    require_low_detail: bool = True
    require_clean_edges: bool = True
    require_no_text: bool = True
    require_no_logos: bool = True
    require_no_watermarks: bool = True
    require_seam_safe: bool = False


class MatrixDefaults(BaseModel):
    """Matrix/output dimension defaults.

    Attributes:
        base_size: Base size in pixels (e.g., 256, 512).
        aspect: Aspect ratio for generated asset.
        even_dimensions: Whether dimensions must be even numbers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_size: int = Field(default=256, gt=0)
    aspect: MatrixAspect = MatrixAspect.SQUARE
    even_dimensions: bool = True


class ProjectionDefaults(BaseModel):
    """Projection mapping defaults.

    Attributes:
        mode: Projection hint (FLAT, POLAR_CONE, POLAR_CYLINDER).
        seam_safe: Whether content tiles seamlessly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: TemplateProjectionHint = TemplateProjectionHint.FLAT
    seam_safe: bool = False


class PNGDefaults(BaseModel):
    """PNG-specific generation defaults.

    Attributes:
        background: Background mode (transparent or opaque).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    background: BackgroundMode = BackgroundMode.TRANSPARENT


class GIFDefaults(BaseModel):
    """GIF-specific generation defaults.

    Attributes:
        background: Background mode (transparent or opaque).
        fps: Frames per second (1-60).
        seconds: Duration in seconds (0-10).
        loop: Whether to loop animation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    background: BackgroundMode = BackgroundMode.TRANSPARENT
    fps: int = Field(default=12, ge=1, le=60)
    seconds: float = Field(default=2.0, gt=0.0, le=10.0)
    loop: bool = True


class AssetTemplate(BaseModel):
    """Complete asset generation template.

    Top-level model for asset templates. Defines prompt-driven PNG/GIF
    generation specifications for visual content.

    Attributes:
        schema_version: Schema version identifier.
        template_id: Unique template identifier (lowercase, alphanumeric).
        name: Human-readable template name.
        template_type: Asset template type (PNG/GIF variants).
        tags: List of tags for categorization.
        prompt_parts: Structured prompt components.
        prompt_policy: Constraint policy flags.
        negative_hints: List of negative prompt hints.
        matrix_defaults: Matrix/output dimension defaults.
        projection_defaults: Projection mapping defaults.
        png_defaults: PNG-specific defaults (required for PNG types).
        gif_defaults: GIF-specific defaults (required for GIF types).
        template_version: Template version string.
        author: Optional template author.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["asset_template.v1"] = "asset_template.v1"
    template_id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_\-\.]*$")
    name: str = Field(min_length=1)
    template_type: AssetTemplateType
    tags: list[str] = Field(default_factory=list)

    prompt_parts: PromptParts
    prompt_policy: PromptPolicy = Field(default_factory=PromptPolicy)
    negative_hints: list[str] = Field(default_factory=list)

    matrix_defaults: MatrixDefaults = Field(default_factory=MatrixDefaults)
    projection_defaults: ProjectionDefaults = Field(default_factory=ProjectionDefaults)
    png_defaults: PNGDefaults | None = None
    gif_defaults: GIFDefaults | None = None

    template_version: str = "1.0.0"
    author: str | None = None

    @model_validator(mode="after")
    def _validate_type_defaults(self) -> AssetTemplate:
        """Validate type-specific defaults are provided."""
        is_png = self.template_type in {
            AssetTemplateType.PNG_OPAQUE,
            AssetTemplateType.PNG_TRANSPARENT,
            AssetTemplateType.PNG_TILE,
        }
        is_gif = self.template_type == AssetTemplateType.GIF_OVERLAY

        # Require png_defaults for PNG types
        if is_png and not self.png_defaults:
            raise ValueError(f"template_type={self.template_type} requires png_defaults")

        # Require gif_defaults for GIF types
        if is_gif and not self.gif_defaults:
            raise ValueError(f"template_type={self.template_type} requires gif_defaults")

        # Dedupe and normalize tags
        self.tags = sorted({tag.strip().lower() for tag in self.tags if tag.strip()})

        # Dedupe and normalize negative hints
        self.negative_hints = sorted({h.strip() for h in self.negative_hints if h.strip()})

        return self
