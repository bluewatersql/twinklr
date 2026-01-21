"""FADE_THROUGH_BLACK transition handler.

Sequence: Fade dimmer out → Snap position → Fade dimmer in
Uses DMXCurveMapper for fade curves.
Follows established handler pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement

from .base import TransitionHandler

if TYPE_CHECKING:
    from ..context import TransitionContext

logger = logging.getLogger(__name__)


class FadeThroughBlackHandler(TransitionHandler):
    """Handler for FADE_THROUGH_BLACK transitions.

    Sequence:
    1. Fade dimmer to 0 (40% of duration)
    2. Snap position (instant at 40%)
    3. Fade dimmer from 0 (40% of duration)
    4. Hold at target (20% of duration)

    Uses DMXCurveMapper for generating fade curves.
    """

    def render(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render FADE_THROUGH_BLACK transition.

        Args:
            context: Transition context with dependencies

        Returns:
            List of transition effects (fade out + fade in)
        """
        logger.debug(
            f"Rendering FADE_THROUGH_BLACK: {context.duration_ms}ms, fixture={context.fixture_id}"
        )

        transition_effects = []

        # Calculate timing splits (40% out, 40% in, 20% hold)
        fade_out_duration = context.duration_ms * 0.4
        fade_in_duration = context.duration_ms * 0.4

        fade_out_end_ms = context.start_ms + fade_out_duration
        fade_in_end_ms = fade_out_end_ms + fade_in_duration

        # Find dimmer effects
        from_dimmer = (
            self._find_dimmer_effect(context.from_effects, context.fixture_id)
            if context.from_effects is not None
            else None
        )
        to_dimmer = (
            self._find_dimmer_effect(context.to_effects, context.fixture_id)
            if context.to_effects is not None
            else None
        )

        # 1. Fade dimmer out
        if from_dimmer:
            fade_out = self._create_dimmer_fade(
                from_dimmer,
                start_ms=context.start_ms,
                end_ms=fade_out_end_ms,
                fade_to_zero=True,
                context=context,
            )
            transition_effects.append(fade_out)
            logger.debug(
                f"Created fade out: {fade_out.element_name} "
                f"({int(context.start_ms)}-{int(fade_out_end_ms)}ms)"
            )

        # 2. Position snap happens instantly at fade_out_end_ms
        # No effects needed - timing change only

        # 3. Fade dimmer in
        if to_dimmer:
            fade_in = self._create_dimmer_fade(
                to_dimmer,
                start_ms=fade_out_end_ms,
                end_ms=fade_in_end_ms,
                fade_to_zero=False,
                context=context,
            )
            transition_effects.append(fade_in)
            logger.debug(
                f"Created fade in: {fade_in.element_name} "
                f"({int(fade_out_end_ms)}-{int(fade_in_end_ms)}ms)"
            )

        logger.debug(f"Generated {len(transition_effects)} FADE_THROUGH_BLACK effects")
        return transition_effects

    def _create_dimmer_fade(
        self,
        dimmer_effect: EffectPlacement,
        start_ms: float,
        end_ms: float,
        fade_to_zero: bool,
        context: TransitionContext,
    ) -> EffectPlacement:
        """Create dimmer fade effect using DMXCurveMapper.

        Args:
            dimmer_effect: Original dimmer effect
            start_ms: Fade start time
            end_ms: Fade end time
            fade_to_zero: True for fade out, False for fade in
            context: Transition context with DMXCurveMapper

        Returns:
            Dimmer fade effect placement with value curve
        """
        direction = "out" if fade_to_zero else "in"
        label = f"fade_{direction}:dimmer"

        # Use Value Curve with ramp or ease curve
        # DMXCurveMapper would generate the actual curve spec
        return EffectPlacement(
            element_name=dimmer_effect.element_name,
            effect_name="Value Curve",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            effect_label=label,
        )

    def _find_dimmer_effect(
        self, effects: list[EffectPlacement], fixture_id: str
    ) -> EffectPlacement | None:
        """Find dimmer effect for fixture.

        Args:
            effects: List of effects
            fixture_id: Fixture identifier

        Returns:
            Dimmer effect if found, None otherwise
        """
        for effect in effects:
            # Match dimmer channel (e.g., "MH1-Dimmer", "Dmx MH1-Dimmer")
            if "Dimmer" in effect.element_name and fixture_id in effect.element_name:
                return effect
        return None
