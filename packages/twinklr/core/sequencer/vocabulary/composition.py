"""Composition enums - layer and blending vocabulary.

Defines layer roles, lanes, and blending modes for choreography composition.
"""

from enum import Enum


class LaneKind(str, Enum):
    """Lane (track) types for choreography.

    Defines the three primary lanes in group planning.

    Attributes:
        BASE: Bed/background continuity layer.
        RHYTHM: Beat-driven motion/texture layer.
        ACCENT: Focal punctuation, hits, callouts.
    """

    BASE = "BASE"
    RHYTHM = "RHYTHM"
    ACCENT = "ACCENT"


class LayerRole(str, Enum):
    """Layer role in choreography composition.

    Used by macro planner to define layer hierarchy.

    Attributes:
        BASE: Foundation layer, mostly continuous.
        RHYTHM: Beat-driven, rhythmic accents.
        ACCENT: Sparse, high-impact moments (PRIMARY).
        HIGHLIGHT: Alias for ACCENT.
        FILL: Fill layer for density.
        TEXTURE: Texture/detail layer.
        CUSTOM: User-defined layer.
    """

    BASE = "BASE"
    RHYTHM = "RHYTHM"
    ACCENT = "ACCENT"
    HIGHLIGHT = "HIGHLIGHT"
    FILL = "FILL"
    TEXTURE = "TEXTURE"
    CUSTOM = "CUSTOM"


class BlendMode(str, Enum):
    """Layer blending strategy.

    Defines how layers combine in composition.

    Attributes:
        NORMAL: Replace (new layer overwrites).
        ADD: Additive blending (lights combine).
        MASK: Mask/subtract (blocks/dims).
    """

    NORMAL = "NORMAL"
    ADD = "ADD"
    MASK = "MASK"


class GPBlendMode(str, Enum):
    """Blend mode for GroupPlanner lanes.

    More granular blend modes for group planning.

    Attributes:
        ADD: Additive blending.
        MAX: Maximum value wins.
        ALPHA_OVER: Alpha compositing (over).
    """

    ADD = "add"
    MAX = "max"
    ALPHA_OVER = "alpha_over"
