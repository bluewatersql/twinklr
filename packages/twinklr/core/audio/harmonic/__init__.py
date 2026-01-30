"""Harmonic analysis module."""

from twinklr.core.audio.harmonic.chords import detect_chords
from twinklr.core.audio.harmonic.hpss import compute_hpss, compute_onset_env
from twinklr.core.audio.harmonic.key import detect_musical_key, extract_chroma
from twinklr.core.audio.harmonic.pitch import extract_pitch_tracking

__all__ = [
    "compute_hpss",
    "compute_onset_env",
    "detect_musical_key",
    "extract_chroma",
    "extract_pitch_tracking",
    "detect_chords",
]
