"""Tests for NativeCurveTuner class.

Following TDD - these tests are written BEFORE implementation.
Tests mathematical parameter tuning for xLights native curves.
"""

from __future__ import annotations

import pytest


def test_tuner_initialization() -> None:
    """Test NativeCurveTuner can be initialized."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    tuner = NativeCurveTuner()
    assert tuner is not None


def test_tune_sine_params_no_adjustment_needed() -> None:
    """Test tuning sine curve that already fits within boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Sine with amplitude 50, center 128: range [78, 178]
    # Fits within [0, 255]
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=50.0,  # amplitude
        p4=128.0,  # center
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should remain unchanged
    assert tuned.p2 == pytest.approx(50.0)
    assert tuned.p4 == pytest.approx(128.0)


def test_tune_sine_params_exceeds_boundaries() -> None:
    """Test tuning sine curve that exceeds boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Sine with amplitude 200, center 128: range [-72, 328]
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=200.0,  # amplitude
        p4=128.0,  # center
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be adjusted to fit [0, 255]
    # New center should be middle: 127.5
    # New amplitude should be half of range: 127.5
    assert tuned.p2 == pytest.approx(127.5)
    assert tuned.p4 == pytest.approx(127.5)

    # Verify fitted range
    fitted_min = tuned.p4 - tuned.p2
    fitted_max = tuned.p4 + tuned.p2
    assert fitted_min >= 0
    assert fitted_max <= 255


def test_tune_sine_asymmetric_boundary() -> None:
    """Test tuning sine to asymmetric DMX boundary (e.g., pan limited)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Sine with large amplitude
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=150.0,  # amplitude
        p4=128.0,  # center
    )

    # Fit to asymmetric range [50, 200]
    tuned = tuner.tune_to_fit(spec, min_limit=50, max_limit=200)

    # New center should be middle of [50, 200]: 125
    # New amplitude should be (200-50)/2: 75
    assert tuned.p4 == pytest.approx(125.0)
    assert tuned.p2 == pytest.approx(75.0)

    # Verify fitted range
    fitted_min = tuned.p4 - tuned.p2
    fitted_max = tuned.p4 + tuned.p2
    assert fitted_min >= 50
    assert fitted_max <= 200


def test_tune_ramp_params_no_adjustment() -> None:
    """Test tuning ramp curve that already fits."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Ramp from 0 to 255 (full range)
    spec = ValueCurveSpec(
        type=NativeCurveType.RAMP,
        p1=0.0,  # min
        p2=255.0,  # max
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should remain unchanged
    assert tuned.p1 == pytest.approx(0.0)
    assert tuned.p2 == pytest.approx(255.0)


def test_tune_ramp_params_exceeds() -> None:
    """Test tuning ramp curve that exceeds boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Ramp from -50 to 350 (exceeds [0, 255])
    spec = ValueCurveSpec(
        type=NativeCurveType.RAMP,
        p1=-50.0,  # min
        p2=350.0,  # max
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be clamped to [0, 255]
    assert tuned.p1 == pytest.approx(0.0)
    assert tuned.p2 == pytest.approx(255.0)


def test_tune_parabolic_params() -> None:
    """Test tuning parabolic curve (similar to sine)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Parabolic with amplitude 200, center 100: range [-100, 300]
    spec = ValueCurveSpec(
        type=NativeCurveType.PARABOLIC,
        p2=200.0,  # amplitude
        p4=100.0,  # center
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be adjusted to fit [0, 255]
    assert tuned.p4 == pytest.approx(127.5)
    assert tuned.p2 == pytest.approx(127.5)


def test_tune_saw_tooth_params() -> None:
    """Test tuning saw tooth curve (similar to ramp)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Saw tooth exceeding range
    spec = ValueCurveSpec(
        type=NativeCurveType.SAW_TOOTH,
        p1=-100.0,  # min
        p2=400.0,  # max
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be clamped
    assert tuned.p1 == pytest.approx(0.0)
    assert tuned.p2 == pytest.approx(255.0)


def test_tune_flat_curve() -> None:
    """Test tuning flat curve (constant value)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Flat curve with value outside range
    spec = ValueCurveSpec(
        type=NativeCurveType.FLAT,
        p1=300.0,  # constant value
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be clamped to max
    assert tuned.p1 == pytest.approx(255.0)


def test_tune_abs_sine_params() -> None:
    """Test tuning absolute sine curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Abs sine with large amplitude
    spec = ValueCurveSpec(
        type=NativeCurveType.ABS_SINE,
        p2=200.0,  # amplitude
        p4=100.0,  # center
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # Should be adjusted (similar to sine)
    assert 0 <= tuned.p4 - tuned.p2 <= 255
    assert 0 <= tuned.p4 + tuned.p2 <= 255


def test_tune_preserves_other_params() -> None:
    """Test that tuning preserves parameters not related to range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Sine with frequency (p1) and phase (p3)
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p1=2.0,  # frequency (not typically used but should be preserved)
        p2=200.0,  # amplitude
        p3=0.5,  # phase (not typically used but should be preserved)
        p4=128.0,  # center
        reverse=True,
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)

    # p1, p3, and reverse should be preserved
    assert tuned.p1 == 2.0
    assert tuned.p3 == 0.5
    assert tuned.reverse is True


def test_tune_exponential_and_logarithmic() -> None:
    """Test tuning exponential and logarithmic curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Exponential curve
    exp_spec = ValueCurveSpec(
        type=NativeCurveType.EXPONENTIAL,
        p1=-50.0,
        p2=300.0,
    )

    exp_tuned = tuner.tune_to_fit(exp_spec, min_limit=0, max_limit=255)
    assert exp_tuned.p1 == pytest.approx(0.0)
    assert exp_tuned.p2 == pytest.approx(255.0)

    # Logarithmic curve
    log_spec = ValueCurveSpec(
        type=NativeCurveType.LOGARITHMIC,
        p1=-50.0,
        p2=300.0,
    )

    log_tuned = tuner.tune_to_fit(log_spec, min_limit=0, max_limit=255)
    assert log_tuned.p1 == pytest.approx(0.0)
    assert log_tuned.p2 == pytest.approx(255.0)


def test_tune_16bit_dmx_range() -> None:
    """Test tuning for 16-bit DMX range [0, 65535]."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    # Sine with large values exceeding 16-bit range
    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=50000.0,  # amplitude
        p4=40000.0,  # center
    )

    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=65535)

    # Should fit within 16-bit range
    fitted_min = tuned.p4 - tuned.p2
    fitted_max = tuned.p4 + tuned.p2
    assert fitted_min >= 0
    assert fitted_max <= 65535


def test_tune_creates_new_instance() -> None:
    """Test that tuning creates a new ValueCurveSpec instance (immutability)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    tuner = NativeCurveTuner()

    original = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p2=200.0,
        p4=128.0,
    )

    tuned = tuner.tune_to_fit(original, min_limit=0, max_limit=255)

    # Original should remain unchanged
    assert original.p2 == 200.0
    assert original.p4 == 128.0

    # Tuned should be different
    assert tuned is not original
