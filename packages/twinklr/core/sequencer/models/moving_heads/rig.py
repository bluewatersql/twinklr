"""Rig Profile Models for the moving head sequencer.

This module defines the configuration models for physical fixtures and
their organization into logical groups. These models describe the
"hardware" side of the system: what fixtures exist and how they are grouped.

Templates reference groups and roles (not fixture IDs) to remain portable
across different rigs.
"""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.models.enum import SemanticGroupType


class FixtureDefinition(BaseModel):
    """Physical fixture definition.

    Attributes:
        fixture_id: Unique identifier for this fixture.

    Example:
        >>> fixture = FixtureDefinition(fixture_id="front_left")
    """

    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)


class SemanticGroup(BaseModel):
    """Logical grouping of fixtures, which a template step targets.

    Templates reference groups (not individual fixtures) for portability.

    Attributes:
        group_id: Unique identifier for this group.
        fixture_ids: List of fixture IDs in this group, left to right.

    Example:
        >>> group = SemanticGroup(group_id="LEFT", fixture_ids=["front_left", "front_right"])
    """

    model_config = ConfigDict(extra="forbid")

    group_id: SemanticGroupType = Field(..., min_length=1)
    fixture_ids: list[str] = Field(..., min_length=1)


class RigProfile(BaseModel):
    """Complete rig configuration.

    Defines the entire physical rig including all fixtures and their
    logical groupings. This is the primary configuration document for
    the sequencer.

    Attributes:
        rig_id: Unique identifier for this rig configuration.
        fixtures: List of all fixture definitions.
        groups: Logical groupings of fixtures.

    Example:
        >>> profile = RigProfile(
        ...     rig_id="main_stage",
        ...     fixtures=[
        ...         FixtureDefinition(fixture_id="fix1"),
        ...         FixtureDefinition(fixture_id="fix2"),
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
) -> RigProfile:
    """Create a RigProfile from a FixtureGroup.

    Assumptions (MVP):
    - ordering is based on FixturePosition.position_index when available
    - rooftop 4-head common groups can be inferred

    You can turn off group inference.

    Example Usage:
    from rig_adapters import rig_profile_from_fixture_group

    rig = rig_profile_from_fixture_group(moving_heads_group, rig_id="rooftop_4")
    """

    # Order left->right using position_index when present, otherwise fixture_id.
    # Sort the original FixtureInstance objects first, then create FixtureDefinition objects
    def _sort_key(fx_instance):
        pos = getattr(fx_instance.config, "position", None)
        if pos is not None and getattr(pos, "position_index", None) is not None:
            return (int(pos.position_index), fx_instance.fixture_id)
        return (10_000, fx_instance.fixture_id)

    fixture_instances_sorted = sorted(group.expand_fixtures(), key=_sort_key)

    fixtures = [
        FixtureDefinition(fixture_id=fixture.fixture_id) for fixture in fixture_instances_sorted
    ]

    fixtures_sorted = fixtures
    fixture_ids = [f.fixture_id for f in fixtures_sorted]

    groups: list[SemanticGroup] = []

    if infer_semantic_groups:
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.ALL,
                fixture_ids=fixture_ids,
            )
        )
        mid = len(fixture_ids) // 2
        left_ids = fixture_ids[:mid] or fixture_ids
        right_ids = fixture_ids[mid:] or fixture_ids
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.LEFT,
                fixture_ids=left_ids,
            )
        )
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.RIGHT,
                fixture_ids=right_ids,
            )
        )

        if len(fixture_ids) >= 4:
            groups.append(
                SemanticGroup(
                    group_id=SemanticGroupType.OUTER,
                    fixture_ids=[fixture_ids[0], fixture_ids[-1]],
                )
            )
            groups.append(
                SemanticGroup(
                    group_id=SemanticGroupType.INNER,
                    fixture_ids=fixture_ids[1:-1],
                )
            )

        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.ODD,
                fixture_ids=fixture_ids[::2] or fixture_ids,
            )
        )
        groups.append(
            SemanticGroup(
                group_id=SemanticGroupType.EVEN,
                fixture_ids=fixture_ids[1::2] or fixture_ids,
            )
        )

    return RigProfile(rig_id=rig_id or group.group_id, groups=groups, fixtures=fixtures)
