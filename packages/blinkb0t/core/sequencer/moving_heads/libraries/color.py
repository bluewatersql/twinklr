"""Color channel library with predefined presets."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ColorCategory(str, Enum):
    """Valid color categories."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SPECIAL = "special"


class ColorMood(str, Enum):
    """Valid color moods."""

    WARM = "warm"
    COOL = "cool"
    NEUTRAL = "neutral"


class ColorPresetDefinition(BaseModel):
    """Definition of a color preset.

    Attributes:
        color_id: Unique color identifier
        name: Human-readable name
        description: Color description
        dmx_value: Color wheel DMX position 0-255 (validated)
        category: Color category (validated enum)
        mood: Color mood (validated enum)
    """

    model_config = ConfigDict(frozen=True)

    color_id: str = Field(min_length=1, description="Unique color identifier")
    name: str = Field(min_length=1, description="Human-readable name")
    description: str = Field(min_length=1, description="Color description")
    dmx_value: int = Field(ge=0, le=255, description="Color wheel DMX position")
    category: ColorCategory = Field(description="Color category")
    mood: ColorMood = Field(description="Color mood")


class ColorLibrary:
    """Library of predefined color presets.

    Maps color names to color wheel DMX positions.
    Note: These are typical values, actual values are fixture-specific.
    """

    PRESETS: dict[str, ColorPresetDefinition] = {
        # Primary colors
        "red": ColorPresetDefinition(
            color_id="red",
            name="Red",
            description="Primary red",
            dmx_value=10,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.WARM,
        ),
        "blue": ColorPresetDefinition(
            color_id="blue",
            name="Blue",
            description="Primary blue",
            dmx_value=30,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        "green": ColorPresetDefinition(
            color_id="green",
            name="Green",
            description="Primary green",
            dmx_value=50,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        "yellow": ColorPresetDefinition(
            color_id="yellow",
            name="Yellow",
            description="Primary yellow",
            dmx_value=70,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.WARM,
        ),
        "magenta": ColorPresetDefinition(
            color_id="magenta",
            name="Magenta",
            description="Primary magenta",
            dmx_value=90,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        "cyan": ColorPresetDefinition(
            color_id="cyan",
            name="Cyan",
            description="Primary cyan",
            dmx_value=110,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        # Secondary colors
        "orange": ColorPresetDefinition(
            color_id="orange",
            name="Orange",
            description="Orange",
            dmx_value=130,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.WARM,
        ),
        "purple": ColorPresetDefinition(
            color_id="purple",
            name="Purple",
            description="Purple/violet",
            dmx_value=150,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.COOL,
        ),
        "amber": ColorPresetDefinition(
            color_id="amber",
            name="Amber",
            description="Amber/gold",
            dmx_value=170,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.WARM,
        ),
        "lime": ColorPresetDefinition(
            color_id="lime",
            name="Lime",
            description="Lime green",
            dmx_value=190,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.COOL,
        ),
        # Special
        "white": ColorPresetDefinition(
            color_id="white",
            name="White",
            description="Open/white (no color)",
            dmx_value=0,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.NEUTRAL,
        ),
        "warm_white": ColorPresetDefinition(
            color_id="warm_white",
            name="Warm White",
            description="Warm white (CTO)",
            dmx_value=210,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.WARM,
        ),
        "cool_white": ColorPresetDefinition(
            color_id="cool_white",
            name="Cool White",
            description="Cool white (CTB)",
            dmx_value=230,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.COOL,
        ),
        "uv": ColorPresetDefinition(
            color_id="uv",
            name="UV",
            description="Ultraviolet",
            dmx_value=250,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.NEUTRAL,
        ),
    }

    @classmethod
    def get_preset(cls, color_id: str) -> ColorPresetDefinition:
        """Get color preset definition.

        Args:
            color_id: Color identifier

        Returns:
            ColorPresetDefinition

        Raises:
            ValueError: If color_id is unknown
        """
        preset = cls.PRESETS.get(color_id)
        if not preset:
            raise ValueError(
                f"Unknown color preset: '{color_id}'. Valid: {sorted(cls.PRESETS.keys())}"
            )
        return preset

    @classmethod
    def get_all_metadata(cls) -> list[dict[str, str | int]]:
        """Get metadata for all presets (for LLM context).

        Returns:
            List of preset metadata dictionaries
        """
        return [
            {
                "color_id": p.color_id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "mood": p.mood,
            }
            for p in cls.PRESETS.values()
        ]

    @classmethod
    def get_by_mood(cls, mood: ColorMood) -> list[ColorPresetDefinition]:
        """Get colors matching a specific mood.

        Args:
            mood: Mood filter (ColorMood enum)

        Returns:
            List of matching color presets
        """
        return [p for p in cls.PRESETS.values() if p.mood == mood]
