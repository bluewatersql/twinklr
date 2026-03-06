"""Lightning effect handler.

Animated lightning bolt simulation. High-energy burst effect ideal
for dramatic accent moments and transitional segments.
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


class LightningHandler:
    """Handler for the xLights 'Lightning' effect.

    Produces animated lightning bolt patterns. Supports:
    - Number of segments
    - Top X/Y and bottom X/Y position offsets
    """

    @property
    def effect_type(self) -> str:
        return "Lightning"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Lightning effect settings.

        Supported parameters in event.parameters:
            - segments: int (1-20, default 6)
                Number of lightning segments.
            - top_x: int (0-100, default 50)
                Top anchor X position.
            - top_y: int (0-100, default 100)
                Top anchor Y position.
            - bot_x: int (0-100, default 50)
                Bottom anchor X position.
            - bot_y: int (0-100, default 0)
                Bottom anchor Y position.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Lightning settings string.
        """
        params = event.parameters

        segments = params.get("segments", 6)
        top_x = params.get("top_x", 50)
        top_y = params.get("top_y", 100)
        bot_x = params.get("bot_x", 50)
        bot_y = params.get("bot_y", 0)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Lightning_Number_Segments", segments)
        builder.add("E_SLIDER_Lightning_TopX", top_x)
        builder.add("E_SLIDER_Lightning_TopY", top_y)
        builder.add("E_SLIDER_Lightning_BOTX", bot_x)
        builder.add("E_SLIDER_Lightning_BOTY", bot_y)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Lightning",
        )


__all__ = ["LightningHandler"]
