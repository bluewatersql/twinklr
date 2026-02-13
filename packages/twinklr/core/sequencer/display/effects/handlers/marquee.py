"""Marquee effect handler.

Scrolling band pattern — lights chase around the edge of a model.
Common for border/outline rhythm effects.
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


class MarqueeHandler:
    """Handler for the xLights 'Marquee' effect.

    Produces a scrolling band around the model edge. Supports
    configurable band/gap sizes, speed, stagger, and wrapping.
    """

    @property
    def effect_type(self) -> str:
        return "Marquee"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Marquee effect settings.

        Supported parameters in event.parameters:
            - band_size: int (1-100, default 39)
            - skip_size: int (0-100, default 44)
            - speed: int (0-100, default 50)
            - stagger: int (0-100, default 16)
            - start: int (0-100, default 0)
            - thickness: int (0-100, default 100)
            - reverse: bool (default False)
            - wrap_x: bool (default False)
            - wrap_y: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Marquee settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Marquee_Band_Size", params.get("band_size", 39))
        builder.add("E_SLIDER_Marquee_Skip_Size", params.get("skip_size", 44))
        builder.add("E_SLIDER_Marquee_Speed", params.get("speed", 50))
        builder.add("E_SLIDER_Marquee_Stagger", params.get("stagger", 16))
        builder.add("E_SLIDER_Marquee_Start", params.get("start", 0))
        builder.add("E_SLIDER_Marquee_Thickness", params.get("thickness", 100))
        builder.add(
            "E_CHECKBOX_Marquee_Reverse",
            1 if params.get("reverse", False) else 0,
        )
        builder.add(
            "E_CHECKBOX_Marquee_WrapX",
            1 if params.get("wrap_x", False) else 0,
        )
        builder.add(
            "E_CHECKBOX_Marquee_WrapY",
            1 if params.get("wrap_y", False) else 0,
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Marquee",
        )


__all__ = ["MarqueeHandler"]
