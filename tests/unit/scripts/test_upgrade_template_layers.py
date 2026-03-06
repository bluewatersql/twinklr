"""Tests for scripts/build/upgrade_template_layers.py.

TDD: tests written before implementation.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
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
    MotionVerb,
    VisualDepth,
)


def _load_module():
    """Load the upgrade_template_layers script module."""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "build" / "upgrade_template_layers.py"
    spec = importlib.util.spec_from_file_location("upgrade_template_layers", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_layer(
    layer_index: int = 0,
    effect_type: str = "Spirals",
    blend_mode: BlendMode = BlendMode.NORMAL,
    mix: float = 1.0,
    layer_depth: VisualDepth = VisualDepth.BACKGROUND,
) -> RecipeLayer:
    """Build a minimal RecipeLayer for testing."""
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer{layer_index}",
        layer_depth=layer_depth,
        effect_type=effect_type,
        blend_mode=blend_mode,
        mix=mix,
        params={},
        motion=[MotionVerb.FADE],
        density=0.5,
        color_source=ColorSource.PALETTE_PRIMARY,
    )


def _make_recipe(
    recipe_id: str = "test_001",
    effect_type: str = "Spirals",
    template_type: GroupTemplateType = GroupTemplateType.BASE,
    tags: list[str] | None = None,
    layers: list[RecipeLayer] | None = None,
) -> EffectRecipe:
    """Build a minimal EffectRecipe for testing."""
    if layers is None:
        layers = [_make_layer(0, effect_type=effect_type)]
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test",
        description="Test template",
        recipe_version="1.0.0",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=tags if tags is not None else ["test"],
        timing=TimingHints(bars_min=2, bars_max=8),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary"]),
        layers=tuple(layers),
        provenance=RecipeProvenance(source="builtin"),
        style_markers=StyleMarkers(complexity=0.3, energy_affinity=EnergyTarget.MED),
    )


def _make_two_layer_dict(
    recipe_id: str = "test_001",
    bottom_effect_type: str = "Spirals",
    upper_blend_mode: str = "ADD",
    tags: list[str] | None = None,
    template_type: str = "BASE",
) -> dict:
    """Build a raw dict for a valid 2-layer upgraded recipe."""
    return {
        "recipe_id": recipe_id,
        "name": "Test",
        "description": "Test template",
        "recipe_version": "1.0.0",
        "template_type": template_type,
        "visual_intent": "ABSTRACT",
        "tags": tags if tags is not None else ["test"],
        "timing": {
            "bars_min": 2,
            "bars_max": 8,
            "beats_per_bar": None,
            "loop_len_ms": None,
            "emphasize_downbeats": False,
        },
        "palette_spec": {"mode": "DICHROME", "palette_roles": ["primary"]},
        "layers": [
            {
                "layer_index": 0,
                "layer_name": "Base",
                "layer_depth": "BACKGROUND",
                "effect_type": bottom_effect_type,
                "blend_mode": "NORMAL",
                "mix": 1.0,
                "params": {},
                "motion": ["FADE"],
                "density": 0.5,
                "color_source": "palette_primary",
                "timing_offset_beats": None,
            },
            {
                "layer_index": 1,
                "layer_name": "Upper",
                "layer_depth": "FOREGROUND",
                "effect_type": "ColorWash",
                "blend_mode": upper_blend_mode,
                "mix": 0.6,
                "params": {},
                "motion": [],
                "density": 0.5,
                "color_source": "palette_primary",
                "timing_offset_beats": None,
            },
        ],
        "provenance": {"source": "builtin", "curator_notes": None},
        "style_markers": {"complexity": 0.3, "energy_affinity": "MED"},
        "model_affinities": [],
        "motif_compatibility": [],
    }


# ---------------------------------------------------------------------------
# Test 1: valid 2-layer upgrade
# ---------------------------------------------------------------------------


def test_validate_valid_two_layer_upgrade() -> None:
    """validate_upgraded_recipe: valid 2-layer upgrade → (True, '', recipe)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", effect_type="Spirals", tags=["test"])
    upgraded_raw = _make_two_layer_dict(
        recipe_id="test_001",
        bottom_effect_type="Spirals",
        upper_blend_mode="ADD",
        tags=["test"],
    )
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, upgraded_raw)
    assert is_valid is True
    assert reason == ""
    assert recipe is not None


