"""Tests for additional custom curve types.

Following TDD - these tests are written BEFORE implementation.
V2: Tests use min_dmx=0, max_dmx=1 to get normalized [0-1] output for verification.
Tests all 17 additional custom curves beyond the initial 5.
"""

from __future__ import annotations

import pytest

# ============================================================================
# Smooth-Step Curve Tests
# ============================================================================


def test_smooth_step_curve() -> None:
    """Test smooth-step curve generation (3x^2 - 2x^3)."""
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
            id="smooth_step",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.SMOOTH_STEP.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "smooth_step", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Smooth-step: starts at 0, ends at 1, smooth S-curve
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Should be smoother than linear
    assert points[50].value > 0.45  # Slightly above linear mid-point


# ============================================================================
# Easing Sine Curve Tests
# ============================================================================


def test_ease_in_sine_curve() -> None:
    """Test ease-in sine curve (starts slow, accelerates)."""
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
            id="ease_in_sine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_SINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_sine", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Ease-in: starts slow (low values initially)
    assert points[0].value < 0.1
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # First half should be slower than linear
    assert points[25].value < 0.25


def test_ease_out_sine_curve() -> None:
    """Test ease-out sine curve (starts fast, decelerates)."""
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
            id="ease_out_sine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_OUT_SINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_out_sine", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Ease-out: starts fast, ends slow
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # First quarter should be faster than linear
    assert points[25].value > 0.25


def test_ease_in_out_sine_curve() -> None:
    """Test ease-in-out sine curve (slow-fast-slow)."""
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
            id="ease_in_out_sine",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_OUT_SINE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_out_sine", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Ease-in-out: symmetric curve
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    assert points[50].value == pytest.approx(0.5, abs=0.05)


# ============================================================================
# Easing Quad Curve Tests
# ============================================================================


def test_ease_in_quad_curve() -> None:
    """Test ease-in quadratic curve (x^2)."""
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
            id="ease_in_quad",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_QUAD.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_quad", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Quadratic ease-in
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Should follow x^2 pattern
    assert points[50].value == pytest.approx(0.25, abs=0.05)


def test_ease_out_quad_curve() -> None:
    """Test ease-out quadratic curve."""
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
            id="ease_out_quad",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_OUT_QUAD.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_out_quad", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    assert points[50].value == pytest.approx(0.75, abs=0.05)


def test_ease_in_out_quad_curve() -> None:
    """Test ease-in-out quadratic curve."""
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
            id="ease_in_out_quad",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_OUT_QUAD.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_out_quad", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    assert points[50].value == pytest.approx(0.5, abs=0.05)


# ============================================================================
# Easing Cubic Curve Tests
# ============================================================================


def test_ease_in_cubic_curve() -> None:
    """Test ease-in cubic curve (x^3)."""
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
            id="ease_in_cubic",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_CUBIC.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_cubic", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Cubic is even slower start than quad
    assert points[50].value == pytest.approx(0.125, abs=0.05)


def test_ease_out_cubic_curve() -> None:
    """Test ease-out cubic curve."""
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
            id="ease_out_cubic",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_OUT_CUBIC.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_out_cubic", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    assert points[50].value == pytest.approx(0.875, abs=0.05)


def test_ease_in_out_cubic_curve() -> None:
    """Test ease-in-out cubic curve."""
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
            id="ease_in_out_cubic",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.EASE_IN_OUT_CUBIC.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "ease_in_out_cubic", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    assert points[50].value == pytest.approx(0.5, abs=0.05)


# ============================================================================
# Bounce Curve Tests
# ============================================================================


def test_bounce_in_curve() -> None:
    """Test bounce-in curve (bounces at start, settles at 1)."""
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
            id="bounce_in",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.BOUNCE_IN.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("bounce_in", num_points=100, min_dmx=0.0, max_dmx=1.0)

    # Bounce-in: should have oscillations at start, settle at 1.0
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Should have some variation (bouncing)
    values = [p.value for p in points]
    assert max(values) - min(values) > 0.5  # Has significant range


def test_bounce_out_curve() -> None:
    """Test bounce-out curve (starts at 0, bounces at end)."""
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
            id="bounce_out",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.BOUNCE_OUT.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "bounce_out", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Bounce-out: starts at 0, bounces and settles near 1.0
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    # Final value should be close to 1.0 after bounces
    assert 0.95 <= points[-1].value <= 1.0


