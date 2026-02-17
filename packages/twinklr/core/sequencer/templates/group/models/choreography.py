"""Choreography graph models — LLM-optimized display configuration.

Models for defining the choreographic representation of a display.
Optimized for LLM planning at group-level granularity (~15-25 groups
per display, not individual models).

Separation of concerns:

- **ChoreographyGraph**: What the LLM needs to plan choreography.
  Physical descriptions, visual weight, spatial relationships, tags.
- **XLightsMapping** (separate module): How choreography IDs resolve
  to xLights element names for XSQ output.

The ``ChoreoGroup.id`` field replaces ``DisplayGroup.group_id`` to
avoid confusion with other group concepts in the system.  Tags use
the closed ``ChoreoTag`` enum for deterministic bidirectional resolution.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, ConfigDict, Field, computed_field

from twinklr.core.sequencer.templates.group.models.display import GroupPosition
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag
from twinklr.core.sequencer.vocabulary.coordination import SpatialIntent
from twinklr.core.sequencer.vocabulary.display import (
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
)
from twinklr.core.sequencer.vocabulary.spatial import HorizontalZone


class ChoreoGroup(BaseModel):
    """A targetable display group for choreography planning.

    Represents a group of physical display elements at the abstraction
    level a choreographer thinks at — e.g., "Arches" (not "Arch 1").

    Attributes:
        id: Planning identifier (e.g., ``ARCHES``, ``MEGA_TREE``).
        role: Physical type / role name (e.g., ``ARCHES``, ``TREES``).
        element_kind: Detailed physical form of the element.
        prominence: Visual weight driving lane assignment.
        position: Categorical spatial position for spatial sorting.
        arrangement: How models within the group are laid out.
        fixture_count: Number of physical models in this group.
        pixel_fraction: Fraction of total display pixels (0.0-1.0).
        tags: Well-defined choreographic grouping tags.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str

    # Physical description
    element_kind: DisplayElementKind | None = None
    prominence: DisplayProminence | None = None
    arrangement: GroupArrangement | None = None

    # Spatial position
    position: GroupPosition | None = None

    # Metrics
    fixture_count: int = Field(default=1, ge=1)
    pixel_fraction: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of total display pixels (0.0-1.0)",
    )

    # Choreographic grouping
    tags: list[ChoreoTag] = Field(default_factory=list)


# Center reference for center-outward sorting
_HORIZONTAL_CENTER: int = HorizontalZone.CENTER.sort_key()


