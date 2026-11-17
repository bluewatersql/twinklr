"""Fixture grouping and batch configuration.

Defines fixture groups, base configurations, and builders for managing multiple fixtures.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from twinklr.core.config.fixtures.capabilities import PROFILE_GUIDE, FixtureCapabilities
from twinklr.core.config.fixtures.dmx import DmxMapping
from twinklr.core.config.fixtures.instances import FixtureConfig, FixtureInstance, FixturePosition
from twinklr.core.config.fixtures.presets import RigPresetLibrary
from twinklr.core.config.fixtures.removed_fields import (
    REMOVED_DMX_MAPPING_FIELDS,
    REMOVED_FIXTURE_FIELDS,
    drop_retired_fields,
    reject_removed_fields,
    reject_removed_position_fields,
)
from twinklr.core.sequencer.models.moving_heads.topology import FixtureTopology


class BaseFixtureConfig(BaseModel):
    """Base configuration shared across all fixtures in a group.

    This eliminates duplication by defining common settings once.
    Individual fixtures inherit these settings and can override as needed.

    Phase 2 Addition: Reduces config size by ~60% for typical setups.
    """

    model_config = ConfigDict(frozen=False)

    # DMX channel assignments (shared mapping)
    dmx_mapping: DmxMapping = Field(..., description="DMX channel assignments")

    # Shared physical profile; a fixture's config_overrides entry replaces it.
    # Left out of dumps when absent.
    physical_profile: FixtureCapabilities | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Explicit capabilities the moving-head renderer needs, shared by every fixture"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def drop_removed_fields(cls, value: object) -> object:
        value = drop_retired_fields(
            value,
            frozenset({"dmx_universe", "channel_count", "capabilities", "movement_speed"}),
            "fixture",
        )
        return reject_removed_fields(value, REMOVED_FIXTURE_FIELDS, "fixture")


def _validated_profile(owner: str, profile: object) -> FixtureCapabilities:
    """Validate a physical profile, naming its owner and the guide's minimal example on
    failure."""
    try:
        return FixtureCapabilities.model_validate(profile)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'profile'}: {item['msg']}"
            for item in error.errors()
        )
        raise ValueError(
            f"{owner} has an invalid physical_profile: {problems}. A minimal profile and "
            f"what it must state: {PROFILE_GUIDE}"
        ) from None


class SimplifiedFixtureInstance(BaseModel):
    """Simplified fixture instance that inherits from base_config.

    Only specifies unique per-fixture values. All other settings inherited from base_config.
    Phase 2 Addition: Reduces per-fixture config from ~80 lines to ~10 lines.
    """

    model_config = ConfigDict(frozen=False)

    fixture_id: str = Field(..., description="Unique fixture identifier (e.g., 'MH1')")
    xlights_model_name: str = Field(..., description="xLights model name (e.g., 'Dmx MH1')")

    # Position is the only section that varies per fixture
    position: FixturePosition | None = Field(default=None, description="Physical mounting position")

    # Optional: Allow overriding base_config for specific fixtures
    config_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Override specific base_config values (e.g., {'dmx_universe': 2})",
    )

    @model_validator(mode="before")
    @classmethod
    def drop_removed_fields(cls, value: object) -> object:
        return drop_retired_fields(value, frozenset({"dmx_start_address"}), "fixture")

    @field_validator("config_overrides")
    @classmethod
    def type_profile_override(cls, value: dict[str, Any], info: Any) -> dict[str, Any]:
        """Refuse a removed field and validate a per-fixture physical_profile override
        rather than pass it untyped."""
        reject_removed_fields(value, REMOVED_FIXTURE_FIELDS, "config_overrides")
        reject_removed_fields(
            value.get("dmx_mapping"), REMOVED_DMX_MAPPING_FIELDS, "config_overrides.dmx_mapping"
        )
        if "position" in value:
            raise ValueError(
                "config_overrides field 'position' never took effect: each fixture's "
                "position is its own `position`, which replaces it. Move it there"
            )
        profile = value.get("physical_profile")
        if profile is None:
            return value
        fixture_id = info.data.get("fixture_id")
        return {**value, "physical_profile": _validated_profile(f"fixture {fixture_id!r}", profile)}


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

    # Named components templates refer to. Left out of dumps when empty.
    presets: RigPresetLibrary = Field(
        default_factory=RigPresetLibrary,
        exclude_if=lambda value: value.is_empty,
        description="Position and attribute presets template steps name by id",
    )

    # The canonical full rig phase distributions rank heads in. Left out of dumps when
    # absent.
    topology: FixtureTopology | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description="Where each head sits in the full rig, for phase distribution",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_removed_fields(cls, value: object) -> object:
        """Refuse a removed field, naming it, here: the `fixtures` union would otherwise
        fall back to the simplified form, which drops a full fixture's `config`."""
        if not isinstance(value, dict):
            return value
        if "xlights_semantic_groups" in value:
            raise ValueError(
                "fixture group field 'xlights_semantic_groups' was removed: nothing renders "
                "to those groups. Delete it; xlights_group names the group of every head"
            )
        for fixture in value.get("fixtures") or ():
            config = fixture.get("config") if isinstance(fixture, dict) else None
            if isinstance(config, dict):
                owner = f"fixture {fixture.get('fixture_id')!r}"
                reject_removed_fields(config, REMOVED_FIXTURE_FIELDS, owner)
                reject_removed_fields(
                    config.get("dmx_mapping"), REMOVED_DMX_MAPPING_FIELDS, f"{owner} dmx_mapping"
                )
                reject_removed_position_fields(config.get("position"), f"{owner} position")
        return value

    @model_validator(mode="before")
    @classmethod
    def surface_invalid_physical_profiles(cls, value: object) -> object:
        """Fail on an invalid fixture physical_profile here, naming the fixture.

        The `fixtures` union would otherwise fall back to the simplified form, which
        drops `config`, and the error would surface later as a missing base_config.
        Other invalid fields keep their existing behavior.
        """
        if not isinstance(value, dict):
            return value
        base = value.get("base_config")
        if isinstance(base, dict) and base.get("physical_profile") is not None:
            _validated_profile("base_config", base["physical_profile"])
        for fixture in value.get("fixtures") or ():
            if not isinstance(fixture, dict):
                continue
            owner = f"fixture {fixture.get('fixture_id')!r}"
            for holder in (fixture.get("config"), fixture.get("config_overrides")):
                if isinstance(holder, dict) and holder.get("physical_profile") is not None:
                    _validated_profile(owner, holder["physical_profile"])
        return value

    @model_validator(mode="after")
    def _validate_presets(self) -> FixtureGroup:
        """Check the presets against the group's fixtures and their physical profiles."""
        if not self.presets.is_empty:
            self.presets.check_rig(
                {
                    fixture.fixture_id: fixture.config.physical_profile
                    for fixture in self.expand_fixtures()
                }
            )
        return self

    @model_validator(mode="after")
    def _validate_topology(self) -> FixtureGroup:
        """Every fixture of the group has a place in the topology. A member the group
        lacks is a missing head: its slot stays empty."""
        if self.topology is not None:
            members = set(self.topology.canonical_ids)
            unplaced = [f.fixture_id for f in self.fixtures if f.fixture_id not in members]
            if unplaced:
                raise ValueError(f"fixtures {unplaced} have no place in the group's topology")
        return self

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

            # Build full FixtureConfig from base_config + overrides. The shared profile
            # is passed as loaded, so what its loading defaulted stays recorded.
            config_dict = self.base_config.model_dump()
            config_dict["physical_profile"] = self.base_config.physical_profile
            config_dict.update(fixture.config_overrides)

            # Add fixture-specific values
            config_dict["fixture_id"] = fixture.fixture_id
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

    def build(self, fixtures: list[tuple[str, str, FixturePosition]]) -> FixtureGroup:
        """Build a fixture group from a list of fixture specs.

        Args:
            fixtures: List of (fixture_id, xlights_name, position) tuples

        Returns:
            Configured FixtureGroup
        """
        group = FixtureGroup(group_id=self.group_id, xlights_group=self.xlights_group)

        for fixture_id, xlights_name, position in fixtures:
            config = self._clone_config(fixture_id, position)
            group.add_fixture(
                FixtureInstance(
                    fixture_id=fixture_id, config=config, xlights_model_name=xlights_name
                )
            )

        return group

    def _clone_config(self, fixture_id: str, position: FixturePosition) -> FixtureConfig:
        """Clone base config with customizations."""
        # Use model_copy() to properly clone the config with updates
        return self.base_config.model_copy(
            update={
                "fixture_id": fixture_id,
                "position": position,
            }
        )
