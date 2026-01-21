"""
Transition type resolution by priority.

This module provides the TransitionResolver class which determines which
transition handler to use when multiple transition configs apply to the
same gap.

Priority System:
    1. transition_in_config (highest priority)
    2. transition_out_config
    3. gap_fill (fallback)

Example:
    >>> resolver = TransitionResolver()
    >>> handler_name = resolver.resolve_transition_type(gap)
    >>> # Returns: "crossfade", "fade_through_black", "snap", or "gap_fill"
"""

from __future__ import annotations

import logging

from blinkb0t.core.domains.sequencing.models.templates import TransitionConfig, TransitionMode
from blinkb0t.core.domains.sequencing.models.transitions import TimelineGap

logger = logging.getLogger(__name__)


# Map TransitionMode enum to handler names
TRANSITION_MODE_TO_HANDLER = {
    TransitionMode.SNAP: "snap",
    TransitionMode.CROSSFADE: "crossfade",
    TransitionMode.FADE_THROUGH_BLACK: "fade_through_black",
}


class TransitionResolver:
    """
    Resolves transition type when multiple configs apply.

    Uses a priority system to determine which transition handler should
    be used for a gap:

    Priority System:
        1. Explicit transition_in (highest) - transition TO the next effect
        2. Explicit transition_out - transition FROM the previous effect
        3. Gap fill (fallback) - implicit gap (sequence start/end, etc.)

    Methods:
        resolve_transition_type: Determine handler name by priority
        get_transition_config: Get winning transition config

    Example:
        >>> resolver = TransitionResolver()
        >>> # Gap with both configs - transition_in wins
        >>> handler = resolver.resolve_transition_type(gap)
        >>> print(handler)  # "crossfade" (from transition_in)
    """

    def resolve_transition_type(self, gap: TimelineGap) -> str:
        """
        Determine which handler to use.

        Applies priority system:
        1. transition_in_config (if present)
        2. transition_out_config (if present)
        3. "gap_fill" (fallback)

        Args:
            gap: TimelineGap with potential transition configs

        Returns:
            Handler name: "crossfade", "fade_through_black", "snap", or "gap_fill"

        Example:
            >>> gap = TimelineGap(
            ...     ...,
            ...     transition_in_config=TransitionConfig(mode=TransitionMode.CROSSFADE, ...),
            ...     transition_out_config=TransitionConfig(mode=TransitionMode.SNAP, ...)
            ... )
            >>> resolver.resolve_transition_type(gap)
            'crossfade'  # transition_in wins
        """
        # Priority 1: transition_in
        if gap.transition_in_config:
            handler = TRANSITION_MODE_TO_HANDLER[gap.transition_in_config.mode]
            logger.debug(f"Gap {gap.start_ms}-{gap.end_ms}ms: Using transition_in ({handler})")
            return handler

        # Priority 2: transition_out
        if gap.transition_out_config:
            handler = TRANSITION_MODE_TO_HANDLER[gap.transition_out_config.mode]
            logger.debug(f"Gap {gap.start_ms}-{gap.end_ms}ms: Using transition_out ({handler})")
            return handler

        # Priority 3: Gap fill
        logger.debug(f"Gap {gap.start_ms}-{gap.end_ms}ms: No transition config, using gap_fill")
        return "gap_fill"

    def get_transition_config(self, gap: TimelineGap) -> TransitionConfig | None:
        """
        Get the winning transition config by priority.

        Returns the config that would be used according to the priority system,
        or None if no explicit transition config is present (gap fill case).

        Args:
            gap: TimelineGap with potential transition configs

        Returns:
            TransitionConfig or None

        Example:
            >>> config = resolver.get_transition_config(gap)
            >>> if config:
            ...     print(f"Duration: {config.duration_bars} bars")
        """
        # Priority order: in > out > None
        return gap.transition_in_config or gap.transition_out_config
