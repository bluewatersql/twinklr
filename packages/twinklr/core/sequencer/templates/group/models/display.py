"""Display graph models (v2).

Models for defining display topology, hierarchy, spatial position, and
physical characteristics of display groups.

xLights supports two kinds of targetable elements:
- **Individual models** (e.g., "Arch 1") — a single physical element.
- **Model groups** (e.g., "61 - Arches") — a set of models sequenced as one.

Both use ``type="model"`` in the XSQ XML; the distinction is semantic.

Each ``DisplayGroup`` entry maps 1:1 to an xLights element.  The plan
references entries by ``group_id``, and the ``TargetResolver`` maps that
to the xLights ``display_name``.

**v2 additions (over v1):**
- Hierarchy via ``parent_group_id`` on ``DisplayGroup``.
- Categorical spatial position via ``GroupPosition`` (replacing float-based).
- Physical metadata: ``element_kind``, ``arrangement``, ``pixel_density``,
  ``prominence``, ``pixel_fraction``.
- Hierarchy traversal and spatial sorting methods on ``DisplayGraph``.
"""

from __future__ import annotations

import random
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from twinklr.core.sequencer.vocabulary.coordination import SpatialIntent
from twinklr.core.sequencer.vocabulary.display import (
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
    PixelDensity,
)
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)


class ElementType(str, Enum):
    """xLights element targeting type.

    Determines how effects are placed in the sequence:
    - MODEL: Effect targets a single physical model.
    - MODEL_GROUP: Effect targets a group; xLights renders across all
      member models as a single canvas.
    """

    MODEL = "model"
    MODEL_GROUP = "model_group"


class GroupPosition(BaseModel):
    """Categorical spatial position for a display group.

    All axes use enum values rather than raw floats so the LLM can
    reason over them directly.  The composition engine uses
    ``sort_key()`` on each enum to order groups for spatial
    coordination (e.g., L2R sweeps).

    Attributes:
        horizontal: Left-to-right position.
        vertical: Bottom-to-top position.
        depth: Front-to-back position.
        zone: Logical zone of the display (HOUSE, YARD, etc.).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizontal: HorizontalZone = HorizontalZone.CENTER
    vertical: VerticalZone = VerticalZone.MID
    depth: DepthZone = DepthZone.NEAR
    zone: DisplayZone | None = None


class DisplayGroup(BaseModel):
    """Single display group definition (v2).

    Represents a targetable xLights element — either an individual model
    or a model group.

    The ``display_name`` must match the exact xLights element name
    (e.g., ``"61 - Arches"``) since groups cannot be created in the
    sequence file alone — they must already exist in the xLights layout.

    Attributes:
        group_id: Unique identifier (UPPER_SNAKE_CASE).
        role: Role name for group-level targeting.
        display_name: Exact xLights element name.
        parent_group_id: Parent group for hierarchy (None = top-level).
        element_type: MODEL or MODEL_GROUP.
        element_kind: Physical type (ARCH, TREE, MATRIX, etc.).
        arrangement: How models are laid out (HORIZONTAL_ROW, GRID, etc.).
        pixel_density: Effect suitability category (LOW, MEDIUM, HIGH).
        prominence: Visual weight (ACCENT, SUPPORTING, ANCHOR, HERO).
        position: Categorical spatial position.
        fixture_count: Number of models in this group.
        pixel_fraction: Fraction of total display pixels (0.0-1.0).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Identity
    group_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str
    display_name: str

    # Hierarchy
    parent_group_id: str | None = None
    element_type: ElementType = Field(
        default=ElementType.MODEL_GROUP,
        description="MODEL or MODEL_GROUP",
    )

    # Physical description
    element_kind: DisplayElementKind | None = None
    arrangement: GroupArrangement | None = None
    pixel_density: PixelDensity | None = None
    prominence: DisplayProminence | None = None

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


# Center reference for center-outward sorting
_HORIZONTAL_CENTER: int = HorizontalZone.CENTER.sort_key()


