"""Integration tests for normalization pipeline.

Tests the complete workflow of:
1. Generating curves (native/custom)
2. Normalizing to [0, 1]
3. Mapping to DMX ranges
4. Auto-fitting to boundaries
"""

from __future__ import annotations

import pytest


def test_custom_curve_full_pipeline() -> None:
    """Test complete pipeline for custom curves: generate → normalize → map."""
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

    # Setup
    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="cosine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.COSINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())

    # Step 1: Generate custom curve directly in target DMX range [50, 200]
    points = generator.generate_custom_points("cosine", num_points=50, min_dmx=50, max_dmx=200)
    assert len(points) == 50

    # Step 2: Points are already in the target DMX range [50, 200]
    assert all(50 <= p.value <= 200 for p in points)


def test_native_curve_with_tuner_pipeline() -> None:
    """Test pipeline for native curves with parameter tuning."""
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Setup
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
    tuner = NativeCurveTuner()

    # Step 1: Generate native spec with large amplitude
    spec = generator.generate_native_spec("sine")
    assert spec.p2 == 200.0  # amplitude
    assert spec.p4 == 128.0  # center

    # Step 2: Tune to fit [0, 255]
    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=255)
    assert tuned.p4 - tuned.p2 >= 0  # min within bounds
    assert tuned.p4 + tuned.p2 <= 255  # max within bounds


def test_auto_fit_exceeding_curve() -> None:
    """Test auto-fit for a curve that significantly exceeds boundaries."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Extreme curve: [-1000, 5000]
    points = [
        CurvePoint(time=0.0, value=-1000.0),
        CurvePoint(time=0.5, value=2000.0),
        CurvePoint(time=1.0, value=5000.0),
    ]

    # Auto-fit to standard DMX [0, 255]
    fitted = normalizer.auto_fit_to_range(points, min_limit=0, max_limit=255)

    # Should fit perfectly within bounds
    assert fitted[0].value == pytest.approx(0.0)
    assert fitted[2].value == pytest.approx(255.0)
    assert 0 <= fitted[1].value <= 255


def test_multi_step_normalization() -> None:
    """Test multiple normalization steps (normalize → map → auto-fit)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Raw curve
    points = [
        CurvePoint(time=0.0, value=100.0),
        CurvePoint(time=1.0, value=500.0),
    ]

    # Step 1: Normalize
    normalized = normalizer.normalize_to_unit_range(points)
    assert normalized[0].value == 0.0
    assert normalized[1].value == 1.0

    # Step 2: Map to intermediate range
    mapped = normalizer.linear_map_to_range(normalized, min_val=50, max_val=250)
    assert mapped[0].value == 50.0
    assert mapped[1].value == 250.0

    # Step 3: Auto-fit to tighter range
    fitted = normalizer.auto_fit_to_range(mapped, min_limit=100, max_limit=200)
    assert all(100 <= p.value <= 200 for p in fitted)


def test_preserve_shape_through_pipeline() -> None:
    """Test that curve shape is preserved through complete pipeline."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Sine-like shape
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.25, value=100.0),
        CurvePoint(time=0.5, value=200.0),
        CurvePoint(time=0.75, value=100.0),
        CurvePoint(time=1.0, value=0.0),
    ]

    # Process through pipeline
    fitted = normalizer.auto_fit_to_range(points, min_limit=0, max_limit=255)

    # Shape should be preserved
    assert fitted[0].value == fitted[4].value  # Start and end equal
    assert fitted[2].value > fitted[1].value > fitted[0].value  # Rising
    assert fitted[2].value > fitted[3].value > fitted[4].value  # Falling
    assert fitted[1].value == fitted[3].value  # Symmetric


def test_native_and_custom_curves_produce_valid_dmx() -> None:
    """Test that both native and custom curves produce valid DMX values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import (
        CurveSource,
        CustomCurveType,
        NativeCurveType,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.generator import (
        CurveGenerator,
        CustomCurveProvider,
        NativeCurveProvider,
    )
    from blinkb0t.core.domains.sequencing.infrastructure.curves.library import CurveLibrary
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Setup
    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="native_sine",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.SINE.value,
            default_params={"amplitude": 100.0, "center": 128.0},
        )
    )
    library.register(
        CurveDefinition(
            id="custom_cosine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.COSINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    tuner = NativeCurveTuner()

    # Test native curve
    native_spec = generator.generate_native_spec("native_sine")
    tuned_spec = tuner.tune_to_fit(native_spec, min_limit=0, max_limit=255)
    assert 0 <= tuned_spec.p4 - tuned_spec.p2 <= 255
    assert 0 <= tuned_spec.p4 + tuned_spec.p2 <= 255

    # Test custom curve (already generated in [0, 255] DMX range)
    custom_points = generator.generate_custom_points(
        "custom_cosine", num_points=100, min_dmx=0, max_dmx=255
    )
    assert all(0 <= p.value <= 255 for p in custom_points)


def test_edge_case_single_point_pipeline() -> None:
    """Test pipeline with single-point curve (edge case)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Single point
    points = [CurvePoint(time=0.5, value=100.0)]

    # Normalize
    normalized = normalizer.normalize_to_unit_range(points)
    assert len(normalized) == 1

    # Map
    mapped = normalizer.linear_map_to_range(normalized, min_val=0, max_val=255)
    assert len(mapped) == 1
    assert 0 <= mapped[0].value <= 255


def test_16bit_dmx_pipeline() -> None:
    """Test pipeline with 16-bit DMX values."""
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
    from blinkb0t.core.domains.sequencing.infrastructure.curves.tuner import NativeCurveTuner
    from blinkb0t.core.domains.sequencing.models.curves import CurveDefinition

    # Setup
    library = CurveLibrary()
    library.register(
        CurveDefinition(
            id="ramp_16bit",
            source=CurveSource.NATIVE,
            base_curve=NativeCurveType.RAMP.value,
            default_params={"min": 0.0, "max": 100000.0},  # Exceeds 16-bit
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    tuner = NativeCurveTuner()

    # Generate and tune
    spec = generator.generate_native_spec("ramp_16bit")
    tuned = tuner.tune_to_fit(spec, min_limit=0, max_limit=65535)

    # Should fit within 16-bit range
    assert tuned.p1 == 0.0
    assert tuned.p2 == 65535.0
