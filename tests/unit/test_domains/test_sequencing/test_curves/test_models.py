"""Tests for curve engine Pydantic models.

Following TDD - these tests are written BEFORE implementation.
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest


def test_curve_point_basic() -> None:
    """Test CurvePoint can be created with time and value."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    point = CurvePoint(time=0.5, value=128)
    assert point.time == 0.5
    assert point.value == 128


def test_curve_point_validation() -> None:
    """Test CurvePoint validates time is between 0-1."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    # Valid: time 0-1
    CurvePoint(time=0.0, value=0)
    CurvePoint(time=1.0, value=255)
    CurvePoint(time=0.5, value=128)

    # Invalid: time < 0 or > 1
    with pytest.raises(ValidationError):
        CurvePoint(time=-0.1, value=128)

    with pytest.raises(ValidationError):
        CurvePoint(time=1.1, value=128)


def test_curve_point_ordering() -> None:
    """Test CurvePoints can be sorted by time."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    points = [
        CurvePoint(time=0.8, value=200),
        CurvePoint(time=0.2, value=50),
        CurvePoint(time=0.5, value=128),
    ]

    sorted_points = sorted(points, key=lambda p: p.time)
    assert sorted_points[0].time == 0.2
    assert sorted_points[1].time == 0.5
    assert sorted_points[2].time == 0.8


def test_value_curve_spec_native() -> None:
    """Test ValueCurveSpec for xLights native curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    spec = ValueCurveSpec(
        type=NativeCurveType.SINE,
        p1=0.0,
        p2=100.0,  # amplitude
        p3=0.0,
        p4=128.0,  # center
        reverse=False,
        min_val=0,
        max_val=255,
    )

    assert spec.type == NativeCurveType.SINE
    assert spec.p2 == 100.0
    assert spec.p4 == 128.0
    assert spec.reverse is False


def test_value_curve_spec_defaults() -> None:
    """Test ValueCurveSpec has sensible defaults."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    spec = ValueCurveSpec(type=NativeCurveType.RAMP)

    # Test defaults
    assert spec.p1 == 0.0
    assert spec.p2 == 0.0
    assert spec.p3 == 0.0
    assert spec.p4 == 0.0
    assert spec.reverse is False
    assert spec.min_val == 0
    assert spec.max_val == 255


def test_value_curve_spec_validation() -> None:
    """Test ValueCurveSpec validates min/max range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import ValueCurveSpec

    # Valid range
    ValueCurveSpec(type=NativeCurveType.SINE, min_val=0, max_val=255)
    ValueCurveSpec(type=NativeCurveType.SINE, min_val=50, max_val=200)

    with pytest.raises(ValidationError):
        ValueCurveSpec(type=NativeCurveType.SINE, min_val=255, max_val=0)

    with pytest.raises(ValidationError):
        ValueCurveSpec(type=NativeCurveType.SINE, min_val=128, max_val=128)


def test_curve_definition_native() -> None:
    """Test CurveDefinition for native curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    curve_def = CurveDefinition(
        id="sine_wave",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
        description="Smooth sine wave",
    )

    assert curve_def.id == "sine_wave"
    assert curve_def.source == CurveSource.NATIVE
    assert curve_def.base_curve == "sine"
    assert curve_def.description == "Smooth sine wave"


def test_curve_definition_custom() -> None:
    """Test CurveDefinition for custom curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    curve_def = CurveDefinition(
        id="cosine_wave",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.COSINE.value,
        description="Cosine wave (complementary to sine)",
    )

    assert curve_def.id == "cosine_wave"
    assert curve_def.source == CurveSource.CUSTOM
    assert curve_def.base_curve == "cosine"


def test_curve_definition_preset() -> None:
    """Test CurveDefinition for preset curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveModifier,
        CurveSource,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    curve_def = CurveDefinition(
        id="smooth_sine",
        source=CurveSource.PRESET,
        base_curve_id="sine",  # Reference to base curve
        modifiers=[CurveModifier.REVERSE.value],
        preset_params={"amplitude": 0.8, "center": 0.5},
        description="Smooth reversed sine for gentle movements",
    )

    assert curve_def.id == "smooth_sine"
    assert curve_def.source == CurveSource.PRESET
    assert curve_def.base_curve_id == "sine"
    assert CurveModifier.REVERSE.value in curve_def.modifiers
    assert curve_def.preset_params["amplitude"] == 0.8