class DisplayGraph(BaseModel):
    """Complete display configuration with hierarchy and spatial metadata.

    Each entry in ``groups`` maps 1:1 to an xLights element.  The
    mapping from ``group_id`` to ``display_name`` is provided externally.

    **Hierarchy:** Groups form a tree via ``parent_group_id``.  Roots
    have ``parent_group_id=None``.  Cycles and dangling references are
    rejected at validation time.

    **Spatial sorting:** ``groups_sorted_by(intent)`` orders groups
    using their ``GroupPosition`` for spatial coordination patterns
    (L2R, R2L, C2O, O2C, B2T, T2B, F2B, B2F).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "display-graph.v2"
    display_id: str
    display_name: str
    groups: list[DisplayGroup] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_hierarchy(self) -> DisplayGraph:
        """Validate hierarchy integrity.

        Checks:
        - Every ``parent_group_id`` references an existing ``group_id``.
        - No cycles in the hierarchy.
        """
        group_ids = {g.group_id for g in self.groups}

        # Check all parent refs are valid
        for g in self.groups:
            if g.parent_group_id is not None and g.parent_group_id not in group_ids:
                msg = (
                    f"parent_group_id '{g.parent_group_id}' on group "
                    f"'{g.group_id}' does not reference an existing group"
                )
                raise ValueError(msg)

        # Check for cycles via path tracing
        parent_map: dict[str, str | None] = {g.group_id: g.parent_group_id for g in self.groups}
        for gid in group_ids:
            visited: set[str] = set()
            current: str | None = gid
            while current is not None:
                if current in visited:
                    msg = f"Cycle detected in hierarchy involving group '{current}'"
                    raise ValueError(msg)
                visited.add(current)
                current = parent_map.get(current)

        return self

    # -------------------------------------------------------------------
    # Backward-compatible computed fields
    # -------------------------------------------------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def groups_by_role(self) -> dict[str, list[str]]:
        """Map role -> list of group_ids (includes all groups)."""
        result: dict[str, list[str]] = {}
        for g in self.groups:
            result.setdefault(g.role, []).append(g.group_id)
        return result

    # -------------------------------------------------------------------
    # Lookup
    # -------------------------------------------------------------------

    def get_group(self, group_id: str) -> DisplayGroup | None:
        """Get group by ID, or None if not found."""
        return next((g for g in self.groups if g.group_id == group_id), None)

    # -------------------------------------------------------------------
    # Hierarchy traversal
    # -------------------------------------------------------------------

    def get_children(self, group_id: str) -> list[DisplayGroup]:
        """Direct children of the given group."""
        return [g for g in self.groups if g.parent_group_id == group_id]

    def get_descendants(self, group_id: str) -> list[DisplayGroup]:
        """All descendants (recursive depth-first)."""
        result: list[DisplayGroup] = []
        stack = list(self.get_children(group_id))
        while stack:
            child = stack.pop()
            result.append(child)
            stack.extend(self.get_children(child.group_id))
        return result

    def get_parent(self, group_id: str) -> DisplayGroup | None:
        """Parent group, or None if top-level."""
        group = self.get_group(group_id)
        if group is None or group.parent_group_id is None:
            return None
        return self.get_group(group.parent_group_id)

    def get_ancestors(self, group_id: str) -> list[DisplayGroup]:
        """Ancestor chain from immediate parent to root."""
        result: list[DisplayGroup] = []
        current = self.get_parent(group_id)
        while current is not None:
            result.append(current)
            current = self.get_parent(current.group_id)
        return result

    def get_root_groups(self) -> list[DisplayGroup]:
        """Top-level groups (parent_group_id is None)."""
        return [g for g in self.groups if g.parent_group_id is None]

    def get_siblings(self, group_id: str) -> list[DisplayGroup]:
        """Other groups sharing the same parent (excludes self)."""
        group = self.get_group(group_id)
        if group is None:
            return []
        return [
            g
            for g in self.groups
            if g.parent_group_id == group.parent_group_id and g.group_id != group_id
        ]

    # -------------------------------------------------------------------
    # Spatial queries
    # -------------------------------------------------------------------

    def groups_in_zone(self, zone: DisplayZone) -> list[DisplayGroup]:
        """All groups whose position is in the given zone."""
        return [g for g in self.groups if g.position is not None and g.position.zone == zone]

    def groups_sorted_by(self, intent: SpatialIntent) -> list[DisplayGroup]:
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
        groups: list[DisplayGroup],
        intent: SpatialIntent,
    ) -> list[DisplayGroup]:
        """Sort groups by spatial intent using position sort keys.

        Supports horizontal (L2R, R2L, C2O, O2C), vertical (B2T, T2B),
        and depth (F2B, B2F) intents.  Groups without a position are
        pushed to the end (or beginning for reversed sorts).
        """

        def _h_key(g: DisplayGroup) -> int:
            if g.position is None:
                return 999
            return g.position.horizontal.sort_key()

        def _v_key(g: DisplayGroup) -> int:
            if g.position is None:
                return 999
            return g.position.vertical.sort_key()

        def _d_key(g: DisplayGroup) -> int:
            if g.position is None:
                return 999
            return g.position.depth.sort_key()

        # -- Horizontal --------------------------------------------------
        if intent == SpatialIntent.L2R:
            return sorted(groups, key=_h_key)

        if intent == SpatialIntent.R2L:
            return sorted(groups, key=_h_key, reverse=True)

        if intent == SpatialIntent.C2O:

            def c2o_key(g: DisplayGroup) -> int:
                if g.position is None:
                    return 999
                return abs(g.position.horizontal.sort_key() - _HORIZONTAL_CENTER)

            return sorted(groups, key=c2o_key)

        if intent == SpatialIntent.O2C:

            def o2c_key(g: DisplayGroup) -> int:
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
            List of dicts with keys: ``role_key``, ``group_type``,
            ``model_count``, ``element_kind``, ``arrangement``,
            ``pixel_density``, ``prominence``, ``pixel_fraction``,
            ``horizontal``, ``vertical``, ``depth``, ``zone``,
            ``parent_group``.
        """
        result: list[dict[str, object]] = []
        for g in self.groups:
            summary: dict[str, object] = {
                "role_key": g.role,
                "group_type": g.element_type.value,
                "model_count": g.fixture_count,
            }
            if g.element_kind is not None:
                summary["element_kind"] = g.element_kind.value
            if g.arrangement is not None:
                summary["arrangement"] = g.arrangement.value
            if g.pixel_density is not None:
                summary["pixel_density"] = g.pixel_density.value
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
            if g.parent_group_id is not None:
                summary["parent_group"] = g.parent_group_id
            result.append(summary)
        return result


__all__ = [
    "DisplayGraph",
    "DisplayGroup",
    "ElementType",
    "GroupPosition",
]
