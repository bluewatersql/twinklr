"""Structure analysis module."""

from twinklr.core.audio.structure.models import SectioningPreset
from twinklr.core.audio.structure.presets import (
    PRESETS,
    get_preset,
    get_preset_or_default,
)
from twinklr.core.audio.structure.sections import (
    detect_song_sections,
    label_section,
    merge_short_sections,
)

__all__ = [
    # Presets
    "PRESETS",
    # Models
    "SectioningPreset",
    "detect_song_sections",
    "get_preset",
    "get_preset_or_default",
    "label_section",
    "merge_short_sections",
]
