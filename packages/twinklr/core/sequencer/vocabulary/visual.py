"""Visual enums - visual style vocabulary.

Defines visual intents, color modes, projection, and warp hints.
"""

from enum import Enum


class GroupVisualIntent(str, Enum):
    """Visual intent classification for templates.

    Describes the visual character and style of the template output.

    Attributes:
        ABSTRACT: Non-representational patterns and shapes.
        IMAGERY: Recognizable visual content (scenes, objects).
        HYBRID: Mix of abstract and imagery elements.
        TEXTURE: Textural patterns (dots, lines, grains).
        GEOMETRIC: Geometric shapes and patterns.
        ORGANIC: Natural, flowing patterns.
    """

    ABSTRACT = "ABSTRACT"
    IMAGERY = "IMAGERY"
    HYBRID = "HYBRID"
    TEXTURE = "TEXTURE"
    GEOMETRIC = "GEOMETRIC"
    ORGANIC = "ORGANIC"


class VisualDepth(str, Enum):
    """Visual depth layer in composition.

    Defines the depth/ordering role of a layer in the final composite.

    Attributes:
        BACKGROUND: Farthest back layer (base/foundation).
        MIDGROUND: Middle layer (supporting elements).
        FOREGROUND: Front layer (primary focus).
        ACCENT: Accent layer (punctuation, highlights).
        TEXTURE: Texture overlay layer.
    """

    BACKGROUND = "BACKGROUND"
    MIDGROUND = "MIDGROUND"
    FOREGROUND = "FOREGROUND"
    ACCENT = "ACCENT"
    TEXTURE = "TEXTURE"


class ColorMode(str, Enum):
    """Color strategy for templates.

    Defines the color palette approach for template output.

    Attributes:
        MONOCHROME: Single color (variations in intensity).
        DICHROME: Two colors (complementary or related).
        TRIAD: Three colors (triad relationship).
        ANALOGOUS: Adjacent colors on color wheel.
        FULL_SPECTRUM: Full color spectrum usage.
    """

    MONOCHROME = "MONOCHROME"
    DICHROME = "DICHROME"
    TRIAD = "TRIAD"
    ANALOGOUS = "ANALOGOUS"
    FULL_SPECTRUM = "FULL_SPECTRUM"


class PaletteRole(str, Enum):
    """Palette role for templates.

    Defines the role of a palette in the template output.

    Attributes:
        PRIMARY: Default base palette for the song/section.
        ACCENT: Highlight/hits/sparkle.
        WARM: Warm bias variant.
        COOL: Cool bias variant.
        NEUTRAL: Whites/silvers/greys or desaturated.
    """

    PRIMARY = "PRIMARY"
    ACCENT = "ACCENT"
    WARM = "WARM"
    COOL = "COOL"
    NEUTRAL = "NEUTRAL"


class ProjectionIntent(str, Enum):
    """Projection mapping intent for templates.

    Describes how visual content maps onto physical display geometry.

    Attributes:
        FLAT: Flat 2D mapping (matrices, flat walls).
        POLAR: Polar coordinate mapping (mega-trees, cones).
        PERSPECTIVE: Perspective projection mapping.
        CYLINDRICAL: Cylindrical surface mapping.
        SPHERICAL: Spherical surface mapping.
    """

    FLAT = "FLAT"
    POLAR = "POLAR"
    PERSPECTIVE = "PERSPECTIVE"
    CYLINDRICAL = "CYLINDRICAL"
    SPHERICAL = "SPHERICAL"


class WarpHint(str, Enum):
    """Projection warp hints for templates.

    Provides hints about special projection requirements.

    Attributes:
        SEAM_SAFE: Content designed to tile seamlessly.
        RADIAL_SYMMETRY: Radially symmetric content.
        TILE_X: Tileable horizontally.
        TILE_Y: Tileable vertically.
        TILE_XY: Tileable in both dimensions.
    """

    SEAM_SAFE = "SEAM_SAFE"
    RADIAL_SYMMETRY = "RADIAL_SYMMETRY"
    TILE_X = "TILE_X"
    TILE_Y = "TILE_Y"
    TILE_XY = "TILE_XY"
