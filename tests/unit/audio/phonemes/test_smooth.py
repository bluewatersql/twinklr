"""Unit tests for viseme smoothing (Phase 6).

Tests cover:
- coalesce_adjacent() - merge identical consecutive visemes
- smooth_visemes() - full smoothing pipeline (min-hold, burst merge, boundary soften)
"""

from twinklr.core.audio.models.phonemes import VisemeEvent
from twinklr.core.audio.phonemes.smooth import coalesce_adjacent, smooth_visemes


class TestCoalesceAdjacent:
    """Test coalesce_adjacent viseme merging."""

    def test_merges_identical_consecutive(self):
        """Consecutive identical visemes should merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="A", start_ms=100, end_ms=200),
            VisemeEvent(viseme="A", start_ms=200, end_ms=300),
        ]

        result = coalesce_adjacent(events)

        assert len(result) == 1
        assert result[0].viseme == "A"
        assert result[0].start_ms == 0
        assert result[0].end_ms == 300

    def test_preserves_different_visemes(self):
        """Different visemes should not merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="E", start_ms=100, end_ms=200),
            VisemeEvent(viseme="O", start_ms=200, end_ms=300),
        ]

        result = coalesce_adjacent(events)

        assert len(result) == 3

    def test_partial_merge(self):
        """Only consecutive identical visemes should merge."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=100),
            VisemeEvent(viseme="A", start_ms=100, end_ms=200),
            VisemeEvent(viseme="E", start_ms=200, end_ms=300),
            VisemeEvent(viseme="E", start_ms=300, end_ms=400),
        ]

        result = coalesce_adjacent(events)

        assert len(result) == 2
        assert result[0].viseme == "A"
        assert result[0].end_ms == 200
        assert result[1].viseme == "E"
        assert result[1].end_ms == 400

    def test_empty_input(self):
        """Empty list should return empty."""
        assert coalesce_adjacent([]) == []

    def test_single_event(self):
        """Single event should pass through unchanged."""
        events = [VisemeEvent(viseme="A", start_ms=0, end_ms=100)]
        result = coalesce_adjacent(events)
        assert len(result) == 1
        assert result[0].viseme == "A"


class TestSmoothVisemes:
    """Test smooth_visemes full pipeline."""

    def test_min_hold_merges_short_into_neighbor(self):
        """Short events should merge into their neighbor."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=200),
            VisemeEvent(viseme="E", start_ms=200, end_ms=220),  # 20ms < 50ms min_hold
            VisemeEvent(viseme="O", start_ms=220, end_ms=400),
        ]

        result, _burst_count = smooth_visemes(
            events,
            min_hold_ms=50,
            min_burst_ms=40,
            boundary_soften_ms=0,
            duration_ms=400,
        )

        # E (20ms) should be merged into a neighbor
        assert len(result) < 3

    def test_burst_merge_merges_short_into_longer(self):
        """Events shorter than min_burst_ms should merge into longer neighbor."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=200),
            VisemeEvent(viseme="E", start_ms=200, end_ms=225),  # 25ms < 40ms min_burst
            VisemeEvent(viseme="O", start_ms=225, end_ms=400),
        ]

        result, burst_count = smooth_visemes(
            events,
            min_hold_ms=10,  # Don't trigger min-hold
            min_burst_ms=40,
            boundary_soften_ms=0,
            duration_ms=400,
        )

        assert burst_count > 0
        assert len(result) < 3

    def test_returns_burst_merge_count(self):
        """Should return count of burst merges performed."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=200),
            VisemeEvent(viseme="E", start_ms=200, end_ms=210),  # 10ms burst
            VisemeEvent(viseme="O", start_ms=210, end_ms=400),
        ]

        _, burst_count = smooth_visemes(
            events,
            min_hold_ms=5,
            min_burst_ms=40,
            boundary_soften_ms=0,
            duration_ms=400,
        )

        assert burst_count >= 1

    def test_boundary_soften_clamps(self):
        """Boundary softening should not exceed [0, duration_ms]."""
        events = [
            VisemeEvent(viseme="A", start_ms=0, end_ms=200),
            VisemeEvent(viseme="E", start_ms=200, end_ms=400),
        ]

        result, _ = smooth_visemes(
            events,
            min_hold_ms=10,
            min_burst_ms=10,
            boundary_soften_ms=15,
            duration_ms=400,
        )

        for ev in result:
            assert ev.start_ms >= 0
            assert ev.end_ms <= 400

    def test_empty_input(self):
        """Empty list should return empty with zero count."""
        result, count = smooth_visemes(
            [],
            min_hold_ms=50,
            min_burst_ms=40,
            boundary_soften_ms=15,
            duration_ms=1000,
        )

        assert result == []
        assert count == 0

    def test_single_event_passes_through(self):
        """Single event should pass through without modification."""
        events = [VisemeEvent(viseme="A", start_ms=0, end_ms=200)]

        result, count = smooth_visemes(
            events,
            min_hold_ms=50,
            min_burst_ms=40,
            boundary_soften_ms=0,
            duration_ms=200,
        )

        assert len(result) == 1
        assert result[0].viseme == "A"
        assert count == 0

    def test_full_pipeline_reduces_event_count(self):
        """Full pipeline with many short events should reduce count."""
        # Create a bunch of short alternating events
        events = []
        for i in range(20):
            events.append(
                VisemeEvent(
                    viseme="A" if i % 2 == 0 else "E",
                    start_ms=i * 15,
                    end_ms=(i + 1) * 15,
                )
            )

        result, _burst_count = smooth_visemes(
            events,
            min_hold_ms=50,
            min_burst_ms=40,
            boundary_soften_ms=10,
            duration_ms=300,
        )

        # Should have fewer events after smoothing
        assert len(result) < len(events)
