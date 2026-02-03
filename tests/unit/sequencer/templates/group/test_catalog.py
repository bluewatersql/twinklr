"""Tests for group template catalog builder."""

import pytest

from twinklr.core.agents.sequencer.group_planner.models import LaneKind
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateCatalogEntry,
    build_template_catalog,
)
from twinklr.core.sequencer.templates.group.enums import (
    GroupTemplateType,
    GroupVisualIntent,
    ProjectionIntent,
)
from twinklr.core.sequencer.templates.group.library import GroupTemplateRegistry
from twinklr.core.sequencer.templates.group.models import GroupPlanTemplate, ProjectionSpec

# Rebuild models with LaneKind now defined
TemplateCatalogEntry.model_rebuild()
TemplateCatalog.model_rebuild()


class TestTemplateCatalogEntry:
    """Test TemplateCatalogEntry model."""

    def test_create_minimal(self):
        """Test creating entry with minimal fields."""
        entry = TemplateCatalogEntry(
            template_id="test", name="Test", compatible_lanes=[LaneKind.BASE]
        )
        assert entry.template_id == "test"
        assert entry.name == "Test"
        assert entry.compatible_lanes == [LaneKind.BASE]
        assert entry.tags == []

    def test_create_with_all_fields(self):
        """Test creating entry with all fields."""
        entry = TemplateCatalogEntry(
            template_id="test",
            name="Test Template",
            compatible_lanes=[LaneKind.BASE, LaneKind.RHYTHM],
            tags=["starfield", "calm"],
            description="Test description",
        )
        assert len(entry.compatible_lanes) == 2
        assert len(entry.tags) == 2
        assert entry.description == "Test description"

    def test_compatible_lanes_required(self):
        """Test compatible_lanes must have at least 1 lane."""
        with pytest.raises(ValueError):
            TemplateCatalogEntry(template_id="test", name="Test", compatible_lanes=[])

    def test_frozen(self):
        """Test entry is frozen."""
        entry = TemplateCatalogEntry(
            template_id="test", name="Test", compatible_lanes=[LaneKind.BASE]
        )
        with pytest.raises(ValueError):
            entry.name = "Modified"


class TestTemplateCatalog:
    """Test TemplateCatalog model."""

    def test_create_empty(self):
        """Test creating empty catalog."""
        catalog = TemplateCatalog()
        assert catalog.entries == []
        assert catalog.schema_version == "template-catalog.v1"

    def test_create_with_entries(self):
        """Test creating catalog with entries."""
        entry1 = TemplateCatalogEntry(
            template_id="test1", name="Test 1", compatible_lanes=[LaneKind.BASE]
        )
        entry2 = TemplateCatalogEntry(
            template_id="test2", name="Test 2", compatible_lanes=[LaneKind.RHYTHM]
        )
        catalog = TemplateCatalog(entries=[entry1, entry2])
        assert len(catalog.entries) == 2

    def test_has_template(self):
        """Test has_template() method."""
        entry = TemplateCatalogEntry(
            template_id="test", name="Test", compatible_lanes=[LaneKind.BASE]
        )
        catalog = TemplateCatalog(entries=[entry])

        assert catalog.has_template("test") is True
        assert catalog.has_template("nonexistent") is False

    def test_get_entry(self):
        """Test get_entry() method."""
        entry = TemplateCatalogEntry(
            template_id="test", name="Test", compatible_lanes=[LaneKind.BASE]
        )
        catalog = TemplateCatalog(entries=[entry])

        found = catalog.get_entry("test")
        assert found is not None
        assert found.template_id == "test"

        not_found = catalog.get_entry("nonexistent")
        assert not_found is None

    def test_list_by_lane(self):
        """Test list_by_lane() method."""
        entry1 = TemplateCatalogEntry(
            template_id="base1", name="Base 1", compatible_lanes=[LaneKind.BASE]
        )
        entry2 = TemplateCatalogEntry(
            template_id="rhythm1",
            name="Rhythm 1",
            compatible_lanes=[LaneKind.RHYTHM, LaneKind.ACCENT],
        )
        entry3 = TemplateCatalogEntry(
            template_id="base2", name="Base 2", compatible_lanes=[LaneKind.BASE]
        )
        catalog = TemplateCatalog(entries=[entry1, entry2, entry3])

        # Filter by BASE
        base_entries = catalog.list_by_lane(LaneKind.BASE)
        assert len(base_entries) == 2
        assert all(LaneKind.BASE in e.compatible_lanes for e in base_entries)

        # Filter by RHYTHM
        rhythm_entries = catalog.list_by_lane(LaneKind.RHYTHM)
        assert len(rhythm_entries) == 1
        assert rhythm_entries[0].template_id == "rhythm1"


