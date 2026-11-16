"""Beat and tempo detection."""

from __future__ import annotations

from itertools import pairwise
import math
from typing import Any

import librosa
import numpy as np

from twinklr.core.audio.utils import frames_to_time


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
_TRIPLE_METER_MARGIN = 0.10
# Fewest tracker beats (eight 4-beat cycles) on which the octave evidence is tested.
_OCTAVE_MIN_BEATS = 32
# Fewest winning bars for downbeat evidence to decide (eight bars, as above): a handful
# of outsized chord changes, such as section changes, cannot place the bar alone.
_MIN_EVIDENCE_GROUPS = 8
# Smallest harmonic-component chroma change (1 - cosine) counted as a chord change. Two
# triads sharing two notes differ by 1/3; in the MIR fixtures the click-driven chroma
# flicker of the harmonic component stays below 0.05 while section changes reach ~0.97.
_MIN_CHORD_CHANGE = 0.05


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

    Known and accepted: half-time-feel material at a fast nominal tempo (trap, drum and
    bass, half-time choruses) is reported at the felt half tempo; a slow song the tracker
    reads at double time below the prior (55 BPM read as 110) is not halved.

    Args:
        tempo_bpm: Tempo from ``compute_beats``
        beat_frames: Beat frames from ``compute_beats``
        onset_env: Onset strength envelope
        chroma_cqt: Chroma of the harmonic (HPSS) component (12 x n_frames); full-mix
            chroma lets drum timbre pass for chord changes
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
    which this subtraction removes. The result is 4/4 unless the triple evidence (the
    better of 3/4 and 6/8) both beats the duple evidence (the better of 2/4 and 4/4) by
    ``_TRIPLE_METER_MARGIN`` and exceeds ``_TRIPLE_METER_MARGIN`` itself. Duple evidence
    is reported as 4/4 because accents alone do not separate 2/4 from 4/4; a weakly
    accented 3/4 can also read as 4/4 (known and accepted).

    ``confidence`` is 1 minus the permutation p-value of the deciding grouping: the share
    of shuffled-beat arrangements whose best-phase score the observed score exceeds.
    Without a real accent pattern it is spread evenly over 0 to 1, so values below 0.95
    mean "not distinguishable from chance"; 0.95 or more is a significant bar accent.

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
        return {"time_signature": "4/4", "confidence": 0.0, "method": "default"}

    z = _zscore(strengths)
    shuffled = _shuffles(z, _NULL_SHUFFLES)
    excess: dict[int, float] = {}
    beaten: dict[int, float] = {}
    for n in (2, 3, 4, 6):
        if len(z) < n * 3:
            excess[n], beaten[n] = 0.0, 0.0
            continue
        observed = _best_phase_grouping(z, n)
        null = np.array([_best_phase_grouping(s, n) for s in shuffled])
        excess[n] = observed - float(null.mean())
        beaten[n] = 1.0 - (1.0 + float(np.sum(null >= observed))) / (1.0 + len(null))

    duple_n = 4 if excess[4] >= excess[2] else 2
    triple_n = 3 if excess[3] >= excess[6] else 6
    if (
        excess[triple_n] > excess[duple_n] + _TRIPLE_METER_MARGIN
        and excess[triple_n] > _TRIPLE_METER_MARGIN
    ):
        signature, deciding = ("3/4" if triple_n == 3 else "6/8"), triple_n
    else:
        signature, deciding = "4/4", duple_n
    best = excess[deciding]

    return {
        "time_signature": signature,
        "confidence": round(beaten[deciding], 3),
        "method": "accent_pattern" if best > _TRIPLE_METER_MARGIN else "default",
        "all_scores": {
            label: round(excess[n], 3)
            for label, n in (("2/4", 2), ("3/4", 3), ("4/4", 4), ("6/8", 6))
        },
    }


def _group_wins(values: np.ndarray, n: int, floor: float = 0.0) -> np.ndarray:
    """Per phase, the n-beat groups (from beat 0) where it is the strict maximum >= floor."""
    k = len(values) // n
    groups = values[: k * n].reshape(k, n)
    top = groups.max(axis=1, keepdims=True)
    counted = (np.sum(groups == top, axis=1) == 1) & (top[:, 0] >= floor)
    return np.bincount(groups.argmax(axis=1)[counted], minlength=n)


def _phase_wins_test(values: np.ndarray, n: int, floor: float = 0.0) -> tuple[int, float, bool]:
    """Phase that most often holds the group maximum, as (phase, 1 - p, decisive).

    p is the permutation p-value of its win count against shuffled beats. Decisive
    needs p < 0.05 and at least ``_MIN_EVIDENCE_GROUPS`` wins.
    """
    wins = _group_wins(values, n, floor)
    phase = int(np.argmax(wins))
    null = np.array([_group_wins(s, n, floor).max() for s in _shuffles(values, 2 * _NULL_SHUFFLES)])
    p_value = (1.0 + float(np.sum(null >= wins[phase]))) / (1.0 + len(null))
    decisive = p_value < 0.05 and int(wins[phase]) >= _MIN_EVIDENCE_GROUPS
    return phase, 1.0 - p_value, decisive


