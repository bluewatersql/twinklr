"""Tests for unified song map builder."""

from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.audio.context.unified_map import (
    _extract_peaks,
    _filter_meaningful_timing_events,
    _find_section_for_time,
    _sample_timeline_at_time,
    build_unified_song_map,
)


class TestExtractPeaks:
    """Tests for _extract_peaks function."""

    def test_finds_local_maxima(self) -> None:
        """Function finds local maxima in time series."""
        times = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        values = [0.0, 0.2, 0.5, 0.3, 0.1, 0.4, 0.8, 0.4, 0.2, 0.1, 0.0]

        peaks = _extract_peaks(times, values, n_peaks=3, min_sep_s=1.0)

        assert len(peaks) <= 3
        # Peak at index 6 (value 0.8) should be included
        peak_times = [p["t_s"] for p in peaks]
        assert 6.0 in peak_times

    def test_respects_min_separation(self) -> None:
        """Peaks are separated by at least min_sep_s."""
        times = list(range(20))
        values = [0.0] * 20
        values[5] = 1.0
        values[6] = 0.95  # Close peak
        values[15] = 0.9

        peaks = _extract_peaks(times, values, n_peaks=5, min_sep_s=5.0)

        # Should not have both 5 and 6 due to min separation
        peak_times = [p["t_s"] for p in peaks]
        if 5 in peak_times and 6 in peak_times:
            pytest.fail("Peaks too close together")

    def test_limits_n_peaks(self) -> None:
        """Result limited to n_peaks."""
        times = list(range(100))
        values = [0.0] * 100
        for i in range(0, 100, 10):
            values[i] = 1.0

        peaks = _extract_peaks(times, values, n_peaks=3, min_sep_s=1.0)

        assert len(peaks) <= 3

    def test_empty_input(self) -> None:
        """Empty input returns empty list."""
        peaks = _extract_peaks([], [], n_peaks=5, min_sep_s=1.0)
        assert peaks == []

    def test_returns_sorted_by_time(self) -> None:
        """Result is sorted by time."""
        times = list(range(20))
        values = [0.0] * 20
        values[15] = 1.0  # Highest
        values[5] = 0.9  # Second highest

        peaks = _extract_peaks(times, values, n_peaks=5, min_sep_s=1.0)

        # Should be sorted by time, not value
        for i in range(1, len(peaks)):
            assert peaks[i]["t_s"] >= peaks[i - 1]["t_s"]


class TestFindSectionForTime:
    """Tests for _find_section_for_time function."""

    def test_finds_correct_section(self) -> None:
        """Returns section containing the time point."""
        sections = [
            {"start_s": 0.0, "end_s": 30.0, "label": "intro"},
            {"start_s": 30.0, "end_s": 60.0, "label": "verse"},
            {"start_s": 60.0, "end_s": 90.0, "label": "chorus"},
        ]

        result = _find_section_for_time(sections, 45.0)
        assert result is not None
        assert result["label"] == "verse"

    def test_returns_none_for_out_of_range(self) -> None:
        """Returns None if time not in any section."""
        sections = [
            {"start_s": 10.0, "end_s": 20.0, "label": "verse"},
        ]

        assert _find_section_for_time(sections, 5.0) is None
        assert _find_section_for_time(sections, 25.0) is None

    def test_boundary_inclusion(self) -> None:
        """Start is inclusive, end is exclusive."""
        sections = [
            {"start_s": 0.0, "end_s": 30.0, "label": "A"},
            {"start_s": 30.0, "end_s": 60.0, "label": "B"},
        ]

        # Exactly at boundary goes to next section
        result = _find_section_for_time(sections, 30.0)
        assert result["label"] == "B"


class TestSampleTimelineAtTime:
    """Tests for _sample_timeline_at_time function."""

    def test_samples_at_exact_time(self) -> None:
        """Samples values at exact time point."""
        timeline = {
            "t_sec": [0.0, 1.0, 2.0, 3.0],
            "energy": [0.1, 0.5, 0.8, 0.3],
        }

        result = _sample_timeline_at_time(timeline, 1.0)
        assert result["energy"] == pytest.approx(0.5, abs=0.01)

    def test_interpolates_between_times(self) -> None:
        """Linearly interpolates between time points."""
        timeline = {
            "t_sec": [0.0, 2.0],
            "energy": [0.0, 1.0],
        }

        result = _sample_timeline_at_time(timeline, 1.0)
        assert result["energy"] == pytest.approx(0.5, abs=0.01)

    def test_handles_empty_timeline(self) -> None:
        """Returns empty dict for empty timeline."""
        result = _sample_timeline_at_time({"t_sec": []}, 1.0)
        assert result == {}


