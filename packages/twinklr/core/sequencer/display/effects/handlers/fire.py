"""Fire effect handler.

Animated fire/flame simulation. Great for warm ambient effects,
dramatic scene transitions, and "burning" Christmas display accents.
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


class FireHandler:
    """Handler for the xLights 'Fire' effect.

    Produces an animated fire/flame simulation. Supports:
    - Flame height control
    - Hue shift (for non-orange fires)
    - Growth cycling
    - Music-reactive growth
    - Location (bottom, top, left, right)
    """

    @property
    def effect_type(self) -> str:
        return "Fire"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Fire effect settings.

        Supported parameters in event.parameters:
            - height: int (1-100, default 50)
                Flame height as percentage of model.
            - hue_shift: int (0-100, default 0)
                Shift fire color away from default orange.
            - growth_cycles: float (0.0-20.0, default 0.0)
                Number of grow/shrink cycles.
            - grow_with_music: bool (default False)
                Make flame height reactive to music.
            - location: str (default "Bottom")
                Origin: Bottom, Top, Left, Right.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Fire settings string.
        """
        params = event.parameters

        height = params.get("height", 50)
        hue_shift = params.get("hue_shift", 0)
        growth_cycles = params.get("growth_cycles", 0.0)
        grow_with_music = params.get("grow_with_music", False)
        location = params.get("location", "Bottom")

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Fire_Height", height)
        builder.add("E_SLIDER_Fire_HueShift", hue_shift)
        builder.add("E_TEXTCTRL_Fire_GrowthCycles", growth_cycles)
        builder.add(
            "E_CHECKBOX_Fire_GrowWithMusic",
            1 if grow_with_music else 0,
        )
        builder.add("E_CHOICE_Fire_Location", location)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Fire",
        )


__all__ = ["FireHandler"]
