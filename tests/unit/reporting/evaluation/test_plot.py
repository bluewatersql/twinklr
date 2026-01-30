"""Unit tests for plot generation with matplotlib.

Tests the plot module's ability to render curve PNG plots.
"""

from pathlib import Path

from twinklr.core.reporting.evaluation.plot import plot_curve


def test_plot_curve_normalized_space(tmp_path: Path):
    """Generate plot in normalized space."""
    samples = [i / 99 for i in range(100)]
    output_path = tmp_path / "test_plot.png"

    plot_curve(
        samples=samples,
        title="Test Normalized Curve",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    # Check file was created
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_curve_dmx_space(tmp_path: Path):
    """Generate plot in DMX space."""
    samples = [i / 99 for i in range(100)]
    output_path = tmp_path / "test_plot_dmx.png"

    plot_curve(
        samples=samples,
        title="Test DMX Curve",
        output_path=output_path,
        space="dmx",
        bar_range=(0.0, 4.0),
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_plot_curve_empty_samples(tmp_path: Path):
    """Handle empty sample list gracefully."""
    samples: list[float] = []
    output_path = tmp_path / "empty_plot.png"

    # Should not crash
    plot_curve(
        samples=samples,
        title="Empty Curve",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    # May or may not create file for empty data
    # Just ensure no exception


def test_plot_curve_single_sample(tmp_path: Path):
    """Handle single sample."""
    samples = [0.5]
    output_path = tmp_path / "single_plot.png"

    plot_curve(
        samples=samples,
        title="Single Sample",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 1.0),
    )

    # Should create plot even with single point
    assert output_path.exists()


def test_plot_curve_long_title(tmp_path: Path):
    """Handle very long title."""
    samples = [0.5] * 50
    output_path = tmp_path / "long_title.png"

    long_title = "A" * 200  # Very long title

    plot_curve(
        samples=samples,
        title=long_title,
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    assert output_path.exists()


def test_plot_curve_creates_parent_dirs(tmp_path: Path):
    """Create parent directories if they don't exist."""
    output_path = tmp_path / "subdir" / "nested" / "plot.png"
    samples = [0.5] * 50

    plot_curve(
        samples=samples,
        title="Test",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    assert output_path.exists()
    assert output_path.parent.exists()


def test_plot_curve_overwrite_existing(tmp_path: Path):
    """Overwrite existing plot file."""
    output_path = tmp_path / "overwrite.png"
    samples = [0.5] * 50

    # Create first plot
    plot_curve(
        samples=samples,
        title="First",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )
    _first_size = output_path.stat().st_size

    # Overwrite with second plot
    plot_curve(
        samples=samples,
        title="Second",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    # File should still exist (may be different size)
    assert output_path.exists()


def test_plot_curve_normalized_y_range(tmp_path: Path):
    """Normalized space should render properly."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.0]
    output_path = tmp_path / "norm_range.png"

    # Just verify it creates the plot without error
    plot_curve(
        samples=samples,
        title="Test",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 2.0),
    )

    assert output_path.exists()


def test_plot_curve_dmx_y_range(tmp_path: Path):
    """DMX space should render properly."""
    samples = [0.0, 0.5, 1.0]
    output_path = tmp_path / "dmx_range.png"

    # Just verify it creates the plot without error
    plot_curve(
        samples=samples,
        title="Test",
        output_path=output_path,
        space="dmx",
        bar_range=(0.0, 2.0),
    )

    assert output_path.exists()


def test_plot_curve_bar_range_labels(tmp_path: Path):
    """Bar range should affect x-axis labels."""
    samples = [0.5] * 100
    output_path = tmp_path / "bar_range.png"

    # Test with 8 bar range
    plot_curve(
        samples=samples,
        title="Test",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 8.0),
    )

    assert output_path.exists()


def test_plot_curve_varying_sample_count(tmp_path: Path):
    """Handle varying sample counts."""
    samples = [0.5] * 100
    output_path = tmp_path / "varying.png"

    # Should handle any sample count
    plot_curve(
        samples=samples,
        title="Varying Count",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 4.0),
    )

    # Should still create plot
    assert output_path.exists()
