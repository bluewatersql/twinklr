"""Enums for group template system.

Group templates define high-level cross-group coordination patterns
for Christmas light displays.
"""

from enum import Enum


class GroupTemplateType(str, Enum):
    """Template type by lane.

    Defines which lane a template belongs to in the choreography system.

    Attributes:
        BASE: Foundation layer (calm, continuous background).
        RHYTHM: Beat-driven motion layer.
        ACCENT: Focal punctuation layer (hits, accents).
        TRANSITION: Section transition templates.
        SPECIAL: Signature moments (chorus, drop, bridge).
    """

    BASE = "BASE"
    RHYTHM = "RHYTHM"
    ACCENT = "ACCENT"
    TRANSITION = "TRANSITION"
    SPECIAL = "SPECIAL"


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


class MotionVerb(str, Enum):
    """Motion primitives for choreography.

    Describes the type of motion applied to display elements.
    Suitable for Christmas light displays (residential/commercial).

    Attributes:
        NONE: No motion (static).
        PULSE: Rhythmic brightness change.
        SWEEP: Linear motion across display.
        WAVE: Smooth wave-like motion.
        RIPPLE: Expanding wave propagation.
        CHASE: Sequential activation pattern.
        STROBE: Rapid on/off (safe rates <8Hz).
        BOUNCE: Back-and-forth motion.
        SPARKLE: Random twinkling elements.
        FADE: Gradual brightness transition.
        WIPE: Progressive reveal/conceal.
        TWINKLE: Slow random brightness variation.
        SHIMMER: Subtle brightness oscillation.
        ROLL: Continuous rotation.
        FLIP: 180-degree position change.
    """

    NONE = "NONE"
    PULSE = "PULSE"
    SWEEP = "SWEEP"
    WAVE = "WAVE"
    RIPPLE = "RIPPLE"
    CHASE = "CHASE"
    STROBE = "STROBE"
    BOUNCE = "BOUNCE"
    SPARKLE = "SPARKLE"
    FADE = "FADE"
    WIPE = "WIPE"
    TWINKLE = "TWINKLE"
    SHIMMER = "SHIMMER"
    ROLL = "ROLL"
    FLIP = "FLIP"


class LayerRole(str, Enum):
    """Layer role in visual composition.

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


class AssetSlotType(str, Enum):
    """Asset slot types for template requirements.

    Defines the type of visual asset required by a template.

    Attributes:
        PNG_OPAQUE: Opaque PNG image (backgrounds).
        PNG_TRANSPARENT: Transparent PNG (cutouts, icons).
        PNG_TILE: Seamless tileable PNG texture.
        GIF_OVERLAY: Animated GIF overlay.
    """

    PNG_OPAQUE = "PNG_OPAQUE"
    PNG_TRANSPARENT = "PNG_TRANSPARENT"
    PNG_TILE = "PNG_TILE"
    GIF_OVERLAY = "GIF_OVERLAY"


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
