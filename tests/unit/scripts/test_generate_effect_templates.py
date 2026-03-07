"""Tests for scripts/build/generate_effect_templates.py.

TDD: tests written before implementation.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from twinklr.core.sequencer.display.effects.handlers import load_builtin_handlers
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    EffectRecipe,
    ModelAffinity,
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
    """Load the generate_effect_templates script module."""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "build" / "generate_effect_templates.py"
    spec = importlib.util.spec_from_file_location("generate_effect_templates", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_layer(
    layer_index: int = 0,
    blend_mode: BlendMode = BlendMode.NORMAL,
    effect_type: str = "On",
    mix: float = 1.0,
) -> RecipeLayer:
    """Build a minimal RecipeLayer for testing."""
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer{layer_index}",
        layer_depth=VisualDepth.BACKGROUND,
        effect_type=effect_type,
        blend_mode=blend_mode,
        mix=mix,
        density=0.5,
        color_source="palette_primary",
    )


def _make_recipe(
    layers: list[RecipeLayer],
    template_type: GroupTemplateType = GroupTemplateType.BASE,
    recipe_id: str = "test_recipe_001",
    tags: list[str] | None = None,
    model_affinities: list[ModelAffinity] | None = None,
    bars_min: int | None = 1,
    bars_max: int | None = 4,
) -> EffectRecipe:
    """Build a minimal EffectRecipe for testing."""
    if tags is None:
        tags = ["test", "unit"]
    if model_affinities is None:
        model_affinities = [ModelAffinity(model_type="megatree", score=0.7)]
    return EffectRecipe(
        recipe_id=recipe_id,
        name="Test Recipe",
        description="Test",
        recipe_version="1.0.0",
        effect_family="bars",
        template_type=template_type,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=tags,
        timing=TimingHints(
            bars_min=bars_min,
            bars_max=bars_max,
            beats_per_bar=None,
            loop_len_ms=None,
            emphasize_downbeats=False,
        ),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=tuple(layers),
        provenance=RecipeProvenance(source="builtin", curator_notes=None),
        style_markers=StyleMarkers(
            complexity=0.3,
            energy_affinity=EnergyTarget.MED,
        ),
        model_affinities=model_affinities,
    )


# ---------------------------------------------------------------------------
# Test 1: valid 2-layer BASE recipe → no failures
# ---------------------------------------------------------------------------


def test_validate_valid_two_layer_base() -> None:
    """A valid 2-layer BASE recipe with non-NORMAL upper blend returns no failures."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers)
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    assert failures == []


# ---------------------------------------------------------------------------
# Test 2: 1-layer BASE → layer count failure
# ---------------------------------------------------------------------------


