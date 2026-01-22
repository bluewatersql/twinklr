"""Gobo channel library with predefined patterns."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GoboCategory(str, Enum):
    """Valid gobo categories."""

    BASIC = "basic"
    GEOMETRIC = "geometric"
    BREAKUP = "breakup"
    SPECIAL = "special"


class GoboPattern(str, Enum):
    """Predefined gobo pattern identifiers."""

    OPEN = "open"
    CIRCLES = "circles"
    TRIANGLES = "triangles"
    STARS = "stars"
    DIAMONDS = "diamonds"
    CLOUDS = "clouds"
    PRISM = "prism"
    SHATTER = "shatter"
    DOTS = "dots"
    FLAME = "flame"
    WATER = "water"
    FOLIAGE = "foliage"
    ABSTRACT = "abstract"


class GoboPatternDefinition(BaseModel):
    """Definition of a gobo pattern.

    Attributes:
        gobo_id: Unique gobo identifier
        name: Human-readable name
        description: Pattern description
        dmx_value: Gobo wheel DMX position 0-255 (validated)
        category: Pattern category (validated enum)
        visual_density: Visual density 1-10 (validated)
    """

    model_config = ConfigDict(frozen=True)

    gobo_id: str = Field(min_length=1, description="Unique gobo identifier")
    name: str = Field(min_length=1, description="Human-readable name")
    description: str = Field(min_length=1, description="Pattern description")
    dmx_value: int = Field(ge=0, le=255, description="Gobo wheel DMX position")
    category: GoboCategory = Field(description="Pattern category")
    visual_density: int = Field(ge=1, le=10, description="Visual density 1-10")


class GoboLibrary:
    """Library of predefined gobo patterns.

    Maps gobo names to gobo wheel DMX positions.
    Note: These are typical values, actual values are fixture-specific.
    """

    PATTERNS: dict[GoboPattern, GoboPatternDefinition] = {
        # Basic
        GoboPattern.OPEN: GoboPatternDefinition(
            gobo_id="open",
            name="Open",
            description="No gobo (open aperture)",
            dmx_value=0,
            category=GoboCategory.BASIC,
            visual_density=1,  # Changed from 0 to meet validation (ge=1)
        ),
        # Geometric patterns
        GoboPattern.CIRCLES: GoboPatternDefinition(
            gobo_id="circles",
            name="Circles",
            description="Circular patterns",
            dmx_value=20,
            category=GoboCategory.GEOMETRIC,
            visual_density=5,
        ),
        GoboPattern.TRIANGLES: GoboPatternDefinition(
            gobo_id="triangles",
            name="Triangles",
            description="Triangle patterns",
            dmx_value=40,
            category=GoboCategory.GEOMETRIC,
            visual_density=6,
        ),
        GoboPattern.STARS: GoboPatternDefinition(
            gobo_id="stars",
            name="Stars",
            description="Star patterns",
            dmx_value=60,
            category=GoboCategory.GEOMETRIC,
            visual_density=7,
        ),
        GoboPattern.DIAMONDS: GoboPatternDefinition(
            gobo_id="diamonds",
            name="Diamonds",
            description="Diamond patterns",
            dmx_value=80,
            category=GoboCategory.GEOMETRIC,
            visual_density=6,
        ),
        # Breakup patterns
        GoboPattern.CLOUDS: GoboPatternDefinition(
            gobo_id="clouds",
            name="Clouds",
            description="Cloud/fog breakup",
            dmx_value=100,
            category=GoboCategory.BREAKUP,
            visual_density=4,
        ),
        GoboPattern.PRISM: GoboPatternDefinition(
            gobo_id="prism",
            name="Prism",
            description="Prism shatter effect",
            dmx_value=120,
            category=GoboCategory.BREAKUP,
            visual_density=8,
        ),
        GoboPattern.SHATTER: GoboPatternDefinition(
            gobo_id="shatter",
            name="Shatter",
            description="Glass shatter pattern",
            dmx_value=140,
            category=GoboCategory.BREAKUP,
            visual_density=9,
        ),
        GoboPattern.DOTS: GoboPatternDefinition(
            gobo_id="dots",
            name="Dots",
            description="Dot breakup pattern",
            dmx_value=160,
            category=GoboCategory.BREAKUP,
            visual_density=7,
        ),
        # Special patterns
        GoboPattern.FLAME: GoboPatternDefinition(
            gobo_id="flame",
            name="Flame",
            description="Flame/fire pattern",
            dmx_value=180,
            category=GoboCategory.SPECIAL,
            visual_density=6,
        ),
        GoboPattern.WATER: GoboPatternDefinition(
            gobo_id="water",
            name="Water",
            description="Water/ripple pattern",
            dmx_value=200,
            category=GoboCategory.SPECIAL,
            visual_density=5,
        ),
        GoboPattern.FOLIAGE: GoboPatternDefinition(
            gobo_id="foliage",
            name="Foliage",
            description="Leaf/foliage pattern",
            dmx_value=220,
            category=GoboCategory.SPECIAL,
            visual_density=7,
        ),
        GoboPattern.ABSTRACT: GoboPatternDefinition(
            gobo_id="abstract",
            name="Abstract",
            description="Abstract organic pattern",
            dmx_value=240,
            category=GoboCategory.SPECIAL,
            visual_density=8,
        ),
    }

    @classmethod
    def get_pattern(cls, gobo_id: str | GoboPattern) -> GoboPatternDefinition:
        """Get gobo pattern definition.

        Args:
            gobo_id: Gobo identifier (string or enum)

        Returns:
            GoboPatternDefinition

        Raises:
            ValueError: If gobo_id is unknown
        """
        # Convert string to enum if needed
        if isinstance(gobo_id, str):
            try:
                pattern_key = GoboPattern(gobo_id)
            except ValueError as e:
                raise ValueError(
                    f"Unknown gobo pattern: '{gobo_id}'. Valid: {[p.value for p in GoboPattern]}"
                ) from e
        else:
            pattern_key = gobo_id

        pattern = cls.PATTERNS.get(pattern_key)
        if not pattern:
            raise ValueError(
                f"Unknown gobo pattern: '{gobo_id}'. Valid: {[p.value for p in GoboPattern]}"
            )
        return pattern

    @classmethod
    def get_all_metadata(cls) -> list[dict[str, str | int]]:
        """Get metadata for all patterns (for LLM context).

        Returns:
            List of pattern metadata dictionaries
        """
        return [
            {
                "gobo_id": p.gobo_id,
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "visual_density": p.visual_density,
            }
            for p in cls.PATTERNS.values()
        ]

    @classmethod
    def get_by_category(cls, category: GoboCategory) -> list[GoboPatternDefinition]:
        """Get gobos in a specific category.

        Args:
            category: Category filter (GoboCategory enum)

        Returns:
            List of matching gobo patterns
        """
        return [p for p in cls.PATTERNS.values() if p.category == category]
