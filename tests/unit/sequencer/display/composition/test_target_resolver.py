"""Unit tests for TargetResolver — direct group_id → display_name mapping."""

from __future__ import annotations

from twinklr.core.sequencer.display.composition.target_resolver import (
    TargetResolver,
)
from twinklr.core.sequencer.templates.group.models.display import (
    DisplayGraph,
    DisplayGroup,
    ElementType,
)


def _make_group_based_graph() -> DisplayGraph:
    """DisplayGraph with MODEL_GROUP entries.

    Simulates a typical xLights layout where effects target
    group elements (e.g., "61 - Arches") containing individual models.
    """
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(
                group_id="ARCHES",
                role="ARCHES",
                display_name="61 - Arches",
                element_type=ElementType.MODEL_GROUP,
            ),
            DisplayGroup(
                group_id="MEGA_TREE",
                role="MEGA_TREE",
                display_name="11 - MegaTree",
                element_type=ElementType.MODEL,
            ),
            DisplayGroup(
                group_id="WINDOWS",
                role="WINDOWS",
                display_name="18 - Windows",
                element_type=ElementType.MODEL_GROUP,
            ),
        ],
    )


def _make_per_model_graph() -> DisplayGraph:
    """DisplayGraph with per-model entries (future mode).

    Simulates a per-model targeting layout where each model
    is sequenced individually.
    """
    return DisplayGraph(
        display_id="test",
        display_name="Test",
        groups=[
            DisplayGroup(
                group_id="ARCH_1",
                role="ARCHES",
                display_name="Arch 1",
                element_type=ElementType.MODEL,
            ),
            DisplayGroup(
                group_id="ARCH_2",
                role="ARCHES",
                display_name="Arch 2",
                element_type=ElementType.MODEL,
            ),
            DisplayGroup(
                group_id="ARCH_3",
                role="ARCHES",
                display_name="Arch 3",
                element_type=ElementType.MODEL,
            ),
        ],
    )


class TestTargetResolverDirectMapping:
    """Tests for direct group_id → display_name mapping."""

    def test_group_resolves_to_display_name(self) -> None:
        """Group_id maps to its display_name."""
        resolver = TargetResolver(_make_group_based_graph())
        assert resolver.resolve("ARCHES") == "61 - Arches"
        assert resolver.resolve("MEGA_TREE") == "11 - MegaTree"
        assert resolver.resolve("WINDOWS") == "18 - Windows"

    def test_per_model_resolves_to_display_name(self) -> None:
        """Per-model group_id maps to its own display_name."""
        resolver = TargetResolver(_make_per_model_graph())
        assert resolver.resolve("ARCH_1") == "Arch 1"
        assert resolver.resolve("ARCH_2") == "Arch 2"
        assert resolver.resolve("ARCH_3") == "Arch 3"

    def test_fallback_for_unknown_id(self) -> None:
        """Unknown group_id falls back to using itself as element name."""
        resolver = TargetResolver(_make_group_based_graph())
        assert resolver.resolve("UNKNOWN_GROUP") == "UNKNOWN_GROUP"


class TestTargetResolverRoles:
    """Tests for role-based resolution."""

    def test_resolve_roles_returns_group_elements(self) -> None:
        """resolve_roles returns display_names for matching roles."""
        resolver = TargetResolver(_make_group_based_graph())
        elements = resolver.resolve_roles(["ARCHES"])
        assert elements == ["61 - Arches"]

    def test_resolve_roles_multiple(self) -> None:
        """resolve_roles with multiple roles returns all matches."""
        resolver = TargetResolver(_make_group_based_graph())
        elements = resolver.resolve_roles(["ARCHES", "WINDOWS"])
        assert "61 - Arches" in elements
        assert "18 - Windows" in elements

    def test_resolve_roles_empty_for_no_match(self) -> None:
        """resolve_roles returns empty list for unmatched roles."""
        resolver = TargetResolver(_make_group_based_graph())
        elements = resolver.resolve_roles(["NONEXISTENT"])
        assert elements == []

    def test_resolve_roles_per_model_graph(self) -> None:
        """resolve_roles returns all per-model entries for a role."""
        resolver = TargetResolver(_make_per_model_graph())
        elements = resolver.resolve_roles(["ARCHES"])
        assert len(elements) == 3
        assert "Arch 1" in elements
        assert "Arch 2" in elements
        assert "Arch 3" in elements


class TestElementTypeDefault:
    """Tests for ElementType defaults."""

    def test_element_type_defaults_to_model_group(self) -> None:
        """ElementType defaults to MODEL_GROUP for backward compat."""
        group = DisplayGroup(
            group_id="TEST",
            role="TEST",
            display_name="Test",
        )
        assert group.element_type == ElementType.MODEL_GROUP
