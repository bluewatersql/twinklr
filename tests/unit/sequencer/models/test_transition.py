"""Unit tests for the plan schema's transition hint."""

from twinklr.core.curves.library import CurveLibrary
from twinklr.core.sequencer.models.enum import TransitionMode
from twinklr.core.sequencer.models.transition import TransitionHint, TransitionStrategy


class TestTransitionStrategy:
    """Test TransitionStrategy enum."""

    def test_all_strategies_defined(self):
        """Test all expected strategies are defined."""
        assert TransitionStrategy.SNAP == "snap"
        assert TransitionStrategy.SMOOTH_INTERPOLATION == "smooth"
        assert TransitionStrategy.CROSSFADE == "crossfade"
        assert TransitionStrategy.FADE_VIA_BLACK == "fade_via_black"
        assert TransitionStrategy.SEQUENCE == "sequence"


class TestTransitionHint:
    """Test TransitionHint model."""

    def test_crossfade_transition(self):
        """Test creating a crossfade transition."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE, duration_bars=1.0, curve=CurveLibrary.LINEAR
        )

        assert hint.mode == TransitionMode.CROSSFADE
        assert hint.duration_bars == 1.0
        assert hint.curve == CurveLibrary.LINEAR

    def test_with_channel_overrides(self):
        """Test transition hint with per-channel overrides."""
        hint = TransitionHint(
            mode=TransitionMode.CROSSFADE,
            duration_bars=1.5,
            per_channel_overrides={
                "dimmer": TransitionStrategy.FADE_VIA_BLACK,
                "color": TransitionStrategy.SNAP,
            },
        )

        assert hint.per_channel_overrides is not None
        assert hint.per_channel_overrides.dimmer == TransitionStrategy.FADE_VIA_BLACK
        assert hint.per_channel_overrides.color == TransitionStrategy.SNAP
        assert hint.per_channel_overrides.pan is None
