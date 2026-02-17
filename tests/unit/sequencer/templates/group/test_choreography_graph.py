"""Tests for ChoreographyGraph, ChoreoGroup, and spatial/tag lookups.

Tests group-level choreography model including:
- ChoreoGroup construction and field defaults
- ChoreographyGraph computed lookups (groups_by_role, groups_by_tag)
- Spatial sorting via groups_sorted_by(intent)
- get_group lookup
"""

import pytest

from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.display import GroupPosition
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag
from twinklr.core.sequencer.vocabulary.coordination import SpatialIntent
from twinklr.core.sequencer.vocabulary.display import (
    DisplayElementKind,
    DisplayProminence,
    GroupArrangement,
)
from twinklr.core.sequencer.vocabulary.spatial import (
    DepthZone,
    DisplayZone,
    HorizontalZone,
    VerticalZone,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_group(
    id: str,
    *,
    role: str | None = None,
    kind: DisplayElementKind = DisplayElementKind.STRING,
    prominence: DisplayProminence = DisplayProminence.ANCHOR,
    horizontal: HorizontalZone = HorizontalZone.CENTER,
    vertical: VerticalZone = VerticalZone.MID,
    depth: DepthZone = DepthZone.NEAR,
    zone: DisplayZone | None = None,
    arrangement: GroupArrangement = GroupArrangement.HORIZONTAL_ROW,
    fixture_count: int = 1,
    pixel_fraction: float = 0.1,
    tags: list[ChoreoTag] | None = None,
) -> ChoreoGroup:
    """Helper to create a ChoreoGroup with sensible defaults."""
    return ChoreoGroup(
        id=id,
        role=role or id,
        element_kind=kind,
        prominence=prominence,
        position=GroupPosition(
            horizontal=horizontal,
            vertical=vertical,
            depth=depth,
            zone=zone,
        ),
        arrangement=arrangement,
        fixture_count=fixture_count,
        pixel_fraction=pixel_fraction,
        tags=tags or [],
    )


def _make_graph(*groups: ChoreoGroup) -> ChoreographyGraph:
    """Helper to create a ChoreographyGraph from groups."""
    return ChoreographyGraph(
        graph_id="test_graph",
        groups=list(groups),
    )


# ---------------------------------------------------------------------------
# ChoreoGroup
# ---------------------------------------------------------------------------


class TestChoreoGroup:
    """Tests for ChoreoGroup model."""

    def test_minimal_construction(self) -> None:
        """ChoreoGroup can be created with just id and role."""
        group = ChoreoGroup(id="ARCHES", role="ARCHES")
        assert group.id == "ARCHES"
        assert group.role == "ARCHES"
        assert group.tags == []
        assert group.fixture_count == 1
        assert group.pixel_fraction == 0.0

    def test_full_construction(self) -> None:
        """ChoreoGroup with all fields populates correctly."""
        group = _make_group(
            "ARCHES",
            role="ARCHES",
            kind=DisplayElementKind.ARCH,
            prominence=DisplayProminence.ANCHOR,
            horizontal=HorizontalZone.FULL_WIDTH,
            zone=DisplayZone.YARD,
            fixture_count=10,
            pixel_fraction=0.15,
            tags=[ChoreoTag.YARD, ChoreoTag.HOUSE],
        )
        assert group.id == "ARCHES"
        assert group.element_kind == DisplayElementKind.ARCH
        assert group.prominence == DisplayProminence.ANCHOR
        assert group.fixture_count == 10
        assert ChoreoTag.YARD in group.tags
        assert ChoreoTag.HOUSE in group.tags

    def test_frozen(self) -> None:
        """ChoreoGroup is immutable after creation."""
        from pydantic import ValidationError

        group = ChoreoGroup(id="TEST", role="TEST")
        with pytest.raises(ValidationError):
            group.id = "CHANGED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChoreographyGraph - Lookups
# ---------------------------------------------------------------------------


class TestChoreographyGraphLookups:
    """Tests for ChoreographyGraph lookup methods."""

    def test_get_group_found(self) -> None:
        """get_group returns the matching group."""
        group = _make_group("ARCHES")
        graph = _make_graph(group)
        assert graph.get_group("ARCHES") is not None
        assert graph.get_group("ARCHES").id == "ARCHES"  # type: ignore[union-attr]

    def test_get_group_not_found(self) -> None:
        """get_group returns None for unknown id."""
        graph = _make_graph(_make_group("ARCHES"))
        assert graph.get_group("NONEXISTENT") is None

    def test_groups_by_role(self) -> None:
        """groups_by_role groups ids by their role."""
        graph = _make_graph(
            _make_group("ARCH_LEFT", role="ARCHES"),
            _make_group("ARCH_RIGHT", role="ARCHES"),
            _make_group("MEGA_TREE", role="MEGA_TREE"),
        )
        by_role = graph.groups_by_role
        assert set(by_role["ARCHES"]) == {"ARCH_LEFT", "ARCH_RIGHT"}
        assert by_role["MEGA_TREE"] == ["MEGA_TREE"]

    def test_groups_by_tag(self) -> None:
        """groups_by_tag groups ids by their tags."""
        graph = _make_graph(
            _make_group("ARCHES", tags=[ChoreoTag.YARD, ChoreoTag.ROOF]),
            _make_group("MEGA_TREE", tags=[ChoreoTag.YARD]),
            _make_group("OUTLINE", tags=[ChoreoTag.HOUSE]),
        )
        by_tag = graph.groups_by_tag
        assert set(by_tag[ChoreoTag.YARD]) == {"ARCHES", "MEGA_TREE"}
        assert by_tag[ChoreoTag.ROOF] == ["ARCHES"]
        assert by_tag[ChoreoTag.HOUSE] == ["OUTLINE"]

    def test_groups_by_tag_empty(self) -> None:
        """groups_by_tag returns empty dict when no tags present."""
        graph = _make_graph(_make_group("ARCHES"))
        assert graph.groups_by_tag == {}

    def test_minimum_one_group(self) -> None:
        """ChoreographyGraph requires at least one group."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChoreographyGraph(graph_id="empty", groups=[])


# ---------------------------------------------------------------------------
# ChoreographyGraph - Spatial Sorting
# ---------------------------------------------------------------------------


class TestChoreographyGraphSpatialSorting:
    """Tests for spatial sorting via groups_sorted_by."""

    def test_l2r_sorts_by_horizontal(self) -> None:
        """L2R intent sorts groups left-to-right."""
        left = _make_group("LEFT", horizontal=HorizontalZone.LEFT)
        center = _make_group("CENTER", horizontal=HorizontalZone.CENTER)
        right = _make_group("RIGHT", horizontal=HorizontalZone.RIGHT)
        graph = _make_graph(right, left, center)

        sorted_ids = [g.id for g in graph.groups_sorted_by(SpatialIntent.L2R)]
        assert sorted_ids == ["LEFT", "CENTER", "RIGHT"]

    def test_r2l_sorts_reversed(self) -> None:
        """R2L intent sorts groups right-to-left."""
        left = _make_group("LEFT", horizontal=HorizontalZone.LEFT)
        right = _make_group("RIGHT", horizontal=HorizontalZone.RIGHT)
        graph = _make_graph(left, right)

        sorted_ids = [g.id for g in graph.groups_sorted_by(SpatialIntent.R2L)]
        assert sorted_ids == ["RIGHT", "LEFT"]

    def test_b2t_sorts_by_vertical(self) -> None:
        """B2T intent sorts groups bottom-to-top."""
        low = _make_group("LOW", vertical=VerticalZone.LOW)
        high = _make_group("HIGH", vertical=VerticalZone.HIGH)
        graph = _make_graph(high, low)

        sorted_ids = [g.id for g in graph.groups_sorted_by(SpatialIntent.B2T)]
        assert sorted_ids == ["LOW", "HIGH"]

    def test_none_preserves_declaration_order(self) -> None:
        """NONE intent preserves original declaration order."""
        a = _make_group("A")
        b = _make_group("B")
        c = _make_group("C")
        graph = _make_graph(b, c, a)

        sorted_ids = [g.id for g in graph.groups_sorted_by(SpatialIntent.NONE)]
        assert sorted_ids == ["B", "C", "A"]

    def test_groups_without_position_sort_last(self) -> None:
        """Groups without position sort after positioned groups."""
        positioned = _make_group("POS", horizontal=HorizontalZone.LEFT)
        unpositioned = ChoreoGroup(id="NOPOS", role="TEST")
        graph = _make_graph(unpositioned, positioned)

        sorted_ids = [g.id for g in graph.groups_sorted_by(SpatialIntent.L2R)]
        assert sorted_ids == ["POS", "NOPOS"]


# ---------------------------------------------------------------------------
# ChoreographyGraph - Planner Summary
# ---------------------------------------------------------------------------


class TestChoreographyGraphPlannerSummary:
    """Tests for to_planner_summary export."""

    def test_summary_includes_core_fields(self) -> None:
        """Planner summary includes role, fixture count, prominence, and detail."""
        graph = _make_graph(
            _make_group(
                "ARCHES",
                role="ARCHES",
                kind=DisplayElementKind.ARCH,
                prominence=DisplayProminence.ANCHOR,
                fixture_count=10,
                pixel_fraction=0.15,
            ),
        )
        summaries = graph.to_planner_summary()
        assert len(summaries) == 1
        s = summaries[0]
        assert s["role_key"] == "ARCHES"
        assert s["model_count"] == 10
        assert s["element_kind"] == "ARCH"
        assert s["prominence"] == "ANCHOR"
        assert s["detail_capability"] == "MEDIUM"

    def test_summary_includes_tags(self) -> None:
        """Planner summary includes tags when present."""
        graph = _make_graph(
            _make_group("ARCHES", tags=[ChoreoTag.YARD, ChoreoTag.ROOF]),
        )
        summaries = graph.to_planner_summary()
        assert "tags" in summaries[0]
        assert "YARD" in summaries[0]["tags"]

    def test_summary_excludes_empty_tags(self) -> None:
        """Planner summary omits tags when empty."""
        graph = _make_graph(_make_group("ARCHES"))
        summaries = graph.to_planner_summary()
        assert "tags" not in summaries[0]
