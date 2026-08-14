"""Ground-truth assertions: detected values against known-correct references.

The repository had none of these — every rhythm and key test asserted structure
("tempo_bpm > 0") rather than correctness, so a detector could return the wrong
answer and stay green. Fixtures are synthesised in-process: no network, no audio
files, no LLM calls.
"""

from __future__ import annotations

import librosa
import numpy as np
import pytest

from twinklr.core.audio.harmonic.hpss import compute_hpss
from twinklr.core.audio.harmonic.key import detect_musical_key
from twinklr.core.audio.rhythm.beats import compute_beats

# The tempogram picks an integer frame lag, so the reachable tempo grid is
# 60 * (sr / hop) / lag. At sr=22050 a 0.5s beat period is 43.07 frames at hop 512
# (unreachable: the neighbours are 117.45 and 123.05 BPM) but exactly 25 frames at
# hop 441. The ground-truth assertions use the commensurate hop so they measure the
# detector rather than the frame grid; the hop-512 behaviour is pinned separately.
KNOWN_TEMPO_BPM = 120.0
GROUND_TRUTH_HOP = 441
DEFAULT_HOP = 512


def _onset_env(y: np.ndarray, sr: int, hop_length: int) -> np.ndarray:
    return librosa.onset.onset_strength(y=compute_hpss(y).percussive, sr=sr, hop_length=hop_length)


class TestTempoGroundTruth:
    """Detected tempo against the click track's known 120 BPM."""

    def test_detected_tempo_matches_click_track_120bpm(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
    ) -> None:
        """Tempo is within 2 BPM of the click track's actual 120 BPM."""
        audio, _ = click_track_120bpm

        tempo_bpm, _ = compute_beats(
            onset_env=_onset_env(audio, sample_rate, GROUND_TRUTH_HOP),
            sr=sample_rate,
            hop_length=GROUND_TRUTH_HOP,
        )

        assert tempo_bpm == pytest.approx(KNOWN_TEMPO_BPM, abs=2.0)

    def test_detected_tempo_at_default_hop_is_frame_quantized(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
    ) -> None:
        """At the app's default hop the answer is limited by the tempogram's lag grid.

        A 120 BPM click reports 117.45 BPM at hop 512 — 60 * (22050/512) / 22, the
        nearest reachable lag. That is frame quantization, not a detection failure,
        and it is why the ground-truth assertion above uses a commensurate hop.
        Recorded for P2P's MIR work.
        """
        audio, _ = click_track_120bpm

        tempo_bpm, _ = compute_beats(
            onset_env=_onset_env(audio, sample_rate, DEFAULT_HOP),
            sr=sample_rate,
            hop_length=DEFAULT_HOP,
        )

        frames_per_second = sample_rate / DEFAULT_HOP
        true_lag = frames_per_second * 60.0 / KNOWN_TEMPO_BPM
        reachable = [
            60.0 * frames_per_second / lag
            for lag in (int(np.floor(true_lag)), int(np.ceil(true_lag)))
        ]

        assert min(abs(tempo_bpm - r) for r in reachable) < 0.1, (
            f"{tempo_bpm} is off the reachable lag grid {reachable}"
        )


class TestBeatPositionGroundTruth:
    """Detected beat positions against the click track's known click times."""

    def test_detected_beats_match_click_positions(
        self,
        click_track_120bpm: tuple[np.ndarray, list[float]],
        sample_rate: int,
    ) -> None:
        """Every detected beat lands within one hop of an actual click."""
        audio, known_beats = click_track_120bpm

        _, beat_frames = compute_beats(
            onset_env=_onset_env(audio, sample_rate, GROUND_TRUTH_HOP),
            sr=sample_rate,
            hop_length=GROUND_TRUTH_HOP,
        )
        detected = librosa.frames_to_time(beat_frames, sr=sample_rate, hop_length=GROUND_TRUTH_HOP)

        hop_s = GROUND_TRUTH_HOP / sample_rate
        errors = [min(abs(float(d) - k) for k in known_beats) for d in detected]

        # Zero margin by construction: every beat is exactly one frame late (+0.0200s),
        # uniformly, from the onset-envelope rise. Routed to P2P-T8; any regression that
        # adds a second frame of lag trips this immediately.
        assert max(errors) <= hop_s + 1e-6, f"worst beat off by {max(errors):.4f}s"
        # The click at t=0 has no onset rise in front of it, so it is not detected.
        assert len(detected) >= len(known_beats) - 1


class TestKeyGroundTruth:
    """Detected key against a constructed tonal fixture."""

    def test_detected_key_matches_constructed_tonal_fixture(
        self,
        c_major_tonal_audio: np.ndarray,
        sample_rate: int,
    ) -> None:
        """A C major triad under a C major scale is detected as C major."""
        result = detect_musical_key(c_major_tonal_audio, sample_rate, hop_length=DEFAULT_HOP)

        assert result["key"] == "C"
        assert result["mode"] == "major"
        assert result["confidence"] > 0.5
