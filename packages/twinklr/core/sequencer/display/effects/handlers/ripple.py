"""Ripple effect handler.

Expanding concentric rings — a ripple pattern radiating outward
(or inward). Common for transition effects and rhythm visuals
that propagate across display elements.
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


class RippleHandler:
    """Handler for the xLights 'Ripple' effect.

    Produces concentric expanding/contracting rings. Supports:
    - Shape selection (Circle, Square, Triangle, Star, etc.)
    - Movement direction (Explode outward or Implode inward)
    - Ring thickness and spacing
    - Cycle count (repetitions within the effect duration)
    - Rotation, 3D shading, and velocity
    """

    @property
    def effect_type(self) -> str:
        return "Ripple"

    @property
    def handler_version(self) -> str:
        return "1.0.0"

    def build_settings(
        self,
        event: RenderEvent,
        ctx: RenderContext,
    ) -> EffectSettings:
        """Build Ripple effect settings.

        Supported parameters in event.parameters:
            - object_to_draw: str (default "Circle")
                Shape: Circle, Square, Triangle, Star, Polygon,
                Heart, Tree, Candy Cane, Snow Flake, Crucifix, Present.
            - movement: str (default "Explode")
                Explode (outward) or Implode (inward).
            - thickness: int (1-100, default 50)
                Thickness of each ripple ring.
            - cycles: float (0.1-20.0, default 1.0)
                Number of expand/contract cycles.
            - rotation: int (0-360, default 0)
                Shape rotation in degrees.
            - points: int (3-20, default 5)
                Number of points (Star, Snow Flake, Polygon only).
            - 3d: bool (default False)
                Enable 3D shading on the rings.
            - velocity: float (0.0-20.0, default 0.0)
                Movement velocity.
            - spacing: float (0.0-20.0, default 0.0)
                Spacing between rings.

        Args:
            event: Render event with parameters.
            ctx: Rendering context.

        Returns:
            EffectSettings with Ripple settings string.
        """
        params = event.parameters

        obj = params.get("object_to_draw", "Circle")
        movement = params.get("movement", "Explode")
        thickness = params.get("thickness", 50)
        cycles = params.get("cycles", 1.0)
        rotation = params.get("rotation", 0)
        points = params.get("points", 5)
        shading_3d = params.get("3d", False)
        velocity = params.get("velocity", 0.0)
        spacing = params.get("spacing", 0.0)

        builder = SettingsStringBuilder()
        builder.add("E_CHOICE_Ripple_Object_To_Draw", obj)
        builder.add("E_CHOICE_Ripple_Movement", movement)
        builder.add("E_SLIDER_Ripple_Thickness", thickness)
        builder.add("E_TEXTCTRL_Ripple_Cycles", cycles)
        builder.add("E_SLIDER_Ripple_Rotation", rotation)
        builder.add("E_SLIDER_Ripple_Points", points)
        builder.add("E_CHECKBOX_Ripple3D", 1 if shading_3d else 0)

        # Only emit velocity/spacing when non-zero to keep settings lean
        if velocity:
            builder.add("E_TEXTCTRL_Ripple_Velocity", velocity)
        if spacing:
            builder.add("E_TEXTCTRL_Ripple_Spacing", spacing)

        builder.add_buffer_style(event.buffer_style)

        if event.buffer_transform:
            builder.add_buffer_transform(event.buffer_transform)

        return EffectSettings(
            settings_string=builder.build(),
            effect_name="Ripple",
        )


__all__ = ["RippleHandler"]
