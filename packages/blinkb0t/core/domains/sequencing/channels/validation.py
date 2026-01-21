"""Channel validation for channel specification system."""

from __future__ import annotations

from typing import Protocol

from blinkb0t.core.domains.sequencing.models.channels import ResolvedChannels


class ChannelValidator(Protocol):
    """Protocol for channel validation.

    Implementations validate resolved channel combinations and return
    validation results with detailed error messages.
    """

    def validate(self, channels: ResolvedChannels) -> tuple[bool, list[str]]:
        """Validate resolved channel combination.

        Args:
            channels: Resolved channel values to validate

        Returns:
            Tuple of (is_valid, errors) where errors is list of validation messages
        """
        ...


class BasicChannelValidator:
    """Basic channel combination validation.

    Validates:
    1. All channel values are from valid sets
    2. No obviously incompatible combinations

    Future enhancements:
    - Fixture-specific validation (check fixture supports channel)
    - Complex interaction rules (e.g., certain colors don't work with certain gobos)
    """

    VALID_SHUTTER_VALUES = {
        "open",
        "closed",
        "strobe_fast",
        "strobe_medium",
        "strobe_slow",
        "pulse",
    }

    VALID_COLOR_VALUES = {
        # Primary colors
        "red",
        "blue",
        "green",
        "yellow",
        "magenta",
        "cyan",
        # Secondary colors
        "orange",
        "purple",
        "amber",
        "lime",
        # Special
        "white",
        "warm_white",
        "cool_white",
        "uv",
    }

    VALID_GOBO_VALUES = {
        # Basic
        "open",
        # Geometric
        "circles",
        "triangles",
        "stars",
        "diamonds",
        # Breakup
        "clouds",
        "prism",
        "shatter",
        "dots",
        # Special
        "flame",
        "water",
        "foliage",
        "abstract",
    }

    def validate(self, channels: ResolvedChannels) -> tuple[bool, list[str]]:
        """Validate resolved channel combination.

        Args:
            channels: Resolved channel values to validate

        Returns:
            Tuple of (is_valid, errors) where errors is list of validation messages
        """
        errors = []

        # Validate shutter
        if channels.shutter not in self.VALID_SHUTTER_VALUES:
            errors.append(
                f"Invalid shutter value: '{channels.shutter}'. "
                f"Valid: {sorted(self.VALID_SHUTTER_VALUES)}"
            )

        # Validate color
        if channels.color not in self.VALID_COLOR_VALUES:
            errors.append(
                f"Invalid color value: '{channels.color}'. Valid: {sorted(self.VALID_COLOR_VALUES)}"
            )

        # Validate gobo
        if channels.gobo not in self.VALID_GOBO_VALUES:
            errors.append(
                f"Invalid gobo value: '{channels.gobo}'. Valid: {sorted(self.VALID_GOBO_VALUES)}"
            )

        # Check incompatible combinations
        # Example: closed shutter + any gobo = pointless (light is off)
        if channels.shutter == "closed" and channels.gobo != "open":
            errors.append("Incompatible: closed shutter with non-open gobo (gobo won't be visible)")

        is_valid = len(errors) == 0
        return (is_valid, errors)
