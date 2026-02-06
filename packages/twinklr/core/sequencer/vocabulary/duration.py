"""Duration vocabulary for categorical planning.

Provides categorical effect durations that the LLM can select from,
eliminating start+end calculation issues. The renderer resolves these
to exact beat counts based on context.
"""

from enum import Enum


class EffectDuration(str, Enum):
    """Categorical effect duration for planning.

    LLM selects duration intent; renderer calculates exact end time
    using BeatGrid and section bounds.

    Examples:
        - HIT: Quick accent, ping (1-2 beats)
        - BURST: Short emphasis (1 bar / 4 beats)
        - PHRASE: Musical phrase (2-4 bars)
        - EXTENDED: Longer passage (4-8 bars)
        - SECTION: Full section duration
    """

    HIT = "HIT"  # 1-2 beats - quick accent, ping
    BURST = "BURST"  # 1 bar (4 beats) - short emphasis
    PHRASE = "PHRASE"  # 2-4 bars - musical phrase
    EXTENDED = "EXTENDED"  # 4-8 bars - longer passage
    SECTION = "SECTION"  # Full section duration


# Duration mapping: (min_beats, max_beats)
# None means "use section bounds"
DURATION_BEATS: dict[EffectDuration, tuple[int | None, int | None]] = {
    EffectDuration.HIT: (1, 2),
    EffectDuration.BURST: (4, 4),  # Exactly 1 bar
    EffectDuration.PHRASE: (8, 16),  # 2-4 bars
    EffectDuration.EXTENDED: (16, 32),  # 4-8 bars
    EffectDuration.SECTION: (None, None),  # Special: uses section bounds
}


def resolve_duration_beats(duration: EffectDuration) -> tuple[int | None, int | None]:
    """Get the beat range for a duration category.

    Args:
        duration: Categorical duration

    Returns:
        Tuple of (min_beats, max_beats), or (None, None) for SECTION
    """
    return DURATION_BEATS[duration]


__all__ = [
    "EffectDuration",
    "DURATION_BEATS",
    "resolve_duration_beats",
]