def _pair_test(
    values: np.ndarray, n: int, a: int, b: int, floor: float = 0.0
) -> tuple[int, float, bool]:
    """Which of bar phases a and b is larger in more bars, as (phase, 1 - p, decisive).

    p is the exact two-sided sign-test p-value over bars where the two differ and the
    larger reaches ``floor``. Decisive needs p < 0.05 and at least
    ``_MIN_EVIDENCE_GROUPS`` wins.
    """
    count = min(len(values[a::n]), len(values[b::n]))
    first, second = values[a::n][:count], values[b::n][:count]
    counted = np.maximum(first, second) >= floor
    a_wins = int(np.sum((first > second) & counted))
    b_wins = int(np.sum((second > first) & counted))
    decided, top = a_wins + b_wins, max(a_wins, b_wins)
    tail = sum(math.comb(decided, i) for i in range(top, decided + 1)) / 2.0**decided
    p_value = min(1.0, 2.0 * tail) if decided else 1.0
    winner = a if a_wins >= b_wins else b
    return winner, 1.0 - p_value, p_value < 0.05 and top >= _MIN_EVIDENCE_GROUPS


def _downbeat_phase(onset: np.ndarray, change: np.ndarray, n: int) -> tuple[int, float, str]:
    """Bar phase from chord changes first, onset accents second (see the caller)."""
    if n % 2 == 0:
        half = n // 2
        parity, parity_conf, parity_ok = _phase_wins_test(change, half, _MIN_CHORD_CHANGE)
        if parity_ok:
            first, second = parity, parity + half
            phase, pair_conf, pair_ok = _pair_test(change, n, first, second, _MIN_CHORD_CHANGE)
            if pair_ok:
                return phase, min(parity_conf, pair_conf), "harmonic_change"
            phase, pair_conf, _ = _pair_test(onset, n, first, second)
            return phase, min(parity_conf, pair_conf), "harmonic_change+onset"
    phase, conf, decisive = _phase_wins_test(change, n, _MIN_CHORD_CHANGE)
    if decisive:
        return phase, conf, "harmonic_change"
    phase, conf, decisive = _phase_wins_test(onset, n)
    if decisive:
        return phase, conf, "onset_accent"
    _, phase = _phase_contrast(_zscore(onset), n)
    return phase, 0.0, "fallback"


def detect_downbeats_phase_aligned(
    *,
    beat_frames: np.ndarray,
    sr: int,
    hop_length: int,
    onset_env: np.ndarray,
    chroma_cqt: np.ndarray,
    beats_per_bar: int,
) -> dict[str, Any]:
    """Detect downbeats by choosing a global bar phase.

    Chord changes mark bar starts more reliably than loudness: in backbeat music the
    snare on 2 and 4 is the loudest beat. Evidence is counted per bar (which phase holds
    the bar's largest value), so a few outsized events cannot decide alone.

    1. Even bars: if one half-bar phase holds the largest chord change in significantly
       many half-bars, the downbeat is that phase or the one half a bar later. Chord
       change chooses between the two when it differs significantly; otherwise the
       onset accent breaks the beat-1 / beat-3 tie (method ``harmonic_change+onset``).
    2. Otherwise the bar phase holding the largest chord change, if significant.
    3. Otherwise the bar phase holding the largest onset accent, if significant.
    4. Otherwise the phase with the highest mean onset (method ``fallback``).

    "Significant" is p < 0.05 with at least eight winning bars; a chord change counts
    only from ``_MIN_CHORD_CHANGE``.
    ``phase_confidence`` is 1 minus the largest p-value among the tests that decided
    the phase (0.95 or more: every deciding test significant), and 0.0 for the fallback.
    Known and accepted: when chords change equally on beats 1 and 3, kick loudness
    decides between them; and the confidence assumes the beat grid is right, so when
    the tracker's tempo is wrong the placement can be confidently wrong.

    Args:
        beat_frames: Beat frame indices
        sr: Sample rate
        hop_length: Hop length
        onset_env: Onset strength envelope
        chroma_cqt: Chroma of the harmonic (HPSS) component (12 x n_frames)
        beats_per_bar: Number of beats per bar

    Returns:
        Dict with downbeats, phase, phase_confidence, method
    """
    if beats_per_bar < 2:
        beats_per_bar = 4
    if len(beat_frames) < beats_per_bar * 2:
        return {"downbeats": [], "phase": 0, "phase_confidence": 0.0, "method": "default"}

    beat_frames = np.asarray(beat_frames, dtype=int)
    onset = _beat_strengths(onset_env, beat_frames)
    change = _harmonic_change(chroma_cqt, beat_frames)
    best_phase, phase_conf, method = _downbeat_phase(onset, change, beats_per_bar)
    phase_conf = round(float(phase_conf), 3)

    downbeat_idxs = np.arange(best_phase, len(beat_frames), beats_per_bar)
    downbeats = []
    for bi in downbeat_idxs:
        t = float(frames_to_time(np.array([beat_frames[bi]]), sr=sr, hop_length=hop_length)[0])
        downbeats.append({"beat_index": int(bi), "time_s": t, "confidence": phase_conf})

    return {
        "downbeats": downbeats,
        "phase": best_phase,
        "phase_confidence": phase_conf,
        "method": method,
    }
