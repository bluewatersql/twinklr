"""Channel blending for smooth transitions between segments.

This module provides functionality to blend DMX channel values during
transition overlap regions, creating smooth interpolations between
source and target states.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from blinkb0t.core.curves.generator import CurveGenerator
from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import ChannelName
from blinkb0t.core.sequencer.models.transition import TransitionPlan, TransitionStrategy
from blinkb0t.core.sequencer.moving_heads.channels.state import ChannelValue

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ChannelBlender:
    """Blends channel values during transition overlap regions.

    Responsibilities:
    - Generate interpolated curves between source and target values
    - Apply per-channel transition strategies
    - Handle different blend modes (linear, crossfade, fade-via-black, etc.)
    """

    def __init__(self, curve_generator: CurveGenerator):
        """Initialize channel blender.

        Args:
            curve_generator: Curve generator for creating interpolation curves.
        """
        self.curve_generator = curve_generator

    def blend_channel(
        self,
        channel_name: ChannelName,
        source_value: int,
        target_value: int,
        transition_plan: TransitionPlan,
        time_in_transition: float,
    ) -> int:
        """Blend a single channel value at a specific time in transition.

        Args:
            channel_name: Channel to blend.
            source_value: Source DMX value (0-255).
            target_value: Target DMX value (0-255).
            transition_plan: Transition plan with strategies and timing.
            time_in_transition: Time within transition (0.0 = start, 1.0 = end).

        Returns:
            Blended DMX value (0-255).

        Example:
            >>> blender = ChannelBlender(curve_generator)
            >>> blended = blender.blend_channel(
            ...     ChannelName.DIMMER,
            ...     source_value=255,
            ...     target_value=0,
            ...     transition_plan=plan,
            ...     time_in_transition=0.5  # Halfway through
            ... )
            >>> print(blended)  # e.g., 128 for linear blend
        """
        # Get strategy for this channel
        strategy = transition_plan.channel_strategies.get(
            channel_name, TransitionStrategy.SMOOTH_INTERPOLATION
        )

        # Apply strategy
        if strategy == TransitionStrategy.SNAP:
            return self._blend_snap(source_value, target_value, time_in_transition)
        elif strategy == TransitionStrategy.SMOOTH_INTERPOLATION:
            return self._blend_smooth(
                source_value, target_value, time_in_transition, transition_plan.hint.curve
            )
        elif strategy == TransitionStrategy.CROSSFADE:
            return self._blend_crossfade(source_value, target_value, time_in_transition)
        elif strategy == TransitionStrategy.FADE_VIA_BLACK:
            return self._blend_fade_via_black(source_value, target_value, time_in_transition)
        elif strategy == TransitionStrategy.SEQUENCE:
            return self._blend_sequence(source_value, target_value, time_in_transition)
        else:
            logger.warning(f"Unknown strategy {strategy}, using smooth interpolation")
            return self._blend_smooth(
                source_value, target_value, time_in_transition, CurveLibrary.LINEAR
            )

    def blend_channel_curve(
        self,
        channel_name: ChannelName,
        source_values: list[int],
        target_values: list[int],
        transition_plan: TransitionPlan,
        n_samples: int,
    ) -> list[int]:
        """Generate complete blended curve for a channel across transition.

        Args:
            channel_name: Channel to blend.
            source_values: Source DMX curve (values over time).
            target_values: Target DMX curve (values over time).
            transition_plan: Transition plan with strategies and timing.
            n_samples: Number of samples in output curve.

        Returns:
            Blended DMX curve (n_samples values, each 0-255).

        Example:
            >>> source_curve = [255] * 100  # Constant bright
            >>> target_curve = [0] * 100    # Constant dark
            >>> blended = blender.blend_channel_curve(
            ...     ChannelName.DIMMER,
            ...     source_curve,
            ...     target_curve,
            ...     plan,
            ...     n_samples=100
            ... )
        """
        if len(source_values) != n_samples or len(target_values) != n_samples:
            raise ValueError(
                f"Source/target curves must have {n_samples} samples, "
                f"got source={len(source_values)}, target={len(target_values)}"
            )

        blended_curve = []

        for i in range(n_samples):
            # Normalize time within transition (0.0 to 1.0)
            time_in_transition = i / (n_samples - 1) if n_samples > 1 else 0.0

            # Get source and target values at this time
            source_value = source_values[i]
            target_value = target_values[i]

            # Blend
            blended_value = self.blend_channel(
                channel_name, source_value, target_value, transition_plan, time_in_transition
            )

            blended_curve.append(blended_value)

        return blended_curve

    def _blend_snap(self, source_value: int, target_value: int, t: float) -> int:
        """SNAP strategy: instant change at midpoint.

        Args:
            source_value: Source DMX value.
            target_value: Target DMX value.
            t: Time in transition (0.0-1.0).

        Returns:
            Source value if t < 0.5, target value otherwise.
        """
        return source_value if t < 0.5 else target_value

    def _blend_smooth(
        self, source_value: int, target_value: int, t: float, curve: CurveLibrary
    ) -> int:
        """SMOOTH_INTERPOLATION strategy: curved interpolation.

        Args:
            source_value: Source DMX value.
            target_value: Target DMX value.
            t: Time in transition (0.0-1.0).
            curve: Curve type for interpolation.

        Returns:
            Interpolated DMX value using specified curve.
        """
        # Edge cases for exact start/end
        if t <= 0.0:
            return source_value
        if t >= 1.0:
            return target_value

        # Generate curve from 0 to 1
        curve_points = self.curve_generator.generate_custom_points(
            curve_id=curve.value,
            num_points=100,
        )

        # Sample curve at time t
        curve_index = int(t * (len(curve_points) - 1))
        curve_value = curve_points[curve_index].v  # 0.0 to 1.0

        # Interpolate between source and target
        blended = source_value + curve_value * (target_value - source_value)

        return self._clamp_dmx(int(round(blended)))

    def _blend_crossfade(self, source_value: int, target_value: int, t: float) -> int:
        """CROSSFADE strategy: linear crossfade with constant power.

        Uses equal-power crossfade curve for perceptually smooth transitions.

        Args:
            source_value: Source DMX value.
            target_value: Target DMX value.
            t: Time in transition (0.0-1.0).

        Returns:
            Crossfaded DMX value.
        """
        import math

        # Equal-power crossfade: sqrt curves for constant perceived power
        fade_out_gain = math.cos(t * math.pi / 2)  # 1.0 -> 0.0
        fade_in_gain = math.sin(t * math.pi / 2)  # 0.0 -> 1.0

        blended = source_value * fade_out_gain + target_value * fade_in_gain

        return self._clamp_dmx(int(blended))

    def _blend_fade_via_black(self, source_value: int, target_value: int, t: float) -> int:
        """FADE_VIA_BLACK strategy: fade to zero, then fade up to target.

        Useful for color/gobo changes where intermediate values don't make sense.

        Args:
            source_value: Source DMX value.
            target_value: Target DMX value.
            t: Time in transition (0.0-1.0).

        Returns:
            DMX value fading through zero.
        """
        if t < 0.5:
            # First half: fade source to zero
            fade_out = 1.0 - (t * 2.0)  # 1.0 -> 0.0
            blended = source_value * fade_out
        else:
            # Second half: fade zero to target
            fade_in = (t - 0.5) * 2.0  # 0.0 -> 1.0
            blended = target_value * fade_in

        return self._clamp_dmx(int(blended))

    def _blend_sequence(self, source_value: int, target_value: int, t: float) -> int:
        """SEQUENCE strategy: sequenced change (close, change, open).

        Useful for shutter channels: close shutter, change state, open shutter.

        Args:
            source_value: Source DMX value.
            target_value: Target DMX value.
            t: Time in transition (0.0-1.0).

        Returns:
            Sequenced DMX value.
        """
        # Edge case for exact end
        if t >= 1.0:
            return target_value

        # Three phases: close (0-0.33), hold closed (0.33-0.66), open (0.66-1.0)
        if t < 0.33:
            # Close: fade to zero
            fade = 1.0 - (t / 0.33)
            return self._clamp_dmx(int(round(source_value * fade)))
        elif t < 0.66:
            # Hold closed
            return 0
        else:
            # Open: fade from zero to target
            fade = (t - 0.66) / 0.34
            return self._clamp_dmx(int(round(target_value * fade)))

    def _clamp_dmx(self, value: int) -> int:
        """Clamp value to valid DMX range (0-255).

        Args:
            value: Raw value.

        Returns:
            Clamped value in range [0, 255].
        """
        return max(0, min(255, value))

    def create_blended_channel_value(
        self,
        channel_name: ChannelName,
        blended_curve: list[int],
        clamp_min: int = 0,
        clamp_max: int = 255,
    ) -> ChannelValue:
        """Create a ChannelValue from a blended DMX curve.

        Args:
            channel_name: Channel name.
            blended_curve: Blended DMX values (0-255).
            clamp_min: Minimum DMX value for clamping.
            clamp_max: Maximum DMX value for clamping.

        Returns:
            ChannelValue with normalized curve points.

        Example:
            >>> blended_curve = [255, 200, 150, 100, 50, 0]
            >>> channel_value = blender.create_blended_channel_value(
            ...     ChannelName.DIMMER,
            ...     blended_curve
            ... )
        """
        from blinkb0t.core.curves.models import CurvePoint, PointsCurve

        # PointsCurve requires at least 2 points
        # If single value, create 2 points with same value
        if len(blended_curve) == 1:
            blended_curve = [blended_curve[0], blended_curve[0]]

        # Convert DMX values to normalized curve points
        curve_points = []

        for i, dmx_value in enumerate(blended_curve):
            # Calculate normalized time (0.0 to 1.0)
            t = i / (len(blended_curve) - 1)

            # Normalize DMX value to [0, 1] based on clamp range
            v = (dmx_value - clamp_min) / (clamp_max - clamp_min) if clamp_max > clamp_min else 0.0
            v = max(0.0, min(1.0, v))  # Clamp to [0, 1]

            curve_points.append(CurvePoint(t=t, v=v))

        # Create PointsCurve
        points_curve = PointsCurve(points=curve_points)

        return ChannelValue(
            channel=channel_name,
            curve=points_curve,
            clamp_min=clamp_min,
            clamp_max=clamp_max,
        )
