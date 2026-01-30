"""Chord recognition from chroma features."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from twinklr.core.audio.utils import frames_to_time

logger = logging.getLogger(__name__)


def detect_chords(
    chroma_cqt: np.ndarray,
    beat_frames: np.ndarray,
    sr: int,
    hop_length: int,
) -> dict[str, Any]:
    """Detect chords at beat positions using chroma template matching.

    Args:
        chroma_cqt: Chroma CQT features (12 x n_frames)
        beat_frames: Beat positions in frames
        sr: Sample rate
        hop_length: Hop length in samples

    Returns:
        Dictionary with chords, chord changes, and statistics
    """
    # Chord templates (normalized chroma profiles)
    CHORD_TEMPLATES = {
        # Major triads (root, major 3rd, perfect 5th)
        "maj": np.array([1.0, 0, 0, 0, 1.0, 0, 0, 1.0, 0, 0, 0, 0], dtype=np.float32),
        # Minor triads (root, minor 3rd, perfect 5th)
        "min": np.array([1.0, 0, 0, 1.0, 0, 0, 0, 1.0, 0, 0, 0, 0], dtype=np.float32),
        # Dominant 7th (root, maj 3rd, perfect 5th, min 7th)
        "7": np.array([1.0, 0, 0, 0, 1.0, 0, 0, 1.0, 0, 0, 1.0, 0], dtype=np.float32),
        # Sus2 (root, maj 2nd, perfect 5th)
        "sus2": np.array([1.0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0], dtype=np.float32),
        # Sus4 (root, perfect 4th, perfect 5th)
        "sus4": np.array([1.0, 0, 0, 0, 0, 1.0, 0, 1.0, 0, 0, 0, 0], dtype=np.float32),
        # Diminished (root, min 3rd, dim 5th)
        "dim": np.array([1.0, 0, 0, 1.0, 0, 0, 1.0, 0, 0, 0, 0, 0], dtype=np.float32),
        # Augmented (root, maj 3rd, aug 5th)
        "aug": np.array([1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0, 0, 0, 0], dtype=np.float32),
    }

    NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    # Extract chroma at beat positions
    beat_frames_clipped = np.clip(beat_frames, 0, chroma_cqt.shape[1] - 1).astype(int)
    chroma_at_beats = chroma_cqt[:, beat_frames_clipped]  # 12 x n_beats

    chords = []
    for beat_idx in range(chroma_at_beats.shape[1]):
        chroma_vec = chroma_at_beats[:, beat_idx]

        # Normalize
        chroma_norm = chroma_vec / (np.linalg.norm(chroma_vec) + 1e-9)

        # Try all 12 transpositions for each template
        best_chord = "N"  # No chord
        best_quality = "N"
        best_score = 0.0

        for quality, template in CHORD_TEMPLATES.items():
            for root in range(12):
                template_rotated = np.roll(template, root)
                template_norm = template_rotated / (np.linalg.norm(template_rotated) + 1e-9)

                # Cosine similarity
                score = float(np.dot(chroma_norm, template_norm))

                if score > best_score:
                    best_score = score
                    best_chord = NOTE_NAMES[root]
                    best_quality = quality

        # Threshold for chord detection
        if best_score < 0.5:
            best_chord = "N"
            best_quality = "N"

        beat_time = float(
            frames_to_time(np.array([beat_frames[beat_idx]]), sr=sr, hop_length=hop_length)[0]
        )

        chords.append(
            {
                "beat_index": int(beat_idx),
                "time_s": beat_time,
                "chord": f"{best_chord}:{best_quality}" if best_chord != "N" else "N",
                "root": best_chord,
                "quality": best_quality,
                "confidence": round(best_score, 3),
            }
        )

    # Chord change detection
    chord_changes = []
    for i in range(1, len(chords)):
        if chords[i]["chord"] != chords[i - 1]["chord"]:
            chord_changes.append(
                {
                    "time_s": chords[i]["time_s"],
                    "from": chords[i - 1]["chord"],
                    "to": chords[i]["chord"],
                }
            )

    # Chord statistics
    chord_names = [c["chord"] for c in chords if c["chord"] != "N"]
    unique_chords = len(set(chord_names))
    major_count = sum(1 for c in chords if c["quality"] == "maj")
    minor_count = sum(1 for c in chords if c["quality"] == "min")

    return {
        "chords": chords,
        "chord_changes": chord_changes,
        "statistics": {
            "total_chords": len(chord_names),
            "unique_chords": unique_chords,
            "chord_change_count": len(chord_changes),
            "major_pct": float(major_count / len(chords)) if chords else 0.0,
            "minor_pct": float(minor_count / len(chords)) if chords else 0.0,
            "avg_chord_duration_s": (
                float(chords[-1]["time_s"]) / len(chord_changes)
                if chord_changes and chords and isinstance(chords[-1]["time_s"], (int, float))
                else 0.0
            ),
        },
    }
