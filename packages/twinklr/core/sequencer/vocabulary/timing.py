"""Timing enums - timing and quantization vocabulary.

Defines timing drivers, time reference kinds, and quantization modes.
"""

from enum import Enum


class TimingDriver(str, Enum):
    """Musical timing that drives layer choreography.

    Defines which musical element drives the timing.

    Attributes:
        BEATS: Quarter notes.
        DOWNBEATS: First beat of each bar.
        BARS: Full bars (4/4 = 4 beats).
        PHRASES: Musical phrases (typically 8-16 bars).
        PEAKS: Energy peaks detected by analysis.
        LYRICS: Lyric/vocal timing.
    """

    BEATS = "BEATS"
    DOWNBEATS = "DOWNBEATS"
    BARS = "BARS"
    PHRASES = "PHRASES"
    PEAKS = "PEAKS"
    LYRICS = "LYRICS"


class GPTimingDriver(str, Enum):
    """Timing driver for GroupPlanner lanes.

    Simplified timing drivers for group planning.

    Attributes:
        BEATS: Beat-driven timing.
        BARS: Bar-driven timing.
        PHRASES: Phrase-driven timing.
        LYRICS: Lyric-driven timing.
    """

    BEATS = "BEATS"
    BARS = "BARS"
    PHRASES = "PHRASES"
    LYRICS = "LYRICS"


class TimeRefKind(str, Enum):
    """Kind of time reference.

    Defines the type of time reference.

    Attributes:
        BAR_BEAT: Bar/beat/beat_frac based timing.
        MS: Absolute milliseconds timing.
    """

    BAR_BEAT = "BAR_BEAT"
    MS = "MS"


class SnapMode(str, Enum):
    """Snap behavior for time alignment.

    Defines how times snap to boundaries.

    Attributes:
        NONE: No snapping.
        START: Snap start to boundary.
        END: Snap end to boundary.
        BOTH: Snap both ends.
        STRETCH: Stretch to fill boundaries.
    """

    NONE = "none"
    START = "start"
    END = "end"
    BOTH = "both"
    STRETCH = "stretch"


class QuantizeMode(str, Enum):
    """Quantization modes for time alignment.

    Defines the granularity of time quantization.

    Attributes:
        NONE: No quantization.
        BARS: Quantize to bar boundaries.
        BEATS: Quantize to beat boundaries.
        EIGHTHS: Quantize to eighth note boundaries.
        SIXTEENTHS: Quantize to sixteenth note boundaries.
    """

    NONE = "none"
    BARS = "bars"
    BEATS = "beats"
    EIGHTHS = "eighths"
    SIXTEENTHS = "sixteenths"
