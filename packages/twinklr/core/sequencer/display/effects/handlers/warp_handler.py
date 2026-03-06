"""Warp effect handler.

Animated warp/distortion effect. Produces sweeping displacement effects
ideal for high-energy transitional moments.
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


class WarpHandler:
    """Handler for the xLights 'Warp' effect.

    Produces an animated warp/distortion pattern. Supports:
    - Warp type (Plasma, Ripple, Twist, Water)
    - Treatment (Constant, In, Out)
    - X/Y position and speed
    """

    @property
    def effect_type(self) -> str:
        return "Warp"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Warp effect settings.

        Supported parameters in event.parameters:
            - warp_type: str (default "Plasma")
                Warp type: Plasma, Ripple, Twist, Water.
            - treatment: str (default "Constant")
                Animation treatment: Constant, In, Out.
            - x: int (0-100, default 50)
                X position offset.
            - y: int (0-100, default 50)
                Y position offset.
            - speed: int (0-50, default 10)
                Warp animation speed.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Warp settings string.
        """
        params = event.parameters

        warp_type = params.get("warp_type", "Plasma")
        treatment = params.get("treatment", "Constant")
        x = params.get("x", 50)
        y = params.get("y", 50)
        speed = params.get("speed", 10)

        builder = SettingsStringBuilder()
        builder.add("E_CHOICE_Warp_Type", warp_type)
        builder.add("E_CHOICE_Warp_Treatment", treatment)
        builder.add("E_SLIDER_Warp_X", x)
        builder.add("E_SLIDER_Warp_Y", y)
        builder.add("E_SLIDER_Warp_Speed", speed)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Warp",
        )


__all__ = ["WarpHandler"]
