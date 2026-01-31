"""Structure analysis module."""

from twinklr.core.audio.structure.models import (
    Section,
    SectionDiagnostics,
    SectioningPreset,
    SectionLabel,
)
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
    "detect_song_sections",
    "merge_short_sections",
    "label_section",
    # Models
    "Section",
    "SectionDiagnostics",
    "SectioningPreset",
    "SectionLabel",
    # Presets
    "PRESETS",
    "get_preset",
    "get_preset_or_default",
]
