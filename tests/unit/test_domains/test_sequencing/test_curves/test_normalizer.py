"""Tests for CurveNormalizer class.

Following TDD - these tests are written BEFORE implementation.
Tests normalization, linear mapping, and auto-fit algorithms.
"""

from __future__ import annotations

import pytest


def test_normalizer_initialization() -> None:
    """Test CurveNormalizer can be initialized."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer

    normalizer = CurveNormalizer()
    assert normalizer is not None


def test_normalize_to_unit_range() -> None:
    """Test normalizing curve points to [0, 1] range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Points in arbitrary range
    points = [
        CurvePoint(time=0.0, value=50.0),
        CurvePoint(time=0.5, value=150.0),
        CurvePoint(time=1.0, value=250.0),
    ]

    normalized = normalizer.normalize_to_unit_range(points)

    # Should be normalized to [0, 1]
    assert normalized[0].value == 0.0  # min value -> 0
    assert normalized[2].value == 1.0  # max value -> 1
    assert 0 < normalized[1].value < 1  # middle value in (0, 1)


def test_normalize_already_normalized() -> None:
    """Test normalizing already normalized points returns same values."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.5, value=0.5),
        CurvePoint(time=1.0, value=1.0),
    ]

    normalized = normalizer.normalize_to_unit_range(points)

    assert normalized[0].value == pytest.approx(0.0)
    assert normalized[1].value == pytest.approx(0.5)
    assert normalized[2].value == pytest.approx(1.0)


def test_linear_map_to_dmx_range() -> None:
    """Test linear mapping from [0, 1] to DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Normalized points [0, 1]
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.5, value=0.5),
        CurvePoint(time=1.0, value=1.0),
    ]

    # Map to DMX range [50, 200]
    mapped = normalizer.linear_map_to_range(points, min_val=50, max_val=200)

    assert mapped[0].value == 50.0
    assert mapped[1].value == 125.0  # Middle of [50, 200]
    assert mapped[2].value == 200.0


def test_linear_map_full_dmx_range() -> None:
    """Test linear mapping to full DMX range [0, 255]."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=1.0),
    ]

    mapped = normalizer.linear_map_to_range(points, min_val=0, max_val=255)

    assert mapped[0].value == 0.0
    assert mapped[1].value == 255.0


def test_auto_fit_prevents_clipping() -> None:
    """Test auto-fit scales curve to fit within boundaries without clipping."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Curve that would exceed boundaries [0, 255]
    points = [
        CurvePoint(time=0.0, value=-50.0),
        CurvePoint(time=0.5, value=128.0),
        CurvePoint(time=1.0, value=350.0),
    ]

    # Auto-fit to [0, 255]
    fitted = normalizer.auto_fit_to_range(points, min_limit=0, max_limit=255)

    # All values should be within bounds
    assert all(0 <= p.value <= 255 for p in fitted)

    # Shape should be preserved (relative relationships)
    assert fitted[1].value > fitted[0].value
    assert fitted[2].value > fitted[1].value


def test_auto_fit_preserves_shape() -> None:
    """Test auto-fit preserves curve shape (relative proportions)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Sine-like curve exceeding [50, 200]
    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=0.25, value=150.0),
        CurvePoint(time=0.5, value=300.0),
        CurvePoint(time=0.75, value=150.0),
        CurvePoint(time=1.0, value=0.0),
    ]

    fitted = normalizer.auto_fit_to_range(points, min_limit=50, max_limit=200)

    # Check shape is preserved
    assert fitted[0].value == fitted[4].value  # Start and end same
    assert fitted[2].value > fitted[1].value  # Peak in middle
    assert fitted[1].value == fitted[3].value  # Symmetric


def test_auto_fit_no_clipping_needed() -> None:
    """Test auto-fit with curve already within bounds."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Curve already within [0, 255]
    points = [
        CurvePoint(time=0.0, value=50.0),
        CurvePoint(time=0.5, value=128.0),
        CurvePoint(time=1.0, value=200.0),
    ]

    fitted = normalizer.auto_fit_to_range(points, min_limit=0, max_limit=255)

    # Should fit within bounds (may be scaled to use full range)
    assert all(0 <= p.value <= 255 for p in fitted)


