# FE-to-Recipes: Testing Plan

**Branch:** `feat/fe-to-recipes`
**Date:** 2026-02-20

---

## Overview

This testing plan covers verification of all Phase 1 (Context Enrichment) and Phase 2 (EffectRecipe) changes. Tests are organized into three tiers: automated unit tests, automated integration tests, and manual user acceptance tests.

---

## Tier 1: Automated Unit Tests

Run all unit tests:
```bash
uv run pytest tests/unit/ -v
```

### Phase 1: Context Enrichment

| Component | Test File | Tests | What's Verified |
|-----------|----------|-------|-----------------|
| Color Arc Models | `tests/unit/feature_engineering/test_color_arc_models.py` | 4 | Model creation, field validation, frozen immutability |
| Color Arc Extractor | `tests/unit/feature_engineering/test_color_arc.py` | 5 | Extraction from phrases/color rows, transition rules, monochrome handling |
| Color Arc Pipeline | `tests/unit/feature_engineering/test_pipeline_color_arc.py` | 3 | Pipeline integration, artifact writing, manifest entry |
| Propensity Models | `tests/unit/feature_engineering/test_propensity_models.py` | 4 | Model creation, field bounds, frozen immutability |
| Propensity Miner | `tests/unit/feature_engineering/test_propensity.py` | 5 | Affinity scoring, target pattern matching, multi-model handling |
| Propensity Pipeline | `tests/unit/feature_engineering/test_pipeline_propensity.py` | 3 | Pipeline integration, artifact writing, manifest entry |
| Style Models | `tests/unit/feature_engineering/test_style_models.py` | 6 | All sub-profiles, fingerprint assembly, blend/evolution models |
| Style Extractor | `tests/unit/feature_engineering/test_style.py` | 6 | Extraction from FE artifacts, dimension scoring, aggregation |
| Style Pipeline | `tests/unit/feature_engineering/test_pipeline_style.py` | 4 | Pipeline integration, artifact writing, manifest entry |
| Context Enrichment | `tests/unit/agents/sequencer/group_planner/test_context_enrichment.py` | 5 | New FE fields on SectionPlanningContext, defaults, backward compat |
| Prompt Rendering | `tests/unit/agents/sequencer/group_planner/test_prompt_rendering.py` | 7 | Jinja2 FE sections render, conditional blocks, empty-state handling |

### Phase 2a: Recipe Foundation

| Component | Test File | Tests | What's Verified |
|-----------|----------|-------|-----------------|
| EffectRecipe Model | `tests/unit/sequencer/templates/group/test_recipe_model.py` | 6 | Single/multi-layer creation, ParamValue static+dynamic, enums |
| Builtin Converter | `tests/unit/sequencer/templates/group/test_converter.py` | 5 | Single-layer conversion, all builtins convert, provenance |
| Recipe Synthesizer | `tests/unit/feature_engineering/test_recipe_synthesizer.py` | 5 | Effect family mapping, motion/energy/color mapping, provenance |
| Promotion Pipeline | `tests/unit/feature_engineering/test_promotion.py` | 5 | Quality gate filtering, cluster dedup, merged provenance |
| RecipeCatalog | `tests/unit/sequencer/templates/group/test_recipe_catalog.py` | 5 | Merge, lane filtering, lookup, override precedence |

### Phase 2b: Planner/Renderer Integration

| Component | Test File | Tests | What's Verified |
|-----------|----------|-------|-----------------|
| Recipe Planner | `tests/unit/agents/sequencer/group_planner/test_recipe_planner.py` | 7 | recipe_catalog field, recipes_for_lane(), context shaping |
| Recipe Renderer | `tests/unit/sequencer/test_recipe_renderer.py` | 9 | Single/multi-layer render, dynamic eval, clamping, color source |

### Phase 2c: Extensions

| Component | Test File | Tests | What's Verified |
|-----------|----------|-------|-----------------|
| Style-Weighted Retrieval | `tests/unit/feature_engineering/test_style_transfer.py` | 9 | Ranking, top_k, 4-dimension scoring, empty catalog |
| StyleBlend & Evolution | `tests/unit/feature_engineering/test_style_blend.py` | 10 | Blend ratios, no accent, evolution directions, clamping |
| Motif Integration | `tests/unit/feature_engineering/test_motif_integration.py` | 6 | MotifCompatibility model, recipe integration, frozen check |

---

## Tier 2: Automated Integration Tests

