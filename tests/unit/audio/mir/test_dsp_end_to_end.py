"""DSP rhythm on short synthesized drum-and-chord audio, through the full source path."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from twinklr.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from twinklr.core.audio.harmonic.key import extract_chroma
from twinklr.core.audio.mir.metrics import event_f1
from twinklr.core.audio.mir.sources import DSPSource, MIRInput, RhythmAnalysis

SR = 22050
HOP = 512
_TRIADS = [(0, 4, 7), (5, 9, 0), (7, 11, 2), (9, 0, 4)]  # C F G Am


def _kick(amp: float) -> np.ndarray:
    t = np.arange(int(0.25 * SR)) / SR
    freq = 50 + 100 * np.exp(-t * 30)
    return amp * np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 14)


def _snare(amp: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(int(0.18 * SR)) / SR
    noise = 0.7 * rng.standard_normal(len(t)) * np.exp(-t * 25)
    return amp * (noise + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30))


def _hat(amp: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(int(0.05 * SR)) / SR
    return amp * 0.35 * np.diff(rng.standard_normal(len(t)), prepend=0) * np.exp(-t * 80)


def _chord(pitch_classes: tuple[int, ...], duration_s: float, amp: float) -> np.ndarray:
    t = np.arange(int(duration_s * SR)) / SR
    out = np.zeros_like(t)
    for pitch_class in pitch_classes:
        for octave, weight in ((3, 0.6), (4, 1.0), (5, 0.4)):
            freq = 440.0 * 2 ** ((pitch_class - 9) / 12 + (octave - 4))
            out += weight * (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t))
    return amp * out * np.minimum(1.0, t / 0.02) * np.exp(-t * 0.6) / 6.0


def _add(signal: np.ndarray, event: np.ndarray, start: int) -> None:
    count = min(len(event), len(signal) - start)
    if count > 0:
        signal[start : start + count] += event[:count]


def _render(
    *,
    bpm: float,
    eighth_pattern: dict[str, list[tuple[int, float]]],
    chord_amp: float,
    seconds: float,
) -> tuple[np.ndarray, list[float]]:
    """4/4 bars of eighth-note drum hits; a new chord on every bar. Returns audio, bar starts."""
    rng = np.random.default_rng(0)
    audio = np.zeros(int(seconds * SR))
    beat_s = 60.0 / bpm
    bar_starts: list[float] = []
    bar = 0
    while (bar + 1) * 4 * beat_s < seconds:
        bar_start = 0.25 + bar * 4 * beat_s
        bar_starts.append(bar_start)
        _add(audio, _chord(_TRIADS[bar % 4], 4 * beat_s + 0.05, chord_amp), int(bar_start * SR))
        for name, hits in eighth_pattern.items():
            for position, amp in hits:
                start = int((bar_start + position * beat_s / 2) * SR)
                level = max(0.0, amp * (1 + rng.normal(0, 0.08)))
                if name == "kick":
                    _add(audio, _kick(level), start)
                elif name == "snare":
                    _add(audio, _snare(level, rng), start)
                else:
                    _add(audio, _hat(level, rng), start)
        bar += 1
    return audio.astype(np.float32), bar_starts


def _analyze(audio: np.ndarray) -> RhythmAnalysis:
    hpss = compute_hpss(audio)
    inputs = MIRInput(
        audio_path=Path("synth.wav"),
        audio=audio,
        sample_rate=SR,
        hop_length=HOP,
        onset_envelope=compute_onset_env(hpss.percussive, SR, HOP),
        chroma=extract_chroma(audio, SR, hop_length=HOP),
        harmonic_audio=hpss.harmonic,
    )
    return DSPSource().analyze_rhythm(inputs)


_EIGHTH_HATS = [(position, 0.6) for position in range(8)]


@pytest.mark.parametrize("chord_amp", [1.0, 0.3], ids=["loud_chords", "quiet_chords"])
def test_79_bpm_backbeat_resolves_to_slow_tactus_with_bars_on_the_chord(
    chord_amp: float,
) -> None:
    audio, bar_starts = _render(
        bpm=79.0,
        eighth_pattern={
            "kick": [(0, 1.0), (4, 0.9)],
            "snare": [(2, 1.0), (6, 1.0)],
            "hat": _EIGHTH_HATS,
        },
        chord_amp=chord_amp,
        seconds=40.0,
    )

    rhythm = _analyze(audio)

    assert rhythm.metadata["time_signature"]["tempo_octave"]["tracker_bpm"] > 150.0
    assert rhythm.tempo_bpm == pytest.approx(79.0, rel=0.04)
    assert rhythm.beats_per_bar == 4
    assert event_f1(bar_starts, rhythm.downbeats_s, tolerance_s=0.07).f1 >= 0.9
    assert rhythm.metadata["downbeat_meta"]["method"].startswith("harmonic_change")


@pytest.mark.parametrize("chord_amp", [1.0, 0.3], ids=["loud_chords", "quiet_chords"])
def test_160_bpm_rock_stays_fast(chord_amp: float) -> None:
    audio, bar_starts = _render(
        bpm=160.0,
        eighth_pattern={
            "kick": [(0, 1.0), (4, 1.0)],
            "snare": [(2, 1.0), (6, 1.0)],
            "hat": [(position, 0.4) for position in range(8)],
        },
        chord_amp=chord_amp,
        seconds=30.0,
    )

    rhythm = _analyze(audio)

    assert rhythm.tempo_bpm == pytest.approx(160.0, rel=0.04)
    assert rhythm.beats_per_bar == 4
    assert event_f1(bar_starts, rhythm.downbeats_s, tolerance_s=0.07).f1 >= 0.9
