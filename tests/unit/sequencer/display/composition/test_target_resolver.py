"""Unit tests for TargetResolver — choreography ID → xLights element name mapping."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.target_resolver import (
    TargetResolver,
)
from twinklr.core.sequencer.display.xlights_mapping import (
    XLightsGroupMapping,
    XLightsMapping,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)


def _make_group_based_setup() -> tuple[ChoreographyGraph, XLightsMapping]:
    """ChoreographyGraph + XLightsMapping for group-based resolution."""
    graph = ChoreographyGraph(
        graph_id="test",
        groups=[
            ChoreoGroup(id="ARCHES", role="ARCHES"),
            ChoreoGroup(id="MEGA_TREE", role="MEGA_TREE"),
            ChoreoGroup(id="WINDOWS", role="WINDOWS"),
        ],
    )
    mapping = XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id="ARCHES", group_name="61 - Arches"),
            XLightsGroupMapping(choreo_id="MEGA_TREE", group_name="11 - MegaTree"),
            XLightsGroupMapping(choreo_id="WINDOWS", group_name="18 - Windows"),
        ],
    )
    return graph, mapping


def _make_per_model_setup() -> tuple[ChoreographyGraph, XLightsMapping]:
    """ChoreographyGraph + XLightsMapping for per-model fallback."""
    graph = ChoreographyGraph(
        graph_id="test",
        groups=[
            ChoreoGroup(id="ARCH_1", role="ARCHES"),
            ChoreoGroup(id="ARCH_2", role="ARCHES"),
            ChoreoGroup(id="ARCH_3", role="ARCHES"),
        ],
    )
    mapping = XLightsMapping(
        entries=[
            XLightsGroupMapping(choreo_id="ARCH_1", group_name="Arch 1"),
            XLightsGroupMapping(choreo_id="ARCH_2", group_name="Arch 2"),
            XLightsGroupMapping(choreo_id="ARCH_3", group_name="Arch 3"),
        ],
    )
    return graph, mapping


class TestTargetResolverDirectMapping:
    """Tests for direct choreo_id → element_name mapping."""

    def test_group_resolves_to_display_name(self) -> None:
        """Choreo ID maps to its xLights group name."""
        graph, mapping = _make_group_based_setup()
        resolver = TargetResolver(graph, mapping)
        assert resolver.resolve("ARCHES") == "61 - Arches"
        assert resolver.resolve("MEGA_TREE") == "11 - MegaTree"
        assert resolver.resolve("WINDOWS") == "18 - Windows"

    def test_per_model_resolves_to_display_name(self) -> None:
        """Per-model choreo ID maps to its model name."""
        graph, mapping = _make_per_model_setup()
        resolver = TargetResolver(graph, mapping)
        assert resolver.resolve("ARCH_1") == "Arch 1"
        assert resolver.resolve("ARCH_2") == "Arch 2"
        assert resolver.resolve("ARCH_3") == "Arch 3"

    def test_fallback_for_unknown_id(self) -> None:
        """Unknown choreo_id falls back to using itself as element name."""
        graph, mapping = _make_group_based_setup()
        resolver = TargetResolver(graph, mapping)
        assert resolver.resolve("UNKNOWN_GROUP") == "UNKNOWN_GROUP"


class TestTargetResolverRoles:
    """Tests for role-based resolution."""

    def test_resolve_roles_returns_group_elements(self) -> None:
        """resolve_roles returns element names for matching roles."""
        graph, mapping = _make_group_based_setup()
        resolver = TargetResolver(graph, mapping)
        elements = resolver.resolve_roles(["ARCHES"])
        assert elements == ["61 - Arches"]

    def test_resolve_roles_multiple(self) -> None:
        """resolve_roles with multiple roles returns all matches."""
        graph, mapping = _make_group_based_setup()
        resolver = TargetResolver(graph, mapping)
        elements = resolver.resolve_roles(["ARCHES", "WINDOWS"])
        assert "61 - Arches" in elements
        assert "18 - Windows" in elements

    def test_resolve_roles_empty_for_no_match(self) -> None:
        """resolve_roles returns empty list for unmatched roles."""
        graph, mapping = _make_group_based_setup()
        resolver = TargetResolver(graph, mapping)
        elements = resolver.resolve_roles(["NONEXISTENT"])
        assert elements == []

    def test_resolve_roles_per_model_graph(self) -> None:
        """resolve_roles returns all per-model entries for a role."""
        graph, mapping = _make_per_model_setup()
        resolver = TargetResolver(graph, mapping)
        elements = resolver.resolve_roles(["ARCHES"])
        assert len(elements) == 3
        assert "Arch 1" in elements
        assert "Arch 2" in elements
        assert "Arch 3" in elements