Run integration tests:
```bash
uv run pytest tests/integration/test_recipe_end_to_end.py tests/integration/feature_engineering/test_fe_phase1_pipeline.py -v
```

### Phase 1 Integration

| Test | File | What's Verified |
|------|------|-----------------|
| FE Pipeline E2E | `tests/integration/feature_engineering/test_fe_phase1_pipeline.py` | Full pipeline run with all Phase 1 stages, artifact production, manifest completeness |

### Phase 2 Integration

| Test | File | What's Verified |
|------|------|-----------------|
| MinedTemplate to Rendered Output | `tests/integration/test_recipe_end_to_end.py` | Full chain: promotion -> catalog -> renderer with quality gates |
| Multi-Layer Rendering | same | 3-layer recipe with dynamic params, color resolution, blend modes |
| Cluster Dedup Provenance | same | Merged provenance from cluster dedup |
| Catalog Lane Filtering | same | BASE/RHYTHM/ACCENT lane assignment |
| Motif Compatibility | same | MotifCompatibility preserved through catalog operations |
| Style-Weighted Retrieval | same | StyleFingerprint-based ranking with effect family preference |

---

## Tier 3: Manual User Acceptance Tests

Use the demo scripts in `scripts/` to verify the pipeline interactively.

### Test 1: Phase 1 FE Pipeline

```bash
uv run python scripts/demo_recipe_pipeline.py --phase 1
```

**Verify:**
- [ ] Color Arc artifacts produced (palette library, section assignments, arc keyframes)
- [ ] Propensity Index artifacts produced (model affinity scores)
- [ ] Style Fingerprint artifacts produced (4-dimension profile)
- [ ] All artifacts serializable to JSON
- [ ] No errors or warnings in output

### Test 2: Recipe Promotion Pipeline

```bash
uv run python scripts/demo_recipe_pipeline.py --phase 2a
```

**Verify:**
- [ ] Mined templates pass quality gates (support >= 5, stability >= 0.3)
- [ ] Low-quality templates rejected with report
- [ ] Synthesized recipes have correct effect types and motion verbs
- [ ] Provenance tracks source template IDs
- [ ] Recipe catalog merges builtins + promoted without duplicates

### Test 3: Recipe Rendering

```bash
uv run python scripts/demo_recipe_pipeline.py --phase 2b
```

**Verify:**
- [ ] Single-layer recipe renders to one RenderedLayer
- [ ] Multi-layer recipe renders all layers in order
- [ ] Dynamic params evaluate correctly (energy * 0.8 with energy=0.75 -> 0.6)
- [ ] Color sources resolve (PALETTE_PRIMARY -> hex from environment)
- [ ] Blend modes and mix values preserved

### Test 4: Style Transfer

```bash
uv run python scripts/demo_recipe_pipeline.py --phase 2c
```

**Verify:**
- [ ] Style-weighted retrieval ranks matching recipes higher
- [ ] StyleBlend interpolates between base and accent correctly
- [ ] Evolution directions shift fingerprint in expected direction
- [ ] Top-k retrieval limits results correctly

### Test 5: Full Pipeline End-to-End

```bash
uv run python scripts/demo_recipe_pipeline.py --phase all
```

**Verify:**
- [ ] Complete pipeline runs without errors
- [ ] All phase outputs are consistent
- [ ] Recipe catalog contains both builtin and promoted recipes
- [ ] Rendered output has resolved parameters and colors

---

## Regression Checks

```bash
# Full unit test suite (should show 0 new failures)
uv run pytest tests/unit/ -v --tb=short

# Existing integration tests still pass
uv run pytest tests/integration/test_categorical_params_e2e.py -v
uv run pytest tests/integration/test_transitions_multi_layer.py -v

# Type checking
uv run mypy packages/twinklr/core/feature_engineering/ packages/twinklr/core/sequencer/templates/group/recipe.py packages/twinklr/core/sequencer/display/recipe_renderer.py

# Linting
uv run ruff check packages/twinklr/core/feature_engineering/ packages/twinklr/core/sequencer/
```

---

## Known Pre-Existing Failures

18 failures + 24 errors in `tests/unit/agents/sequencer/macro_planner/` are pre-existing on `main` and unrelated to this branch.

---

## Sign-Off Checklist

- [ ] All Tier 1 unit tests pass
- [ ] All Tier 2 integration tests pass
- [ ] Tier 3 manual tests completed
- [ ] Regression checks show no new failures
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Code reviewed
