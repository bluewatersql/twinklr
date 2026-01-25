"""Unit tests for plot generation with matplotlib.

Tests the plot module's ability to render curve PNG plots.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from blinkb0t.core.reporting.evaluation.plot import plot_curve


def test_plot_curve_normalized_space(tmp_path: Path):
    """Generate plot in normalized space."""
    samples = [i / 99 for i in range(100)]
    times_ms = [i * 10 for i in range(100)]
    output_path = tmp_path / "test_plot.png"

    plot_curve(
        samples=samples,
        times_ms=times_ms,
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
    times_ms = [i * 10 for i in range(100)]
    output_path = tmp_path / "test_plot_dmx.png"

    plot_curve(
        samples=samples,
        times_ms=times_ms,
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
    times_ms: list[int] = []
    output_path = tmp_path / "empty_plot.png"

    # Should not crash
    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Empty Curve",
        output_path=output_path,
        space="norm",
    )

    # May or may not create file for empty data
    # Just ensure no exception


def test_plot_curve_single_sample(tmp_path: Path):
    """Handle single sample."""
    samples = [0.5]
    times_ms = [0]
    output_path = tmp_path / "single_plot.png"

    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Single Sample",
        output_path=output_path,
        space="norm",
    )

    # Should create plot even with single point
    assert output_path.exists()


def test_plot_curve_long_title(tmp_path: Path):
    """Handle very long title."""
    samples = [0.5] * 50
    times_ms = [i * 10 for i in range(50)]
    output_path = tmp_path / "long_title.png"

    long_title = "A" * 200  # Very long title

    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title=long_title,
        output_path=output_path,
        space="norm",
    )

    assert output_path.exists()


def test_plot_curve_creates_parent_dirs(tmp_path: Path):
    """Create parent directories if they don't exist."""
    output_path = tmp_path / "subdir" / "nested" / "plot.png"
    samples = [0.5] * 50
    times_ms = [i * 10 for i in range(50)]

    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Test",
        output_path=output_path,
        space="norm",
    )

    assert output_path.exists()
    assert output_path.parent.exists()


def test_plot_curve_overwrite_existing(tmp_path: Path):
    """Overwrite existing plot file."""
    output_path = tmp_path / "overwrite.png"
    samples = [0.5] * 50
    times_ms = [i * 10 for i in range(50)]

    # Create first plot
    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="First",
        output_path=output_path,
        space="norm",
    )
    _first_size = output_path.stat().st_size

    # Overwrite with second plot
    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Second",
        output_path=output_path,
        space="norm",
    )

    # File should still exist (may be different size)
    assert output_path.exists()


def test_plot_curve_normalized_y_range(tmp_path: Path):
    """Normalized space should have y-axis 0-1."""
    samples = [0.0, 0.5, 1.0, 0.5, 0.0]
    times_ms = [0, 250, 500, 750, 1000]
    output_path = tmp_path / "norm_range.png"

    # Mock plt to check y-axis limits
    with patch("blinkb0t.core.reporting.evaluation.plot.plt") as mock_plt:
        mock_ax = Mock()
        mock_plt.subplots.return_value = (Mock(), mock_ax)

        plot_curve(
            samples=samples,
            times_ms=times_ms,
            title="Test",
            output_path=output_path,
            space="norm",
        )

        # Check ylim was set to [0, 1]
        mock_ax.set_ylim.assert_called_once_with(0, 1)


def test_plot_curve_dmx_y_range(tmp_path: Path):
    """DMX space should have y-axis 0-255."""
    samples = [0.0, 0.5, 1.0]
    times_ms = [0, 500, 1000]
    output_path = tmp_path / "dmx_range.png"

    # Mock plt to check y-axis limits
    with patch("blinkb0t.core.reporting.evaluation.plot.plt") as mock_plt:
        mock_ax = Mock()
        mock_plt.subplots.return_value = (Mock(), mock_ax)

        plot_curve(
            samples=samples,
            times_ms=times_ms,
            title="Test",
            output_path=output_path,
            space="dmx",
        )

        # Check ylim was set to [0, 255]
        mock_ax.set_ylim.assert_called_once_with(0, 255)


def test_plot_curve_bar_range_labels(tmp_path: Path):
    """Bar range should affect x-axis labels."""
    samples = [0.5] * 100
    times_ms = [i * 40 for i in range(100)]  # 4000ms total
    output_path = tmp_path / "bar_range.png"

    # 4000ms at 120 BPM = 8 bars
    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Test",
        output_path=output_path,
        space="norm",
        bar_range=(0.0, 8.0),
    )

    assert output_path.exists()


def test_plot_curve_mismatched_lengths(tmp_path: Path):
    """Handle mismatched sample and time lengths."""
    samples = [0.5] * 100
    times_ms = [i * 10 for i in range(50)]  # Half as many times
    output_path = tmp_path / "mismatch.png"

    # Should handle gracefully (will use min length)
    plot_curve(
        samples=samples,
        times_ms=times_ms,
        title="Mismatched",
        output_path=output_path,
        space="norm",
    )

    # Should still create plot
    assert output_path.exists()
