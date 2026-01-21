"""Transition renderer orchestrator.

Thin orchestration layer that coordinates transition handlers.
Follows established PatternStepProcessor pattern.
Uses dependency injection, no inline creation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.timing.resolver import TimeResolver
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.models.templates import TransitionMode
from blinkb0t.core.domains.sequencing.moving_heads.transitions.context import TransitionContext
from blinkb0t.core.domains.sequencing.moving_heads.transitions.registry import (
    TransitionHandlerRegistry,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TransitionRenderer:
    """Orchestrator for transition rendering.

    Follows established architectural patterns:
    - Dependency injection (all dependencies passed in)
    - Delegates to handlers via registry
    - No inline component creation
    - Thin orchestration layer

    Example:
        renderer = TransitionRenderer(
            time_resolver=time_resolver,
            dmx_curve_mapper=dmx_curve_mapper
        )

        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,
            from_effects=step1_effects,
            to_effects=step2_effects,
            fixture_id="MH1",
            transition_start_ms=1000,
            curve="ease_in_out_sine"
        )
    """

    def __init__(
        self,
        time_resolver: TimeResolver,
        dmx_curve_mapper: DMXCurveMapper,
    ):
        """Initialize renderer with injected dependencies.

        Args:
            time_resolver: Timing resolution for musical time
            dmx_curve_mapper: Curve mapper for value curve generation
        """
        self.time_resolver = time_resolver
        self.dmx_curve_mapper = dmx_curve_mapper

        # Create handler registry (manages all transition handlers)
        self.registry = TransitionHandlerRegistry()

        logger.debug("TransitionRenderer initialized with proper DI")

    def render_gap(
        self,
        mode_str: str,
        start_ms: float,
        end_ms: float,
        from_position: tuple[float, float] | None,
        to_position: tuple[float, float] | None,
        fixture_id: str,
        curve: str | None = None,
    ) -> list[EffectPlacement]:
        """Render gap filling transition using anchor positions.

        New unified approach for gap filling that uses calculated anchor
        positions instead of requiring full effects.

        Args:
            mode_str: Handler mode string ("gap_fill", "crossfade", etc.)
            start_ms: Gap start time in milliseconds
            end_ms: Gap end time in milliseconds
            from_position: Starting anchor position as (pan_deg, tilt_deg) or None
            to_position: Target anchor position as (pan_deg, tilt_deg) or None
            fixture_id: Fixture identifier
            curve: Optional easing curve

        Returns:
            List of EffectPlacement objects for gap filling
        """
        duration_ms = end_ms - start_ms

        # Build context for gap filling
        context = TransitionContext(
            mode=mode_str,
            duration_bars=0.0,  # Not used for gap filling
            curve=curve,
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
            from_position=from_position,
            to_position=to_position,
            from_effects=None,
            to_effects=None,
            fixture_id=fixture_id,
            dmx_curve_mapper=self.dmx_curve_mapper,
            time_resolver=self.time_resolver,
        )

        # Get handler from registry
        handler = self.registry.get_handler(mode_str)

        # Delegate to handler
        logger.debug(
            f"Rendering gap: {mode_str} from {from_position} to {to_position} "
            f"({start_ms:.0f}-{end_ms:.0f}ms, {duration_ms:.0f}ms)"
        )
        effects = handler.render(context)

        logger.debug(f"Gap fill complete: {len(effects)} effects generated")
        return effects

    def render_transition(
        self,
        mode: TransitionMode,
        duration_bars: float,
        from_effects: list[EffectPlacement],
        to_effects: list[EffectPlacement],
        fixture_id: str,
        transition_start_ms: int,
        curve: str | None = None,
    ) -> list[EffectPlacement]:
        """Render transition between two sets of effects.

        Orchestrates transition rendering by:
        1. Converting TransitionMode to mode string
        2. Resolving duration from bars to milliseconds
        3. Building TransitionContext with dependencies
        4. Dispatching to appropriate handler via registry
        5. Returning generated effects

        Args:
            mode: Transition mode enum
            duration_bars: Transition duration in musical bars
            from_effects: Effects from previous step
            to_effects: Effects from next step
            fixture_id: Fixture identifier
            transition_start_ms: Start time of transition (absolute ms)
            curve: Optional easing curve (e.g., "ease_in_out_sine")

        Returns:
            List of transition effect placements

        Raises:
            ValueError: If transition mode is unknown
        """
        # Convert enum to string
        mode_str = self._mode_to_string(mode)

        # Resolve duration from bars to milliseconds
        duration_ms = self._resolve_duration(duration_bars, transition_start_ms)
        end_ms = transition_start_ms + duration_ms

        # Build context with all dependencies
        context = TransitionContext(
            mode=mode_str,
            duration_bars=duration_bars,
            curve=curve,
            start_ms=float(transition_start_ms),
            end_ms=float(end_ms),
            duration_ms=float(duration_ms),
            from_effects=from_effects,
            to_effects=to_effects,
            fixture_id=fixture_id,
            dmx_curve_mapper=self.dmx_curve_mapper,
            time_resolver=self.time_resolver,
        )

        # Get handler from registry
        handler = self.registry.get_handler(mode_str)

        # Delegate to handler
        logger.debug(f"Delegating {mode_str} transition to handler: {handler.__class__.__name__}")
        effects = handler.render(context)

        logger.debug(
            f"Transition rendering complete: {len(effects)} effects generated "
            f"for {mode_str} transition"
        )
        return effects

    def _mode_to_string(self, mode: TransitionMode) -> str:
        """Convert TransitionMode enum to string.

        Args:
            mode: TransitionMode enum value

        Returns:
            Mode string for handler lookup
        """
        mode_map = {
            TransitionMode.SNAP: "snap",
            TransitionMode.CROSSFADE: "crossfade",
            TransitionMode.FADE_THROUGH_BLACK: "fade_through_black",
        }
        return mode_map.get(mode, "snap")

    def _resolve_duration(self, duration_bars: float, start_ms: int) -> int:
        """Resolve musical duration to milliseconds.

        Uses TimeResolver to convert bars → ms.

        Args:
            duration_bars: Duration in musical bars
            start_ms: Start time for context

        Returns:
            Duration in milliseconds
        """
        # Convert bars to ms using time resolver
        end_ms = self.time_resolver.bars_to_ms(duration_bars)
        return int(end_ms)
