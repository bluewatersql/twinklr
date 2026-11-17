from enum import StrEnum


class TimingMode(StrEnum):
    """Timing reference mode."""

    MUSICAL = "musical"  # Bars/beats (tempo-aware)
    ABSOLUTE_MS = "absolute_ms"  # Milliseconds (fixed)


class QuantizeMode(StrEnum):
    """Beat quantization options for timing alignment."""

    NONE = "none"  # No quantization (use exact timing)
    ANY_BEAT = "any_beat"  # Snap to nearest beat
    DOWNBEAT = "downbeat"  # Snap to bar boundaries (downbeats only)
    HALF_BAR = "half_bar"  # Snap to half-bar positions
    QUARTER_BAR = "quarter_bar"  # Snap to quarter-bar positions
    EIGHTH_BAR = "eighth_bar"  # Snap to eighth-bar positions
    SIXTEENTH_BAR = "sixteenth_bar"  # Snap to sixteenth-bar positions


class TransitionMode(StrEnum):
    """Transition mode between segments."""

    SNAP = "snap"  # Instant change (no blend)
    CROSSFADE = "crossfade"  # Overlapping fade out/in
    MORPH = "morph"  # Smooth morphing (Bezier curves)
    FADE_VIA_BLACK = "fade_via_black"  # Fade to black, change, fade up
    SWEEP = "sweep"  # Sweeping motion (advanced)
    BLACKOUT = "blackout"  # Cut to or from dark at the boundary


class TemplateCategory(StrEnum):
    LOW_ENERGY = "low_energy"
    MEDIUM_ENERGY = "medium_energy"
    HIGH_ENERGY = "high_energy"


class SemanticGroupType(StrEnum):
    ALL = "ALL"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INNER = "INNER"
    OUTER = "OUTER"
    ODD = "ODD"
    EVEN = "EVEN"


class TemplateRole(StrEnum):
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


class Intensity(StrEnum):
    """Movement intensity levels.

    This is the single moving-head planner/renderer intensity vocabulary. Numeric
    movement and dimmer parameters remain owned by the renderer's parameter tables.
    """

    SLOW = "SLOW"
    SMOOTH = "SMOOTH"
    FAST = "FAST"
    DRAMATIC = "DRAMATIC"
    INTENSE = "INTENSE"


class ChannelName(StrEnum):
    """DMX channel names for moving head fixtures.

    These represent the primary controllable channels on a moving head fixture.

    Attributes:
        PAN: Horizontal rotation/position channel.
        TILT: Vertical rotation/position channel.
        DIMMER: Brightness/intensity channel.
        ZOOM: Beam angle, for a profile that declares a zoom axis.

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
    ZOOM = "zoom"
