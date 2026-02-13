"""SingleStrand (Chase) effect handler.

Chase/marquee effect — lights move sequentially along a strand.
Common for rhythm-layer patterns (alternating, sequential movement).
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


class ChaseHandler:
    """Handler for the xLights 'SingleStrand' (Chase) effect.

    Produces sequential light movement along a strand. Supports:
    - Chase types: Left-Right, Right-Left, Bounce, etc.
    - Speed and color cycling
    - Group size for multi-pixel chase
    """

    @property
    def effect_type(self) -> str:
        return "SingleStrand"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build SingleStrand (Chase) effect settings.

        Supported parameters in event.parameters:
            - chase_type: str (default "Left-Right")
              Options: "Left-Right", "Right-Left", "Bounce from Left",
                       "Bounce from Right", "Dual Bounce"
            - speed: int (1-100, default 50)
            - color_chase: bool (default True)
            - group_count: int (1-50, default 1)
            - chase_rotations: float (default 1.0)
            - fade_type: str (default "None")
              Options: "None", "Fade In", "Fade Out", "In/Out"
            - colors: str (default "Palette")
              Options: "Palette", "Rainbow"

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with SingleStrand settings string.
        """
        params = event.parameters

        chase_type = params.get("chase_type", "Left-Right")
        speed = params.get("speed", 50)
        color_chase = params.get("color_chase", True)
        group_count = params.get("group_count", 1)
        rotations = params.get("chase_rotations", 1.0)
        fade_type = params.get("fade_type", "None")
        colors = params.get("colors", "Palette")

        builder = SettingsStringBuilder()
        builder.add("E_CHOICE_Chase_Type1", chase_type)
        builder.add("E_SLIDER_Chase_Speed1", speed)
        builder.add("E_CHECKBOX_Chase_Color2Color1", 1 if color_chase else 0)
        builder.add("E_SLIDER_Chase_Group_All", group_count)
        builder.add("E_SLIDER_Chase_Rotations", rotations)
        builder.add("E_CHOICE_Fade_Type", fade_type)
        builder.add("E_CHOICE_SingleStrand_Colors", colors)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="SingleStrand",
        )


__all__ = ["ChaseHandler"]
