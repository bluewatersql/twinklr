"""Unit tests for curve analysis and metric computation.

Tests the analyze module's statistical metrics and flag generation.
"""

from twinklr.core.reporting.evaluation.analyze import analyze_curve, check_loop_continuity
from twinklr.core.reporting.evaluation.config import EvalConfig
from twinklr.core.reporting.evaluation.models import ReportFlagLevel


def test_analyze_curve_all_zeros():
    """Analyze curve with all zero values."""
    samples = [0.0] * 100
    config = EvalConfig()

    stats, flags = analyze_curve(samples, config)

    assert stats.min == 0.0
    assert stats.max == 0.0
    assert stats.range == 0.0
    assert stats.mean == 0.0
    assert stats.std == 0.0
    assert stats.clamp_pct == 100.0  # All values at boundary (0.0)
    assert stats.energy == 0.0

    # Should flag as static curve
    assert len(flags) > 0
    # Static curve is flagged (may be INFO or WARNING)
    assert any(f.code == "STATIC_CURVE" for f in flags)


def test_analyze_curve_all_ones():
    """Analyze curve with all maximum values."""
    samples = [1.0] * 100
    config = EvalConfig()

    stats, flags = analyze_curve(samples, config)

    assert stats.min == 1.0
    assert stats.max == 1.0
    assert stats.range == 0.0
    assert stats.mean == 1.0
    assert stats.std == 0.0
    assert stats.clamp_pct == 100.0  # All clamped at max
    assert stats.energy == 0.0  # No variation

    # Should flag high clamping
    assert len(flags) > 0
    assert any("clamp" in f.message.lower() for f in flags)


def test_analyze_curve_normal_range():
    """Analyze curve with normal variation."""
    # Linear ramp from 0 to 1
    samples = [i / 99 for i in range(100)]
    config = EvalConfig()

    stats, _flags = analyze_curve(samples, config)

    assert 0.0 <= stats.min <= 0.01
    assert 0.99 <= stats.max <= 1.0
    assert 0.9 <= stats.range <= 1.0
    assert 0.4 <= stats.mean <= 0.6
    assert stats.std > 0.1  # Should have variation
    assert stats.energy > 0.0

    # Should have minimal clamping (less than 5%)
    assert stats.clamp_pct < 5.0


def test_analyze_curve_clamping_warning():
    """Curve with moderate clamping triggers warning."""
    # 60% of samples at boundaries
    samples = [0.0] * 30 + [0.5] * 40 + [1.0] * 30
    config = EvalConfig(clamp_warning_threshold=0.5, clamp_error_threshold=0.8)

    stats, flags = analyze_curve(samples, config)

    # 60% clamped (30 at 0, 30 at 1)
    assert 55.0 <= stats.clamp_pct <= 65.0

    # Should have warning flag
    warnings = [f for f in flags if f.level == ReportFlagLevel.WARNING]
    assert len(warnings) > 0
    assert any("clamp" in f.message.lower() for f in warnings)


def test_analyze_curve_clamping_error():
    """Curve with excessive clamping triggers error."""
    # 90% of samples at boundaries
    samples = [0.0] * 45 + [0.5] * 10 + [1.0] * 45
    config = EvalConfig(clamp_warning_threshold=0.5, clamp_error_threshold=0.8)

    stats, flags = analyze_curve(samples, config)

    # Curve 90% clamped
    assert stats.clamp_pct >= 80.0

    # Should have error flag
    errors = [f for f in flags if f.level == ReportFlagLevel.ERROR]
    assert len(errors) > 0
    assert any("clamp" in f.message.lower() for f in errors)


def test_analyze_curve_low_energy():
    """Curve with low energy (little variation) should be detected."""
    # Almost flat with tiny variation
    samples = [0.5 + 0.001 * i for i in range(100)]
    config = EvalConfig()

    stats, _flags = analyze_curve(samples, config)

    assert stats.energy < 0.01  # Very low energy

    # Curve is nearly static, may or may not generate flags depending on config
    # Just verify analysis completes
    assert stats.mean > 0.4
    assert stats.mean < 0.6


def test_analyze_curve_sine_wave():
    """Analyze smooth sine wave curve."""
    import math

    samples = [0.5 + 0.5 * math.sin(i * 2 * math.pi / 100) for i in range(100)]
    config = EvalConfig()

    stats, flags = analyze_curve(samples, config)

    assert -0.1 <= stats.min <= 0.1  # Near 0
    assert 0.9 <= stats.max <= 1.1  # Near 1
    assert 0.4 <= stats.mean <= 0.6  # Centered
    assert stats.std > 0.2  # Good variation
    assert stats.energy > 0.01  # Has energy

    # Should have minimal errors
    errors = [f for f in flags if f.level == ReportFlagLevel.ERROR]
    assert len(errors) == 0


def test_check_loop_continuity_perfect():
    """Check loop with perfect continuity (first == last)."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.0]
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    assert result.ok is True
    assert result.loop_delta == 0.0


def test_check_loop_continuity_small_gap():
    """Check loop with small acceptable gap."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.05]  # Small gap
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    assert result.ok is True
    assert result.loop_delta == 0.05


def test_check_loop_continuity_warning():
    """Check loop with discontinuity warning."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.15]  # Moderate gap
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    assert result.ok is False
    assert result.loop_delta == 0.15


def test_check_loop_continuity_error():
    """Check loop with large discontinuity."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.8]  # Large jump
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    assert result.ok is False
    assert result.loop_delta == 0.8


def test_check_loop_continuity_empty():
    """Check loop with empty samples."""
    samples: list[float] = []
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    # Should gracefully handle empty input
    assert result.ok is True  # Vacuously true
    assert result.loop_delta == 0.0


def test_check_loop_continuity_single_sample():
    """Check loop with single sample."""
    samples = [0.5]
    threshold = 0.1

    result = check_loop_continuity(samples, threshold)

    # Single sample is continuous with itself
    assert result.ok is True
    assert result.loop_delta == 0.0


def test_analyze_curve_custom_thresholds():
    """Test with custom threshold configuration."""
    samples = [0.0] * 60 + [0.5] * 40  # 60% clamped at 0
    config = EvalConfig(
        clamp_warning_threshold=0.4,  # Lower threshold (40%)
        clamp_error_threshold=0.7,  # Higher threshold (70%)
    )

    _stats, flags = analyze_curve(samples, config)

    # With lower warning threshold, should trigger warning
    warnings = [f for f in flags if f.level == ReportFlagLevel.WARNING]
    assert len(warnings) > 0

    # But not error (under 70%)
    errors = [f for f in flags if f.level == ReportFlagLevel.ERROR]
    assert len(errors) == 0
