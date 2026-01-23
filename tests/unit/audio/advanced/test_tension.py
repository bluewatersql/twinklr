"""Tests for tension curve computation."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.advanced.tension import compute_tension_curve


class TestComputeTensionCurve:
    """Tests for compute_tension_curve function."""

    def test_returns_expected_structure(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert "tension_curve" in result
        assert "times_s" in result
        assert "components" in result
        assert "tension_peaks" in result
        assert "tension_releases" in result
        assert "statistics" in result

    def test_components_structure(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Components dict contains expected sub-curves."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        components = result["components"]
        assert "dissonance" in components
        assert "dynamic_intensity" in components
        assert "spectral_density" in components

    def test_tension_values_in_range(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tension curve values are in reasonable range."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        tension = result["tension_curve"]
        assert all(0.0 <= t <= 1.0 for t in tension)

    def test_statistics_structure(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Statistics dict contains expected keys."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        stats = result["statistics"]
        assert "avg_tension" in stats
        assert "tension_variance" in stats
        assert "peak_count" in stats
        assert "release_count" in stats
        assert "max_tension" in stats
        assert "min_tension" in stats

    def test_peak_structure(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tension peaks have expected structure."""
        n_frames = sample_chroma.shape[1]
        # Create energy with clear peaks
        energy_curve = np.zeros(n_frames, dtype=np.float32)
        energy_curve[100] = 1.0
        energy_curve[200] = 1.0
        energy_curve[300] = 1.0
        spectral_flatness = np.random.rand(n_frames).astype(np.float32) * 0.2
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if result["tension_peaks"]:
            peak = result["tension_peaks"][0]
            assert "time_s" in peak
            assert "tension" in peak

    def test_release_structure(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Tension releases have expected structure."""
        n_frames = sample_chroma.shape[1]
        # Create energy with clear drops
        energy_curve = np.ones(n_frames, dtype=np.float32)
        energy_curve[150:160] = 0.1  # Sharp drop
        spectral_flatness = np.random.rand(n_frames).astype(np.float32) * 0.2
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if result["tension_releases"]:
            release = result["tension_releases"][0]
            assert "time_s" in release
            assert "tension_drop" in release

    def test_handles_minor_key(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function handles minor key correctly."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "A", "mode": "minor"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert "tension_curve" in result

    def test_handles_list_inputs(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function handles list inputs (from JSON deserialization)."""
        n_frames = sample_chroma.shape[1]
        # Pass as lists
        energy_curve = [float(x) for x in np.random.rand(n_frames)]
        spectral_flatness = [float(x) for x in np.random.rand(n_frames)]
        onset_env = [float(x) for x in np.random.rand(n_frames)]
        times_s = [float(x) for x in np.arange(n_frames) * 0.023]
        key_info = {"key": "C", "mode": "major"}

        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert "tension_curve" in result

    def test_unknown_key_handled(
        self,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Unknown key name falls back to C."""
        n_frames = sample_chroma.shape[1]
        energy_curve = np.random.rand(n_frames).astype(np.float32)
        spectral_flatness = np.random.rand(n_frames).astype(np.float32)
        onset_env = np.random.rand(n_frames).astype(np.float32)
        times_s = (np.arange(n_frames) * 0.023).astype(np.float32)
        key_info = {"key": "X", "mode": "major"}  # Invalid key

        # Should not raise
        result = compute_tension_curve(
            chroma_cqt=sample_chroma,
            energy_curve=energy_curve,
            spectral_flatness=spectral_flatness,
            onset_env=onset_env,
            times_s=times_s,
            key_info=key_info,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert "tension_curve" in result
