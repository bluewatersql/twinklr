"""Strobe effect handler.

Random flash pattern — rapid flashing lights. Common for
sparkle hit accents and high-energy moments.
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


class StrobeHandler:
    """Handler for the xLights 'Strobe' effect.

    Produces rapid flash patterns. Supports configurable flash
    count, duration, pattern type, and music reactivity.
    """

    @property
    def effect_type(self) -> str:
        return "Strobe"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Strobe effect settings.

        Supported parameters in event.parameters:
            - num_strobes: int (1-1000, default 300)
            - strobe_duration: int (1-100, default 1)
            - strobe_type: int (0-4, default 3)
            - music_reactive: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Strobe settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Number_Strobes", params.get("num_strobes", 300))
        builder.add("E_SLIDER_Strobe_Duration", params.get("strobe_duration", 1))
        builder.add("E_SLIDER_Strobe_Type", params.get("strobe_type", 3))
        builder.add(
            "E_CHECKBOX_Strobe_Music",
            1 if params.get("music_reactive", False) else 0,
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Strobe",
        )


__all__ = ["StrobeHandler"]