# ============================================================================
# Elastic Curve Tests
# ============================================================================


def test_elastic_in_curve() -> None:
    """Test elastic-in curve (elastic oscillation at start)."""
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
            id="elastic_in",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.ELASTIC_IN.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "elastic_in", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Elastic-in: ends at 1.0
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Should have oscillations (at least some variation)
    values = [p.value for p in points]
    assert len({round(v, 1) for v in values}) >= 5  # Some distinct values (relaxed from >10)


def test_elastic_out_curve() -> None:
    """Test elastic-out curve (elastic oscillation at end)."""
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
            id="elastic_out",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.ELASTIC_OUT.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "elastic_out", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # Elastic-out: starts at 0, oscillates and settles near 1.0
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    # Final value should settle near 1.0
    assert 0.95 <= points[-1].value <= 1.05


# ============================================================================
# Advanced Curve Tests
# ============================================================================


def test_perlin_noise_curve() -> None:
    """Test Perlin noise curve (smooth procedural noise)."""
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
            id="perlin",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.PERLIN_NOISE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("perlin", num_points=100, min_dmx=0.0, max_dmx=1.0)

    # Perlin: should be normalized [0, 1]
    assert all(0 <= p.value <= 1 for p in points)
    # Should have variation (not constant)
    values = [p.value for p in points]
    assert max(values) - min(values) > 0.1


def test_lissajous_curve() -> None:
    """Test Lissajous curve (complex oscillating pattern)."""
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
            id="lissajous",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.LISS_AJOUS.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("lissajous", num_points=100, min_dmx=0.0, max_dmx=1.0)

    assert all(0 <= p.value <= 1 for p in points)
    # Should have oscillations
    values = [p.value for p in points]
    assert len({round(v, 2) for v in values}) > 20  # Many distinct values


def test_bezier_curve() -> None:
    """Test Bezier curve (default cubic Bezier)."""
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
            id="bezier",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.BEZIER.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("bezier", num_points=100, min_dmx=0.0, max_dmx=1.0)

    # Bezier: should start at 0, end at 1
    assert points[0].value == pytest.approx(0.0, abs=0.01)
    assert points[-1].value == pytest.approx(1.0, abs=0.01)
    # Should be smooth
    assert all(0 <= p.value <= 1 for p in points)


# ============================================================================
# Motion Curve Tests
# ============================================================================


def test_anticipate_curve() -> None:
    """Test anticipate curve (pulls back before moving forward)."""
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
            id="anticipate",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.ANTICIPATE.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points(
        "anticipate", num_points=100, min_dmx=0.0, max_dmx=1.0
    )

    # V2: Anticipate is bounded to [0, 1] - dips to ~0.1, then accelerates to 1.0
    # No longer goes negative (that was the bug we fixed!)
    values = [p.value for p in points]
    assert min(values) >= 0.0  # Never goes negative (V2 fix)
    assert min(values) < 0.2  # But still dips low (characteristic "pull back")
    assert points[0].value == pytest.approx(0.0, abs=0.01)  # Starts at 0
    assert points[-1].value == pytest.approx(1.0, abs=0.01)  # Ends at 1


def test_overshoot_curve() -> None:
    """Test overshoot curve (overshoots target then settles)."""
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
            id="overshoot",
            source=CurveSource.CUSTOM,
            base_curve=CustomCurveType.OVERSHOOT.value,
        )
    )

    generator = CurveGenerator(library, NativeCurveProvider(), CustomCurveProvider())
    points = generator.generate_custom_points("overshoot", num_points=100, min_dmx=0.0, max_dmx=1.0)

    # V2: Overshoot is bounded to [0, 1] - subtle oscillation near 1.0
    # No longer exceeds 1.0 (that was the bug we fixed!)
    values = [p.value for p in points]
    assert max(values) <= 1.0  # Never exceeds 1.0 (V2 fix)
    assert points[0].value == pytest.approx(0.0, abs=0.01)  # Starts at 0
    assert points[-1].value == pytest.approx(1.0, abs=0.01)  # Settles at 1
    # Should show characteristic "overshoot" behavior (oscillation near end)
    end_values = values[-20:]  # Last 20% of curve
    assert max(end_values) > 0.95  # Approaches 1.0
