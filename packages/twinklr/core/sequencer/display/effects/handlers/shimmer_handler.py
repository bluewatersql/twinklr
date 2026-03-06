"""Shimmer effect handler.

Random pixel shimmer/sparkle overlay. High-energy multi-color effect
ideal for accenting any base layer with glittery motion.
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


class ShimmerHandler:
    """Handler for the xLights 'Shimmer' effect.

    Produces a random shimmer/sparkle pattern. Supports:
    - Use all colors toggle
    - Cycle count
    """

    @property
    def effect_type(self) -> str:
        return "Shimmer"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Shimmer effect settings.

        Supported parameters in event.parameters:
            - use_all_colors: bool (default False)
                Use all palette colors simultaneously.
            - cycles: float (0.0-20.0, default 1.0)
                Number of shimmer cycles.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Shimmer settings string.
        """
        params = event.parameters

        use_all_colors = params.get("use_all_colors", False)
        cycles = params.get("cycles", 1.0)

        builder = SettingsStringBuilder()
        builder.add("E_CHECKBOX_Shimmer_Use_All_Colors", 1 if use_all_colors else 0)
        builder.add("E_TEXTCTRL_Shimmer_Cycles", cycles)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Shimmer",
        )


__all__ = ["ShimmerHandler"]