class ChoreographyGraph(BaseModel):
    """Complete choreographic display configuration.

    LLM-optimized representation of a display.  Each ``ChoreoGroup``
    represents a group of physical elements at the level a choreographer
    plans against.

    Provides computed lookups (``groups_by_role``, ``groups_by_tag``)
    and spatial sorting (``groups_sorted_by``) for planning and rendering.

    Attributes:
        graph_id: Unique identifier for this graph.
        groups: List of choreography groups (min 1).
    """

    model_config = ConfigDict(extra="forbid")

    graph_id: str
    groups: list[ChoreoGroup] = Field(min_length=1)

    # -------------------------------------------------------------------
    # Computed lookups
    # -------------------------------------------------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def groups_by_role(self) -> dict[str, list[str]]:
        """Map role -> list of ChoreoGroup ids."""
        result: dict[str, list[str]] = {}
        for g in self.groups:
            result.setdefault(g.role, []).append(g.id)
        return result

    @computed_field  # type: ignore[prop-decorator]
    @property
    def groups_by_tag(self) -> dict[ChoreoTag, list[str]]:
        """Map tag -> list of ChoreoGroup ids.

        Only tags that appear on at least one group are included.
        """
        result: dict[ChoreoTag, list[str]] = {}
        for g in self.groups:
            for tag in g.tags:
                result.setdefault(tag, []).append(g.id)
        return result

    # -------------------------------------------------------------------
    # Lookup
    # -------------------------------------------------------------------

    def get_group(self, group_id: str) -> ChoreoGroup | None:
        """Get group by id, or None if not found."""
        return next((g for g in self.groups if g.id == group_id), None)

    # -------------------------------------------------------------------
    # Spatial queries
    # -------------------------------------------------------------------

    def groups_sorted_by(self, intent: SpatialIntent) -> list[ChoreoGroup]:
        """Groups ordered by spatial intent.

        Args:
            intent: The spatial direction for ordering.

        Returns:
            Groups sorted according to the intent.
            Groups without a position sort after groups with positions.
            ``NONE`` returns groups in declaration order.
            ``RANDOM`` returns groups in a shuffled order.
        """
        if intent == SpatialIntent.NONE:
            return list(self.groups)

        if intent == SpatialIntent.RANDOM:
            result = list(self.groups)
            random.shuffle(result)
            return result

        return self._sort_by_intent(list(self.groups), intent)

    @staticmethod
    def _sort_by_intent(
        groups: list[ChoreoGroup],
        intent: SpatialIntent,
    ) -> list[ChoreoGroup]:
        """Sort groups by spatial intent using position sort keys."""

        def _h_key(g: ChoreoGroup) -> int:
            if g.position is None:
                return 999
            return g.position.horizontal.sort_key()

        def _v_key(g: ChoreoGroup) -> int:
            if g.position is None:
                return 999
            return g.position.vertical.sort_key()

        def _d_key(g: ChoreoGroup) -> int:
            if g.position is None:
                return 999
            return g.position.depth.sort_key()

        # -- Horizontal --------------------------------------------------
        if intent == SpatialIntent.L2R:
            return sorted(groups, key=_h_key)

        if intent == SpatialIntent.R2L:
            return sorted(groups, key=_h_key, reverse=True)

        if intent == SpatialIntent.C2O:

            def c2o_key(g: ChoreoGroup) -> int:
                if g.position is None:
                    return 999
                return abs(g.position.horizontal.sort_key() - _HORIZONTAL_CENTER)

            return sorted(groups, key=c2o_key)

        if intent == SpatialIntent.O2C:

            def o2c_key(g: ChoreoGroup) -> int:
                if g.position is None:
                    return -1
                return abs(g.position.horizontal.sort_key() - _HORIZONTAL_CENTER)

            return sorted(groups, key=o2c_key, reverse=True)

        # -- Vertical ----------------------------------------------------
        if intent == SpatialIntent.B2T:
            return sorted(groups, key=_v_key)

        if intent == SpatialIntent.T2B:
            return sorted(groups, key=_v_key, reverse=True)

        # -- Depth -------------------------------------------------------
        if intent == SpatialIntent.F2B:
            return sorted(groups, key=_d_key)

        if intent == SpatialIntent.B2F:
            return sorted(groups, key=_d_key, reverse=True)

        return list(groups)

    # -------------------------------------------------------------------
    # Planner context export
    # -------------------------------------------------------------------

    def to_planner_summary(self) -> list[dict[str, object]]:
        """Export groups as enriched dicts for LLM planner prompts.

        Each dict includes the group's identity, physical metadata, and
        spatial position so the planner can make informed decisions.

        Returns:
            List of dicts with keys: ``role_key``, ``model_count``,
            ``element_kind``, ``arrangement``, ``prominence``,
            ``pixel_fraction``, ``horizontal``, ``vertical``, ``depth``,
            ``zone``, ``tags``.
        """
        result: list[dict[str, object]] = []
        for g in self.groups:
            summary: dict[str, object] = {
                "role_key": g.role,
                "model_count": g.fixture_count,
            }
            if g.element_kind is not None:
                summary["element_kind"] = g.element_kind.value
            if g.arrangement is not None:
                summary["arrangement"] = g.arrangement.value
            if g.prominence is not None:
                summary["prominence"] = g.prominence.value
            if g.pixel_fraction > 0.0:
                summary["pixel_fraction"] = round(g.pixel_fraction, 3)
            if g.position is not None:
                summary["horizontal"] = g.position.horizontal.value
                summary["vertical"] = g.position.vertical.value
                summary["depth"] = g.position.depth.value
                if g.position.zone is not None:
                    summary["zone"] = g.position.zone.value
            if g.tags:
                summary["tags"] = [t.value for t in g.tags]
            result.append(summary)
        return result


__all__ = [
    "ChoreoGroup",
    "ChoreographyGraph",
]
