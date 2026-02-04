"""Universal musical timing models.

This module provides timing abstractions shared across all sequencing domains
(moving heads, RGB, lasers, etc.).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.sequencer.models.enum import QuantizeMode, TimingMode
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind


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


class TimeRef(BaseModel):
    """Canonical time reference for all authored timing.

    Supports two modes:
    - BAR_BEAT: (bar, beat, beat_frac) with optional offset_ms nudge
    - MS: Absolute milliseconds (offset_ms required, bar/beat must be None)

    Attributes:
        kind: Type of time reference (BAR_BEAT or MS).
        bar: Bar number (1-indexed, required for BAR_BEAT).
        beat: Beat number within bar (1-indexed, required for BAR_BEAT).
        beat_frac: Fractional beat position (0.0-1.0).
        offset_ms: Millisecond offset (fine nudge for BAR_BEAT, required for MS).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TimeRefKind

    # BAR_BEAT fields
    bar: int | None = Field(default=None, ge=1)
    beat: int | None = Field(default=None, ge=1)
    beat_frac: float = Field(default=0.0, ge=0.0, le=1.0)

    # Fine nudge (BAR_BEAT) or required absolute offset (MS)
    offset_ms: int | None = None

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> TimeRef:
        """Validate fields match the kind."""
        if self.kind == TimeRefKind.BAR_BEAT:
            if self.bar is None:
                raise ValueError("TimeRef(kind=BAR_BEAT): bar is required")
            if self.beat is None:
                raise ValueError("TimeRef(kind=BAR_BEAT): beat is required")
        elif self.kind == TimeRefKind.MS:
            if self.offset_ms is None:
                raise ValueError("TimeRef(kind=MS): offset_ms is required")
            if self.bar is not None:
                raise ValueError("TimeRef(kind=MS): bar must be None")
            if self.beat is not None:
                raise ValueError("TimeRef(kind=MS): beat must be None")
        return self
