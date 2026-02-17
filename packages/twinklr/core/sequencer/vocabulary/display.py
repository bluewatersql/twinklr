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
        CANDY_CANE: Candy cane element.
        CIRCLE: Circle element.
        CUBE: Cube element.
        CUSTOM: Custom element.
        DMX: Generic DMX fixture.
        FLOOD: Flood / wash lights.
        GROUP: Group containing heterogeneous model types.
        ICICLES: Icicle / drip lights (plural alias).
        MATRIX: LED matrix / panel.
        MOVING_HEAD: DMX moving head fixture.
        PIXEL_STICK: Pixel stick / bullet node.
        POLYLINE: Polyline element.
        SINGLE_LINE: Single line element.
        SNOWFLAKE: Snowflake element.
        SPHERE: Sphere element.
        SPINNER: Spinning / rotating element.
        STAR: Star element.
        STRING: Standard string lights (eaves, outlines, rooflines).
        TREE: Tree (mega tree, mini tree, spiral tree).
        WINDOW: Window frame / window grid.
        WINDOW_FRAME: Window frame element.
        WREATH: Wreath element.
    """

    ARCH = "ARCH"
    CANDY_CANE = "CANDY_CANE"
    CIRCLE = "CIRCLE"
    CUBE = "CUBE"
    CUSTOM = "CUSTOM"
    DMX = "DMX"
    FLOOD = "FLOOD"
    GROUP = "GROUP"
    ICICLES = "ICICLES"
    MATRIX = "MATRIX"
    MOVING_HEAD = "MOVING_HEAD"
    PIXEL_STICK = "PIXEL_STICK"
    POLYLINE = "POLYLINE"
    SINGLE_LINE = "SINGLE_LINE"
    SNOWFLAKE = "SNOWFLAKE"
    SPHERE = "SPHERE"
    SPINNER = "SPINNER"
    STAR = "STAR"
    STRING = "STRING"
    TREE = "TREE"
    WINDOW = "WINDOW"
    WINDOW_FRAME = "WINDOW_FRAME"
    WREATH = "WREATH"


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
