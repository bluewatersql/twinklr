"""Genre-specific presets for section detection.

These presets are tuned for different musical genres and control how the
section detection algorithm behaves. Start with these defaults and tune
based on your corpus.
"""

from __future__ import annotations

from twinklr.core.audio.structure.models import SectioningPreset

# Default presets for common genres
PRESETS: dict[str, SectioningPreset] = {
    "edm": SectioningPreset(
        genre="edm",
        min_sections=12,
        max_sections=18,
        min_len_beats=16,  # Longer sections (drops are extended)
        novelty_L_beats=16,  # Larger kernel for macro structure
        peak_delta=0.07,  # Moderate sensitivity
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.8,  # Drops are critical for EDM
            "builds_weight": 0.6,
            "vocals_weight": 0.3,  # Less important (often instrumental)
            "chords_weight": 0.2,
        },
    ),
    "pop": SectioningPreset(
        genre="pop",
        min_sections=14,
        max_sections=20,
        min_len_beats=12,  # Standard pop sections
        novelty_L_beats=12,
        peak_delta=0.06,  # Balanced sensitivity
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.5,
            "builds_weight": 0.5,
            "vocals_weight": 0.7,  # Vocals define structure in pop
            "chords_weight": 0.4,
        },
    ),
    "country": SectioningPreset(
        genre="country",
        min_sections=12,
        max_sections=18,
        min_len_beats=12,
        novelty_L_beats=12,
        peak_delta=0.05,  # More sensitive (subtle structure changes)
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.3,  # Less pronounced drops
            "builds_weight": 0.4,
            "vocals_weight": 0.8,  # Vocals and story-driven
            "chords_weight": 0.6,  # Harmonic structure important
        },
    ),
    "christmas_classic": SectioningPreset(
        genre="christmas_classic",
        min_sections=12,
        max_sections=18,
        min_len_beats=10,  # Shorter sections (verse-heavy)
        novelty_L_beats=12,
        peak_delta=0.045,  # More sensitive (subtle changes)
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.2,  # Rare in classic Christmas
            "builds_weight": 0.3,
            "vocals_weight": 0.7,
            "chords_weight": 0.7,  # Strong harmonic structure
        },
    ),
    "christmas_modern": SectioningPreset(
        genre="christmas_modern",
        min_sections=14,
        max_sections=20,
        min_len_beats=12,
        novelty_L_beats=12,
        peak_delta=0.06,  # Similar to pop
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.6,  # Modern Christmas can have drops
            "builds_weight": 0.5,
            "vocals_weight": 0.7,
            "chords_weight": 0.5,
        },
    ),
}


def get_preset(genre: str) -> SectioningPreset:
    """Get preset for a specific genre.

    Args:
        genre: Genre name (edm, pop, country, christmas_classic, christmas_modern)

    Returns:
        SectioningPreset for the genre

    Raises:
        KeyError: If genre not found

    Examples:
        >>> preset = get_preset("edm")
        >>> preset.min_sections
        12
    """
    if genre not in PRESETS:
        raise KeyError(
            f"Unknown genre '{genre}'. Available: {', '.join(PRESETS.keys())}"
        )
    return PRESETS[genre]


def get_preset_or_default(genre: str | None, default: str = "pop") -> SectioningPreset:
    """Get preset for genre, or default if genre is None or unknown.

    Args:
        genre: Genre name, or None
        default: Default genre to use if genre is None or unknown

    Returns:
        SectioningPreset

    Examples:
        >>> preset = get_preset_or_default(None)
        >>> preset.genre
        'pop'
        >>> preset = get_preset_or_default("unknown_genre", default="edm")
        >>> preset.genre
        'edm'
    """
    if genre is None:
        return PRESETS[default]

    try:
        return get_preset(genre)
    except KeyError:
        return PRESETS[default]