# ---------------------------------------------------------------------------
# Test 2: 1-layer BASE → (False, "layer count", None)
# ---------------------------------------------------------------------------


def test_validate_one_layer_base_fails() -> None:
    """validate_upgraded_recipe: 1-layer output for BASE template → (False, 'layer count', None)."""
    module = _load_module()
    original = _make_recipe(
        recipe_id="test_001",
        effect_type="Spirals",
        template_type=GroupTemplateType.BASE,
        tags=["test"],
    )
    # Only 1 layer in upgraded
    raw = _make_two_layer_dict(recipe_id="test_001", bottom_effect_type="Spirals", tags=["test"])
    raw["layers"] = raw["layers"][:1]  # truncate to 1 layer
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "layer count"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 3: recipe_id mismatch → (False, "recipe_id", None)
# ---------------------------------------------------------------------------


def test_validate_recipe_id_mismatch_fails() -> None:
    """validate_upgraded_recipe: recipe_id mismatch → (False, 'recipe_id', None)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", tags=["test"])
    raw = _make_two_layer_dict(recipe_id="different_id", tags=["test"])
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "recipe_id"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 4: bottom layer effect_type changed → (False, "effect_type", None)
# ---------------------------------------------------------------------------


def test_validate_bottom_layer_effect_type_changed_fails() -> None:
    """validate_upgraded_recipe: bottom layer effect_type changed → (False, 'effect_type', None)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", effect_type="Spirals", tags=["test"])
    raw = _make_two_layer_dict(
        recipe_id="test_001",
        bottom_effect_type="ColorWash",  # changed from Spirals
        tags=["test"],
    )
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "effect_type"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 5: tags removed → (False, "tags", None)
# ---------------------------------------------------------------------------


def test_validate_tags_removed_fails() -> None:
    """validate_upgraded_recipe: tags removed → (False, 'tags', None)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", tags=["test", "sparkle"])
    # upgraded only has "test", missing "sparkle"
    raw = _make_two_layer_dict(recipe_id="test_001", tags=["test"])
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "tags"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 6: invalid Pydantic schema → (False, "schema", None)
# ---------------------------------------------------------------------------


def test_validate_invalid_pydantic_schema_fails() -> None:
    """validate_upgraded_recipe: invalid Pydantic schema → (False, 'schema', None)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", tags=["test"])
    raw = {"recipe_id": "test_001", "broken": "data"}  # invalid schema
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "schema"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 7: upper layers all NORMAL blend → (False, "blend", None)
# ---------------------------------------------------------------------------


def test_validate_upper_layers_all_normal_blend_fails() -> None:
    """validate_upgraded_recipe: upper layers all NORMAL blend → (False, 'blend', None)."""
    module = _load_module()
    original = _make_recipe(recipe_id="test_001", effect_type="Spirals", tags=["test"])
    raw = _make_two_layer_dict(
        recipe_id="test_001",
        bottom_effect_type="Spirals",
        upper_blend_mode="NORMAL",  # all NORMAL — should fail blend check
        tags=["test"],
    )
    is_valid, reason, recipe = module.validate_upgraded_recipe(original, raw)
    assert is_valid is False
    assert reason == "blend"
    assert recipe is None


# ---------------------------------------------------------------------------
# Test 8: pipeline assembles correct context (mock LLM)
# ---------------------------------------------------------------------------


