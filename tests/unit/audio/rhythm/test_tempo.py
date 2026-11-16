"""Tests for the local-tempo curve of the resolved beat grid."""

from __future__ import annotations

import numpy as np
import pytest

from twinklr.core.audio.rhythm.tempo import local_tempo_curve


def _beats(bpm: float, end_s: float, start_s: float = 0.25) -> list[float]:
    return [float(t) for t in np.arange(start_s, end_s, 60.0 / bpm)]


def test_package_exports_the_local_tempo_curve() -> None:
    from twinklr.core.audio.rhythm import local_tempo_curve as exported

    assert exported is local_tempo_curve


class TestLocalTempoCurve:
    """Local tempo read from the same beats that the grid uses."""

    def test_returns_only_the_curve_and_its_summary(self) -> None:
        result = local_tempo_curve(_beats(120.0, 30.0), duration_s=30.0)

        assert set(result) == {"tempo_curve", "average_tempo_bpm", "tempo_std"}
        assert set(result["tempo_curve"][0]) == {"time_s", "tempo_bpm"}

    def test_halved_grid_reports_the_halved_tempo(self) -> None:
        """A grid resolved to 78.3 BPM must not be reported at the tracker's 156.6 BPM."""
        result = local_tempo_curve(_beats(78.3, 120.0), duration_s=120.0)

        assert result["average_tempo_bpm"] == pytest.approx(78.3, rel=0.01)
        assert all(
            point["tempo_bpm"] == pytest.approx(78.3, rel=0.01) for point in result["tempo_curve"]
        )

    def test_tempo_step_shows_in_the_curve(self) -> None:
        beats = _beats(100.0, 30.0) + _beats(140.0, 60.0, start_s=30.0)

        result = local_tempo_curve(beats, duration_s=60.0)

        tempos = [point["tempo_bpm"] for point in result["tempo_curve"]]
        assert tempos[0] == pytest.approx(100.0, rel=0.02)
        assert tempos[-1] == pytest.approx(140.0, rel=0.02)

    def test_windows_start_every_half_window_through_the_last_full_window(self) -> None:
        result = local_tempo_curve(_beats(120.0, 30.0), duration_s=30.0, window_size_s=10.0)

        assert [point["time_s"] for point in result["tempo_curve"]] == [0.0, 5.0, 10.0, 15.0, 20.0]

    def test_the_last_full_window_ends_at_the_song_end(self) -> None:
        # A change at 33 s in a 40 s song must be visible.
        beats = _beats(120.0, 33.0) + _beats(200.0, 40.0, start_s=33.0)

        result = local_tempo_curve(beats, duration_s=40.0, window_size_s=10.0)

        last = result["tempo_curve"][-1]
        assert last["time_s"] == 30.0
        assert last["tempo_bpm"] == pytest.approx(200.0, rel=0.02)

    def test_uneven_duration_adds_a_window_ending_at_the_song_end(self) -> None:
        result = local_tempo_curve(_beats(120.0, 33.0), duration_s=33.0, window_size_s=10.0)

        times = [point["time_s"] for point in result["tempo_curve"]]
        assert times == [0.0, 5.0, 10.0, 15.0, 20.0, 23.0]

    def test_a_window_needs_four_beats(self) -> None:
        # Two beats 9 s apart would otherwise read as 6.7 BPM.
        beats = [0.5, 9.5, *_beats(120.0, 40.0, start_s=10.0)]

        result = local_tempo_curve(beats, duration_s=40.0, window_size_s=10.0)

        assert result["tempo_curve"][0]["time_s"] == 5.0
        assert all(point["tempo_bpm"] > 100.0 for point in result["tempo_curve"])

    def test_smaller_window_gives_more_points(self) -> None:
        beats = _beats(120.0, 30.0)

        large = local_tempo_curve(beats, duration_s=30.0, window_size_s=15.0)
        small = local_tempo_curve(beats, duration_s=30.0, window_size_s=5.0)

        assert len(small["tempo_curve"]) > len(large["tempo_curve"])

    def test_average_and_spread_summarise_the_curve(self) -> None:
        beats = _beats(100.0, 30.0) + _beats(140.0, 60.0, start_s=30.0)

        result = local_tempo_curve(beats, duration_s=60.0)

        tempos = [point["tempo_bpm"] for point in result["tempo_curve"]]
        assert result["average_tempo_bpm"] == pytest.approx(float(np.mean(tempos)))
        assert result["tempo_std"] == pytest.approx(float(np.std(tempos)), abs=1e-6)

    def test_audio_shorter_than_the_window_gives_one_point(self) -> None:
        result = local_tempo_curve(_beats(90.0, 5.0), duration_s=5.0, window_size_s=10.0)

        assert len(result["tempo_curve"]) == 1
        assert result["average_tempo_bpm"] == pytest.approx(90.0, rel=0.01)

    @pytest.mark.parametrize(
        "beats", [[], [1.0], [1.0, 1.5, 2.0]], ids=["no_beats", "one_beat", "three_beats"]
    )
    def test_too_few_beats_give_an_empty_curve(self, beats: list[float]) -> None:
        result = local_tempo_curve(beats, duration_s=30.0)

        assert result == {"tempo_curve": [], "average_tempo_bpm": 0.0, "tempo_std": 0.0}

    def test_non_finite_beats_are_ignored(self) -> None:
        beats = [*_beats(120.0, 5.0), float("nan")]

        result = local_tempo_curve(beats, duration_s=5.0)

        assert result["average_tempo_bpm"] == pytest.approx(120.0, rel=0.01)
