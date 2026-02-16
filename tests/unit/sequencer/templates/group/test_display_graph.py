"""Tests for DisplayGraph hierarchy, spatial ordering, and physical metadata.

Tests the v2 DisplayGraph with hierarchy (parent_group_id), categorical
spatial positions (GroupPosition), physical metadata (element_kind,
arrangement, pixel_density, prominence), and the spatial sorting methods
that bridge SpatialIntent to group ordering.
"""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    ElementType,
    GroupPosition,
)
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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_group(
    group_id: str,
    *,
    parent: str | None = None,
    element_type: ElementType = ElementType.MODEL_GROUP,
    kind: DisplayElementKind = DisplayElementKind.STRING,
    arrangement: GroupArrangement = GroupArrangement.HORIZONTAL_ROW,
    density: PixelDensity = PixelDensity.MEDIUM,
    prominence: DisplayProminence = DisplayProminence.ANCHOR,
    horizontal: HorizontalZone = HorizontalZone.CENTER,
    vertical: VerticalZone = VerticalZone.MID,
    depth: DepthZone = DepthZone.NEAR,
    zone: DisplayZone | None = None,
    pixel_fraction: float = 0.1,
    fixture_count: int = 1,
) -> DisplayGroup:
    """Helper to create a DisplayGroup with full metadata."""
    return DisplayGroup(
        group_id=group_id,
        role=group_id,
        display_name=group_id,
        element_type=element_type,
        parent_group_id=parent,
        element_kind=kind,
        arrangement=arrangement,
        pixel_density=density,
        prominence=prominence,
        position=GroupPosition(
            horizontal=horizontal,
            vertical=vertical,
            depth=depth,
            zone=zone,
        ),
        pixel_fraction=pixel_fraction,
        fixture_count=fixture_count,
    )


