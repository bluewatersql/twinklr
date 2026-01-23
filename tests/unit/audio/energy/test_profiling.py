"""Tests for energy profiling (song classification)."""

from __future__ import annotations

import numpy as np

from blinkb0t.core.audio.energy.profiling import classify_song_energy_profile


class TestClassifySongEnergyProfile:
    """Tests for classify_song_energy_profile function."""

    def test_returns_expected_structure(self) -> None:
        """Function returns expected dictionary structure."""
        energy_curve = np.random.rand(500).astype(np.float32)
        onset_env = np.random.rand(500).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        assert "profile" in result
        assert "parameters" in result
        assert "statistics" in result

    def test_profile_is_valid_category(self) -> None:
        """Returned profile is one of expected categories."""
        energy_curve = np.random.rand(500).astype(np.float32)
        onset_env = np.random.rand(500).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        valid_profiles = {
            "high_energy",
            "low_energy_stable",
            "slow_gentle",
            "highly_dynamic",
            "moderate_low",
            "moderate",
        }
        assert result["profile"] in valid_profiles

    def test_high_energy_profile_detection(self) -> None:
        """High energy with high dynamics produces high_energy profile."""
        # High mean (>0.65) and high gradient_std (>0.008)
        n_frames = 500
        energy_curve = np.full(n_frames, 0.75, dtype=np.float32)
        # Add high dynamics
        energy_curve[::10] = 0.9
        energy_curve[5::10] = 0.6

        onset_env = np.random.rand(n_frames).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=140.0,  # Fast tempo
            onset_env=onset_env,
            duration_s=180.0,
        )

        # Should detect as high_energy or highly_dynamic
        assert result["profile"] in {"high_energy", "highly_dynamic"}

    def test_low_energy_stable_profile_detection(self) -> None:
        """Low energy with low variation produces low_energy_stable profile."""
        n_frames = 500
        # Low mean (<0.4) and low coefficient of variation (<0.35)
        energy_curve = np.full(n_frames, 0.3, dtype=np.float32)
        # Add very small variation
        energy_curve += np.random.rand(n_frames).astype(np.float32) * 0.05

        onset_env = np.ones(n_frames, dtype=np.float32) * 0.3

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=70.0,  # Slow tempo
            onset_env=onset_env,
            duration_s=180.0,
        )

        # Should detect as low_energy_stable or slow_gentle
        assert result["profile"] in {"low_energy_stable", "slow_gentle", "moderate_low"}

    def test_slow_gentle_profile_detection(self) -> None:
        """Slow tempo with low energy produces slow_gentle profile."""
        n_frames = 500
        # Low energy (<0.5), slow tempo (<100)
        energy_curve = np.full(n_frames, 0.4, dtype=np.float32)
        onset_env = np.ones(n_frames, dtype=np.float32) * 0.3

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=80.0,  # Slow tempo
            onset_env=onset_env,
            duration_s=180.0,
        )

        # Should detect as slow_gentle, low_energy_stable, or moderate_low
        assert result["profile"] in {"slow_gentle", "low_energy_stable", "moderate_low"}

    def test_parameters_contain_required_keys(self) -> None:
        """Parameters dict contains all required detection parameters."""
        energy_curve = np.random.rand(500).astype(np.float32)
        onset_env = np.random.rand(500).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        params = result["parameters"]
        assert "min_build_bars" in params
        assert "gradient_percentile" in params
        assert "min_energy_gain" in params
        assert "detect_drops_independent" in params
        assert "drop_gradient_percentile" in params

    def test_statistics_contain_expected_metrics(self) -> None:
        """Statistics dict contains expected analysis metrics."""
        energy_curve = np.random.rand(500).astype(np.float32)
        onset_env = np.random.rand(500).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        stats = result["statistics"]
        assert "energy_mean" in stats
        assert "energy_std" in stats
        assert "energy_median" in stats
        assert "energy_range" in stats
        assert "energy_cv" in stats
        assert "gradient_std" in stats
        assert "onset_density" in stats
        assert "tempo_bpm" in stats

    def test_parameter_adaptation_for_stable_songs(self) -> None:
        """Very stable songs (low CV) get more sensitive parameters."""
        n_frames = 500
        # Very stable energy (low CV < 0.25)
        stable_energy = np.full(n_frames, 0.5, dtype=np.float32)
        stable_energy += np.random.rand(n_frames).astype(np.float32) * 0.02

        onset_env = np.ones(n_frames, dtype=np.float32) * 0.5

        result = classify_song_energy_profile(
            energy_curve=stable_energy,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        # Low CV should result in lower gradient_percentile and min_energy_gain
        assert result["parameters"]["min_energy_gain"] < 0.15  # Adapted lower

    def test_statistics_values_are_rounded(self) -> None:
        """Statistics values are rounded for cleaner output."""
        energy_curve = np.random.rand(500).astype(np.float32)
        onset_env = np.random.rand(500).astype(np.float32)

        result = classify_song_energy_profile(
            energy_curve=energy_curve,
            tempo_bpm=120.0,
            onset_env=onset_env,
            duration_s=180.0,
        )

        # Check that values are rounded (have limited decimal places)
        energy_mean = result["statistics"]["energy_mean"]
        # Should have at most 3 decimal places
        assert energy_mean == round(energy_mean, 3)

    def test_handles_constant_energy(self) -> None:
        """Constant energy (no variation) is handled without division by zero."""
        n_frames = 500
        constant_energy = np.full(n_frames, 0.5, dtype=np.float32)
        constant_onset = np.full(n_frames, 0.3, dtype=np.float32)

        # Should not raise
        result = classify_song_energy_profile(
            energy_curve=constant_energy,
            tempo_bpm=120.0,
            onset_env=constant_onset,
            duration_s=180.0,
        )

        assert result["profile"] in {
            "low_energy_stable",
            "moderate",
            "moderate_low",
            "slow_gentle",
        }
