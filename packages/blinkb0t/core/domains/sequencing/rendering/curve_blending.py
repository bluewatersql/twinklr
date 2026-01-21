"""Curve blending logic for crossfade transitions.

Extracted from curve_pipeline.py to reduce complexity and improve maintainability.
Handles all blending operations between adjacent effects.
"""

from __future__ import annotations

from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.utils.logging import get_logger

from .models import RenderedEffect, SequencedEffect

logger = get_logger(__name__)


class CurveBlender:
    """Handles curve blending for crossfade transitions.

    Responsibilities:
    - Extract transition configuration (mode, duration)
    - Interpolate within curves
    - Blend curve pairs at boundaries
    - Apply crossfade to all channels

    This class contains the mathematical operations for blending curves,
    extracted from CurvePipeline to reduce its complexity.
    """

    def get_transition_mode(
        self,
        curr: SequencedEffect,
        next_effect: SequencedEffect,
    ) -> str:
        """Get transition mode between two effects.

        Checks boundary_info for transition configurations:
        1. curr.boundary_info.exit_transition.mode (highest priority)
        2. next_effect.boundary_info.entry_transition.mode
        3. Default to "SNAP" if neither exists

        Args:
            curr: Current effect
            next_effect: Next effect

        Returns:
            Transition mode string ("SNAP", "CROSSFADE", etc.)

        Example:
            >>> mode = blender.get_transition_mode(effect1, effect2)
            >>> assert mode in ["SNAP", "CROSSFADE", "FADE_THROUGH_BLACK"]
        """
        # Check exit transition (highest priority)
        if curr.boundary_info and curr.boundary_info.exit_transition:
            exit_mode: str = curr.boundary_info.exit_transition.mode.value
            return exit_mode.upper()

        # Check entry transition
        if next_effect.boundary_info and next_effect.boundary_info.entry_transition:
            entry_mode: str = next_effect.boundary_info.entry_transition.mode.value
            return entry_mode.upper()

        # Default to SNAP
        return "SNAP"

    def get_blend_duration(
        self,
        curr: SequencedEffect,
        next_effect: SequencedEffect,
    ) -> int:
        """Get blend duration in milliseconds between two effects.

        Checks transition configurations for duration specification:
        1. curr.boundary_info.exit_transition.duration_bars (convert to ms)
        2. next_effect.boundary_info.entry_transition.duration_bars
        3. Default to 500ms if not specified

        Note: For Phase 4, we use a fixed 500ms default. Full beat_grid
        conversion will be added in future phases.

        Args:
            curr: Current effect
            next_effect: Next effect

        Returns:
            Blend duration in milliseconds

        Example:
            >>> duration = blender.get_blend_duration(effect1, effect2)
            >>> assert duration >= 0
        """
        # For Phase 4: Simple default implementation
        # TODO: Add beat_grid conversion for duration_bars → ms in future phase

        # Default to 500ms
        return 500

    def interpolate(
        self,
        curve: list[CurvePoint],
        time: float,
    ) -> float:
        """Linear interpolation within a curve at normalized time [0, 1].

        Finds the two surrounding points and performs linear interpolation.
        Handles edge cases:
        - time < 0 → returns first point's value
        - time > 1 → returns last point's value
        - time exactly on point → returns that point's value
        - single point curve → returns that point's value

        Args:
            curve: List of curve points (must be sorted by time)
            time: Normalized time [0, 1]

        Returns:
            Interpolated DMX value

        Example:
            >>> curve = [CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)]
            >>> value = blender.interpolate(curve, 0.5)
            >>> assert value == 127.5
        """
        if not curve:
            raise ValueError("Cannot interpolate empty curve")

        # Single point - return its value
        if len(curve) == 1:
            return curve[0].value

        # Clamp time to [0, 1]
        if time <= curve[0].time:
            return curve[0].value
        if time >= curve[-1].time:
            return curve[-1].value

        # Find surrounding points
        for i in range(len(curve) - 1):
            p1 = curve[i]
            p2 = curve[i + 1]

            if p1.time <= time <= p2.time:
                # Linear interpolation
                if p2.time == p1.time:
                    # Same time (shouldn't happen, but handle gracefully)
                    return p1.value

                # t is the normalized position between p1 and p2
                t = (time - p1.time) / (p2.time - p1.time)
                return p1.value + t * (p2.value - p1.value)

        # Should never reach here if curve is properly sorted
        return curve[-1].value

    def blend_channel_pair(
        self,
        curr_curve: list[CurvePoint],
        next_curve: list[CurvePoint],
        blend_end_curr: float,
        blend_start_next: float,
    ) -> tuple[list[CurvePoint], list[CurvePoint]]:
        """Blend two curves at their boundary (returns new curves).

        Applies crossfade blending in the overlap regions:
        - Last (1 - blend_end_curr) portion of curr_curve
        - First blend_start_next portion of next_curve

        Uses weighted average: blended_value = (1-t)*curr + t*next
        where t increases from 0 to 1 across the blend window.

        Note: CurvePoint is immutable, so we create new point objects.

        Args:
            curr_curve: Current effect's curve
            next_curve: Next effect's curve
            blend_end_curr: Time in curr where blending starts [0, 1]
            blend_start_next: Time in next where blending ends [0, 1]

        Returns:
            Tuple of (blended_curr, blended_next)

        Example:
            >>> # Blend last 30% of curr with first 30% of next
            >>> blended_curr, blended_next = blender.blend_channel_pair(curr, next, 0.7, 0.3)
        """
        # Blend the end of curr_curve (create new points)
        blended_curr = []
        for point in curr_curve:
            if point.time >= blend_end_curr:
                # Calculate blend weight (0 at blend_end_curr, 1 at time=1.0)
                if blend_end_curr < 1.0:
                    blend_weight = (point.time - blend_end_curr) / (1.0 - blend_end_curr)
                else:
                    blend_weight = 1.0

                # Sample from START of next_curve (time=0.0 is the boundary)
                next_value = self.interpolate(next_curve, 0.0)

                new_value = (1 - blend_weight) * point.value + blend_weight * next_value
                blended_curr.append(CurvePoint(time=point.time, value=new_value))
            else:
                # Outside blend region - keep original
                blended_curr.append(point)

        # Blend the start of next_curve (create new points)
        blended_next = []
        for point in next_curve:
            if point.time <= blend_start_next:
                # Calculate blend weight (1 at time=0, 0 at blend_start_next)
                if blend_start_next > 0.0:
                    blend_weight = 1.0 - (point.time / blend_start_next)
                else:
                    blend_weight = 0.0

                # Sample from END of curr_curve (time=1.0 is the boundary)
                curr_value = self.interpolate(curr_curve, 1.0)

                # Blend: (1-t)*next + t*curr (inverted since we're at start of next)
                new_value = blend_weight * curr_value + (1 - blend_weight) * point.value
                blended_next.append(CurvePoint(time=point.time, value=new_value))
            else:
                # Outside blend region - keep original
                blended_next.append(point)

        return (blended_curr, blended_next)

    def apply_crossfade_channels(
        self,
        curr: RenderedEffect,
        next_effect: RenderedEffect,
        blend_duration_ms: int,
    ) -> None:
        """Apply crossfade blending to all channels between two effects.

        Blends pan, tilt, dimmer (and optional channels if present).
        Respects maximum 30% blend window for each effect.

        Modifies the RenderedEffect objects in-place by replacing their
        rendered_channels with blended versions.

        Args:
            curr: Current rendered effect (modified in-place)
            next_effect: Next rendered effect (modified in-place)
            blend_duration_ms: Desired blend duration in milliseconds

        Example:
            >>> blender.apply_crossfade_channels(effect1, effect2, 500)
            >>> # effect1 and effect2 now have blended channels
        """
        from .models import RenderedChannels

        # Calculate effect durations
        curr_duration = curr.end_ms - curr.start_ms
        next_duration = next_effect.end_ms - next_effect.start_ms

        # Limit blend to 30% of each effect's duration
        max_blend_curr = curr_duration * 0.3
        max_blend_next = next_duration * 0.3
        actual_blend = min(blend_duration_ms, max_blend_curr, max_blend_next)

        # Calculate blend regions in normalized time [0, 1]
        blend_end_curr = 1.0 - (actual_blend / curr_duration)
        blend_start_next = actual_blend / next_duration

        # Type declarations for blended channels
        blended_pan_curr: ValueCurveSpec | list[CurvePoint] | int
        blended_pan_next: ValueCurveSpec | list[CurvePoint] | int
        blended_tilt_curr: ValueCurveSpec | list[CurvePoint] | int
        blended_tilt_next: ValueCurveSpec | list[CurvePoint] | int
        blended_dimmer_curr: ValueCurveSpec | list[CurvePoint] | int
        blended_dimmer_next: ValueCurveSpec | list[CurvePoint] | int
        blended_shutter_curr: ValueCurveSpec | list[CurvePoint] | int | None
        blended_shutter_next: ValueCurveSpec | list[CurvePoint] | int | None

        # Blend pan channel (only blend Custom curves, keep Native as-is)
        if isinstance(curr.rendered_channels.pan, list) and isinstance(
            next_effect.rendered_channels.pan, list
        ):
            blended_pan_curr, blended_pan_next = self.blend_channel_pair(
                curr.rendered_channels.pan,
                next_effect.rendered_channels.pan,
                blend_end_curr,
                blend_start_next,
            )
        else:
            # Native curves - no blending (SNAP transition)
            blended_pan_curr = curr.rendered_channels.pan
            blended_pan_next = next_effect.rendered_channels.pan

        # Blend tilt channel (only blend Custom curves, keep Native as-is)
        if isinstance(curr.rendered_channels.tilt, list) and isinstance(
            next_effect.rendered_channels.tilt, list
        ):
            blended_tilt_curr, blended_tilt_next = self.blend_channel_pair(
                curr.rendered_channels.tilt,
                next_effect.rendered_channels.tilt,
                blend_end_curr,
                blend_start_next,
            )
        else:
            # Native curves - no blending (SNAP transition)
            blended_tilt_curr = curr.rendered_channels.tilt
            blended_tilt_next = next_effect.rendered_channels.tilt

        # Blend dimmer channel (only blend Custom curves, keep Native as-is)
        if isinstance(curr.rendered_channels.dimmer, list) and isinstance(
            next_effect.rendered_channels.dimmer, list
        ):
            blended_dimmer_curr, blended_dimmer_next = self.blend_channel_pair(
                curr.rendered_channels.dimmer,
                next_effect.rendered_channels.dimmer,
                blend_end_curr,
                blend_start_next,
            )
        else:
            # Native curves - no blending (SNAP transition)
            blended_dimmer_curr = curr.rendered_channels.dimmer
            blended_dimmer_next = next_effect.rendered_channels.dimmer

        # Blend optional channels if present (only blend Custom curves)
        if curr.rendered_channels.shutter and next_effect.rendered_channels.shutter:
            if isinstance(curr.rendered_channels.shutter, list) and isinstance(
                next_effect.rendered_channels.shutter, list
            ):
                blended_shutter_curr, blended_shutter_next = self.blend_channel_pair(
                    curr.rendered_channels.shutter,
                    next_effect.rendered_channels.shutter,
                    blend_end_curr,
                    blend_start_next,
                )
            else:
                # Native curves - no blending (SNAP transition)
                blended_shutter_curr = curr.rendered_channels.shutter
                blended_shutter_next = next_effect.rendered_channels.shutter
        else:
            # Keep originals if one is None
            blended_shutter_curr = curr.rendered_channels.shutter
            blended_shutter_next = next_effect.rendered_channels.shutter

        # Update rendered channels (create new RenderedChannels objects)
        curr.rendered_channels = RenderedChannels(
            pan=blended_pan_curr,
            tilt=blended_tilt_curr,
            dimmer=blended_dimmer_curr,
            shutter=blended_shutter_curr,
            color=curr.rendered_channels.color,  # Don't blend color
            gobo=curr.rendered_channels.gobo,  # Don't blend gobo
        )

        next_effect.rendered_channels = RenderedChannels(
            pan=blended_pan_next,
            tilt=blended_tilt_next,
            dimmer=blended_dimmer_next,
            shutter=blended_shutter_next,
            color=next_effect.rendered_channels.color,
            gobo=next_effect.rendered_channels.gobo,
        )
