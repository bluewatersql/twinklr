"""Color Arc Engine output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NamedPalette(BaseModel):
    """A concrete color palette with mood/temperature metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    palette_id: str = Field(description="Unique palette identifier.")
    name: str = Field(description="Human-readable palette name.")
    colors: tuple[str, ...] = Field(description="Hex color values.")
    mood_tags: tuple[str, ...] = Field(default=(), description="Mood descriptors.")
    temperature: Literal["warm", "cool", "neutral"] = Field(
        description="Overall color temperature."
    )


class SectionColorAssignment(BaseModel):
    """Color assignment for a single song section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    package_id: str
    sequence_file_id: str
    section_label: str
    section_index: int = Field(ge=0)
    palette_id: str = Field(description="Reference to NamedPalette.")
    spatial_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="target_group_id -> PaletteRole (primary, accent, warm, cool, neutral).",
    )
    shift_timing: Literal["beat_aligned", "section_boundary"] = Field(
        default="section_boundary",
        description="When palette transitions occur.",
    )
    contrast_target: float = Field(ge=0.0, le=1.0, description="Target contrast level.")


class ArcKeyframe(BaseModel):
    """A keyframe in the song-level color arc curve."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_pct: float = Field(ge=0.0, le=1.0, description="Position in song (0=start, 1=end).")
    temperature: float = Field(ge=0.0, le=1.0, description="Color temperature (0=cool, 1=warm).")
    saturation: float = Field(ge=0.0, le=1.0, description="Saturation level.")
    contrast: float = Field(ge=0.0, le=1.0, description="Contrast level.")


class ColorTransitionRule(BaseModel):
    """Rule for transitioning between palettes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_palette_id: str
    to_palette_id: str
    transition_style: Literal["crossfade", "cut", "ripple"] = Field(default="crossfade")
    duration_bars: int = Field(ge=1, description="Transition duration in bars.")


class SongColorArc(BaseModel):
    """Complete song-level color narrative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    palette_library: tuple[NamedPalette, ...] = Field(description="Available palettes.")
    section_assignments: tuple[SectionColorAssignment, ...] = Field(
        description="Per-section color assignments."
    )
    arc_curve: tuple[ArcKeyframe, ...] = Field(description="Song-level color arc keyframes.")
    transition_rules: tuple[ColorTransitionRule, ...] = Field(
        default=(), description="Palette transition rules."
    )
