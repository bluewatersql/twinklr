"""Color Wash effect handler.

Gradient fill effect — the most common background/ambient effect
in xLights. Supports horizontal/vertical direction, cycling, and
shimmer modifiers.
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


class ColorWashHandler:
    """Handler for the xLights 'Color Wash' effect.

    Produces a gradient fill across the model. Supports:
    - Horizontal/vertical direction
    - Color cycling with configurable speed
    - Shimmer modifier
    """

    @property
    def effect_type(self) -> str:
        return "Color Wash"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Color Wash effect settings.

        Supported parameters in event.parameters:
            - horizontal_fade: bool (default True)
            - vertical_fade: bool (default False)
            - shimmer: bool (default False)
            - cycles: float (default 1.0)
            - speed: int (1-100, default 50)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Color Wash settings string.
        """
        params = event.parameters

        h_fade = params.get("horizontal_fade", True)
        v_fade = params.get("vertical_fade", False)
        shimmer = params.get("shimmer", False)
        cycles = params.get("cycles", 1.0)
        speed = params.get("speed", 50)

        builder = SettingsStringBuilder()
        builder.add("E_CHECKBOX_ColorWash_HFade", 1 if h_fade else 0)
        builder.add("E_CHECKBOX_ColorWash_VFade", 1 if v_fade else 0)
        builder.add("E_CHECKBOX_ColorWash_Shimmer", 1 if shimmer else 0)
        builder.add("E_TEXTCTRL_ColorWash_Cycles", cycles)
        builder.add("E_SLIDER_ColorWash_Speed", speed)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Color Wash",
        )


__all__ = ["ColorWashHandler"]
