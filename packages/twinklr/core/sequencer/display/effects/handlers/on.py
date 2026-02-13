"""On effect handler.

The simplest xLights effect — solid color fill. Used for hits,
flashes, bells, and as the fallback for unmapped templates.
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


class OnHandler:
    """Handler for the xLights 'On' effect.

    Produces a solid color fill. Intensity is controlled via the
    event's intensity field (mapped to E_TEXTCTRL_Eff_On_End/Start).
    Supports optional shimmer modifier for subtle sparkle.
    """

    @property
    def effect_type(self) -> str:
        return "On"

    @property
    def handler_version(self) -> str:
        return "1.1.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build On effect settings.

        Supported parameters in event.parameters:
            - shimmer: bool (default False) — enables shimmer modifier.
            - shimmer_cycles: float (default 1.0) — shimmer cycle count
              (only emitted when shimmer is True).

        Args:
            event: Render event with intensity and parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with the On effect settings string.
        """
        params = event.parameters
        intensity_pct = int(event.intensity * 100)
        shimmer = params.get("shimmer", False)

        builder = SettingsStringBuilder()
        builder.add("E_TEXTCTRL_Eff_On_End", intensity_pct)
        builder.add("E_TEXTCTRL_Eff_On_Start", intensity_pct)

        if shimmer:
            builder.add("E_CHECKBOX_On_Shimmer", 1)
            shimmer_cycles = params.get("shimmer_cycles")
            if shimmer_cycles is not None:
                builder.add("E_TEXTCTRL_On_Cycles", shimmer_cycles)

        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="On",
        )


__all__ = ["OnHandler"]
