"""Playback Plan Model for the moving head sequencer.

This module defines the PlaybackPlan model which specifies what template
to compile and the playback window.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class PlaybackPlan(BaseModel):
    """Plan for compiling a template into a playback window.

    Specifies which template to use, optional preset and modifiers,
    and the time window for compilation.

    Attributes:
        template_id: Identifier of the template to compile.
        preset_id: Optional preset to apply to the template.
        modifiers: Optional modifier overrides.
        window_start_ms: Start of playback window in milliseconds.
        window_end_ms: End of playback window in milliseconds.

    Example:
        >>> plan = PlaybackPlan(
        ...     template_id="fan_pulse",
        ...     preset_id="CHILL",
        ...     window_start_ms=0,
        ...     window_end_ms=10000,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1)
    preset_id: str | None = Field(None)
    modifiers: dict[str, Any] = Field(default_factory=dict)

    window_start_ms: int = Field(..., ge=0)
    window_end_ms: int = Field(..., ge=0)

    @field_validator("window_end_ms")
    @classmethod
    def validate_window(cls, window_end_ms: int, info: ValidationInfo) -> int:
        """Validate window_end_ms >= window_start_ms."""
        window_start_ms = info.data.get("window_start_ms", 0) if info.data else 0
        if window_end_ms < window_start_ms:
            raise ValueError(
                f"window_end_ms ({window_end_ms}) < window_start_ms ({window_start_ms})"
            )
        return window_end_ms
