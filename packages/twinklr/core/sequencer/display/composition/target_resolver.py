"""Target resolver: maps choreography IDs to xLights element names.

Each choreography ID (``ChoreoGroup.id``) resolves to one or more
xLights element names via the ``XLightsMapping``.  Role-based
resolution uses the ``ChoreographyGraph`` to find IDs by role, then
resolves each through the mapping.
"""

from __future__ import annotations

import logging

from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)

logger = logging.getLogger(__name__)


class TargetResolver:
    """Resolves choreography IDs to xLights element names.

    Uses group-first resolution via :class:`XLightsMapping`.
    Role-based resolution uses :class:`ChoreographyGraph` for the
    role-to-id lookup, then resolves through the mapping.

    Args:
        choreo_graph: Choreography graph for role lookups.
        xlights_mapping: Mapping for name resolution.
    """

    def __init__(
        self,
        choreo_graph: ChoreographyGraph,
        xlights_mapping: XLightsMapping,
    ) -> None:
        self._choreo_graph = choreo_graph
        self._xlights_mapping = xlights_mapping

    def resolve(self, choreo_id: str) -> str:
        """Resolve a choreography ID to a single xLights element name.

        For group-based resolution this returns the group name.
        For multi-model fallback this returns the first model name.

        Args:
            choreo_id: ChoreoGroup.id from the plan.

        Returns:
            xLights element name (single string for backward compatibility).
        """
        names = self._xlights_mapping.resolve(choreo_id)
        return names[0]

    def resolve_all(self, choreo_id: str) -> list[str]:
        """Resolve a choreography ID to all xLights element names.

        Returns all resolved names (useful for model-level fallback).

        Args:
            choreo_id: ChoreoGroup.id from the plan.

        Returns:
            List of xLights element names.
        """
        return self._xlights_mapping.resolve(choreo_id)

    def resolve_roles(self, target_roles: list[str]) -> list[str]:
        """Resolve target roles to a list of element names.

        Finds all groups matching any of the given roles via the
        choreography graph, then resolves each to element names.

        Args:
            target_roles: Role names (e.g., ``["ARCHES", "WINDOWS"]``).

        Returns:
            List of xLights element names for matching groups.
        """
        elements: list[str] = []
        groups_by_role = self._choreo_graph.groups_by_role
        for role in target_roles:
            for choreo_id in groups_by_role.get(role, []):
                names = self._xlights_mapping.resolve(choreo_id)
                elements.extend(names)
        return elements


__all__ = [
    "TargetResolver",
]
