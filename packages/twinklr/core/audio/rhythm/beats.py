"""Beat and tempo detection."""

from __future__ import annotations

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


def detect_time_signature(
    *,
    beat_frames: np.ndarray,
    onset_env: np.ndarray,
) -> dict[str, Any]:
    """Detect time signature using accent pattern analysis.

    New approach: Score how well beats group into n-beat patterns with strong first beat.

    Args:
        beat_frames: Beat frame indices
        onset_env: Onset strength envelope

    Returns:
        Dict with time_signature, confidence, method, all_scores
    """
    if len(beat_frames) < 8:
        return {"time_signature": "4/4", "confidence": 0.0, "method": "default"}

    bf = np.clip(beat_frames.astype(int), 0, len(onset_env) - 1)
    strengths = np.asarray(onset_env[bf], dtype=np.float32)

    if strengths.size < 12:
        return {"time_signature": "4/4", "confidence": 0.3, "method": "default"}

    # Normalize strengths
    strengths_norm = (strengths - strengths.mean()) / (strengths.std() + 1e-9)

    def score_grouping(n: int) -> float:
        """Score how well beats group into n-beat patterns with strong first beat."""
        if len(strengths_norm) < n * 3:
            return 0.0
        n_groups = len(strengths_norm) // n
        if n_groups < 2:
            return 0.0
        grouped = strengths_norm[: n_groups * n].reshape(n_groups, n)
        # First beat should be strongest in each group
        first_beat_is_max = (grouped.argmax(axis=1) == 0).astype(float)
        # Also consider: first beat above average
        first_beat_above_avg = (grouped[:, 0] > grouped.mean(axis=1)).astype(float)
        return float(0.6 * np.mean(first_beat_is_max) + 0.4 * np.mean(first_beat_above_avg))

    # Also compute autocorrelation as secondary signal
    x = strengths_norm
    ac = np.correlate(x, x, mode="full")[len(x) - 1 :]
    if ac.size > 0 and float(ac[0]) > 1e-9:
        ac = ac / ac[0]
    else:
        ac = np.zeros_like(x)

    def ac_at(i: int) -> float:
        return float(ac[i]) if i < len(ac) else 0.0

    # Combine both methods
    scores = {
        "2/4": 0.7 * score_grouping(2) + 0.3 * ac_at(2),
        "3/4": 0.7 * score_grouping(3) + 0.3 * ac_at(3),
        "4/4": 0.7 * score_grouping(4) + 0.3 * ac_at(4),
        "6/8": 0.7 * score_grouping(6) + 0.3 * ac_at(6),
    }

    best_sig, best_val = max(scores.items(), key=lambda kv: kv[1])

    # 4/4 is overwhelmingly common, so bias toward it slightly
    if scores["4/4"] > 0.4 and best_val - scores["4/4"] < 0.15:
        best_sig = "4/4"
        best_val = scores["4/4"]

    if best_val > 0.25:
        return {
            "time_signature": best_sig,
            "confidence": float(np.clip(best_val, 0, 1)),
            "method": "accent_pattern",
            "all_scores": {k: round(v, 3) for k, v in scores.items()},
        }
    return {
        "time_signature": "4/4",
        "confidence": float(np.clip(best_val, 0, 1)),
        "method": "default",
        "all_scores": {k: round(v, 3) for k, v in scores.items()},
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


def detect_tempo_changes(y: np.ndarray, sr: int, *, hop_length: int) -> dict[str, Any]:
    """Detect tempo variations throughout the song.

    Args:
        y: Audio time series
        sr: Sample rate
        hop_length: Hop length

    Returns:
        Dict with tempo_curve, tempo_changes, statistics
    """
    window_size_s = 10.0
    window_samples = int(window_size_s * sr)
    hop_samples = int(window_samples / 2)

    # Early exit for short audio
    if len(y) < window_samples:
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
            return {
                "tempo_curve": [{"time_s": 0.0, "tempo_bpm": float(tempo)}],
                "tempo_changes": [],
                "average_tempo_bpm": float(tempo),
                "tempo_std": 0.0,
                "is_stable": True,
            }
        except Exception:
            return {
                "tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}],
                "tempo_changes": [],
                "average_tempo_bpm": 120.0,
                "tempo_std": 0.0,
                "is_stable": True,
            }

    tempos = []
    times = []

    for i in range(0, len(y) - window_samples + 1, hop_samples):
        y_win = y[i : i + window_samples]
        try:
            tempo, _ = librosa.beat.beat_track(y=y_win, sr=sr, hop_length=hop_length)
            tempos.append(float(tempo))
            times.append(float(i / sr))
        except Exception:
            pass

    if not tempos:
        return {
            "tempo_curve": [{"time_s": 0.0, "tempo_bpm": 120.0}],
            "tempo_changes": [],
            "average_tempo_bpm": 120.0,
            "tempo_std": 0.0,
            "is_stable": True,
        }

    tempo_arr = np.array(tempos, dtype=np.float32)
    avg_tempo = float(np.mean(tempo_arr))
    tempo_std = float(np.std(tempo_arr))

    # Detect significant tempo changes
    threshold = max(5.0, tempo_std)
    changes = []
    for i in range(1, len(tempos)):
        if abs(tempos[i] - tempos[i - 1]) > threshold:
            changes.append(
                {
                    "time_s": times[i],
                    "from_bpm": tempos[i - 1],
                    "to_bpm": tempos[i],
                    "change_bpm": tempos[i] - tempos[i - 1],
                }
            )

    is_stable = tempo_std < 5.0

    return {
        "tempo_curve": [
            {"time_s": t, "tempo_bpm": bpm} for t, bpm in zip(times, tempos, strict=False)
        ],
        "tempo_changes": changes,
        "average_tempo_bpm": avg_tempo,
        "tempo_std": tempo_std,
        "is_stable": is_stable,
    }
