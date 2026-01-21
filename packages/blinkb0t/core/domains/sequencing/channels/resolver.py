"""Channel resolver for channel specification system."""

from __future__ import annotations

import logging

from blinkb0t.core.config.models import ChannelDefaults
from blinkb0t.core.domains.sequencing.channels.validation import ChannelValidator
from blinkb0t.core.domains.sequencing.models.channels import (
    ChannelSpecification,
    ResolvedChannels,
)

logger = logging.getLogger(__name__)


class ChannelResolver:
    """Resolve channel specifications with job defaults.

    Responsibilities:
    - Apply precedence rules (section overrides job)
    - Validate resolved combinations
    - Provide clear error messages

    Example:
        >>> validator = BasicChannelValidator()
        >>> resolver = ChannelResolver(validator)
        >>> defaults = ChannelDefaults(shutter="open", color="white", gobo="open")
        >>> spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
        >>> resolved = resolver.resolve(defaults, spec)
        >>> resolved.shutter  # "strobe_fast" (from override)
        >>> resolved.color    # "white" (from default)
        >>> resolved.gobo     # "stars" (from override)
    """

    def __init__(self, validator: ChannelValidator):
        """Initialize resolver with validator.

        Args:
            validator: Channel validator for validating resolved combinations
        """
        self._validator = validator

    def resolve(
        self, defaults: ChannelDefaults, specification: ChannelSpecification
    ) -> ResolvedChannels:
        """Resolve section channel specification with job defaults.

        Args:
            defaults: Job-level channel defaults
            specification: Section-level channel overrides

        Returns:
            ResolvedChannels with final values

        Raises:
            ValueError: If resolved combination is invalid

        Example:
            >>> defaults = ChannelDefaults(shutter="open", color="white", gobo="open")
            >>> spec = ChannelSpecification(shutter="strobe_fast", gobo="stars")
            >>> resolved = resolver.resolve(defaults, spec)
            >>> resolved.shutter  # "strobe_fast" (from override)
            >>> resolved.color    # "white" (from default)
            >>> resolved.gobo     # "stars" (from override)
        """
        # Apply precedence: section override > job default
        shutter = specification.shutter or defaults.shutter
        color = specification.color or defaults.color
        gobo = specification.gobo or defaults.gobo

        # Create resolved object
        resolved = ResolvedChannels(shutter=shutter, color=color, gobo=gobo)

        # Validate combination
        is_valid, errors = self._validator.validate(resolved)
        if not is_valid:
            error_msg = "; ".join(errors)
            raise ValueError(
                f"Invalid channel combination: {error_msg}\n"
                f"Resolved: shutter={shutter}, color={color}, gobo={gobo}"
            )

        logger.debug(f"Resolved channels: shutter={shutter}, color={color}, gobo={gobo}")

        return resolved

    def resolve_with_fallback(
        self, defaults: ChannelDefaults, specification: ChannelSpecification
    ) -> ResolvedChannels:
        """Resolve with fallback on validation failure.

        If resolved combination is invalid, fall back to job defaults.
        Logs warning but doesn't raise exception.

        Args:
            defaults: Job-level channel defaults
            specification: Section-level channel overrides

        Returns:
            ResolvedChannels (either resolved or fallback to defaults)

        Example:
            >>> # Invalid spec will fall back to defaults
            >>> spec = ChannelSpecification(shutter="invalid_value")
            >>> resolved = resolver.resolve_with_fallback(defaults, spec)
            >>> resolved.shutter  # "open" (fallback to default)
        """
        try:
            return self.resolve(defaults, specification)
        except ValueError as e:
            logger.warning(f"Channel resolution failed, falling back to defaults: {e}")
            # Fall back to job defaults (guaranteed valid)
            return ResolvedChannels(
                shutter=defaults.shutter, color=defaults.color, gobo=defaults.gobo
            )
