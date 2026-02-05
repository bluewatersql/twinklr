"""Theming models - theme, palette, and tag definitions.

Models for visual theming and categorization, shared across
both group and asset template systems.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from twinklr.core.sequencer.theming.enums import TagCategory, ThemeScope
from twinklr.core.sequencer.vocabulary.energy import EnergyTarget


class ColorStop(BaseModel):
    """Single color stop in a palette gradient.

    Attributes:
        hex: Color in hex format (#RRGGBB or #RRGGBBAA).
        name: Optional human-readable color name.
        weight: Relative weight for color distribution (default 1.0).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Accept either "#RRGGBB" or "#RRGGBBAA"
    hex: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
    name: str | None = None
    weight: float = Field(default=1.0, ge=0.0)


class PaletteDefinition(BaseModel):
    """Color palette definition for themed content.

    Attributes:
        palette_id: Stable identifier (e.g., 'christmas.gingerbread_warm').
        title: Human-readable palette name.
        description: Optional palette description.
        stops: List of color stops (2-12 colors).
        usage_hint: Short hint for prompt generation.
        background_hex: Optional default background color.
    """

    model_config = ConfigDict(extra="forbid")

    palette_id: str = Field(..., description="Stable id, e.g. 'christmas.gingerbread_warm'")
    title: str
    description: str | None = None

    stops: list[ColorStop] = Field(..., min_length=2, max_length=12)

    # Optional: hinting only (not enforcement) for generation
    usage_hint: str | None = Field(
        default=None,
        description="Short hint for prompts, e.g. 'warm browns, icing white, candy reds/greens'",
    )

    # Optional: when you care about constraints later
    background_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagDefinition(BaseModel):
    """Tag definition for categorization and search.

    Attributes:
        tag: Tag identifier (dot-separated, lowercase).
        description: Optional tag description.
        category: Optional category classification.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag: str = Field(..., pattern=r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
    description: str | None = None
    category: TagCategory | None = None


class ThemeDefinition(BaseModel):
    """Theme definition for visual consistency across templates.

    Attributes:
        theme_id: Stable theme identifier.
        title: Human-readable theme name.
        description: Optional theme description.
        default_tags: Tags to include by default.
        avoid_tags: Tags to avoid in themed content.
        style_tags: Style-related tags for the theme.
        default_palette_id: Optional default palette for this theme.
        recommended_template_ids: Templates that work well with this theme.
    """

    model_config = ConfigDict(extra="forbid")

    theme_id: str
    title: str
    description: str | None = None

    # Defaults that influence prompts & selection
    default_tags: list[str] = Field(default_factory=list)
    avoid_tags: list[str] = Field(default_factory=lambda: ["text", "logo", "watermark"])
    style_tags: list[str] = Field(
        default_factory=lambda: ["flat", "bold", "high_contrast", "low_detail"]
    )

    default_palette_id: str | None = None

    # Optional: later, you can map templates/motifs if you want
    recommended_template_ids: list[str] = Field(default_factory=list)


class ThemeRef(BaseModel):
    """Reference to a theme for visual consistency.

    Used when placing templates to specify which theme should be applied.

    Attributes:
        theme_id: Theme to reference (e.g., 'christmas.gingerbread_house').
        scope: How broadly the theme applies.
        tags: Extra tags to bias generation.
        palette_id: Optional palette override.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    theme_id: str = Field(..., description="Stable id, e.g. 'christmas.gingerbread_house'")
    scope: ThemeScope = Field(..., description="How broadly the theme applies (SONG, SECTION, or PLACEMENT)")
    tags: list[str] = Field(default_factory=list, max_length=5, description="Extra tags to bias generation")
    palette_id: str | None = Field(default=None, description="Optional palette override")

    @field_validator("scope", mode="before")
    @classmethod
    def normalize_scope(cls, v: str | ThemeScope) -> str | ThemeScope:
        """Normalize scope to uppercase to handle LLM outputs like 'song'."""
        if isinstance(v, str):
            return v.upper()
        return v


class ThemeCatalog(BaseModel):
    """Catalog of themes, palettes, and tags.

    Provides a centralized registry for visual theming resources.

    Attributes:
        schema_version: Schema version identifier.
        themes: Dictionary of theme definitions keyed by theme_id.
        palettes: Dictionary of palette definitions keyed by palette_id.
        tags: Dictionary of tag definitions keyed by tag.
    """

    schema_version: Literal["theme_catalog.v1"] = "theme_catalog.v1"
    themes: dict[str, ThemeDefinition] = Field(default_factory=dict)
    palettes: dict[str, PaletteDefinition] = Field(default_factory=dict)
    tags: dict[str, TagDefinition] = Field(default_factory=dict)


class MotifDefinition(BaseModel):
    """Motif definition for visual content guidance.

    Motifs are derived from motif.* tags and provide structured metadata
    for planners and validators.

    Attributes:
        motif_id: Stable identifier (e.g., 'spiral', 'snowflakes').
        tags: Tags for template matching (must include motif.* tag).
        description: Motif description.
        preferred_energy: Energy levels this motif works best at.
        usage_notes: Optional usage guidance for planners.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    motif_id: str = Field(..., min_length=1, description="Stable id derived from motif.* tag")
    tags: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=8,
        description="Tags for template matching (must include at least one motif.* tag)",
    )
    description: str = Field(default="", max_length=300)
    preferred_energy: list[EnergyTarget] = Field(default_factory=list)
    usage_notes: str = Field(default="", max_length=500)


__all__ = [
    "ColorStop",
    "PaletteDefinition",
    "TagDefinition",
    "ThemeCatalog",
    "ThemeDefinition",
    "ThemeRef",
    "MotifDefinition",
]
