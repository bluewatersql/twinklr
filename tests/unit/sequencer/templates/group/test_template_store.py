"""Tests for TemplateStore — JSON-backed template storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.store import (
    TemplateStore,
)
from twinklr.core.sequencer.vocabulary import (
    GroupTemplateType,
    LaneKind,
)


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
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
        "tags": ["wash", "slow"],
        "timing": {"bars_min": 4, "bars_max": 64},
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [
            {
                "layer_index": 0,
                "layer_name": "Wash",
                "layer_depth": "BACKGROUND",
                "effect_type": "ColorWash",
                "blend_mode": "NORMAL",
                "mix": 1.0,
                "params": {},
                "density": 0.9,
                "color_source": "palette_primary",
            }
        ],
        "provenance": {"source": "builtin"},
        "style_markers": {"complexity": 0.33, "energy_affinity": "LOW"},
    }
    (builtins / "gtpl_base_wash_slow.json").write_text(json.dumps(recipe_data), encoding="utf-8")

    recipe_data2 = dict(recipe_data)
    recipe_data2["recipe_id"] = "gtpl_rhythm_pulse_fast"
    recipe_data2["name"] = "Pulse Fast"
    recipe_data2["template_type"] = "RHYTHM"
    recipe_data2["tags"] = ["pulse", "fast"]
    recipe_data2["style_markers"] = {"complexity": 0.5, "energy_affinity": "HIGH"}
    (builtins / "gtpl_rhythm_pulse_fast.json").write_text(
        json.dumps(recipe_data2), encoding="utf-8"
    )

    index = {
        "schema_version": "template-index.v1",
        "total": 2,
        "entries": [
            {
                "recipe_id": "gtpl_base_wash_slow",
                "name": "Wash Slow",
                "template_type": "BASE",
                "visual_intent": "ABSTRACT",
                "tags": ["wash", "slow"],
                "source": "builtin",
                "file": "builtins/gtpl_base_wash_slow.json",
            },
            {
                "recipe_id": "gtpl_rhythm_pulse_fast",
                "name": "Pulse Fast",
                "template_type": "RHYTHM",
                "visual_intent": "ABSTRACT",
                "tags": ["pulse", "fast"],
                "source": "builtin",
                "file": "builtins/gtpl_rhythm_pulse_fast.json",
            },
        ],
    }
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    return tmp_path


def test_load_from_index(store_dir: Path) -> None:
    """TemplateStore loads entries from index.json."""
    store = TemplateStore.from_directory(store_dir)
    assert len(store.entries) == 2


def test_has_recipe(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    assert store.has_recipe("gtpl_base_wash_slow")
    assert store.has_recipe("gtpl_rhythm_pulse_fast")
    assert not store.has_recipe("nonexistent")


def test_get_recipe_lazy_loads(store_dir: Path) -> None:
    """get_recipe reads and deserializes JSON on first access."""
    store = TemplateStore.from_directory(store_dir)
    recipe = store.get_recipe("gtpl_base_wash_slow")
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == "gtpl_base_wash_slow"
    assert recipe.name == "Wash Slow"


def test_get_recipe_caches(store_dir: Path) -> None:
    """Second call returns same instance (cached)."""
    store = TemplateStore.from_directory(store_dir)
    r1 = store.get_recipe("gtpl_base_wash_slow")
    r2 = store.get_recipe("gtpl_base_wash_slow")
    assert r1 is r2


def test_get_recipe_not_found(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    assert store.get_recipe("nonexistent") is None


def test_list_by_type(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    base = store.list_by_type(GroupTemplateType.BASE)
    assert len(base) == 1
    assert base[0].recipe_id == "gtpl_base_wash_slow"

    rhythm = store.list_by_type(GroupTemplateType.RHYTHM)
    assert len(rhythm) == 1


def test_list_by_lane(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    base = store.list_by_lane(LaneKind.BASE)
    assert len(base) == 1

    accent = store.list_by_lane(LaneKind.ACCENT)
    assert len(accent) == 0


def test_entry_compatible_lanes(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    entry = store.get_entry("gtpl_base_wash_slow")
    assert entry is not None
    assert LaneKind.BASE in entry.compatible_lanes


def test_all_recipe_ids(store_dir: Path) -> None:
    store = TemplateStore.from_directory(store_dir)
    ids = store.all_recipe_ids()
    assert set(ids) == {"gtpl_base_wash_slow", "gtpl_rhythm_pulse_fast"}
