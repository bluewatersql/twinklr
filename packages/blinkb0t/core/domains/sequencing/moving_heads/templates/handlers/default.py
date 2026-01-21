"""Default movement handler for common cases."""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.domains.sequencing.channels.state import ChannelState
from blinkb0t.core.domains.sequencing.models.channels import SequencedEffect
from blinkb0t.core.domains.sequencing.moving_heads.resolvers.context import ResolverContext
from blinkb0t.core.domains.sequencing.moving_heads.templates.handlers.base_movement import (
    BaseMovementHandler,
)
from blinkb0t.core.utils.math import clamp

logger = logging.getLogger(__name__)


class DefaultMovementHandler(BaseMovementHandler):
    """Default handler for all common movement patterns.

    Handles:
    - Value curve rendering (most common path)
    - Static movements (no curves = static position)
    - Geometry transformations
    - Dimmer patterns
    - Transitions/holds (just movements)
    """

    def _resolve_categorical_params(
        self, params_dict: dict[str, Any], pattern_id: str
    ) -> dict[str, float]:
        """Resolve categorical parameters to numeric values.

        Args:
            params_dict: Dict that may contain categorical params (e.g., {"intensity": "SMOOTH"})
            pattern_id: Pattern ID to look up library defaults

        Returns:
            Dict with numeric params (e.g., {"amplitude": 0.3, "frequency": 0.5})
        """
        from blinkb0t.core.domains.sequencing.libraries.moving_heads import (
            DIMMER_LIBRARY,
            MOVEMENT_LIBRARY,
            DimmerID,
            MovementID,
        )
        from blinkb0t.core.domains.sequencing.libraries.moving_heads.base import (
            CategoricalIntensity,
        )

        # If params already numeric, return as-is
        if "amplitude" in params_dict and isinstance(params_dict["amplitude"], (int, float)):
            return {
                "amplitude": float(params_dict.get("amplitude", 1.0)),
                "frequency": float(params_dict.get("frequency", 1.0)),
                "center": float(params_dict.get("center", 128.0)),
            }

        # Try to resolve categorical intensity
        intensity_val = params_dict.get("intensity")
        if not intensity_val:
            # No categorical params, return defaults
            return {"amplitude": 1.0, "frequency": 1.0, "center": 128.0}

        # If intensity is already numeric (from LLM plan), use it directly
        if isinstance(intensity_val, (int, float)):
            return {"amplitude": float(intensity_val), "frequency": 1.0, "center": 128.0}

        # Try to parse as numeric string
        if isinstance(intensity_val, str):
            try:
                numeric_intensity = float(intensity_val)
                return {"amplitude": numeric_intensity, "frequency": 1.0, "center": 128.0}
            except ValueError:
                pass  # Not numeric, try categorical

        # Must be categorical string
        intensity_str = str(intensity_val)

        # Try as movement pattern
        try:
            movement_id = MovementID(pattern_id)
            movement_lib = MOVEMENT_LIBRARY.get(movement_id)
            if movement_lib and movement_lib.categorical_params:
                intensity_enum = CategoricalIntensity(intensity_str.upper())
                numeric_params = movement_lib.categorical_params.get(intensity_enum)
                if numeric_params:
                    return {
                        "amplitude": numeric_params.amplitude,
                        "frequency": numeric_params.frequency,
                        "center": numeric_params.center,
                    }
        except (ValueError, KeyError):
            pass

        # Try as dimmer pattern (dimmer params have different structure)
        try:
            dimmer_id = DimmerID(pattern_id)
            dimmer_lib = DIMMER_LIBRARY.get(dimmer_id)
            if dimmer_lib and dimmer_lib.categorical_params:
                intensity_enum = CategoricalIntensity(intensity_str.upper())
                dimmer_params_obj = dimmer_lib.categorical_params.get(intensity_enum)
                if dimmer_params_obj:
                    # Dimmer params use min/max intensity and period, not amplitude/frequency/center
                    # Convert to common format (amplitude = normalized max, frequency = 1/period)
                    amplitude = dimmer_params_obj.max_intensity / 255.0
                    frequency = (
                        1.0 / dimmer_params_obj.period if dimmer_params_obj.period > 0 else 1.0
                    )
                    center = (
                        dimmer_params_obj.min_intensity + dimmer_params_obj.max_intensity
                    ) / 2.0
                    return {
                        "amplitude": amplitude,
                        "frequency": frequency,
                        "center": center,
                    }
        except (ValueError, KeyError):
            pass

        # Fallback to defaults
        logger.debug(
            f"Could not resolve categorical params for pattern '{pattern_id}', "
            f"intensity '{intensity_str}' - using defaults (amplitude=0.3)"
        )
        return {"amplitude": 0.3, "frequency": 1.0, "center": 128.0}

    def resolve(
        self,
        instruction: dict[str, Any],
        context: ResolverContext,
        targets: list[str],
    ) -> list[Any]:
        """Resolve instruction to effect placements.

        Args:
            instruction: Full instruction dict
            context: Resolver context
            targets: List of target fixture names

        Returns:
            List of EffectPlacement objects
        """
        timing = (context.start_ms, context.end_ms)
        return self._resolve_movement(instruction, context, targets, timing)

    def _resolve_movement(
        self,
        instruction: dict[str, Any],
        context: ResolverContext,
        targets: list[str],
        timing: tuple[int, int],
    ) -> list[SequencedEffect]:
        """Resolve movement instruction to sequenced effects.

        Handles both value curves and static movements (no curves = static).

        Args:
            instruction: Instruction dict
            context: Resolver context
            targets: Target fixture names
            timing: (start_ms, end_ms) tuple

        Returns:
            List of SequencedEffect (single effect for default handler)
        """
        movement = instruction.get("movement", {})
        dimmer = instruction.get("dimmer", {})

        # Resolve pan/tilt centers
        pan_center, tilt_center = self._resolve_pan_tilt(instruction, context)

        # Create curves (intelligently determine if value curves should be used)
        curves = {}
        duration_ms = timing[1] - timing[0]

        # Determine if movement should use value curves
        # Static patterns (hold, static) should NOT use curves
        # Dynamic patterns (sweep, circle, bounce, etc.) SHOULD use curves
        movement_pattern = movement.get("pattern", "hold")
        use_movement_curves = movement_pattern not in ["hold", "static"]

        # Determine if dimmer should use value curves
        # Note: dimmer can have "pattern" OR "profile_id" depending on source
        dimmer_pattern = dimmer.get("pattern") or dimmer.get("profile_id", "full")
        use_dimmer_curves = dimmer_pattern not in ["full", "hold", "static"]

        # Resolve categorical parameters to numeric values
        # Parameters can come as categorical strings (e.g., "SMOOTH") or numeric (e.g., 0.3)
        movement_params = self._resolve_categorical_params(movement, movement_pattern)
        dimmer_params = self._resolve_categorical_params(dimmer, dimmer_pattern)

        # Extract amplitude for DMX range scaling
        normalized_amplitude = movement_params.get("amplitude", 1.0)

        # Pan curve (if movement is dynamic)
        if use_movement_curves:
            pan_min_base, pan_max_base = context.boundaries.pan_limits
            pan_center_dmx = (pan_min_base + pan_max_base) / 2.0
            pan_range = pan_max_base - pan_min_base

            # Scale range by categorical amplitude
            scaled_pan_range = pan_range * normalized_amplitude
            pan_min = int(pan_center_dmx - scaled_pan_range / 2.0)
            pan_max = int(pan_center_dmx + scaled_pan_range / 2.0)

            logger.debug(
                f"Pan range scaled by amplitude {normalized_amplitude:.2f}: "
                f"[{pan_min_base}, {pan_max_base}] → [{pan_min}, {pan_max}]"
            )

            pan_curve = self._create_value_curve(
                movement,
                "pan",
                pan_min,
                pan_max,
                context.sequencer_context.dmx_curve_mapper,
                duration_ms,
                params=movement_params,  # Pass resolved movement params
            )
            if pan_curve:
                curves["pan"] = pan_curve
                logger.debug(f"✓ Created pan curve: {type(pan_curve).__name__}")
            else:
                logger.warning(f"✗ Failed to create pan curve for pattern {movement_pattern}")

        # Tilt curve (if movement is dynamic)
        if use_movement_curves:
            tilt_min_base, tilt_max_base = context.boundaries.tilt_limits
            tilt_center_dmx = (tilt_min_base + tilt_max_base) / 2.0
            tilt_range = tilt_max_base - tilt_min_base

            # Scale range by categorical amplitude
            scaled_tilt_range = tilt_range * normalized_amplitude
            tilt_min = int(tilt_center_dmx - scaled_tilt_range / 2.0)
            tilt_max = int(tilt_center_dmx + scaled_tilt_range / 2.0)

            logger.debug(
                f"Tilt range scaled by amplitude {normalized_amplitude:.2f}: "
                f"[{tilt_min_base}, {tilt_max_base}] → [{tilt_min}, {tilt_max}]"
            )

            tilt_curve = self._create_value_curve(
                movement,
                "tilt",
                tilt_min,
                tilt_max,
                context.sequencer_context.dmx_curve_mapper,
                duration_ms,
                params=movement_params,  # Pass resolved movement params
            )
            if tilt_curve:
                curves["tilt"] = tilt_curve

        # Dimmer curve (if dimmer is dynamic)
        if use_dimmer_curves:
            dimmer_curve = self._create_value_curve(
                dimmer,
                "dimmer",
                0,
                255,
                context.sequencer_context.dmx_curve_mapper,
                duration_ms,
                params=dimmer_params,  # Pass resolved dimmer params
            )
            if dimmer_curve:
                curves["dimmer"] = dimmer_curve

        # Build DMX state
        # If curves exist, use them; otherwise static values (static movement)
        state = ChannelState(context.first_fixture)

        if curves.get("pan"):
            state.set_channel("pan", pan_center, value_curve=curves["pan"])
        else:
            state.set_channel("pan", pan_center)

        if curves.get("tilt"):
            state.set_channel("tilt", tilt_center, value_curve=curves["tilt"])
        else:
            state.set_channel("tilt", tilt_center)

        # Resolve dimmer value
        dimmer_value = self._resolve_dimmer_value(instruction, timing)
        if curves.get("dimmer"):
            state.set_channel("dimmer", dimmer_value, value_curve=curves["dimmer"])
        else:
            state.set_channel("dimmer", dimmer_value)

        # Additional channels
        channels_spec = instruction.get("channels", {})
        for channel_name, channel_value in channels_spec.items():
            state.set_channel(channel_name, channel_value)

        # Create metadata
        metadata = {
            "handler": "default",
            "pattern": instruction.get("movement", {}).get("pattern", "static"),
        }

        # Propagate gap fill marker from instruction if present
        if instruction.get("_is_gap_fill"):
            metadata["is_gap_fill"] = True

        return [self._create_sequenced_effect(state, targets, timing, metadata)]

    def _resolve_pan_tilt(
        self, instruction: dict[str, Any], context: ResolverContext
    ) -> tuple[int, int]:
        """Resolve pan/tilt centers from instruction.

        Args:
            instruction: Instruction dict
            context: Resolver context

        Returns:
            (pan_center, tilt_center) tuple
        """
        # Get base pan from orientation
        pan_front = context.fixture.config.orientation.pan_front_dmx

        # Get tilt from instruction or default
        tilt_cfg = instruction.get("tilt", {})
        tilt_mode = str(tilt_cfg.get("value", "above_horizon"))
        if tilt_mode == "up":
            tilt_base = context.fixture.config.orientation.tilt_up_dmx
        elif tilt_mode == "zero":
            tilt_base = context.fixture.config.orientation.tilt_zero_dmx
        else:
            tilt_base = context.fixture.config.orientation.tilt_zero_dmx

        # Apply offsets
        movement = instruction.get("movement", {})
        pan_offset_deg = float(movement.get("pan_offset_deg", 0.0) or 0.0)
        tilt_offset_deg = float(movement.get("tilt_offset_deg", 0.0) or 0.0)

        pan_range_deg = context.sequencer_context.pan_range_deg
        tilt_range_deg = context.sequencer_context.tilt_range_deg

        pan_offset_dmx = (
            int(round((pan_offset_deg / pan_range_deg) * 255.0)) if pan_range_deg > 0 else 0
        )
        tilt_offset_dmx = (
            int(round((tilt_offset_deg / tilt_range_deg) * 255.0)) if tilt_range_deg > 0 else 0
        )

        pan_center = context.boundaries.clamp_pan(pan_front + pan_offset_dmx)
        tilt_center = context.boundaries.clamp_tilt(tilt_base + tilt_offset_dmx)

        return pan_center, tilt_center

    def _resolve_dimmer_value(self, instruction: dict[str, Any], timing: tuple[int, int]) -> int:
        """Resolve dimmer value from instruction.

        Args:
            instruction: Instruction dict
            timing: (start_ms, end_ms) tuple

        Returns:
            Dimmer DMX value (0-255)
        """
        dimmer = instruction.get("dimmer", {})
        pattern = dimmer.get("pattern", "static")

        if pattern == "blackout":
            return 0

        base_pct = dimmer.get("base_pct")
        if base_pct is None:
            base_pct = dimmer.get("min_pct", 35)

        return clamp(int(round((float(base_pct) / 100.0) * 255.0)), 0, 255)
