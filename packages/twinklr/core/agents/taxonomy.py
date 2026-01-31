"""Taxonomy - Enums and controlled vocabularies for agent system.

This module defines all enums used across the Twinklr agent system.
Strict enums prevent conceptual drift and ensure consistency.
"""

from enum import Enum

# Core Layer & Composition Enums


class LayerRole(str, Enum):
    """Layer role in choreography composition."""

    BASE = "BASE"  # Foundation layer, mostly continuous
    RHYTHM = "RHYTHM"  # Beat-driven, rhythmic accents
    ACCENT = "ACCENT"  # Sparse, high-impact moments (PRIMARY)
    HIGHLIGHT = "HIGHLIGHT"  # Alias for ACCENT
    FILL = "FILL"  # Fill layer for density
    TEXTURE = "TEXTURE"  # Texture/detail layer
    CUSTOM = "CUSTOM"  # User-defined layer


class BlendMode(str, Enum):
    """Layer blending strategy."""

    NORMAL = "NORMAL"  # Replace (new layer overwrites)
    ADD = "ADD"  # Additive blending (lights combine)
    MASK = "MASK"  # Mask/subtract (blocks/dims)


class TimingDriver(str, Enum):
    """Musical timing that drives layer choreography."""

    BEATS = "BEATS"  # Quarter notes
    DOWNBEATS = "DOWNBEATS"  # First beat of each bar
    BARS = "BARS"  # Full bars (4/4 = 4 beats)
    PHRASES = "PHRASES"  # Musical phrases (typically 8-16 bars)
    PEAKS = "PEAKS"  # Energy peaks detected by analysis
    LYRICS = "LYRICS"  # Lyric/vocal timing


# Planning & Strategy Enums


class MotionDensity(str, Enum):
    """Overall activity level in a section."""

    SPARSE = "SPARSE"  # Minimal activity, spacious
    MED = "MED"  # Moderate activity
    BUSY = "BUSY"  # High activity, dense choreography


class EnergyTarget(str, Enum):
    """Target energy level for a section."""

    LOW = "LOW"  # Subdued, ambient
    MED = "MED"  # Moderate energy
    HIGH = "HIGH"  # High energy, driving
    BUILD = "BUILD"  # Rising energy
    RELEASE = "RELEASE"  # Falling energy
    PEAK = "PEAK"  # Maximum energy moment


class ChoreographyStyle(str, Enum):
    """Visual approach for choreography."""

    IMAGERY = "IMAGERY"  # Picture/gif-based, representational
    ABSTRACT = "ABSTRACT"  # Pure light patterns, non-representational
    HYBRID = "HYBRID"  # Mix of imagery and abstract


# Display Target Enums


class TargetRole(str, Enum):
    """Abstract roles for residential display props."""

    # Primary architectural elements
    OUTLINE = "OUTLINE"  # House/roofline outline
    MEGA_TREE = "MEGA_TREE"  # Central hero element
    HERO = "HERO"  # Featured prop (star, spinner, etc.)

    # Secondary elements
    ARCHES = "ARCHES"  # Archway elements
    TREES = "TREES"  # Yard trees
    PROPS = "PROPS"  # Generic props
    FLOODS = "FLOODS"  # Floodlights/wash lights
    ACCENTS = "ACCENTS"  # Small accent props
    WINDOWS = "WINDOWS"  # Window lighting

    # Matrix/display elements
    MATRIX = "MATRIX"  # LED matrix for imagery

    # Moving lights
    MOVING_HEADS = "MOVING_HEADS"  # Moving head fixtures
