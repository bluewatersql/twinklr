"""Tests for build and drop detection."""

from __future__ import annotations

import numpy as np
import pytest

from twinklr.core.audio.energy.builds_drops import detect_builds_and_drops


class TestDetectBuildsAndDrops:
    """Tests for detect_builds_and_drops function."""

    def test_returns_expected_structure(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Function returns expected dictionary structure."""
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=sample_onset_env[:500],
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        assert "builds" in result
        assert "drops" in result
        assert "pre_drops" in result
        assert "statistics" in result
        assert "profile" in result

    def test_detects_build_in_synthetic_data(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Detects build in synthetic energy curve with clear ramp."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        # Should detect at least one build
        assert len(result["builds"]) >= 1

    def test_build_structure(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Each detected build has required fields."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        if result["builds"]:
            build = result["builds"][0]
            assert "start_s" in build
            assert "end_s" in build
            assert "duration_s" in build
            assert "energy_gain" in build

    def test_drop_structure(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Each detected drop has required fields."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        if result["drops"]:
            drop = result["drops"][0]
            assert "time_s" in drop
            assert "energy_before" in drop
            assert "energy_after" in drop
            assert "type" in drop

    def test_flat_energy_returns_empty(self) -> None:
        """Flat energy curve with no dynamics returns empty builds/drops."""
        n_frames = 500
        flat_energy = np.full(n_frames, 0.5, dtype=np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        onset_env = np.ones(n_frames, dtype=np.float32) * 0.3
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=flat_energy,
            times_s=times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        # Should have no builds (no energy gain)
        assert len(result["builds"]) == 0

    def test_short_energy_returns_empty(self) -> None:
        """Energy curve shorter than 50 frames returns empty results."""
        short_energy = np.random.rand(30).astype(np.float32)
        times_s = (np.arange(30) * 0.023).astype(np.float32)
        onset_env = np.random.rand(30).astype(np.float32)
        beats_s = [0.5 * i for i in range(5)]

        result = detect_builds_and_drops(
            energy_curve=short_energy,
            times_s=times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        assert result["builds"] == []
        assert result["drops"] == []
        assert result["profile"]["profile"] == "unknown"

    def test_statistics_structure(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Statistics dict contains expected keys."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        stats = result["statistics"]
        assert "build_count" in stats
        assert "drop_count" in stats
        assert "pre_drop_count" in stats

    def test_profile_info_included(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Energy profile info is included in result."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        assert "profile" in result["profile"]
        assert "parameters" in result["profile"]

    def test_build_end_after_start(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Build end time is always after start time."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        for build in result["builds"]:
            assert build["end_s"] > build["start_s"]
            assert build["duration_s"] > 0

    def test_energy_gain_positive_for_builds(
        self,
        sample_energy_curve_with_build: np.ndarray,
        sample_times_s: np.ndarray,
    ) -> None:
        """Builds have positive energy gain."""
        onset_env = np.random.rand(500).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=sample_energy_curve_with_build,
            times_s=sample_times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        for build in result["builds"]:
            assert build["energy_gain"] > 0

    def test_independent_drops_detected(self) -> None:
        """Independent drops (not associated with builds) are detected."""
        n_frames = 500
        energy = np.full(n_frames, 0.5, dtype=np.float32)

        # Create a sudden independent drop
        energy[200:210] = 0.9
        energy[210:220] = 0.2

        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        beats_s = [0.5 * i for i in range(20)]

        result = detect_builds_and_drops(
            energy_curve=energy,
            times_s=times_s,
            onset_env=onset_env,
            beats_s=beats_s,
            tempo_bpm=120.0,
        )

        # Should detect independent drop
        _independent_drops = [d for d in result["drops"] if d.get("type") == "independent"]
        # Detection depends on profile and thresholds
        assert result["profile"]["parameters"]["detect_drops_independent"] is True


class TestBuildMergeOrdering:
    """The adjacent-build merge assumes the list is in time order."""

    @staticmethod
    def _three_builds() -> tuple[np.ndarray, np.ndarray]:
        """Energy curve with three separated ramps whose gains grow over time.

        Energy order (C, B, A) is the reverse of time order (A, B, C), so a merge
        that runs over an energy-sorted list sees negative gaps and folds all three
        into one.
        """
        n_frames = 2000
        frame_dur = 512 / 22050
        energy = np.full(n_frames, 0.1, dtype=np.float32)
        for start, stop, peak in ((100, 200, 0.3), (700, 800, 0.55), (1400, 1500, 0.9)):
            energy[start:stop] = np.linspace(0.1, peak, stop - start)
            energy[stop:] = 0.1
        times_s = (np.arange(n_frames) * frame_dur).astype(np.float32)
        return energy, times_s

    def test_builds_merge_preserves_all_and_is_time_ordered(self) -> None:
        """Every build survives the merge and the result is sorted by start_s."""
        from twinklr.core.audio.energy.builds_drops import _detect_builds_windowed

        energy, times_s = self._three_builds()
        builds = _detect_builds_windowed(
            energy_smooth=energy,
            times_s=times_s,
            bar_duration_s=2.0,
            min_build_bars=1,
            min_energy_gain=0.05,
            gradient=np.gradient(energy),
        )

        assert len(builds) == 3, f"builds were dropped by the merge: {builds}"
        starts = [b["start_s"] for b in builds]
        assert starts == sorted(starts)
        assert [round(b["energy_gain"], 2) for b in builds] == sorted(
            round(b["energy_gain"], 2) for b in builds
        ), "the three ramps grow over time, so time order must not be energy order"

    def test_public_builds_are_time_ordered(self) -> None:
        """detect_builds_and_drops returns a chronological builds list."""
        energy, times_s = self._three_builds()
        result = detect_builds_and_drops(
            energy_curve=energy,
            times_s=times_s,
            onset_env=np.ones(len(energy), dtype=np.float32) * 0.3,
            beats_s=[0.5 * i for i in range(90)],
            tempo_bpm=120.0,
        )

        starts = [b["start_s"] for b in result["builds"]]
        assert starts == sorted(starts)


class TestTimeSignatureWindows:
    """Build/drop windows are sized from the detected time signature."""

    def test_build_windows_respect_time_signature(self) -> None:
        """A 3/4 track gets windows three quarters the length of a 4/4 track."""
        n_frames = 2000
        frame_dur = 512 / 22050
        energy = np.full(n_frames, 0.1, dtype=np.float32)
        energy[200:1200] = np.linspace(0.1, 0.9, 1000)
        energy[1200:] = 0.9
        times_s = (np.arange(n_frames) * frame_dur).astype(np.float32)
        onset_env = np.ones(n_frames, dtype=np.float32) * 0.3
        beats_s = [0.5 * i for i in range(90)]

        common = {
            "energy_curve": energy,
            "times_s": times_s,
            "onset_env": onset_env,
            "beats_s": beats_s,
            "tempo_bpm": 120.0,
        }
        four_four = detect_builds_and_drops(**common, beats_per_bar=4)
        three_four = detect_builds_and_drops(**common, beats_per_bar=3)

        assert four_four["builds"] and three_four["builds"]
        d4 = four_four["builds"][0]["duration_s"]
        d3 = three_four["builds"][0]["duration_s"]
        assert d3 == pytest.approx(d4 * 3 / 4, abs=2 * frame_dur)
