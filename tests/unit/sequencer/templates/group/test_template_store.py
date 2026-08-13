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
        "effect_family": "color_wash",
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


# ============================================================================
# Real tracked catalog (catalog/templates/) — not a synthetic tmp fixture.
# See P1K-T3: this directory is the single git-tracked data home.
# ============================================================================

_REPO_ROOT = Path(__file__).resolve().parents[5]
_CATALOG_TEMPLATES_DIR = _REPO_ROOT / "catalog" / "templates"


def test_load_from_real_catalog() -> None:
    """TemplateStore loads the tracked catalog/templates/ seed set successfully."""
    store = TemplateStore.from_directory(_CATALOG_TEMPLATES_DIR)
    index = json.loads((_CATALOG_TEMPLATES_DIR / "index.json").read_text(encoding="utf-8"))
    expected_count = len(index["entries"])

    assert expected_count > 0
    assert len(store.entries) == expected_count
    assert set(store.all_recipe_ids()) == {e["recipe_id"] for e in index["entries"]}

    # Every entry's full EffectRecipe must actually load (not just index metadata).
    for recipe_id in store.all_recipe_ids():
        recipe = store.get_recipe(recipe_id)
        assert isinstance(recipe, EffectRecipe)
        assert recipe.recipe_id == recipe_id


# ============================================================================
# from_catalog_with_local_extensions / merge — tracked-catalog-then-local-
# extensions overlay used by production consumers (display_stages.py,
# taxonomy_utils.py, evidence.py) to optionally pick up a developer's local,
# untracked data/templates/ without requiring promotion into git first.
# ============================================================================


def test_from_catalog_with_local_extensions_merges_new_entries(
    store_dir: Path, tmp_path: Path
) -> None:
    """A local extensions dir with a new recipe_id adds to the tracked catalog."""
    local_dir = tmp_path / "local_ext"
    builtins = local_dir / "builtins"
    builtins.mkdir(parents=True)

    extra_recipe = {
        "recipe_id": "gtpl_accent_local_only",
        "name": "Local Only",
        "description": "Locally staged, not promoted",
        "recipe_version": "1.0.0",
        "effect_family": "color_wash",
        "template_type": "ACCENT",
        "visual_intent": "ABSTRACT",
        "tags": ["local"],
        "timing": {"bars_min": 1, "bars_max": 4},
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [
            {
                "layer_index": 0,
                "layer_name": "Hit",
                "layer_depth": "BACKGROUND",
                "effect_type": "ColorWash",
                "blend_mode": "NORMAL",
                "mix": 1.0,
                "params": {},
                "density": 0.9,
                "color_source": "palette_primary",
            }
        ],
        "provenance": {"source": "mined"},
        "style_markers": {"complexity": 0.2, "energy_affinity": "LOW"},
    }
    (builtins / "gtpl_accent_local_only.json").write_text(
        json.dumps(extra_recipe), encoding="utf-8"
    )
    local_index = {
        "schema_version": "template-index.v1",
        "total": 1,
        "entries": [
            {
                "recipe_id": "gtpl_accent_local_only",
                "name": "Local Only",
                "template_type": "ACCENT",
                "visual_intent": "ABSTRACT",
                "tags": ["local"],
                "source": "mined",
                "file": "builtins/gtpl_accent_local_only.json",
            }
        ],
    }
    (local_dir / "index.json").write_text(json.dumps(local_index), encoding="utf-8")

    store = TemplateStore.from_catalog_with_local_extensions(store_dir, local_dir)

    assert store.has_recipe("gtpl_base_wash_slow")  # from the tracked catalog
    assert store.has_recipe("gtpl_accent_local_only")  # from the local overlay
    recipe = store.get_recipe("gtpl_accent_local_only")
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == "gtpl_accent_local_only"


def test_from_catalog_with_local_extensions_overlay_shadows_same_recipe_id(
    store_dir: Path, tmp_path: Path
) -> None:
    """A local overlay entry with the same recipe_id as a catalog entry wins.

    Documented precedence: tracked-catalog-then-local-extensions — the local
    overlay is presumed newer/more specific, so both the metadata entry and
    the lazily-loaded EffectRecipe content must come from the overlay, not
    the tracked catalog, for a shared recipe_id.
    """
    local_dir = tmp_path / "local_ext"
    builtins = local_dir / "builtins"
    builtins.mkdir(parents=True)

    overriding_recipe = {
        "recipe_id": "gtpl_base_wash_slow",  # same id as the tracked catalog entry
        "name": "Wash Slow (local override)",
        "description": "Locally-edited override of the tracked recipe",
        "recipe_version": "2.0.0",
        "effect_family": "color_wash",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["wash", "slow", "local-override"],
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
        "provenance": {"source": "mined"},
        "style_markers": {"complexity": 0.33, "energy_affinity": "LOW"},
    }
    (builtins / "gtpl_base_wash_slow.json").write_text(
        json.dumps(overriding_recipe), encoding="utf-8"
    )
    local_index = {
        "schema_version": "template-index.v1",
        "total": 1,
        "entries": [
            {
                "recipe_id": "gtpl_base_wash_slow",
                "name": "Wash Slow (local override)",
                "template_type": "BASE",
                "visual_intent": "ABSTRACT",
                "tags": ["wash", "slow", "local-override"],
                "source": "mined",
                "file": "builtins/gtpl_base_wash_slow.json",
            }
        ],
    }
    (local_dir / "index.json").write_text(json.dumps(local_index), encoding="utf-8")

    store = TemplateStore.from_catalog_with_local_extensions(store_dir, local_dir)

    # Metadata entry comes from the overlay.
    entry = store.get_entry("gtpl_base_wash_slow")
    assert entry is not None
    assert entry.name == "Wash Slow (local override)"
    assert entry.source == "mined"

    # get_recipe() must resolve the file against the overlay's own base_dir,
    # not the tracked catalog's — this is the part that would silently
    # regress to the wrong content (or FileNotFoundError) without per-entry
    # base-dir tracking.
    recipe = store.get_recipe("gtpl_base_wash_slow")
    assert isinstance(recipe, EffectRecipe)
    assert recipe.name == "Wash Slow (local override)"
    assert recipe.recipe_version == "2.0.0"
    assert recipe.provenance.source == "mined"


def test_from_catalog_with_local_extensions_missing_overlay_is_noop(store_dir: Path) -> None:
    """A local extensions dir that doesn't exist is silently ignored."""
    store = TemplateStore.from_catalog_with_local_extensions(
        store_dir, store_dir.parent / "does_not_exist"
    )
    assert set(store.all_recipe_ids()) == {"gtpl_base_wash_slow", "gtpl_rhythm_pulse_fast"}


def test_from_catalog_with_local_extensions_none_overlay_is_noop(store_dir: Path) -> None:
    """A None local extensions dir is silently ignored."""
    store = TemplateStore.from_catalog_with_local_extensions(store_dir, None)
    assert set(store.all_recipe_ids()) == {"gtpl_base_wash_slow", "gtpl_rhythm_pulse_fast"}
