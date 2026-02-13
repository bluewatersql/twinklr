"""Snowflakes effect handler.

Falling snowflake particles — a winter/holiday staple.
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


class SnowflakesHandler:
    """Handler for the xLights 'Snowflakes' effect.

    Produces falling snowflake particles with configurable count,
    speed, and shape type.
    """

    @property
    def effect_type(self) -> str:
        return "Snowflakes"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Snowflakes effect settings.

        Supported parameters in event.parameters:
            - count: int (0-200, default 100)
            - speed: int (0-100, default 50)
            - snowflake_type: int (0-5, default 1)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Snowflakes settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Snowflakes_Count", params.get("count", 100))
        builder.add("E_SLIDER_Snowflakes_Speed", params.get("speed", 50))
        builder.add("E_SLIDER_Snowflakes_Type", params.get("snowflake_type", 1))
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Snowflakes",
        )


__all__ = ["SnowflakesHandler"]
