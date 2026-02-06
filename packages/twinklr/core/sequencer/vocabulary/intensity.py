"""Intensity vocabulary for categorical planning.

Provides categorical intensity levels that the LLM can select from,
eliminating numeric precision issues. The renderer resolves these
to lane-appropriate numeric values.
"""

from enum import Enum


class IntensityLevel(str, Enum):
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


# Intensity mapping: level -> lane -> numeric value
# Guarantees BASE < RHYTHM < ACCENT at every intensity level
INTENSITY_MAP: dict[IntensityLevel, dict[str, float]] = {
    IntensityLevel.WHISPER: {"BASE": 0.15, "RHYTHM": 0.25, "ACCENT": 0.35},
    IntensityLevel.SOFT: {"BASE": 0.35, "RHYTHM": 0.50, "ACCENT": 0.65},
    IntensityLevel.MED: {"BASE": 0.55, "RHYTHM": 0.75, "ACCENT": 0.90},
    IntensityLevel.STRONG: {"BASE": 0.75, "RHYTHM": 0.95, "ACCENT": 1.10},
    IntensityLevel.PEAK: {"BASE": 0.90, "RHYTHM": 1.10, "ACCENT": 1.30},
}


def resolve_intensity(level: IntensityLevel, lane: str) -> float:
    """Resolve categorical intensity to numeric value.

    Args:
        level: Categorical intensity level
        lane: Lane name (BASE, RHYTHM, ACCENT)

    Returns:
        Numeric intensity value appropriate for the lane

    Raises:
        KeyError: If lane is not recognized
    """
    return INTENSITY_MAP[level][lane]


__all__ = [
    "IntensityLevel",
    "INTENSITY_MAP",
    "resolve_intensity",
]
