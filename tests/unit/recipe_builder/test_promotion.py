"""Tests for recipe_builder promotion — staged recipes → builtins + index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from twinklr.core.recipe_builder.promotion import (
    PromotionResult,
    promote_staged_recipes,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe


def _recipe_json(
    recipe_id: str = "gen_twinkle_v1",
    name: str = "Generated Twinkle",
    effect_type: str = "Twinkle",
    energy: str = "LOW",
    template_type: str = "BASE",
    source: str = "generated",
) -> dict:
    """Build a minimal recipe dict matching EffectRecipe schema."""
    return {
        "recipe_id": recipe_id,
        "name": name,
        "description": "Test generated recipe",
        "recipe_version": "1.0.0",
        "effect_family": effect_type.lower(),
        "template_type": template_type,
        "visual_intent": "ABSTRACT",
        "tags": ["generated", effect_type.lower()],
        "timing": {
            "bars_min": 2,
            "bars_max": 8,
            "beats_per_bar": None,
            "loop_len_ms": None,
            "emphasize_downbeats": False,
        },
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [
            {
                "layer_index": 0,
                "layer_name": "main",
                "layer_depth": "BACKGROUND",
                "effect_type": effect_type,
                "blend_mode": "NORMAL",
                "mix": 1.0,
                "density": 0.5,
                "color_source": "palette_primary",
            }
        ],
        "provenance": {"source": source, "curator_notes": None},
        "style_markers": {"complexity": 0.4, "energy_affinity": energy},
    }


def _write_staged(staged_dir: Path, recipe_id: str, **kwargs: str) -> Path:
    """Write a staged recipe JSON and return the path."""
    data = _recipe_json(recipe_id=recipe_id, **kwargs)
    path = staged_dir / f"{recipe_id}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def _make_index(templates_dir: Path, entries: list[dict] | None = None) -> Path:
    """Write an index.json and return its path."""
    entries = entries or []
    index = {
        "schema_version": "template-index.v1",
        "total": len(entries),
        "entries": entries,
    }
    index_path = templates_dir / "index.json"
    index_path.write_text(json.dumps(index, indent=2))
    return index_path


def _setup_dirs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create staged_dir, templates_dir, and builtins_dir."""
    staged_dir = tmp_path / "run" / "staged_recipes"
    staged_dir.mkdir(parents=True)
    templates_dir = tmp_path / "templates"
    builtins_dir = templates_dir / "builtins"
    builtins_dir.mkdir(parents=True)
    _make_index(templates_dir)
    return staged_dir, templates_dir, builtins_dir


# ---------------------------------------------------------------------------
# Test 1: promotes staged recipes into builtins directory
# ---------------------------------------------------------------------------


def test_copies_recipe_to_builtins(tmp_path: Path) -> None:
    """Promoted recipe JSON must appear in builtins/ directory."""
    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_twinkle_v1")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    promoted_file = builtins_dir / "gen_twinkle_v1.json"
    assert promoted_file.exists()
    data = json.loads(promoted_file.read_text())
    assert data["recipe_id"] == "gen_twinkle_v1"


# ---------------------------------------------------------------------------
# Test 2: updates provenance source to "generated"
# ---------------------------------------------------------------------------


def test_promoted_recipe_keeps_provenance(tmp_path: Path) -> None:
    """Promoted recipe retains its original provenance source."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_fire_v1", effect_type="Fire", source="generated")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    promoted = json.loads(
        (templates_dir / "builtins" / "gen_fire_v1.json").read_text()
    )
    assert promoted["provenance"]["source"] == "generated"


# ---------------------------------------------------------------------------
# Test 3: adds entry to index.json
# ---------------------------------------------------------------------------


def test_adds_entry_to_index(tmp_path: Path) -> None:
    """Promoted recipe must appear as a new entry in index.json."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_twinkle_v1")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    index = json.loads((templates_dir / "index.json").read_text())
    ids = [e["recipe_id"] for e in index["entries"]]
    assert "gen_twinkle_v1" in ids
    assert index["total"] == 1


# ---------------------------------------------------------------------------
# Test 4: index entry has correct metadata fields
# ---------------------------------------------------------------------------


