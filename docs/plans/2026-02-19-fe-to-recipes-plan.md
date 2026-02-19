# FE-to-Recipes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bridge feature engineering outputs to the planner and renderer via context enrichment (Phase 1) and a new EffectRecipe composite model (Phase 2).

**Architecture:** A+B hybrid — Phase 1 adds new FE stages and activates the adapter payload in planner prompts. Phase 2 introduces EffectRecipe as a multi-layer composite spec modeled on xLights presets, with a promotion pipeline from mined templates through human curation to renderable recipes.

**Tech Stack:** Python 3.12+, Pydantic V2 (frozen models), Jinja2 (planner prompts), pytest, ruff, mypy

**Design Doc:** `docs/plans/2026-02-19-fe-to-recipes-design.md`

---

## Phase 1: Context Enrichment

### Task 1: Color Arc Engine — Output Models

**Files:**
- Create: `packages/twinklr/core/feature_engineering/models/color_arc.py`
- Modify: `packages/twinklr/core/feature_engineering/models/__init__.py` (add re-exports)
- Test: `tests/unit/feature_engineering/test_color_arc_models.py`

**Step 1: Write the failing test**

```python
"""Tests for Color Arc output models."""

from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    ColorTransitionRule,
    NamedPalette,
    SectionColorAssignment,
    SongColorArc,
)


def test_named_palette_creation() -> None:
    p = NamedPalette(
        palette_id="pal_icy_blue",
        name="Icy Blue",
        colors=("#A8D8EA", "#E0F7FA", "#FFFFFF"),
        mood_tags=("calm", "winter"),
        temperature="cool",
    )
    assert p.palette_id == "pal_icy_blue"
    assert len(p.colors) == 3
    assert p.temperature == "cool"


def test_section_color_assignment_creation() -> None:
    a = SectionColorAssignment(
        schema_version="v1.0.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label="chorus",
        section_index=1,
        palette_id="pal_icy_blue",
        spatial_mapping={"group_megatree": "primary", "group_arch": "accent"},
        shift_timing="section_boundary",
        contrast_target=0.7,
    )
    assert a.section_label == "chorus"
    assert a.spatial_mapping["group_megatree"] == "primary"


def test_arc_keyframe_bounds() -> None:
    k = ArcKeyframe(position_pct=0.5, temperature=0.3, saturation=0.8, contrast=0.6)
    assert 0.0 <= k.position_pct <= 1.0


def test_song_color_arc_assembly() -> None:
    palette = NamedPalette(
        palette_id="pal_1",
        name="Test",
        colors=("#FF0000",),
        mood_tags=(),
        temperature="warm",
    )
    assignment = SectionColorAssignment(
        schema_version="v1.0.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label="intro",
        section_index=0,
        palette_id="pal_1",
        spatial_mapping={},
        shift_timing="section_boundary",
        contrast_target=0.5,
    )
    rule = ColorTransitionRule(
        from_palette_id="pal_1",
        to_palette_id="pal_1",
        transition_style="crossfade",
        duration_bars=2,
    )
    arc = SongColorArc(
        schema_version="v1.0.0",
        palette_library=(palette,),
        section_assignments=(assignment,),
        arc_curve=(ArcKeyframe(position_pct=0.0, temperature=0.5, saturation=0.7, contrast=0.5),),
        transition_rules=(rule,),
    )
    assert len(arc.palette_library) == 1
    assert len(arc.section_assignments) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/feature_engineering/test_color_arc_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Create `packages/twinklr/core/feature_engineering/models/color_arc.py`:

```python
"""Color Arc Engine output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NamedPalette(BaseModel):
    """A concrete color palette with mood/temperature metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    palette_id: str = Field(description="Unique palette identifier.")
    name: str = Field(description="Human-readable palette name.")
    colors: tuple[str, ...] = Field(description="Hex color values.")
    mood_tags: tuple[str, ...] = Field(default=(), description="Mood descriptors.")
    temperature: Literal["warm", "cool", "neutral"] = Field(
        description="Overall color temperature."
    )


