"""Tests for tension curve computation.

CRITICAL REGRESSION TESTS:
These tests specifically address the TypeError bug where energy_curve,
spectral_flatness, and onset_env were being passed as Python lists instead
of numpy arrays, causing "can't multiply sequence by non-int of type 'float'".

The bug was in extract_spectral_features() and compute_beats() calling
as_float_list() before passing to compute_tension_curve(), which expects
numpy arrays for arithmetic operations.
"""

from __future__ import annotations

import numpy as np

from blinkb0t.core.domains.audio.advanced.tension import compute_tension_curve


class TestComputeTensionCurveRegression:
    """Regression tests for compute_tension_curve() TypeError bugs."""

    def test_compute_tension_with_numpy_arrays(
        self,
        mock_chroma_cqt: np.ndarray,
        mock_energy_curve: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_onset_env: np.ndarray,
        mock_times_s: np.ndarray,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that compute_tension_curve works with numpy arrays (not lists).

        REGRESSION TEST for TypeError: can't multiply sequence by non-int of type 'float'

        This test verifies that when energy_curve, spectral_flatness, and onset_env
        are passed as numpy arrays (as they should be), the function performs
        arithmetic operations correctly.

        The bug occurred when these were converted to lists via as_float_list()
        before being passed to compute_tension_curve().
        """
        # Verify inputs are numpy arrays (not lists)
        assert isinstance(mock_energy_curve, np.ndarray), "energy_curve must be numpy array"
        assert isinstance(mock_spectral_flatness, np.ndarray), (
            "spectral_flatness must be numpy array"
        )
        assert isinstance(mock_onset_env, np.ndarray), "onset_env must be numpy array"

        # Call compute_tension_curve - should NOT raise TypeError
        result = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=mock_energy_curve,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # Verify result structure
        assert isinstance(result, dict)
        assert "tension_curve" in result
        assert "tension_peaks" in result
        assert "statistics" in result

    def test_compute_tension_arithmetic_operations(
        self,
        mock_chroma_cqt: np.ndarray,
        mock_energy_curve: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_onset_env: np.ndarray,
        mock_times_s: np.ndarray,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that arithmetic operations work correctly with numpy arrays.

        REGRESSION TEST: Verify that operations like:
        - dynamic_intensity = 0.6 * energy_norm + 0.4 * onset_norm
        work when inputs are numpy arrays (not lists).
        """
        # This should NOT raise: TypeError: can't multiply sequence by non-int of type 'float'
        result = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=mock_energy_curve,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # If we got here, arithmetic operations succeeded
        assert isinstance(result, dict)
        assert "tension_curve" in result

        # Verify tension curve is numeric array
        tension = result["tension_curve"]
        tension_array = np.asarray(tension)
        assert tension_array.dtype in [np.float32, np.float64]

    def test_compute_tension_with_list_inputs(
        self,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that compute_tension_curve handles list inputs (converts to numpy).

        This test documents that the function now converts list inputs to
        numpy arrays internally, preventing the TypeError.
        """
        # Create list inputs (simulating the bug)
        n_frames = 100
        chroma_cqt = np.random.uniform(0, 1, (12, n_frames)).astype(np.float32)
        energy_curve_list = [0.5] * n_frames
        spectral_flatness_list = [0.2] * n_frames
        onset_env_list = [0.1] * n_frames
        times_s = np.arange(n_frames) * 512 / sample_rate

        # The function now converts to numpy arrays internally, so this should work
        result = compute_tension_curve(
            chroma_cqt=chroma_cqt,
            energy_curve=energy_curve_list,
            spectral_flatness=spectral_flatness_list,
            onset_env=onset_env_list,
            times_s=times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # Should succeed because function converts lists to arrays
        assert isinstance(result, dict)
        assert "tension_curve" in result


class TestComputeTensionCurveLogic:
    """Tests for compute_tension_curve() business logic."""

    def test_compute_tension_returns_expected_structure(
        self,
        mock_chroma_cqt: np.ndarray,
        mock_energy_curve: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_onset_env: np.ndarray,
        mock_times_s: np.ndarray,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that compute_tension_curve returns expected structure."""
        result = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=mock_energy_curve,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # Check all expected keys
        assert "tension_curve" in result
        assert "tension_peaks" in result
        assert "statistics" in result

        # Check types
        tension_curve = result["tension_curve"]
        assert isinstance(tension_curve, (list, np.ndarray))

        tension_peaks = result["tension_peaks"]
        assert isinstance(tension_peaks, list)

        statistics = result["statistics"]
        assert isinstance(statistics, dict)

    def test_compute_tension_normalization(
        self,
        mock_chroma_cqt: np.ndarray,
        mock_energy_curve: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_onset_env: np.ndarray,
        mock_times_s: np.ndarray,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that tension curve values are normalized [0, 1]."""
        result = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=mock_energy_curve,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        tension_array = np.asarray(result["tension_curve"])
        assert np.all(tension_array >= 0.0), "Some tension values < 0"
        assert np.all(tension_array <= 1.0), "Some tension values > 1"

    def test_compute_tension_with_varying_energy(
        self,
        mock_chroma_cqt: np.ndarray,
        mock_spectral_flatness: np.ndarray,
        mock_onset_env: np.ndarray,
        mock_times_s: np.ndarray,
        mock_key_info: dict,
        sample_rate: int,
    ):
        """Test that higher energy results in higher tension."""
        # Create low energy curve
        low_energy = np.full(len(mock_times_s), 0.2, dtype=np.float32)
        result_low = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=low_energy,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # Create high energy curve
        high_energy = np.full(len(mock_times_s), 0.8, dtype=np.float32)
        result_high = compute_tension_curve(
            chroma_cqt=mock_chroma_cqt,
            energy_curve=high_energy,
            spectral_flatness=mock_spectral_flatness,
            onset_env=mock_onset_env,
            times_s=mock_times_s,
            key_info=mock_key_info,
            sr=sample_rate,
            hop_length=512,
        )

        # Higher energy should generally result in higher average tension
        tension_low = np.mean(result_low["tension_curve"])
        tension_high = np.mean(result_high["tension_curve"])

        # This is a heuristic test - energy is one component of tension
        # So higher energy should contribute to higher tension
        assert tension_high >= tension_low, (
            f"Higher energy should result in equal or higher tension: "
            f"low={tension_low:.3f}, high={tension_high:.3f}"
        )
