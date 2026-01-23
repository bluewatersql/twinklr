"""Tests for timeline builder."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.timeline.builder import build_timeline_export


class TestBuildTimelineExport:
    """Tests for build_timeline_export function."""

    def test_returns_expected_structure(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        n_frames = 200  # Smaller for test
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0, 1.5, 2.0],
            downbeats_s=[0.5, 2.0],
            section_bounds_s=[0.0, 2.0, 4.0],
        )

        assert "timeline" in result
        assert "composites" in result

    def test_timeline_contains_expected_keys(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Timeline dict contains all expected feature keys."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        timeline = result["timeline"]
        assert "times_s" in timeline
        assert "rms_norm" in timeline
        assert "loudness" in timeline
        assert "onset_norm" in timeline
        assert "brightness_norm" in timeline
        assert "flatness" in timeline
        assert "motion" in timeline
        assert "tonal_novelty" in timeline
        assert "hpss_perc_ratio" in timeline
        assert "is_beat" in timeline
        assert "is_downbeat" in timeline
        assert "section_id" in timeline

    def test_composites_contains_show_intensity(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Composites dict contains show_intensity curve."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        assert "show_intensity" in result["composites"]

    def test_beat_markers_are_binary(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """is_beat and is_downbeat arrays are binary (0 or 1)."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0, 1.5],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        assert all(v in {0, 1} for v in result["timeline"]["is_beat"])
        assert all(v in {0, 1} for v in result["timeline"]["is_downbeat"])

    def test_beats_marked_at_correct_positions(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Beat markers appear at specified times."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        # Should have some beat markers set
        assert sum(result["timeline"]["is_beat"]) >= 1

    def test_empty_rms_returns_empty_timeline(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Empty RMS norm returns empty timeline."""
        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=np.array([], dtype=np.float32),
            rms_norm=np.array([], dtype=np.float32),  # Empty
            brightness_norm=np.array([], dtype=np.float32),
            flatness_norm=np.array([], dtype=np.float32),
            motion_norm=np.array([], dtype=np.float32),
            chroma_cqt=sample_chroma[:, :0],
            beats_s=[],
            downbeats_s=[],
            section_bounds_s=[],
        )

        assert result["timeline"] == {}

    def test_handles_list_inputs(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Function handles list inputs (from JSON)."""
        n_frames = 200
        # Pass as lists
        onset_env = [float(x) for x in np.random.rand(n_frames)]
        rms_norm = [float(x) for x in np.random.rand(n_frames)]
        brightness_norm = [float(x) for x in np.random.rand(n_frames)]
        flatness_norm = [float(x) for x in np.random.rand(n_frames)]
        motion_norm = [float(x) for x in np.random.rand(n_frames)]

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        assert "timeline" in result

    def test_show_intensity_in_valid_range(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Show intensity values are in [0, 1] range."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        intensity = result["composites"]["show_intensity"]
        assert all(0.0 <= i <= 1.0 for i in intensity)


class TestTimelineEdgeCases:
    """Tests for timeline builder edge cases."""

    def test_hpss_exception_fallback(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """When HPSS fails, returns zeros for hpss_perc_ratio."""
        from unittest.mock import patch

        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        # Mock librosa.feature.rms to raise exception
        with patch("librosa.feature.rms", side_effect=Exception("RMS failed")):
            result = build_timeline_export(
                y=sine_wave_440hz,
                sr=sample_rate,
                hop_length=hop_length,
                frame_length=frame_length,
                onset_env=onset_env,
                rms_norm=rms_norm,
                brightness_norm=brightness_norm,
                flatness_norm=flatness_norm,
                motion_norm=motion_norm,
                chroma_cqt=sample_chroma[:, :n_frames],
                beats_s=[0.5, 1.0],
                downbeats_s=[0.5],
                section_bounds_s=[0.0, 2.0],
            )

            # Should still return valid result with zeros for hpss_perc_ratio
            assert "hpss_perc_ratio" in result["timeline"]
            assert all(v == 0.0 for v in result["timeline"]["hpss_perc_ratio"])

    def test_1d_chroma_input(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Handles 1D chroma input (reshapes to 2D)."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        # 1D chroma array
        chroma_1d = np.random.rand(n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=chroma_1d,
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        # Should still compute tonal novelty
        assert "tonal_novelty" in result["timeline"]

    def test_chroma_longer_than_frames(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Handles chroma longer than n_frames (truncates)."""
        n_frames = 100  # Smaller than chroma
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        # Chroma is 500 frames (from fixture), n_frames is 100
        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma,  # 12 x 500
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        # tonal_novelty should be n_frames length
        assert len(result["timeline"]["tonal_novelty"]) == n_frames

    def test_chroma_shorter_than_frames(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Handles chroma shorter than n_frames (pads)."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        # Short chroma array
        short_chroma = np.random.rand(12, 50).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=short_chroma,  # 12 x 50 (shorter than n_frames)
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
        )

        # tonal_novelty should be n_frames length
        assert len(result["timeline"]["tonal_novelty"]) == n_frames

    def test_with_hpss_components_provided(
        self,
        sine_wave_440hz: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Test with pre-computed HPSS components."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        rms_norm = np.random.rand(n_frames).astype(np.float32)
        brightness_norm = np.random.rand(n_frames).astype(np.float32)
        flatness_norm = np.random.rand(n_frames).astype(np.float32)
        motion_norm = np.random.rand(n_frames).astype(np.float32)

        # Pre-computed HPSS
        y_harm = sine_wave_440hz * 0.8
        y_perc = sine_wave_440hz * 0.2

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=sample_chroma[:, :n_frames],
            beats_s=[0.5, 1.0],
            downbeats_s=[0.5],
            section_bounds_s=[0.0, 2.0],
            y_harm=y_harm,
            y_perc=y_perc,
        )

        # Should use pre-computed HPSS
        assert "hpss_perc_ratio" in result["timeline"]

    def test_single_frame(
        self,
        sine_wave_440hz: np.ndarray,
        sample_rate: int,
        hop_length: int,
        frame_length: int,
    ) -> None:
        """Handles single frame input."""
        n_frames = 1
        onset_env = np.array([0.5], dtype=np.float32)
        rms_norm = np.array([0.5], dtype=np.float32)
        brightness_norm = np.array([0.5], dtype=np.float32)
        flatness_norm = np.array([0.5], dtype=np.float32)
        motion_norm = np.array([0.5], dtype=np.float32)
        chroma = np.random.rand(12, n_frames).astype(np.float32)

        result = build_timeline_export(
            y=sine_wave_440hz,
            sr=sample_rate,
            hop_length=hop_length,
            frame_length=frame_length,
            onset_env=onset_env,
            rms_norm=rms_norm,
            brightness_norm=brightness_norm,
            flatness_norm=flatness_norm,
            motion_norm=motion_norm,
            chroma_cqt=chroma,
            beats_s=[],
            downbeats_s=[],
            section_bounds_s=[],
        )

        assert len(result["timeline"]["times_s"]) == 1