def test_curve_definition_defaults() -> None:
    """Test CurveDefinition has sensible defaults."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    curve_def = CurveDefinition(
        id="test_curve",
        source=CurveSource.NATIVE,
        base_curve="sine",
    )

    assert curve_def.modifiers == []
    assert curve_def.default_params == {}
    assert curve_def.metadata is None
    assert curve_def.description is None


def test_curve_definition_validation() -> None:
    """Test CurveDefinition validates required fields."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Valid
    CurveDefinition(
        id="valid_curve",
        source=CurveSource.NATIVE,
        base_curve="sine",
    )

    # Invalid: missing id
    with pytest.raises(ValidationError):
        CurveDefinition(
            source=CurveSource.NATIVE,
            base_curve="sine",
        )

    # Invalid: missing source
    with pytest.raises(ValidationError):
        CurveDefinition(
            id="test",
            base_curve="sine",
        )


def test_curve_metadata() -> None:
    """Test CurveMetadata model."""
    from blinkb0t.core.domains.sequencing.models.curves import CurveMetadata

    metadata = CurveMetadata(
        use_cases=["smooth transitions", "audience scans"],
        priority=1,
        performance_notes="Efficient native curve",
        tags=["smooth", "professional"],
    )

    assert "smooth transitions" in metadata.use_cases
    assert metadata.priority == 1
    assert metadata.performance_notes == "Efficient native curve"
    assert "smooth" in metadata.tags


def test_curve_metadata_defaults() -> None:
    """Test CurveMetadata has sensible defaults."""
    from blinkb0t.core.domains.sequencing.models.curves import CurveMetadata

    metadata = CurveMetadata()

    assert metadata.use_cases == []
    assert metadata.priority == 2  # Normal priority
    assert metadata.performance_notes is None
    assert metadata.tags == []


def test_curve_definition_with_metadata() -> None:
    """Test CurveDefinition can include metadata."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
    from blinkb0t.core.domains.sequencing.models.curves import (
        CurveDefinition,
        CurveMetadata,
    )

    metadata = CurveMetadata(
        use_cases=["smooth movements"],
        priority=1,
        tags=["native", "efficient"],
    )

    curve_def = CurveDefinition(
        id="sine_smooth",
        source=CurveSource.NATIVE,
        base_curve="sine",
        metadata=metadata,
    )

    assert curve_def.metadata is not None
    assert curve_def.metadata.priority == 1
    assert "native" in curve_def.metadata.tags


def test_models_are_json_serializable() -> None:
    """Test all models can be serialized to/from JSON."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.models.curves import (
        CurveDefinition,
        CurvePoint,
        ValueCurveSpec,
    )

    # Test CurvePoint
    point = CurvePoint(time=0.5, value=128)
    point_json = point.model_dump()
    assert point_json["time"] == 0.5
    assert point_json["value"] == 128

    # Test ValueCurveSpec
    spec = ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0, p4=128.0)
    spec_json = spec.model_dump()
    assert spec_json["type"] == "sine"  # Internal lowercase value

    # Test CurveDefinition
    curve_def = CurveDefinition(
        id="test_curve",
        source=CurveSource.NATIVE,
        base_curve="sine",
    )
    curve_json = curve_def.model_dump()
    assert curve_json["id"] == "test_curve"
    assert curve_json["source"] == "native"


def test_models_from_json() -> None:
    """Test models can be created from JSON dict."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
    from blinkb0t.core.domains.sequencing.models.curves import (
        CurveDefinition,
        CurvePoint,
        ValueCurveSpec,
    )

    # Test CurvePoint from dict
    point_data = {"time": 0.5, "value": 128}
    point = CurvePoint(**point_data)
    assert point.time == 0.5

    # Test ValueCurveSpec from dict
    spec_data = {
        "type": NativeCurveType.SINE,
        "p2": 100.0,
        "p4": 128.0,
    }
    spec = ValueCurveSpec(**spec_data)
    assert spec.p2 == 100.0

    # Test CurveDefinition from dict
    curve_data = {
        "id": "test",
        "source": "native",
        "base_curve": "sine",
    }
    curve = CurveDefinition(**curve_data)
    assert curve.id == "test"


def test_model_immutability() -> None:
    """Test models are frozen (immutable) for safety."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    point = CurvePoint(time=0.5, value=128)

    # Should not be able to modify after creation
    with pytest.raises((ValidationError, AttributeError)):
        point.time = 0.8


def test_model_equality() -> None:
    """Test models support equality comparison."""
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    point1 = CurvePoint(time=0.5, value=128)
    point2 = CurvePoint(time=0.5, value=128)
    point3 = CurvePoint(time=0.6, value=128)

    assert point1 == point2
    assert point1 != point3
