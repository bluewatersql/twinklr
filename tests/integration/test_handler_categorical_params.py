"""Integration tests for categorical params in movement/dimmer handlers.

Tests that handlers correctly pass categorical parameters and adapter
registry through to the curve generation pipeline.

Every call here uses **production's call shape**: intensity is supplied only as
the `generate` argument, exactly as `step_compiler.compile_step` does. The
earlier version of this file passed intensity twice — once as the argument and
once as a params-dict key — which is what let the suite stay green while
`DefaultMovementHandler.generate` discarded the argument and read the key that
production never sets (P4-F1/P4-M4). The key is deliberately absent below; a
dedicated pin that the argument beats a conflicting key lives in
`tests/unit/sequencer/moving_heads/test_movement_intensity.py`.
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

    def test_handler_generates_curves(self):
        """Handler resolves a library pattern into curves."""
        handler = DefaultMovementHandler()

        # Use existing pattern from library
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        params = {
            "movement_pattern": pattern,
            "geometry": GeometryType.FAN,
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

    def test_handler_intensity_affects_curves(self):
        """Rising intensity yields rising curve energy, along the whole ladder."""
        handler = DefaultMovementHandler()

        # Use sweep_lr pattern which doesn't have custom categorical_params
        pattern = MovementLibrary.PATTERNS[MovementType.SWEEP_LR]

        ladder = [
            Intensity.SLOW,
            Intensity.SMOOTH,
            Intensity.DRAMATIC,
            Intensity.FAST,
            Intensity.INTENSE,
        ]

        energies = []
        for intensity in ladder:
            params = {
                "movement_pattern": pattern,
                "geometry": GeometryType.FAN,
            }

            result = handler.generate(
                params=params,
                n_samples=50,
                cycles=2.0,
                intensity=intensity,
            )

            # Calculate energy (total variation)
            pan_values = [p.v for p in result.pan_curve]
            energies.append(
                sum(abs(pan_values[i + 1] - pan_values[i]) for i in range(len(pan_values) - 1))
            )

        # Higher intensity should have more energy, and the ends must differ
        assert energies == sorted(energies), energies
        assert energies[0] < energies[-1], energies

    def test_handler_with_dramatic_intensity(self):
        """Test handler with dramatic intensity produces significant movement."""
        handler = DefaultMovementHandler()

        # Use pan_shake pattern
        pattern = MovementLibrary.PATTERNS[MovementType.PAN_SHAKE]

        params = {
            "movement_pattern": pattern,
            "geometry": GeometryType.FAN,
        }

        result = handler.generate(
            params=params,
            n_samples=30,
            cycles=1.0,
            intensity=Intensity.DRAMATIC,  # High amplitude
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
