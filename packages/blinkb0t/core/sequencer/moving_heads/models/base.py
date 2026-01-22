from enum import Enum


class Intensity(str, Enum):
    """Movement intensity levels.

    Maps intensity names to amplitude values.
    Higher intensity = larger motion amplitude.

    Attributes:
        SLOW: Minimal motion (0.08 amplitude).
        SMOOTH: Gentle motion (0.15 amplitude).
        FAST: Moderate motion (0.25 amplitude).
        DRAMATIC: Large motion (0.4 amplitude).
    """

    SLOW = "SLOW"
    SMOOTH = "SMOOTH"
    FAST = "FAST"
    DRAMATIC = "DRAMATIC"

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
        }
        return amplitudes[self]


class PanPose(str, Enum):
    """Standard pan pose positions.

    Defines normalized pan positions across the horizontal range.
    Values are ordered from left (0.0) to right (1.0).

    Attributes:
        WIDE_LEFT: Far left position (0.1).
        LEFT: Left position (0.3).
        CENTER: Center position (0.5).
        RIGHT: Right position (0.7).
        WIDE_RIGHT: Far right position (0.9).
    """

    WIDE_LEFT = "WIDE_LEFT"
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"
    WIDE_RIGHT = "WIDE_RIGHT"

    @property
    def norm_value(self) -> float:
        """Get normalized value for this pose."""
        values = {
            PanPose.WIDE_LEFT: 0.1,
            PanPose.LEFT: 0.3,
            PanPose.CENTER: 0.5,
            PanPose.RIGHT: 0.7,
            PanPose.WIDE_RIGHT: 0.9,
        }
        return values[self]


class TiltPose(str, Enum):
    """Standard tilt pose positions.

    Defines normalized tilt positions across the vertical range.
    Values are ordered from up/sky (high) to down/stage (low).

    Attributes:
        SKY: Pointing up (0.9).
        HORIZON: Level/horizontal (0.5).
        CROWD: Aimed at audience (0.3).
        STAGE: Pointing down at stage (0.1).
    """

    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"

    @property
    def norm_value(self) -> float:
        """Get normalized value for this pose."""
        values = {
            TiltPose.SKY: 0.9,
            TiltPose.HORIZON: 0.5,
            TiltPose.CROWD: 0.3,
            TiltPose.STAGE: 0.1,
        }
        return values[self]
