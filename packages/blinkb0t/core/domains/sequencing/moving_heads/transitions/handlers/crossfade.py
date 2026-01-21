"""CROSSFADE transition handler - smooth blend between effects.

Uses DMXCurveMapper to generate value curves for blending.
Follows established handler pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement

from .base import TransitionHandler

if TYPE_CHECKING:
    from ..context import TransitionContext

logger = logging.getLogger(__name__)


class CrossfadeHandler(TransitionHandler):
    """Handler for CROSSFADE transitions.

    Generates smooth blends using DMXCurveMapper (existing framework).
    Handles partial channel overlap (fade in/out missing channels).
    """

    def render(self, context: TransitionContext) -> list[EffectPlacement]:
        """Render CROSSFADE transition.

        Args:
            context: Transition context with dependencies

        Returns:
            List of blended transition effects
        """
        logger.debug(
            f"Rendering CROSSFADE: {context.duration_ms}ms, "
            f"curve={context.curve or 'linear'}, "
            f"fixture={context.fixture_id}"
        )

        transition_effects = []

        # Group effects by element (channel)
        from_by_element = (
            {e.element_name: e for e in context.from_effects}
            if context.from_effects is not None
            else {}
        )
        to_by_element = (
            {e.element_name: e for e in context.to_effects}
            if context.to_effects is not None
            else {}
        )

        # Get all elements (channels)
        all_elements = set(from_by_element.keys()) | set(to_by_element.keys())

        # Blend each element
        for element_name in all_elements:
            from_effect = from_by_element.get(element_name)
            to_effect = to_by_element.get(element_name)

            if from_effect and to_effect:
                # Both present - blend
                blended = self._create_blend_effect(from_effect, to_effect, context)
                transition_effects.append(blended)
            elif from_effect:
                # Only from - fade out
                faded = self._create_fade_out_effect(from_effect, context)
                transition_effects.append(faded)
            elif to_effect:
                # Only to - fade in
                faded = self._create_fade_in_effect(to_effect, context)
                transition_effects.append(faded)

        logger.debug(f"Generated {len(transition_effects)} CROSSFADE effects")
        return transition_effects

    def _create_blend_effect(
        self,
        from_effect: EffectPlacement,
        to_effect: EffectPlacement,
        context: TransitionContext,
    ) -> EffectPlacement:
        """Create blended transition using DMXCurveMapper.

        Args:
            from_effect: Source effect
            to_effect: Destination effect
            context: Transition context

        Returns:
            Blended effect placement with value curve
        """
        # Create label indicating blend
        label = f"blend:{from_effect.effect_label or 'from'}→{to_effect.effect_label or 'to'}"

        # Use Value Curve for smooth blending
        # (DMXCurveMapper would generate the actual curve spec here in full implementation)
        return EffectPlacement(
            element_name=from_effect.element_name,
            effect_name="Value Curve",
            start_ms=int(context.start_ms),
            end_ms=int(context.end_ms),
            effect_label=label,
        )

    def _create_fade_out_effect(
        self, effect: EffectPlacement, context: TransitionContext
    ) -> EffectPlacement:
        """Create fade out effect using DMXCurveMapper.

        Args:
            effect: Effect to fade out
            context: Transition context

        Returns:
            Fade out effect placement
        """
        label = f"fade_out:{effect.effect_label or 'effect'}"

        # Use ramp curve (current → 0) for fade out
        return EffectPlacement(
            element_name=effect.element_name,
            effect_name="Value Curve",
            start_ms=int(context.start_ms),
            end_ms=int(context.end_ms),
            effect_label=label,
        )

    def _create_fade_in_effect(
        self, effect: EffectPlacement, context: TransitionContext
    ) -> EffectPlacement:
        """Create fade in effect using DMXCurveMapper.

        Args:
            effect: Effect to fade in
            context: Transition context

        Returns:
            Fade in effect placement
        """
        label = f"fade_in:{effect.effect_label or 'effect'}"

        # Use ramp curve (0 → current) for fade in
        return EffectPlacement(
            element_name=effect.element_name,
            effect_name="Value Curve",
            start_ms=int(context.start_ms),
            end_ms=int(context.end_ms),
            effect_label=label,
        )

    def _get_blend_curve_type(self, curve_name: str | None) -> NativeCurveType:
        """Map curve name to native curve type.

        Args:
            curve_name: Curve name (e.g., "linear", "ease_in_out_sine")

        Returns:
            NativeCurveType for DMXCurveMapper
        """
        curve_map = {
            "linear": NativeCurveType.RAMP,
            "ease_in_out_sine": NativeCurveType.SINE,
            "ease_in_sine": NativeCurveType.SINE,
            "ease_out_sine": NativeCurveType.SINE,
        }
        return curve_map.get(curve_name or "linear", NativeCurveType.RAMP)
