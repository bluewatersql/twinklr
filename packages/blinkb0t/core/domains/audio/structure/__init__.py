"""Structure analysis module."""

from blinkb0t.core.domains.audio.structure.sections import (
    detect_song_sections,
    label_section,
    merge_short_sections,
)

__all__ = ["detect_song_sections", "merge_short_sections", "label_section"]
