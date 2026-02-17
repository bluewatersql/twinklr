"""Target expansion engine — resolves typed targets to concrete group IDs.

Expands :class:`PlanTarget` objects (group, zone, split) into concrete
``ChoreoGroup.id`` values using :class:`ChoreographyGraph` metadata.

The expansion happens after LLM planning and before rendering:

1. LLM produces a plan with typed targets (zone, split, or group).
2. ``TargetExpander`` resolves each target to concrete group IDs.
3. Placements targeting zones/splits are fanned out into per-group
   placements with ``target.type == GROUP``.

For SEQUENCED modes with zone/split targets, the expander also populates
``CoordinationConfig.group_order`` using spatial sorting.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    SplitDimension,
    TargetType,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag

logger = logging.getLogger(__name__)

# Modes that use window + config (assembler-expanded)
_EXPANSION_MODES = frozenset(
    {
        CoordinationMode.SEQUENCED,
        CoordinationMode.CALL_RESPONSE,
        CoordinationMode.RIPPLE,
    }
)


def _group_target(gid: str) -> PlanTarget:
    """Create a GROUP PlanTarget from a group id."""
    return PlanTarget(type=TargetType.GROUP, id=gid)


class TargetExpander:
    """Expands typed targets to concrete group IDs.

    Resolves zone and split targets using ChoreographyGraph metadata.
    Group targets pass through directly.

    Args:
        choreo_graph: The choreography graph with group definitions.
    """

    def __init__(self, choreo_graph: ChoreographyGraph) -> None:
        self._graph = choreo_graph
        self._valid_group_ids = {g.id for g in choreo_graph.groups}

    def expand_target(self, target: PlanTarget) -> list[str]:
        """Expand a single target to group IDs.

        Args:
            target: The target to expand.

        Returns:
            List of concrete ChoreoGroup.id values.

        Raises:
            ValueError: If target references unknown group/zone/split.
        """
        if target.type == TargetType.GROUP:
            if target.id not in self._valid_group_ids:
                msg = f"Unknown group target: '{target.id}'"
                raise ValueError(msg)
            return [target.id]

        if target.type == TargetType.ZONE:
            try:
                tag = ChoreoTag(target.id)
            except ValueError:
                msg = f"Unknown zone target: '{target.id}' (not a valid ChoreoTag)"
                raise ValueError(msg) from None
            resolved = self._graph.groups_by_tag.get(tag, [])
            if not resolved:
                logger.warning("Zone target '%s' resolves to 0 groups", target.id)
            return list(resolved)

        if target.type == TargetType.SPLIT:
            try:
                split = SplitDimension(target.id)
            except ValueError:
                msg = (
                    f"Unknown split target: '{target.id}' "
                    f"(not a valid SplitDimension)"
                )
                raise ValueError(msg) from None
            resolved = self._graph.groups_by_split.get(split, [])
            if not resolved:
                logger.warning("Split target '%s' resolves to 0 groups", target.id)
            return list(resolved)

        msg = f"Unknown target type: '{target.type}'"
        raise ValueError(msg)

    def expand_targets(self, targets: list[PlanTarget]) -> list[str]:
        """Expand a list of targets to a deduplicated list of group IDs.

        Preserves first-seen order for deterministic output.

        Args:
            targets: List of targets to expand.

        Returns:
            Deduplicated list of concrete group IDs.
        """
        seen: set[str] = set()
        result: list[str] = []
        for target in targets:
            for gid in self.expand_target(target):
                if gid not in seen:
                    seen.add(gid)
                    result.append(gid)
        return result

    def expand_placement(self, placement: GroupPlacement) -> list[GroupPlacement]:
        """Expand a placement's target to per-group placements.

        For GROUP targets, returns the placement unchanged.
        For ZONE/SPLIT targets, returns one placement per resolved group,
        each with a concrete GROUP target.

        Args:
            placement: Placement with a typed target.

        Returns:
            List of placements with concrete GROUP targets.
        """
        group_ids = self.expand_target(placement.target)
        if not group_ids:
            return []

        if len(group_ids) == 1 and placement.target.type == TargetType.GROUP:
            # Already a concrete group target — pass through
            return [placement]

        # Multiple groups or zone/split → fan out to per-group placements
        expanded: list[GroupPlacement] = []
        for gid in group_ids:
            expanded.append(
                placement.model_copy(
                    update={
                        "placement_id": f"{placement.placement_id}_{gid.lower()}",
                        "target": _group_target(gid),
                    },
                )
            )
        return expanded

    def expand_plan(self, plan: CoordinationPlan) -> CoordinationPlan:
        """Expand all targets in a coordination plan.

        For UNIFIED/COMPLEMENTARY modes, expands placements to per-group
        placements.  For SEQUENCED modes, populates
        ``config.group_order`` if empty.

        Args:
            plan: Plan with typed targets.

        Returns:
            New plan with all targets resolved to concrete groups.
        """
        expanded_group_ids = self.expand_targets(plan.targets)

        if plan.coordination_mode in _EXPANSION_MODES:
            # SEQUENCED/CALL_RESPONSE/RIPPLE: populate group_order
            config = plan.config
            if config is not None and not config.group_order:
                config = CoordinationConfig(
                    group_order=expanded_group_ids,
                    step_unit=config.step_unit,
                    step_duration=config.step_duration,
                    phase_offset=config.phase_offset,
                    spill_policy=config.spill_policy,
                    spatial_intent=config.spatial_intent,
                )

            # Convert targets to concrete group targets
            concrete_targets = [_group_target(gid) for gid in expanded_group_ids]

            return CoordinationPlan(
                coordination_mode=plan.coordination_mode,
                targets=concrete_targets,
                placements=plan.placements,
                window=plan.window,
                config=config,
            )

        # UNIFIED/COMPLEMENTARY: expand placements
        expanded_placements: list[GroupPlacement] = []
        for placement in plan.placements:
            expanded_placements.extend(self.expand_placement(placement))

        # Derive concrete targets from expanded placements
        seen: set[str] = set()
        resolved_targets: list[PlanTarget] = []
        for p in expanded_placements:
            if p.target.id not in seen:
                seen.add(p.target.id)
                resolved_targets.append(p.target)

        return CoordinationPlan(
            coordination_mode=plan.coordination_mode,
            targets=resolved_targets,
            placements=expanded_placements,
            window=plan.window,
            config=plan.config,
        )


__all__ = [
    "TargetExpander",
]
