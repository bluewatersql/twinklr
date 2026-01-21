"""Tests for DMXCurveMapper class.

Following TDD - these tests are written BEFORE implementation.
Tests the integration layer that ties together generator, normalizer, tuner, and boundary enforcer.
"""

from __future__ import annotations

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.xlights_adapter import CustomCurveSpec

# ============================================================================
# Initialization Tests
# ============================================================================


def test_dmx_mapper_initialization() -> None:
    """Test DMXCurveMapper can be initialized with dependencies."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    normalizer = CurveNormalizer()
    tuner = NativeCurveTuner()

    mapper = DMXCurveMapper(generator, normalizer, tuner)

    assert mapper is not None


# ============================================================================
# Auto-Fit Decision Logic Tests
# ============================================================================


def test_should_apply_auto_fit_explicit_override_true() -> None:
    """Test explicit auto_fit=True override."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Explicit override should take priority
    assert mapper._should_apply_auto_fit("pan", None, explicit_override=True) is True
    assert mapper._should_apply_auto_fit("pan", {"enforce_boundaries": False}, True) is True


def test_should_apply_auto_fit_explicit_override_false() -> None:
    """Test explicit auto_fit=False override."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Explicit override should take priority even if geometry says True
    assert mapper._should_apply_auto_fit("pan", None, explicit_override=False) is False
    assert mapper._should_apply_auto_fit("pan", {"enforce_boundaries": True}, False) is False


def test_should_apply_auto_fit_geometry_config() -> None:
    """Test auto-fit decision based on geometry config."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Geometry config: enforce boundaries
    assert mapper._should_apply_auto_fit("pan", {"enforce_boundaries": True}, None) is True

    # Geometry config: don't enforce boundaries
    assert mapper._should_apply_auto_fit("pan", {"enforce_boundaries": False}, None) is False


def test_should_apply_auto_fit_per_channel_config() -> None:
    """Test per-channel auto-fit configuration."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Per-channel configuration
    geometry_config = {"enforce_boundaries": {"pan": True, "tilt": False, "dimmer": False}}

    assert mapper._should_apply_auto_fit("pan", geometry_config, None) is True
    assert mapper._should_apply_auto_fit("tilt", geometry_config, None) is False
    assert mapper._should_apply_auto_fit("dimmer", geometry_config, None) is False


def test_should_apply_auto_fit_channel_defaults() -> None:
    """Test default auto-fit behavior per channel type."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # No config: use channel defaults
    assert mapper._should_apply_auto_fit("pan", None, None) is True  # Physical limits
    assert mapper._should_apply_auto_fit("tilt", None, None) is True  # Physical limits
    assert mapper._should_apply_auto_fit("dimmer", None, None) is False  # Full range OK


# ============================================================================
# Native Curve Mapping Tests
# ============================================================================


def test_map_native_curve_with_auto_fit() -> None:
    """Test mapping native curve with auto-fit enabled."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 200.0, "center": 128.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Map with auto-fit (amplitude 200 exceeds [0, 255])
    result = mapper.map_to_channel(
        curve_id="sine",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        auto_fit=True,
    )

    # Should return tuned ValueCurveSpec
    assert result.type == NativeCurveType.SINE
    # Tuned amplitude should fit within [0, 255]
    assert result.p4 - result.p2 >= 0  # min >= 0
    assert result.p4 + result.p2 <= 255  # max <= 255


def test_map_native_curve_without_auto_fit() -> None:
    """Test mapping native curve with auto-fit disabled."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 200.0, "center": 128.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Map without auto-fit
    result = mapper.map_to_channel(
        curve_id="sine",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        auto_fit=False,
    )

    # Should return original spec (not tuned)
    assert result.type == NativeCurveType.SINE
    assert result.p2 == 200.0  # Original amplitude unchanged
    assert result.p4 == 128.0  # Original center unchanged


# ============================================================================
# Custom Curve Mapping Tests
# ============================================================================


def test_map_custom_curve_with_auto_fit() -> None:
    """Test mapping custom curve with auto-fit enabled."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
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
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Map with auto-fit to narrow range
    result = mapper.map_to_channel(
        curve_id="cosine", channel_name="pan", min_limit=50, max_limit=200, auto_fit=True
    )

    # Should return CustomCurveSpec with points
    assert isinstance(result, CustomCurveSpec)
    assert len(result.points) > 0

    # All values should fit within [50, 200]
    values = [p.value for p in result.points]
    assert all(50 <= v <= 200 for v in values)


def test_map_custom_curve_without_auto_fit() -> None:
    """Test mapping custom curve with auto-fit disabled."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="anticipate",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.ANTICIPATE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Map without auto-fit (anticipate goes negative)
    result = mapper.map_to_channel(
        curve_id="anticipate",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        auto_fit=False,
    )

    # Should return CustomCurveSpec with points
    assert isinstance(result, CustomCurveSpec)

    # Anticipate curve should have pullback (values dip below starting point)
    # Note: Constrained to [0, 255] DMX range, doesn't go negative
    values = [p.value for p in result.points]
    # Check that curve dips (has values below the max)
    min_val = min(values)
    max_val = max(values)
    assert min_val < max_val * 0.5  # Significant dip (less than 50% of max)


# ============================================================================
# Geometry-Based Auto-Fit Tests
# ============================================================================


def test_map_with_geometry_enforce_boundaries() -> None:
    """Test mapping with geometry config that enforces boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 200.0, "center": 128.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Geometry config: enforce boundaries
    result = mapper.map_to_channel(
        curve_id="sine",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        geometry_config={"type": "fan", "enforce_boundaries": True},
    )

    # Should apply auto-fit (tuned parameters)
    assert result.p4 - result.p2 >= 0
    assert result.p4 + result.p2 <= 255


def test_map_with_geometry_no_enforce() -> None:
    """Test mapping with geometry config that doesn't enforce boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="overshoot",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.OVERSHOOT.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Geometry config: don't enforce boundaries (sky circles)
    result = mapper.map_to_channel(
        curve_id="overshoot",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        geometry_config={"type": "sky_circles", "enforce_boundaries": False},
    )

    # Should NOT apply auto-fit (overshoot can exceed 1.0)
    values = [p.value for p in result.points]
    assert max(values) > 1.0  # Overshoots


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_map_nonexistent_curve_raises_error() -> None:
    """Test mapping nonexistent curve raises appropriate error."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner

    library = CurveLibrary()
    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    with pytest.raises(ValueError, match="not found"):
        mapper.map_to_channel(
            curve_id="nonexistent", channel_name="pan", min_limit=0, max_limit=255
        )


def test_map_with_custom_params() -> None:
    """Test mapping with custom parameter overrides."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.dmx_mapper import DMXCurveMapper
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 100.0, "center": 128.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Override with custom amplitude
    result = mapper.map_to_channel(
        curve_id="sine",
        channel_name="pan",
        min_limit=0,
        max_limit=255,
        params={"amplitude": 50.0},
        auto_fit=False,
    )

    # Should use overridden amplitude
    assert result.p2 == 50.0
