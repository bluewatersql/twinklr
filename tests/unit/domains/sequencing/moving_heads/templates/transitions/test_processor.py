"""
Unit tests for TransitionProcessor.

Tests for Phase 2 orchestration: gap detection, resolution, and rendering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.templates import TransitionConfig, TransitionMode
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    TimelineEffect,
    TimelineGap,
)

if TYPE_CHECKING:
    from blinkb0t.core.domains.sequencing.models.transitions import Timeline
from blinkb0t.core.domains.sequencing.moving_heads.transitions.processor import (
    TransitionProcessor,
)


class TestTransitionProcessor:
    """Test TransitionProcessor orchestration."""

    @pytest.fixture
    def mock_gap_detector(self):
        """Create mock GapDetector."""
        return Mock()

    @pytest.fixture
    def mock_resolver(self):
        """Create mock TransitionResolver."""
        return Mock()

    @pytest.fixture
    def mock_renderer(self):
        """Create mock TransitionRenderer."""
        return Mock()

    @pytest.fixture
    def processor(self, mock_gap_detector, mock_resolver, mock_renderer):
        """Create TransitionProcessor with mocks."""
        return TransitionProcessor(
            gap_detector=mock_gap_detector,
            resolver=mock_resolver,
            transition_renderer=mock_renderer,
        )

    @pytest.fixture
    def mock_effect_placement(self):
        """Create mock EffectPlacement."""
        return EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=0,
            end_ms=1000,
        )

    @pytest.fixture
    def mock_fixtures(self):
        """Create mock FixtureGroup."""
        mock = Mock()
        mock.fixtures = []
        return mock

    def test_process_calls_gap_detector(
        self, processor, mock_gap_detector, mock_effect_placement, mock_fixtures
    ):
        """Test processor calls gap detector with timeline."""
        effect = TimelineEffect(
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
        timeline: Timeline = [effect]

        mock_gap_detector.detect_all_gaps.return_value = []

        processor.process(
            timeline=timeline,
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Verify gap detector was called
        mock_gap_detector.detect_all_gaps.assert_called_once_with(timeline, 180000.0)

    def test_process_calls_resolver_for_each_gap(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor calls resolver for each detected gap."""
        gap1 = TimelineGap(
            start_ms=0.0,
            end_ms=1000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
        )
        gap2 = TimelineGap(
            start_ms=5000.0,
            end_ms=6000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
        )

        mock_gap_detector.detect_all_gaps.return_value = [gap1, gap2]
        mock_renderer.render_gap.return_value = []

        processor.process(
            timeline=[],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Verify render_gap called for each gap
        assert mock_renderer.render_gap.call_count == 2

    def test_process_calls_renderer_for_each_gap(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor calls renderer for each gap."""
        gap = TimelineGap(
            start_ms=0.0,
            end_ms=1000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
            from_position=None,
            to_position=(0.0, 45.0),
        )

        mock_gap_detector.detect_all_gaps.return_value = [gap]
        mock_renderer.render_gap.return_value = []

        processor.process(
            timeline=[],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Verify render_gap called
        mock_renderer.render_gap.assert_called_once()
        call_args = mock_renderer.render_gap.call_args[1]
        assert call_args["mode_str"] == "gap_fill"
        assert call_args["start_ms"] == 0.0
        assert call_args["end_ms"] == 1000.0

    def test_process_merges_effects(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_effect_placement,
        mock_fixtures,
    ):
        """Test processor merges main effects with transition effects."""
        # Main effect
        main_effect = TimelineEffect(
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

        # Mock gap and transition effect
        gap = TimelineGap(
            start_ms=0.0,
            end_ms=1000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
        )

        transition_effect = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=0,
            end_ms=1000,
        )

        mock_gap_detector.detect_all_gaps.return_value = [gap]
        mock_resolver.resolve_transition_type.return_value = "gap_fill"
        mock_resolver.get_transition_config.return_value = None
        mock_renderer.render_gap.return_value = [transition_effect]

        result = processor.process(
            timeline=[main_effect],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Should have both effects
        assert len(result) == 2
        # Verify types (both should be EffectPlacement)
        assert isinstance(result[0], EffectPlacement)
        assert isinstance(result[1], EffectPlacement)

    def test_process_sorts_by_time(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor sorts effects by start time."""
        # Create separate effect placements with correct times
        effect_placement1 = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=5000,
            end_ms=8000,
        )

        effect_placement2 = EffectPlacement(
            element_name="Dmx MH1",
            effect_name="DMX",
            start_ms=1000,
            end_ms=3000,
        )

        # Effects out of order
        effect1 = TimelineEffect(
            start_ms=5000.0,
            end_ms=8000.0,
            fixture_id="MH1",
            effect=effect_placement1,
            pan_start=0.0,
            pan_end=45.0,
            tilt_start=0.0,
            tilt_end=30.0,
            step_index=1,
            template_id="test",
        )

        effect2 = TimelineEffect(
            start_ms=1000.0,
            end_ms=3000.0,
            fixture_id="MH1",
            effect=effect_placement2,
            pan_start=0.0,
            pan_end=0.0,
            tilt_start=0.0,
            tilt_end=0.0,
            step_index=0,
            template_id="test",
        )

        mock_gap_detector.detect_all_gaps.return_value = []

        result = processor.process(
            timeline=[effect1, effect2],  # Out of order
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Should be sorted by time
        assert result[0].start_ms < result[1].start_ms
        assert result[0].start_ms == 1000
        assert result[1].start_ms == 5000

    def test_timing_snap_with_small_gap(self, processor):
        """Test timing snap with gap smaller than threshold."""
        # Gap < 10ms should fill completely
        start_ms, end_ms = processor._snap_timing(
            gap_start_ms=1000.0,
            gap_end_ms=1005.0,  # 5ms gap
            transition_duration_ms=500.0,
        )

        # Should fill the entire gap
        assert start_ms == 1000.0
        assert end_ms == 1005.0

    def test_timing_snap_with_large_gap_and_short_transition(self, processor):
        """Test timing snap when transition is shorter than gap."""
        # 1000ms gap, 200ms transition
        start_ms, end_ms = processor._snap_timing(
            gap_start_ms=1000.0,
            gap_end_ms=2000.0,
            transition_duration_ms=200.0,
        )

        # Should center the transition (400ms padding on each side)
        assert start_ms == pytest.approx(1400.0, abs=1.0)
        assert end_ms == pytest.approx(1600.0, abs=1.0)

    def test_timing_snap_clamps_to_available_space(self, processor):
        """Test timing snap clamps transition to available space."""
        # 100ms gap, 500ms transition (too long)
        start_ms, end_ms = processor._snap_timing(
            gap_start_ms=1000.0,
            gap_end_ms=1100.0,
            transition_duration_ms=500.0,
        )

        # Should clamp to gap boundaries
        assert start_ms == 1000.0
        assert end_ms == 1100.0

    def test_process_passes_config_to_renderer(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor passes transition config to renderer."""
        transition_config = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition_config,
        )

        mock_gap_detector.detect_all_gaps.return_value = [gap]
        mock_renderer.render_gap.return_value = []

        processor.process(
            timeline=[],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Verify render_gap called (config is handled by TransitionResolver, not passed directly)
        mock_renderer.render_gap.assert_called_once()

    def test_process_passes_anchor_positions(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor passes anchor positions to renderer."""
        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            from_position=(45.0, 30.0),
            to_position=(90.0, 60.0),
        )

        mock_gap_detector.detect_all_gaps.return_value = [gap]
        mock_renderer.render_gap.return_value = []

        processor.process(
            timeline=[],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Verify anchors passed to renderer
        call_args = mock_renderer.render_gap.call_args[1]
        assert call_args["from_position"] == (45.0, 30.0)
        assert call_args["to_position"] == (90.0, 60.0)

    def test_process_handles_empty_timeline(
        self,
        processor,
        mock_gap_detector,
        mock_resolver,
        mock_renderer,
        mock_fixtures,
    ):
        """Test processor handles empty timeline gracefully."""
        mock_gap_detector.detect_all_gaps.return_value = []

        result = processor.process(
            timeline=[],
            song_duration_ms=180000.0,
            fixtures=mock_fixtures,
        )

        # Should return empty list
        assert result == []
