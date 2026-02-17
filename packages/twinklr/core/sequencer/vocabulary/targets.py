"""Target enums - display target vocabulary.

Defines abstract roles for residential display props.
"""

from enum import Enum


class TargetRole(str, Enum):
    """Abstract roles for residential display props.

    Defines logical groupings of display elements by physical prop type.
    Choreographic intent (hero/accent weighting) is expressed via
    ``DisplayProminence``, not here.

    Attributes:
        ARCHES: Archway elements.
        CANDY_CANES: Candy cane elements.
        CIRCLES: Circle elements.
        CUBES: Cube elements.
        CUSTOM: Custom / generic elements (xLights "Custom" model type).
        FLOODS: Floodlights / wash lights.
        HERO: Featured prop (star, spinner, etc.).
        ICICLES: Icicle / drip lights.
        LINES: Line elements.
        MATRICES: LED matrices for imagery.
        MEGA_TREE: Central hero element.
        MOVING_HEADS: Moving head fixtures.
        OUTLINE: House / roofline outline.
        SNOWFLAKES: Snowflake elements.
        SPHERES: Sphere elements.
        SPINNERS: Spinning / rotating elements.
        STARS: Star elements.
        TREES: Yard trees.
        WINDOWS: Window lighting.
        WREATH: Wreath element.
    """

    ARCHES = "ARCHES"
    CANDY_CANES = "CANDY_CANES"
    CIRCLES = "CIRCLES"
    CUBES = "CUBES"
    CUSTOM = "CUSTOM"
    FLOODS = "FLOODS"
    HERO = "HERO"
    ICICLES = "ICICLES"
    LINES = "LINES"
    MATRICES = "MATRICES"
    MEGA_TREE = "MEGA_TREE"
    MOVING_HEADS = "MOVING_HEADS"
    OUTLINE = "OUTLINE"
    SNOWFLAKES = "SNOWFLAKES"
    SPHERES = "SPHERES"
    SPINNERS = "SPINNERS"
    STARS = "STARS"
    TREES = "TREES"
    WINDOWS = "WINDOWS"
    WREATH = "WREATH"
