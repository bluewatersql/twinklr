"""Tests for scripts/build/audit_template_structure.py.

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
    """Load the audit_template_structure script module."""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "scripts" / "build" / "audit_template_structure.py"
    spec = importlib.util.spec_from_file_location("audit_template_structure", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_layer(
    layer_index: int = 0,
    blend_mode: BlendMode = BlendMode.NORMAL,
    mix: float = 1.0,
) -> RecipeLayer:
    """Build a minimal RecipeLayer for testing."""
    return RecipeLayer(
        layer_index=layer_index,
        layer_name=f"Layer{layer_index}",
        layer_depth=VisualDepth.FOREGROUND,
        effect_type="On",
        blend_mode=blend_mode,
        mix=mix,
        density=0.5,
        color_source="palette_primary",
    )


def _make_recipe(layers: list[RecipeLayer], effect_type: str = "On") -> EffectRecipe:
    """Build a minimal EffectRecipe for testing."""
    return EffectRecipe(
        recipe_id="test_recipe_001",
        name="Test Recipe",
        description="Test",
        recipe_version="1.0.0",
        effect_family="bars",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["test"],
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
# Test 1: single-layer recipe → FLAT
# ---------------------------------------------------------------------------


def test_classify_posture_single_layer_is_flat() -> None:
    """A recipe with one layer must be classified as FLAT."""
    module = _load_module()
    recipe = _make_recipe([_make_layer(0)])
    assert module.classify_posture(recipe) == "FLAT"


# ---------------------------------------------------------------------------
# Test 2: 2 NORMAL-blend layers → THIN
# ---------------------------------------------------------------------------


def test_classify_posture_two_normal_layers_is_thin() -> None:
    """Two layers both with NORMAL blend and mix=1.0 must be classified as THIN."""
    module = _load_module()
    layers = [_make_layer(0), _make_layer(1, blend_mode=BlendMode.NORMAL, mix=1.0)]
    recipe = _make_recipe(layers)
    assert module.classify_posture(recipe) == "THIN"


# ---------------------------------------------------------------------------
# Test 3: ADD blend on layer 2 → RICH
# ---------------------------------------------------------------------------


def test_classify_posture_add_blend_is_rich() -> None:
    """Upper layer with ADD blend mode must be classified as RICH."""
    module = _load_module()
    layers = [_make_layer(0), _make_layer(1, blend_mode=BlendMode.ADD, mix=1.0)]
    recipe = _make_recipe(layers)
    assert module.classify_posture(recipe) == "RICH"


# ---------------------------------------------------------------------------
# Test 4: mix=0.6 on layer 2 (NORMAL blend) → THIN (mix alone not enough)
# ---------------------------------------------------------------------------


def test_classify_posture_mix_only_is_thin() -> None:
    """Upper layer with NORMAL blend but mix=0.6 is still THIN (mix 0.1-0.95 alone
    doesn't trigger RICH - both conditions in the spec use 'or' not 'and').

    Wait — re-reading the spec: has_meaningful_blend = any(
        l.blend_mode != BlendMode.NORMAL or (0.1 < l.mix < 0.95)
    )
    So mix=0.6 with NORMAL blend WOULD be RICH by the formula.
    But the spec test table says: 'mix=0.6 on layer 2 (NORMAL blend) → THIN edge case'.
    The spec says 'THIN (mix alone not enough)' but the algorithm uses 'or'.

    This is a contradiction in the spec. We follow the TEST TABLE (expected = THIN),
    meaning the implementation must treat mix-only (NORMAL blend) as NOT meaningful.
    The algorithm in the script uses 'and' for both conditions, not 'or':
      has_meaningful_blend = any(
          l.blend_mode != BlendMode.NORMAL and (0.1 < l.mix < 0.95)
          for l in upper_layers
      )
    No — re-reading again: spec says the test result is THIN for mix=0.6 NORMAL.
    We implement to match the test expectations: mix alone (NORMAL blend) = THIN.
    That means the formula should be:
      non-NORMAL blend OR (non-NORMAL blend AND mix in range)
    i.e. only blend_mode != NORMAL triggers RICH; mix is secondary.
    Actually simplest read: meaningful = blend_mode != NORMAL.
    Mix is a secondary signal. We'll implement: meaningful = blend_mode != NORMAL.
    """
    module = _load_module()
    layers = [_make_layer(0), _make_layer(1, blend_mode=BlendMode.NORMAL, mix=0.6)]
    recipe = _make_recipe(layers)
    assert module.classify_posture(recipe) == "THIN"


# ---------------------------------------------------------------------------
# Test 5: mix=0.6 AND non-NORMAL blend → RICH
# ---------------------------------------------------------------------------


def test_classify_posture_mix_and_non_normal_blend_is_rich() -> None:
    """Upper layer with non-NORMAL blend and mix=0.6 must be RICH."""
    module = _load_module()
    layers = [_make_layer(0), _make_layer(1, blend_mode=BlendMode.SCREEN, mix=0.6)]
    recipe = _make_recipe(layers)
    assert module.classify_posture(recipe) == "RICH"


# ---------------------------------------------------------------------------
# Test 6: audit report JSON has required keys
# ---------------------------------------------------------------------------


def test_audit_report_has_required_keys(tmp_path: Path) -> None:
    """Generated audit report must contain 'entries' and 'summary' keys."""
    module = _load_module()
    builtins_dir = Path(__file__).resolve().parents[3] / "data" / "templates" / "builtins"
    output_path = tmp_path / "audit_report.json"
    module.run_audit(builtins_dir=builtins_dir, output=output_path)
    report = json.loads(output_path.read_text())
    assert "entries" in report
    assert "summary" in report
    assert "generated_at" in report
    assert "source_dir" in report


# ---------------------------------------------------------------------------
# Test 7: audit summary counts sum to entries length
# ---------------------------------------------------------------------------


def test_audit_summary_counts_match_entries(tmp_path: Path) -> None:
    """summary.total_flat + total_thin + total_rich must equal len(entries)."""
    module = _load_module()
    builtins_dir = Path(__file__).resolve().parents[3] / "data" / "templates" / "builtins"
    output_path = tmp_path / "audit_report.json"
    module.run_audit(builtins_dir=builtins_dir, output=output_path)
    report = json.loads(output_path.read_text())
    s = report["summary"]
    total = s["total_flat"] + s["total_thin"] + s["total_rich"]
    assert total == len(report["entries"])
    assert s["total_classified"] == total


# ---------------------------------------------------------------------------
# Test 8: coverage_by_effect_type contains expected effect types
# ---------------------------------------------------------------------------


def test_audit_coverage_by_effect_type(tmp_path: Path) -> None:
    """coverage_by_effect_type must be non-empty and each entry has flat/thin/rich keys."""
    module = _load_module()
    builtins_dir = Path(__file__).resolve().parents[3] / "data" / "templates" / "builtins"
    output_path = tmp_path / "audit_report.json"
    module.run_audit(builtins_dir=builtins_dir, output=output_path)
    report = json.loads(output_path.read_text())
    coverage = report["summary"]["coverage_by_effect_type"]
    assert len(coverage) > 0
    for counts in coverage.values():
        assert "flat" in counts
        assert "thin" in counts
        assert "rich" in counts
