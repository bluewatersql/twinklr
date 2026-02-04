"""Theming enums - tag and theme scope vocabulary.

Enums specific to the theming domain.
"""

from enum import Enum


class TagCategory(str, Enum):
    """Category classification for tags.

    Used for organizing and filtering tags in catalogs.

    Attributes:
        MOTIF: Visual motif tags (e.g., "gingerbread_house", "snowflake").
        STYLE: Style tags (e.g., "flat_vector", "high_contrast").
        SETTING: Setting/scene tags (e.g., "winter", "night").
        CONSTRAINT: Constraint tags (e.g., "no_text", "seam_safe").
    """

    MOTIF = "motif"
    STYLE = "style"
    SETTING = "setting"
    CONSTRAINT = "constraint"


class ThemeScope(str, Enum):
    """Scope of theme application.

    Defines how broadly a theme should be applied.

    Attributes:
        SONG: Theme applies to entire song.
        SECTION: Theme applies to a section.
        PLACEMENT: Theme applies to a single placement.
    """

    SONG = "song"
    SECTION = "section"
    PLACEMENT = "placement"
