"""Rig Profile Models for the moving head sequencer.

This module defines the configuration models for physical fixtures and
their organization into logical groups. These models describe the
"hardware" side of the system - what fixtures exist, where they are,
and how they're calibrated.

Templates reference groups and roles (not fixture IDs) to remain portable
across different rigs.
"""

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from blinkb0t.core.config.fixtures import FixtureGroup
from blinkb0t.core.sequencer.models.enum import ChaseOrder, SemanticGroupType


class FixtureCalibration(BaseModel):
    """Calibration settings for a fixture.

    Defines the DMX range limits and inversion settings for each fixture.
    These values are used by handlers to map normalized curves to DMX.

    Attributes:
        pan_min_dmx: Minimum DMX value for pan channel.
        pan_max_dmx: Maximum DMX value for pan channel.
        tilt_min_dmx: Minimum DMX value for tilt channel.
        tilt_max_dmx: Maximum DMX value for tilt channel.
        pan_inverted: If True, pan direction is reversed.
        tilt_inverted: If True, tilt direction is reversed.
        dimmer_floor_dmx: Minimum dimmer value (prevents flicker).
        dimmer_ceiling_dmx: Maximum dimmer value.

    Example:
        >>> cal = FixtureCalibration(
        ...     pan_min_dmx=10,
        ...     pan_max_dmx=245,
        ...     dimmer_floor_dmx=60,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    pan_min_dmx: int = Field(0, ge=0, le=255)
    pan_max_dmx: int = Field(255, ge=0, le=255)
    tilt_min_dmx: int = Field(0, ge=0, le=255)
    tilt_max_dmx: int = Field(255, ge=0, le=255)

    pan_inverted: bool = Field(False)
    tilt_inverted: bool = Field(False)

    dimmer_floor_dmx: int = Field(0, ge=0, le=255)
    dimmer_ceiling_dmx: int = Field(255, ge=0, le=255)

    @field_validator("dimmer_ceiling_dmx")
    @classmethod
    def validate_dimmer_range(cls, v: int, info: ValidationInfo) -> int:
        """Validate dimmer_ceiling_dmx >= dimmer_floor_dmx."""
        floor = info.data.get("dimmer_floor_dmx", 0) if info.data else 0
        if v < floor:
            raise ValueError(f"dimmer_ceiling_dmx ({v}) < dimmer_floor_dmx ({floor})")
        return v


class FixtureDefinition(BaseModel):
    """Physical fixture definition.

    Defines a single physical fixture with its DMX addressing, role,
    position, and calibration settings.

    Attributes:
        fixture_id: Unique identifier for this fixture.
        universe: DMX universe number (1-512).
        start_address: Starting DMX address in the universe (1-512).
        role: Semantic role (e.g., "FRONT_LEFT", "BACK_CENTER").
        spatial_position: (x, y) position for ordering and geometry.
        calibration: Per-fixture calibration settings.

    Example:
        >>> fixture = FixtureDefinition(
        ...     fixture_id="front_left",
        ...     universe=1,
        ...     start_address=1,
        ...     role="FRONT_LEFT",
        ...     spatial_position=(-1.0, 0.0),
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)
    calibration: FixtureCalibration | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _set_default_calibration(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Set default calibration if not provided."""
        if isinstance(data, dict) and data.get("calibration") is None:
            data["calibration"] = {}
        return data


class SemanticGroup(BaseModel):
    """Logical grouping of fixtures.

    Groups fixtures for collective operations like phase offset spreading.
    Templates reference groups (not individual fixtures) for portability.

    Attributes:
        group_id: Unique identifier for this group.
        fixture_ids: List of fixture IDs in this group.
        order: Default chase order for phase offsets.

    Example:
        >>> group = SemanticGroup(
        ...     group_id="fronts",
        ...     fixture_ids=["front_left", "front_right"],
        ...     order=ChaseOrder.LEFT_TO_RIGHT,
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    group_id: SemanticGroupType = Field(..., min_length=1)
    fixture_ids: list[str] = Field(..., min_length=1)
    order: ChaseOrder = Field(ChaseOrder.LEFT_TO_RIGHT)


class RigProfile(BaseModel):
    """Complete rig configuration.

    Defines the entire physical rig including all fixtures and their
    logical groupings. This is the primary configuration document for
    the sequencer.

    Attributes:
        rig_id: Unique identifier for this rig configuration.
        fixtures: List of all fixture definitions.
        groups: Logical groupings of fixtures.
        default_dimmer_floor_dmx: Default dimmer floor for all fixtures.
        default_dimmer_ceiling_dmx: Default dimmer ceiling for all fixtures.

    Example:
        >>> profile = RigProfile(
        ...     rig_id="main_stage",
        ...     fixtures=[
        ...         FixtureDefinition(fixture_id="fix1", universe=1, start_address=1),
        ...         FixtureDefinition(fixture_id="fix2", universe=1, start_address=17),
        ...     ],
        ...     groups=[
        ...         SemanticGroup(group_id="all", fixture_ids=["fix1", "fix2"]),
        ...     ],
        ... )
    """

    model_config = ConfigDict(extra="forbid")

    rig_id: str = Field(..., min_length=1)
    fixtures: list[FixtureDefinition] = Field(..., min_length=1)
    groups: list[SemanticGroup] = Field(default_factory=list)

    default_dimmer_floor_dmx: int | None = Field(60, ge=0, le=255)
    default_dimmer_ceiling_dmx: int | None = Field(255, ge=0, le=255)

    @field_validator("groups")
    @classmethod
    def validate_group_fixtures(
        cls,
        groups: list[SemanticGroup],
        info: ValidationInfo,
    ) -> list[SemanticGroup]:
        """Validate that all fixture IDs in groups exist in fixtures."""
        fixtures: list[FixtureDefinition] = info.data.get("fixtures", []) if info.data else []
        fixture_ids = {f.fixture_id for f in fixtures}

        for group in groups:
            for fid in group.fixture_ids:
                if fid not in fixture_ids:
                    raise ValueError(f"Group {group.group_id} references unknown fixture: {fid}")

        return groups


def rig_profile_from_fixture_group(
    group: FixtureGroup,
    *,
    rig_id: str | None = None,
    infer_semantic_groups: bool = True,
    infer_orders: bool = True,
    infer_roles: bool = True,
    dimmer_floor_dmx: int | None = None,
) -> RigProfile:
    """Create a RigProfile from a FixtureGroup.

    Assumptions (MVP):
    - ordering is based on FixturePosition.position_index when available
    - rooftop 4-head common groups/orders can be inferred

    You can turn off inference and provide groups/orders/roles explicitly.

    Example Usage:
    from rig_adapters import rig_profile_from_fixture_group

    rig = rig_profile_from_fixture_group(
        moving_heads_group,
        rig_id="rooftop_4",
        dimmer_floor_dmx=60,  # set your real floor here
    )
    """

    fixtures: list[FixtureDefinition] = []
    for fixture in group.expand_fixtures():
        fixtures.append(
            FixtureDefinition(
                fixture_id=fixture.fixture_id,
            )
        )

    # Order left->right using position_index when present, otherwise fixture_id.
    def _sort_key(fx):
        pos = getattr(fx.config, "position", None)
        if pos is not None and getattr(pos, "position_index", None) is not None:
            return (int(pos.position_index), fx.fixture_id)
        return (10_000, fx.fixture_id)

    fixtures_sorted = sorted(fixtures, key=_sort_key)
    fixture_ids = [f.fixture_id for f in fixtures_sorted]

    groups: list[SemanticGroup] = []
    order_mode = ChaseOrder.LEFT_TO_RIGHT

    if infer_semantic_groups:
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.ALL,
                fixture_ids=fixture_ids,
                order=order_mode,
            )
        )
        mid = len(fixture_ids) // 2
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.LEFT,
                fixture_ids=fixture_ids[:mid],
                order=order_mode,
            )
        )
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.RIGHT,
                fixture_ids=fixture_ids[mid:],
                order=order_mode,
            )
        )

        if len(fixture_ids) >= 4:
            groups.append(
                SemanticGroup(
                    group_id=SemanticGroupType.OUTER,
                    fixture_ids=[fixture_ids[0], fixture_ids[-1]],
                    order=order_mode,
                )
            )
            groups.append(
                SemanticGroup(
                    group_id=SemanticGroupType.INNER,
                    fixture_ids=fixture_ids[1:-1],
                    order=order_mode,
                )
            )

        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.ODD,
                fixture_ids=fixture_ids[::2],
                order=order_mode,
            )
        )
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.EVEN,
                fixture_ids=fixture_ids[1::2],
                order=order_mode,
            )
        )

    calib_kwargs = {}
    if dimmer_floor_dmx is not None:
        calib_kwargs["dimmer_floor_dmx"] = dimmer_floor_dmx

    return RigProfile(
        rig_id=rig_id or group.group_id,
        groups=groups,
        fixtures=fixtures,
        default_dimmer_floor_dmx=None,
        default_dimmer_ceiling_dmx=None,
    )
