"""Base movement handler with shared abstractions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from blinkb0t.core.config.adapter import get_inversion_map, get_max_channel
from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.infrastructure.curves.factory import get_curve_factory
from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec
from blinkb0t.core.domains.sequencing.infrastructure.xsq.effect_placement import EffectPlacement
from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect
from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import (
    MovementResolver,
    ResolverContext,
)
from blinkb0t.core.domains.sequencing.moving_heads.templates.geometry.engine import GeometryEngine
from blinkb0t.core.utils.math import clamp

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseMovementHandler(MovementResolver):
    """Base handler with all shared abstractions.

    Provides common functionality for all movement handlers:
    - Pan/tilt resolution
    - Geometry handling
    - Curve creation
    - DMX state management
    - EffectPlacement creation
    """

    def __init__(self) -> None:
        """Initialize base handler with dependencies."""
        super().__init__()
        self._geometry_engine = GeometryEngine()
        # Note: DMXCurveMapper is now provided via SequencerContext, not created per-handler

    def _should_use_value_curves(self, instruction: dict[str, Any]) -> bool:
        """Determine if instruction should use value curves.

        Args:
            instruction: Plan instruction dict

        Returns:
            True if value curves should be used
        """
        inst_mode = instruction.get("rendering_mode")
        if inst_mode:
            return bool(inst_mode == "value_curve")

        movement = instruction.get("movement", {}) or {}
        move_mode = movement.get("rendering_mode", "discrete_blocks")

        dimmer = instruction.get("dimmer", {}) or {}
        dim_mode = dimmer.get("rendering_mode", "discrete_blocks")

        return bool(move_mode == "value_curve" or dim_mode == "value_curve")

    def _create_value_curve(
        self,
        movement: dict[str, Any],
        channel_type: str,
        min_limit: int,
        max_limit: int,
        curve_mapper: DMXCurveMapper,
        duration_ms: int | None = None,
        params: dict[str, Any] | None = None,
    ) -> ValueCurveSpec | CustomCurveSpec | None:
        """Create a value curve from movement specification.

        Uses CurveFactory to automatically determine if curve should be
        Native (ValueCurveSpec) or Custom (CustomCurveSpec with point array).

        Args:
            movement: Movement specification dict
            channel_type: Channel type ("pan", "tilt", "dimmer")
            min_limit: Minimum DMX value
            max_limit: Maximum DMX value
            curve_mapper: DMXCurveMapper instance from context (unused, for compatibility)
            duration_ms: Optional duration for custom curves

        Returns:
            ValueCurveSpec for native curves, CustomCurveSpec for custom curves, or None if invalid
        """
        if not movement:
            logger.warning(f"Missing movement data for {channel_type} channel")
            return None

        curve_preset = movement.get("curve_preset", "sine")

        try:
            # Use CurveFactory to create appropriate spec (Native or Custom)
            factory = get_curve_factory()

            # Calculate optimal point count for custom curves based on duration
            num_points = 100  # Default
            if duration_ms:
                # ~10 points per second for smooth curves
                num_points = max(20, min(300, int((duration_ms / 1000.0) * 10)))

            # Extract categorical params (resolved by PatternStepProcessor or handler)
            # Note: Amplitude scaling is already applied to min/max DMX limits in handler
            # before calling this method, so we only pass frequency here
            categorical_params = {}

            # Use passed params if provided (from handler resolution)
            if params and "frequency" in params:
                categorical_params["frequency"] = float(params["frequency"])
                logger.debug(
                    f"Applying frequency from params: {categorical_params['frequency']:.2f}"
                )
            elif "frequency" in movement:
                # Fallback to movement dict for backwards compatibility
                categorical_params["frequency"] = float(movement["frequency"])
                logger.debug(
                    f"Applying frequency from movement: {categorical_params['frequency']:.2f}"
                )

            curve_spec = factory.create_curve(
                curve_name=curve_preset,
                min_dmx=float(min_limit),
                max_dmx=float(max_limit),
                params=categorical_params if categorical_params else None,
                num_points=num_points,
            )

            logger.debug(
                f"Created {type(curve_spec).__name__} for {channel_type}: "
                f"curve={curve_preset}, range=[{min_limit}, {max_limit}]"
            )

            return curve_spec
        except Exception as e:
            logger.error(f"Failed to generate curve '{curve_preset}' for {channel_type}: {e}")
            return self._create_default_curve(channel_type, min_limit, max_limit)

    def _create_default_curve(
        self, channel_type: str, min_limit: int, max_limit: int
    ) -> ValueCurveSpec:
        """Create default value curve.

        Args:
            channel_type: Channel type
            min_limit: Minimum DMX value
            max_limit: Maximum DMX value

        Returns:
            Default ValueCurveSpec
        """
        center_dmx = (min_limit + max_limit) / 2.0
        amplitude_dmx = (max_limit - min_limit) / 2.0

        if channel_type == "dimmer":
            return ValueCurveSpec(
                type=NativeCurveType.RAMP,
                p1=clamp(128, min_limit, max_limit),
                p2=clamp(128, min_limit, max_limit),
                reverse=False,
                min_val=min_limit,
                max_val=max_limit,
            )

        p1 = clamp(center_dmx - amplitude_dmx / 2, min_limit, max_limit)
        p2 = clamp(center_dmx + amplitude_dmx / 2, min_limit, max_limit)

        return ValueCurveSpec(
            type=NativeCurveType.SINE,
            p1=p1,
            p2=p2,
            p3=1.0,
            p4=0.0,
            reverse=False,
            min_val=min_limit,
            max_val=max_limit,
        )

    def _build_dmx_settings(
        self,
        values: dict[int, int],
        curves: dict[int, ValueCurveSpec | CustomCurveSpec] | None,
        context: ResolverContext,
    ) -> str:
        """Build DMX settings string for xLights.

        Args:
            values: DMX channel values
            curves: Optional value curves
            context: Resolver context

        Returns:
            DMX settings string
        """
        inv = get_inversion_map(context.fixtures)
        max_channel = get_max_channel(context.fixtures)
        n_channels = max(16, max_channel)
        n_channels = ((n_channels + 15) // 16) * 16

        parts: list[str] = []
        parts.append("B_CHOICE_BufferStyle=Per Model Default")

        for ch in range(1, n_channels + 1):
            parts.append(f"E_CHECKBOX_INVDMX{ch}={int(inv.get(ch, 0))}")

        parts.append("E_NOTEBOOK1=Channels 1-16")

        for ch in range(1, n_channels + 1):
            parts.append(f"E_SLIDER_DMX{ch}={int(values.get(ch, 0))}")

        if curves:
            for ch, curve_spec in curves.items():
                if curve_spec is not None:
                    curve_str = curve_spec.to_xlights_string(ch)
                    parts.append(f"E_VALUECURVE_DMX{ch}={curve_str}")

        return ",".join(parts)

    def _create_sequenced_effect(
        self,
        state: ChannelState,
        targets: list[str],
        timing: tuple[int, int],
        metadata: dict[str, Any] | None = None,
    ) -> SequencedEffect:
        """Create sequenced effect from channel state.

        Args:
            state: Channel state with pan/tilt/dimmer/etc values
            targets: Target semantic groups/fixtures
            timing: (start_ms, end_ms) tuple
            metadata: Optional metadata (pattern name, intensity, etc.)

        Returns:
            SequencedEffect object ready for pipeline integration
        """
        start_ms, end_ms = timing

        # SequencedEffect expects dict[str, ChannelState]
        # We pass the same state object for all active channels
        # The pipeline will handle extracting individual channel values
        channels = {}
        for channel_name in ["pan", "tilt", "dimmer", "shutter", "color", "gobo"]:
            # Check if channel has a value OR a curve (value curves don't set base values)
            dmx_channel = state._get_dmx_channel(channel_name)
            logger.info(
                f"[HANDLER_TRACE] Channel {channel_name}: dmx_channel={dmx_channel}, in values={dmx_channel in state.values if dmx_channel else False}, in curves={dmx_channel in state.value_curves if dmx_channel else False}"
            )
            if dmx_channel is not None and (
                dmx_channel in state.values or dmx_channel in state.value_curves
            ):
                # Share the same ChannelState object (contains all channels)
                # Pipeline will extract the specific channel it needs
                channels[channel_name] = state
                logger.info(f"[HANDLER_TRACE] Added {channel_name} to channels dict")

        # DEBUG: Log value curves in state
        logger.info(
            f"[EFFECT_CREATE] State has {len(state.value_curves)} value_curves: {list(state.value_curves.keys())}"
        )
        logger.info(
            f"[EFFECT_CREATE] Creating SequencedEffect with channels: {list(channels.keys())}"
        )

        return SequencedEffect(
            targets=targets,
            channels=channels,
            start_ms=start_ms,
            end_ms=end_ms,
            metadata=metadata or {},
        )

    def _create_effect_placements(
        self,
        state: ChannelState,
        targets: list[str],
        timing: tuple[int, int],
        context: ResolverContext,
    ) -> list[EffectPlacement]:
        """Create effect placements from channel state.

        DEPRECATED: Use _create_sequenced_effect instead.
        Kept for backward compatibility during migration.

        Args:
            state: Channel state
            targets: Target fixture names
            timing: (start_ms, end_ms) tuple
            context: Resolver context

        Returns:
            List of EffectPlacement objects
        """
        start_ms, end_ms = timing

        values = state.to_dmx_dict()
        curves = state.to_value_curves_dict()
        settings = self._build_dmx_settings(values, curves, context)

        ref = context.xsq.append_effectdb(settings)

        placements = []
        for target in targets:
            context.xsq.ensure_element(target, element_type="model")
            placements.append(
                EffectPlacement(
                    element_name=target,
                    effect_name="DMX",
                    ref=ref,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    palette=0,
                )
            )

        return placements

    def resolve(
        self,
        instruction: dict[str, Any],
        context: ResolverContext,
        targets: list[str],
    ) -> list[SequencedEffect]:
        """Resolve instruction to sequenced effects (abstract).

        Subclasses must implement this method.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement resolve()")