class TestBuildTemplateCatalog:
    """Test build_template_catalog() function."""

    def test_build_catalog_empty_registry(self):
        """Test building catalog from empty registry."""
        # Create isolated registry
        registry = GroupTemplateRegistry()

        # Temporarily swap global registry
        from twinklr.core.sequencer.templates.group import catalog

        original_registry = catalog.REGISTRY
        catalog.REGISTRY = registry

        try:
            result = build_template_catalog()
            assert isinstance(result, TemplateCatalog)
            assert result.entries == []
        finally:
            catalog.REGISTRY = original_registry

    def test_build_catalog_with_templates(self):
        """Test building catalog with registered templates."""
        # Create isolated registry
        registry = GroupTemplateRegistry()

        # Register sample templates
        def make_base():
            return GroupPlanTemplate(
                template_id="base_test",
                name="Base Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["test", "base"],
            )

        def make_rhythm():
            return GroupPlanTemplate(
                template_id="rhythm_test",
                name="Rhythm Test",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.GEOMETRIC,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                tags=["test", "rhythm"],
            )

        registry.register(make_base)
        registry.register(make_rhythm)

        # Temporarily swap global registry
        from twinklr.core.sequencer.templates.group import catalog

        original_registry = catalog.REGISTRY
        catalog.REGISTRY = registry

        try:
            result = build_template_catalog()
            assert isinstance(result, TemplateCatalog)
            assert len(result.entries) == 2

            # Verify BASE template
            base_entry = result.get_entry("base_test")
            assert base_entry is not None
            assert base_entry.name == "Base Test"
            assert base_entry.compatible_lanes == [LaneKind.BASE]
            assert "test" in base_entry.tags
            assert "base" in base_entry.tags

            # Verify RHYTHM template
            rhythm_entry = result.get_entry("rhythm_test")
            assert rhythm_entry is not None
            assert rhythm_entry.name == "Rhythm Test"
            assert rhythm_entry.compatible_lanes == [LaneKind.RHYTHM]
        finally:
            catalog.REGISTRY = original_registry

    def test_template_type_to_lane_mapping(self):
        """Test template_type maps correctly to LaneKind."""
        registry = GroupTemplateRegistry()

        # Test all template types
        for template_type, _ in [
            (GroupTemplateType.BASE, LaneKind.BASE),
            (GroupTemplateType.RHYTHM, LaneKind.RHYTHM),
            (GroupTemplateType.ACCENT, LaneKind.ACCENT),
        ]:

            def make_template(tt=template_type):
                return GroupPlanTemplate(
                    template_id=f"test_{tt.value.lower()}",
                    name=f"Test {tt.value}",
                    template_type=tt,
                    visual_intent=GroupVisualIntent.ABSTRACT,
                    projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                )

            registry.register(make_template)

        # Temporarily swap global registry
        from twinklr.core.sequencer.templates.group import catalog

        original_registry = catalog.REGISTRY
        catalog.REGISTRY = registry

        try:
            result = build_template_catalog()

            # Verify each mapping
            base_entry = result.get_entry("test_base")
            assert base_entry.compatible_lanes == [LaneKind.BASE]

            rhythm_entry = result.get_entry("test_rhythm")
            assert rhythm_entry.compatible_lanes == [LaneKind.RHYTHM]

            accent_entry = result.get_entry("test_accent")
            assert accent_entry.compatible_lanes == [LaneKind.ACCENT]
        finally:
            catalog.REGISTRY = original_registry