def test_index_entry_metadata(tmp_path: Path) -> None:
    """Index entry must carry recipe_id, name, template_type, visual_intent, tags, source, file."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_spirals_v1", name="Generated Spirals",
                  effect_type="Spirals", template_type="ACCENT")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    index = json.loads((templates_dir / "index.json").read_text())
    entry = index["entries"][0]
    assert entry["recipe_id"] == "gen_spirals_v1"
    assert entry["name"] == "Generated Spirals"
    assert entry["template_type"] == "ACCENT"
    assert entry["visual_intent"] == "ABSTRACT"
    assert entry["file"] == "builtins/gen_spirals_v1.json"
    assert entry["source"] == "generated"
    assert isinstance(entry["tags"], list)


# ---------------------------------------------------------------------------
# Test 5: preserves existing index entries
# ---------------------------------------------------------------------------


def test_preserves_existing_index_entries(tmp_path: Path) -> None:
    """Existing entries in index.json must survive promotion."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)

    existing_entry = {
        "recipe_id": "gtpl_base_old",
        "name": "Old Builtin",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["old"],
        "source": "builtin",
        "file": "builtins/gtpl_base_old.json",
    }
    _make_index(templates_dir, entries=[existing_entry])

    _write_staged(staged_dir, "gen_new_v1")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    index = json.loads((templates_dir / "index.json").read_text())
    ids = [e["recipe_id"] for e in index["entries"]]
    assert "gtpl_base_old" in ids
    assert "gen_new_v1" in ids
    assert index["total"] == 2


# ---------------------------------------------------------------------------
# Test 6: skips duplicate recipe_id already in index
# ---------------------------------------------------------------------------


def test_skips_duplicate_recipe_id(tmp_path: Path) -> None:
    """If a recipe_id already exists in the index, it must be skipped."""
    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)

    existing_entry = {
        "recipe_id": "gen_twinkle_v1",
        "name": "Existing Twinkle",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["existing"],
        "source": "builtin",
        "file": "builtins/gen_twinkle_v1.json",
    }
    _make_index(templates_dir, entries=[existing_entry])
    (builtins_dir / "gen_twinkle_v1.json").write_text("{}")

    _write_staged(staged_dir, "gen_twinkle_v1")

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert result.skipped == 1
    assert result.promoted == 0


# ---------------------------------------------------------------------------
# Test 7: returns PromotionResult with counts
# ---------------------------------------------------------------------------


def test_returns_promotion_result(tmp_path: Path) -> None:
    """promote_staged_recipes must return PromotionResult with correct counts."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_a")
    _write_staged(staged_dir, "gen_b", effect_type="Fire", energy="HIGH")

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert isinstance(result, PromotionResult)
    assert result.promoted == 2
    assert result.skipped == 0
    assert len(result.promoted_ids) == 2
    assert "gen_a" in result.promoted_ids
    assert "gen_b" in result.promoted_ids


# ---------------------------------------------------------------------------
# Test 8: handles multiple promotions
# ---------------------------------------------------------------------------


def test_promotes_multiple_recipes(tmp_path: Path) -> None:
    """All staged recipes must be promoted and indexed."""
    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)
    for i in range(5):
        _write_staged(staged_dir, f"gen_recipe_{i}", name=f"Recipe {i}")

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert result.promoted == 5
    index = json.loads((templates_dir / "index.json").read_text())
    assert index["total"] == 5
    for i in range(5):
        assert (builtins_dir / f"gen_recipe_{i}.json").exists()


# ---------------------------------------------------------------------------
# Test 9: validates recipe JSON before promotion
# ---------------------------------------------------------------------------


def test_skips_invalid_recipe_json(tmp_path: Path) -> None:
    """Invalid recipe JSON must be skipped (not crash the run)."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_valid")
    (staged_dir / "gen_broken.json").write_text('{"invalid": true}')

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert result.promoted == 1
    assert result.skipped == 1
    assert "gen_broken" in result.skipped_ids


# ---------------------------------------------------------------------------
# Test 10: empty staged directory returns zero-count result
# ---------------------------------------------------------------------------


def test_empty_staged_dir(tmp_path: Path) -> None:
    """Empty staged dir must return PromotionResult with zero counts."""
    staged_dir, templates_dir, _ = _setup_dirs(tmp_path)

    result = promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    assert result.promoted == 0
    assert result.skipped == 0
    assert result.promoted_ids == []


# ---------------------------------------------------------------------------
# Test 11: staged directory does not exist raises clear error
# ---------------------------------------------------------------------------


def test_missing_staged_dir_raises(tmp_path: Path) -> None:
    """Non-existent staged dir must raise FileNotFoundError."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    _make_index(templates_dir)

    with pytest.raises(FileNotFoundError):
        promote_staged_recipes(
            staged_dir=tmp_path / "nonexistent",
            templates_dir=templates_dir,
        )


# ---------------------------------------------------------------------------
# Test 12: promoted recipe is valid EffectRecipe
# ---------------------------------------------------------------------------


def test_promoted_file_is_valid_effect_recipe(tmp_path: Path) -> None:
    """The promoted JSON must parse as a valid EffectRecipe."""
    staged_dir, templates_dir, builtins_dir = _setup_dirs(tmp_path)
    _write_staged(staged_dir, "gen_twinkle_v1")

    promote_staged_recipes(staged_dir=staged_dir, templates_dir=templates_dir)

    data = json.loads((builtins_dir / "gen_twinkle_v1.json").read_text())
    recipe = EffectRecipe.model_validate(data)
    assert recipe.recipe_id == "gen_twinkle_v1"
