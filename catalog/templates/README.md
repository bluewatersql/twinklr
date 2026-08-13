# catalog/templates/

Git-tracked home for the recipe catalog (`EffectRecipe` / group templates)
consumed by `TemplateStore.from_directory()`. This directory is the single
data home for `data/templates`-class content — see
`build/specs/phase-1k-knowledge-edges/P1K-T3-catalog-in-git.md` and
`build/specs/phase-0-foundation/P0-T2-structural-test-repair.md`'s
Orchestrator reconciliation notes (2026-08-13). Tests consume this catalog;
they never fork their own copy of it (except the tiny pathological-case set
under `tests/fixtures/templates-extra/`, which is deliberately *not* real
catalog content).

## Provenance and licensing gate

Recipes tracked here are original or cleared-for-redistribution
*compositions* — blend modes, motion verbs, timing hints, parameter
structures — not vendor sequence files, audio, or media assets. This
directory never contains a copy of anyone else's `.xsq`/`.zip`/audio/image
content.

If you mine your own local corpus (`data/vendor_packages/`, gitignored,
never tracked), do **not** promote or commit a recipe you have not
personally confirmed you have the right to redistribute in this form. See
`RecipeProvenance.source` (`builtin`/`mined`/`curated`/`generated`) for how
each entry originated, and treat `mined`/`curated` entries as requiring that
confirmation before promotion. This gate is tracked project-wide as a named,
prospective risk (P6-F5); it is not blocking for work that doesn't touch
mining or promotion.

## Current contents (P0-T2 seed subset)

As of P0-T2 (structural test repair), this directory holds a **minimal
seed set of 5 hand-authored `builtin` recipes** — not the full ~37-recipe
production catalog — chosen to be the smallest set that lets
`test_engine.py`/`test_sequenced.py`/`test_renderer_overlay.py` assert real
composition-engine behavior (effect-type keyword resolution, multi-lane
layout, blend-mode assignment, SEQUENCED/RIPPLE/CALL_RESPONSE expansion,
asset-overlay wiring) on every checkout, with no corpus-generation step:

| recipe_id | lane | purpose |
|---|---|---|
| `gtpl_base_wash_split` | BASE | ambient wash keyword resolution, timing/palette/overlay tests |
| `gtpl_rhythm_chase_single` | RHYTHM | "chase" keyword resolution, SEQUENCED/RIPPLE/CALL_RESPONSE expansion |
| `gtpl_rhythm_alternate_ab` | RHYTHM | explicit `effect_map.py` override (SingleStrand) |
| `gtpl_accent_hit_color` | ACCENT | "hit" keyword resolution, multi-lane blend mode |
| `gtpl_accent_hit_white` | ACCENT | zero-duration/section-boundary diagnostics |

**P1K-T4 coordination point**: this seed subset is the starting point for
Phase 1K's full catalog build-out (moving the ~37 production builtins here
verbatim, plus a curated first mining pass — see P1K-T3's spec). Whoever
picks up P1K-T3/P1K-T4 should extend this directory in place rather than
create a second tracked template directory.

## What still points elsewhere

A handful of tests and production call sites still hardcode the legacy
`data/templates` path (gitignored, absent on a clean checkout) rather than
this directory — `pipeline/display_stages.py`,
`agents/taxonomy_utils.py::_get_supported_motif_ids_cached`, and
`recipe_builder/evidence.py::DEFAULT_TEMPLATES_DIR`. Repointing those is
P1K-T3's job (production code), not this task's (test-only scope); the
corresponding tests are marked `requires_template_data` and skip cleanly
until that repoint lands.

## `.enrichment/`

`catalog/templates/.enrichment/` is the FE-computed sidecar cache
(regenerable, never needed at runtime) and stays untracked even though this
parent directory is tracked — see `.gitignore`.