class SectionColorAssignment(BaseModel):
    """Color assignment for a single song section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    package_id: str
    sequence_file_id: str
    section_label: str
    section_index: int = Field(ge=0)
    palette_id: str = Field(description="Reference to NamedPalette.")
    spatial_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="target_group_id -> PaletteRole (primary, accent, warm, cool, neutral).",
    )
    shift_timing: Literal["beat_aligned", "section_boundary"] = Field(
        default="section_boundary",
        description="When palette transitions occur.",
    )
    contrast_target: float = Field(ge=0.0, le=1.0, description="Target contrast level.")


class ArcKeyframe(BaseModel):
    """A keyframe in the song-level color arc curve."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_pct: float = Field(ge=0.0, le=1.0, description="Position in song (0=start, 1=end).")
    temperature: float = Field(ge=0.0, le=1.0, description="Color temperature (0=cool, 1=warm).")
    saturation: float = Field(ge=0.0, le=1.0, description="Saturation level.")
    contrast: float = Field(ge=0.0, le=1.0, description="Contrast level.")


class ColorTransitionRule(BaseModel):
    """Rule for transitioning between palettes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    from_palette_id: str
    to_palette_id: str
    transition_style: Literal["crossfade", "cut", "ripple"] = Field(default="crossfade")
    duration_bars: int = Field(ge=1, description="Transition duration in bars.")


class SongColorArc(BaseModel):
    """Complete song-level color narrative."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="v1.0.0")
    palette_library: tuple[NamedPalette, ...] = Field(description="Available palettes.")
    section_assignments: tuple[SectionColorAssignment, ...] = Field(
        description="Per-section color assignments."
    )
    arc_curve: tuple[ArcKeyframe, ...] = Field(
        description="Song-level color arc keyframes."
    )
    transition_rules: tuple[ColorTransitionRule, ...] = Field(
        default=(), description="Palette transition rules."
    )
```

Add re-exports to `models/__init__.py`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/feature_engineering/test_color_arc_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/twinklr/core/feature_engineering/models/color_arc.py \
       packages/twinklr/core/feature_engineering/models/__init__.py \
       tests/unit/feature_engineering/test_color_arc_models.py
git commit -m "feat(fe): add Color Arc Engine output models"
```

---

### Task 2: Color Arc Engine — Extractor

**Files:**
- Create: `packages/twinklr/core/feature_engineering/color_arc.py`
- Test: `tests/unit/feature_engineering/test_color_arc.py`

**Step 1: Write the failing test**

```python
"""Tests for ColorArcExtractor."""

from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.models.color_arc import SongColorArc
# ... factory helpers for EffectPhrase, ColorNarrativeRow ...


def test_extract_produces_song_color_arc() -> None:
    phrases = _make_phrases_with_sections(["intro", "verse", "chorus"])
    color_rows = _make_color_narrative_rows(["intro", "verse", "chorus"])
    result = ColorArcExtractor().extract(phrases=phrases, color_narrative=color_rows)
    assert isinstance(result, SongColorArc)
    assert len(result.palette_library) >= 1
    assert len(result.section_assignments) == 3


def test_contrast_shift_generates_transition_rule() -> None:
    color_rows = _make_color_narrative_rows_with_shift(
        sections=["verse", "chorus"],
        contrast_shift=0.65,
    )
    result = ColorArcExtractor().extract(
        phrases=_make_phrases_with_sections(["verse", "chorus"]),
        color_narrative=color_rows,
    )
    assert len(result.transition_rules) >= 1
    assert result.transition_rules[0].from_palette_id != result.transition_rules[0].to_palette_id


def test_mono_section_gets_monochrome_palette() -> None:
    color_rows = _make_color_narrative_rows(["chorus"], dominant_color_class="mono")
    result = ColorArcExtractor().extract(
        phrases=_make_phrases_with_sections(["chorus"]),
        color_narrative=color_rows,
    )
    palette = next(p for p in result.palette_library if p.palette_id == result.section_assignments[0].palette_id)
    assert palette.temperature in ("warm", "cool", "neutral")
    assert len(palette.colors) <= 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/feature_engineering/test_color_arc.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Create `packages/twinklr/core/feature_engineering/color_arc.py`:

The extractor takes `EffectPhrase` tuples + `ColorNarrativeRow` tuples (from existing stage) and produces a `SongColorArc`. Key logic:
- Group color_narrative rows by section
- Map `dominant_color_class` (mono/palette/multi) to `NamedPalette` templates with holiday heuristics
- Compute `contrast_shift_from_prev` → `ColorTransitionRule` entries
- Build `arc_curve` keyframes from section energy progression
- Assign spatial mapping from target roles in phrases

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/feature_engineering/test_color_arc.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/twinklr/core/feature_engineering/color_arc.py \
       tests/unit/feature_engineering/test_color_arc.py
git commit -m "feat(fe): implement ColorArcExtractor"
```

