# FE-to-Recipes: Implementation Overview

**Branch:** `feat/fe-to-recipes`
**Date:** 2026-02-20
**Commits:** 24 (22 features + 1 revert + 1 integration test)
**Files changed:** 45 (+6,339 lines)

---

## Summary

This branch bridges feature engineering (FE) outputs to the group planner and renderer via two phases:

- **Phase 1 (Context Enrichment):** Three new FE extractors (Color Arc, Propensity Miner, Style Fingerprint) produce structured analysis artifacts. These are injected into the planner's `SectionPlanningContext` and rendered into Jinja2 prompt templates, giving the LLM planner richer context for template selection.

- **Phase 2 (EffectRecipe Model):** A new `EffectRecipe` composite model replaces flat template references with multi-layer, parameterized recipe specifications. A promotion pipeline converts high-quality mined templates into curated recipes. A recipe-aware renderer evaluates dynamic parameters and resolves color sources at render time.

---

## Phase 1: Context Enrichment

### Color Arc Engine (Tasks 1-3)

Extracts a song-level color narrative arc from existing `ColorNarrativeRow` and `EffectPhrase` data.

**New models:** `SongColorArc`, `NamedPalette`, `SectionColorAssignment`, `ArcKeyframe`, `ColorTransitionRule`

**Key files:**
- `feature_engineering/models/color_arc.py` -- Output models
- `feature_engineering/color_arc.py` -- `ColorArcExtractor`
- `feature_engineering/pipeline.py` -- Pipeline integration (`enable_color_arc` flag)

**What it produces:** Per-section palette assignments, song-level temperature/saturation arc keyframes, palette transition rules triggered by contrast shifts between sections.

### Propensity Miner (Tasks 4-6)

Builds model-type affinity scores by cross-referencing effect phrases with target naming conventions.

**New models:** `EffectModelAffinity`, `PropensityIndex`

**Key files:**
- `feature_engineering/models/propensity.py` -- Output models
- `feature_engineering/propensity.py` -- `PropensityMiner`
- `feature_engineering/pipeline.py` -- Pipeline integration (`enable_propensity` flag)

**What it produces:** Per-model-type affinity scores (e.g., MegaTree=0.85, Arch=0.62) based on which targets are most frequently used with which effect patterns.

### Style Fingerprint (Tasks 7-9)

Aggregates FE artifacts into a creator/package style profile across four dimensions.

**New models:** `TransitionStyleProfile`, `ColorStyleProfile`, `TimingStyleProfile`, `LayeringStyleProfile`, `StyleFingerprint`, `StyleBlend`, `StyleEvolution`

**Key files:**
- `feature_engineering/models/style.py` -- Output models
- `feature_engineering/style.py` -- `StyleFingerprintExtractor`
- `feature_engineering/pipeline.py` -- Pipeline integration (`enable_style_fingerprint` flag)

**What it produces:** A multi-dimensional style fingerprint capturing transition preferences, color tendencies, timing patterns, and layering habits. Used downstream for style-weighted recipe retrieval.

### Adapter Activation (Tasks 10-11)

Connects Phase 1 outputs to the group planner's prompt templates.

**Key files:**
- `agents/sequencer/group_planner/context.py` -- 7 new optional FE fields on `SectionPlanningContext`
- `agents/sequencer/group_planner/context_shaping.py` -- Context shaping for FE data
- `agents/sequencer/group_planner/prompts/planner/developer.j2` -- Conditional FE sections
- `agents/sequencer/group_planner/prompts/planner/user.j2` -- FE context rendering

**Backward compatible:** All new fields default to `None`. Existing callers are unaffected.

---

## Phase 2a: Recipe Foundation

### EffectRecipe Data Model (Task 13)

A multi-layer, parameterized recipe specification modeled on xLights preset structure.

**Key types:** `EffectRecipe`, `RecipeLayer`, `ParamValue`, `PaletteSpec`, `StyleMarkers`, `RecipeProvenance`, `ModelAffinity`, `ColorSource`, `MotifCompatibility`

**Key file:** `sequencer/templates/group/recipe.py`

**Design highlights:**
- Layers have `blend_mode`, `mix`, `density`, and `visual_depth`
- `ParamValue` supports static values OR dynamic expressions (e.g., `energy * 0.8`)
- `ColorSource` enum maps to palette roles resolved at render time
- `RecipeProvenance` tracks whether a recipe is `builtin` or `mined`

### Builtin Converter (Task 14)

Auto-converts existing `GroupPlanTemplate` builtins into `EffectRecipe` format.

**Key file:** `sequencer/templates/group/converter.py` -- `convert_builtin_to_recipe()`

### Recipe Synthesizer (Task 15)

Converts FE `MinedTemplate` instances into `EffectRecipe` specs using deterministic mapping tables.

**Key file:** `feature_engineering/recipe_synthesizer.py` -- `RecipeSynthesizer`

