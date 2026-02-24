"""Tests for group template catalog builder."""

import json
from pathlib import Path

import pytest

from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
    build_template_catalog_from_store,
)
from twinklr.core.sequencer.templates.group.store import TemplateStore
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
)


class TestTemplateInfo:
    """Test TemplateInfo model."""

    def test_create_minimal(self):
        """Test creating entry with minimal fields."""
        entry = TemplateInfo(
            template_id="test",
            version="1.0",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        assert entry.template_id == "test"
        assert entry.name == "Test"
        assert entry.compatible_lanes == [LaneKind.BASE]
        assert entry.tags == ()

    def test_create_with_all_fields(self):
        """Test creating entry with all fields."""
        entry = TemplateInfo(
            template_id="test",
            version="1.0",
            name="Test Template",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=("starfield", "calm"),
            description="Test description",
        )
        assert entry.compatible_lanes == [LaneKind.BASE]
        assert len(entry.tags) == 2
        assert entry.description == "Test description"

    def test_compatible_lanes_derived(self):
        """Test compatible_lanes is derived from template_type."""
        base_entry = TemplateInfo(
            template_id="test_base",
            version="1.0",
            name="Test Base",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        assert base_entry.compatible_lanes == [LaneKind.BASE]

        rhythm_entry = TemplateInfo(
            template_id="test_rhythm",
            version="1.0",
            name="Test Rhythm",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.GEOMETRIC,
            tags=(),
        )
        assert rhythm_entry.compatible_lanes == [LaneKind.RHYTHM]

        # TRANSITION has no lane
        transition_entry = TemplateInfo(
            template_id="test_transition",
            version="1.0",
            name="Test Transition",
            template_type=GroupTemplateType.TRANSITION,
            visual_intent=GroupVisualIntent.HYBRID,
            tags=(),
        )
        assert transition_entry.compatible_lanes == []

    def test_frozen(self):
        """Test entry is frozen."""
        entry = TemplateInfo(
            template_id="test",
            version="1.0",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
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
        entry1 = TemplateInfo(
            template_id="test1",
            version="1.0",
            name="Test 1",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        entry2 = TemplateInfo(
            template_id="test2",
            version="1.0",
            name="Test 2",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.GEOMETRIC,
            tags=(),
        )
        catalog = TemplateCatalog(entries=[entry1, entry2])
        assert len(catalog.entries) == 2

    def test_has_template(self):
        """Test has_template() method."""
        entry = TemplateInfo(
            template_id="test",
            version="1.0",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        catalog = TemplateCatalog(entries=[entry])

        assert catalog.has_template("test") is True
        assert catalog.has_template("nonexistent") is False

    def test_get_entry(self):
        """Test get_entry() method."""
        entry = TemplateInfo(
            template_id="test",
            version="1.0",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        catalog = TemplateCatalog(entries=[entry])

        found = catalog.get_entry("test")
        assert found is not None
        assert found.template_id == "test"

        not_found = catalog.get_entry("nonexistent")
        assert not_found is None

    def test_list_by_lane(self):
        """Test list_by_lane() method."""
        entry1 = TemplateInfo(
            template_id="base1",
            version="1.0",
            name="Base 1",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        )
        entry2 = TemplateInfo(
            template_id="rhythm1",
            version="1.0",
            name="Rhythm 1",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.GEOMETRIC,
            tags=(),
        )
        entry3 = TemplateInfo(
            template_id="base2",
            version="1.0",
            name="Base 2",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
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


@pytest.fixture()
def _store_dir(tmp_path: Path) -> Path:
    """Create a minimal template store on disk."""
    builtins = tmp_path / "builtins"
    builtins.mkdir()

    recipe_data = {
        "recipe_id": "gtpl_base_wash_slow",
        "name": "Wash Slow",
        "description": "Slow wash",
        "recipe_version": "1.0.0",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["wash", "slow", "test"],
        "timing": {"bars_min": 4, "bars_max": 64},
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [],
        "provenance": {"source": "builtin"},
        "style_markers": {"complexity": 0.3, "energy_affinity": "LOW"},
    }
    (builtins / "gtpl_base_wash_slow.json").write_text(json.dumps(recipe_data), encoding="utf-8")

    recipe_data2 = dict(recipe_data)
    recipe_data2["recipe_id"] = "gtpl_rhythm_pulse_fast"
    recipe_data2["name"] = "Pulse Fast"
    recipe_data2["template_type"] = "RHYTHM"
    recipe_data2["tags"] = ["pulse", "fast", "test"]
    (builtins / "gtpl_rhythm_pulse_fast.json").write_text(
        json.dumps(recipe_data2), encoding="utf-8"
    )

    recipe_data3 = dict(recipe_data)
    recipe_data3["recipe_id"] = "gtpl_accent_sparkle"
    recipe_data3["name"] = "Sparkle"
    recipe_data3["template_type"] = "ACCENT"
    recipe_data3["tags"] = ["sparkle", "test"]
    (builtins / "gtpl_accent_sparkle.json").write_text(json.dumps(recipe_data3), encoding="utf-8")

    index = {
        "schema_version": "template-index.v1",
        "total": 3,
        "entries": [
            {
                "recipe_id": "gtpl_base_wash_slow",
                "name": "Wash Slow",
                "template_type": "BASE",
                "visual_intent": "ABSTRACT",
                "tags": ["wash", "slow", "test"],
                "source": "builtin",
                "file": "builtins/gtpl_base_wash_slow.json",
            },
            {
                "recipe_id": "gtpl_rhythm_pulse_fast",
                "name": "Pulse Fast",
                "template_type": "RHYTHM",
                "visual_intent": "ABSTRACT",
                "tags": ["pulse", "fast", "test"],
                "source": "builtin",
                "file": "builtins/gtpl_rhythm_pulse_fast.json",
            },
            {
                "recipe_id": "gtpl_accent_sparkle",
                "name": "Sparkle",
                "template_type": "ACCENT",
                "visual_intent": "ABSTRACT",
                "tags": ["sparkle", "test"],
                "source": "builtin",
                "file": "builtins/gtpl_accent_sparkle.json",
            },
        ],
    }
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


class TestBuildTemplateCatalogFromStore:
    """Test build_template_catalog_from_store() function."""

    def test_build_catalog_empty_store(self, tmp_path: Path) -> None:
        """Test building catalog from empty store."""
        (tmp_path / "index.json").write_text(
            json.dumps({"schema_version": "template-index.v1", "total": 0, "entries": []}),
            encoding="utf-8",
        )
        store = TemplateStore.from_directory(tmp_path)
        result = build_template_catalog_from_store(store)
        assert isinstance(result, TemplateCatalog)
        assert result.entries == []

    def test_build_catalog_with_templates(self, _store_dir: Path) -> None:
        """Test building catalog from store with templates."""
        store = TemplateStore.from_directory(_store_dir)
        result = build_template_catalog_from_store(store)
        assert isinstance(result, TemplateCatalog)
        assert len(result.entries) == 3

        base_entry = result.get_entry("gtpl_base_wash_slow")
        assert base_entry is not None
        assert base_entry.name == "Wash Slow"
        assert base_entry.compatible_lanes == [LaneKind.BASE]
        assert "wash" in base_entry.tags
        assert "test" in base_entry.tags

        rhythm_entry = result.get_entry("gtpl_rhythm_pulse_fast")
        assert rhythm_entry is not None
        assert rhythm_entry.name == "Pulse Fast"
        assert rhythm_entry.compatible_lanes == [LaneKind.RHYTHM]

    def test_template_type_to_lane_mapping(self, _store_dir: Path) -> None:
        """Test template_type maps correctly to LaneKind."""
        store = TemplateStore.from_directory(_store_dir)
        result = build_template_catalog_from_store(store)

        base_entry = result.get_entry("gtpl_base_wash_slow")
        assert base_entry is not None
        assert base_entry.compatible_lanes == [LaneKind.BASE]

        rhythm_entry = result.get_entry("gtpl_rhythm_pulse_fast")
        assert rhythm_entry is not None
        assert rhythm_entry.compatible_lanes == [LaneKind.RHYTHM]

        accent_entry = result.get_entry("gtpl_accent_sparkle")
        assert accent_entry is not None
        assert accent_entry.compatible_lanes == [LaneKind.ACCENT]
