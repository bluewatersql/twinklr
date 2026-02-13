"""Twinkle effect handler.

Random twinkling lights — gentle, distributed flicker.
Common for sparkle/starfield base and rhythm patterns.
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


class TwinkleHandler:
    """Handler for the xLights 'Twinkle' effect.

    Produces a twinkling/sparkle pattern with configurable density
    and speed. Supports strobe mode for more aggressive flicker.
    """

    @property
    def effect_type(self) -> str:
        return "Twinkle"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Twinkle effect settings.

        Supported parameters in event.parameters:
            - count: int (1-100, default 3)
            - steps: int (1-100, default 30)
            - strobe: bool (default False)
            - re_random: bool (default False)
            - style: str (default "New Render Method")

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Twinkle settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Twinkle_Count", params.get("count", 3))
        builder.add("E_SLIDER_Twinkle_Steps", params.get("steps", 30))
        builder.add(
            "E_CHECKBOX_Twinkle_Strobe",
            1 if params.get("strobe", False) else 0,
        )
        builder.add(
            "E_CHECKBOX_Twinkle_ReRandom",
            1 if params.get("re_random", False) else 0,
        )
        builder.add(
            "E_CHOICE_Twinkle_Style",
            params.get("style", "New Render Method"),
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Twinkle",
        )


__all__ = ["TwinkleHandler"]
