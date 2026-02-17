"""Tests for DisplayGraph -> ChoreographyGraph + XLightsMapping factory functions.

Tests the migration bridge that converts existing DisplayGraph instances
into the new ChoreographyGraph and XLightsMapping models.
"""

from twinklr.core.sequencer.display.xlights_mapping import XLightsMapping
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
)
from twinklr.core.sequencer.templates.group.models.compat import (
    choreo_graph_from_display_graph,
    xlights_mapping_from_display_graph,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    GroupPosition,
)
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


def _make_display_graph() -> DisplayGraph:
    """Build a minimal DisplayGraph for conversion testing."""
    return DisplayGraph(
        display_id="test_display",
        display_name="Test Display",
        groups=[
            DisplayGroup(
                group_id="ARCHES",
                role="ARCHES",
                display_name="61 - Arches",
                element_kind=DisplayElementKind.ARCH,
                arrangement=GroupArrangement.HORIZONTAL_ROW,
                pixel_density=PixelDensity.MEDIUM,
                prominence=DisplayProminence.ANCHOR,
                position=GroupPosition(
                    horizontal=HorizontalZone.FULL_WIDTH,
                    vertical=VerticalZone.LOW,
                    depth=DepthZone.NEAR,
                    zone=DisplayZone.YARD,
                ),
                fixture_count=10,
                pixel_fraction=0.15,
            ),
            DisplayGroup(
                group_id="MEGA_TREE",
                role="MEGA_TREE",
                display_name="MegaTree",
                element_kind=DisplayElementKind.TREE,
                arrangement=GroupArrangement.SINGLE,
                pixel_density=PixelDensity.HIGH,
                prominence=DisplayProminence.HERO,
                position=GroupPosition(
                    horizontal=HorizontalZone.CENTER,
                    vertical=VerticalZone.FULL_HEIGHT,
                    depth=DepthZone.NEAR,
                    zone=DisplayZone.YARD,
                ),
                fixture_count=1,
                pixel_fraction=0.25,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# choreo_graph_from_display_graph
# ---------------------------------------------------------------------------


class TestChoreoGraphFromDisplayGraph:
    """Tests for DisplayGraph -> ChoreographyGraph conversion."""

    def test_converts_all_groups(self) -> None:
        """All DisplayGroups become ChoreoGroups."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        assert isinstance(cg, ChoreographyGraph)
        assert len(cg.groups) == 2

    def test_maps_group_id_to_id(self) -> None:
        """DisplayGroup.group_id becomes ChoreoGroup.id."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        ids = {g.id for g in cg.groups}
        assert ids == {"ARCHES", "MEGA_TREE"}

    def test_preserves_physical_fields(self) -> None:
        """Physical metadata fields are preserved in conversion."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        arches = cg.get_group("ARCHES")
        assert arches is not None
        assert arches.role == "ARCHES"
        assert arches.element_kind == DisplayElementKind.ARCH
        assert arches.prominence == DisplayProminence.ANCHOR
        assert arches.fixture_count == 10
        assert arches.pixel_fraction == 0.15
        assert arches.arrangement == GroupArrangement.HORIZONTAL_ROW

    def test_preserves_position(self) -> None:
        """GroupPosition is preserved in conversion."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        arches = cg.get_group("ARCHES")
        assert arches is not None
        assert arches.position is not None
        assert arches.position.horizontal == HorizontalZone.FULL_WIDTH
        assert arches.position.zone == DisplayZone.YARD

    def test_drops_display_name(self) -> None:
        """ChoreoGroup has no display_name field."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        arches = cg.get_group("ARCHES")
        assert arches is not None
        assert not hasattr(arches, "display_name")

    def test_graph_id_from_display_id(self) -> None:
        """ChoreographyGraph.graph_id is derived from DisplayGraph.display_id."""
        dg = _make_display_graph()
        cg = choreo_graph_from_display_graph(dg)
        assert cg.graph_id == "test_display"


# ---------------------------------------------------------------------------
# xlights_mapping_from_display_graph
# ---------------------------------------------------------------------------


class TestXLightsMappingFromDisplayGraph:
    """Tests for DisplayGraph -> XLightsMapping conversion."""

    def test_creates_entry_per_group(self) -> None:
        """Each DisplayGroup produces an XLightsGroupMapping entry."""
        dg = _make_display_graph()
        xm = xlights_mapping_from_display_graph(dg)
        assert isinstance(xm, XLightsMapping)
        assert len(xm.entries) == 2

    def test_maps_group_id_to_display_name(self) -> None:
        """choreo_id -> group_name maps group_id -> display_name."""
        dg = _make_display_graph()
        xm = xlights_mapping_from_display_graph(dg)
        resolved = xm.resolve("ARCHES")
        assert resolved == ["61 - Arches"]

    def test_all_groups_resolvable(self) -> None:
        """All DisplayGraph groups are resolvable in the mapping."""
        dg = _make_display_graph()
        xm = xlights_mapping_from_display_graph(dg)
        assert xm.has_entry("ARCHES")
        assert xm.has_entry("MEGA_TREE")
