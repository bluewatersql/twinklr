"""Fireworks effect handler.

Animated fireworks explosions. High-energy burst effect perfect for
dramatic accent moments and celebration sequences.
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


class FireworksHandler:
    """Handler for the xLights 'Fireworks' effect.

    Produces animated fireworks explosions. Supports:
    - Number of explosions
    - Particle count and velocity
    - Fade rate
    - Music-reactive mode
    """

    @property
    def effect_type(self) -> str:
        return "Fireworks"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Fireworks effect settings.

        Supported parameters in event.parameters:
            - num_explosions: int (1-20, default 5)
                Number of simultaneous explosions.
            - count: int (1-100, default 50)
                Number of particles per explosion.
            - velocity: int (0-100, default 50)
                Particle launch velocity.
            - fade: int (0-100, default 30)
                Particle fade rate.
            - use_music: bool (default False)
                Trigger explosions on music beats.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Fireworks settings string.
        """
        params = event.parameters

        num_explosions = params.get("num_explosions", 5)
        count = params.get("count", 50)
        velocity = params.get("velocity", 50)
        fade = params.get("fade", 30)
        use_music = params.get("use_music", False)

        builder = SettingsStringBuilder()
        builder.add("E_SLIDER_Fireworks_Num_Explosions", num_explosions)
        builder.add("E_SLIDER_Fireworks_Count", count)
        builder.add("E_SLIDER_Fireworks_Velocity", velocity)
        builder.add("E_SLIDER_Fireworks_Fade", fade)
        builder.add("E_CHECKBOX_Fireworks_UseMusic", 1 if use_music else 0)
        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Fireworks",
        )


__all__ = ["FireworksHandler"]
