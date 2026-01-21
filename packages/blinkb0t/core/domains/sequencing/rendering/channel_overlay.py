"""Channel overlay resolution (shutter/color/gobo).

Resolves per-section channel overlays from AgentImplementation.
This happens early in the pipeline (before segment rendering) so that
all channel specifications are available when creating SequencedEffects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blinkb0t.core.agents.moving_heads.models_agent_plan import AgentImplementation
    from blinkb0t.core.config.models import JobConfig
    from blinkb0t.core.domains.sequencing.channels.handlers import (
        ColorHandler,
        GoboHandler,
        ShutterHandler,
    )

from .models import ChannelOverlay


def resolve_channel_overlays(
    agent_implementation: AgentImplementation,
    shutter_handler: ShutterHandler,
    color_handler: ColorHandler,
    gobo_handler: GoboHandler,
    job_config: JobConfig,
) -> dict[str, ChannelOverlay]:
    """Resolve channel overlay specifications per section.

    This happens BEFORE segment rendering so that all channels can be
    included in each SequencedEffect from the start.

    Resolves appearance channels (shutter, color, gobo) for each section
    by calling the appropriate handlers. Handlers may return:
    - Static values (int)
    - RGB tuples (color only)
    - ValueCurveSpec for dynamic patterns (e.g., strobe shutter)

    Args:
        agent_implementation: Implementation with sections
        shutter_handler: Handler for shutter patterns
        color_handler: Handler for color presets
        gobo_handler: Handler for gobo patterns
        job_config: Job configuration with channel defaults

    Returns:
        Dictionary mapping section_id (section.name) to ChannelOverlay:
        {
            "intro": ChannelOverlay(
                shutter=255,  # Static (open)
                color=(255, 255, 255),  # White
                gobo=0  # Open
            ),
            "chorus_1": ChannelOverlay(
                shutter=CustomCurveSpec(...),  # Strobe
                color=(255, 0, 0),  # Red
                gobo=3  # Stars
            ),
            ...
        }

    Example:
        >>> overlays = resolve_channel_overlays(
        ...     agent_implementation=implementation,
        ...     shutter_handler=shutter_handler,
        ...     color_handler=color_handler,
        ...     gobo_handler=gobo_handler,
        ...     job_config=job_config
        ... )
        >>> intro_overlay = overlays["intro"]
        >>> intro_overlay.shutter  # 255 (open)
        >>> intro_overlay.color  # (255, 255, 255) (white)
    """
    overlays = {}

    # Get job-level defaults
    defaults = job_config.channel_defaults

    for section in agent_implementation.sections:
        # Note: Sections are in bars, but handlers expect ms
        # TODO: Pass BeatGrid to convert bars→ms here, or update handlers to accept bars
        # For now, handlers receive 0,0 as they don't actually use timing (Phase 2 limitation)
        start_ms = 0
        end_ms = 0

        # Resolve shutter (returns static DMX value or ValueCurveSpec)
        shutter_pattern = defaults.shutter
        shutter = shutter_handler.resolve(
            pattern_id=shutter_pattern,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        # Resolve color (returns RGB tuple or DMX value)
        color_preset = defaults.color
        color = color_handler.resolve(
            preset_id=color_preset,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        # Resolve gobo (returns static DMX value)
        gobo_pattern = defaults.gobo
        gobo = gobo_handler.resolve(
            pattern_id=gobo_pattern,
            start_ms=start_ms,
            end_ms=end_ms,
        )

        # Create typed overlay using section.name as key
        overlays[section.name] = ChannelOverlay(
            shutter=shutter,
            color=color,
            gobo=gobo,
        )

    return overlays
