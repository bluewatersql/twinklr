from enum import Enum


class TimingMode(str, Enum):
    """Timing reference mode."""

    MUSICAL = "musical"  # Bars/beats (tempo-aware)
    ABSOLUTE_MS = "absolute_ms"  # Milliseconds (fixed)


class QuantizeMode(str, Enum):
    """Beat quantization options for timing alignment."""

    NONE = "none"  # No quantization (use exact timing)
    ANY_BEAT = "any_beat"  # Snap to nearest beat
    DOWNBEAT = "downbeat"  # Snap to bar boundaries (downbeats only)
    HALF_BAR = "half_bar"  # Snap to half-bar positions
    QUARTER_BAR = "quarter_bar"  # Snap to quarter-bar positions
    EIGHTH_BAR = "eighth_bar"  # Snap to eighth-bar positions
    SIXTEENTH_BAR = "sixteenth_bar"  # Snap to sixteenth-bar positions


class TransitionMode(str, Enum):
    SNAP = "snap"
    CROSSFADE = "crossfade"


class BlendMode(str, Enum):
    OVERRIDE = "override"
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"


class TemplateCategory(str, Enum):
    LOW_ENERGY = "low_energy"
    MEDIUM_ENERGY = "medium_energy"
    HIGH_ENERGY = "high_energy"


class SemanticGroupType(str, Enum):
    ALL = "ALL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INNER = "INNER"
    OUTER = "OUTER"
    ODD = "ODD"
    EVEN = "EVEN"


class ChaseOrder(str, Enum):
    """Order for phase offset spreading.

    Defines the order in which fixtures in a group receive phase offsets
    when creating chase effects.

    Attributes:
        LEFT_TO_RIGHT: Start from left-most fixture.
        RIGHT_TO_LEFT: Start from right-most fixture.
        OUTSIDE_IN: Start from outer fixtures, move inward.
        INSIDE_OUT: Start from center fixtures, move outward.
    """

    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    RIGHT_TO_LEFT = "RIGHT_TO_LEFT"
    OUTSIDE_IN = "OUTSIDE_IN"
    INSIDE_OUT = "INSIDE_OUT"
    ODD_EVEN = "ODD_EVEN"


class TemplateRole(str, Enum):
    OUTER_LEFT = "OUTER_LEFT"
    INNER_LEFT = "INNER_LEFT"
    INNER_RIGHT = "INNER_RIGHT"
    OUTER_RIGHT = "OUTER_RIGHT"
    FAR_LEFT = "FAR_LEFT"
    FAR_RIGHT = "FAR_RIGHT"
    MID_LEFT = "MID_LEFT"
    MID_RIGHT = "MID_RIGHT"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER_RIGHT = "CENTER_RIGHT"
    CENTER = "CENTER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class AimZone(str, Enum):
    """Predefined aim targets.

    Defines standard aim zones for geometry handlers to position fixtures.

    Attributes:
        SKY: Aim upward (typically tilt up).
        HORIZON: Aim level (parallel to ground).
        CROWD: Aim toward audience area.
        STAGE: Aim toward stage/performance area.
    """

    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"


class Intensity(str, Enum):
    """Movement intensity levels.

    Maps intensity names to amplitude values.
    Higher intensity = larger motion amplitude.

    Attributes:
        SLOW: Minimal motion (0.08 amplitude).
        SMOOTH: Gentle motion (0.15 amplitude).
        FAST: Moderate motion (0.25 amplitude).
        DRAMATIC: Large motion (0.4 amplitude).
        INTENSE: Maximum motion (0.5 amplitude).
    """

    SLOW = "SLOW"
    SMOOTH = "SMOOTH"
    FAST = "FAST"
    DRAMATIC = "DRAMATIC"
    INTENSE = "INTENSE"

    @property
    def amplitude(self) -> float:
        """Get normalized amplitude for this intensity.

        Returns amplitude as fraction of full range.
        For pan/tilt, this represents half the total swing.
        """
        amplitudes = {
            Intensity.SLOW: 0.08,
            Intensity.SMOOTH: 0.15,
            Intensity.FAST: 0.25,
            Intensity.DRAMATIC: 0.4,
            Intensity.INTENSE: 0.5,
        }
        return amplitudes[self]


class ChannelName(str, Enum):
    """DMX channel names for moving head fixtures.

    These represent the primary controllable channels on a moving head fixture.

    Attributes:
        PAN: Horizontal rotation/position channel.
        TILT: Vertical rotation/position channel.
        DIMMER: Brightness/intensity channel.

    Example:
        >>> channel = ChannelName.PAN
        >>> channel.value
        'PAN'
    """

    PAN = "pan"
    TILT = "tilt"
    DIMMER = "dimmer"
    SHUTTER = "shutter"
    COLOR = "color"
    GOBO = "gobo"
