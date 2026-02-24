"""Integration tests for categorical params in movement/dimmer handlers.

Tests that handlers correctly pass categorical parameters and adapter
registry through to the curve generation pipeline.
"""

from __future__ import annotations

from twinklr.core.sequencer.models.enum import Intensity
from twinklr.core.sequencer.moving_heads.handlers.movement.default import (
    DefaultMovementHandler,
)
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import (
    MovementLibrary,
    MovementType,
)


class TestMovementHandlerCategoricalParams:
    """Tests for DefaultMovementHandler with categorical parameters."""

    def test_handler_generates_curves_currently(self):
        """Test handler generates curves with current implementation."""
        # This test documents current behavior - categorical params are already
        # extracted and passed to generate_curve, but not through registry adapter system
        handler = DefaultMovementHandler()

        # Use existing pattern from library
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        params = {
            "movement_pattern": pattern,
            "geometry": GeometryType.FAN,
            "intensity": Intensity.FAST,
        }

        # Generate curves
        result = handler.generate(
            params=params,
            n_samples=20,
            cycles=2.0,
            intensity=Intensity.FAST,
        )

        # Should generate valid curves
        assert result.pan_curve is not None
        assert len(result.pan_curve) > 0
        assert result.tilt_curve is not None or result.tilt_static_dmx is not None

    def test_handler_intensity_affects_curves_currently(self):
        """Test that different intensities produce different curve energies (current behavior)."""
        handler = DefaultMovementHandler()

        # Use sweep_lr pattern which doesn't have custom categorical_params
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        results = {}
        for intensity in [Intensity.SLOW, Intensity.SMOOTH, Intensity.FAST, Intensity.DRAMATIC]:
            params = {
                "movement_pattern": pattern,
                "geometry": GeometryType.FAN,
                "intensity": intensity,
            }

            result = handler.generate(
                params=params,
                n_samples=50,
                cycles=2.0,
                intensity=intensity,
            )

            # Calculate energy (total variation)
            pan_values = [p.v for p in result.pan_curve]
            pan_energy = sum(
                abs(pan_values[i + 1] - pan_values[i]) for i in range(len(pan_values) - 1)
            )
            results[intensity] = pan_energy

        # Higher intensity should have more energy
        assert results[Intensity.SLOW] < results[Intensity.FAST]
        assert results[Intensity.SMOOTH] < results[Intensity.DRAMATIC]

    def test_handler_with_dramatic_intensity(self):
        """Test handler with dramatic intensity produces significant movement."""
        handler = DefaultMovementHandler()

        # Use pan_shake pattern
        pattern = MovementLibrary.PATTERNS[MovementType.PAN_SHAKE]

        params = {
            "movement_pattern": pattern,
            "geometry": GeometryType.FAN,
            "intensity": Intensity.DRAMATIC,  # High amplitude
        }

        result = handler.generate(
            params=params,
            n_samples=30,
            cycles=1.0,
            intensity=Intensity.DRAMATIC,
        )

        # Should generate valid curves
        assert result.pan_curve is not None
        pan_values = [p.v for p in result.pan_curve]
        value_range = max(pan_values) - min(pan_values)

        # DRAMATIC intensity should have significant range
        assert value_range > 0.1  # Should have noticeable movement

    def test_handler_backward_compatibility_no_adapter(self):
        """Test handler works without adapter registry (backward compat)."""
        handler = DefaultMovementHandler()
        # Note: No adapter registry set

        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        params = {
            "movement_pattern": pattern,
            "geometry": GeometryType.FAN,
            "intensity": Intensity.SMOOTH,
        }

        # Should still work (falls back to direct params)
        result = handler.generate(
            params=params,
            n_samples=20,
            cycles=1.0,
            intensity=Intensity.SMOOTH,
        )

        assert result.pan_curve is not None
        assert len(result.pan_curve) > 0
