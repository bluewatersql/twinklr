"""Harmonic analysis module."""

from blinkb0t.core.domains.audio.harmonic.chords import detect_chords
from blinkb0t.core.domains.audio.harmonic.hpss import compute_hpss, compute_onset_env
from blinkb0t.core.domains.audio.harmonic.key import detect_musical_key, extract_chroma
from blinkb0t.core.domains.audio.harmonic.pitch import extract_pitch_tracking

__all__ = [
    "compute_hpss",
    "compute_onset_env",
    "detect_musical_key",
    "extract_chroma",
    "extract_pitch_tracking",
    "detect_chords",
]
