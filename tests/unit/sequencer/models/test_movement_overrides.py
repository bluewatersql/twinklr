"""Tests for Movement model categorical parameter overrides."""

from pydantic import ValidationError
import pytest

from blinkb0t.core.curves.library import CurveLibrary
from blinkb0t.core.sequencer.models.enum import Intensity
from blinkb0t.core.sequencer.models.template import Movement, MovementType
from blinkb0t.core.sequencer.moving_heads.libraries.movement import (
    get_curve_categorical_params,
)


class TestMovementOverrideFields:
    """Tests for amplitude/frequency/center_offset override fields."""

    def test_movement_has_override_fields(self):
        """Test that Movement model has optional override fields."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            amplitude_override=0.8,
            frequency_override=1.5,
            center_offset_override=0.6,
        )

        assert movement.amplitude_override == 0.8
        assert movement.frequency_override == 1.5
        assert movement.center_offset_override == 0.6

    def test_override_fields_are_optional(self):
        """Test that override fields default to None."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
        )

        assert movement.amplitude_override is None
        assert movement.frequency_override is None
        assert movement.center_offset_override is None

    def test_amplitude_override_validates_range(self):
        """Test that amplitude_override must be in [0, 1]."""
        # Valid values
        Movement(movement_type=MovementType.SWEEP_LR, amplitude_override=0.0)
        Movement(movement_type=MovementType.SWEEP_LR, amplitude_override=1.0)
        Movement(movement_type=MovementType.SWEEP_LR, amplitude_override=0.5)

        # Invalid values
        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, amplitude_override=-0.1)

        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, amplitude_override=1.1)

    def test_frequency_override_validates_range(self):
        """Test that frequency_override must be in [0, 10]."""
        # Valid values
        Movement(movement_type=MovementType.SWEEP_LR, frequency_override=0.0)
        Movement(movement_type=MovementType.SWEEP_LR, frequency_override=10.0)
        Movement(movement_type=MovementType.SWEEP_LR, frequency_override=5.0)

        # Invalid values
        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, frequency_override=-0.1)

        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, frequency_override=10.1)

    def test_center_offset_override_validates_range(self):
        """Test that center_offset_override must be in [0, 1]."""
        # Valid values
        Movement(movement_type=MovementType.SWEEP_LR, center_offset_override=0.0)
        Movement(movement_type=MovementType.SWEEP_LR, center_offset_override=1.0)
        Movement(movement_type=MovementType.SWEEP_LR, center_offset_override=0.5)

        # Invalid values
        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, center_offset_override=-0.1)

        with pytest.raises(ValidationError):
            Movement(movement_type=MovementType.SWEEP_LR, center_offset_override=1.1)


