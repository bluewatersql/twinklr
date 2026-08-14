"""Regenerates `tone.wav`, the synthetic audio input for this evaluation run.

Deterministic and offline: a click track (quarter notes at 120bpm) plus a steady
220Hz tone, long enough for `AudioAnalyzer`'s local tempo/structure DSP to run
against. Not committed as a binary — run this to reproduce it.

Usage:
    uv run python evaluations/2026-08-13-golden-fixture-mh4-minimal/generate_audio.py
"""

from __future__ import annotations

from pathlib import Path
import wave

import numpy as np


def write_synthetic_tone(path: Path, *, duration_s: float = 64.0, sample_rate: int = 22050) -> None:
    t = np.arange(int(sample_rate * duration_s)) / sample_rate
    beat_period = 0.5  # 120 BPM quarter notes
    click = (np.mod(t, beat_period) < 0.03).astype(np.float64)
    envelope = np.exp(-np.mod(t, beat_period) * 40)
    percussion = click * envelope
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    signal = 0.6 * percussion + tone
    signal = signal / np.max(np.abs(signal))
    pcm = (signal * 32767 * 0.8).astype(np.int16)

    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = Path(__file__).parent / "tone.wav"
    write_synthetic_tone(out)
    print(f"wrote {out}")
