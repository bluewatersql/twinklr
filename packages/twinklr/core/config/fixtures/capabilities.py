"""Fixture capabilities and performance specifications.

Defines what features a fixture has and how fast it can move.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FixtureCapabilities(BaseModel):
    """What this fixture can actually do.

    Defines the feature set available on this fixture model.
    """

    model_config = ConfigDict(frozen=True)

    has_color_wheel: bool = Field(default=True, description="Has color wheel")
    has_gobo_wheel: bool = Field(default=True, description="Has gobo wheel")
    has_prism: bool = Field(default=False, description="Has prism effect")
    has_zoom: bool = Field(default=False, description="Has motorized zoom")
    has_iris: bool = Field(default=False, description="Has iris control")
    has_frost: bool = Field(default=False, description="Has frost filter")
    beam_angle_deg: float = Field(
        default=15.0, gt=0, le=90, description="Beam angle in degrees (spot vs wash)"
    )


class MovementSpeed(BaseModel):
    """How fast the fixture can actually move.

    Used for realistic timing and sequence planning.
    """

    model_config = ConfigDict(frozen=True)

    pan_speed_deg_per_sec: float = Field(
        default=180.0, gt=0, description="Pan speed in degrees/second"
    )
    tilt_speed_deg_per_sec: float = Field(
        default=90.0, gt=0, description="Tilt speed in degrees/second"
    )
    color_change_ms: int = Field(
        default=100, ge=0, description="Color wheel change time in milliseconds"
    )
    gobo_change_ms: int = Field(
        default=150, ge=0, description="Gobo wheel change time in milliseconds"
    )
