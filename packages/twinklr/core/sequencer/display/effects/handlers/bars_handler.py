"""Bars effect handler.

Animated horizontal or vertical bars sweeping across the display.
Excellent for rhythm-driven patterns and multi-target fixtures.
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


class BarsHandler:
    """Handler for the xLights 'Bars' effect.

    Produces animated sweeping bars across the display. Supports:
    - Bar count
    - Direction (Left, Right, Up, Down, Alternate Up, Alternate Down,
      Alternate Left, Alternate Right)
    - Highlight and 3D shading
    - Cycle count
    """

    @property
    def effect_type(self) -> str:
        return "Bars"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Bars effect settings.

        Supported parameters in event.parameters:
            - bar_count: int (1-100, default 5)
                Number of bars displayed.
            - direction: str (default "Left")
                Sweep direction: Left, Right, Up, Down, Alternate Up,
                Alternate Down, Alternate Left, Alternate Right.
            - highlight: bool (default False)
                Add highlight to bar edges.
            - bars_3d: bool (default False)
                Enable 3D shading on bars.
            - cycles: float (0.0-20.0, default 1.0)
                Number of animation cycles.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Bars settings string.
        """
        params = event.parameters

        bar_count = params.get("bar_count", 5)
        direction = params.get("direction", "Left")
        highlight = params.get("highlight", False)
        bars_3d = params.get("bars_3d", False)
        cycles = params.get("cycles", 1.0)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Bars_BarCount", bar_count)
        builder.add("E_CHOICE_Bars_Direction", direction)
        builder.add("E_CHECKBOX_Bars_Highlight", 1 if highlight else 0)
        builder.add("E_CHECKBOX_Bars_3D", 1 if bars_3d else 0)
        builder.add("E_TEXTCTRL_Bars_Cycles", cycles)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Bars",
        )


__all__ = ["BarsHandler"]
