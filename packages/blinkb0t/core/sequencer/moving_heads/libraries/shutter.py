"""Shutter channel library with predefined patterns."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ShutterPattern(str, Enum):
    """Predefined shutter pattern identifiers.

    Provides type-safe pattern IDs with IDE autocomplete.
    """

    OPEN = "open"
    CLOSED = "closed"
    STROBE_FAST = "strobe_fast"
    STROBE_MEDIUM = "strobe_medium"
    STROBE_SLOW = "strobe_slow"
    PULSE = "pulse"


class ShutterPatternDefinition(BaseModel):
    """Definition of a shutter pattern.

    Attributes:
        pattern_id: Unique pattern identifier
        name: Human-readable name
        description: Pattern description
        dmx_value: DMX value 0-255 (None for dynamic patterns)
        is_dynamic: Whether pattern requires beat sync
        energy_level: Energy level 1-10 (validated)
    """

    model_config = ConfigDict(frozen=True)

    pattern_id: str = Field(min_length=1, description="Unique pattern identifier")
    name: str = Field(min_length=1, description="Human-readable name")
    description: str = Field(min_length=1, description="Pattern description")
    dmx_value: int | None = Field(None, ge=0, le=255, description="DMX value (None for dynamic)")
    is_dynamic: bool = Field(description="Whether pattern requires beat sync")
    energy_level: int = Field(ge=1, le=10, description="Energy level 1-10")


class ShutterLibrary:
    """Library of predefined shutter patterns.

    Provides DMX values for different shutter effects.
    """

    # DMX value constants (typical values, fixture-specific)
    DMX_CLOSED = 0
    DMX_OPEN = 255
    DMX_STROBE_SLOW = 150
    DMX_STROBE_MEDIUM = 200
    DMX_STROBE_FAST = 250

    PATTERNS: dict[str, ShutterPatternDefinition] = {
        "open": ShutterPatternDefinition(
            pattern_id="open",
            name="Open",
            description="Shutter fully open (continuous light)",
            dmx_value=DMX_OPEN,
            is_dynamic=False,
            energy_level=5,
        ),
        "closed": ShutterPatternDefinition(
            pattern_id="closed",
            name="Closed",
            description="Shutter closed (blackout)",
            dmx_value=DMX_CLOSED,
            is_dynamic=False,
            energy_level=1,  # Changed from 0 to meet validation (ge=1)
        ),
        "strobe_fast": ShutterPatternDefinition(
            pattern_id="strobe_fast",
            name="Fast Strobe",
            description="Fast strobe effect",
            dmx_value=DMX_STROBE_FAST,
            is_dynamic=False,
            energy_level=10,
        ),
        "strobe_medium": ShutterPatternDefinition(
            pattern_id="strobe_medium",
            name="Medium Strobe",
            description="Medium speed strobe",
            dmx_value=DMX_STROBE_MEDIUM,
            is_dynamic=False,
            energy_level=7,
        ),
        "strobe_slow": ShutterPatternDefinition(
            pattern_id="strobe_slow",
            name="Slow Strobe",
            description="Slow strobe effect",
            dmx_value=DMX_STROBE_SLOW,
            is_dynamic=False,
            energy_level=5,
        ),
        "pulse": ShutterPatternDefinition(
            pattern_id="pulse",
            name="Pulse",
            description="Beat-synchronized pulsing (open/closed)",
            dmx_value=None,
            is_dynamic=True,
            energy_level=6,
        ),
    }

    @classmethod
    def get_pattern(cls, pattern_id: str) -> ShutterPatternDefinition:
        """Get shutter pattern definition.

        Args:
            pattern_id: Pattern identifier

        Returns:
            ShutterPatternDefinition

        Raises:
            ValueError: If pattern_id is unknown
        """
        pattern = cls.PATTERNS.get(pattern_id)
        if not pattern:
            raise ValueError(
                f"Unknown shutter pattern: '{pattern_id}'. Valid: {sorted(cls.PATTERNS.keys())}"
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
                "pattern_id": p.pattern_id,
                "name": p.name,
                "description": p.description,
                "energy_level": p.energy_level,
            }
            for p in cls.PATTERNS.values()
        ]
