"""Resolve plan targets to FixtureGroup instances.

Centralizes all semantic group resolution and model mapping logic.
"""

from __future__ import annotations

import logging
from typing import Any

from blinkb0t.core.config.fixtures import FixtureConfig, FixtureGroup, FixtureInstance
from blinkb0t.core.utils.fixtures import build_semantic_groups

logger = logging.getLogger(__name__)


def resolve_plan_targets(
    plan: dict[str, Any],
    base_fixtures: FixtureGroup,
) -> dict[str, FixtureGroup]:
    """Resolve all plan targets to FixtureGroup instances.

    This centralizes ALL target resolution logic in one place. Downstream code
    just works with FixtureGroup instances - no need to know about semantic groups,
    model mapping, or xLights names.

    Strategy:
    - Semantic groups (LEFT, RIGHT, etc): Explode to individual fixtures with their configs
    - Mapped groups (ALL): Create virtual fixture (first fixture, position stripped)
    - Individual fixtures (MH1): Create single-fixture group

    Args:
        plan: Plan dict with sections containing targets
        base_fixtures: Loaded fixture group (all fixtures)

    Returns:
        Dict mapping plan targets to FixtureGroup instances
        Example: {
            "ALL": FixtureGroup([virtual_mh]),
            "LEFT": FixtureGroup([mh1, mh2]),
            "MH1": FixtureGroup([mh1])
        }
    """
    # Build semantic groups from fixture IDs
    fixture_ids = [f.fixture_id for f in base_fixtures]
    semantic_groups = build_semantic_groups(fixture_ids)

    # Get xLights mapping
    model_map = base_fixtures.get_xlights_mapping()

    # Collect all unique targets from plan
    targets = set()
    for section in plan.get("sections", []):
        # targets at section level (list)
        section_targets = section.get("targets", [])
        if section_targets:
            for t in section_targets:
                targets.add(str(t).strip())

        # target in instructions
        for inst in section.get("instructions", []):
            target = str(inst.get("target", "ALL")).strip()
            targets.add(target)

    # Resolve each target to a FixtureGroup
    resolved = {}
    for target in targets:
        fixture_group = _resolve_target(target, base_fixtures, semantic_groups, model_map)
        if fixture_group:
            resolved[target] = fixture_group
            logger.debug(
                f"Resolved target '{target}' → FixtureGroup with "
                f"{len(fixture_group.fixtures)} fixture(s)"
            )

    return resolved


def _resolve_target(
    target: str,
    base_fixtures: FixtureGroup,
    semantic_groups: dict[str, list[str]],
    model_map: dict[str, str],
) -> FixtureGroup | None:
    """Resolve a single target to a FixtureGroup."""

    # Case 1: ALL (mapped group) - explode to individual fixtures
    # Changed from virtual fixture to enable per_fixture_offsets
    # Special handling: ALL uses base xlights_group, not semantic groups
    if target.upper() == "ALL":
        fixture_ids = semantic_groups.get("ALL", [])
        fixtures = []
        for fixture_id in fixture_ids:
            fixture = base_fixtures.get_fixture(fixture_id)
            if fixture:
                fixtures.append(fixture)

        return FixtureGroup(
            group_id="ALL",
            fixtures=fixtures,  # type: ignore[arg-type]
            xlights_group=base_fixtures.xlights_group,  # Use base group's xlights_group ("90 - MH")
        )

    # Case 2: Semantic group (LEFT, RIGHT, etc) - explode to individual fixtures
    if target in semantic_groups:
        fixture_ids = semantic_groups[target]
        return _create_exploded_group(base_fixtures, fixture_ids, target)

    # Case 3: Individual fixture (MH1, MH2, etc) - single fixture group
    fixture = base_fixtures.get_fixture(target)
    if fixture:
        return FixtureGroup(
            group_id=target,
            fixtures=[fixture],
            xlights_group=None,  # Semantic group
        )

    logger.warning(f"Could not resolve target '{target}'")
    return None


def _create_virtual_group(
    base_fixtures: FixtureGroup,
    group_id: str,
) -> FixtureGroup:
    """Create virtual fixture group for mapped groups like ALL.

    Takes the first fixture and strips position info to create a
    "virtual" fixture that represents the entire group.
    """
    first_fixture = list(base_fixtures)[0]

    # Clone config but strip position
    virtual_config = FixtureConfig(
        fixture_id=group_id,
        dmx_mapping=first_fixture.config.dmx_mapping,
        inversions=first_fixture.config.inversions,
        channel_count=first_fixture.config.channel_count,
        pan_tilt_range=first_fixture.config.pan_tilt_range,
        orientation=first_fixture.config.orientation,
        limits=first_fixture.config.limits,
        capabilities=first_fixture.config.capabilities,
        position=None,  # Stripped!
        movement_speed=first_fixture.config.movement_speed,
    )

    virtual_fixture = FixtureInstance(
        fixture_id=group_id,
        config=virtual_config,
        xlights_model_name=base_fixtures.xlights_group or f"GROUP - {group_id}",
    )

    return FixtureGroup(
        group_id=group_id,
        fixtures=[virtual_fixture],
        xlights_group=base_fixtures.xlights_group,
    )


def _create_exploded_group(
    base_fixtures: FixtureGroup,
    fixture_ids: list[str],
    group_id: str,
) -> FixtureGroup:
    """Create group with individual fixtures (for semantic groups)."""
    fixtures = []
    for fixture_id in fixture_ids:
        fixture = base_fixtures.get_fixture(fixture_id)
        if fixture:
            fixtures.append(fixture)

    # Look up xLights model name for this semantic group (e.g., LEFT → "90.02 - MH - LEFT")
    xlights_model_name = base_fixtures.xlights_semantic_groups.get(group_id)

    # Note: fixtures list contains FixtureInstance objects (already expanded by get_fixture)
    return FixtureGroup(
        group_id=group_id,
        fixtures=fixtures,  # type: ignore[arg-type]  # Already expanded
        xlights_group=xlights_model_name,  # Use semantic group's xLights model name
    )
