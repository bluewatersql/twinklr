"""
Unit tests for TransitionResolver.

Tests for priority-based transition resolution when multiple configs apply.
"""

import pytest

from blinkb0t.core.domains.sequencing.models.templates import TransitionConfig, TransitionMode
from blinkb0t.core.domains.sequencing.models.transitions import (
    GapType,
    TimelineGap,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.resolver import (
    TransitionResolver,
)


class TestTransitionResolver:
    """Test TransitionResolver priority-based resolution."""

    @pytest.fixture
    def resolver(self) -> TransitionResolver:
        """Create TransitionResolver instance."""
        return TransitionResolver()

    def test_priority_1_transition_in_wins(self, resolver):
        """Test transition_in_config has highest priority."""
        transition_in = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        transition_out = TransitionConfig(
            mode=TransitionMode.FADE_THROUGH_BLACK, duration_bars=0.25
        )

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition_in,
            transition_out_config=transition_out,
        )

        handler_name = resolver.resolve_transition_type(gap)

        # transition_in should win
        assert handler_name == "crossfade"

    def test_priority_2_transition_out(self, resolver):
        """Test transition_out_config when no transition_in."""
        transition_out = TransitionConfig(
            mode=TransitionMode.FADE_THROUGH_BLACK, duration_bars=0.25
        )

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=None,
            transition_out_config=transition_out,
        )

        handler_name = resolver.resolve_transition_type(gap)

        assert handler_name == "fade_through_black"

    def test_priority_3_gap_fill_fallback(self, resolver):
        """Test gap_fill fallback when no transition configs."""
        gap = TimelineGap(
            start_ms=0.0,
            end_ms=5000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
            transition_in_config=None,
            transition_out_config=None,
        )

        handler_name = resolver.resolve_transition_type(gap)

        assert handler_name == "gap_fill"

    def test_get_transition_config_returns_in_first(self, resolver):
        """Test get_transition_config returns transition_in first."""
        transition_in = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)
        transition_out = TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.0)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition_in,
            transition_out_config=transition_out,
        )

        config = resolver.get_transition_config(gap)

        assert config == transition_in

    def test_get_transition_config_returns_out_when_no_in(self, resolver):
        """Test get_transition_config returns transition_out when no in."""
        transition_out = TransitionConfig(
            mode=TransitionMode.FADE_THROUGH_BLACK, duration_bars=0.25
        )

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1500.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=None,
            transition_out_config=transition_out,
        )

        config = resolver.get_transition_config(gap)

        assert config == transition_out

    def test_get_transition_config_returns_none_when_no_configs(self, resolver):
        """Test get_transition_config returns None when no configs."""
        gap = TimelineGap(
            start_ms=0.0,
            end_ms=5000.0,
            gap_type=GapType.START,
            fixture_id="MH1",
            transition_in_config=None,
            transition_out_config=None,
        )

        config = resolver.get_transition_config(gap)

        assert config is None

    def test_snap_transition_mode(self, resolver):
        """Test SNAP transition mode mapping."""
        transition = TransitionConfig(mode=TransitionMode.SNAP, duration_bars=0.0)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=1000.0,  # Zero duration for snap
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition,
        )

        handler_name = resolver.resolve_transition_type(gap)

        assert handler_name == "snap"

    def test_crossfade_transition_mode(self, resolver):
        """Test CROSSFADE transition mode mapping."""
        transition = TransitionConfig(mode=TransitionMode.CROSSFADE, duration_bars=0.5)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition,
        )

        handler_name = resolver.resolve_transition_type(gap)

        assert handler_name == "crossfade"

    def test_fade_through_black_transition_mode(self, resolver):
        """Test FADE_THROUGH_BLACK transition mode mapping."""
        transition = TransitionConfig(mode=TransitionMode.FADE_THROUGH_BLACK, duration_bars=0.5)

        gap = TimelineGap(
            start_ms=1000.0,
            end_ms=2000.0,
            gap_type=GapType.MID_SEQUENCE,
            fixture_id="MH1",
            transition_in_config=transition,
        )

        handler_name = resolver.resolve_transition_type(gap)

        assert handler_name == "fade_through_black"
