"""Tests for curve engine enums.

Following TDD - these tests are written BEFORE implementation.
"""

from __future__ import annotations


def test_curve_source_enum_exists() -> None:
    """Test CurveSource enum is defined with correct values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource

    # Test enum members exist
    assert hasattr(CurveSource, "NATIVE")
    assert hasattr(CurveSource, "CUSTOM")
    assert hasattr(CurveSource, "PRESET")

    # Test values
    assert CurveSource.NATIVE.value == "native"
    assert CurveSource.CUSTOM.value == "custom"
    assert CurveSource.PRESET.value == "preset"


def test_curve_source_enum_iteration() -> None:
    """Test CurveSource enum can be iterated."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource

    sources = list(CurveSource)
    assert len(sources) == 3
    assert CurveSource.NATIVE in sources
    assert CurveSource.CUSTOM in sources
    assert CurveSource.PRESET in sources


def test_native_curve_type_enum_exists() -> None:
    """Test NativeCurveType enum is defined with xLights native curves."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType

    # Test all 8 native xLights curve types exist
    assert hasattr(NativeCurveType, "FLAT")
    assert hasattr(NativeCurveType, "RAMP")
    assert hasattr(NativeCurveType, "SINE")
    assert hasattr(NativeCurveType, "ABS_SINE")
    assert hasattr(NativeCurveType, "PARABOLIC")
    assert hasattr(NativeCurveType, "LOGARITHMIC")
    assert hasattr(NativeCurveType, "EXPONENTIAL")
    assert hasattr(NativeCurveType, "SAW_TOOTH")

    # Test values match internal representation (lowercase, converted to title case for xLights)
    assert NativeCurveType.FLAT.value == "flat"
    assert NativeCurveType.RAMP.value == "ramp"
    assert NativeCurveType.SINE.value == "sine"
    assert NativeCurveType.ABS_SINE.value == "abs sine"
    assert NativeCurveType.PARABOLIC.value == "parabolic"
    assert NativeCurveType.LOGARITHMIC.value == "logarithmic"
    assert NativeCurveType.EXPONENTIAL.value == "exponential"
    assert NativeCurveType.SAW_TOOTH.value == "saw tooth"


def test_native_curve_type_count() -> None:
    """Test NativeCurveType has exactly 8 types."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType

    types = list(NativeCurveType)
    assert len(types) == 8


def test_custom_curve_type_enum_exists() -> None:
    """Test CustomCurveType enum is defined with custom curve types."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CustomCurveType

    # Test some key custom curves exist (we'll implement 22 total)
    assert hasattr(CustomCurveType, "COSINE")
    assert hasattr(CustomCurveType, "TRIANGLE")
    assert hasattr(CustomCurveType, "S_CURVE")
    assert hasattr(CustomCurveType, "SMOOTHER_STEP")

    # Test values
    assert CustomCurveType.COSINE.value == "cosine"
    assert CustomCurveType.TRIANGLE.value == "triangle"
    assert CustomCurveType.S_CURVE.value == "s_curve"
    assert CustomCurveType.SMOOTHER_STEP.value == "smoother_step"


def test_curve_modifier_enum_exists() -> None:
    """Test CurveModifier enum is defined."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveModifier

    # Test key modifiers exist
    assert hasattr(CurveModifier, "REVERSE")
    assert hasattr(CurveModifier, "WRAP")
    assert hasattr(CurveModifier, "BOUNCE")

    # Test values
    assert CurveModifier.REVERSE.value == "reverse"
    assert CurveModifier.WRAP.value == "wrap"
    assert CurveModifier.BOUNCE.value == "bounce"


def test_categorical_level_enum_exists() -> None:
    """Test CategoricalLevel enum for LLM-friendly parameters."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CategoricalLevel

    # Test all 5 categorical levels exist
    assert hasattr(CategoricalLevel, "SMOOTH")
    assert hasattr(CategoricalLevel, "MEDIUM")
    assert hasattr(CategoricalLevel, "DRAMATIC")
    assert hasattr(CategoricalLevel, "INTENSE")
    assert hasattr(CategoricalLevel, "EXTREME")

    # Test values
    assert CategoricalLevel.SMOOTH.value == "smooth"
    assert CategoricalLevel.MEDIUM.value == "medium"
    assert CategoricalLevel.DRAMATIC.value == "dramatic"
    assert CategoricalLevel.INTENSE.value == "intense"
    assert CategoricalLevel.EXTREME.value == "extreme"


def test_categorical_level_count() -> None:
    """Test CategoricalLevel has exactly 5 levels."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CategoricalLevel

    levels = list(CategoricalLevel)
    assert len(levels) == 5


def test_categorical_level_ordering() -> None:
    """Test CategoricalLevel members are in intensity order."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CategoricalLevel

    levels = list(CategoricalLevel)
    expected_order = [
        CategoricalLevel.SMOOTH,
        CategoricalLevel.MEDIUM,
        CategoricalLevel.DRAMATIC,
        CategoricalLevel.INTENSE,
        CategoricalLevel.EXTREME,
    ]
    assert levels == expected_order


def test_enum_string_conversion() -> None:
    """Test enums can be converted to/from strings."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CategoricalLevel,
        CurveSource,
    )

    # Test string conversion
    assert CurveSource.NATIVE.value == "native"
    assert str(CurveSource.NATIVE.value) == "native"

    # Test from string (using enum constructor)
    assert CurveSource("native") == CurveSource.NATIVE
    assert CategoricalLevel("smooth") == CategoricalLevel.SMOOTH


def test_enums_are_hashable() -> None:
    """Test enums can be used as dict keys (hashable)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CategoricalLevel,
        CurveSource,
    )

    # Test can be used as dict keys
    source_dict = {CurveSource.NATIVE: "native_impl", CurveSource.CUSTOM: "custom_impl"}
    assert source_dict[CurveSource.NATIVE] == "native_impl"

    level_dict = {CategoricalLevel.SMOOTH: 0.2, CategoricalLevel.EXTREME: 1.0}
    assert level_dict[CategoricalLevel.SMOOTH] == 0.2


def test_enums_are_comparable() -> None:
    """Test enum members can be compared for equality."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource

    # Test equality
    assert CurveSource.NATIVE == CurveSource.NATIVE
    assert CurveSource.NATIVE != CurveSource.CUSTOM

    # Test identity
    assert CurveSource.NATIVE is CurveSource.NATIVE
