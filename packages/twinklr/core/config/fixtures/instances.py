"""Fixture instances and their configurations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from twinklr.core.config.fixtures.capabilities import FixtureCapabilities
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.physical import (
    REMOVED_FIXTURE_FIELDS,
    drop_retired_fields,
    reject_removed_fields,
    reject_removed_position_fields,
)


class FixturePosition(BaseModel):
    """Where a fixture sits on its mount, for ordering the rig left to right."""

    model_config = ConfigDict(frozen=False)

    position_index: int = Field(
        default=1, ge=1, le=10, description="Position number on this mount (1st, 2nd, etc.)"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        return reject_removed_position_fields(value)


class FixtureConfig(BaseModel):
    """Configuration of one moving head fixture."""

    model_config = ConfigDict(frozen=False)

    # Identification
    fixture_id: str = Field(..., description="Unique fixture identifier (e.g., 'MH1', 'MH2')")

    # DMX channel numbers, listed to the planner
    dmx_mapping: DmxMapping = Field(..., description="DMX channel assignments")

    # Position (optional - orders the rig left to right)
    position: FixturePosition | None = Field(default=None, description="Physical mounting position")

    # The renderer's profile of this fixture; required to render (or given once as the
    # group's base_config). Left out of dumps when absent.
    physical_profile: FixtureCapabilities | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Explicit capabilities the moving-head renderer needs for this fixture, unless "
            "the group's base_config gives them"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def drop_removed_fields(cls, value: object) -> object:
        value = drop_retired_fields(
            value,
            frozenset(
                {
                    "dmx_universe",
                    "dmx_start_address",
                    "channel_count",
                    "capabilities",
                    "movement_speed",
                }
            ),
            "fixture",
        )
        return reject_removed_fields(value, REMOVED_FIXTURE_FIELDS, "fixture")


class FixtureInstance(BaseModel):
    """A single fixture instance in the rig.

    Combines fixture configuration with xLights model mapping.
    """

    model_config = ConfigDict(frozen=False)

    fixture_id: str = Field(..., description="Unique fixture identifier")
    config: FixtureConfig = Field(..., description="Fixture configuration")
    xlights_model_name: str = Field(..., description="xLights model name (e.g., 'Dmx MH1')")

    @model_validator(mode="after")
    def sync_fixture_id(self) -> FixtureInstance:
        """Ensure fixture_id matches config."""
        if self.config.fixture_id != self.fixture_id:
            self.config.fixture_id = self.fixture_id
        return self
