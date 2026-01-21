"""Fixture grouping and batch configuration.

Defines fixture groups, base configurations, and builders for managing multiple fixtures.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blinkb0t.core.config.fixtures.capabilities import FixtureCapabilities, MovementSpeed
from blinkb0t.core.config.fixtures.dmx import ChannelInversions, DmxMapping
from blinkb0t.core.config.fixtures.instances import FixtureConfig, FixtureInstance, FixturePosition
from blinkb0t.core.config.fixtures.physical import MovementLimits, Orientation, PanTiltRange


class BaseFixtureConfig(BaseModel):
    """Base configuration shared across all fixtures in a group.

    This eliminates duplication by defining common settings once.
    Individual fixtures inherit these settings and can override as needed.

    Phase 2 Addition: Reduces config size by ~60% for typical setups.
    """

    model_config = ConfigDict(frozen=False)

    # DMX configuration (shared across all fixtures)
    dmx_universe: int = Field(default=1, ge=1, le=64, description="DMX universe number")
    channel_count: int = Field(default=16, ge=1, le=128, description="Number of DMX channels used")

    # DMX channel assignments (shared mapping)
    dmx_mapping: DmxMapping = Field(..., description="DMX channel assignments")
    inversions: ChannelInversions = Field(
        default_factory=ChannelInversions, description="Channel inversion flags"
    )

    # Physical capabilities (shared across fixtures)
    pan_tilt_range: PanTiltRange = Field(
        default_factory=PanTiltRange, description="Physical movement range"
    )
    orientation: Orientation = Field(
        default_factory=Orientation, description="Calibration and orientation data"
    )
    limits: MovementLimits = Field(
        default_factory=MovementLimits, description="Safety movement limits"
    )

    capabilities: FixtureCapabilities = Field(
        default_factory=FixtureCapabilities, description="Feature capabilities"
    )
    movement_speed: MovementSpeed = Field(
        default_factory=MovementSpeed, description="Movement speed specifications"
    )


class SimplifiedFixtureInstance(BaseModel):
    """Simplified fixture instance that inherits from base_config.

    Only specifies unique per-fixture values. All other settings inherited from base_config.
    Phase 2 Addition: Reduces per-fixture config from ~80 lines to ~10 lines.
    """

    model_config = ConfigDict(frozen=False)

    fixture_id: str = Field(..., description="Unique fixture identifier (e.g., 'MH1')")
    dmx_start_address: int = Field(..., ge=1, le=512, description="Starting DMX address")
    xlights_model_name: str = Field(..., description="xLights model name (e.g., 'Dmx MH1')")

    # Position is the only section that varies per fixture
    position: FixturePosition | None = Field(
        default=None, description="Physical mounting position and offsets"
    )

    # Optional: Allow overriding base_config for specific fixtures
    config_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Override specific base_config values (e.g., {'dmx_universe': 2})",
    )


class FixtureGroup(BaseModel):
    """A collection of fixtures that work together.

    Groups can be:
    - Physical groups (mapped to xLights groups)
    - Semantic groups (logical groupings for sequencing)

    Phase 2 Enhancement: Supports base_config for DRY fixture configuration.
    """

    model_config = ConfigDict(frozen=False)

    group_id: str = Field(..., description="Unique group identifier (e.g., 'MOVING_HEADS')")

    # New: Base configuration (optional for backward compatibility)
    base_config: BaseFixtureConfig | None = Field(
        default=None, description="Shared configuration for all fixtures (Phase 2 feature)"
    )

    # Support both old (FixtureInstance) and new (SimplifiedFixtureInstance) formats
    fixtures: list[FixtureInstance | SimplifiedFixtureInstance] = Field(
        default_factory=list, description="Fixtures in this group"
    )

    xlights_group: str | None = Field(
        default=None,
        description="xLights group name for ALL fixtures (e.g., 'GROUP - MOVING HEADS')",
    )
    xlights_semantic_groups: dict[str, str] = Field(
        default_factory=dict,
        description="Semantic group name -> xLights group model name (e.g., 'LEFT': 'GROUP - MH LEFT')",
    )

    def is_semantic(self) -> bool:
        """Check if this is a semantic group (no xLights mapping).

        Returns:
            True if semantic group, False if physical/xLights group
        """
        return self.xlights_group is None

    def expand_fixtures(self) -> list[FixtureInstance]:
        """Expand simplified fixtures into full FixtureInstance objects.

        Phase 2 Feature: Applies base_config to SimplifiedFixtureInstance objects.
        FixtureInstance objects are returned as-is (backward compatibility).

        Returns:
            List of fully configured FixtureInstance objects

        Raises:
            ValueError: If base_config is None but SimplifiedFixtureInstance found
        """
        expanded = []

        for fixture in self.fixtures:
            # Already a full FixtureInstance - use as-is
            if isinstance(fixture, FixtureInstance):
                expanded.append(fixture)
                continue

            # SimplifiedFixtureInstance - needs expansion
            if not self.base_config:
                raise ValueError(
                    f"Fixture {fixture.fixture_id} uses simplified format but "
                    "no base_config provided in FixtureGroup"
                )

            # Build full FixtureConfig from base_config + overrides
            config_dict = self.base_config.model_dump()
            config_dict.update(fixture.config_overrides)

            # Add fixture-specific values
            config_dict["fixture_id"] = fixture.fixture_id
            config_dict["dmx_start_address"] = fixture.dmx_start_address
            config_dict["position"] = fixture.position

            full_config = FixtureConfig.model_validate(config_dict)

            expanded.append(
                FixtureInstance(
                    fixture_id=fixture.fixture_id,
                    config=full_config,
                    xlights_model_name=fixture.xlights_model_name,
                )
            )

        return expanded

    def add_fixture(self, fixture: FixtureInstance | SimplifiedFixtureInstance) -> None:
        """Add a fixture to the group."""
        self.fixtures.append(fixture)

    def get_fixture(self, fixture_id: str) -> FixtureInstance | None:
        """Get a fixture by ID.

        Args:
            fixture_id: Fixture identifier

        Returns:
            FixtureInstance if found, None otherwise

        Note:
            For SimplifiedFixtureInstance, this will expand it first.
        """
        expanded = self.expand_fixtures()
        return next((f for f in expanded if f.fixture_id == fixture_id), None)

    def get_xlights_mapping(self) -> dict[str, str]:
        """Generate complete xLights model mapping.

        Returns:
            Dictionary mapping fixture IDs/group names to xLights model names.
            Includes: individual fixtures, "ALL" group, and semantic groups (LEFT, RIGHT, etc.)
        """
        mapping = {}

        # Add main group mapping if exists
        if self.xlights_group:
            mapping["ALL"] = self.xlights_group

        # Add semantic group mappings (LEFT, RIGHT, ODD, EVEN, etc.)
        mapping.update(self.xlights_semantic_groups)

        # Add individual fixture mappings
        for fixture in self.fixtures:
            mapping[fixture.fixture_id] = fixture.xlights_model_name

        return mapping

    def __iter__(self):
        """Allow iteration over fixtures."""
        return iter(self.fixtures)

    def __len__(self):
        """Get number of fixtures in group."""
        return len(self.fixtures)


class FixtureGroupBuilder(BaseModel):
    """Helper to build fixture groups easily.

    Simplifies creation of fixture groups by cloning a base configuration
    and customizing per-fixture parameters.
    """

    model_config = ConfigDict(frozen=False)

    group_id: str = Field(..., description="Group identifier")
    xlights_group: str = Field(..., description="xLights group name")
    base_config: FixtureConfig = Field(..., description="Base configuration to clone")

    def build(self, fixtures: list[tuple[str, int, str, FixturePosition]]) -> FixtureGroup:
        """Build a fixture group from a list of fixture specs.

        Args:
            fixtures: List of (fixture_id, dmx_addr, xlights_name, position) tuples

        Returns:
            Configured FixtureGroup
        """
        group = FixtureGroup(group_id=self.group_id, xlights_group=self.xlights_group)

        for fixture_id, dmx_addr, xlights_name, position in fixtures:
            config = self._clone_config(fixture_id, dmx_addr, position)
            group.add_fixture(
                FixtureInstance(
                    fixture_id=fixture_id, config=config, xlights_model_name=xlights_name
                )
            )

        return group

    def _clone_config(
        self, fixture_id: str, dmx_addr: int, position: FixturePosition
    ) -> FixtureConfig:
        """Clone base config with customizations."""
        # Use model_copy() to properly clone the config with updates
        return self.base_config.model_copy(
            update={
                "fixture_id": fixture_id,
                "dmx_start_address": dmx_addr,
                "position": position,
            }
        )
