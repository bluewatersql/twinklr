"""Physical movement and orientation configuration.

Defines physical capabilities, ranges, limits, and calibration data for fixtures.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PanTiltRange(BaseModel):
    """Physical movement capabilities of the fixture in degrees."""

    model_config = ConfigDict(frozen=True)

    pan_range_deg: float = Field(
        default=540.0, gt=0, le=720, description="Total pan range in degrees"
    )
    tilt_range_deg: float = Field(
        default=270.0, gt=0, le=360, description="Total tilt range in degrees"
    )


class Orientation(BaseModel):
    """Calibration data mapping physical positions to DMX values.

    These reference points allow accurate conversion between DMX values
    and real-world degrees.
    """

    model_config = ConfigDict(frozen=False)

    # Reference DMX values for known positions
    pan_front_dmx: int = Field(
        default=128, ge=0, le=255, description="DMX value when pointing forward (center)"
    )
    tilt_zero_dmx: int = Field(
        default=22, ge=0, le=255, description="DMX value at horizon/level (0°)"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            removed = sorted(
                {"tilt_up_dmx", "tilt_above_horizon_deg", "resting_position"} & value.keys()
            )
            if removed:
                raise ValueError(
                    f"orientation fields {removed} were removed because they never affected output"
                )
        return value


class MovementLimits(BaseModel):
    """Safety limits to prevent unwanted fixture positions.

    These limits prevent fixtures from pointing at the truss, ceiling,
    or other unsafe directions.
    """

    model_config = ConfigDict(frozen=False)

    pan_min: int = Field(default=50, ge=0, le=255, description="Minimum pan DMX value")
    pan_max: int = Field(default=190, ge=0, le=255, description="Maximum pan DMX value")
    tilt_min: int = Field(default=5, ge=0, le=255, description="Minimum tilt DMX value")
    tilt_max: int = Field(default=125, ge=0, le=255, description="Maximum tilt DMX value")
    avoid_backward: bool = Field(
        default=True, description="Prevent pointing backward (> 90° from forward)"
    )

    @field_validator("pan_max")
    @classmethod
    def validate_pan_range(cls, v: int, info: Any) -> int:
        """Validate that pan_min < pan_max."""
        pan_min = info.data.get("pan_min", 0)
        if pan_min >= v:
            raise ValueError(f"pan_min ({pan_min}) must be less than pan_max ({v})")
        return v

    @field_validator("tilt_max")
    @classmethod
    def validate_tilt_range(cls, v: int, info: Any) -> int:
        """Validate that tilt_min < tilt_max."""
        tilt_min = info.data.get("tilt_min", 0)
        if tilt_min >= v:
            raise ValueError(f"tilt_min ({tilt_min}) must be less than tilt_max ({v})")
        return v
