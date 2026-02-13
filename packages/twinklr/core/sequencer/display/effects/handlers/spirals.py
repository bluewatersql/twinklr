"""Spirals effect handler.

Spiral/candy-stripe pattern — rotating bands of color. Common for
candy stripe motifs and rhythmic spiral animations.
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


class SpiralsHandler:
    """Handler for the xLights 'Spirals' effect.

    Produces rotating spiral bands. Supports:
    - Number of spirals (arms)
    - Movement speed and direction
    - Band thickness
    - 3D shading and blending
    """

    @property
    def effect_type(self) -> str:
        return "Spirals"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Spirals effect settings.

        Supported parameters in event.parameters:
            - palette_count: int (1-10, default 3)
            - movement: float (-5.0 to 5.0, default 1.0)
            - rotation: int (-300 to 300, default 20)
            - thickness: int (0-100, default 50)
            - blend: bool (default False)
            - 3d: bool (default False)
            - grow: bool (default False)
            - shrink: bool (default False)

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Spirals settings string.
        """
        params = event.parameters

        palette_count = params.get("palette_count", 3)
        movement = params.get("movement", 1.0)
        rotation = params.get("rotation", 20)
        thickness = params.get("thickness", 50)
        blend = params.get("blend", False)
        shading_3d = params.get("3d", False)
        grow = params.get("grow", False)
        shrink = params.get("shrink", False)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Spirals_Count", palette_count)
        builder.add("E_SLIDER_Spirals_Movement", movement)
        builder.add("E_SLIDER_Spirals_Rotation", rotation)
        builder.add("E_SLIDER_Spirals_Thickness", thickness)
        builder.add("E_CHECKBOX_Spirals_Blend", 1 if blend else 0)
        builder.add("E_CHECKBOX_Spirals_3D", 1 if shading_3d else 0)
        builder.add("E_CHECKBOX_Spirals_Grow", 1 if grow else 0)
        builder.add("E_CHECKBOX_Spirals_Shrink", 1 if shrink else 0)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Spirals",
        )


__all__ = ["SpiralsHandler"]
