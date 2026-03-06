"""Tests for scripts/build/align_templates.py.

TDD: tests written before implementation.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    PaletteSpec,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    VisualDepth,
)


def _load_module():
    """Load the align_templates script module."""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "build" / "align_templates.py"
    spec = importlib.util.spec_from_file_location("align_templates", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_layer(
    layer_index: int = 0,
    effect_type: str = "On",
    blend_mode: BlendMode = BlendMode.NORMAL,
    mix: float = 1.0,
) -> RecipeLayer:
    """Build a minimal RecipeLayer for testing."""
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer{layer_index}",
        layer_depth=VisualDepth.FOREGROUND,
        effect_type=effect_type,
        blend_mode=blend_mode,
        mix=mix,
        density=0.5,
        color_source="palette_primary",
    )


def _make_recipe(
    layers: list[RecipeLayer],
    recipe_id: str = "test_recipe_001",
    template_type: GroupTemplateType = GroupTemplateType.BASE,
    tags: list[str] | None = None,
) -> EffectRecipe:
    """Build a minimal EffectRecipe for testing."""
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test Recipe",
        description="Test",
        recipe_version="1.0.0",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=tags if tags is not None else ["test"],
        timing=TimingHints(
            bars_min=1,
            bars_max=4,
            beats_per_bar=None,
            loop_len_ms=None,
            emphasize_downbeats=False,
        ),
        palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
        layers=tuple(layers),
        provenance=RecipeProvenance(source="builtin", curator_notes=None),
        style_markers=StyleMarkers(
            complexity=0.3,
            energy_affinity=EnergyTarget.MED,
        ),
    )


# ---------------------------------------------------------------------------
# Test 1: structural_similarity_identical — identical recipes → 1.0
# ---------------------------------------------------------------------------


def test_structural_similarity_identical() -> None:
    """Identical recipes must score 1.0."""
    module = _load_module()
    layer = _make_layer(0, effect_type="On", blend_mode=BlendMode.NORMAL)
    recipe = _make_recipe([layer], tags=["test", "ambient"])
    score = module.structural_similarity(recipe, recipe)
    assert score == 1.0


# ---------------------------------------------------------------------------
# Test 2: structural_similarity_different_effect_type — different effect_type → ≤0.6
# ---------------------------------------------------------------------------


def test_structural_similarity_different_effect_type() -> None:
    """Recipes with different primary effect_type must score ≤ 0.6."""
    module = _load_module()
    layer_a = _make_layer(0, effect_type="On")
    layer_b = _make_layer(0, effect_type="Sparkle")
    recipe_a = _make_recipe([layer_a], tags=["test"])
    recipe_b = _make_recipe([layer_b], tags=["test"])
    score = module.structural_similarity(recipe_a, recipe_b)
    assert score <= 0.6


# ---------------------------------------------------------------------------
# Test 3: structural_similarity_tag_partial — same type/template but different tags
# ---------------------------------------------------------------------------


def test_structural_similarity_tag_partial() -> None:
    """Partial tag overlap yields a partial score contribution."""
    module = _load_module()
    layer = _make_layer(0, effect_type="On")
    recipe_a = _make_recipe([layer], tags=["a", "b", "c", "d"])
    recipe_b = _make_recipe([layer], tags=["a", "b", "e", "f"])
    score_full = module.structural_similarity(recipe_a, recipe_a)
    score_partial = module.structural_similarity(recipe_a, recipe_b)
    # Partial should be lower than identical but positive
    assert 0.0 < score_partial < score_full


# ---------------------------------------------------------------------------
# Test 4: decide_alignment_replace — score>0.85 + promoted match → "REPLACE"
# ---------------------------------------------------------------------------


def test_decide_alignment_replace() -> None:
    """Score > 0.85 with a promoted match must yield REPLACE."""
    module = _load_module()
    layer = _make_layer(0, effect_type="On")
    promoted = _make_recipe([layer], recipe_id="promoted_001")
    result = module.decide_alignment(score=0.90, promoted_match=promoted)
    assert result == "REPLACE"


# ---------------------------------------------------------------------------
# Test 5: decide_alignment_keep — score<0.6 + promoted match → "KEEP"
# ---------------------------------------------------------------------------


def test_decide_alignment_keep() -> None:
    """Score < 0.6 with a promoted match must yield KEEP."""
    module = _load_module()
    layer = _make_layer(0, effect_type="On")
    promoted = _make_recipe([layer], recipe_id="promoted_001")
    result = module.decide_alignment(score=0.50, promoted_match=promoted)
    assert result == "KEEP"


# ---------------------------------------------------------------------------
# Test 6: decide_alignment_preserve — no promoted match → "PRESERVE"
# ---------------------------------------------------------------------------


def test_decide_alignment_preserve() -> None:
    """No promoted match must yield PRESERVE regardless of score."""
    module = _load_module()
    result = module.decide_alignment(score=0.95, promoted_match=None)
    assert result == "PRESERVE"


# ---------------------------------------------------------------------------
# Test 7: align_script_reads_inputs — reads staged_upgrades and recipe_catalog
# ---------------------------------------------------------------------------


def test_align_script_reads_inputs(tmp_path: Path) -> None:
    """run_alignment reads staged_upgrades dir and recipe_catalog_path."""
    module = _load_module()

    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    staged_dir = tmp_path / "staged_upgrades"
    staged_dir.mkdir()
    deprecated_dir = tmp_path / "deprecated"
    deprecated_dir.mkdir()
    report_output = tmp_path / "alignment_report.json"
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps({"schema_version": "template-index.v1", "total": 0, "entries": []}),
        encoding="utf-8",
    )

    # Minimal recipe_catalog with one entry
    layer_data = {
        "layer_index": 0,
        "layer_name": "Layer0",
        "layer_depth": "FOREGROUND",
        "effect_type": "On",
        "blend_mode": "NORMAL",
        "mix": 1.0,
        "density": 0.5,
        "color_source": "palette_primary",
    }
    recipe_data = {
        "recipe_id": "promoted_001",
        "name": "Promoted 001",
        "description": "Test",
        "recipe_version": "1.0.0",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["test"],
        "timing": {
            "bars_min": 1,
            "bars_max": 4,
            "beats_per_bar": None,
            "loop_len_ms": None,
            "emphasize_downbeats": False,
        },
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [layer_data],
        "provenance": {"source": "promoted", "curator_notes": None},
        "style_markers": {"complexity": 0.3, "energy_affinity": "MED"},
    }
    catalog_path = tmp_path / "recipe_catalog.json"
    catalog_path.write_text(json.dumps({"recipes": [recipe_data]}), encoding="utf-8")

    # Should not raise even with empty builtins/staged dirs
    module.run_alignment(
        builtins_dir=builtins_dir,
        staged_dir=staged_dir,
        recipe_catalog_path=catalog_path,
        deprecated_dir=deprecated_dir,
        report_output=report_output,
        index_path=index_path,
    )
    assert report_output.exists()


# ---------------------------------------------------------------------------
# Test 8: align_script_writes_report — writes alignment_report.json
# ---------------------------------------------------------------------------


def test_align_script_writes_report(tmp_path: Path) -> None:
    """run_alignment writes alignment_report.json with required structure."""
    module = _load_module()

    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    staged_dir = tmp_path / "staged_upgrades"
    staged_dir.mkdir()
    deprecated_dir = tmp_path / "deprecated"
    deprecated_dir.mkdir()
    report_output = tmp_path / "alignment_report.json"
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps({"schema_version": "template-index.v1", "total": 0, "entries": []}),
        encoding="utf-8",
    )
    catalog_path = tmp_path / "recipe_catalog.json"
    catalog_path.write_text(json.dumps({"recipes": []}), encoding="utf-8")

    module.run_alignment(
        builtins_dir=builtins_dir,
        staged_dir=staged_dir,
        recipe_catalog_path=catalog_path,
        deprecated_dir=deprecated_dir,
        report_output=report_output,
        index_path=index_path,
    )

    report = json.loads(report_output.read_text())
    assert "generated_at" in report
    assert "entries" in report
    assert "summary" in report
    summary = report["summary"]
    assert "replace_count" in summary
    assert "review_count" in summary
    assert "keep_count" in summary
    assert "preserve_count" in summary


# ---------------------------------------------------------------------------
# Test 9: apply_replace_moves_to_deprecated — moves files to deprecated/
# ---------------------------------------------------------------------------


def test_apply_replace_moves_to_deprecated(tmp_path: Path) -> None:
    """apply_replace_decisions moves builtin files to deprecated/ directory."""
    module = _load_module()

    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    deprecated_dir = tmp_path / "deprecated"
    deprecated_dir.mkdir()

    # Create a minimal builtin recipe file
    layer_data = {
        "layer_index": 0,
        "layer_name": "Layer0",
        "layer_depth": "FOREGROUND",
        "effect_type": "On",
        "blend_mode": "NORMAL",
        "mix": 1.0,
        "density": 0.5,
        "color_source": "palette_primary",
    }
    recipe_data = {
        "recipe_id": "builtin_001",
        "name": "Builtin 001",
        "description": "Test",
        "recipe_version": "1.0.0",
        "template_type": "BASE",
        "visual_intent": "ABSTRACT",
        "tags": ["test"],
        "timing": {
            "bars_min": 1,
            "bars_max": 4,
            "beats_per_bar": None,
            "loop_len_ms": None,
            "emphasize_downbeats": False,
        },
        "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
        "layers": [layer_data],
        "provenance": {"source": "builtin", "curator_notes": None},
        "style_markers": {"complexity": 0.3, "energy_affinity": "MED"},
    }
    builtin_file = builtins_dir / "builtin_001.json"
    builtin_file.write_text(json.dumps(recipe_data), encoding="utf-8")

    # Build a replace decision entry
    entries = [
        {
            "recipe_id": "builtin_001",
            "action": "REPLACE",
            "matched_promoted_id": "promoted_001",
            "similarity_score": 0.90,
        }
    ]

    module.apply_replace_decisions(
        entries=entries,
        builtins_dir=builtins_dir,
        deprecated_dir=deprecated_dir,
    )

    # File should have moved to deprecated/
    assert not builtin_file.exists()
    assert (deprecated_dir / "builtin_001.json").exists()


# ---------------------------------------------------------------------------
# Test 10: tag_propagation_to_promoted — promoted inherits missing tags
# ---------------------------------------------------------------------------


def test_tag_propagation_to_promoted(tmp_path: Path) -> None:
    """Promoted replacement recipe inherits missing tags from deprecated builtin."""
    module = _load_module()

    layer_data = {
        "layer_index": 0,
        "layer_name": "Layer0",
        "layer_depth": "FOREGROUND",
        "effect_type": "On",
        "blend_mode": "NORMAL",
        "mix": 1.0,
        "density": 0.5,
        "color_source": "palette_primary",
    }

    def _make_json(recipe_id: str, tags: list[str], source: str = "builtin") -> dict:
        return {
            "recipe_id": recipe_id,
            "name": recipe_id,
            "description": "Test",
            "recipe_version": "1.0.0",
            "template_type": "BASE",
            "visual_intent": "ABSTRACT",
            "tags": tags,
            "timing": {
                "bars_min": 1,
                "bars_max": 4,
                "beats_per_bar": None,
                "loop_len_ms": None,
                "emphasize_downbeats": False,
            },
            "palette_spec": {"mode": "MONOCHROME", "palette_roles": ["primary"]},
            "layers": [layer_data],
            "provenance": {"source": source, "curator_notes": None},
            "style_markers": {"complexity": 0.3, "energy_affinity": "MED"},
        }

    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    staged_dir = tmp_path / "staged_upgrades"
    staged_dir.mkdir()

    # Deprecated builtin has unique tags ["rare_tag", "old_tag"]
    deprecated_data = _make_json("builtin_001", ["test", "rare_tag", "old_tag"])
    (builtins_dir / "builtin_001.json").write_text(json.dumps(deprecated_data), encoding="utf-8")

    # Promoted only has ["test", "new_tag"]
    promoted_data = _make_json("promoted_001", ["test", "new_tag"], source="promoted")
    (staged_dir / "promoted_001.json").write_text(json.dumps(promoted_data), encoding="utf-8")

    entries = [
        {
            "recipe_id": "builtin_001",
            "action": "REPLACE",
            "matched_promoted_id": "promoted_001",
            "similarity_score": 0.90,
        }
    ]

    module.propagate_tags(
        entries=entries,
        builtins_dir=builtins_dir,
        staged_dir=staged_dir,
    )

    # After propagation, promoted recipe should have inherited rare_tag and old_tag
    updated = json.loads((staged_dir / "promoted_001.json").read_text())
    updated_tags = set(updated["tags"])
    assert "rare_tag" in updated_tags
    assert "old_tag" in updated_tags
    # Original tags preserved
    assert "test" in updated_tags
    assert "new_tag" in updated_tags
