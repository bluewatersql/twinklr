"""Build fixture contexts from rig profile and fixture group.

Separates fixture context construction from the rendering pipeline
so it can be tested and reused independently.
"""

from __future__ import annotations

from typing import Any

from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.models.context import FixtureContext
from twinklr.core.sequencer.models.moving_heads.rig import RigProfile

_ROLE_MAP_1 = ["CENTER"]
_ROLE_MAP_2 = ["LEFT", "RIGHT"]
_ROLE_MAP_3 = ["LEFT", "CENTER", "RIGHT"]
_ROLE_MAP_4 = ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]

_ROLE_MAPS: dict[int, list[str]] = {
    1: _ROLE_MAP_1,
    2: _ROLE_MAP_2,
    3: _ROLE_MAP_3,
    4: _ROLE_MAP_4,
}


def _infer_fixture_role(group_id: str, fixture_index: int, group_size: int) -> str:
    """Infer a semantic fixture role from its position within a group.

    Groups of 1-4 fixtures get well-known spatial role names.  Larger groups
    fall back to ``{group_id}_{fixture_index}`` positional naming.

    Args:
        group_id: Identifier of the fixture group.
        fixture_index: Zero-based position of the fixture within the group.
        group_size: Total number of fixtures in the group.

    Returns:
        A role string describing the fixture's spatial position.
    """
    role_map = _ROLE_MAPS.get(group_size)
    if role_map is not None and fixture_index < len(role_map):
        return role_map[fixture_index]
    return f"{group_id}_{fixture_index}"


def build_fixture_contexts(
    rig_profile: RigProfile,
    fixture_group: FixtureGroup,
) -> list[FixtureContext]:
    """Build fixture contexts from rig profile and fixture group.

    For each fixture in the rig, constructs a :class:`FixtureContext` with:
    - Calibration data from the fixture definition
    - Full :class:`FixtureConfig` for degree→DMX conversion
    - Spatial role inferred from position within the fixture group

    Args:
        rig_profile: Physical rig profile with fixture definitions and groups.
        fixture_group: Fixture group configuration with instances.

    Returns:
        List of :class:`FixtureContext` objects, one per fixture.
    """
    contexts: list[FixtureContext] = []

    # Get actual fixture configs from fixture_group for degree->DMX conversion
    fixture_configs = {fx.fixture_id: fx.config for fx in fixture_group.expand_fixtures()}

    for fixture_def in rig_profile.fixtures:
        # Build calibration dict from FixtureCalibration model
        calibration: dict[str, Any] = {}
        if fixture_def.calibration:
            calibration = {
                "pan_min_dmx": fixture_def.calibration.pan_min_dmx,
                "pan_max_dmx": fixture_def.calibration.pan_max_dmx,
                "tilt_min_dmx": fixture_def.calibration.tilt_min_dmx,
                "tilt_max_dmx": fixture_def.calibration.tilt_max_dmx,
                "pan_inverted": fixture_def.calibration.pan_inverted,
                "tilt_inverted": fixture_def.calibration.tilt_inverted,
                "dimmer_floor_dmx": fixture_def.calibration.dimmer_floor_dmx,
                "dimmer_ceiling_dmx": fixture_def.calibration.dimmer_ceiling_dmx,
            }

        # Add the full FixtureConfig for degree->DMX conversion in geometry handlers
        if fixture_def.fixture_id in fixture_configs:
            calibration["fixture_config"] = fixture_configs[fixture_def.fixture_id]

        # Infer role from fixture groups (first group that contains this fixture)
        role = "UNKNOWN"
        for group in rig_profile.groups:
            if fixture_def.fixture_id in group.fixture_ids:
                idx = group.fixture_ids.index(fixture_def.fixture_id)
                role = _infer_fixture_role(
                    group_id=group.group_id,
                    fixture_index=idx,
                    group_size=len(group.fixture_ids),
                )
                break

        contexts.append(
            FixtureContext(
                fixture_id=fixture_def.fixture_id,
                role=role,
                calibration=calibration,
            )
        )

    return contexts
