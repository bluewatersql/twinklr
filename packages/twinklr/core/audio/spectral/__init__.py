"""Spectral analysis module."""

from twinklr.core.audio.spectral.bands import extract_dynamic_features
from twinklr.core.audio.spectral.basic import extract_spectral_features
from twinklr.core.audio.spectral.vocals import detect_vocals

__all__ = ["extract_spectral_features", "extract_dynamic_features", "detect_vocals"]
