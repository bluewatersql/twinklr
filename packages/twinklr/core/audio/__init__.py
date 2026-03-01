"""Audio analysis domain."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from twinklr.core.audio.analyzer import AudioAnalyzer

__all__ = [
    "AudioAnalyzer",
]


def __getattr__(name: str) -> object:
    if name == "AudioAnalyzer":
        from twinklr.core.audio.analyzer import AudioAnalyzer

        return AudioAnalyzer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
