"""Target enums - display target vocabulary.

Defines abstract roles for residential display props.
"""

from enum import Enum


class TargetRole(str, Enum):
    """Abstract roles for residential display props.

    Defines logical groupings of display elements.

    Attributes:
        OUTLINE: House/roofline outline.
        MEGA_TREE: Central hero element.
        HERO: Featured prop (star, spinner, etc.).
        ARCHES: Archway elements.
        TREES: Yard trees.
        PROPS: Generic props.
        FLOODS: Floodlights/wash lights.
        ACCENTS: Small accent props.
        WINDOWS: Window lighting.
        MATRIX: LED matrix for imagery.
        MOVING_HEADS: Moving head fixtures.
    """

    OUTLINE = "OUTLINE"
    MEGA_TREE = "MEGA_TREE"
    HERO = "HERO"
    ARCHES = "ARCHES"
    TREES = "TREES"
    PROPS = "PROPS"
    FLOODS = "FLOODS"
    ACCENTS = "ACCENTS"
    WINDOWS = "WINDOWS"
    MATRIX = "MATRIX"
    MOVING_HEADS = "MOVING_HEADS"