---

### Task 3: Color Arc Engine — Pipeline Integration

**Files:**
- Modify: `packages/twinklr/core/feature_engineering/pipeline.py` (add enable flag + writer call)
- Test: `tests/unit/feature_engineering/test_pipeline_color_arc.py`

**Step 1: Write the failing test**

Test that the pipeline calls the color arc extractor when `enable_color_arc=True` and writes `color_arc.json` to the output directory.

**Step 2: Run test to verify it fails**

**Step 3: Implement**

- Add `enable_color_arc: bool = True` to `FeatureEngineeringPipelineOptions`
- Initialize `ColorArcExtractor` in `__init__()`
- Add `_write_color_arc()` method following existing `_write_color_narrative()` pattern
- Call from `_write_v1_tail_artifacts()`
- Add to feature store manifest

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(fe): integrate ColorArcExtractor into pipeline"
```

---

### Task 4: Propensity Miner — Output Models

**Files:**
- Create: `packages/twinklr/core/feature_engineering/models/propensity.py`
- Modify: `packages/twinklr/core/feature_engineering/models/__init__.py`
- Test: `tests/unit/feature_engineering/test_propensity_models.py`

Follow the same TDD pattern as Task 1. Models: `EffectModelAffinity`, `EffectModelAntiAffinity`, `PropensityIndex`.

**Step 1-5:** Test → Fail → Implement → Pass → Commit

```bash
git commit -m "feat(fe): add Propensity Miner output models"
```

---

### Task 5: Propensity Miner — Extractor

**Files:**
- Create: `packages/twinklr/core/feature_engineering/propensity.py`
- Test: `tests/unit/feature_engineering/test_propensity.py`

Extractor takes `EffectPhrase` tuples and cross-references target names with model type heuristics (target naming conventions: "MegaTree", "Arch", "Matrix", etc.) to build affinity scores.

**Step 1-5:** Test → Fail → Implement → Pass → Commit

```bash
git commit -m "feat(fe): implement PropensityMiner"
```

---

### Task 6: Propensity Miner — Pipeline Integration

**Files:**
- Modify: `packages/twinklr/core/feature_engineering/pipeline.py`
- Test: `tests/unit/feature_engineering/test_pipeline_propensity.py`

Same pattern as Task 3. Add `enable_propensity: bool = True`, writer method, manifest entry.

```bash
git commit -m "feat(fe): integrate PropensityMiner into pipeline"
```

---

### Task 7: Style Fingerprint — Output Models

**Files:**
- Create: `packages/twinklr/core/feature_engineering/models/style.py`
- Modify: `packages/twinklr/core/feature_engineering/models/__init__.py`
- Test: `tests/unit/feature_engineering/test_style_models.py`

Models: `TransitionStyleProfile`, `ColorStyleProfile`, `TimingStyleProfile`, `LayeringStyleProfile`, `StyleFingerprint`, `StyleBlend`, `StyleEvolution`.

**Step 1-5:** Test → Fail → Implement → Pass → Commit

```bash
git commit -m "feat(fe): add Style Fingerprint output models"
```

---

### Task 8: Style Fingerprint — Extractor

**Files:**
- Create: `packages/twinklr/core/feature_engineering/style.py`
- Test: `tests/unit/feature_engineering/test_style.py`

Extractor aggregates existing FE artifacts per creator/package:
- `layering_features.jsonl` → `LayeringStyleProfile`
- `color_narrative.jsonl` → `ColorStyleProfile`
- `transition_graph.json` → `TransitionStyleProfile`
- `motif_catalog.json` → motif_preferences
- `effect_phrases.jsonl` → recipe_preferences, `TimingStyleProfile`

**Step 1-5:** Test → Fail → Implement → Pass → Commit

```bash
git commit -m "feat(fe): implement StyleFingerprintExtractor"
```

---

### Task 9: Style Fingerprint — Pipeline Integration

**Files:**
- Modify: `packages/twinklr/core/feature_engineering/pipeline.py`
- Test: `tests/unit/feature_engineering/test_pipeline_style.py`

Same pattern. Add `enable_style_fingerprint: bool = True`, writer method, manifest entry.

```bash
git commit -m "feat(fe): integrate StyleFingerprintExtractor into pipeline"
```

---

### Task 10: Adapter Activation — Extend SectionPlanningContext

**Files:**
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/context.py`
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/orchestrator.py` (or wherever contexts are built)
- Test: `tests/unit/agents/sequencer/group_planner/test_context_enrichment.py`

**Step 1: Write the failing test**

```python
def test_section_planning_context_has_fe_fields() -> None:
    ctx = SectionPlanningContext(
        # ... existing required fields ...
        color_arc=mock_section_color_assignment,
        propensity_hints=mock_propensity_hints,
        style_constraints=mock_style_blend,
        template_recommendations=mock_recommendations,
        transition_hints=mock_transition_hints,
        motif_context=mock_motif_context,
        layering_budget=mock_layering_budget,
    )
    assert ctx.color_arc is not None
    assert ctx.propensity_hints is not None
