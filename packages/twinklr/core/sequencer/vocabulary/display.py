"""Display vocabulary — physical metadata enums for display groups.

Categorical descriptors that tell the LLM what a display group
physically is, how it is arranged, and how visually prominent it is.
These enable informed choreography decisions without requiring the
planner to guess from role names alone.
"""

from enum import Enum


class DisplayElementKind(str, Enum):
    """Physical type of display element.

    Tells the planner what kind of thing this group represents so it
    can select appropriate effects and coordination patterns.

    Attributes:
        ARCH: Arch element (pixel arch, wire arch).
        TREE: Tree (mega tree, mini tree, spiral tree).
        MATRIX: LED matrix / panel.
        STRING: Standard string lights (eaves, outlines, rooflines).
        WINDOW: Window frame / window grid.
        STAR: Star element.
        SNOWFLAKE: Snowflake element.
        SPINNER: Spinning / rotating element.
        PROP: Generic decorative prop (Santa, reindeer, nativity).
        CANDY_CANE: Candy cane element.
        WREATH: Wreath element.
        ICICLE: Icicle / drip lights.
        FLOOD: Flood / wash lights.
        PIXEL_STICK: Pixel stick / bullet node.
        MOVING_HEAD: DMX moving head fixture.
        MIXED: Group containing heterogeneous model types.
    """

    ARCH = "ARCH"
    TREE = "TREE"
    MATRIX = "MATRIX"
    STRING = "STRING"
    WINDOW = "WINDOW"
    STAR = "STAR"
    SNOWFLAKE = "SNOWFLAKE"
    SPINNER = "SPINNER"
    PROP = "PROP"
    CANDY_CANE = "CANDY_CANE"
    WREATH = "WREATH"
    ICICLE = "ICICLE"
    FLOOD = "FLOOD"
    PIXEL_STICK = "PIXEL_STICK"
    MOVING_HEAD = "MOVING_HEAD"
    MIXED = "MIXED"


class GroupArrangement(str, Enum):
    """Physical arrangement of models within a group.

    Determines which spatial coordination patterns make sense.  For
    example, ``HORIZONTAL_ROW`` supports L2R / R2L sweeps, while
    ``SINGLE`` does not benefit from sequenced coordination.

    Attributes:
        HORIZONTAL_ROW: Models spread left-to-right (e.g., arches across yard).
        VERTICAL_COLUMN: Models stacked top-to-bottom (e.g., pixel sticks on a pole).
        DEPTH_SEQUENCE: Models arranged front-to-back (e.g., layered yard elements).
        GRID: Models in a 2-D array (e.g., window matrix).
        CLUSTER: Models grouped together with no clear axis.
        SINGLE: Single model (e.g., mega tree, standalone prop).
    """

    HORIZONTAL_ROW = "HORIZONTAL_ROW"
    VERTICAL_COLUMN = "VERTICAL_COLUMN"
    DEPTH_SEQUENCE = "DEPTH_SEQUENCE"
    GRID = "GRID"
    CLUSTER = "CLUSTER"
    SINGLE = "SINGLE"


class PixelDensity(str, Enum):
    """Pixel density category.

    Determines which effects look good on the element.  High-density
    elements (matrices, dense trees) can render detailed imagery;
    low-density elements (candy canes, simple strings) only suit
    simple on/off or chase patterns.

    Attributes:
        LOW: Sparse props, simple strings, candy canes.
        MEDIUM: Standard string lights, arches.
        HIGH: Matrices, dense trees, pixel sticks.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DisplayProminence(str, Enum):
    """Visual weight / prominence in the overall display.

    Guides the planner on how to allocate visual budget.  ``HERO``
    elements deserve peak-intensity accent moments; ``ACCENT``
    elements should stay subtle.

    Attributes:
        ACCENT: Small decorative element (stars, snowflakes).
        SUPPORTING: Secondary visual element (candy canes, icicles).
        ANCHOR: Primary visual element (outlines, arches).
        HERO: Showpiece / centerpiece (mega tree, large matrix).
    """

    ACCENT = "ACCENT"
    SUPPORTING = "SUPPORTING"
    ANCHOR = "ANCHOR"
    HERO = "HERO"


__all__ = [
    "DisplayElementKind",
    "DisplayProminence",
    "GroupArrangement",
    "PixelDensity",
]
