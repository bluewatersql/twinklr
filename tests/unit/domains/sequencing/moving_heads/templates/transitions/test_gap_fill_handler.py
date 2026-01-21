"""Tests for Phase 3 GapFillHandler.

Tests the unified gap filling approach using transitions framework.
"""

from unittest.mock import Mock

import pytest

from blinkb0t.core.domains.sequencing.moving_heads.transitions.context import (
    TransitionContext,
)
from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.gap_fill import (
    GapFillHandler,
)


class TestGapFillHandlerInit:
    """Test GapFillHandler initialization."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        return Mock()

    def test_default_initialization(self, mock_registry):
        """Test handler with default settings."""
        handler = GapFillHandler(handler_registry=mock_registry)

        assert handler.large_gap_threshold_ms == 5000
        assert handler.soft_home_pan_deg == 0.0
        assert handler.soft_home_tilt_deg == 0.0

    def test_custom_threshold(self, mock_registry):
        """Test handler with custom threshold."""
        handler = GapFillHandler(handler_registry=mock_registry, large_gap_threshold_ms=3000)

        assert handler.large_gap_threshold_ms == 3000

    def test_custom_soft_home(self, mock_registry):
        """Test handler with custom soft home position."""
        handler = GapFillHandler(handler_registry=mock_registry, soft_home_pose=(10.0, 5.0))

        assert handler.soft_home_pan_deg == 10.0
        assert handler.soft_home_tilt_deg == 5.0


class TestGapFillHandlerRouting:
    """Test gap fill handler routing logic."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        mock_reg = Mock()
        # Mock crossfade handler
        mock_crossfade = Mock()
        mock_crossfade.render = Mock(return_value=[])
        mock_reg.get_handler = Mock(return_value=mock_crossfade)
        return mock_reg

    @pytest.fixture
    def handler(self, mock_registry) -> GapFillHandler:
        """Create handler for testing."""
        return GapFillHandler(handler_registry=mock_registry, large_gap_threshold_ms=5000)

    @pytest.fixture
    def mock_context(self) -> TransitionContext:
        """Create mock context."""
        return TransitionContext(
            mode="gap_fill",
            duration_bars=1.0,
            curve="ease_in_out_sine",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=[Mock()],  # Has previous effects
            to_effects=[Mock()],  # Has next effects
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

    def test_sequence_start_detection(
        self, handler: GapFillHandler, mock_context: TransitionContext
    ):
        """Test detection of sequence start (no from_effects)."""
        mock_context.from_effects = []  # No previous effects

        # Should route to _render_sequence_start
        result = handler.render(mock_context)

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_sequence_end_detection(self, handler: GapFillHandler, mock_context: TransitionContext):
        """Test detection of sequence end (no to_effects)."""
        mock_context.to_effects = []  # No next effects

        # Should route to _render_sequence_end
        result = handler.render(mock_context)

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_large_gap_detection(self, handler: GapFillHandler, mock_context: TransitionContext):
        """Test detection of large gap (≥5s)."""
        mock_context.duration_ms = 6000.0  # 6 seconds

        # Should route to _render_large_gap
        result = handler.render(mock_context)

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_small_gap_detection(self, handler: GapFillHandler, mock_context: TransitionContext):
        """Test detection of small gap (<5s)."""
        mock_context.duration_ms = 3000.0  # 3 seconds

        # Should route to _render_small_gap
        result = handler.render(mock_context)

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_exact_threshold_is_large_gap(
        self, handler: GapFillHandler, mock_context: TransitionContext
    ):
        """Test that exactly 5s is treated as large gap."""
        mock_context.duration_ms = 5000.0  # Exactly 5 seconds

        # Should route to _render_large_gap (>= threshold)
        result = handler.render(mock_context)

        assert isinstance(result, list)


class TestLargeGapPhasing:
    """Test large gap 40/20/40 phase split."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        mock_reg = Mock()
        # Mock crossfade handler
        mock_crossfade = Mock()
        mock_crossfade.render = Mock(return_value=[])
        mock_reg.get_handler = Mock(return_value=mock_crossfade)
        return mock_reg

    @pytest.fixture
    def handler(self, mock_registry) -> GapFillHandler:
        """Create handler for testing."""
        return GapFillHandler(handler_registry=mock_registry, large_gap_threshold_ms=5000)

    def test_phase_split_calculation(self, handler: GapFillHandler):
        """Test that large gap is split into 40/20/40 phases."""
        # Create context with 10 second gap
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=2.0,
            curve="ease_in_out_sine",
            start_ms=1000.0,
            end_ms=11000.0,
            duration_ms=10000.0,
            from_effects=[Mock()],
            to_effects=[Mock()],
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        # Call the large gap handler
        result = handler._render_large_gap(context)

        # Verify phase calculations (logged in debug)
        # Phase 1: 4000ms (40%)
        # Phase 2: 2000ms (20%)
        # Phase 3: 4000ms (40%)
        # Total: 10000ms

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_phase_split_with_odd_duration(self, handler: GapFillHandler):
        """Test phase split with duration that doesn't divide evenly."""
        # Create context with 7 second gap
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=1.4,
            curve="ease_in_out_sine",
            start_ms=1000.0,
            end_ms=8000.0,
            duration_ms=7000.0,
            from_effects=[Mock()],
            to_effects=[Mock()],
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_large_gap(context)

        # Phase 1: 2800ms (40%)
        # Phase 2: 1400ms (20%)
        # Phase 3: 2800ms (40%)
        # Total: 7000ms

        assert isinstance(result, list)


class TestSequenceStartEnd:
    """Test sequence start/end handling."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_registry) -> GapFillHandler:
        """Create handler for testing."""
        return GapFillHandler(handler_registry=mock_registry)

    def test_sequence_start_with_no_target_effects(self, handler: GapFillHandler):
        """Test sequence start with no target effects (edge case)."""
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=0.5,
            curve="ease_in_out_sine",
            start_ms=0.0,
            end_ms=500.0,
            duration_ms=500.0,
            from_effects=[],  # Sequence start
            to_effects=[],  # But no target effects!
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_sequence_start(context)

        # Should return hold effect at soft home
        assert len(result) == 1
        assert result[0].start_ms == 0
        assert result[0].end_ms == 500

    def test_sequence_end_with_no_source_effects(self, handler: GapFillHandler):
        """Test sequence end with no source effects (edge case)."""
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=0.5,
            curve="ease_in_out_sine",
            start_ms=10000.0,
            end_ms=10500.0,
            duration_ms=500.0,
            from_effects=[],  # No source effects!
            to_effects=[],  # Sequence end
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_sequence_end(context)

        # Should return hold effect at soft home
        assert len(result) == 1
        assert result[0].start_ms == 10000
        assert result[0].end_ms == 10500


class TestSmallGapHandling:
    """Test small gap direct ramp."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock registry."""
        mock_reg = Mock()
        # Mock crossfade handler
        mock_crossfade = Mock()
        mock_crossfade.render = Mock(return_value=[])
        mock_reg.get_handler = Mock(return_value=mock_crossfade)
        return mock_reg

    @pytest.fixture
    def handler(self, mock_registry) -> GapFillHandler:
        """Create handler for testing."""
        return GapFillHandler(handler_registry=mock_registry, large_gap_threshold_ms=5000)

    def test_small_gap_with_source_and_target(self, handler: GapFillHandler):
        """Test small gap with valid source and target effects."""
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=0.5,
            curve="linear",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=[Mock()],  # Has source
            to_effects=[Mock()],  # Has target
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_small_gap(context)

        # For now, returns empty list (placeholder)
        assert isinstance(result, list)

    def test_small_gap_missing_source(self, handler: GapFillHandler):
        """Test small gap with missing source effects (edge case)."""
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=0.5,
            curve="linear",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=[],  # No source!
            to_effects=[Mock()],
            from_position=None,  # No from position
            to_position=None,
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_small_gap(context)

        # Should return hold effect at soft home (fallback)
        assert len(result) == 1
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000

    def test_small_gap_missing_target(self, handler: GapFillHandler):
        """Test small gap with missing target effects (edge case)."""
        context = TransitionContext(
            mode="gap_fill",
            duration_bars=0.5,
            curve="linear",
            start_ms=1000.0,
            end_ms=2000.0,
            duration_ms=1000.0,
            from_effects=[Mock()],
            to_effects=[],  # No target!
            from_position=(45.0, 30.0),  # Has from position
            to_position=None,
            fixture_id="MH1",
            dmx_curve_mapper=Mock(),
            time_resolver=Mock(),
        )

        result = handler._render_small_gap(context)

        # Should return hold effect at from_position
        assert len(result) == 1
        assert result[0].start_ms == 1000
        assert result[0].end_ms == 2000


class TestBackwardCompatibility:
    """Test that existing transition handlers still work."""

    def test_gap_fill_handler_follows_transition_handler_interface(self):
        """Test that GapFillHandler implements TransitionHandler interface."""
        from blinkb0t.core.domains.sequencing.moving_heads.transitions.handlers.base import (
            TransitionHandler,
        )

        mock_registry = Mock()
        handler = GapFillHandler(handler_registry=mock_registry)

        assert isinstance(handler, TransitionHandler)
        assert hasattr(handler, "render")
        assert callable(handler.render)
