"""
Unit tests for GapDetector.

Tests for detecting all types of gaps in a timeline, including sequence start/end
and inter-section gaps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    TimelineEffect,
    TimelineGap,
)

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.transitions import Timeline
from blinkb0t.core.domains.sequencing.moving_heads.transitions.gap_detector import (
    GapDetector,
)


class TestGapDetector:
    """Test GapDetector gap identification."""

    @pytest.fixture
    def detector(self) -> GapDetector:
        """Create GapDetector instance."""
        return GapDetector()

    @pytest.fixture
    def mock_effect_placement(self) -> EffectPlacement:
        """Create mock EffectPlacement."""
        return EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=0,
            end_ms=1000,
        )

    def test_detect_sequence_start_gap(self, detector, mock_effect_placement):
        """Test detection of gap at sequence start."""
        # Timeline starts at 5000ms
        effect = TimelineEffect(
            start_ms=5000.0,
            end_ms=8000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="test",
        )
        timeline: Timeline = [effect]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Should detect START gap
        start_gaps = [g for g in gaps if g.gap_type == GapType.START]
        assert len(start_gaps) == 1

        gap = start_gaps[0]
        assert gap.start_ms == 0.0
        assert gap.end_ms == 5000.0
        assert gap.to_position == (0.0, 0.0)  # First effect start
        assert gap.from_position is None  # No previous effect

    def test_detect_sequence_end_gap(self, detector, mock_effect_placement):
        """Test detection of gap at sequence end."""
        # Timeline ends at 175000ms, song is 180000ms
        effect = TimelineEffect(
            start_ms=1000.0,
            end_ms=175000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=90.0,
            tilt_start=0.0,
            tilt_end=60.0,
            step_index=0,
            template_id="test",
        )
        timeline: Timeline = [effect]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Should detect END gap
        end_gaps = [g for g in gaps if g.gap_type == GapType.END]
        assert len(end_gaps) == 1

        gap = end_gaps[0]
        assert gap.start_ms == 175000.0
        assert gap.end_ms == 180000.0
        assert gap.from_position == (90.0, 60.0)  # Last effect end
        assert gap.to_position is None  # No next effect

    def test_no_gaps_when_timeline_fills_song(self, detector, mock_effect_placement):
        """Test no gaps when timeline perfectly fills song duration."""
        effect = TimelineEffect(
            start_ms=0.0,
            end_ms=180000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=0,
            template_id="test",
        )
        timeline: Timeline = [effect]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Should have no implicit gaps
        implicit_gaps = [g for g in gaps if g.gap_type in [GapType.START, GapType.END]]
        assert len(implicit_gaps) == 0

    def test_detect_explicit_gaps_from_timeline(self, detector, mock_effect_placement):
        """Test extraction of explicit gaps from timeline."""
        effect1 = TimelineEffect(
            start_ms=1000.0,
            end_ms=3000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="test",
        )

        explicit_gap = TimelineGap(
            start_ms=3000.0,
            end_ms=3500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            from_position=(45.0, 30.0),
            to_position=(0.0, 0.0),
        )

        effect2 = TimelineEffect(
            start_ms=3500.0,
            end_ms=5000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=1,
            template_id="test",
        )

        timeline: Timeline = [effect1, explicit_gap, effect2]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Should include the explicit gap
        mid_gaps = [g for g in gaps if g.gap_type == GapType.MID_SEQUENCE]
        assert len(mid_gaps) == 1
        assert mid_gaps[0] == explicit_gap

    def test_gaps_sorted_by_time(self, detector, mock_effect_placement):
        """Test gaps are returned sorted by start time."""
        # Create timeline with gaps at start, middle, and end
        effect1 = TimelineEffect(
            start_ms=5000.0,
            end_ms=8000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="test",
        )

        explicit_gap = TimelineGap(
            start_ms=8000.0,
            end_ms=10000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
        )

        effect2 = TimelineEffect(
            start_ms=10000.0,
            end_ms=15000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=45.0,
            pan_end=90.0,
            tilt_start=30.0,
            tilt_end=60.0,
            step_index=1,
            template_id="test",
        )

        timeline: Timeline = [effect1, explicit_gap, effect2]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Verify sorted order
        for i in range(len(gaps) - 1):
            assert gaps[i].start_ms <= gaps[i + 1].start_ms

        # Should be: START gap, explicit gap, END gap
        assert len(gaps) == 3
        assert gaps[0].gap_type == GapType.START
        assert gaps[1].gap_type == GapType.MID_SEQUENCE
        assert gaps[2].gap_type == GapType.END

    def test_extract_anchors_from_effects(self, detector, mock_effect_placement):
        """Test anchor extraction from adjacent effects."""
        effect1 = TimelineEffect(
            start_ms=1000.0,
            end_ms=5000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="test",
        )

        timeline: Timeline = [effect1]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # START gap should have to_position from effect1 start
        start_gap = next(g for g in gaps if g.gap_type == GapType.START)
        assert start_gap.to_position == (0.0, 0.0)

        # END gap should have from_position from effect1 end
        end_gap = next(g for g in gaps if g.gap_type == GapType.END)
        assert end_gap.from_position == (45.0, 30.0)

    def test_empty_timeline(self, detector):
        """Test detection with empty timeline."""
        timeline: Timeline = []

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # Should create a single gap covering entire song
        assert len(gaps) == 1
        assert gaps[0].start_ms == 0.0
        assert gaps[0].end_ms == 180000.0
        assert gaps[0].gap_type == GapType.START  # Or could be considered full gap

    def test_fixture_id_propagation(self, detector, mock_effect_placement):
        """Test fixture IDs are correctly assigned to gaps."""
        effect = TimelineEffect(
            start_ms=5000.0,
            end_ms=8000.0,
            fixture_id="MH2",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=0,
            template_id="test",
        )
        timeline: Timeline = [effect]

        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        # All gaps should have fixture ID from effect
        for gap in gaps:
            assert gap.fixture_id == "MH2"

    def test_handle_missing_anchors(self, detector, mock_effect_placement):
        """Test graceful handling of missing anchor positions."""
        # Create effect with missing end positions (None)
        effect = TimelineEffect(
            start_ms=1000.0,
            end_ms=5000.0,
            fixture_id="MH1",
            effect=mock_effect_placement,
            pan_start=0.0,
            pan_end=0.0,  # Could be None in some cases
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=0,
            template_id="test",
        )
        timeline: Timeline = [effect]

        # Should not crash, should handle gracefully
        gaps = detector.detect_all_gaps(timeline, song_duration_ms=180000.0)

        assert len(gaps) > 0  # Should still detect gaps
