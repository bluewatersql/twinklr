"""Butterfly effect handler.

Animated butterfly/kaleidoscope-like pattern. Produces symmetrical
sweeping patterns great for full matrix displays and mega trees.
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


class ButterflyHandler:
    """Handler for the xLights 'Butterfly' effect.

    Produces an animated butterfly/symmetry pattern. Supports:
    - Direction (Normal, Reverse)
    - Color scheme (Render, Rainbow, Palette)
    - Style selection (1-5)
    - Chunk count and skip
    """

    @property
    def effect_type(self) -> str:
        return "Butterfly"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Butterfly effect settings.

        Supported parameters in event.parameters:
            - direction: str (default "Normal")
                Animation direction: Normal, Reverse.
            - colors: str (default "Render")
                Color scheme: Render, Rainbow, Palette.
            - style: int (1-5, default 1)
                Butterfly style variant.
            - chunks: int (1-10, default 1)
                Number of chunks.
            - skip: int (1-10, default 1)
                Skip interval between chunks.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Butterfly settings string.
        """
        params = event.parameters

        direction = params.get("direction", "Normal")
        colors = params.get("colors", "Render")
        style = params.get("style", 1)
        chunks = params.get("chunks", 1)
        skip = params.get("skip", 1)

        builder = SettingsStringBuilder()
        builder.add("E_CHOICE_Butterfly_Direction", direction)
        builder.add("E_CHOICE_Butterfly_Colors", colors)
        builder.add("E_SLIDER_Butterfly_Style", style)
        builder.add("E_SLIDER_Butterfly_Chunks", chunks)
        builder.add("E_SLIDER_Butterfly_Skip", skip)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Butterfly",
        )


__all__ = ["ButterflyHandler"]
