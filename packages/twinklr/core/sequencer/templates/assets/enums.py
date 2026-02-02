"""Enums for asset template system.

Asset templates define prompt-driven PNG/GIF generation specifications
for visual content used in group choreography.
"""

from enum import Enum


class AssetTemplateType(str, Enum):
    """Asset template type classification.

    Defines the output format and usage for asset generation.

    Attributes:
        PNG_OPAQUE: Opaque PNG for backgrounds/plates.
        PNG_TRANSPARENT: Transparent PNG for cutouts/overlays.
        PNG_TILE: Seamless tileable PNG texture.
        GIF_OVERLAY: Animated GIF for motion overlays.
    """

    PNG_OPAQUE = "PNG_OPAQUE"
    PNG_TRANSPARENT = "PNG_TRANSPARENT"
    PNG_TILE = "PNG_TILE"
    GIF_OVERLAY = "GIF_OVERLAY"


class BackgroundMode(str, Enum):
    """Background mode for asset generation.

    Defines whether the asset has a transparent or opaque background.

    Attributes:
        TRANSPARENT: Transparent background (alpha channel).
        OPAQUE: Opaque background (solid color).
    """

    TRANSPARENT = "transparent"
    OPAQUE = "opaque"


class MatrixAspect(str, Enum):
    """Asset aspect ratio for matrix displays.

    Defines the width:height ratio for generated assets.

    Attributes:
        SQUARE: 1:1 aspect ratio.
        WIDE: 2:1 aspect ratio (landscape).
        TALL: 1:2 aspect ratio (portrait).
        HD: 16:9 aspect ratio (widescreen).
        STANDARD: 4:3 aspect ratio.
    """

    SQUARE = "1:1"
    WIDE = "2:1"
    TALL = "1:2"
    HD = "16:9"
    STANDARD = "4:3"


class TemplateProjectionHint(str, Enum):
    """Projection hint for asset templates.

    Suggests the intended projection mapping for the asset.

    Attributes:
        FLAT: Flat 2D projection (matrices, walls).
        POLAR_CONE: Polar projection for conical displays (mega-trees).
        POLAR_CYLINDER: Polar projection for cylindrical displays.
    """

    FLAT = "FLAT"
    POLAR_CONE = "POLAR_CONE"
    POLAR_CYLINDER = "POLAR_CYLINDER"