def test_validate_one_layer_base_fails() -> None:
    """A 1-layer BASE recipe must fail the layer count check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [_make_layer(0, BlendMode.NORMAL, "On")]
    recipe = _make_recipe(layers)
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("layer" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 3: upper layers all NORMAL blend → blend failure
# ---------------------------------------------------------------------------


def test_validate_upper_layers_normal_blend_fails() -> None:
    """A recipe where all upper layers have NORMAL blend must fail the blend check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [
        _make_layer(0, BlendMode.NORMAL, "On"),
        _make_layer(1, BlendMode.NORMAL, "Color Wash"),
    ]
    recipe = _make_recipe(layers)
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("blend" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 4: effect_type not in registry → handler failure
# ---------------------------------------------------------------------------


def test_validate_effect_type_not_in_registry_fails() -> None:
    """An effect type not registered in the handler registry must fail the handler check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [
        _make_layer(0, BlendMode.NORMAL, "UnknownEffectXYZ"),
        _make_layer(1, BlendMode.ADD, "Color Wash"),
    ]
    recipe = _make_recipe(layers)
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("handler" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 5: duplicate recipe_id → duplicate failure
# ---------------------------------------------------------------------------


def test_validate_duplicate_recipe_id_fails() -> None:
    """A recipe_id already in the index must fail the duplicate check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers, recipe_id="test_recipe_001")
    index = {"test_recipe_001": True}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("duplicate" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 6: empty model_affinities → affinities failure
# ---------------------------------------------------------------------------


def test_validate_empty_model_affinities_fails() -> None:
    """A recipe with no model_affinities must fail the affinities check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers, model_affinities=[])
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("affin" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 7: bars_min = 0 → timing failure
# ---------------------------------------------------------------------------


def test_validate_bars_min_zero_fails() -> None:
    """A recipe with bars_min=None (absent) and bars_max > 16 or bars_min < 1 must fail timing."""
    module = _load_module()
    registry = load_builtin_handlers()
    # bars_min must be >= 1 per TimingHints constraint, so use bars_max=17 to trigger timing failure
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers, bars_min=1, bars_max=20)
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("timing" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 8: empty tags → tags failure
# ---------------------------------------------------------------------------


def test_validate_empty_tags_fails() -> None:
    """A recipe with empty tags list must fail the tags check."""
    module = _load_module()
    registry = load_builtin_handlers()
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers, tags=[])
    index: dict[str, bool] = {}
    failures = module.validate_generated_template(recipe, registry, index)
    check_names = [f.check_name for f in failures]
    assert any("tag" in name.lower() for name in check_names)


# ---------------------------------------------------------------------------
# Test 9: assemble_fe_context returns profile and exemplars
# ---------------------------------------------------------------------------


def test_assemble_fe_context_returns_profile_and_exemplars() -> None:
    """assemble_fe_context must return effect_metadata_profile and stack_recipe_exemplars."""
    module = _load_module()
    layers = [_make_layer(0, BlendMode.NORMAL, "On"), _make_layer(1, BlendMode.ADD, "Color Wash")]
    recipe = _make_recipe(layers)
    effect_metadata = {
        "Pinwheel": {
            "corpus_phrase_count": 5,
            "summary": "Spinning pattern",
        }
    }
    catalog = [recipe, recipe]
    result = module.assemble_fe_context(
        effect_family="Pinwheel",
        lane="base",
        effect_metadata=effect_metadata,
        recipe_catalog=catalog,
    )
    assert "effect_metadata_profile" in result
    assert "stack_recipe_exemplars" in result
    assert "target_lane" in result


# ---------------------------------------------------------------------------
# Test 10: assemble_fe_context handles missing metadata gracefully
# ---------------------------------------------------------------------------


def test_assemble_fe_context_missing_metadata() -> None:
    """assemble_fe_context must handle a missing effect_family key gracefully."""
    module = _load_module()
    result = module.assemble_fe_context(
        effect_family="NonExistentEffect",
        lane="base",
        effect_metadata={},
        recipe_catalog=[],
    )
    assert "effect_metadata_profile" in result
    assert result["effect_metadata_profile"] is None
    assert "stack_recipe_exemplars" in result
    assert result["stack_recipe_exemplars"] == []


# ---------------------------------------------------------------------------
# Test 11: select_mode with corpus → "fe_grounded"
# ---------------------------------------------------------------------------


def test_select_mode_with_corpus() -> None:
    """select_mode returns 'fe_grounded' when corpus_phrase_count > 0."""
    module = _load_module()
    effect_metadata = {"Pinwheel": {"corpus_phrase_count": 10}}
    result = module.select_mode("Pinwheel", effect_metadata)
    assert result == "fe_grounded"


# ---------------------------------------------------------------------------
# Test 12: select_mode without corpus → "llm_creative"
# ---------------------------------------------------------------------------


def test_select_mode_without_corpus() -> None:
    """select_mode returns 'llm_creative' when corpus_phrase_count = 0 or missing."""
    module = _load_module()
    effect_metadata = {"Pinwheel": {"corpus_phrase_count": 0}}
    assert module.select_mode("Pinwheel", effect_metadata) == "llm_creative"
    assert module.select_mode("UnknownEffect", effect_metadata) == "llm_creative"
    assert module.select_mode("Pinwheel", {}) == "llm_creative"


# ---------------------------------------------------------------------------
# Test 13: Pinwheel templates pass all 8 validation checks
# ---------------------------------------------------------------------------


def test_pinwheel_templates_pass_validation() -> None:
    """The hand-authored Pinwheel JSON templates must pass all 8 validation checks."""
    module = _load_module()
    registry = load_builtin_handlers()
    builtins_dir = Path(__file__).resolve().parents[3] / "data" / "templates" / "builtins"

    pinwheel_files = [
        builtins_dir / "pinwheel_base_001.json",
        builtins_dir / "pinwheel_rhythm_001.json",
    ]
    index: dict[str, bool] = {}

    for path in pinwheel_files:
        assert path.exists(), f"Missing pinwheel template: {path}"
        recipe = EffectRecipe.model_validate(json.loads(path.read_text(encoding="utf-8")))
        failures = module.validate_generated_template(recipe, registry, index)
        assert failures == [], f"{path.name} validation failures: {failures}"
        index[recipe.recipe_id] = True


# ---------------------------------------------------------------------------
# Test 14: script dry-run mode processes target list without LLM calls
# ---------------------------------------------------------------------------


def test_generate_script_dry_run(tmp_path: Path) -> None:
    """In dry-run mode the script processes its target list and writes a report without LLM calls."""
    module = _load_module()
    targets = ["Pinwheel", "Twinkle"]
    output_path = tmp_path / "dry_run_report.json"
    module.run_dry_run(targets=targets, output=output_path)
    assert output_path.exists()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert "targets" in report
    assert "mode" in report
    assert report["mode"] == "dry_run"
    assert len(report["targets"]) == len(targets)


# ---------------------------------------------------------------------------
# Test 15: ValidationFailure has check_name and message fields
# ---------------------------------------------------------------------------


def test_validation_failure_model() -> None:
    """ValidationFailure dataclass must have check_name and message fields."""
    module = _load_module()
    vf = module.ValidationFailure(check_name="layer_count", message="Need at least 2 layers")
    assert vf.check_name == "layer_count"
    assert vf.message == "Need at least 2 layers"
