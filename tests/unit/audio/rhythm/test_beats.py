"""Tests for beat and rhythm detection."""

from __future__ import annotations

from itertools import pairwise
from typing import ClassVar

import numpy as np
import pytest

from twinklr.core.audio.rhythm.beats import (
    compute_beats,
    detect_downbeats_phase_aligned,
    detect_time_signature,
    resolve_tempo_octave,
)

SR = 22050
HOP = 512
FPS = SR / HOP


def _accent_grid(
    pattern: list[float], *, downbeat_phase: int, n_beats: int = 72, seed: int = 0
) -> tuple[np.ndarray, np.ndarray]:
    """Regular beat frames whose onset strengths repeat ``pattern`` from ``downbeat_phase``.

    Accents carry Gaussian noise (sd 0.15) so that a single bar is not always decisive.
    """
    rng = np.random.default_rng(seed)
    beat_frames = np.arange(n_beats, dtype=int) * 21 + 10
    onset_env = np.zeros(int(beat_frames[-1]) + 30, dtype=np.float32)
    for index, frame in enumerate(beat_frames):
        accent = pattern[(index - downbeat_phase) % len(pattern)]
        onset_env[frame] = max(0.0, accent + rng.normal(0.0, 0.15))
    return beat_frames, onset_env


_THREE_FOUR = [1.0, 0.4, 0.4]
_FOUR_FOUR = [1.0, 0.45, 0.7, 0.45]
_SIX_EIGHT = [1.0, 0.4, 0.4, 0.6, 0.4, 0.4]
_TWO_FOUR = [1.0, 0.4]
# 2/4 accents cannot be told from 4/4 by accent evidence alone (the tempo-change MIR
# fixture is 4/4 yet shows a larger 2-beat than 4-beat excess); duple meters report 4/4.
_METER_CASES = [
    (pattern, phase, expected)
    for pattern, expected in (
        (_THREE_FOUR, "3/4"),
        (_FOUR_FOUR, "4/4"),
        (_SIX_EIGHT, "6/8"),
        (_TWO_FOUR, "4/4"),
    )
    for phase in range(len(pattern))
]


