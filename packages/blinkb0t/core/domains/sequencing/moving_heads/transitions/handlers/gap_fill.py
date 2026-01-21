"""Gap filling transition handler - Phase 3 unified approach.

Implements intelligent gap filling with smooth transitions:
- Start of sequence: Hold at home with shutter closed
- End of sequence: Hold at home with shutter closed
- Large gaps (≥5s): End → soft home → start (40/20/40 split) using transition handlers
- Small gaps (<5s): End → start (direct transition) using transition handlers

Delegates to existing transition handlers (CrossfadeHandler, etc.) for smooth motion.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement

from ..context import TransitionContext
from .base import TransitionHandler

if TYPE_CHECKING:
    from ..registry import TransitionHandlerRegistry

logger = logging.getLogger(__name__)


class GapFillHandler(TransitionHandler):
    """Handle gap filling with smooth transitions.

    Phase 3 Feature: Unified gap filling approach using transitions framework.

    Implements intelligent behavior based on gap duration:
    - Large gaps (≥5s): Three-phase transition
      * Phase 1 (40%): Smooth ramp from end position to soft home
      * Phase 2 (20%): Hold at soft home (shutter closed, dimmer off)
      * Phase 3 (40%): Smooth ramp from soft home to start position
    - Small gaps (<5s): Direct ramp from end to start position

    Handles special cases:
    - Sequence start: Ramp from soft home to first position
    - Sequence end: Ramp from last position to soft home

    Example:
        >>> handler = GapFillHandler(large_gap_threshold_ms=5000)
        >>> context = TransitionContext(
        ...     mode="gap_fill",
        ...     duration_ms=6000,  # 6 second gap
        ...     from_effects=[...],  # End of previous section
        ...     to_effects=[...],    # Start of next section
        ...     ...
        ... )
        >>> gap_effects = handler.render(context)
        >>> # Returns 3-phase transition: end→home (40%), hold (20%), home→start (40%)
    """

    def __init__(
        self,
        handler_registry: TransitionHandlerRegistry,
        large_gap_threshold_ms: int = 5000,
        soft_home_pose: tuple[float, float] = (0.0, 0.0),  # (pan_deg, tilt_deg)
    ):
        """Initialize gap fill handler.

        Args:
            handler_registry: Registry for accessing other transition handlers
            large_gap_threshold_ms: Gaps >= this use 3-phase transition (default: 5000ms)
            soft_home_pose: Soft home position in degrees (pan, tilt) (default: 0, 0)
        """
        self.registry = handler_registry
        self.large_gap_threshold_ms = large_gap_threshold_ms
        self.soft_home_pan_deg, self.soft_home_tilt_deg = soft_home_pose

        logger.debug(
            f"GapFillHandler initialized: threshold={large_gap_threshold_ms}ms, "
            f"soft_home=({self.soft_home_pan_deg}°, {self.soft_home_tilt_deg}°)"
        )

    def render(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render gap filling transition.

        Args:
            context: Transition context with gap details

        Returns:
            List of EffectPlacement objects for gap filling

        Note:
            - For large gaps: Returns 3 effects (ramp down, hold, ramp up)
            - For small gaps: Returns 1 effect (direct ramp)
            - For sequence start/end: Returns 1 effect (ramp to/from home)
        """
        gap_duration_ms = context.duration_ms

        # Determine gap type
        is_sequence_start = not context.from_effects  # No previous effects
        is_sequence_end = not context.to_effects  # No next effects
        is_large_gap = gap_duration_ms >= self.large_gap_threshold_ms

        logger.debug(
            f"Gap fill: duration={gap_duration_ms}ms, "
            f"start={is_sequence_start}, end={is_sequence_end}, large={is_large_gap}"
        )

        # Route to appropriate handler
        if is_sequence_start:
            return self._render_sequence_start(context)
        elif is_sequence_end:
            return self._render_sequence_end(context)
        elif is_large_gap:
            return self._render_large_gap(context)
        else:
            return self._render_small_gap(context)

    def _render_sequence_start(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render sequence start: soft home → first position.

        Creates hold effect at soft home position with shutter closed.

        Args:
            context: Transition context

        Returns:
            Single EffectPlacement holding at home
        """
        logger.debug(f"Rendering sequence start gap: {context.start_ms}ms → {context.end_ms}ms")

        # For sequence start, hold at soft home with shutter closed
        pan_deg = self.soft_home_pan_deg
        tilt_deg = self.soft_home_tilt_deg

        return self._create_hold_effect(
            context=context,
            pan_deg=pan_deg,
            tilt_deg=tilt_deg,
            dimmer_pct=0.0,  # Lights off
            label="gap_start",
        )

    def _render_sequence_end(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render sequence end: last position → soft home.

        Creates hold effect at soft home position with shutter closed.

        Args:
            context: Transition context

        Returns:
            Single EffectPlacement holding at home
        """
        logger.debug(f"Rendering sequence end gap: {context.start_ms}ms → {context.end_ms}ms")

        # For sequence end, hold at soft home with shutter closed
        pan_deg = self.soft_home_pan_deg
        tilt_deg = self.soft_home_tilt_deg

        return self._create_hold_effect(
            context=context,
            pan_deg=pan_deg,
            tilt_deg=tilt_deg,
            dimmer_pct=0.0,  # Lights off
            label="gap_end",
        )

    def _render_large_gap(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render large gap (≥5s): end → soft home → start (40/20/40 split).

        Three-phase transition:
        1. Phase 1 (40%): Transition from end position to soft home
        2. Phase 2 (20%): Hold at soft home (shutter closed, dimmer off)
        3. Phase 3 (40%): Transition from soft home to start position

        Args:
            context: Transition context

        Returns:
            Effects for all three phases
        """
        gap_duration_ms = context.duration_ms
        phase1_duration_ms = gap_duration_ms * 0.4  # 40%
        phase2_duration_ms = gap_duration_ms * 0.2  # 20%
        phase3_duration_ms = gap_duration_ms - phase1_duration_ms - phase2_duration_ms  # 40%

        phase1_start_ms = context.start_ms
        phase1_end_ms = phase1_start_ms + phase1_duration_ms

        phase2_start_ms = phase1_end_ms
        phase2_end_ms = phase2_start_ms + phase2_duration_ms

        phase3_start_ms = phase2_end_ms
        phase3_end_ms = context.end_ms

        logger.debug(
            f"Rendering large gap (3-phase): "
            f"phase1={phase1_duration_ms:.0f}ms, phase2={phase2_duration_ms:.0f}ms, phase3={phase3_duration_ms:.0f}ms"
        )

        all_effects = []

        # Phase 1: End → Soft Home (transition)
        if context.from_position:
            from_effects_p1 = self._create_position_effects(
                context.from_position, phase1_start_ms, context.fixture_id, "gap_from"
            )
            to_effects_p1 = self._create_position_effects(
                (self.soft_home_pan_deg, self.soft_home_tilt_deg),
                phase1_end_ms,
                context.fixture_id,
                "gap_home",
            )

            handler = self.registry.get_handler("crossfade")
            ctx_p1 = TransitionContext(
                mode="crossfade",
                duration_bars=0.0,
                curve="ease_in_out_sine",
                start_ms=phase1_start_ms,
                end_ms=phase1_end_ms,
                duration_ms=phase1_duration_ms,
                from_effects=from_effects_p1,
                to_effects=to_effects_p1,
                fixture_id=context.fixture_id,
                dmx_curve_mapper=context.dmx_curve_mapper,
                time_resolver=context.time_resolver,
            )
            all_effects.extend(handler.render(ctx_p1))

        # Phase 2: Hold at Soft Home
        hold_ctx = TransitionContext(
            mode="gap_fill",
            duration_bars=0.0,
            curve=None,
            start_ms=phase2_start_ms,
            end_ms=phase2_end_ms,
            duration_ms=phase2_duration_ms,
            fixture_id=context.fixture_id,
            dmx_curve_mapper=context.dmx_curve_mapper,
            time_resolver=context.time_resolver,
        )
        all_effects.extend(
            self._create_hold_effect(
                context=hold_ctx,
                pan_deg=self.soft_home_pan_deg,
                tilt_deg=self.soft_home_tilt_deg,
                dimmer_pct=0.0,  # Shutter closed
                label="gap_large_hold",
            )
        )

        # Phase 3: Soft Home → Start (transition)
        if context.to_position:
            from_effects_p3 = self._create_position_effects(
                (self.soft_home_pan_deg, self.soft_home_tilt_deg),
                phase3_start_ms,
                context.fixture_id,
                "gap_home",
            )
            to_effects_p3 = self._create_position_effects(
                context.to_position, phase3_end_ms, context.fixture_id, "gap_to"
            )

            handler = self.registry.get_handler("crossfade")
            ctx_p3 = TransitionContext(
                mode="crossfade",
                duration_bars=0.0,
                curve="ease_in_out_sine",
                start_ms=phase3_start_ms,
                end_ms=phase3_end_ms,
                duration_ms=phase3_duration_ms,
                from_effects=from_effects_p3,
                to_effects=to_effects_p3,
                fixture_id=context.fixture_id,
                dmx_curve_mapper=context.dmx_curve_mapper,
                time_resolver=context.time_resolver,
            )
            all_effects.extend(handler.render(ctx_p3))

        return all_effects

    def _render_small_gap(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render small gap (<5s): direct transition end → start.

        Creates smooth transition from end position to start position using crossfade.

        Args:
            context: Transition context

        Returns:
            Transition effects from end → start
        """
        logger.debug(
            f"Rendering small gap (direct transition): "
            f"{context.start_ms}ms → {context.end_ms}ms ({context.duration_ms}ms)"
        )

        # Create placeholder effects from anchor positions
        from_effects = (
            self._create_position_effects(
                context.from_position, context.start_ms, context.fixture_id, "gap_from"
            )
            if context.from_position
            else []
        )

        to_effects = (
            self._create_position_effects(
                context.to_position, context.end_ms, context.fixture_id, "gap_to"
            )
            if context.to_position
            else []
        )

        if not from_effects or not to_effects:
            logger.warning("Missing anchor positions for small gap, creating hold")
            return self._create_hold_effect(
                context=context,
                pan_deg=self.soft_home_pan_deg,
                tilt_deg=self.soft_home_tilt_deg,
                dimmer_pct=0.0,
                label="gap_small_fallback",
            )

        # Use crossfade handler for smooth transition
        handler = self.registry.get_handler("crossfade")
        transition_context = TransitionContext(
            mode="crossfade",
            duration_bars=0.0,
            curve=context.curve or "ease_in_out_sine",
            start_ms=context.start_ms,
            end_ms=context.end_ms,
            duration_ms=context.duration_ms,
            from_effects=from_effects,
            to_effects=to_effects,
            fixture_id=context.fixture_id,
            dmx_curve_mapper=context.dmx_curve_mapper,
            time_resolver=context.time_resolver,
        )

        return handler.render(transition_context)

    def _create_position_effects(
        self,
        position: tuple[float, float],
        time_ms: float,
        fixture_id: str,
        label_prefix: str,
    ) -> list[EffectPlacement]:
        """Create placeholder EffectPlacement objects from anchor position.

        Creates pan/tilt effects at specified position to feed to transition handlers.

        Args:
            position: (pan_deg, tilt_deg) anchor position
            time_ms: Time in milliseconds
            fixture_id: Fixture identifier
            label_prefix: Prefix for effect labels

        Returns:
            List of EffectPlacement objects for pan and tilt
        """
        pan_deg, tilt_deg = position

        # Create pan effect - encode position in label since EffectPlacement doesn't have position fields
        pan_effect = EffectPlacement(
            element_name=f"Dmx {fixture_id}-Pan",
            effect_name="DMX",
            start_ms=int(time_ms),
            end_ms=int(time_ms) + 1,  # Minimal duration
            effect_label=f"{label_prefix}_pan_{pan_deg:.1f}deg",
        )

        # Create tilt effect
        tilt_effect = EffectPlacement(
            element_name=f"Dmx {fixture_id}-Tilt",
            effect_name="DMX",
            start_ms=int(time_ms),
            end_ms=int(time_ms) + 1,
            effect_label=f"{label_prefix}_tilt_{tilt_deg:.1f}deg",
        )

        return [pan_effect, tilt_effect]

    def _create_hold_effect(
        self,
        context: TransitionContext,
        pan_deg: float,
        tilt_deg: float,
        dimmer_pct: float,
        label: str,
    ) -> list[EffectPlacement]:
        """Create a simple hold effect at specified position.

        Args:
            context: Transition context
            pan_deg: Pan position in degrees
            tilt_deg: Tilt position in degrees
            dimmer_pct: Dimmer percentage (0-100)
            label: Label for the effect

        Returns:
            List containing single EffectPlacement for hold
        """
        # Create simple DMX settings string for hold effect
        effect = EffectPlacement(
            element_name=f"Dmx {context.fixture_id}",
            effect_name="DMX",
            start_ms=int(context.start_ms),
            end_ms=int(context.end_ms),
            effect_label=f"{label}_{context.fixture_id}",
        )

        logger.debug(
            f"Created hold effect: {label} at ({pan_deg}°, {tilt_deg}°), "
            f"dimmer={dimmer_pct}%, duration={context.duration_ms:.0f}ms"
        )

        return [effect]
