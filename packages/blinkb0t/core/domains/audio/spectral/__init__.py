"""Spectral analysis module."""

from blinkb0t.core.domains.audio.spectral.bands import extract_dynamic_features
from blinkb0t.core.domains.audio.spectral.basic import extract_spectral_features
from blinkb0t.core.domains.audio.spectral.vocals import detect_vocals

__all__ = ["extract_spectral_features", "extract_dynamic_features", "detect_vocals"]
