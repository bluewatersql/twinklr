"""Unit tests for curve extraction from IR segments.

Tests the extract module's ability to sample curves from FixtureSegment IR.
"""

from unittest.mock import Mock

from blinkb0t.core.reporting.evaluation.extract import (
    extract_curves_from_segments,
)
from blinkb0t.core.sequencer.models.enum import ChannelName


def test_extract_curves_empty_segments():
    """Extract from empty segment list returns empty dict."""
    result = extract_curves_from_segments(
        segments=[],
        section_window_ms=(0, 1000),
        samples_per_bar=96,
        bar_duration_ms=500.0,
    )
    assert result == {}


def test_extract_curves_with_static_value():
    """Extract from segment with static DMX value."""
    # Create mock segment
    seg = Mock()
    seg.fixture_id = "test_fixture"
    seg.t0_ms = 0
    seg.t1_ms = 1000
    seg.channels = {
        ChannelName.PAN: Mock(static_dmx=128, value_points=None),
    }

    result = extract_curves_from_segments(
        segments=[seg],
        section_window_ms=(0, 1000),
        samples_per_bar=10,
        bar_duration_ms=500.0,
    )

    assert "test_fixture" in result
    assert "pan" in result["test_fixture"]

    # Static values should be consistent (normalized)
    pan_samples = result["test_fixture"]["pan"]
    assert len(pan_samples) > 0
    # All samples should be ~0.5 (128/255)
    assert all(abs(s - 128 / 255) < 0.02 for s in pan_samples)


def test_extract_curves_multiple_fixtures():
    """Extract from segments with multiple fixtures."""
    seg1 = Mock()
    seg1.fixture_id = "fixture_a"
    seg1.t0_ms = 0
    seg1.t1_ms = 1000
    seg1.channels = {
        ChannelName.PAN: Mock(static_dmx=100, value_points=None),
    }

    seg2 = Mock()
    seg2.fixture_id = "fixture_b"
    seg2.t0_ms = 0
    seg2.t1_ms = 1000
    seg2.channels = {
        ChannelName.PAN: Mock(static_dmx=200, value_points=None),
    }

    result = extract_curves_from_segments(
        segments=[seg1, seg2],
        section_window_ms=(0, 1000),
        samples_per_bar=10,
        bar_duration_ms=500.0,
    )

    assert "fixture_a" in result
    assert "fixture_b" in result
    assert "pan" in result["fixture_a"]
    assert "pan" in result["fixture_b"]


def test_extract_curves_windowing():
    """Extract respects time windows."""
    seg = Mock()
    seg.fixture_id = "test_fixture"
    seg.t0_ms = 0
    seg.t1_ms = 2000
    seg.channels = {
        ChannelName.PAN: Mock(static_dmx=128, value_points=None),
    }

    # Window only 500-1000ms (one bar at 500ms/bar)
    result = extract_curves_from_segments(
        segments=[seg],
        section_window_ms=(500, 1000),
        samples_per_bar=20,
        bar_duration_ms=500.0,
    )

    pan_samples = result["test_fixture"]["pan"]
    # Should have ~20 samples (1 bar at 20 samples/bar)
    assert 15 <= len(pan_samples) <= 25


def test_extract_curves_no_channels():
    """Handle segment with no matching channels."""
    seg = Mock()
    seg.fixture_id = "test_fixture"
    seg.t0_ms = 0
    seg.t1_ms = 1000
    seg.channels = {}  # No channels

    result = extract_curves_from_segments(
        segments=[seg],
        section_window_ms=(0, 1000),
        samples_per_bar=10,
        bar_duration_ms=500.0,
    )

    # May have fixture key, but should handle gracefully
    # Either empty dict or fixture with no channels
    assert isinstance(result, dict)