**Mapping tables:** `effect_family` -> xLights effect type, `motion_class` -> `MotionVerb`, `energy_class` -> `GroupTemplateType`, `color_class` -> `ColorMode`

### Promotion Pipeline (Task 16)

Orchestrates quality gates, cluster dedup, and recipe synthesis to promote high-quality mined templates.

**Key file:** `feature_engineering/promotion.py` -- `PromotionPipeline`

**Pipeline stages:**
1. Quality gate: filter by `min_support` and `min_stability`
2. Cluster dedup: merge similar templates (keeps designated representative)
3. Recipe synthesis: convert surviving templates to `EffectRecipe`

---

## Phase 2b: Planner/Renderer Integration

### RecipeCatalog (Task 17)

Unified catalog merging auto-converted builtins with FE-promoted recipes.

**Key file:** `sequencer/templates/group/recipe_catalog.py` -- `RecipeCatalog`

**Interface:** `has_recipe()`, `get_recipe()`, `list_by_lane()`, `merge(builtins, promoted)`

### Recipe-Aware Planner (Task 18)

Injects recipe metadata (layer count, effect types, model affinities) into planner prompt templates.

**Key files:**
- `agents/sequencer/group_planner/context.py` -- `recipe_catalog` field, `recipes_for_lane()` method
- `agents/sequencer/group_planner/context_shaping.py` -- `_shape_recipe_catalog()` helper
- `agents/sequencer/group_planner/prompts/planner/developer.j2` -- Recipe catalog table

### Recipe-Aware Renderer (Task 19)

Multi-layer renderer that evaluates dynamic parameters and resolves color sources.

**Key file:** `sequencer/display/recipe_renderer.py`

**Key types:** `RecipeRenderer`, `RenderedLayer`, `RecipeRenderResult`, `RenderEnvironment`

**Capabilities:**
- Dynamic parameter evaluation via restricted `eval()` with `energy` and `density` variables
- Clamping to `min_val`/`max_val` bounds
- Color source resolution (`PALETTE_PRIMARY` -> hex from environment)
- Per-layer blend mode and mix level preservation

---

## Phase 2c: Extensions

### Style-Weighted Retrieval (Task 20)

Re-ranks recipe catalog using `StyleFingerprint` across 4 dimensions.

**Key file:** `feature_engineering/style_transfer.py` -- `StyleWeightedRetrieval`

**Scoring dimensions:** effect family preference, layering match, density match, complexity match

### StyleBlend & Evolution (Task 21)

Linear interpolation between base+accent styles with directional evolution.

**Key file:** `feature_engineering/style_transfer.py` -- `StyleBlendEvaluator`

**Evolution directions:** `more_complex`, `simpler`, `warmer`, `cooler`, `higher_energy`, `calmer`

### Motif Integration (Task 24)

Adds `MotifCompatibility` scoring to `EffectRecipe` for motif-boosted retrieval.

**Key file:** `sequencer/templates/group/recipe.py` -- `MotifCompatibility` model

### Skipped: AI Asset Generation (Tasks 22-23)

Tasks 22-23 were **reverted** -- they duplicated the existing asset generation system at `core/agents/assets/` which already uses OpenAI's gpt-image-1.5 API with full retry logic, prompt enrichment, catalog management, and content-hash caching.

---

## Test Coverage

| Category | Test Files | Test Count |
|----------|-----------|------------|
| Phase 1 Unit Tests | 10 files | ~80 tests |
| Phase 2 Unit Tests | 9 files | ~65 tests |
| Phase 1 Integration | 1 file | 8 tests |
| Phase 2 Integration | 1 file | 6 tests |
| **Total new tests** | **21 files** | **~159 tests** |

All existing tests continue to pass (2864 passing, 18 pre-existing failures in macro_planner unrelated to this branch).

---

## Architecture Diagram

```
Audio File
    |
    v
FE Pipeline (existing)
    |
    +-- ColorNarrativeExtractor (existing)
    +-- ColorArcExtractor (NEW) -----> SongColorArc
    +-- PropensityMiner (NEW) -------> PropensityIndex
    +-- StyleFingerprintExtractor (NEW) -> StyleFingerprint
    +-- TemplateMiner (existing) ----> MinedTemplate
    |
    v
PromotionPipeline (NEW)
    |  quality gate -> cluster dedup -> recipe synthesis
    v
RecipeCatalog (NEW)
    |  merge(builtins + promoted)
    |
    +-- StyleWeightedRetrieval (NEW) -- re-rank by style
    +-- MotifCompatibility (NEW) ----- boost by motif match
    |
    v
Group Planner (existing, enriched)
    |  SectionPlanningContext + FE fields + recipe catalog
    |  Jinja2 prompts with FE context sections
    v
RecipeRenderer (NEW)
    |  dynamic param eval, color source resolution
    v
Multi-layer xLights effects
```