```

**Step 2-5:** Test → Fail → Add fields (all optional with `None` default for backward compat) → Pass → Commit

```bash
git commit -m "feat(planner): extend SectionPlanningContext with FE fields"
```

---

### Task 11: Adapter Activation — Planner Prompt Injection

**Files:**
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/prompts/planner/developer.j2`
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/prompts/planner/user.j2`
- Test: `tests/unit/agents/sequencer/group_planner/test_prompt_rendering.py`

**Step 1: Write the failing test**

Test that when FE context fields are populated, the rendered prompt includes the FE data sections.

**Step 2-5:** Test → Fail → Add Jinja2 blocks for each FE field (conditional `{% if color_arc %}` blocks) → Pass → Commit

```bash
git commit -m "feat(planner): inject FE context into planner prompts"
```

---

### Task 12: Phase 1 Integration Test

**Files:**
- Create: `tests/integration/feature_engineering/test_fe_phase1_pipeline.py`

End-to-end test: run FE pipeline with all Phase 1 stages enabled on demo data, verify all new artifacts are produced and pass validation.

```bash
git commit -m "test(fe): add Phase 1 integration test"
```

---

## Phase 2a: Recipe Foundation

### Task 13: EffectRecipe Data Model

**Files:**
- Create: `packages/twinklr/core/sequencer/templates/group/recipe.py`
- Modify: `packages/twinklr/core/sequencer/vocabulary/__init__.py` (add new enums)
- Test: `tests/unit/sequencer/templates/group/test_recipe_model.py`

**Step 1: Write the failing test**

```python
"""Tests for EffectRecipe model."""

from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    ModelAffinity,
    PaletteSpec,
    ParamValue,
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
from twinklr.core.sequencer.templates.group.models import TimingHints


def test_single_layer_recipe() -> None:
    recipe = EffectRecipe(
        recipe_id="candy_cane_stack_v1",
        name="Candy Cane Stack",
        description="Red/white bars with sparkle overlay",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["candy_cane", "christmas", "classic"],
        timing=TimingHints(bars_min=4, bars_max=64),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0,
                layer_name="Base",
                layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash",
                blend_mode=BlendMode.NORMAL,
                mix=1.0,
                params={"Direction": ParamValue(value="Vertical"), "Speed": ParamValue(value=0)},
                motion=[MotionVerb.FADE],
                density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
    )
    assert recipe.recipe_id == "candy_cane_stack_v1"
    assert len(recipe.layers) == 1


