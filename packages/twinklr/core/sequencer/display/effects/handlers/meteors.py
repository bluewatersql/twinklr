"""Meteors effect handler.

Falling meteor/spark shower — trails of light streaming in a
direction. Common for spark shower accent effects.
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


class MeteorsHandler:
    """Handler for the xLights 'Meteors' effect.

    Produces streaming meteor trails. Supports direction, speed,
    count, trail length, and music reactivity.
    """

    @property
    def effect_type(self) -> str:
        return "Meteors"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Meteors effect settings.

        Supported parameters in event.parameters:
            - count: int (1-200, default 10)
            - length: int (1-100, default 25)
            - speed: int (1-50, default 10)
            - swirl_intensity: int (0-100, default 0)
            - direction: str (default "Down")
              Options: "Down", "Up", "Left", "Right", "Explode", "Implode"
            - color_type: str (default "Palette")
              Options: "Palette", "Rainbow"
            - music_reactive: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Meteors settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Meteors_Count", params.get("count", 10))
        builder.add("E_SLIDER_Meteors_Length", params.get("length", 25))
        builder.add("E_SLIDER_Meteors_Speed", params.get("speed", 10))
        builder.add("E_SLIDER_Meteors_Swirl_Intensity", params.get("swirl_intensity", 0))
        builder.add("E_CHOICE_Meteors_Effect", params.get("direction", "Down"))
        builder.add("E_CHOICE_Meteors_Type", params.get("color_type", "Palette"))
        builder.add(
            "E_CHECKBOX_Meteors_UseMusic",
            1 if params.get("music_reactive", False) else 0,
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Meteors",
        )


__all__ = ["MeteorsHandler"]