@pytest.fixture()
def sample_graph() -> DisplayGraph:
    """Realistic display hierarchy for testing.

    ALL_DISPLAY (MODEL_GROUP, parent of all)
    ├── HOUSE (MODEL_GROUP, parent of OUTLINE + WINDOWS)
    │   ├── OUTLINE (MODEL_GROUP, STRING, h=FULL_WIDTH, v=HIGH, d=FAR)
    │   └── WINDOWS (MODEL_GROUP, WINDOW, h=CENTER, v=MID, d=MID)
    ├── YARD (MODEL_GROUP, parent of MEGA_TREE + ARCHES + CANDY_CANES)
    │   ├── MEGA_TREE (MODEL, TREE, h=CENTER, v=FULL_HEIGHT, d=NEAR)
    │   ├── ARCHES (MODEL_GROUP, ARCH, h=FULL_WIDTH, v=LOW, d=NEAR)
    │   └── CANDY_CANES (MODEL_GROUP, CANDY_CANE, h=RIGHT, v=LOW, d=NEAR)
    └── ACCENT_ZONE (MODEL_GROUP, parent of SANTA)
        └── SANTA (MODEL_GROUP, PROP, h=LEFT, v=GROUND, d=NEAR)
    """
    return DisplayGraph(
        display_id="test_display",
        display_name="Test Display",
        groups=[
            _make_group(
                "ALL_DISPLAY",
                kind=DisplayElementKind.MIXED,
                arrangement=GroupArrangement.CLUSTER,
                pixel_fraction=1.0,
            ),
            _make_group(
                "HOUSE",
                parent="ALL_DISPLAY",
                kind=DisplayElementKind.MIXED,
                arrangement=GroupArrangement.CLUSTER,
                pixel_fraction=0.35,
            ),
            _make_group(
                "OUTLINE",
                parent="HOUSE",
                kind=DisplayElementKind.STRING,
                arrangement=GroupArrangement.HORIZONTAL_ROW,
                density=PixelDensity.MEDIUM,
                prominence=DisplayProminence.ANCHOR,
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.HIGH,
                depth=DepthZone.FAR,
                zone=DisplayZone.HOUSE,
                pixel_fraction=0.20,
                fixture_count=10,
            ),
            _make_group(
                "WINDOWS",
                parent="HOUSE",
                kind=DisplayElementKind.WINDOW,
                arrangement=GroupArrangement.GRID,
                density=PixelDensity.HIGH,
                prominence=DisplayProminence.SUPPORTING,
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.MID,
                depth=DepthZone.MID,
                zone=DisplayZone.HOUSE,
                pixel_fraction=0.15,
                fixture_count=8,
            ),
            _make_group(
                "YARD",
                parent="ALL_DISPLAY",
                kind=DisplayElementKind.MIXED,
                arrangement=GroupArrangement.CLUSTER,
                pixel_fraction=0.55,
            ),
            _make_group(
                "MEGA_TREE",
                parent="YARD",
                element_type=ElementType.MODEL,
                kind=DisplayElementKind.TREE,
                arrangement=GroupArrangement.SINGLE,
                density=PixelDensity.HIGH,
                prominence=DisplayProminence.HERO,
                horizontal=HorizontalZone.CENTER,
                vertical=VerticalZone.FULL_HEIGHT,
                zone=DisplayZone.YARD,
                pixel_fraction=0.25,
                fixture_count=1,
            ),
            _make_group(
                "ARCHES",
                parent="YARD",
                kind=DisplayElementKind.ARCH,
                arrangement=GroupArrangement.HORIZONTAL_ROW,
                density=PixelDensity.MEDIUM,
                prominence=DisplayProminence.ANCHOR,
                horizontal=HorizontalZone.FULL_WIDTH,
                vertical=VerticalZone.LOW,
                zone=DisplayZone.YARD,
                pixel_fraction=0.15,
                fixture_count=5,
            ),
            _make_group(
                "CANDY_CANES",
                parent="YARD",
                kind=DisplayElementKind.CANDY_CANE,
                arrangement=GroupArrangement.HORIZONTAL_ROW,
                density=PixelDensity.LOW,
                prominence=DisplayProminence.SUPPORTING,
                horizontal=HorizontalZone.RIGHT,
                vertical=VerticalZone.LOW,
                zone=DisplayZone.YARD,
                pixel_fraction=0.15,
                fixture_count=4,
            ),
            _make_group(
                "ACCENT_ZONE",
                parent="ALL_DISPLAY",
                kind=DisplayElementKind.MIXED,
                arrangement=GroupArrangement.CLUSTER,
                pixel_fraction=0.10,
            ),
            _make_group(
                "SANTA",
                parent="ACCENT_ZONE",
                kind=DisplayElementKind.PROP,
                arrangement=GroupArrangement.SINGLE,
                density=PixelDensity.LOW,
                prominence=DisplayProminence.ACCENT,
                horizontal=HorizontalZone.LEFT,
                vertical=VerticalZone.GROUND,
                zone=DisplayZone.ACCENT,
                pixel_fraction=0.10,
                fixture_count=1,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Hierarchy traversal
# ---------------------------------------------------------------------------


class TestHierarchyTraversal:
    """Test parent-child traversal methods on DisplayGraph."""

    def test_get_children_of_root(self, sample_graph: DisplayGraph) -> None:
        children = sample_graph.get_children("ALL_DISPLAY")
        child_ids = [c.group_id for c in children]
        assert sorted(child_ids) == ["ACCENT_ZONE", "HOUSE", "YARD"]

    def test_get_children_of_leaf(self, sample_graph: DisplayGraph) -> None:
        children = sample_graph.get_children("SANTA")
        assert children == []

    def test_get_children_of_zone(self, sample_graph: DisplayGraph) -> None:
        children = sample_graph.get_children("YARD")
        child_ids = [c.group_id for c in children]
        assert sorted(child_ids) == ["ARCHES", "CANDY_CANES", "MEGA_TREE"]

    def test_get_parent(self, sample_graph: DisplayGraph) -> None:
        parent = sample_graph.get_parent("OUTLINE")
        assert parent is not None
        assert parent.group_id == "HOUSE"

    def test_get_parent_of_root(self, sample_graph: DisplayGraph) -> None:
        parent = sample_graph.get_parent("ALL_DISPLAY")
        assert parent is None

    def test_get_ancestors(self, sample_graph: DisplayGraph) -> None:
        ancestors = sample_graph.get_ancestors("ARCHES")
        ancestor_ids = [a.group_id for a in ancestors]
        assert ancestor_ids == ["YARD", "ALL_DISPLAY"]

    def test_get_ancestors_of_root(self, sample_graph: DisplayGraph) -> None:
        ancestors = sample_graph.get_ancestors("ALL_DISPLAY")
        assert ancestors == []

    def test_get_descendants(self, sample_graph: DisplayGraph) -> None:
        descendants = sample_graph.get_descendants("YARD")
        desc_ids = {d.group_id for d in descendants}
        assert desc_ids == {"MEGA_TREE", "ARCHES", "CANDY_CANES"}

    def test_get_descendants_of_root(self, sample_graph: DisplayGraph) -> None:
        descendants = sample_graph.get_descendants("ALL_DISPLAY")
        # 3 zone groups + 6 leaf groups = 9
        assert len(descendants) == 9

    def test_get_root_groups(self, sample_graph: DisplayGraph) -> None:
        roots = sample_graph.get_root_groups()
        root_ids = [r.group_id for r in roots]
        assert root_ids == ["ALL_DISPLAY"]

    def test_get_siblings(self, sample_graph: DisplayGraph) -> None:
        siblings = sample_graph.get_siblings("ARCHES")
        sibling_ids = {s.group_id for s in siblings}
        assert sibling_ids == {"MEGA_TREE", "CANDY_CANES"}

    def test_get_siblings_of_root(self, sample_graph: DisplayGraph) -> None:
        siblings = sample_graph.get_siblings("ALL_DISPLAY")
        assert siblings == []


# ---------------------------------------------------------------------------
# Filtered views
# ---------------------------------------------------------------------------


class TestFilteredViews:
    """Test groups_in_zone and groups_by_role."""

    def test_all_groups_are_in_graph(self, sample_graph: DisplayGraph) -> None:
        assert len(sample_graph.groups) == 10

    def test_groups_in_zone(self, sample_graph: DisplayGraph) -> None:
        yard_groups = sample_graph.groups_in_zone(DisplayZone.YARD)
        yard_ids = {g.group_id for g in yard_groups}
        assert yard_ids == {"MEGA_TREE", "ARCHES", "CANDY_CANES"}

    def test_groups_in_zone_empty(self, sample_graph: DisplayGraph) -> None:
        perimeter_groups = sample_graph.groups_in_zone(DisplayZone.PERIMETER)
        assert perimeter_groups == []

    def test_groups_by_role(self, sample_graph: DisplayGraph) -> None:
        by_role = sample_graph.groups_by_role
        assert "OUTLINE" in by_role
        assert "ALL_DISPLAY" in by_role


# ---------------------------------------------------------------------------
# Spatial sorting
# ---------------------------------------------------------------------------


class TestSpatialSorting:
    """Test groups_sorted_by with different SpatialIntents."""

    def test_l2r_sorts_left_to_right(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.L2R)
        ids = [g.group_id for g in sorted_groups]
        # SANTA (LEFT=1) should come before CANDY_CANES (RIGHT=5)
        assert ids.index("SANTA") < ids.index("CANDY_CANES")

    def test_r2l_sorts_right_to_left(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.R2L)
        ids = [g.group_id for g in sorted_groups]
        # CANDY_CANES (RIGHT=5) should come before SANTA (LEFT=1)
        assert ids.index("CANDY_CANES") < ids.index("SANTA")

    def test_c2o_sorts_center_outward(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.C2O)
        ids = [g.group_id for g in sorted_groups]
        # CENTER groups first, then LEFT/RIGHT groups at edges
        # MEGA_TREE/WINDOWS (CENTER=3) before SANTA (LEFT=1) and CANDY_CANES (RIGHT=5)
        center_indices = [ids.index("MEGA_TREE"), ids.index("WINDOWS")]
        edge_indices = [ids.index("SANTA"), ids.index("CANDY_CANES")]
        assert max(center_indices) < min(edge_indices)

    def test_o2c_sorts_outer_to_center(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.O2C)
        ids = [g.group_id for g in sorted_groups]
        # Edge groups before center groups
        edge_indices = [ids.index("SANTA"), ids.index("CANDY_CANES")]
        center_indices = [ids.index("MEGA_TREE"), ids.index("WINDOWS")]
        assert max(edge_indices) < min(center_indices)

    def test_b2t_sorts_bottom_to_top(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.B2T)
        ids = [g.group_id for g in sorted_groups]
        # SANTA (GROUND=0) should come before OUTLINE (HIGH=3)
        assert ids.index("SANTA") < ids.index("OUTLINE")

    def test_t2b_sorts_top_to_bottom(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.T2B)
        ids = [g.group_id for g in sorted_groups]
        # OUTLINE (HIGH=3) should come before SANTA (GROUND=0)
        assert ids.index("OUTLINE") < ids.index("SANTA")

    def test_f2b_sorts_front_to_back(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.F2B)
        ids = [g.group_id for g in sorted_groups]
        # ARCHES (NEAR=0) should come before OUTLINE (FAR=2)
        assert ids.index("ARCHES") < ids.index("OUTLINE")

    def test_b2f_sorts_back_to_front(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.B2F)
        ids = [g.group_id for g in sorted_groups]
        # OUTLINE (FAR=2) should come before ARCHES (NEAR=0)
        assert ids.index("OUTLINE") < ids.index("ARCHES")

    def test_none_returns_groups_in_order(self, sample_graph: DisplayGraph) -> None:
        sorted_groups = sample_graph.groups_sorted_by(SpatialIntent.NONE)
        assert [g.group_id for g in sorted_groups] == [g.group_id for g in sample_graph.groups]


# ---------------------------------------------------------------------------
# Spatial sort keys
# ---------------------------------------------------------------------------


class TestSortKeys:
    """Test that spatial enum sort_key() methods produce correct orderings."""

    def test_horizontal_sort_order(self) -> None:
        zones = [
            HorizontalZone.FAR_RIGHT,
            HorizontalZone.LEFT,
            HorizontalZone.CENTER,
            HorizontalZone.FAR_LEFT,
        ]
        sorted_zones = sorted(zones, key=lambda z: z.sort_key())
        assert sorted_zones == [
            HorizontalZone.FAR_LEFT,
            HorizontalZone.LEFT,
            HorizontalZone.CENTER,
            HorizontalZone.FAR_RIGHT,
        ]

    def test_full_width_sorts_as_center(self) -> None:
        assert HorizontalZone.FULL_WIDTH.sort_key() == HorizontalZone.CENTER.sort_key()

    def test_vertical_sort_order(self) -> None:
        zones = [
            VerticalZone.TOP,
            VerticalZone.GROUND,
            VerticalZone.MID,
        ]
        sorted_zones = sorted(zones, key=lambda z: z.sort_key())
        assert sorted_zones == [
            VerticalZone.GROUND,
            VerticalZone.MID,
            VerticalZone.TOP,
        ]

    def test_full_height_sorts_as_mid(self) -> None:
        assert VerticalZone.FULL_HEIGHT.sort_key() == VerticalZone.MID.sort_key()

    def test_depth_sort_order(self) -> None:
        zones = [DepthZone.FAR, DepthZone.NEAR, DepthZone.MID]
        sorted_zones = sorted(zones, key=lambda z: z.sort_key())
        assert sorted_zones == [DepthZone.NEAR, DepthZone.MID, DepthZone.FAR]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Test Pydantic validators for hierarchy integrity."""

    def test_invalid_parent_ref(self) -> None:
        """parent_group_id must reference an existing group_id."""
        with pytest.raises(ValidationError, match="parent_group_id"):
            DisplayGraph(
                display_id="test",
                display_name="Test",
                groups=[
                    _make_group("ARCHES", parent="NONEXISTENT"),
                ],
            )

    def test_cycle_detection(self) -> None:
        """Hierarchy must not contain cycles."""
        with pytest.raises(ValidationError, match=r"[Cc]ycle"):
            DisplayGraph(
                display_id="test",
                display_name="Test",
                groups=[
                    _make_group("A", parent="B"),
                    _make_group("B", parent="A"),
                ],
            )

    def test_flat_graph_no_hierarchy_valid(self) -> None:
        """A flat graph (no parents) should still be valid."""
        graph = DisplayGraph(
            display_id="flat",
            display_name="Flat Display",
            groups=[
                _make_group("A"),
                _make_group("B"),
            ],
        )
        assert len(graph.groups) == 2

    def test_schema_version_v2(self, sample_graph: DisplayGraph) -> None:
        assert sample_graph.schema_version == "display-graph.v2"