def test_normalize_and_map_pipeline() -> None:
    """Test complete pipeline: normalize then map to DMX range."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # Raw curve points
    points = [
        CurvePoint(time=0.0, value=100.0),
        CurvePoint(time=0.5, value=500.0),
        CurvePoint(time=1.0, value=900.0),
    ]

    # Step 1: Normalize to [0, 1]
    normalized = normalizer.normalize_to_unit_range(points)
    assert normalized[0].value == 0.0
    assert normalized[2].value == 1.0

    # Step 2: Map to DMX range
    mapped = normalizer.linear_map_to_range(normalized, min_val=50, max_val=200)
    assert mapped[0].value == 50.0
    assert mapped[2].value == 200.0


def test_time_values_preserved() -> None:
    """Test that time values are never modified during normalization."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [
        CurvePoint(time=0.0, value=10.0),
        CurvePoint(time=0.3, value=50.0),
        CurvePoint(time=0.7, value=90.0),
        CurvePoint(time=1.0, value=100.0),
    ]

    # Test all operations preserve time
    normalized = normalizer.normalize_to_unit_range(points)
    assert [p.time for p in normalized] == [0.0, 0.3, 0.7, 1.0]

    mapped = normalizer.linear_map_to_range(points, min_val=0, max_val=255)
    assert [p.time for p in mapped] == [0.0, 0.3, 0.7, 1.0]

    fitted = normalizer.auto_fit_to_range(points, min_limit=0, max_limit=255)
    assert [p.time for p in fitted] == [0.0, 0.3, 0.7, 1.0]


def test_empty_points_list() -> None:
    """Test handling of empty points list."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer

    normalizer = CurveNormalizer()

    # Should return empty list or raise appropriate error
    result = normalizer.normalize_to_unit_range([])
    assert result == []


def test_single_point() -> None:
    """Test handling of single point (edge case)."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [CurvePoint(time=0.5, value=128.0)]

    # Should handle gracefully (map to middle or similar)
    result = normalizer.normalize_to_unit_range(points)
    assert len(result) == 1


def test_constant_value_points() -> None:
    """Test normalization of points with constant value."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    # All points have same value
    points = [
        CurvePoint(time=0.0, value=128.0),
        CurvePoint(time=0.5, value=128.0),
        CurvePoint(time=1.0, value=128.0),
    ]

    # Should handle gracefully (map to 0.5 or similar)
    normalized = normalizer.normalize_to_unit_range(points)
    assert all(isinstance(p.value, float) for p in normalized)


def test_negative_values() -> None:
    """Test handling of negative values in curve."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [
        CurvePoint(time=0.0, value=-100.0),
        CurvePoint(time=0.5, value=0.0),
        CurvePoint(time=1.0, value=100.0),
    ]

    normalized = normalizer.normalize_to_unit_range(points)

    # Should normalize to [0, 1]
    assert normalized[0].value == 0.0
    assert normalized[1].value == 0.5
    assert normalized[2].value == 1.0


def test_large_dmx_values() -> None:
    """Test mapping to 16-bit DMX range [0, 65535]."""
    from blinkb0t.core.domains.sequencing.infrastructure.curves.normalizer import CurveNormalizer
    from blinkb0t.core.domains.sequencing.models.curves import CurvePoint

    normalizer = CurveNormalizer()

    points = [
        CurvePoint(time=0.0, value=0.0),
        CurvePoint(time=1.0, value=1.0),
    ]

    # Map to 16-bit DMX
    mapped = normalizer.linear_map_to_range(points, min_val=0, max_val=65535)

    assert mapped[0].value == 0.0
    assert mapped[1].value == 65535.0
