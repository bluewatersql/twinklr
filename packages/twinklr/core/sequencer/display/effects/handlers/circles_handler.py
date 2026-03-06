"""Circles effect handler.

Animated expanding/contracting circles. Works well on matrices,
mega trees, and arches for rhythmic burst effects.
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


class CirclesHandler:
    """Handler for the xLights 'Circles' effect.

    Produces animated expanding circles. Supports:
    - Circle count
    - Circle size
    - Bounce, collide, and plasma modes
    """

    @property
    def effect_type(self) -> str:
        return "Circles"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Circles effect settings.

        Supported parameters in event.parameters:
            - count: int (1-100, default 5)
                Number of circles.
            - size: int (1-100, default 50)
                Circle size as percentage.
            - bounce: bool (default False)
                Enable bounce behaviour.
            - collide: bool (default False)
                Enable circle collision.
            - plasma: bool (default False)
                Enable plasma colouring mode.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Circles settings string.
        """
        params = event.parameters

        count = params.get("count", 5)
        size = params.get("size", 50)
        bounce = params.get("bounce", False)
        collide = params.get("collide", False)
        plasma = params.get("plasma", False)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Circles_Count", count)
        builder.add("E_SLIDER_Circles_Size", size)
        builder.add("E_CHECKBOX_Circles_Bounce", 1 if bounce else 0)
        builder.add("E_CHECKBOX_Circles_Collide", 1 if collide else 0)
        builder.add("E_CHECKBOX_Circles_Plasma", 1 if plasma else 0)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Circles",
        )


__all__ = ["CirclesHandler"]
