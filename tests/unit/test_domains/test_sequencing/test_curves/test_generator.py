"""Tests for CurveGenerator and providers.

Following TDD - these tests are written BEFORE implementation.
Uses provider pattern to avoid god-class anti-pattern.
"""

from __future__ import annotations

import pytest

# ============================================================================
# CurveGenerator (Orchestrator) Tests
# ============================================================================


def test_curve_generator_initialization() -> None:
    """Test CurveGenerator can be initialized with library and providers."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()
    native_provider = NativeCurveProvider()
    custom_provider = CustomCurveProvider()
    generator = CurveGenerator(library, native_provider, custom_provider)

    assert generator is not None


def test_curve_generator_routes_to_native_provider() -> None:
    """Test CurveGenerator routes native curves to NativeCurveProvider."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    spec = generator.generate_native_spec("sine")

    assert spec is not None
    assert spec.type == NativeCurveType.SINE


def test_curve_generator_routes_to_custom_provider() -> None:
    """Test CurveGenerator routes custom curves to CustomCurveProvider."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="cosine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.COSINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("cosine", num_points=100)

    assert len(points) == 100


# ============================================================================
# NativeCurveProvider Tests
# ============================================================================


def test_native_provider_generate_sine_spec() -> None:
    """Test NativeCurveProvider generates sine curve spec."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import NativeCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = NativeCurveProvider()
    curve_def = CurveDefinition(
        id="sine",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
    )

    spec = provider.generate(curve_def)

    assert spec.type == NativeCurveType.SINE


def test_native_provider_sine_with_params() -> None:
    """Test NativeCurveProvider maps sine parameters correctly."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import NativeCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = NativeCurveProvider()
    curve_def = CurveDefinition(
        id="sine",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
    )

    spec = provider.generate(curve_def, params={"amplitude": 100.0, "center": 128.0})

    assert spec.type == NativeCurveType.SINE
    assert spec.p2 == 100.0  # amplitude -> p2
    assert spec.p4 == 128.0  # center -> p4


def test_native_provider_ramp_with_params() -> None:
    """Test NativeCurveProvider maps ramp parameters correctly."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import NativeCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = NativeCurveProvider()
    curve_def = CurveDefinition(
        id="ramp",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.RAMP.value,
    )

    spec = provider.generate(curve_def, params={"min": 0.0, "max": 255.0})

    assert spec.type == NativeCurveType.RAMP
    assert spec.p1 == 0.0  # min -> p1
    assert spec.p2 == 255.0  # max -> p2


def test_native_provider_all_curve_types() -> None:
    """Test NativeCurveProvider supports all 8 native curve types."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import NativeCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = NativeCurveProvider()

    for curve_type in NativeCurveType:
        curve_def = CurveDefinition(
            id=curve_type.value,
            source=CurveSource.NATIVE,
            base_curve=curve_type.value,
        )
        spec = provider.generate(curve_def)
        assert spec.type == curve_type


def test_native_provider_default_params() -> None:
    """Test NativeCurveProvider uses default params when none provided."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import NativeCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = NativeCurveProvider()
    curve_def = CurveDefinition(
        id="sine",
        source=CurveSource.NATIVE,
        base_curve=NativeCurveType.SINE.value,
        default_params={"amplitude": 50.0, "center": 127.0},
    )

    spec = provider.generate(curve_def)  # No params provided

    # Should use default_params
    assert spec.p2 == 50.0
    assert spec.p4 == 127.0


# ============================================================================
# CustomCurveProvider Tests
# ============================================================================


def test_custom_provider_generate_cosine_points() -> None:
    """Test CustomCurveProvider generates cosine curve points."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="cosine",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.COSINE.value,
    )

    # Generate with custom DMX range to get normalized [0, 1] values
    points = provider.generate(curve_def, num_points=100, min_dmx=0.0, max_dmx=1.0)

    assert len(points) == 100
    assert all(0 <= p.time <= 1 for p in points)
    assert all(0 <= p.value <= 1 for p in points)


def test_custom_provider_cosine_shape() -> None:
    """Test CustomCurveProvider generates correct cosine shape."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="cosine",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.COSINE.value,
    )

    # Generate in DMX space [0, 255]
    points = provider.generate(curve_def, num_points=100, min_dmx=0.0, max_dmx=255.0)

    # Cosine: starts at max, dips to min, ends at max
    assert points[0].value == pytest.approx(255.0, abs=2.0)
    assert points[-1].value == pytest.approx(255.0, abs=2.0)
    assert any(p.value < 50.0 for p in points)  # Has values near 0


def test_custom_provider_triangle_points() -> None:
    """Test CustomCurveProvider generates triangle wave."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="triangle",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.TRIANGLE.value,
    )

    points = provider.generate(curve_def, num_points=100)

    assert len(points) == 100
    # Triangle rises then falls
    mid_idx = len(points) // 2
    assert points[mid_idx].value > points[0].value


def test_custom_provider_s_curve_points() -> None:
    """Test CustomCurveProvider generates S-curve (sigmoid)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="s_curve",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.S_CURVE.value,
    )

    # Generate in DMX space [0, 255]
    points = provider.generate(curve_def, num_points=100, min_dmx=0.0, max_dmx=255.0)

    # S-curve: starts low, smooth transition, ends high
    assert points[0].value < 50.0
    assert points[-1].value > 200.0


def test_custom_provider_variable_point_count() -> None:
    """Test CustomCurveProvider handles different point counts."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="cosine",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.COSINE.value,
    )

    for num_points in [10, 50, 100, 200]:
        points = provider.generate(curve_def, num_points=num_points)
        assert len(points) == num_points


def test_custom_provider_time_normalized() -> None:
    """Test CustomCurveProvider normalizes time to [0, 1]."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import CustomCurveProvider
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    provider = CustomCurveProvider()
    curve_def = CurveDefinition(
        id="cosine",
        source=CurveSource.CUSTOM,
        base_curve=CustomCurveType.COSINE.value,
    )

    points = provider.generate(curve_def, num_points=100)

    assert points[0].time == pytest.approx(0.0)
    assert points[-1].time == pytest.approx(1.0)

    times = [p.time for p in points]
    assert times == sorted(times)


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_generator_curve_not_found() -> None:
    """Test CurveGenerator raises error for nonexistent curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    with pytest.raises(ValueError, match="not found"):
        generator.generate_native_spec("nonexistent")


def test_generator_wrong_source_type_native() -> None:
    """Test CurveGenerator raises error when trying to generate native spec for custom curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="cosine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.COSINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    with pytest.raises(ValueError, match="not a native curve"):
        generator.generate_native_spec("cosine")


def test_generator_wrong_source_type_custom() -> None:
    """Test CurveGenerator raises error when trying to generate custom points for native curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    with pytest.raises(ValueError, match="not a custom curve"):
        generator.generate_custom_points("sine")
