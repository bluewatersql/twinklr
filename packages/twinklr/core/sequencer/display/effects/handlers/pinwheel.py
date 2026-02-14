"""Pinwheel effect handler.

Rotating pinwheel/windmill pattern. Eye-catching for star toppers,
mega trees, and any circular display element that benefits from
rotational motion.
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


class PinwheelHandler:
    """Handler for the xLights 'Pinwheel' effect.

    Produces a rotating pinwheel pattern. Supports:
    - Number of arms
    - Arm size and thickness
    - Rotation speed and direction
    - Twist amount
    - 3D shading style
    """

    @property
    def effect_type(self) -> str:
        return "Pinwheel"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Pinwheel effect settings.

        Supported parameters in event.parameters:
            - arms: int (1-20, default 3)
                Number of pinwheel arms.
            - arm_size: int (1-400, default 100)
                Size of each arm.
            - twist: int (-300 to 300, default 0)
                Twist/spiral amount per arm.
            - thickness: int (0-100, default 50)
                Arm thickness as percentage of segment.
            - speed: int (0-50, default 10)
                Rotation speed.
            - offset: int (0-360, default 0)
                Starting rotation offset in degrees.
            - style: str (default "New Render Method")
                Rendering style.
            - clockwise: bool (default True)
                Rotation direction.
            - 3d: str (default "none")
                3D shading style: "none", "3D", "3D Inverted",
                "Pinwheel 3D".

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Pinwheel settings string.
        """
        params = event.parameters

        arms = params.get("arms", 3)
        arm_size = params.get("arm_size", 100)
        twist = params.get("twist", 0)
        thickness = params.get("thickness", 50)
        speed = params.get("speed", 10)
        offset = params.get("offset", 0)
        style = params.get("style", "New Render Method")
        clockwise = params.get("clockwise", True)
        shading_3d = params.get("3d", "none")

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Pinwheel_Arms", arms)
        builder.add("E_SLIDER_Pinwheel_ArmSize", arm_size)
        builder.add("E_SLIDER_Pinwheel_Twist", twist)
        builder.add("E_SLIDER_Pinwheel_Thickness", thickness)
        builder.add("E_SLIDER_Pinwheel_Speed", speed)
        builder.add("E_SLIDER_Pinwheel_Offset", offset)
        builder.add("E_CHOICE_Pinwheel_Style", style)
        builder.add(
            "E_CHECKBOX_Pinwheel_Rotation",
            1 if clockwise else 0,
        )
        builder.add("E_CHOICE_Pinwheel_3D", shading_3d)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Pinwheel",
        )


__all__ = ["PinwheelHandler"]
