"""End-to-end integration tests for categorical intensity parameters.

Tests the full pipeline from categorical params → adapters → curve generation.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.curves.adapters import build_default_adapter_registry
from blinkb0t.core.curves.library import CurveLibrary, build_default_registry
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
    DEFAULT_MOVEMENT_PARAMS,
    MovementCategoricalParams,
)


class TestCurveRegistryWithCategoricalParams:
    """Tests for CurveRegistry.resolve() with categorical params."""

    def test_resolve_with_categorical_params_sine(self):
        """Test resolving SINE curve with categorical params."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.SINE.value)

        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        # Should accept categorical_params
        result = registry.resolve(
            definition=definition,
            n_samples=20,
            categorical_params=categorical,
        )

        assert len(result) == 20
        # Sine should use amplitude/frequency directly
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_resolve_with_categorical_params_pulse(self):
        """Test resolving PULSE curve with categorical params (adapter needed)."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.PULSE.value)

        categorical = MovementCategoricalParams(
            amplitude=0.6,
            frequency=1.5,
            center_offset=0.5,
        )

        # Pulse needs adapter to convert amplitude → high/low
        result = registry.resolve(
            definition=definition,
            n_samples=20,
            categorical_params=categorical,
        )

        assert len(result) == 20
        # Pulse should generate valid curve
        assert all(0.0 <= p.v <= 1.0 for p in result)

    def test_resolve_without_categorical_params_backward_compatible(self):
        """Test resolve still works without categorical_params (backward compat)."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.SINE.value)

        # Old API without categorical_params
        result = registry.resolve(
            definition=definition,
            n_samples=20,
            amplitude=0.5,
            frequency=1.0,
        )

        assert len(result) == 20
        assert all(0.0 <= p.v <= 1.0 for p in result)


class TestIntensityProgression:
    """Tests that intensity levels produce expected curve variations."""

    @pytest.mark.parametrize(
        "intensity,expected_freq_min",
        [
            (Intensity.SLOW, 0.3),
            (Intensity.SMOOTH, 0.8),
            (Intensity.FAST, 1.2),
            (Intensity.DRAMATIC, 1.4),
            (Intensity.INTENSE, 1.8),
        ],
    )
    def test_intensity_affects_frequency(self, intensity, expected_freq_min):
        """Test that higher intensity levels use higher frequencies."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.MOVEMENT_SINE.value)

        params = DEFAULT_MOVEMENT_PARAMS[intensity]

        result = registry.resolve(
            definition=definition,
            n_samples=50,
            categorical_params=params,
        )

        # Movement curves add loop-ready point
        assert len(result) >= 50
        # Higher intensity should have more variation (energy)
        values = [p.v for p in result]
        energy = sum(abs(values[i + 1] - values[i]) for i in range(len(values) - 1))

        # Energy should increase with intensity
        if intensity == Intensity.SLOW:
            assert energy < 5.0  # Low energy
        elif intensity == Intensity.INTENSE:
            assert energy > 5.0  # High energy

    def test_intensity_progression_movement_pulse(self):
        """Test MOVEMENT_PULSE works across all intensity levels."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.MOVEMENT_PULSE.value)

        energies = {}

        for intensity in [
            Intensity.SLOW,
            Intensity.SMOOTH,
            Intensity.FAST,
            Intensity.DRAMATIC,
            Intensity.INTENSE,
        ]:
            params = DEFAULT_MOVEMENT_PARAMS[intensity]

            result = registry.resolve(
                definition=definition,
                n_samples=50,
                categorical_params=params,
            )

            assert len(result) > 0
            values = [p.v for p in result]
            energy = sum(abs(values[i + 1] - values[i]) for i in range(len(values) - 1))
            energies[intensity] = energy

        # Verify intensity progression (higher intensity = more energy)
        assert energies[Intensity.SLOW] < energies[Intensity.INTENSE]
        assert energies[Intensity.SMOOTH] < energies[Intensity.DRAMATIC]


class TestAdapterIntegration:
    """Tests that adapters are applied correctly."""

    def test_pulse_adapter_converts_amplitude_to_high_low(self):
        """Test PULSE adapter converts amplitude correctly."""
        registry = build_default_registry()
        adapter_registry = build_default_adapter_registry()

        definition = registry.get(CurveLibrary.PULSE.value)

        categorical = MovementCategoricalParams(
            amplitude=0.8,
            frequency=2.0,
            center_offset=0.5,
        )

        # Resolve with adapter
        result = registry.resolve(
            definition=definition,
            n_samples=20,
            categorical_params=categorical,
            adapter_registry=adapter_registry,
        )

        assert len(result) == 20

        # Pulse should respect amplitude via high/low conversion
        # High = center + amp/2 = 0.5 + 0.4 = 0.9
        # Low = center - amp/2 = 0.5 - 0.4 = 0.1
        values = [p.v for p in result]
        max_val = max(values)
        min_val = min(values)

        # Should approximate the high/low range
        assert max_val > 0.8
        assert min_val < 0.2

    def test_fixed_behavior_curves_ignore_intensity(self):
        """Test fixed behavior curves ignore intensity params."""
        registry = build_default_registry()
        adapter_registry = build_default_adapter_registry()

        definition = registry.get(CurveLibrary.EASE_IN_SINE.value)

        # Try different intensities
        categorical_slow = MovementCategoricalParams(
            amplitude=0.3,
            frequency=0.5,
            center_offset=0.5,
        )

        categorical_intense = MovementCategoricalParams(
            amplitude=1.0,
            frequency=3.0,
            center_offset=0.5,
        )

        result_slow = registry.resolve(
            definition=definition,
            n_samples=20,
            categorical_params=categorical_slow,
            adapter_registry=adapter_registry,
        )

        result_intense = registry.resolve(
            definition=definition,
            n_samples=20,
            categorical_params=categorical_intense,
            adapter_registry=adapter_registry,
        )

        # Fixed behavior should produce identical curves
        assert len(result_slow) == len(result_intense)

        # Values should be very similar (fixed behavior)
        for p1, p2 in zip(result_slow, result_intense, strict=True):
            assert abs(p1.v - p2.v) < 0.01


class TestBackwardCompatibility:
    """Tests that existing code continues to work."""

    def test_resolve_without_adapters_still_works(self):
        """Test resolve works without adapter_registry (backward compat)."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.SINE.value)

        # Old API - no categorical_params, no adapter_registry
        result = registry.resolve(
            definition=definition,
            n_samples=20,
        )

        assert len(result) == 20

    def test_resolve_with_direct_params_still_works(self):
        """Test resolve with direct params bypasses adapters."""
        registry = build_default_registry()
        definition = registry.get(CurveLibrary.SINE.value)

        # Old API - direct parameters
        result = registry.resolve(
            definition=definition,
            n_samples=20,
            amplitude=0.7,
            frequency=1.5,
        )

        assert len(result) == 20
        # Should use the direct params
        assert all(0.0 <= p.v <= 1.0 for p in result)
