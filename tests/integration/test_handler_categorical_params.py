"""Integration tests for categorical params in movement/dimmer handlers.

Tests that handlers correctly pass categorical parameters and adapter
registry through to the curve generation pipeline.

Every call here uses **production's call shape**: intensity is supplied only as
the `generate` argument, exactly as `step_compiler.compile_step` does.
`DefaultMovementHandler.generate` reads intensity from a `params["intensity"]` key,
defaulting to SMOOTH, and production never sets that key. P1P-T3 made the argument
authoritative (P4-F1); that was reverted on 2026-11-12 at the owner's request. The
handler-level pins live in
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

    def test_handler_intensity_argument_does_not_change_curves(self):
        """P4-F1 reverted: in production's call shape every intensity renders alike."""
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

        pan_curves = []
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
            pan_curves.append([p.v for p in result.pan_curve])

        assert all(curve == pan_curves[0] for curve in pan_curves[1:])

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