def _drum_track(
    *,
    bpm: float,
    pattern: list[float],
    chord_every: int,
    chord_phase: int = 0,
    n_events: int = 192,
    jitter_s: float = 0.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Onset envelope and chroma for events on a ``bpm`` grid.

    ``pattern`` cycles the event accents; the chord changes on every ``chord_every``-th
    event starting at ``chord_phase``, cycling C, F, G, A minor.
    """
    rng = np.random.default_rng(seed)
    step_s = 60.0 / bpm
    times = 0.5 + np.arange(n_events) * step_s + rng.normal(0.0, jitter_s, n_events)
    n_frames = int((times[-1] + 1.0) * FPS)
    onset_env = rng.random(n_frames).astype(np.float32) * 0.02
    for index, time_s in enumerate(times):
        frame = round(time_s * FPS)
        accent = max(0.0, pattern[index % len(pattern)] + rng.normal(0.0, 0.04))
        onset_env[frame] += accent
        onset_env[frame + 1] += 0.4 * accent
    triads = [(0, 4, 7), (5, 9, 0), (7, 11, 2), (9, 0, 4)]
    chroma = rng.random((12, n_frames)).astype(np.float32) * 0.05
    change_frames = [round(times[i] * FPS) for i in range(chord_phase, n_events, chord_every)]
    bounds = [0, *change_frames, n_frames]
    for chord_index, (start, end) in enumerate(pairwise(bounds)):
        for pitch in triads[chord_index % len(triads)]:
            chroma[pitch, start:end] += 1.0
    return onset_env, chroma


class TestComputeBeats:
    """Tests for compute_beats function."""

    def test_returns_tempo_and_beat_frames(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns a tempo and beat frames array."""
        tempo, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert isinstance(tempo, float)
        assert isinstance(beat_frames, np.ndarray)
        assert tempo >= 0.0

    def test_tempo_in_reasonable_range(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Detected tempo is within reasonable BPM range."""
        tempo, _ = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        # Librosa typically returns tempo in range 30-300 BPM
        assert 30 <= tempo <= 300 or tempo == 0.0

    def test_beat_frames_are_integers(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Beat frames should be integers."""
        _, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert beat_frames.dtype == int or np.issubdtype(beat_frames.dtype, np.integer)

    def test_beat_frames_within_bounds(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Beat frames should be within onset_env length."""
        _, beat_frames = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        if len(beat_frames) > 0:
            assert beat_frames.min() >= 0
            assert beat_frames.max() < len(sample_onset_env)

    def test_custom_start_bpm(
        self,
        sample_onset_env: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Start BPM parameter influences tempo detection."""
        # This tests the parameter is accepted; actual influence depends on librosa
        tempo, _ = compute_beats(
            onset_env=sample_onset_env,
            sr=sample_rate,
            hop_length=hop_length,
            start_bpm=90.0,
        )

        assert isinstance(tempo, float)

    def test_empty_onset_env(self, sample_rate: int, hop_length: int) -> None:
        """Empty onset envelope is handled."""
        empty_env = np.array([], dtype=np.float32)

        # Should not raise
        tempo, beat_frames = compute_beats(
            onset_env=empty_env,
            sr=sample_rate,
            hop_length=hop_length,
        )

        assert isinstance(tempo, float)
        assert isinstance(beat_frames, np.ndarray)


class TestDetectTimeSignature:
    """Tests for detect_time_signature function."""

    def test_returns_expected_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        assert "time_signature" in result
        assert "confidence" in result
        assert "method" in result

    def test_time_signature_is_valid(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Detected time signature is one of expected values."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        valid_signatures = {"2/4", "3/4", "4/4", "6/8"}
        assert result["time_signature"] in valid_signatures

    def test_confidence_in_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Confidence is in [0, 1] range."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        assert 0.0 <= result["confidence"] <= 1.0

    def test_few_beats_returns_default(
        self,
        sample_onset_env: np.ndarray,
    ) -> None:
        """Fewer than 8 beats returns default 4/4."""
        few_beats = np.array([10, 30, 50, 70], dtype=int)  # Only 4 beats

        result = detect_time_signature(
            beat_frames=few_beats,
            onset_env=sample_onset_env,
        )

        assert result["time_signature"] == "4/4"
        assert result["method"] == "default"

    def test_4_4_time_detection(self) -> None:
        """Test detection of 4/4 time signature with strong downbeats."""
        # Create an onset envelope with strong accents every 4 beats
        n_frames = 1000
        onset_env = np.zeros(n_frames, dtype=np.float32)

        # Beat frames every ~21 frames (120 BPM at sr=22050, hop=512)
        beat_frames = np.arange(10, 900, 21, dtype=int)

        # Make every 4th beat stronger (downbeat pattern)
        for i, bf in enumerate(beat_frames):
            if bf < n_frames:
                onset_env[bf] = 1.0 if i % 4 == 0 else 0.5

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # 4/4 should be detected or at least have high score
        assert "all_scores" in result
        # 4/4 score should be competitive
        assert result["all_scores"]["4/4"] > 0.2

    def test_all_scores_included(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
    ) -> None:
        """All time signature scores are included when method is accent_pattern."""
        result = detect_time_signature(
            beat_frames=sample_beat_frames,
            onset_env=sample_onset_env,
        )

        if result["method"] == "accent_pattern":
            assert "all_scores" in result
            assert "2/4" in result["all_scores"]
            assert "3/4" in result["all_scores"]
            assert "4/4" in result["all_scores"]
            assert "6/8" in result["all_scores"]


class TestDetectDownbeatsPhaseAligned:
    """Tests for detect_downbeats_phase_aligned function."""

    def test_returns_expected_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Function returns expected dictionary structure."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert "downbeats" in result
        assert "phase" in result
        assert "phase_confidence" in result

    def test_downbeats_structure(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Each downbeat has required fields."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        if result["downbeats"]:
            db = result["downbeats"][0]
            assert "beat_index" in db
            assert "time_s" in db
            assert "confidence" in db

    def test_phase_in_valid_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Phase offset is within beats_per_bar range."""
        beats_per_bar = 4
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=beats_per_bar,
        )

        assert 0 <= result["phase"] < beats_per_bar

    def test_phase_confidence_in_range(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Phase confidence is in [0, 1] range."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert 0.0 <= result["phase_confidence"] <= 1.0

    def test_few_beats_returns_empty(
        self,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Fewer than 2*beats_per_bar returns empty downbeats."""
        few_beats = np.array([10, 30, 50], dtype=int)  # Only 3 beats

        result = detect_downbeats_phase_aligned(
            beat_frames=few_beats,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=4,
        )

        assert result["downbeats"] == []
        assert result["phase_confidence"] == 0.0

    def test_downbeat_spacing(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Downbeats are spaced beats_per_bar apart."""
        beats_per_bar = 4
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=beats_per_bar,
        )

        downbeats = result["downbeats"]
        if len(downbeats) >= 2:
            # Check beat indices are spaced by beats_per_bar
            for i in range(1, len(downbeats)):
                diff = downbeats[i]["beat_index"] - downbeats[i - 1]["beat_index"]
                assert diff == beats_per_bar

    def test_invalid_beats_per_bar_handled(
        self,
        sample_beat_frames: np.ndarray,
        sample_onset_env: np.ndarray,
        sample_chroma: np.ndarray,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Invalid beats_per_bar (< 2) is corrected to 4."""
        result = detect_downbeats_phase_aligned(
            beat_frames=sample_beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=sample_onset_env,
            chroma_cqt=sample_chroma,
            beats_per_bar=1,  # Invalid, should be corrected to 4
        )

        # Should have processed without error
        assert isinstance(result["downbeats"], list)

    def test_low_phase_confidence_case(
        self,
        sample_rate: int,
        hop_length: int,
    ) -> None:
        """Test when phase scores are too low for confidence."""
        # Create uniform onset env - all phases will score similarly
        onset_env = np.ones(1000, dtype=np.float32) * 0.5
        beat_frames = np.arange(0, 900, 20, dtype=int)
        chroma = np.ones((12, 1000), dtype=np.float32) * 0.5

        result = detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=sample_rate,
            hop_length=hop_length,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=4,
        )

        # Should return low or zero confidence when phases are similar
        assert result["phase_confidence"] >= 0.0
        assert result["phase_confidence"] <= 1.0


class TestTimeSignatureEdgeCases:
    """Additional edge case tests for time signature detection."""

    def test_very_low_strength_beats(self) -> None:
        """Test with very low onset strength."""
        # Create onset envelope with very low values
        n_frames = 1000
        onset_env = np.full(n_frames, 0.001, dtype=np.float32)
        beat_frames = np.arange(10, 900, 20, dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should handle gracefully
        assert "time_signature" in result
        assert result["time_signature"] in {"2/4", "3/4", "4/4", "6/8"}

    def test_insufficient_beats_for_grouping(self) -> None:
        """Test when beats are insufficient for proper grouping analysis."""
        n_frames = 200
        onset_env = np.random.rand(n_frames).astype(np.float32)
        beat_frames = np.array([10, 30, 50, 70, 90, 110, 130, 150, 170, 190], dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should handle gracefully
        assert "time_signature" in result

    def test_uniform_onset_strengths(self) -> None:
        """Test with uniform onset strengths (no accent pattern)."""
        n_frames = 1000
        onset_env = np.ones(n_frames, dtype=np.float32)
        beat_frames = np.arange(10, 900, 20, dtype=int)

        result = detect_time_signature(
            beat_frames=beat_frames,
            onset_env=onset_env,
        )

        # Should default to 4/4 with low confidence
        assert result["time_signature"] == "4/4"


class TestMeterIsPhaseAwareAndChanceCorrected:
    """Meter detection scores every bar phase and subtracts the shuffled-beat baseline."""

    @pytest.mark.parametrize(("pattern", "downbeat_phase", "expected"), _METER_CASES)
    def test_accent_pattern_at_every_downbeat_phase(
        self, pattern: list[float], downbeat_phase: int, expected: str
    ) -> None:
        beat_frames, onset_env = _accent_grid(pattern, downbeat_phase=downbeat_phase)

        result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)

        assert result["time_signature"] == expected
        assert result["method"] == "accent_pattern"

    def test_no_accent_structure_scores_near_zero_and_defaults_to_4_4(self) -> None:
        rng = np.random.default_rng(3)
        beat_frames = np.arange(72, dtype=int) * 21 + 10
        onset_env = np.zeros(int(beat_frames[-1]) + 30, dtype=np.float32)
        onset_env[beat_frames] = rng.random(len(beat_frames)).astype(np.float32)

        result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)

        assert result["time_signature"] == "4/4"
        assert result["method"] == "default"
        assert all(abs(score) < 0.1 for score in result["all_scores"].values())

    def test_detection_is_deterministic(self) -> None:
        beat_frames, onset_env = _accent_grid([1.0, 0.4, 0.4], downbeat_phase=2)

        first = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)
        second = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)

        assert first == second

    @pytest.mark.parametrize(("pattern", "downbeat_phase", "expected"), _METER_CASES)
    def test_confidence_is_share_of_shuffles_beaten(
        self, pattern: list[float], downbeat_phase: int, expected: str
    ) -> None:
        """A clear accent pattern beats (almost) every shuffled arrangement of its beats."""
        beat_frames, onset_env = _accent_grid(pattern, downbeat_phase=downbeat_phase)

        result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)

        assert result["confidence"] >= 0.95

    def test_confidence_is_low_without_accent_structure(self) -> None:
        rng = np.random.default_rng(3)
        beat_frames = np.arange(72, dtype=int) * 21 + 10
        onset_env = np.zeros(int(beat_frames[-1]) + 30, dtype=np.float32)
        onset_env[beat_frames] = rng.random(len(beat_frames)).astype(np.float32)

        result = detect_time_signature(beat_frames=beat_frames, onset_env=onset_env)

        assert 0.0 <= result["confidence"] < 0.95


def _bar_grid(
    *,
    onset_pattern: list[float],
    chord_positions: set[int],
    downbeat_phase: int,
    chords: list[tuple[int, ...]],
    n_bars: int = 24,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Beat frames, onset envelope and chroma for bars of ``len(onset_pattern)`` beats.

    The bar starts at beat index ``downbeat_phase``. The chord advances through
    ``chords`` on every bar position in ``chord_positions``.
    """
    rng = np.random.default_rng(seed)
    beats_per_bar = len(onset_pattern)
    n_beats = n_bars * beats_per_bar + downbeat_phase
    beat_frames = np.arange(n_beats, dtype=int) * 21 + 10
    n_frames = int(beat_frames[-1]) + 30
    onset_env = rng.random(n_frames).astype(np.float32) * 0.02
    chroma = rng.random((12, n_frames)).astype(np.float32) * 0.05
    chord_index = 0
    for index, frame in enumerate(beat_frames):
        position = (index - downbeat_phase) % beats_per_bar
        onset_env[frame] += max(0.0, onset_pattern[position] + rng.normal(0.0, 0.05))
        if position in chord_positions:
            chord_index += 1
        for pitch in chords[chord_index % len(chords)]:
            chroma[pitch, frame : frame + 21] += 1.0
    return beat_frames, onset_env, chroma


_C, _F, _G, _AM = (0, 4, 7), (5, 9, 0), (7, 11, 2), (9, 0, 4)


class TestDownbeatPhaseFromHarmonicChange:
    """Chord changes place the bar; onset accents only break a beat-1/beat-3 tie."""

    def _downbeats(
        self, beat_frames: np.ndarray, onset_env: np.ndarray, chroma: np.ndarray, bpb: int
    ) -> dict[str, object]:
        return detect_downbeats_phase_aligned(
            beat_frames=beat_frames,
            sr=SR,
            hop_length=HOP,
            onset_env=onset_env,
            chroma_cqt=chroma,
            beats_per_bar=bpb,
        )

    @pytest.mark.parametrize("downbeat_phase", range(4))
    def test_backbeat_4_4_downbeat_is_a_chord_beat(self, downbeat_phase: int) -> None:
        # Snare on 2 and 4 is the loudest beat; two chords alternate on 1 and 3.
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[0.6, 1.0, 0.6, 1.0],
            chord_positions={0, 2},
            downbeat_phase=downbeat_phase,
            chords=[_C, _G],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert result["phase"] % 2 == downbeat_phase % 2

    @pytest.mark.parametrize("downbeat_phase", range(4))
    def test_backbeat_kick_on_1_breaks_the_beat_1_3_tie(self, downbeat_phase: int) -> None:
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[0.75, 1.0, 0.55, 1.0],
            chord_positions={0, 2},
            downbeat_phase=downbeat_phase,
            chords=[_C, _G],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert result["phase"] == downbeat_phase
        assert result["method"] == "harmonic_change+onset"

    @pytest.mark.parametrize("downbeat_phase", range(4))
    def test_chord_on_beat_1_only_decides_without_onset(self, downbeat_phase: int) -> None:
        # Backbeat accents would put the bar on beat 2 or 4; the chord change says beat 1.
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[0.6, 1.0, 0.6, 1.0],
            chord_positions={0},
            downbeat_phase=downbeat_phase,
            chords=[_C, _F, _G, _AM],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert result["phase"] == downbeat_phase
        assert result["method"] == "harmonic_change"
        assert result["phase_confidence"] >= 0.95

    @pytest.mark.parametrize("downbeat_phase", range(4))
    def test_downbeat_accented_4_4_without_chord_changes(self, downbeat_phase: int) -> None:
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[1.0, 0.45, 0.65, 0.45],
            chord_positions=set(),
            downbeat_phase=downbeat_phase,
            chords=[_C],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert result["phase"] == downbeat_phase
        assert result["method"] == "onset_accent"
        assert result["phase_confidence"] >= 0.95

    @pytest.mark.parametrize("downbeat_phase", range(4))
    def test_downbeat_accented_4_4_with_chords_on_1(self, downbeat_phase: int) -> None:
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[1.0, 0.45, 0.65, 0.45],
            chord_positions={0},
            downbeat_phase=downbeat_phase,
            chords=[_C, _F, _G, _AM],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert result["phase"] == downbeat_phase

    @pytest.mark.parametrize("downbeat_phase", range(3))
    def test_waltz_at_every_phase(self, downbeat_phase: int) -> None:
        beat_frames, onset_env, chroma = _bar_grid(
            onset_pattern=[1.0, 0.4, 0.4],
            chord_positions={0},
            downbeat_phase=downbeat_phase,
            chords=[_C, _F, _G, _AM],
        )

        result = self._downbeats(beat_frames, onset_env, chroma, 3)

        assert result["phase"] == downbeat_phase
        assert result["phase_confidence"] >= 0.95

    def test_no_evidence_falls_back_deterministically_with_zero_confidence(self) -> None:
        rng = np.random.default_rng(5)
        beat_frames = np.arange(96, dtype=int) * 21 + 10
        n_frames = int(beat_frames[-1]) + 30
        onset_env = np.zeros(n_frames, dtype=np.float32)
        onset_env[beat_frames] = rng.random(len(beat_frames)).astype(np.float32)
        chroma = rng.random((12, n_frames)).astype(np.float32)

        first = self._downbeats(beat_frames, onset_env, chroma, 4)
        second = self._downbeats(beat_frames, onset_env, chroma, 4)

        assert first == second
        assert first["method"] == "fallback"
        assert first["phase_confidence"] == 0.0


class TestResolveTempoOctave:
    """The tracker's tempo is halved only on backbeat evidence (see resolve_tempo_octave)."""

    # Half-time feel at 79 BPM: kick, hat, snare, hat on the 158 BPM eighths, with hats
    # loud enough that the tracker locks to the eighths; the chord changes with the kick
    # at the start of every 79 BPM bar.
    HALF_TIME_FEEL: ClassVar[list[float]] = [0.8, 0.6, 1.0, 0.6]

    def _track_and_resolve(
        self, onset_env: np.ndarray, chroma: np.ndarray
    ) -> tuple[float, np.ndarray, float, np.ndarray, dict[str, object]]:
        tempo, beat_frames = compute_beats(onset_env=onset_env, sr=SR, hop_length=HOP)
        resolved_tempo, resolved_frames, record = resolve_tempo_octave(
            tempo_bpm=tempo,
            beat_frames=beat_frames,
            onset_env=onset_env,
            chroma_cqt=chroma,
        )
        return tempo, beat_frames, resolved_tempo, resolved_frames, record

    @pytest.mark.parametrize("jitter_s", [0.0, 0.008])
    def test_double_time_backbeat_resolves_to_slower_tactus(self, jitter_s: float) -> None:
        onset_env, chroma = _drum_track(
            bpm=158.0, pattern=self.HALF_TIME_FEEL, chord_every=8, jitter_s=jitter_s
        )

        tempo, beat_frames, resolved_tempo, resolved_frames, record = self._track_and_resolve(
            onset_env, chroma
        )

        assert tempo == pytest.approx(158.0, rel=0.03)  # the tracker locks to eighths
        assert resolved_tempo == pytest.approx(tempo / 2.0)
        assert len(resolved_frames) == pytest.approx(len(beat_frames) / 2.0, abs=1)
        # The kept beats are the kick/snare eighths, not the hats.
        strengths = [float(onset_env[frame - 2 : frame + 3].max()) for frame in resolved_frames]
        assert float(np.median(strengths)) > 0.75
        assert record["chosen_bpm"] == pytest.approx(resolved_tempo)
        assert record["tracker_bpm"] == pytest.approx(tempo)
        assert "backbeat" in str(record["reason"])

    @pytest.mark.parametrize(
        "pattern", [[1.0, 0.6, 0.8, 0.6], [1.0, 1.0, 1.0, 1.0]], ids=["downbeat", "flat"]
    )
    def test_genuinely_fast_4_4_stays_fast(self, pattern: list[float]) -> None:
        onset_env, chroma = _drum_track(bpm=160.0, pattern=pattern, chord_every=4)

        tempo, beat_frames, resolved_tempo, resolved_frames, record = self._track_and_resolve(
            onset_env, chroma
        )

        assert tempo == pytest.approx(160.0, rel=0.03)
        assert resolved_tempo == tempo
        assert np.array_equal(resolved_frames, beat_frames)
        assert record["chosen_bpm"] == pytest.approx(tempo)

    def test_slow_track_is_not_doubled_or_halved(self) -> None:
        onset_env, chroma = _drum_track(
            bpm=70.0, pattern=[0.7, 1.0, 0.7, 1.0], chord_every=4, n_events=64
        )

        tempo, beat_frames, resolved_tempo, resolved_frames, _ = self._track_and_resolve(
            onset_env, chroma
        )

        assert tempo == pytest.approx(70.0, rel=0.03)
        assert resolved_tempo == tempo
        assert np.array_equal(resolved_frames, beat_frames)

    def test_sparse_grid_keeps_tracker_tempo(self) -> None:
        onset_env, chroma = _drum_track(
            bpm=158.0, pattern=self.HALF_TIME_FEEL, chord_every=8, n_events=12
        )

        tempo, beat_frames, resolved_tempo, resolved_frames, record = self._track_and_resolve(
            onset_env, chroma
        )

        assert resolved_tempo == tempo
        assert np.array_equal(resolved_frames, beat_frames)
        assert record["reason"]

    def test_resolution_is_deterministic(self) -> None:
        onset_env, chroma = _drum_track(bpm=158.0, pattern=self.HALF_TIME_FEEL, chord_every=8)

        first = self._track_and_resolve(onset_env, chroma)
        second = self._track_and_resolve(onset_env, chroma)

        assert first[2] == second[2]
        assert np.array_equal(first[3], second[3])
        assert first[4] == second[4]
