"""Shared fixtures for audio tests."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def sample_rate() -> int:
    """Standard sample rate for tests."""
    return 22050


@pytest.fixture
def duration_s() -> float:
    """Standard duration for test audio."""
    return 30.0


@pytest.fixture
def mock_audio_signal(sample_rate: int, duration_s: float) -> np.ndarray:
    """Generate mock audio signal (sine wave at 440Hz)."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s))
    # Simple sine wave at 440 Hz (A4)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t)
    return signal.astype(np.float32)


@pytest.fixture
def mock_spectral_centroid(
    duration_s: float, hop_length: int = 512, sample_rate: int = 22050
) -> np.ndarray:
    """Generate mock spectral centroid array (numpy, not list).

    This fixture specifically returns a numpy array to test the regression
    where spectral_centroid was being converted to a list before passing
    to detect_vocals(), causing TypeError.
    """
    n_frames = int((duration_s * sample_rate) / hop_length)
    # Generate realistic spectral centroid values (Hz)
    centroid = np.random.uniform(1000, 3000, n_frames)
    return centroid.astype(np.float32)


@pytest.fixture
def mock_spectral_flatness(
    duration_s: float, hop_length: int = 512, sample_rate: int = 22050
) -> np.ndarray:
    """Generate mock spectral flatness array (numpy, not list).

    This fixture specifically returns a numpy array to test the regression
    where spectral_flatness was being converted to a list before passing
    to detect_vocals(), causing TypeError.
    """
    n_frames = int((duration_s * sample_rate) / hop_length)
    # Flatness is between 0 (tonal) and 1 (noisy)
    flatness = np.random.uniform(0.1, 0.3, n_frames)
    return flatness.astype(np.float32)


@pytest.fixture
def mock_energy_curve(
    duration_s: float, hop_length: int = 512, sample_rate: int = 22050
) -> np.ndarray:
    """Generate mock energy curve array (numpy, not list).

    This fixture specifically returns a numpy array to test the regression
    where energy_curve was being converted to a list before passing
    to compute_tension_curve(), causing TypeError.
    """
    n_frames = int((duration_s * sample_rate) / hop_length)
    energy = np.random.uniform(0.0, 1.0, n_frames)
    return energy.astype(np.float32)


@pytest.fixture
def mock_onset_env(
    duration_s: float, hop_length: int = 512, sample_rate: int = 22050
) -> np.ndarray:
    """Generate mock onset envelope array (numpy, not list).

    This fixture specifically returns a numpy array to test the regression
    where onset_env was being converted to a list, causing TypeError.
    """
    n_frames = int((duration_s * sample_rate) / hop_length)
    onset = np.random.uniform(0.0, 0.5, n_frames)
    return onset.astype(np.float32)


@pytest.fixture
def mock_chroma_cqt(
    duration_s: float, hop_length: int = 512, sample_rate: int = 22050
) -> np.ndarray:
    """Generate mock chroma CQT array (12 x n_frames)."""
    n_frames = int((duration_s * sample_rate) / hop_length)
    # 12 chroma bins
    chroma = np.random.uniform(0.0, 1.0, (12, n_frames))
    return chroma.astype(np.float32)


@pytest.fixture
def mock_key_info() -> dict:
    """Generate mock key detection info."""
    return {
        "key": "C",
        "mode": "major",
        "confidence": 0.85,
    }


@pytest.fixture
def mock_times_s(duration_s: float, hop_length: int = 512, sample_rate: int = 22050) -> np.ndarray:
    """Generate mock time array in seconds."""
    n_frames = int((duration_s * sample_rate) / hop_length)
    times = np.arange(n_frames) * hop_length / sample_rate
    return times.astype(np.float32)