def test_upgrade_pipeline_assembles_correct_context(tmp_path: Path) -> None:
    """Upgrade pipeline assembles context with template + optional metadata."""
    module = _load_module()

    # Build a minimal audit report with one FLAT candidate
    original = _make_recipe(recipe_id="spirals_base_001", effect_type="Spirals", tags=["test"])
    original_json = original.model_dump(mode="json")
    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    (builtins_dir / "spirals_base_001.json").write_text(json.dumps(original_json), encoding="utf-8")

    audit_report = {
        "entries": [
            {
                "recipe_id": "spirals_base_001",
                "posture": "FLAT",
                "effect_type": "Spirals",
                "template_type": "BASE",
                "layer_count": 1,
                "tags": ["test"],
                "upper_layer_blend_modes": [],
                "upper_layer_mixes": [],
            }
        ],
        "summary": {"total_flat": 1, "total_thin": 0, "total_rich": 0, "upgrade_candidates": 1},
    }
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report), encoding="utf-8")
    output_dir = tmp_path / "staged_upgrades"

    # Mock LLM to capture the context assembled
    captured_contexts: list[dict] = []

    upgraded_raw = _make_two_layer_dict(
        recipe_id="spirals_base_001",
        bottom_effect_type="Spirals",
        tags=["test"],
    )

    def mock_call_llm(context: dict, client: object) -> dict:
        captured_contexts.append(context)
        return upgraded_raw

    with patch.object(module, "call_llm", side_effect=mock_call_llm):
        module.run_upgrade_pipeline(
            audit_report_path=audit_path,
            builtins_dir=builtins_dir,
            output_dir=output_dir,
            batch_size=10,
        )

    assert len(captured_contexts) == 1
    ctx = captured_contexts[0]
    assert "template" in ctx
    assert ctx["template"]["recipe_id"] == "spirals_base_001"


# ---------------------------------------------------------------------------
# Test 9: pipeline stages to output path (mock LLM)
# ---------------------------------------------------------------------------


def test_upgrade_pipeline_stages_to_output_path(tmp_path: Path) -> None:
    """Upgrade pipeline stages upgraded recipe to output_dir/{recipe_id}.json."""
    module = _load_module()

    original = _make_recipe(recipe_id="spirals_base_001", effect_type="Spirals", tags=["test"])
    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    (builtins_dir / "spirals_base_001.json").write_text(
        json.dumps(original.model_dump(mode="json")), encoding="utf-8"
    )

    audit_report = {
        "entries": [
            {
                "recipe_id": "spirals_base_001",
                "posture": "FLAT",
                "effect_type": "Spirals",
                "template_type": "BASE",
                "layer_count": 1,
                "tags": ["test"],
                "upper_layer_blend_modes": [],
                "upper_layer_mixes": [],
            }
        ],
        "summary": {"upgrade_candidates": 1},
    }
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report), encoding="utf-8")
    output_dir = tmp_path / "staged_upgrades"

    upgraded_raw = _make_two_layer_dict(
        recipe_id="spirals_base_001",
        bottom_effect_type="Spirals",
        tags=["test"],
    )

    with patch.object(module, "call_llm", return_value=upgraded_raw):
        module.run_upgrade_pipeline(
            audit_report_path=audit_path,
            builtins_dir=builtins_dir,
            output_dir=output_dir,
            batch_size=10,
        )

    staged_file = output_dir / "spirals_base_001.json"
    assert staged_file.exists()
    staged_data = json.loads(staged_file.read_text())
    assert staged_data["recipe_id"] == "spirals_base_001"
    assert len(staged_data["layers"]) == 2


# ---------------------------------------------------------------------------
# Test 10: pipeline writes upgrade_report.json (mock LLM)
# ---------------------------------------------------------------------------


def test_upgrade_pipeline_writes_upgrade_report(tmp_path: Path) -> None:
    """Upgrade pipeline writes upgrade_report.json with success/failure counts."""
    module = _load_module()

    original = _make_recipe(recipe_id="spirals_base_001", effect_type="Spirals", tags=["test"])
    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    (builtins_dir / "spirals_base_001.json").write_text(
        json.dumps(original.model_dump(mode="json")), encoding="utf-8"
    )

    audit_report = {
        "entries": [
            {
                "recipe_id": "spirals_base_001",
                "posture": "FLAT",
                "effect_type": "Spirals",
                "template_type": "BASE",
                "layer_count": 1,
                "tags": ["test"],
                "upper_layer_blend_modes": [],
                "upper_layer_mixes": [],
            }
        ],
        "summary": {"upgrade_candidates": 1},
    }
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report), encoding="utf-8")
    output_dir = tmp_path / "staged_upgrades"

    upgraded_raw = _make_two_layer_dict(
        recipe_id="spirals_base_001",
        bottom_effect_type="Spirals",
        tags=["test"],
    )

    with patch.object(module, "call_llm", return_value=upgraded_raw):
        module.run_upgrade_pipeline(
            audit_report_path=audit_path,
            builtins_dir=builtins_dir,
            output_dir=output_dir,
            batch_size=10,
        )

    # upgrade_report.json lives in the features dir relative to output_dir parent
    report_path = output_dir.parent / "upgrade_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert "success_count" in report
    assert "failure_count" in report
    assert report["success_count"] == 1
    assert report["failure_count"] == 0