class TestGetCategoricalParamsMethod:
    """Tests for Movement.get_categorical_params() method."""

    def test_method_exists(self):
        """Test that get_categorical_params method exists."""
        movement = Movement(movement_type=MovementType.SWEEP_LR)

        assert hasattr(movement, "get_categorical_params")
        assert callable(movement.get_categorical_params)

    def test_returns_base_params_when_no_overrides(self):
        """Test returns base params when no overrides are set."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
        )

        # Get base params for SWEEP_LR (uses MOVEMENT_TRIANGLE)
        base_params = get_curve_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SMOOTH)

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        assert result.amplitude == base_params.amplitude
        assert result.frequency == base_params.frequency
        assert result.center_offset == base_params.center_offset

    def test_applies_amplitude_override(self):
        """Test applies amplitude override."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            amplitude_override=0.9,
        )

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        # Amplitude should be overridden
        assert result.amplitude == 0.9

        # Other params should come from base
        base_params = get_curve_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SMOOTH)
        assert result.frequency == base_params.frequency
        assert result.center_offset == base_params.center_offset

    def test_applies_frequency_override(self):
        """Test applies frequency override."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            frequency_override=2.5,
        )

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        # Frequency should be overridden
        assert result.frequency == 2.5

        # Other params should come from base
        base_params = get_curve_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SMOOTH)
        assert result.amplitude == base_params.amplitude
        assert result.center_offset == base_params.center_offset

    def test_applies_center_offset_override(self):
        """Test applies center_offset override."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            center_offset_override=0.7,
        )

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        # Center offset should be overridden
        assert result.center_offset == 0.7

        # Other params should come from base
        base_params = get_curve_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE, Intensity.SMOOTH)
        assert result.amplitude == base_params.amplitude
        assert result.frequency == base_params.frequency

    def test_applies_multiple_overrides(self):
        """Test applies multiple overrides simultaneously."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            amplitude_override=0.9,
            frequency_override=2.5,
            center_offset_override=0.7,
        )

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        # All overrides should be applied
        assert result.amplitude == 0.9
        assert result.frequency == 2.5
        assert result.center_offset == 0.7

    def test_returns_immutable_params(self):
        """Test that returned params are immutable."""
        from pydantic import ValidationError

        movement = Movement(movement_type=MovementType.SWEEP_LR)

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_TRIANGLE)

        with pytest.raises(ValidationError):
            result.amplitude = 0.999

    def test_works_with_different_curves(self):
        """Test works with different curve types."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.DRAMATIC,
            amplitude_override=0.75,
        )

        # Should work with different curve types
        for curve_id in [
            CurveLibrary.MOVEMENT_SINE,
            CurveLibrary.MOVEMENT_TRIANGLE,
            CurveLibrary.MOVEMENT_PULSE,
        ]:
            result = movement.get_categorical_params(curve_id)

            # Override should always be applied
            assert result.amplitude == 0.75

            # Base params should vary by curve
            base_params = get_curve_categorical_params(curve_id, Intensity.DRAMATIC)
            assert result.frequency == base_params.frequency


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing templates."""

    def test_existing_templates_work_without_overrides(self):
        """Test that existing Movement instances work without override fields."""
        # This simulates an existing template that doesn't have overrides
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            cycles=2.0,
            params={"custom_param": 42},
        )

        # Should work fine
        assert movement.movement_type == MovementType.SWEEP_LR
        assert movement.intensity == Intensity.SMOOTH
        assert movement.cycles == 2.0
        assert movement.params["custom_param"] == 42

        # Overrides should be None
        assert movement.amplitude_override is None
        assert movement.frequency_override is None
        assert movement.center_offset_override is None

    def test_get_categorical_params_without_overrides_uses_base(self):
        """Test that get_categorical_params uses base params when no overrides."""
        movement = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.FAST,
        )

        result = movement.get_categorical_params(CurveLibrary.MOVEMENT_SINE)

        # Should match base params exactly
        base_params = get_curve_categorical_params(CurveLibrary.MOVEMENT_SINE, Intensity.FAST)

        assert result.amplitude == base_params.amplitude
        assert result.frequency == base_params.frequency
        assert result.center_offset == base_params.center_offset

    def test_serialization_with_overrides(self):
        """Test that Movement with overrides can be serialized/deserialized."""
        original = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
            amplitude_override=0.8,
            frequency_override=1.5,
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = Movement(**data)

        assert restored.amplitude_override == original.amplitude_override
        assert restored.frequency_override == original.frequency_override
        assert restored.center_offset_override == original.center_offset_override

    def test_serialization_without_overrides(self):
        """Test that Movement without overrides serializes cleanly."""
        original = Movement(
            movement_type=MovementType.SWEEP_LR,
            intensity=Intensity.SMOOTH,
        )

        # Serialize to dict
        data = original.model_dump()

        # Overrides should be None or excluded
        assert data.get("amplitude_override") is None
        assert data.get("frequency_override") is None
        assert data.get("center_offset_override") is None

        # Deserialize back
        restored = Movement(**data)

        assert restored.amplitude_override is None
        assert restored.frequency_override is None
        assert restored.center_offset_override is None
