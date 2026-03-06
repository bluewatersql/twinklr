"""Morph effect handler.

Animated morphing line between two points. Versatile transitional
effect for sweeping motion across matrices and arches.
"""

from __future__ import annotations

from twinklr.core.sequencer.display.effects.protocol import (
    EffectSettings,
    RenderContext,
)
from twinklr.core.sequencer.display.effects.settings_builder import (
    SettingsStringBuilder,
)
from twinklr.core.sequencer.display.models.render_event import RenderEvent


class MorphHandler:
    """Handler for the xLights 'Morph' effect.

    Produces an animated morphing line. Supports:
    - Start point (X1, Y1)
    - End point (X1, Y1)
    - Duration control
    """

    @property
    def effect_type(self) -> str:
        return "Morph"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Morph effect settings.

        Supported parameters in event.parameters:
            - start_x1: int (0-100, default 0)
                Start point X1 position.
            - start_y1: int (0-100, default 0)
                Start point Y1 position.
            - end_x1: int (0-100, default 100)
                End point X1 position.
            - end_y1: int (0-100, default 100)
                End point Y1 position.
            - duration: int (0-100, default 20)
                Morph head duration as percentage.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Morph settings string.
        """
        params = event.parameters

        start_x1 = params.get("start_x1", 0)
        start_y1 = params.get("start_y1", 0)
        end_x1 = params.get("end_x1", 100)
        end_y1 = params.get("end_y1", 100)
        duration = params.get("duration", 20)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Morph_Start_X1", start_x1)
        builder.add("E_SLIDER_Morph_Start_Y1", start_y1)
        builder.add("E_SLIDER_Morph_End_X1", end_x1)
        builder.add("E_SLIDER_Morph_End_Y1", end_y1)
        builder.add("E_SLIDER_MorphDuration", duration)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Morph",
        )


__all__ = ["MorphHandler"]
