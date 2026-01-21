"""Unit tests for TransitionRenderer.

Follows TDD principles - tests written before implementation.

Tests cover all three transition modes:
1. SNAP - Instant cut (no blending)
2. CROSSFADE - Smooth blend with optional easing
3. FADE_THROUGH_BLACK - Dim out, snap position, dim in
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.xsq import EffectPlacement
from blinkb0t.core.domains.sequencing.models.templates import TransitionMode
from blinkb0t.core.domains.sequencing.moving_heads.transitions import (
    TransitionContext,
    TransitionRenderer,
)


class TestTransitionRenderer:
    """Test suite for TransitionRenderer."""

    @pytest.fixture
    def mock_time_resolver(self):
        """Mock TimeResolver with bars_to_ms."""
        resolver = Mock()
        # 1 bar = 2000ms @ 120 BPM
        resolver.bars_to_ms = Mock(side_effect=lambda bars, **kwargs: int(bars * 2000))
        return resolver

    @pytest.fixture
    def mock_dmx_curve_mapper(self):
        """Mock DMXCurveMapper."""
        return Mock()

    @pytest.fixture
    def renderer(self, mock_time_resolver, mock_dmx_curve_mapper):
        """Create TransitionRenderer instance."""
        return TransitionRenderer(
            time_resolver=mock_time_resolver,
            dmx_curve_mapper=mock_dmx_curve_mapper,
        )

    @pytest.fixture
    def simple_effects_from(self):
        """Create simple 'from' effects for testing."""
        return [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=0,
                end_ms=1000,
                effect_label="pan:0→50",
            ),
            EffectPlacement(
                element_name="MH1-Tilt",
                effect_name="Value Curve",
                start_ms=0,
                end_ms=1000,
                effect_label="tilt:0→50",
            ),
            EffectPlacement(
                element_name="MH1-Dimmer",
                effect_name="On",
                start_ms=0,
                end_ms=1000,
                effect_label="255",
            ),
        ]

    @pytest.fixture
    def simple_effects_to(self):
        """Create simple 'to' effects for testing."""
        return [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=1000,
                end_ms=2000,
                effect_label="pan:50→100",
            ),
            EffectPlacement(
                element_name="MH1-Tilt",
                effect_name="Value Curve",
                start_ms=1000,
                end_ms=2000,
                effect_label="tilt:50→100",
            ),
            EffectPlacement(
                element_name="MH1-Dimmer",
                effect_name="On",
                start_ms=1000,
                end_ms=2000,
                effect_label="200",
            ),
        ]

    # ========================================================================
    # SNAP Mode Tests
    # ========================================================================

    def test_snap_returns_empty_list(self, renderer, simple_effects_from, simple_effects_to):
        """Test SNAP mode returns no transition effects (instant cut)."""
        effects = renderer.render_transition(
            mode=TransitionMode.SNAP,
            duration_bars=0.0,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        assert effects == []
        assert len(effects) == 0

    def test_snap_ignores_curve_parameter(self, renderer, simple_effects_from, simple_effects_to):
        """Test SNAP mode ignores curve parameter."""
        effects = renderer.render_transition(
            mode=TransitionMode.SNAP,
            duration_bars=1.0,  # Duration ignored
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
            curve="ease_in_out_sine",  # Curve ignored
        )

        assert effects == []

    # ========================================================================
    # CROSSFADE Mode Tests
    # ========================================================================

    def test_crossfade_returns_transition_effects(
        self, renderer, simple_effects_from, simple_effects_to
    ):
        """Test CROSSFADE mode generates transition effects."""
        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,  # 1 second @ 120 BPM
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        assert len(effects) > 0
        assert all(isinstance(e, EffectPlacement) for e in effects)

    def test_crossfade_covers_all_channels(self, renderer, simple_effects_from, simple_effects_to):
        """Test CROSSFADE creates effects for all channels."""
        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        # Extract element names (channels)
        channels = {e.element_name for e in effects}

        # Should have pan, tilt, dimmer
        assert "MH1-Pan" in channels
        assert "MH1-Tilt" in channels
        assert "MH1-Dimmer" in channels

    def test_crossfade_timing_correct(self, renderer, simple_effects_from, simple_effects_to):
        """Test CROSSFADE effects have correct timing."""
        start_ms = 1000
        duration_bars = 0.5  # 1 second
        expected_end_ms = start_ms + 1000

        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=duration_bars,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=start_ms,
        )

        for effect in effects:
            assert effect.start_ms == start_ms
            assert effect.end_ms == expected_end_ms

    def test_crossfade_with_easing_curve(self, renderer, simple_effects_from, simple_effects_to):
        """Test CROSSFADE with easing curve."""
        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
            curve="ease_in_out_sine",
        )

        assert len(effects) > 0
        # Effects should be labeled with "blend" to indicate transition
        assert any("blend" in e.effect_label.lower() for e in effects if e.effect_label)

    def test_crossfade_handles_partial_channel_overlap(self, renderer):
        """Test CROSSFADE when only some channels are present."""
        from_effects = [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=0,
                end_ms=1000,
                effect_label="pan:0→50",
            )
        ]

        to_effects = [
            EffectPlacement(
                element_name="MH1-Tilt",
                effect_name="Value Curve",
                start_ms=1000,
                end_ms=2000,
                effect_label="tilt:0→50",
            )
        ]

        effects = renderer.render_transition(
            mode=TransitionMode.CROSSFADE,
            duration_bars=0.5,
            from_effects=from_effects,
            to_effects=to_effects,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        # Should handle partial overlap gracefully
        assert len(effects) >= 2  # Fade out pan, fade in tilt

    # ========================================================================
    # FADE_THROUGH_BLACK Mode Tests
    # ========================================================================

    def test_fade_through_black_returns_effects(
        self, renderer, simple_effects_from, simple_effects_to
    ):
        """Test FADE_THROUGH_BLACK mode generates transition effects."""
        effects = renderer.render_transition(
            mode=TransitionMode.FADE_THROUGH_BLACK,
            duration_bars=1.0,  # 2 seconds @ 120 BPM
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        assert len(effects) > 0
        assert all(isinstance(e, EffectPlacement) for e in effects)

    def test_fade_through_black_has_dimmer_effects(
        self, renderer, simple_effects_from, simple_effects_to
    ):
        """Test FADE_THROUGH_BLACK creates dimmer effects (fade out + fade in)."""
        effects = renderer.render_transition(
            mode=TransitionMode.FADE_THROUGH_BLACK,
            duration_bars=1.0,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        # Should have dimmer effects
        dimmer_effects = [e for e in effects if "Dimmer" in e.element_name]
        assert len(dimmer_effects) >= 2  # Fade out + fade in

    def test_fade_through_black_timing_sequence(
        self, renderer, simple_effects_from, simple_effects_to
    ):
        """Test FADE_THROUGH_BLACK timing sequence (40% out, 40% in, 20% hold)."""
        start_ms = 1000
        duration_bars = 1.0  # 2000ms
        total_duration_ms = 2000

        effects = renderer.render_transition(
            mode=TransitionMode.FADE_THROUGH_BLACK,
            duration_bars=duration_bars,
            from_effects=simple_effects_from,
            to_effects=simple_effects_to,
            fixture_id="MH1",
            transition_start_ms=start_ms,
        )

        dimmer_effects = [e for e in effects if "Dimmer" in e.element_name]

        # At least one effect should start at transition start
        assert any(e.start_ms == start_ms for e in dimmer_effects)

        # Effects should span the transition duration
        all_effects_end = max(e.end_ms for e in effects)
        assert all_effects_end <= start_ms + total_duration_ms + 100  # Allow small variance

    def test_fade_through_black_handles_missing_dimmer(self, renderer):
        """Test FADE_THROUGH_BLACK when dimmer effects are missing."""
        # Effects without dimmer
        from_effects = [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=0,
                end_ms=1000,
                effect_label="pan:0→50",
            )
        ]

        to_effects = [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=1000,
                end_ms=2000,
                effect_label="pan:50→100",
            )
        ]

        effects = renderer.render_transition(
            mode=TransitionMode.FADE_THROUGH_BLACK,
            duration_bars=1.0,
            from_effects=from_effects,
            to_effects=to_effects,
            fixture_id="MH1",
            transition_start_ms=1000,
        )

        # Should handle gracefully (may return empty or create default dimmer effects)
        assert isinstance(effects, list)


class TestTransitionContext:
    """Test suite for TransitionContext dataclass."""

    def test_context_creation(self):
        """Test TransitionContext can be created with all required fields."""
        context = TransitionContext(
            mode="crossfade",
            duration_bars=0.5,
            curve="ease_in_out_sine",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=[],
            to_effects=[],
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        assert context.mode == "crossfade"
        assert context.duration_bars == 0.5
        assert context.curve == "ease_in_out_sine"
        assert context.start_ms == 1000.0
        assert context.end_ms == 2000.0
        assert context.duration_ms == 1000.0
        assert context.fixture_id == "MH1"

    def test_context_with_effects(self):
        """Test TransitionContext stores effects correctly."""
        from_effects = [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=0,
                end_ms=1000,
            )
        ]

        to_effects = [
            EffectPlacement(
                element_name="MH1-Pan",
                effect_name="Value Curve",
                start_ms=1000,
                end_ms=2000,
            )
        ]

        context = TransitionContext(
            mode="crossfade",
            duration_bars=0.5,
            curve="linear",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=from_effects,
            to_effects=to_effects,
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        assert len(context.from_effects) == 1
        assert len(context.to_effects) == 1
        assert context.from_effects[0].element_name == "MH1-Pan"
        assert context.to_effects[0].element_name == "MH1-Pan"
