"""Audio-specific test fixtures for unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# ============================================================================
# Synthetic Audio Fixtures
# ============================================================================


@pytest.fixture
def sample_rate() -> int:
    """Standard sample rate for tests."""
    return 22050


@pytest.fixture
def hop_length() -> int:
    """Standard hop length for tests."""
    return 512


@pytest.fixture
def frame_length() -> int:
    """Standard frame length for tests."""
    return 2048


@pytest.fixture
def sine_wave_440hz(sample_rate: int) -> np.ndarray:
    """5 seconds of 440Hz sine wave audio."""
    duration = 5.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    return np.sin(2 * np.pi * 440 * t).astype(np.float32)


@pytest.fixture
def click_track_120bpm(sample_rate: int) -> tuple[np.ndarray, list[float]]:
    """Synthetic click track at 120 BPM with known beat positions.

    Returns:
        Tuple of (audio_array, beat_times_in_seconds)
    """
    duration = 10.0
    tempo_bpm = 120.0
    beat_interval_s = 60.0 / tempo_bpm  # 0.5 seconds

    n_samples = int(sample_rate * duration)
    y = np.zeros(n_samples, dtype=np.float32)

    # Generate beat times
    beat_times: list[float] = []
    t = 0.0
    while t < duration - 0.1:
        beat_times.append(t)
        # Add a short click (10ms burst)
        start_sample = int(t * sample_rate)
        click_duration = int(0.01 * sample_rate)
        end_sample = min(start_sample + click_duration, n_samples)
        y[start_sample:end_sample] = 0.8
        t += beat_interval_s

    return y, beat_times


@pytest.fixture
def silence_audio(sample_rate: int) -> np.ndarray:
    """2 seconds of silence."""
    duration = 2.0
    return np.zeros(int(sample_rate * duration), dtype=np.float32)


@pytest.fixture
def very_short_audio(sample_rate: int) -> np.ndarray:
    """5 seconds of random noise (below 10s threshold)."""
    duration = 5.0
    rng = np.random.default_rng(42)
    return rng.standard_normal(int(sample_rate * duration)).astype(np.float32) * 0.1


@pytest.fixture
def noisy_audio(sample_rate: int) -> np.ndarray:
    """10 seconds of white noise."""
    duration = 10.0
    rng = np.random.default_rng(42)
    return rng.standard_normal(int(sample_rate * duration)).astype(np.float32) * 0.3


@pytest.fixture
def long_audio(sample_rate: int) -> np.ndarray:
    """30 seconds of audio with varying amplitude for section detection."""
    duration = 30.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

    # Create a signal with different "sections"
    # Section 1: 0-10s - quiet sine wave
    section1 = np.sin(2 * np.pi * 220 * t) * 0.3

    # Section 2: 10-20s - louder sine wave with harmonics
    section2 = (np.sin(2 * np.pi * 440 * t) + 0.5 * np.sin(2 * np.pi * 880 * t)) * 0.6

    # Section 3: 20-30s - return to quieter
    section3 = np.sin(2 * np.pi * 330 * t) * 0.4

    y = np.where(t < 10, section1, np.where(t < 20, section2, section3))
    return y.astype(np.float32)


# ============================================================================
# Pre-computed Feature Fixtures
# ============================================================================


@pytest.fixture
def sample_onset_env() -> np.ndarray:
    """1000 frames of onset envelope with known peaks."""
    env = np.zeros(1000, dtype=np.float32)
    # Create some peaks at known locations
    peak_locations = [100, 200, 300, 400, 500, 600, 700, 800, 900]
    for loc in peak_locations:
        # Gaussian-like peak
        indices = np.arange(max(0, loc - 10), min(1000, loc + 10))
        env[indices] = np.exp(-0.5 * ((indices - loc) / 3) ** 2)
    return env


@pytest.fixture
def sample_beat_frames() -> np.ndarray:
    """Known beat positions (frames) for 120 BPM at sr=22050, hop=512."""
    # 120 BPM = 2 beats/second = 1 beat every 0.5s
    # At sr=22050, hop=512: frames_per_second = 22050/512 ≈ 43
    # So 1 beat every ~21.5 frames
    frames_per_beat = 21.5
    n_beats = 40  # About 20 seconds of beats
    return np.arange(0, n_beats * frames_per_beat, frames_per_beat).astype(int)


@pytest.fixture
def sample_chroma() -> np.ndarray:
    """12 x 500 frames of chroma features simulating C major key."""
    n_frames = 500
    chroma = np.zeros((12, n_frames), dtype=np.float32)
    # C major: strong C, E, G (indices 0, 4, 7)
    chroma[0, :] = 0.8  # C
    chroma[4, :] = 0.6  # E
    chroma[7, :] = 0.7  # G
    # Some minor activity on other notes
    rng = np.random.default_rng(42)
    chroma += rng.uniform(0, 0.2, (12, n_frames)).astype(np.float32)
    return chroma


@pytest.fixture
def sample_energy_curve_with_build() -> np.ndarray:
    """Energy curve with a known build (ramp up) and drop."""
    n_frames = 500
    energy = np.zeros(n_frames, dtype=np.float32)

    # Flat start: 0-100
    energy[:100] = 0.3

    # Build: 100-250 (ramp from 0.3 to 0.9)
    energy[100:250] = np.linspace(0.3, 0.9, 150)

    # High plateau: 250-350
    energy[250:350] = 0.9

    # Drop: 350-380 (sharp drop from 0.9 to 0.2)
    energy[350:380] = np.linspace(0.9, 0.2, 30)

    # Flat end: 380-500
    energy[380:] = 0.2

    return energy


@pytest.fixture
def sample_times_s() -> np.ndarray:
    """Time array matching sample_energy_curve_with_build (500 frames)."""
    # Assuming sr=22050, hop=512: each frame is 512/22050 ≈ 0.0232s
    frame_duration = 512 / 22050
    return (np.arange(500) * frame_duration).astype(np.float32)


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def mock_app_config() -> MagicMock:
    """Mocked AppConfig for audio tests."""
    config = MagicMock()
    config.cache_dir = "/tmp/test_cache"
    config.audio_processing.hop_length = 512
    config.audio_processing.frame_length = 2048
    return config


@pytest.fixture
def mock_job_config() -> MagicMock:
    """Mocked JobConfig for audio tests."""
    config = MagicMock()
    config.checkpoint_dir = "/tmp/test_checkpoints"
    return config


# ============================================================================
# Result Structure Fixtures
# ============================================================================


@pytest.fixture
def sample_song_features() -> dict[str, Any]:
    """Sample song features dict matching schema v2.3."""
    return {
        "schema_version": "2.3",
        "audio_path": "/test/audio.mp3",
        "sr": 22050,
        "duration_s": 180.0,
        "tempo_bpm": 120.0,
        "beats_s": [0.5 * i for i in range(360)],  # 360 beats at 120 BPM
        "bars_s": [2.0 * i for i in range(90)],  # 90 bars
        "time_signature": {
            "time_signature": "4/4",
            "confidence": 0.8,
            "method": "accent_pattern",
        },
        "assumptions": {"time_signature": "4/4", "beats_per_bar": 4},
        "rhythm": {
            "beat_confidence": 0.8,
            "downbeats": list(range(0, 360, 4)),
            "downbeat_meta": {"phase_confidence": 0.7},
        },
        "key": {"key": "C", "mode": "major", "confidence": 0.75},
        "energy": {
            "rms_norm": [0.5] * 100,
            "times_s": [0.1 * i for i in range(100)],
            "phrase_level": [0.5] * 100,
        },
        "spectral": {
            "brightness": [0.5] * 100,
            "statistics": {"brightness_variance": 500},
        },
        "dynamics": {"statistics": {"dynamic_range": 0.4, "transient_density": 2.0}},
        "structure": {
            "sections": [
                {"section_id": 0, "start_s": 0.0, "end_s": 30.0, "label": "intro"},
                {"section_id": 1, "start_s": 30.0, "end_s": 60.0, "label": "verse"},
                {"section_id": 2, "start_s": 60.0, "end_s": 90.0, "label": "chorus"},
                {"section_id": 3, "start_s": 90.0, "end_s": 120.0, "label": "verse"},
                {"section_id": 4, "start_s": 120.0, "end_s": 150.0, "label": "chorus"},
                {"section_id": 5, "start_s": 150.0, "end_s": 180.0, "label": "outro"},
            ],
            "boundary_times_s": [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0],
        },
        "builds_drops": {
            "builds": [{"start_s": 50.0, "end_s": 60.0, "energy_gain": 0.3}],
            "drops": [{"time_s": 60.0, "energy_before": 0.9, "energy_after": 0.3}],
            "statistics": {"build_count": 1, "drop_count": 1},
        },
        "vocals": {
            "vocal_segments": [{"start_s": 30.0, "end_s": 90.0, "avg_probability": 0.8}],
            "statistics": {"vocal_coverage_pct": 33.3},
        },
        "chords": {
            "chords": [{"chord": "C:maj", "time_s": 0.0}],
            "statistics": {"chord_change_count": 20, "major_pct": 0.7},
        },
        "pitch": {"statistics": {"pitch_std": 100.0, "voiced_proportion": 0.5}},
        "tension": {
            "tension_curve": [0.5] * 100,
            "statistics": {"avg_tension": 0.5, "tension_variance": 0.1, "peak_count": 5},
        },
        "tempo_analysis": {"is_stable": True, "average_tempo_bpm": 120.0},
        "extensions": {
            "timeline": {
                "t_sec": [0.1 * i for i in range(100)],
                "energy": [0.5] * 100,
                "hpss_perc_ratio": [0.1] * 100,
            },
            "composites": {"show_intensity": [0.5] * 100},
        },
    }


# ============================================================================
# Edge Case Fixtures
# ============================================================================


@pytest.fixture
def empty_array() -> np.ndarray:
    """Empty numpy array."""
    return np.array([], dtype=np.float32)


@pytest.fixture
def single_value_array() -> np.ndarray:
    """Single value array."""
    return np.array([0.5], dtype=np.float32)


@pytest.fixture
def constant_array() -> np.ndarray:
    """Array with all same values."""
    return np.full(100, 0.5, dtype=np.float32)


@pytest.fixture
def array_with_nan() -> np.ndarray:
    """Array containing NaN values."""
    arr = np.array([1.0, 2.0, np.nan, 4.0, 5.0], dtype=np.float32)
    return arr


@pytest.fixture
def array_with_inf() -> np.ndarray:
    """Array containing infinity values."""
    arr = np.array([1.0, 2.0, np.inf, 4.0, -np.inf], dtype=np.float32)
    return arr
