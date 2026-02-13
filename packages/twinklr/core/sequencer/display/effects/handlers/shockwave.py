"""Shockwave effect handler.

Expanding ring pattern — a ring grows outward from a center point.
Common for burst/explosion accent effects.
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


class ShockwaveHandler:
    """Handler for the xLights 'Shockwave' effect.

    Produces an expanding ring from a center point. Supports
    configurable start/end radius, ring width, and acceleration.
    """

    @property
    def effect_type(self) -> str:
        return "Shockwave"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Shockwave effect settings.

        Supported parameters in event.parameters:
            - start_radius: int (0-250, default 1)
            - end_radius: int (0-250, default 250)
            - start_width: int (0-255, default 99)
            - end_width: int (0-255, default 10)
            - center_x: int (0-100, default 50)
            - center_y: int (0-100, default 50)
            - accel: int (-10 to 10, default 0)
            - blend_edges: bool (default True)
            - scale: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Shockwave settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Shockwave_Start_Radius", params.get("start_radius", 1))
        builder.add("E_SLIDER_Shockwave_End_Radius", params.get("end_radius", 250))
        builder.add("E_SLIDER_Shockwave_Start_Width", params.get("start_width", 99))
        builder.add("E_SLIDER_Shockwave_End_Width", params.get("end_width", 10))
        builder.add("E_SLIDER_Shockwave_CenterX", params.get("center_x", 50))
        builder.add("E_SLIDER_Shockwave_CenterY", params.get("center_y", 50))
        builder.add("E_SLIDER_Shockwave_Accel", params.get("accel", 0))
        builder.add(
            "E_CHECKBOX_Shockwave_Blend_Edges",
            1 if params.get("blend_edges", True) else 0,
        )
        builder.add(
            "E_CHECKBOX_Shockwave_Scale",
            1 if params.get("scale", False) else 0,
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Shockwave",
        )


__all__ = ["ShockwaveHandler"]