def test_multi_layer_recipe_candy_cane() -> None:
    recipe = EffectRecipe(
        recipe_id="candy_cane_stack_v1",
        name="Candy Cane Stack",
        description="Multi-layer candy cane with sparkle",
        recipe_version="1.0.0",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=["candy_cane"],
        timing=TimingHints(bars_min=4, bars_max=64),
        palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
        layers=(
            RecipeLayer(
                layer_index=0, layer_name="Base", layer_depth=VisualDepth.BACKGROUND,
                effect_type="ColorWash", blend_mode=BlendMode.NORMAL, mix=1.0,
                params={}, motion=[MotionVerb.FADE], density=0.8,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=1, layer_name="Pattern", layer_depth=VisualDepth.MIDGROUND,
                effect_type="Bars", blend_mode=BlendMode.ADD, mix=0.7,
                params={"BarCount": ParamValue(value=8), "Direction": ParamValue(value="Diagonal")},
                motion=[MotionVerb.SWEEP], density=0.6,
                color_source=ColorSource.PALETTE_PRIMARY,
            ),
            RecipeLayer(
                layer_index=2, layer_name="Accents", layer_depth=VisualDepth.FOREGROUND,
                effect_type="Sparkle", blend_mode=BlendMode.SCREEN, mix=0.45,
                params={"Density": ParamValue(value=30), "Size": ParamValue(value=2)},
                motion=[MotionVerb.SPARKLE], density=0.3,
                color_source=ColorSource.WHITE_ONLY,
            ),
        ),
        provenance=RecipeProvenance(source="builtin"),
    )
    assert len(recipe.layers) == 3
    assert recipe.layers[1].blend_mode == BlendMode.ADD
    assert recipe.layers[2].color_source == ColorSource.WHITE_ONLY


def test_dynamic_param_value() -> None:
    p = ParamValue(expr="energy * 0.8", min_val=10, max_val=90)
    assert p.expr is not None
    assert p.value is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/sequencer/templates/group/test_recipe_model.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

Create `packages/twinklr/core/sequencer/templates/group/recipe.py` with all models from the design doc.

**Step 4-5:** Pass → Commit

```bash
git commit -m "feat(recipe): add EffectRecipe data model"
```

---

### Task 14: Builtin Template → EffectRecipe Auto-Converter

**Files:**
- Create: `packages/twinklr/core/sequencer/templates/group/converter.py`
- Test: `tests/unit/sequencer/templates/group/test_converter.py`

**Step 1: Write the failing test**

```python
def test_convert_single_layer_builtin_to_recipe() -> None:
    builtin = make_gtpl_base_wash_soft()  # existing builtin
    recipe = convert_builtin_to_recipe(builtin)
    assert isinstance(recipe, EffectRecipe)
    assert recipe.recipe_id == builtin.template_id
    assert recipe.template_type == builtin.template_type
    assert len(recipe.layers) == len(builtin.layer_recipe)
    assert recipe.provenance.source == "builtin"


def test_all_builtins_convert_without_error() -> None:
    from twinklr.core.sequencer.templates.group.library import REGISTRY
    for info in REGISTRY.list_templates():
        template = REGISTRY.get_template(info.template_id)
        recipe = convert_builtin_to_recipe(template)
        assert recipe.recipe_id == template.template_id
```

**Step 2-5:** Test → Fail → Implement converter that maps `LayerRecipe` → `RecipeLayer` → Pass → Commit

```bash
git commit -m "feat(recipe): builtin GroupPlanTemplate to EffectRecipe converter"
```

---

### Task 15: Recipe Synthesizer — FE MinedTemplate → EffectRecipe

**Files:**
- Create: `packages/twinklr/core/feature_engineering/recipe_synthesizer.py`
- Test: `tests/unit/feature_engineering/test_recipe_synthesizer.py`

Implements the mapping rules table from the design doc. Takes a `MinedTemplate` (from `content_templates.json` or `orchestration_templates.json`) and produces an `EffectRecipe`.

**Step 1: Write the failing test**

```python
def test_synthesize_single_strand_sweep() -> None:
    mined = MinedTemplate(
        template_id="uuid-1",
        template_kind="content",
        template_signature="single_strand|sweep|palette|mid|rhythmic|single_target|rhythm_driver",
        effect_family="single_strand",
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        # ...
    )
    recipe = RecipeSynthesizer().synthesize(mined, recipe_id="synth_single_strand_sweep_v1")
    assert recipe.template_type == GroupTemplateType.RHYTHM  # rhythm_driver → RHYTHM
    assert recipe.layers[0].effect_type == "SingleStrand"
    assert MotionVerb.SWEEP in recipe.layers[0].motion
    assert recipe.provenance.source == "mined"
    assert "uuid-1" in recipe.provenance.mined_template_ids
```

