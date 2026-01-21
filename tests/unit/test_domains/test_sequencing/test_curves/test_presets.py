"""Tests for Curve Presets.

Following TDD - these tests are written BEFORE implementation.
Tests preset curve definitions and resolution.
"""

from __future__ import annotations

import pytest

# ============================================================================
# Preset Definition Tests
# ============================================================================


def test_create_preset_curve_definition() -> None:
    """Test creating a preset curve definition."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Preset: smooth sine (reduced amplitude sine)
    preset = CurveDefinition(
        id="smooth_sine",
        source=CurveSource.PRESET,
        base_curve_id="sine",
        preset_params={"amplitude": 50.0, "center": 127.5},
        modifiers=[],
    )

    assert preset.source == CurveSource.PRESET
    assert preset.base_curve_id == "sine"
    assert preset.preset_params["amplitude"] == 50.0


def test_create_preset_with_modifiers() -> None:
    """Test creating preset with modifiers."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveModifier,
        CurveSource,
    )
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Preset: reversed dramatic bounce
    preset = CurveDefinition(
        id="dramatic_bounce_reversed",
        source=CurveSource.PRESET,
        base_curve_id="bounce_out",
        modifiers=[CurveModifier.REVERSE],
        preset_params={"intensity": 0.8},
    )

    assert preset.modifiers == [CurveModifier.REVERSE]
    assert preset.base_curve_id == "bounce_out"


# ============================================================================
# Preset Resolution Tests
# ============================================================================


def test_resolve_simple_preset_native_base() -> None:
    """Test resolving preset with native base curve."""
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

    # Register base native curve
    library.register(
        CurveDefinition(
            id="sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 100.0, "center": 128.0},
        )
    )

    # Register preset
    library.register(
        CurveDefinition(
            id="smooth_sine",
            source=CurveSource.PRESET,
            base_curve_id="sine",
            preset_params={"amplitude": 50.0},  # Override: gentler
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Generate preset - should resolve to native sine with preset params
    spec = generator.generate_native_spec("smooth_sine")

    assert spec.type == NativeCurveType.SINE
    assert spec.p2 == 50.0  # Preset amplitude
    assert spec.p4 == 128.0  # Default center (not overridden)


def test_resolve_simple_preset_custom_base() -> None:
    """Test resolving preset with custom base curve."""
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

    # Register base custom curve
    library.register(
        CurveDefinition(
            id="bounce_out", source=CurveSource.CUSTOM, base_curve=CustomCurveType.BOUNCE_OUT.value
        )
    )

    # Register preset
    library.register(
        CurveDefinition(
            id="dramatic_bounce",
            source=CurveSource.PRESET,
            base_curve_id="bounce_out",
            preset_params={},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Generate preset points
    points = generator.generate_custom_points("dramatic_bounce", num_points=50)

    assert len(points) == 50
    # Should have bounce characteristics (bouncing at end)
    assert points[0].value == pytest.approx(0.0, abs=0.01)


def test_resolve_preset_with_reverse_modifier() -> None:
    """Test resolving preset with REVERSE modifier."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveModifier,
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

    # Base curve: ramp (0 → 1)
    library.register(
        CurveDefinition(
            id="ease_in_quad",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_QUAD.value,
        )
    )

    # Preset: reversed ramp (1 → 0)
    library.register(
        CurveDefinition(
            id="ease_out_quad_reverse",
            source=CurveSource.PRESET,
            base_curve_id="ease_in_quad",
            modifiers=[CurveModifier.REVERSE],
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Generate reversed curve
    points = generator.generate_custom_points("ease_out_quad_reverse", num_points=100)

    # Reversed: should start high, end low
    assert points[0].value > points[-1].value


def test_resolve_preset_param_override() -> None:
    """Test that runtime params can override preset params."""
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
            default_params={"amplitude": 100.0, "center": 128.0},
        )
    )

    library.register(
        CurveDefinition(
            id="smooth_sine",
            source=CurveSource.PRESET,
            base_curve_id="sine",
            preset_params={"amplitude": 50.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Override preset params at runtime
    spec = generator.generate_native_spec("smooth_sine", params={"amplitude": 75.0})

    # Should use runtime override
    assert spec.p2 == 75.0


def test_nested_preset_not_supported() -> None:
    """Test that presets cannot reference other presets (only base curves)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
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
            id="preset1",
            source=CurveSource.PRESET,
            base_curve_id="sine",
            preset_params={},
        )
    )

    library.register(
        CurveDefinition(
            id="preset2",
            source=CurveSource.PRESET,
            base_curve_id="preset1",  # Nested preset!
            preset_params={},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Should raise error or handle gracefully
    with pytest.raises(ValueError, match="Preset cannot reference another preset"):
        generator.generate_native_spec("preset2")


# ============================================================================
# Preset with DMXCurveMapper Tests
# ============================================================================


def test_map_preset_to_channel() -> None:
    """Test mapping preset through DMXCurveMapper."""
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

    library.register(
        CurveDefinition(
            id="smooth_sine",
            source=CurveSource.PRESET,
            base_curve_id="sine",
            preset_params={"amplitude": 60.0},
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    mapper = DMXCurveMapper(generator, CurveNormalizer(), NativeCurveTuner())

    # Map preset
    result = mapper.map_to_channel(
        curve_id="smooth_sine", channel_name="pan", min_limit=0, max_limit=255
    )

    assert result.type == NativeCurveType.SINE
    assert result.p2 == 60.0  # Preset amplitude


# ============================================================================
# Preset Library Loading Tests
# ============================================================================


def test_load_presets_from_dict() -> None:
    """Test loading preset definitions from dictionary."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveModifier,
        CurveSource,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary

    library = CurveLibrary()

    # Load from list (simulating JSON)
    presets_data = [
        {
            "id": "sine",
            "source": "native",
            "base_curve": "sine",
            "default_params": {"amplitude": 100.0, "center": 128.0},
        },
        {
            "id": "smooth_sine",
            "source": "preset",
            "base_curve_id": "sine",
            "preset_params": {"amplitude": 50.0},
            "modifiers": [],
        },
        {
            "id": "dramatic_sine_reversed",
            "source": "preset",
            "base_curve_id": "sine",
            "preset_params": {"amplitude": 150.0},
            "modifiers": ["reverse"],
        },
    ]

    library.load_from_dict(presets_data)

    # Check loaded
    assert library.has("sine")
    assert library.has("smooth_sine")
    assert library.has("dramatic_sine_reversed")

    # Check preset details
    smooth = library.get("smooth_sine")
    assert smooth.source == CurveSource.PRESET
    assert smooth.base_curve_id == "sine"
    assert smooth.preset_params["amplitude"] == 50.0

    dramatic = library.get("dramatic_sine_reversed")
    assert dramatic.modifiers == [CurveModifier.REVERSE]


def test_preset_validation_requires_base_curve_id() -> None:
    """Test that preset definitions require base_curve_id."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import CurveSource
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    with pytest.raises(ValueError, match="base_curve_id"):
        CurveDefinition(
            id="invalid_preset",
            source=CurveSource.PRESET,
            # Missing base_curve_id!
        )
