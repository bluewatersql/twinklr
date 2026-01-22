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


class ColorPreset(str, Enum):
    """Predefined color preset identifiers."""

    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"
    MAGENTA = "magenta"
    CYAN = "cyan"
    ORANGE = "orange"
    PURPLE = "purple"
    AMBER = "amber"
    LIME = "lime"
    WHITE = "white"
    WARM_WHITE = "warm_white"
    COOL_WHITE = "cool_white"
    UV = "uv"


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

    PRESETS: dict[ColorPreset, ColorPresetDefinition] = {
        # Primary colors
        ColorPreset.RED: ColorPresetDefinition(
            color_id="red",
            name="Red",
            description="Primary red",
            dmx_value=10,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.WARM,
        ),
        ColorPreset.BLUE: ColorPresetDefinition(
            color_id="blue",
            name="Blue",
            description="Primary blue",
            dmx_value=30,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        ColorPreset.GREEN: ColorPresetDefinition(
            color_id="green",
            name="Green",
            description="Primary green",
            dmx_value=50,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        ColorPreset.YELLOW: ColorPresetDefinition(
            color_id="yellow",
            name="Yellow",
            description="Primary yellow",
            dmx_value=70,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.WARM,
        ),
        ColorPreset.MAGENTA: ColorPresetDefinition(
            color_id="magenta",
            name="Magenta",
            description="Primary magenta",
            dmx_value=90,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        ColorPreset.CYAN: ColorPresetDefinition(
            color_id="cyan",
            name="Cyan",
            description="Primary cyan",
            dmx_value=110,
            category=ColorCategory.PRIMARY,
            mood=ColorMood.COOL,
        ),
        # Secondary colors
        ColorPreset.ORANGE: ColorPresetDefinition(
            color_id="orange",
            name="Orange",
            description="Orange",
            dmx_value=130,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.WARM,
        ),
        ColorPreset.PURPLE: ColorPresetDefinition(
            color_id="purple",
            name="Purple",
            description="Purple/violet",
            dmx_value=150,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.COOL,
        ),
        ColorPreset.AMBER: ColorPresetDefinition(
            color_id="amber",
            name="Amber",
            description="Amber/gold",
            dmx_value=170,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.WARM,
        ),
        ColorPreset.LIME: ColorPresetDefinition(
            color_id="lime",
            name="Lime",
            description="Lime green",
            dmx_value=190,
            category=ColorCategory.SECONDARY,
            mood=ColorMood.COOL,
        ),
        # Special
        ColorPreset.WHITE: ColorPresetDefinition(
            color_id="white",
            name="White",
            description="Open/white (no color)",
            dmx_value=0,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.NEUTRAL,
        ),
        ColorPreset.WARM_WHITE: ColorPresetDefinition(
            color_id="warm_white",
            name="Warm White",
            description="Warm white (CTO)",
            dmx_value=210,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.WARM,
        ),
        ColorPreset.COOL_WHITE: ColorPresetDefinition(
            color_id="cool_white",
            name="Cool White",
            description="Cool white (CTB)",
            dmx_value=230,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.COOL,
        ),
        ColorPreset.UV: ColorPresetDefinition(
            color_id="uv",
            name="UV",
            description="Ultraviolet",
            dmx_value=250,
            category=ColorCategory.SPECIAL,
            mood=ColorMood.NEUTRAL,
        ),
    }

    @classmethod
    def get_preset(cls, color_id: str | ColorPreset) -> ColorPresetDefinition:
        """Get color preset definition.

        Args:
            color_id: Color identifier (string or enum)

        Returns:
            ColorPresetDefinition

        Raises:
            ValueError: If color_id is unknown
        """
        # Convert string to enum if needed
        if isinstance(color_id, str):
            try:
                preset_key = ColorPreset(color_id)
            except ValueError as e:
                raise ValueError(
                    f"Unknown color preset: '{color_id}'. Valid: {[p.value for p in ColorPreset]}"
                ) from e
        else:
            preset_key = color_id

        preset = cls.PRESETS.get(preset_key)
        if not preset:
            raise ValueError(
                f"Unknown color preset: '{color_id}'. Valid: {[p.value for p in ColorPreset]}"
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
