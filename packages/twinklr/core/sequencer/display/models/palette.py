"""Palette and transition models for the display renderer.

Defines ResolvedPalette (colors ready for xLights) and TransitionSpec.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResolvedPalette(BaseModel):
    """Resolved color palette ready for xLights ColorPalette string generation.

    Contains concrete hex color values and modifier settings. This is the
    renderer's internal representation; PaletteBuilder converts it to
    the xLights comma-separated string format.

    Attributes:
        colors: Hex color values for palette slots (up to 8).
        active_slots: 1-based indices of active color slots.
        sparkle_frequency: Sparkle frequency (0-200), None to omit.
        music_sparkles: Whether sparkles are music-reactive.
        brightness: Brightness override (0-100), None to omit.
        brightness_curve: ValueCurve string for animated brightness.
        sparkle_color: Hex color for sparkles, None for default white.
        hue_adjust: Hue adjustment (-100 to 100), None to omit.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    colors: list[str] = Field(
        min_length=1,
        max_length=8,
        description="Hex color values (#RRGGBB) for palette slots",
    )
    active_slots: list[int] = Field(
        min_length=1,
        description="1-based indices of active color slots",
    )
    sparkle_frequency: int | None = Field(
        default=None,
        ge=0,
        le=200,
        description="Sparkle frequency (0-200)",
    )
    music_sparkles: bool = Field(
        default=False,
        description="Whether sparkles are music-reactive",
    )
    brightness: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Brightness override (0-100)",
    )
    brightness_curve: str | None = Field(
        default=None,
        description="ValueCurve string for animated brightness",
    )
    sparkle_color: str | None = Field(
        default=None,
        description="Hex color for sparkles (#RRGGBB)",
    )
    hue_adjust: int | None = Field(
        default=None,
        ge=-100,
        le=100,
        description="Hue adjustment (-100 to 100)",
    )

    @field_validator("colors")
    @classmethod
    def validate_hex_colors(cls, v: list[str]) -> list[str]:
        """Validate all colors are valid hex format."""
        for color in v:
            if not color.startswith("#") or len(color) != 7:
                raise ValueError(
                    f"Color must be #RRGGBB format, got '{color}'"
                )
        return v

    @field_validator("active_slots")
    @classmethod
    def validate_slot_indices(cls, v: list[int]) -> list[int]:
        """Validate slot indices are 1-8."""
        for slot in v:
            if not 1 <= slot <= 8:
                raise ValueError(
                    f"Active slot must be 1-8, got {slot}"
                )
        return v


class TransitionSpec(BaseModel):
    """Specification for a visual transition between effects.

    Attributes:
        type: xLights transition type name.
        duration_ms: Transition duration in milliseconds.
        reverse: Whether to reverse the transition direction.
        adjust: Transition adjustment value (0-100).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(
        default="Fade",
        description="xLights transition type (e.g., 'Fade', 'Wipe')",
    )
    duration_ms: int = Field(
        default=500,
        ge=0,
        description="Transition duration in milliseconds",
    )
    reverse: bool = Field(
        default=False,
        description="Whether to reverse transition direction",
    )
    adjust: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Transition adjustment value",
    )


__all__ = [
    "ResolvedPalette",
    "TransitionSpec",
]
