"""Genre-specific presets for section detection.

These presets are tuned for different musical genres and control how the
section detection algorithm behaves. Start with these defaults and tune
based on your corpus.
"""

from __future__ import annotations

from twinklr.core.audio.structure.models import SectioningPreset

ALIASES = {
    # Common spellings / separators
    "rap": "hiphop",
    "hip-hop": "hiphop",
    "hip hop": "hiphop",
    "alt_rock": "rock",
    "alt rock": "rock",
    "alternative": "rock",
    "metalcore": "metal",
    # Christmas variants
    "xmas": "christmas_modern",
    "xmas_classic": "christmas_classic",
    "xmas_modern": "christmas_modern",
    "holiday": "christmas_classic",
    # Defaults
    "unknown": "default",
    "other": "default",
}

PRESETS: dict[str, SectioningPreset] = {
    "edm": SectioningPreset(
        genre="edm",
        min_sections=10,
        max_sections=16,
        min_len_beats=24,  # prevents 4–8s fragments at 140–170bpm
        novelty_L_beats=16,  # macro structure
        peak_delta=0.08,  # slightly less sensitive (baseline already adds coverage)
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.9,
            "builds_weight": 0.7,
            "vocals_weight": 0.25,
            "chords_weight": 0.2,
        },
    ),
    "pop": SectioningPreset(
        genre="pop",
        min_sections=8,
        max_sections=14,
        min_len_beats=20,  # ~6–10s at typical pop tempi
        novelty_L_beats=12,
        peak_delta=0.075,  # reduce micro peaks; hybrid baseline handles regularity
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.5,
            "builds_weight": 0.6,
            "vocals_weight": 0.75,
            "chords_weight": 0.4,
        },
    ),
    "country": SectioningPreset(
        genre="country",
        min_sections=7,
        max_sections=12,
        min_len_beats=24,  # longer sections; narrative; avoids “micro instrumental”
        novelty_L_beats=14,  # slightly more macro than pop
        peak_delta=0.085,  # LESS sensitive now (baseline already gives you structure)
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.2,
            "builds_weight": 0.4,
            "vocals_weight": 0.85,
            "chords_weight": 0.65,
        },
    ),
    "christmas_classic": SectioningPreset(
        genre="christmas_classic",
        min_sections=8,
        max_sections=14,
        min_len_beats=20,
        novelty_L_beats=14,
        peak_delta=0.08,
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.15,
            "builds_weight": 0.3,
            "vocals_weight": 0.75,
            "chords_weight": 0.75,
        },
    ),
    "christmas_modern": SectioningPreset(
        genre="christmas_modern",
        min_sections=8,
        max_sections=14,
        min_len_beats=20,
        novelty_L_beats=12,
        peak_delta=0.075,
        pre_avg=10,
        post_avg=10,
        context_weights={
            "drops_weight": 0.55,
            "builds_weight": 0.55,
            "vocals_weight": 0.75,
            "chords_weight": 0.5,
        },
    ),
    "rock": SectioningPreset(
        genre="rock",
        min_sections=8,
        max_sections=14,
        min_len_beats=22,
        novelty_L_beats=14,
        peak_delta=0.08,
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.35,
            "builds_weight": 0.45,
            "vocals_weight": 0.65,
            "chords_weight": 0.55,
        },
    ),
    "hiphop": SectioningPreset(
        genre="hiphop",
        min_sections=6,
        max_sections=12,
        min_len_beats=24,
        novelty_L_beats=14,
        peak_delta=0.09,  # less sensitive (repetition + subtle changes)
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.25,
            "builds_weight": 0.35,
            "vocals_weight": 0.85,  # lyrical structure
            "chords_weight": 0.35,
        },
    ),
    "metal": SectioningPreset(
        genre="metal",
        min_sections=8,
        max_sections=14,
        min_len_beats=28,  # prevents 4–6s fragments at high bpm
        novelty_L_beats=16,
        peak_delta=0.09,
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.30,
            "builds_weight": 0.55,
            "vocals_weight": 0.55,
            "chords_weight": 0.45,
        },
    ),
    "ballad": SectioningPreset(
        genre="ballad",
        min_sections=6,
        max_sections=10,
        min_len_beats=20,  # tempo often slower; beats->seconds longer anyway
        novelty_L_beats=16,  # macro structure
        peak_delta=0.095,  # avoid over-seg on subtle timbre shifts
        pre_avg=14,
        post_avg=14,
        context_weights={
            "drops_weight": 0.15,
            "builds_weight": 0.35,
            "vocals_weight": 0.90,
            "chords_weight": 0.70,
        },
    ),
    "instrumental": SectioningPreset(
        genre="instrumental",
        min_sections=7,
        max_sections=12,
        min_len_beats=22,
        novelty_L_beats=16,
        peak_delta=0.085,
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.35,
            "builds_weight": 0.50,
            "vocals_weight": 0.05,
            "chords_weight": 0.75,  # harmony/texture drives structure
        },
    ),
    "default": SectioningPreset(
        genre="default",
        min_sections=8,
        max_sections=14,
        min_len_beats=22,
        novelty_L_beats=14,
        peak_delta=0.085,
        pre_avg=12,
        post_avg=12,
        context_weights={
            "drops_weight": 0.40,
            "builds_weight": 0.45,
            "vocals_weight": 0.60,
            "chords_weight": 0.50,
        },
    ),
}

# Genre aliases are now merged into the original ALIASES dict above


def _normalize_genre_key(genre: str) -> str:
    g = genre.strip().lower()
    g = g.replace("/", "_").replace("-", "_")
    g = "_".join(g.split())  # spaces -> underscores
    return g


def get_preset(genre: str) -> SectioningPreset:
    """Get preset for a specific genre (with alias normalization)."""
    key = _normalize_genre_key(genre)

    # alias resolution (also normalize alias targets)
    key = ALIASES.get(key, key)
    key = _normalize_genre_key(key)

    if key not in PRESETS:
        raise KeyError(
            f"Unknown genre '{genre}' (normalized='{key}'). Available: {', '.join(PRESETS.keys())}"
        )

    return PRESETS[key]


def get_preset_or_default(genre: str | None, default: str = "default") -> SectioningPreset:
    if genre is None:
        return PRESETS[default]

    try:
        return get_preset(genre)
    except KeyError:
        return PRESETS[default]
