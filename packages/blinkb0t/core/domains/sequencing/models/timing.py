"""Universal musical timing models.

This module provides timing abstractions shared across all sequencing domains
(moving heads, RGB, lasers, etc.).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class MusicalTiming(BaseModel):
    """Universal musical timing specification.

    Defines timing in musical terms (bars/beats) that can be converted
    to absolute time (milliseconds) using audio-derived beat positions.

    This model is universal and can be used across all sequencing domains
    (moving heads, RGB, lasers, etc.).
    """

    model_config = ConfigDict(frozen=True)

    mode: TimingMode = TimingMode.MUSICAL

    # Musical timing (used when mode=MUSICAL)
    start_offset_bars: float = Field(
        default=0.0, ge=0.0, description="Start time in bars (0.0 = beginning of song)"
    )
    duration_bars: float = Field(
        default=1.0, gt=0.0, description="Duration in bars (1.0 = one bar)"
    )

    # Absolute timing (used when mode=ABSOLUTE_MS)
    start_offset_ms: int | None = Field(
        default=None, ge=0, description="Start time in milliseconds (when mode=ABSOLUTE_MS)"
    )
    duration_ms: int | None = Field(
        default=None, gt=0, description="Duration in milliseconds (when mode=ABSOLUTE_MS)"
    )

    # Quantization
    quantize_start: QuantizeMode = QuantizeMode.ANY_BEAT
    quantize_end: QuantizeMode = QuantizeMode.ANY_BEAT

    @model_validator(mode="after")
    def validate_mode_fields(self) -> MusicalTiming:
        """Validate that appropriate fields are set for the mode."""
        if self.mode == TimingMode.MUSICAL:
            # Musical mode: bars must be set
            if self.start_offset_bars < 0:
                raise ValueError("start_offset_bars must be >= 0 in MUSICAL mode")
            if self.duration_bars <= 0:
                raise ValueError("duration_bars must be > 0 in MUSICAL mode")

        elif self.mode == TimingMode.ABSOLUTE_MS:
            # Absolute mode: milliseconds must be set
            if self.start_offset_ms is None:
                raise ValueError("start_offset_ms required in ABSOLUTE_MS mode")
            if self.duration_ms is None:
                raise ValueError("duration_ms required in ABSOLUTE_MS mode")

        return self
