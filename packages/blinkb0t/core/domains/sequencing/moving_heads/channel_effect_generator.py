"""Channel effect generation for moving head sequencing.

Extracted from MovingHeadSequencer to simplify orchestration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from blinkb0t.core.config.fixtures import FixtureGroup
    from blinkb0t.core.config.models import JobConfig
    from blinkb0t.core.domains.sequencing.channels.handlers import (
        ColorHandler,
        GoboHandler,
        ShutterHandler,
    )

logger = logging.getLogger(__name__)


class ChannelEffectGenerator:
    """Generates channel effects from plan specifications."""

    def __init__(
        self,
        shutter_handler: ShutterHandler,
        color_handler: ColorHandler,
        gobo_handler: GoboHandler,
        job_config: JobConfig,
    ):
        """Initialize channel effect generator.

        Args:
            shutter_handler: Handler for shutter effects
            color_handler: Handler for color effects
            gobo_handler: Handler for gobo effects
            job_config: Job configuration for defaults
        """
        self.shutter_handler = shutter_handler
        self.color_handler = color_handler
        self.gobo_handler = gobo_handler
        self.job_config = job_config

    def generate(
        self,
        section: dict[str, Any],
        instruction: dict[str, Any],
        fixture_group: FixtureGroup,
        section_start_ms: int,
        section_end_ms: int,
        beat_times_ms: list[int] | None = None,
    ) -> list[Any]:  # Returns list[ChannelEffect]
        """Generate channel effects from plan specifications.

        Args:
            section: Section plan dict
            instruction: Instruction dict
            fixture_group: Target fixtures
            section_start_ms: Section start time
            section_end_ms: Section end time
            beat_times_ms: Optional beat times for synchronization

        Returns:
            List of ChannelEffect objects
        """
        from blinkb0t.core.domains.sequencing.models.channels import ChannelEffect

        channel_effects: list[ChannelEffect] = []

        # Get channel specifications
        channel_spec = section.get("channels")

        if not channel_spec and self.job_config.channel_defaults:
            defaults = self.job_config.channel_defaults
            channel_spec = {
                "shutter": defaults.shutter if defaults.shutter else None,
                "color": defaults.color if defaults.color else None,
                "gobo": defaults.gobo if defaults.gobo else None,
            }

        # No channel specifications found
        if not channel_spec:
            logger.debug("No channel specifications found for section")
            return []

        # Generate shutter effects
        if channel_spec.get("shutter"):
            try:
                shutter_effects = self.shutter_handler.render(
                    channel_value=channel_spec["shutter"] or "open",
                    fixtures=fixture_group,
                    start_time_ms=section_start_ms,
                    end_time_ms=section_end_ms,
                    beat_times_ms=beat_times_ms,
                )
                channel_effects.extend(shutter_effects)
                logger.debug(f"Generated {len(shutter_effects)} shutter effects")
            except Exception as e:
                logger.error(f"Failed to generate shutter effects: {e}", exc_info=True)

        # Generate color effects
        if channel_spec.get("color"):
            try:
                color_effects = self.color_handler.render(
                    channel_value=channel_spec["color"] or "white",
                    fixtures=fixture_group,
                    start_time_ms=section_start_ms,
                    end_time_ms=section_end_ms,
                    beat_times_ms=beat_times_ms,
                )
                channel_effects.extend(color_effects)
                logger.debug(f"Generated {len(color_effects)} color effects")
            except Exception as e:
                logger.error(f"Failed to generate color effects: {e}", exc_info=True)

        # Generate gobo effects
        if channel_spec.get("gobo"):
            try:
                gobo_effects = self.gobo_handler.render(
                    channel_value=channel_spec["gobo"] or "open",
                    fixtures=fixture_group,
                    start_time_ms=section_start_ms,
                    end_time_ms=section_end_ms,
                    beat_times_ms=beat_times_ms,
                )
                channel_effects.extend(gobo_effects)
                logger.debug(f"Generated {len(gobo_effects)} gobo effects")
            except Exception as e:
                logger.error(f"Failed to generate gobo effects: {e}", exc_info=True)

        logger.info(f"Generated {len(channel_effects)} total channel effects")
        return channel_effects
