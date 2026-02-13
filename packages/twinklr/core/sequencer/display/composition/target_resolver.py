"""Target resolver: maps group_ids to xLights element names.

Each ``group_id`` in the plan maps directly to a ``DisplayGroup``
entry in the ``DisplayGraph``. The ``display_name`` on that entry
is the exact xLights element name used in the XSQ output.

The DisplayGraph is provided externally (from fixture config or
user mapping) — the renderer does not create or infer groups.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.templates.group.models.display import DisplayGraph

logger = logging.getLogger(__name__)


class TargetResolver:
    """Resolves group_ids from the plan to xLights element names.

    Direct 1:1 mapping: ``group_id`` → ``DisplayGroup.display_name``.
    Unknown IDs fall back to using the group_id as the element name
    (with a debug log warning).

    The DisplayGraph determines whether the target is a model group
    (e.g., ``"61 - Arches"``) or an individual model (e.g.,
    ``"Arch 1"``). The resolver does not distinguish — it just maps
    the ID to the configured display_name.

    Args:
        display_graph: Display graph for name resolution.
    """

    def __init__(self, display_graph: DisplayGraph) -> None:
        self._display_graph = display_graph
        # Build lookup: group_id → display_name
        self._group_map: dict[str, str] = {}
        for group in display_graph.groups:
            self._group_map[group.group_id] = group.display_name

    def resolve(self, group_id: str) -> str:
        """Resolve a group_id to an xLights element name.

        Args:
            group_id: Group ID from the plan.

        Returns:
            xLights element name.
        """
        if group_id in self._group_map:
            return self._group_map[group_id]

        # Fallback: use group_id directly as element name
        logger.debug(
            "Group '%s' not in DisplayGraph, using as element name directly",
            group_id,
        )
        return group_id

    def resolve_roles(self, target_roles: list[str]) -> list[str]:
        """Resolve target_roles to a list of element names.

        Finds all groups matching any of the given roles.

        Args:
            target_roles: Role names (e.g., ["OUTLINE", "ARCHES"]).

        Returns:
            List of xLights element names for matching groups.
        """
        elements: list[str] = []
        for group in self._display_graph.groups:
            if group.role in target_roles:
                elements.append(group.display_name)
        return elements


__all__ = [
    "TargetResolver",
]