**Step 2-5:** Test → Fail → Implement mapping rules → Pass → Commit

```bash
git commit -m "feat(fe): implement RecipeSynthesizer (MinedTemplate to EffectRecipe)"
```

---

### Task 16: Promotion Pipeline

**Files:**
- Create: `packages/twinklr/core/feature_engineering/promotion.py`
- Test: `tests/unit/feature_engineering/test_promotion.py`

Orchestrates: quality gate → candidate builder → cluster dedup → recipe synthesis → catalog merge.

**Step 1: Write the failing test**

```python
def test_promotion_pipeline_filters_low_quality() -> None:
    candidates = [_low_support_template(), _high_support_template()]
    quality_report = _quality_report(passed=True)
    result = PromotionPipeline().run(
        candidates=candidates,
        quality_report=quality_report,
        min_support=10,
    )
    assert len(result.promoted_recipes) == 1  # only high support
    assert result.report.rejected_count == 1


def test_promotion_pipeline_merges_clusters() -> None:
    candidates = [_template_a(), _template_b_similar_to_a()]
    clusters = [_cluster_containing(["a", "b"])]
    review_decisions = {"cluster-1": "merge_into:a"}
    result = PromotionPipeline().run(
        candidates=candidates,
        clusters=clusters,
        review_decisions=review_decisions,
    )
    assert len(result.promoted_recipes) == 1
    assert len(result.promoted_recipes[0].provenance.mined_template_ids) == 2
```

**Step 2-5:** Test → Fail → Implement → Pass → Commit

```bash
git commit -m "feat(fe): implement Promotion Pipeline"
```

---

## Phase 2b: Planner/Renderer Integration

### Task 17: Recipe-Aware TemplateCatalog

**Files:**
- Modify: `packages/twinklr/core/sequencer/templates/group/library.py`
- Create: `packages/twinklr/core/sequencer/templates/group/recipe_catalog.py`
- Test: `tests/unit/sequencer/templates/group/test_recipe_catalog.py`

Create a `RecipeCatalog` that merges builtin recipes (auto-converted) with promoted FE recipes. Expose the same filtering interface (`templates_for_lane`, etc.) but backed by EffectRecipe.

```bash
git commit -m "feat(recipe): add RecipeCatalog merging builtins and promoted recipes"
```

---

### Task 18: Recipe-Aware Planner