# ---------------------------------------------------------------------------
# Test 11: pipeline skips already-staged (resume support)
# ---------------------------------------------------------------------------


def test_upgrade_pipeline_skips_already_staged(tmp_path: Path) -> None:
    """Upgrade pipeline skips templates that already have a staged file."""
    module = _load_module()

    original = _make_recipe(recipe_id="spirals_base_001", effect_type="Spirals", tags=["test"])
    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    (builtins_dir / "spirals_base_001.json").write_text(
        json.dumps(original.model_dump(mode="json")), encoding="utf-8"
    )

    audit_report = {
        "entries": [
            {
                "recipe_id": "spirals_base_001",
                "posture": "FLAT",
                "effect_type": "Spirals",
                "template_type": "BASE",
                "layer_count": 1,
                "tags": ["test"],
                "upper_layer_blend_modes": [],
                "upper_layer_mixes": [],
            }
        ],
        "summary": {"upgrade_candidates": 1},
    }
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report), encoding="utf-8")

    # Pre-stage the output file to simulate resume
    output_dir = tmp_path / "staged_upgrades"
    output_dir.mkdir()
    already_staged = _make_two_layer_dict(
        recipe_id="spirals_base_001",
        bottom_effect_type="Spirals",
        tags=["test"],
    )
    (output_dir / "spirals_base_001.json").write_text(json.dumps(already_staged), encoding="utf-8")

    call_count = 0

    def mock_call_llm(context: dict, client: object) -> dict:
        nonlocal call_count
        call_count += 1
        return already_staged

    with patch.object(module, "call_llm", side_effect=mock_call_llm):
        module.run_upgrade_pipeline(
            audit_report_path=audit_path,
            builtins_dir=builtins_dir,
            output_dir=output_dir,
            batch_size=10,
        )

    # LLM should NOT have been called since the file is already staged
    assert call_count == 0


# ---------------------------------------------------------------------------
# Test 12: pipeline handles LLM API error gracefully
# ---------------------------------------------------------------------------


def test_upgrade_pipeline_handles_llm_error(tmp_path: Path) -> None:
    """Upgrade pipeline handles LLM API error gracefully (logs failure, continues)."""
    module = _load_module()

    original = _make_recipe(recipe_id="spirals_base_001", effect_type="Spirals", tags=["test"])
    builtins_dir = tmp_path / "builtins"
    builtins_dir.mkdir()
    (builtins_dir / "spirals_base_001.json").write_text(
        json.dumps(original.model_dump(mode="json")), encoding="utf-8"
    )

    audit_report = {
        "entries": [
            {
                "recipe_id": "spirals_base_001",
                "posture": "FLAT",
                "effect_type": "Spirals",
                "template_type": "BASE",
                "layer_count": 1,
                "tags": ["test"],
                "upper_layer_blend_modes": [],
                "upper_layer_mixes": [],
            }
        ],
        "summary": {"upgrade_candidates": 1},
    }
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(json.dumps(audit_report), encoding="utf-8")
    output_dir = tmp_path / "staged_upgrades"

    def mock_call_llm_error(context: dict, client: object) -> dict:
        raise RuntimeError("LLM API rate limit exceeded")

    with patch.object(module, "call_llm", side_effect=mock_call_llm_error):
        # Should not raise — must handle gracefully
        module.run_upgrade_pipeline(
            audit_report_path=audit_path,
            builtins_dir=builtins_dir,
            output_dir=output_dir,
            batch_size=10,
        )

    # No staged file should have been created
    assert not (output_dir / "spirals_base_001.json").exists()

    # upgrade_report.json should record the failure
    report_path = output_dir.parent / "upgrade_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["failure_count"] == 1
    assert report["success_count"] == 0
