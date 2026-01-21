"""Channel heuristic validator for agent extensions.

Provides fast, non-LLM validation for channel appropriateness.
"""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.agents.moving_heads.models_agent_plan import SectionPlan
from blinkb0t.core.domains.sequencing.libraries.channels import (
    ColorLibrary,
    GoboLibrary,
    ShutterLibrary,
)
from blinkb0t.core.domains.sequencing.models.channels import ChannelSpecification

logger = logging.getLogger(__name__)


class ChannelHeuristicValidator:
    """Heuristic validation for channel specifications.

    Validates channel appropriateness based on energy levels and
    detects obvious conflicts. Fast, non-LLM checks.

    Example:
        >>> validator = ChannelHeuristicValidator()
        >>> is_valid, warnings = validator.validate_section_channels(
        ...     section=section_plan,
        ...     song_features=song_features
        ... )
        >>> if not is_valid:
        ...     for warning in warnings:
        ...         print(f"Warning: {warning}")
    """

    def __init__(self) -> None:
        """Initialize channel validator."""
        self._shutter_lib = ShutterLibrary()
        self._color_lib = ColorLibrary()
        self._gobo_lib = GoboLibrary()

    def validate_section_channels(
        self,
        section: SectionPlan,
        song_features: dict[str, Any] | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate channel specifications for a section.

        Args:
            section: Section plan with channel specifications
            song_features: Song features (optional, for energy estimation)

        Returns:
            (is_valid, warnings) tuple where is_valid is True if no warnings

        """
        warnings = []

        # Get section energy
        section_energy = section.energy_level

        # Validate shutter appropriateness
        if section.channels.shutter:
            shutter_warning = self._validate_shutter(section.channels.shutter, section_energy)
            if shutter_warning:
                warnings.append(shutter_warning)

        # Validate color appropriateness
        if section.channels.color:
            color_warning = self._validate_color(section.channels.color, section_energy)
            if color_warning:
                warnings.append(color_warning)

        # Validate gobo appropriateness
        if section.channels.gobo:
            gobo_warning = self._validate_gobo(section.channels.gobo, section_energy)
            if gobo_warning:
                warnings.append(gobo_warning)

        # Check for obvious conflicts
        conflict_warning = self._check_conflicts(section.channels)
        if conflict_warning:
            warnings.append(conflict_warning)

        is_valid = len(warnings) == 0
        return (is_valid, warnings)

    def _validate_shutter(self, shutter: str, energy: int) -> str | None:
        """Validate shutter choice matches energy.

        Args:
            shutter: Shutter pattern ID
            energy: Section energy level (0-100)

        Returns:
            Warning message if inappropriate, None if valid
        """
        try:
            pattern = self._shutter_lib.get_pattern(shutter)
        except (KeyError, ValueError):
            return f"Unknown shutter pattern: {shutter}"

        # High energy should use strobe
        if energy > 70 and pattern.energy_level < 7:
            return (
                f"High energy section ({energy}) should use more intense shutter "
                f"(currently: {shutter} with energy {pattern.energy_level})"
            )

        # Low energy should not use strobe
        if energy < 40 and pattern.energy_level > 6:
            return (
                f"Low energy section ({energy}) should not use intense strobe "
                f"(currently: {shutter} with energy {pattern.energy_level})"
            )

        return None

    def _validate_color(self, color: str, energy: int) -> str | None:
        """Validate color choice matches energy.

        Args:
            color: Color preset ID
            energy: Section energy level (0-100)

        Returns:
            Warning message if inappropriate, None if valid
        """
        try:
            preset = self._color_lib.get_preset(color)
        except (KeyError, ValueError):
            return f"Unknown color preset: {color}"

        # High energy may benefit from warm colors (suggestion, not hard rule)
        if energy > 70 and preset.mood.value == "cool":
            return (
                f"High energy section ({energy}) may benefit from warm colors "
                f"(currently: {color} - {preset.mood.value} mood)"
            )

        return None

    def _validate_gobo(self, gobo: str, energy: int) -> str | None:
        """Validate gobo choice.

        Args:
            gobo: Gobo pattern ID
            energy: Section energy level (0-100)

        Returns:
            Warning message if inappropriate, None if valid
        """
        try:
            pattern = self._gobo_lib.get_pattern(gobo)
        except (KeyError, ValueError):
            return f"Unknown gobo pattern: {gobo}"

        # High energy sections may benefit from higher visual density
        if energy > 80 and pattern.visual_density < 5:
            return (
                f"High energy section ({energy}) may benefit from more visually dense gobo "
                f"(currently: {gobo} with density {pattern.visual_density})"
            )

        return None

    def _check_conflicts(self, channels: ChannelSpecification) -> str | None:
        """Check for conflicting channel combinations.

        Args:
            channels: Channel specification

        Returns:
            Warning message if conflict detected, None if valid
        """
        shutter = channels.shutter
        gobo = channels.gobo

        # Closed shutter + gobo = pointless (gobo won't be visible)
        if shutter == "closed" and gobo and gobo != "open":
            return f"Closed shutter with {gobo} gobo - gobo won't be visible"

        return None
