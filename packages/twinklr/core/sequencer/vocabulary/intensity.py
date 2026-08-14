"""Intensity vocabulary for categorical planning.

Provides categorical intensity levels that the LLM can select from,
eliminating numeric precision issues. The renderer resolves these
to lane-appropriate numeric values.
"""

from enum import StrEnum


class IntensityLevel(StrEnum):
    """Categorical intensity level for planning.

    LLM selects intent; renderer maps to lane-appropriate numeric values.

    Hierarchy guarantee: At every level, BASE < RHYTHM < ACCENT.

    Examples:
        - WHISPER: Barely visible, ambient glow
        - SOFT: Gentle background, supporting role
        - MED: Balanced presence, default choice
        - STRONG: Prominent, attention-drawing
        - PEAK: Maximum impact, focal moments only
    """

    WHISPER = "WHISPER"  # Barely visible, ambient
    SOFT = "SOFT"  # Gentle background
    MED = "MED"  # Balanced presence (default)
    STRONG = "STRONG"  # Prominent, attention-drawing
    PEAK = "PEAK"  # Maximum impact, focal moments


__all__ = ["IntensityLevel"]
