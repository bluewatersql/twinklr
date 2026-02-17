"""xLights element mapping — resolves choreography IDs to xLights elements.

Thin mapping layer that bridges the choreographic model
(``ChoreographyGraph``) to xLights element names for XSQ output.

Resolution strategy (group-first, model fallback):

1. If ``group_name`` exists → use the xLights model group.
2. If ``model_names`` exist → fall back to individual model names.
3. Otherwise → fall back to using the ``choreo_id`` as the element name.

This mirrors the moving heads mapping pattern.  In v0 the mapping is
a direct 1:1 (choreo_id → group_name).  Tag-based sub-group splits
(``tag_splits``) are reserved for future work when the xLights layout
parser can auto-discover them.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class XLightsGroupMapping(BaseModel):
    """Mapping entry for a single choreography group.

    Attributes:
        choreo_id: ChoreoGroup.id this entry maps.
        group_name: xLights model group name (preferred resolution target).
        model_names: Individual xLights model names (fallback).
        tag_splits: Tag -> model names for sub-group patterns (future).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    choreo_id: str
    group_name: str | None = None
    model_names: list[str] = Field(default_factory=list)
    tag_splits: dict[str, list[str]] = Field(default_factory=dict)


class XLightsMapping(BaseModel):
    """Maps choreography IDs to xLights elements.

    Resolution strategy: group-first with model-level fallback.

    Attributes:
        entries: List of group mapping entries.
    """

    model_config = ConfigDict(extra="forbid")

    entries: list[XLightsGroupMapping] = Field(default_factory=list)

    def _index(self) -> dict[str, XLightsGroupMapping]:
        """Build choreo_id -> entry lookup (not cached; graph is small)."""
        return {e.choreo_id: e for e in self.entries}

    def resolve(self, choreo_id: str) -> list[str]:
        """Resolve a choreography ID to xLights element name(s).

        Strategy:
        1. group_name exists → ``[group_name]``
        2. model_names exist → model_names list
        3. Unknown/empty → ``[choreo_id]`` (fallback)

        Args:
            choreo_id: ChoreoGroup.id to resolve.

        Returns:
            List of xLights element names (usually 1 for group resolution).
        """
        index = self._index()
        entry = index.get(choreo_id)

        if entry is None:
            logger.debug(
                "Choreo ID '%s' not in XLightsMapping, using as element name",
                choreo_id,
            )
            return [choreo_id]

        if entry.group_name is not None:
            return [entry.group_name]

        if entry.model_names:
            return list(entry.model_names)

        logger.debug(
            "Choreo ID '%s' has no group_name or model_names, using as element name",
            choreo_id,
        )
        return [choreo_id]

    def resolve_all(self) -> dict[str, list[str]]:
        """Resolve all entries to a choreo_id -> element names mapping.

        Returns:
            Dict mapping each choreo_id to its resolved element name(s).
        """
        return {entry.choreo_id: self.resolve(entry.choreo_id) for entry in self.entries}

    def has_entry(self, choreo_id: str) -> bool:
        """Check if a choreo_id has a mapping entry.

        Args:
            choreo_id: ChoreoGroup.id to check.

        Returns:
            True if an entry exists for this ID.
        """
        return any(e.choreo_id == choreo_id for e in self.entries)


__all__ = [
    "XLightsGroupMapping",
    "XLightsMapping",
]
