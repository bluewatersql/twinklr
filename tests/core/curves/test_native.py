"""Tests for native curve specs and tuning."""

import pytest

from blinkb0t.core.curves.native import (
    NativeCurveSpec,
    NativeCurveType,
    generate_native_spec,
    tune_native_spec,
)


def test_generate_native_spec_sine_defaults() -> None:
    spec = generate_native_spec(NativeCurveType.SINE)
    assert spec.p2 == 100.0
    assert spec.p4 == 128.0


def test_generate_native_spec_ramp_defaults() -> None:
    spec = generate_native_spec(NativeCurveType.RAMP)
    assert spec.p1 == 0.0
    assert spec.p2 == 255.0


def test_native_spec_to_xlights_string() -> None:
    spec = NativeCurveSpec(type=NativeCurveType.FLAT, p1=128.0)
    value = spec.to_xlights_string(channel=1)
    assert "Type=Flat" in value
    assert "P1=128.00" in value


def test_tune_native_spec_amplitude_center() -> None:
    spec = NativeCurveSpec(type=NativeCurveType.SINE, p2=200.0, p4=128.0)
    tuned = tune_native_spec(spec, min_limit=0.0, max_limit=255.0)
    assert tuned.p2 == 127.5
    assert tuned.p4 == 127.5


def test_tune_native_spec_min_max_clamp() -> None:
    spec = NativeCurveSpec(type=NativeCurveType.RAMP, p1=-10.0, p2=300.0)
    tuned = tune_native_spec(spec, min_limit=0.0, max_limit=255.0)
    assert tuned.p1 == 0.0
    assert tuned.p2 == 255.0


def test_native_spec_invalid_range() -> None:
    with pytest.raises(ValueError, match="min_val must be less than max_val"):
        NativeCurveSpec(type=NativeCurveType.FLAT, min_val=10, max_val=0)
