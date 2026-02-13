"""Fan effect handler.

Radial fan/blade pattern — rotating blades emanating from a center
point. Common for radial ray motifs and accent effects.
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


class FanHandler:
    """Handler for the xLights 'Fan' effect.

    Produces a radial fan pattern with configurable blades,
    rotation, and center position.
    """

    @property
    def effect_type(self) -> str:
        return "Fan"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Fan effect settings.

        Supported parameters in event.parameters:
            - num_blades: int (1-50, default 16)
            - blade_width: int (0-100, default 42)
            - revolutions: int (0-500, default 276)
            - start_angle: int (0-360, default 0)
            - start_radius: int (0-250, default 1)
            - end_radius: int (0-2500, default 250)
            - center_x: int (0-100, default 50)
            - center_y: int (0-100, default 50)
            - duration: int (0-100, default 100)
            - num_elements: int (1-4, default 1)
            - blend_edges: bool (default True)
            - reverse: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Fan settings string.
        """
        params = event.parameters

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Fan_Num_Blades", params.get("num_blades", 16))
        builder.add("E_SLIDER_Fan_Blade_Width", params.get("blade_width", 42))
        builder.add("E_SLIDER_Fan_Revolutions", params.get("revolutions", 276))
        builder.add("E_SLIDER_Fan_Start_Angle", params.get("start_angle", 0))
        builder.add("E_SLIDER_Fan_Start_Radius", params.get("start_radius", 1))
        builder.add("E_SLIDER_Fan_End_Radius", params.get("end_radius", 250))
        builder.add("E_SLIDER_Fan_CenterX", params.get("center_x", 50))
        builder.add("E_SLIDER_Fan_CenterY", params.get("center_y", 50))
        builder.add("E_SLIDER_Fan_Duration", params.get("duration", 100))
        builder.add("E_SLIDER_Fan_Num_Elements", params.get("num_elements", 1))
        builder.add(
            "E_CHECKBOX_Fan_Blend_Edges",
            1 if params.get("blend_edges", True) else 0,
        )
        builder.add(
            "E_CHECKBOX_Fan_Reverse",
            1 if params.get("reverse", False) else 0,
        )
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Fan",
        )


__all__ = ["FanHandler"]
