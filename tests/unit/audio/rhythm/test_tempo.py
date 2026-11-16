"""Tests for tempo change detection over the resolved beat grid."""

from __future__ import annotations

import numpy as np
import pytest

from twinklr.core.audio.rhythm.tempo import detect_tempo_changes


def _beats(bpm: float, duration_s: float, start_s: float = 0.25) -> list[float]:
    return [float(t) for t in np.arange(start_s, duration_s, 60.0 / bpm)]


def test_package_exports_live_tempo_change_detector() -> None:
    from twinklr.core.audio.rhythm import detect_tempo_changes as exported_detector

    assert exported_detector is detect_tempo_changes


class TestDetectTempoChanges:
    """The tempo curve is read from the same beats that the grid uses."""

    def test_returns_expected_structure(self) -> None:
        result = detect_tempo_changes(_beats(120.0, 30.0), duration_s=30.0)

        assert set(result) == {
            "tempo_curve",
            "tempo_changes",
            "average_tempo_bpm",
            "tempo_std",
            "is_stable",
        }
        point = result["tempo_curve"][0]
        assert set(point) == {"time_s", "tempo_bpm"}

    def test_halved_grid_reports_the_halved_tempo(self) -> None:
        """A grid resolved to 78.3 BPM must not be reported at the tracker's 156.6 BPM."""
        result = detect_tempo_changes(_beats(78.3, 120.0), duration_s=120.0)

        assert result["average_tempo_bpm"] == pytest.approx(78.3, rel=0.01)
        assert all(
            point["tempo_bpm"] == pytest.approx(78.3, rel=0.01) for point in result["tempo_curve"]
        )
        assert result["is_stable"] is True
        assert result["tempo_changes"] == []

    def test_tempo_step_is_reported_as_a_change(self) -> None:
        beats = _beats(100.0, 30.0) + [30.0 + t for t in _beats(140.0, 30.0, start_s=0.0)]

        result = detect_tempo_changes(beats, duration_s=60.0)

        tempos = [point["tempo_bpm"] for point in result["tempo_curve"]]
        assert tempos[0] == pytest.approx(100.0, rel=0.02)
        assert tempos[-1] == pytest.approx(140.0, rel=0.02)
        assert result["tempo_changes"]
        change = result["tempo_changes"][0]
        assert set(change) == {"time_s", "from_bpm", "to_bpm", "change_pct"}
        assert result["is_stable"] is False

    def test_window_hop_is_half_the_window(self) -> None:
        result = detect_tempo_changes(_beats(120.0, 30.0), duration_s=30.0, window_size_s=10.0)

        assert [point["time_s"] for point in result["tempo_curve"]] == [0.0, 5.0, 10.0, 15.0]

    def test_smaller_window_gives_more_points(self) -> None:
        beats = _beats(120.0, 30.0)

        large = detect_tempo_changes(beats, duration_s=30.0, window_size_s=15.0)
        small = detect_tempo_changes(beats, duration_s=30.0, window_size_s=5.0)

        assert len(small["tempo_curve"]) > len(large["tempo_curve"])

    def test_average_is_the_mean_of_the_curve(self) -> None:
        beats = _beats(100.0, 30.0) + [30.0 + t for t in _beats(140.0, 30.0, start_s=0.0)]

        result = detect_tempo_changes(beats, duration_s=60.0)

        tempos = [point["tempo_bpm"] for point in result["tempo_curve"]]
        assert result["average_tempo_bpm"] == pytest.approx(float(np.mean(tempos)))
        assert result["tempo_std"] == pytest.approx(float(np.std(tempos)), abs=1e-6)

    def test_audio_shorter_than_the_window_gives_one_point(self) -> None:
        result = detect_tempo_changes(_beats(90.0, 5.0), duration_s=5.0, window_size_s=10.0)

        assert len(result["tempo_curve"]) == 1
        assert result["average_tempo_bpm"] == pytest.approx(90.0, rel=0.01)
        assert result["is_stable"] is True

    @pytest.mark.parametrize("beats", [[], [1.0]], ids=["no_beats", "one_beat"])
    def test_too_few_beats_give_an_empty_curve(self, beats: list[float]) -> None:
        result = detect_tempo_changes(beats, duration_s=30.0)

        assert result == {
            "tempo_curve": [],
            "tempo_changes": [],
            "average_tempo_bpm": 0.0,
            "tempo_std": 0.0,
            "is_stable": True,
        }