class TestFilterMeaningfulTimingEvents:
    """Tests for _filter_meaningful_timing_events function."""

    def test_filters_by_track_name(self) -> None:
        """Only keeps events from meaningful track names."""
        events = {
            "beat_track": [{"time_ms": 1000}],
            "phrase_track": [{"time_ms": 2000}],
            "random_track": [{"time_ms": 3000}],  # Should be filtered
        }

        result = _filter_meaningful_timing_events(events)

        # Should have beat and phrase, not random
        track_names = [e["track_name"] for e in result]
        assert any("beat" in tn for tn in track_names)
        assert all("random" not in tn.lower() for tn in track_names)

    def test_limits_events_per_track(self) -> None:
        """Limits events per track to max_events_per_track."""
        events = {
            "beat_track": [{"time_ms": i * 100} for i in range(50)],
        }

        result = _filter_meaningful_timing_events(events, max_events_per_track=10)

        assert len(result) <= 10


class TestBuildUnifiedSongMap:
    """Tests for build_unified_song_map function."""

    def test_returns_expected_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Function returns expected dictionary structure."""
        result = build_unified_song_map(sample_song_features)

        assert "metadata" in result
        assert "sections" in result
        assert "events" in result
        assert "arc" in result

    def test_metadata_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Metadata contains expected keys."""
        result = build_unified_song_map(sample_song_features)

        metadata = result["metadata"]
        assert "duration_s" in metadata
        assert "tempo_bpm" in metadata
        assert "total_bars" in metadata
        assert "total_beats" in metadata
        assert "total_sections" in metadata
        assert "event_resolution" in metadata
        assert "total_events" in metadata

    def test_section_summaries_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Section summaries have expected structure."""
        result = build_unified_song_map(sample_song_features)

        if result["sections"]:
            section = result["sections"][0]
            assert "id" in section
            assert "label" in section
            assert "time_range" in section
            assert "duration_s" in section
            assert "bars" in section

    def test_arc_structure(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Arc contains expected keys."""
        result = build_unified_song_map(sample_song_features)

        arc = result["arc"]
        assert "energy_peaks" in arc
        assert "tonal_shifts" in arc
        assert "section_transitions" in arc

    def test_respects_resolution_parameter(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Resolution parameter affects event generation."""
        result_beat = build_unified_song_map(
            sample_song_features,
            resolution="beat",
        )
        result_bar = build_unified_song_map(
            sample_song_features,
            resolution="bar",
        )

        # Beat resolution should have more events
        assert result_beat["metadata"]["total_events"] >= result_bar["metadata"]["total_events"]

    def test_max_events_parameter(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Max events parameter limits event count."""
        result = build_unified_song_map(
            sample_song_features,
            max_events=10,
        )

        assert len(result["events"]) <= 10

    def test_includes_sequence_events_when_provided(
        self,
        sample_song_features: dict[str, Any],
    ) -> None:
        """Includes sequence timing events when fingerprint provided."""
        seq_fingerprint = {
            "timing_track_events": {
                "beat_markers": [
                    {"time_ms": 1000, "label": "beat1"},
                    {"time_ms": 2000, "label": "beat2"},
                ]
            }
        }

        result = build_unified_song_map(
            sample_song_features,
            seq_fingerprint=seq_fingerprint,
        )

        assert result["sequence_timing"] is not None
        assert len(result["sequence_timing"]) > 0

    def test_handles_empty_features(self) -> None:
        """Handles minimal/empty features gracefully."""
        minimal_features: dict[str, Any] = {
            "duration_s": 60.0,
            "tempo_bpm": 120.0,
            "beats_s": [],
            "bars_s": [],
            "structure": {"sections": []},
        }

        result = build_unified_song_map(minimal_features)

        assert "metadata" in result
        assert result["metadata"]["total_sections"] == 0