**Files:**
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/context.py`
- Modify: `packages/twinklr/core/agents/sequencer/group_planner/prompts/planner/developer.j2`
- Test: `tests/unit/agents/sequencer/group_planner/test_recipe_planner.py`

Update `SectionPlanningContext.template_catalog` to accept `RecipeCatalog`. Update prompt to show recipe metadata (layer count, effect types, model affinities) alongside template IDs.

```bash
git commit -m "feat(planner): recipe-aware template selection"
```

---

### Task 19: Recipe-Aware Renderer

**Files:**
- Modify: `packages/twinklr/core/sequencer/` (renderer pipeline files)
- Test: `tests/unit/sequencer/test_recipe_renderer.py`

Extend the rendering pipeline to read `EffectRecipe.layers` and emit multi-layer xLights effects with blend modes and mix levels. This is the most significant renderer change.

**Sub-steps:**
1. Test single-layer recipe renders identically to current builtin rendering
2. Test multi-layer recipe produces correct xLights layer stack
3. Test dynamic param evaluation (energy expression → concrete value)
4. Test color_source resolution (PALETTE_PRIMARY → concrete hex from ColorArc)

```bash
git commit -m "feat(renderer): multi-layer EffectRecipe rendering"
```

---

## Phase 2c: Extensions

### Task 20: Style Transfer — Style-Weighted Retrieval

**Files:**
- Create: `packages/twinklr/core/feature_engineering/style_transfer.py`
- Test: `tests/unit/feature_engineering/test_style_transfer.py`

Implement `StyleWeightedRetrieval` that re-ranks the recipe catalog using a `StyleFingerprint` or `StyleBlend`.

```bash
git commit -m "feat(fe): implement style-weighted recipe retrieval"
```

---

### Task 21: Style Transfer — StyleBlend & Evolution

**Files:**
- Modify: `packages/twinklr/core/feature_engineering/style_transfer.py`
- Test: `tests/unit/feature_engineering/test_style_blend.py`

Add `StyleBlend` evaluation: base+accent style mixing, directional evolution (more_complex, simpler, warmer, etc.).

```bash
git commit -m "feat(fe): implement StyleBlend and StyleEvolution"
```

---

### Task 22: AI Asset Generation — Provider Interface

**Files:**
- Create: `packages/twinklr/core/assets/generator.py`
- Create: `packages/twinklr/core/assets/models.py`
- Test: `tests/unit/assets/test_asset_generator.py`

Define `AssetGenerator` protocol, `AssetRequest`, `AssetResult` models. Implement prompt builder that enriches `NarrativeAssetDirective` with palette + technical constraints.

```bash
git commit -m "feat(assets): add AI asset generation provider interface"
```

---

### Task 23: AI Asset Generation — OpenAI DALL-E Provider

**Files:**
- Create: `packages/twinklr/core/assets/providers/dalle.py`
- Test: `tests/unit/assets/test_dalle_provider.py`

Implement `DalleAssetGenerator` wrapping OpenAI Images API. Content-hash caching.

```bash
git commit -m "feat(assets): implement DALL-E asset generation provider"
```

---

### Task 24: Enhanced Motif Integration

**Files:**
- Modify: `packages/twinklr/core/sequencer/templates/group/recipe.py` (add `motif_compatibility`)
- Modify: `packages/twinklr/core/feature_engineering/promotion.py` (compute motif compatibility during promotion)
- Test: `tests/unit/feature_engineering/test_motif_integration.py`

Add `MotifCompatibility` to EffectRecipe. During promotion, score each recipe against motif catalog. During retrieval, boost recipes matching section's assigned motifs.

```bash
git commit -m "feat(fe): motif-aware recipe compatibility scoring"
```

---

### Task 25: Phase 2 Integration Test

**Files:**
- Create: `tests/integration/test_recipe_end_to_end.py`

End-to-end: FE pipeline → promotion → recipe catalog → planner selection → renderer output. Verify multi-layer xLights effects are produced correctly.

```bash
git commit -m "test: add Phase 2 recipe end-to-end integration test"
```

---

## Dependency Graph

```
Phase 1:
  Task 1 (Color Arc models)
  → Task 2 (Color Arc extractor) → Task 3 (pipeline integration)

  Task 4 (Propensity models)
  → Task 5 (Propensity extractor) → Task 6 (pipeline integration)

  Task 7 (Style models)
  → Task 8 (Style extractor) → Task 9 (pipeline integration)

  Tasks 3,6,9 → Task 10 (extend SectionPlanningContext)
  → Task 11 (prompt injection)
  → Task 12 (Phase 1 integration test)

Phase 2a:
  Task 13 (EffectRecipe model)
  → Task 14 (builtin converter)
  → Task 15 (recipe synthesizer)
  → Task 16 (promotion pipeline)

Phase 2b:
  Tasks 14,16 → Task 17 (recipe catalog)
  → Task 18 (recipe-aware planner)
  → Task 19 (recipe-aware renderer)

Phase 2c:
  Task 8 → Task 20 (style-weighted retrieval)
  → Task 21 (style blend/evolution)

  Task 22 (asset provider interface)
  → Task 23 (DALL-E provider)

  Task 16 → Task 24 (motif integration)

  Tasks 19,21,23,24 → Task 25 (Phase 2 integration test)
```

## Parallel Execution Opportunities

Within each phase, independent tracks can run in parallel:

**Phase 1 parallel tracks:**
- Track A: Tasks 1→2→3 (Color Arc)
- Track B: Tasks 4→5→6 (Propensity)
- Track C: Tasks 7→8→9 (Style)
- Sync point: Task 10 (all three must complete)

**Phase 2a parallel tracks:**
- Track A: Task 13→14 (Recipe model + converter)
- Track B: Task 13→15 (Recipe model + synthesizer, depends on 13 only)
- Sync point: Task 16 (needs 15)

**Phase 2c parallel tracks:**
- Track A: Tasks 20→21 (Style transfer)
- Track B: Tasks 22→23 (Asset generation)
- Track C: Task 24 (Motif integration)
- Sync point: Task 25 (all must complete)
