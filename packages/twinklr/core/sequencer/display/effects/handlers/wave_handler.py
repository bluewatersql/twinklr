"""Wave effect handler.

Animated wave pattern sweeping across the display. Great for rhythmic
flowing patterns on matrices, arches, and mega trees.
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


class WaveHandler:
    """Handler for the xLights 'Wave' effect.

    Produces an animated wave pattern. Supports:
    - Wave type (Sine, Square, Triangle, Decaying Sine, Decaying Square,
      Heartbeat, Distant Heartbeat)
    - Direction (Left, Right, Up, Down)
    - Number of waves, speed, and thickness
    """

    @property
    def effect_type(self) -> str:
        return "Wave"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Wave effect settings.

        Supported parameters in event.parameters:
            - wave_type: str (default "Sine")
                Wave shape: Sine, Square, Triangle, Decaying Sine,
                Decaying Square, Heartbeat, Distant Heartbeat.
            - direction: str (default "Left")
                Wave movement direction: Left, Right, Up, Down.
            - number_waves: int (1-20, default 3)
                Number of wave cycles visible.
            - speed: int (0-50, default 10)
                Wave scroll speed.
            - thickness: int (1-100, default 50)
                Wave thickness as percentage.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Wave settings string.
        """
        params = event.parameters

        wave_type = params.get("wave_type", "Sine")
        direction = params.get("direction", "Left")
        number_waves = params.get("number_waves", 3)
        speed = params.get("speed", 10)
        thickness = params.get("thickness", 50)

        builder = SettingsStringBuilder()
        builder.add("E_CHOICE_Wave_Type", wave_type)
        builder.add("E_CHOICE_Wave_Direction", direction)
        builder.add("E_SLIDER_Wave_Number_Waves", number_waves)
        builder.add("E_SLIDER_Wave_Speed", speed)
        builder.add("E_SLIDER_Wave_Thickness", thickness)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Wave",
        )


__all__ = ["WaveHandler"]
