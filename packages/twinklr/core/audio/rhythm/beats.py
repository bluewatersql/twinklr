"""Beat and tempo detection."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import librosa
import numpy as np

from twinklr.core.audio.utils import frames_to_time, normalize_to_0_1


def compute_beats(
    *,
    onset_env: np.ndarray,
    sr: int,
    hop_length: int,
    start_bpm: float = 120.0,
) -> tuple[float, np.ndarray]:
    """Extract tempo and beat frames from onset envelope.

    Args:
        onset_env: Onset strength envelope
        sr: Sample rate
        hop_length: Hop length
        start_bpm: Initial tempo estimate

    Returns:
        Tuple of (tempo_bpm, beat_frames)
    """
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        units="frames",
        start_bpm=start_bpm,
        tightness=100,
    )
    # Convert numpy array/scalar to Python float using .item()
    if tempo is not None:
        tempo_f = float(tempo.item()) if hasattr(tempo, "item") else float(tempo)
    else:
        tempo_f = 0.0
    return tempo_f, np.asarray(beat_frames, dtype=int)


# Shuffled-beat null used to chance-correct the phase-aware statistics below. The
# generator is seeded so analysis stays deterministic.
_NULL_SHUFFLES = 100
_NULL_SEED = 0
# A triple meter must beat the duple evidence by this much chance-corrected score.
TRIPLE_METER_MARGIN = 0.10
# Fewest tracker beats (eight 4-beat cycles) on which the octave evidence is tested.
_OCTAVE_MIN_BEATS = 32


def _beat_strengths(onset_env: np.ndarray, beat_frames: np.ndarray) -> np.ndarray:
    """Peak onset strength within +/-2 frames of each beat (absorbs tracker jitter)."""
    frames = np.clip(beat_frames.astype(int), 0, len(onset_env) - 1)
    return np.array([float(onset_env[max(0, f - 2) : f + 3].max()) for f in frames])


def _zscore(values: np.ndarray) -> np.ndarray:
    return np.asarray((values - values.mean()) / (values.std() + 1e-9), dtype=np.float64)


def _shuffles(values: np.ndarray, count: int) -> list[np.ndarray]:
    rng = np.random.default_rng(_NULL_SEED)
    return [rng.permutation(values) for _ in range(count)]


def _grouping_score(z: np.ndarray, n: int, phase: int) -> float:
    """How well beats from ``phase`` group into n-beat bars with a strong first beat."""
    n_groups = (len(z) - phase) // n
    grouped = z[phase : phase + n_groups * n].reshape(n_groups, n)
    first_is_max = float(np.mean(grouped.argmax(axis=1) == 0))
    first_above_mean = float(np.mean(grouped[:, 0] > grouped.mean(axis=1)))
    return 0.6 * first_is_max + 0.4 * first_above_mean


def _best_phase_grouping(z: np.ndarray, n: int) -> float:
    return max(_grouping_score(z, n, phase) for phase in range(n))


def _phase_contrast(z: np.ndarray, n: int) -> tuple[float, int]:
    """Largest mean(z at phase p of n) - mean(z elsewhere), and that phase."""
    contrasts = []
    for phase in range(n):
        mask = np.zeros(len(z), dtype=bool)
        mask[phase::n] = True
        contrasts.append(float(z[mask].mean() - z[~mask].mean()))
    best = int(np.argmax(contrasts))
    return contrasts[best], best


def _periodic_phase_test(values: np.ndarray, n: int) -> dict[str, Any]:
    """Strongest phase of an n-beat periodicity, tested against shuffled beats.

    Significant when the observed best-phase contrast exceeds the 95th percentile of the
    best-phase contrast over shuffled beats (a one-sided permutation test, p < 0.05).
    """
    z = _zscore(values)
    observed, phase = _phase_contrast(z, n)
    null = np.array([_phase_contrast(s, n)[0] for s in _shuffles(z, 2 * _NULL_SHUFFLES)])
    return {
        "phase": phase,
        "excess": round(observed - float(null.mean()), 3),
        "significant": bool(observed > float(np.percentile(null, 95))),
    }


def _harmonic_change(chroma_cqt: np.ndarray, beat_frames: np.ndarray) -> np.ndarray:
    """Chroma change entering each beat span: 1 - cosine(span i-1, span i); 0 at the ends."""
    frames = np.clip(beat_frames.astype(int), 0, chroma_cqt.shape[1] - 1)
    spans = np.stack(
        [
            np.median(chroma_cqt[:, start : max(end, start + 1)], axis=1)
            for start, end in pairwise(frames)
        ],
        axis=1,
    )
    unit = spans / (np.linalg.norm(spans, axis=0) + 1e-9)
    change = np.zeros(len(frames), dtype=np.float64)
    change[1:-1] = 1.0 - np.sum(unit[:, 1:] * unit[:, :-1], axis=0)
    return change


def resolve_tempo_octave(
    *,
    tempo_bpm: float,
    beat_frames: np.ndarray,
    onset_env: np.ndarray,
    chroma_cqt: np.ndarray,
    start_bpm: float = 120.0,
) -> tuple[float, np.ndarray, dict[str, Any]]:
    """Choose between the tracker's tempo and half of it from backbeat evidence.

    On the tracker's grid, the strongest 4-beat onset accent and the strongest 4-beat
    harmonic-change phase are each tested against shuffled beats. When both are
    significant and the accent falls exactly two tracker beats from the chord change,
    the accent is a backbeat (snare on 2 and 4 against chords on 1 and 3) and the tracker
    has locked to the eighth notes: the tempo is halved, keeping the beats that carry
    the accent and the chord changes. An accent in phase with the chord change is a
    downbeat and keeps the tracker tempo, as does any weaker or ambiguous evidence. Half
    tempo is only considered when it stays within one octave of the tracker prior
    (``tempo_bpm >= start_bpm``). The tempo is never doubled.

    Args:
        tempo_bpm: Tempo from ``compute_beats``
        beat_frames: Beat frames from ``compute_beats``
        onset_env: Onset strength envelope
        chroma_cqt: Chroma features (12 x n_frames)
        start_bpm: The tracker prior used by ``compute_beats``

    Returns:
        Tuple of (tempo_bpm, beat_frames, record); the record lists both candidates, the
        evidence and the reason for the choice.
    """
    beat_frames = np.asarray(beat_frames, dtype=int)
    record: dict[str, Any] = {
        "tracker_bpm": float(tempo_bpm),
        "half_bpm": float(tempo_bpm) / 2.0,
        "chosen_bpm": float(tempo_bpm),
    }
    if len(beat_frames) < _OCTAVE_MIN_BEATS:
        record["reason"] = f"kept tracker tempo: fewer than {_OCTAVE_MIN_BEATS} beats"
        return tempo_bpm, beat_frames, record
    if tempo_bpm < start_bpm:
        record["reason"] = "kept tracker tempo: half tempo is over an octave below the prior"
        return tempo_bpm, beat_frames, record

    accent = _periodic_phase_test(_beat_strengths(onset_env, beat_frames), 4)
    harmonic = _periodic_phase_test(_harmonic_change(chroma_cqt, beat_frames), 4)
    record["accent"] = accent
    record["harmonic_change"] = harmonic
    offset = (accent["phase"] - harmonic["phase"]) % 4
    if not (accent["significant"] and harmonic["significant"]):
        record["reason"] = "kept tracker tempo: no significant 4-beat accent and chord phase"
        return tempo_bpm, beat_frames, record
    if offset != 2:
        record["reason"] = f"kept tracker tempo: accent is {offset} beats from chord change"
        return tempo_bpm, beat_frames, record

    half_tempo = float(tempo_bpm) / 2.0
    record["chosen_bpm"] = half_tempo
    record["reason"] = "halved: backbeat accent two beats from the chord change"
    return half_tempo, beat_frames[accent["phase"] % 2 :: 2], record


def detect_time_signature(
    *,
    beat_frames: np.ndarray,
    onset_env: np.ndarray,
) -> dict[str, Any]:
    """Detect time signature from phase-aware, chance-corrected accent grouping.

    For each grouping n in (2, 3, 4, 6), the score is how well beats fall into n-beat bars
    with a strong first beat, at the best of the n bar phases, minus the same best-phase
    score averaged over shuffled beats. Small groupings score higher by chance alone,
    which this subtraction removes. The result is 4/4 unless the triple evidence
    (3/4 or 6/8) beats the duple evidence (2/4 or 4/4) by ``TRIPLE_METER_MARGIN``; duple
    evidence is reported as 4/4 because accents alone do not separate 2/4 from 4/4.

    Args:
        beat_frames: Beat frame indices
        onset_env: Onset strength envelope

    Returns:
        Dict with time_signature, confidence, method, all_scores (chance-corrected)
    """
    if len(beat_frames) < 8:
        return {"time_signature": "4/4", "confidence": 0.0, "method": "default"}

    strengths = _beat_strengths(onset_env, beat_frames)

    if strengths.size < 12:
        return {"time_signature": "4/4", "confidence": 0.3, "method": "default"}

    z = _zscore(strengths)
    shuffled = _shuffles(z, _NULL_SHUFFLES)
    excess: dict[int, float] = {}
    for n in (2, 3, 4, 6):
        if len(z) < n * 3:
            excess[n] = 0.0
            continue
        baseline = float(np.mean([_best_phase_grouping(s, n) for s in shuffled]))
        excess[n] = _best_phase_grouping(z, n) - baseline

    duple = max(excess[2], excess[4])
    triple = max(excess[3], excess[6])
    if triple > duple + TRIPLE_METER_MARGIN and triple > TRIPLE_METER_MARGIN:
        signature = "3/4" if excess[3] >= excess[6] else "6/8"
        best = triple
    else:
        signature, best = "4/4", duple

    return {
        "time_signature": signature,
        "confidence": float(np.clip(best, 0.0, 1.0)),
        "method": "accent_pattern" if best > TRIPLE_METER_MARGIN else "default",
        "all_scores": {
            label: round(excess[n], 3)
            for label, n in (("2/4", 2), ("3/4", 3), ("4/4", 4), ("6/8", 6))
        },
    }


def detect_downbeats_phase_aligned(
    *,
    beat_frames: np.ndarray,
    sr: int,
    hop_length: int,
    onset_env: np.ndarray,
    chroma_cqt: np.ndarray,
    beats_per_bar: int,
) -> dict[str, Any]:
    """Detect downbeats by choosing a global phase offset.

    Maximizes onset strength + harmonic change at downbeat positions.

    Args:
        beat_frames: Beat frame indices
        sr: Sample rate
        hop_length: Hop length
        onset_env: Onset strength envelope
        chroma_cqt: Chroma features (12 x n_frames)
        beats_per_bar: Number of beats per bar

    Returns:
        Dict with downbeats, phase, phase_confidence
    """
    if beats_per_bar < 2:
        beats_per_bar = 4
    if len(beat_frames) < beats_per_bar * 2:
        return {"downbeats": [], "phase": 0, "phase_confidence": 0.0}

    bf = np.clip(beat_frames.astype(int), 0, len(onset_env) - 1)
    onset = np.asarray(onset_env[bf], dtype=np.float32)

    # Harmonic change proxy: cosine distance between consecutive beat chroma vectors
    idx = np.clip(bf, 0, chroma_cqt.shape[1] - 1)
    C = np.asarray(chroma_cqt[:, idx], dtype=np.float32)  # 12 x nbeats
    norms = np.linalg.norm(C, axis=0) + 1e-9
    Cn = C / norms

    harm_change = np.zeros(Cn.shape[1], dtype=np.float32)
    if Cn.shape[1] > 1:
        harm_change[1:] = 1.0 - np.sum(Cn[:, 1:] * Cn[:, :-1], axis=0)

    score = 0.7 * normalize_to_0_1(onset) + 0.3 * normalize_to_0_1(harm_change)

    phase_scores = [float(score[p::beats_per_bar].sum()) for p in range(beats_per_bar)]
    best_phase = int(np.argmax(phase_scores))

    sorted_scores = sorted(phase_scores, reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] > 0.1:
        # Confidence = margin between best and second-best, normalized
        phase_conf = float((sorted_scores[0] - sorted_scores[1]) / sorted_scores[0])
        phase_conf = np.clip(phase_conf, 0.0, 1.0)
    else:
        phase_conf = 0.0

    downbeat_idxs = np.arange(best_phase, len(beat_frames), beats_per_bar)
    downbeats = []
    for bi in downbeat_idxs:
        t = float(frames_to_time(np.array([beat_frames[bi]]), sr=sr, hop_length=hop_length)[0])
        downbeats.append({"beat_index": int(bi), "time_s": t, "confidence": float(phase_conf)})

    return {"downbeats": downbeats, "phase": best_phase, "phase_confidence": float(phase_conf)}
