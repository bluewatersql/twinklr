# Twinklr Reactivation Review — Plan

_Phase-aware plan. Updated 2026-08-13. Mode: **continuous** (user elected continuation
at the passed discovery gate, 2026-08-13), local-safe (live paid LLM calls still
require per-run confirmation; user has indicated the env will carry a current API
token). Baseline `aa8d325`._

**USER_MANDATED remediation input (2026-08-13):** retarget hardcoded model IDs to
current OpenAI models and refresh env/token configuration. This is an accepted
direction for the remediation roadmap (Stage 8), not an instruction to modify code
during the review.

## Stage status

| Stage | Description | Status |
|---|---|---|
| 0 | Bootstrap & governance (spec, plan, ACTIVE.md, capability inventory) | COMPLETE |
| 1 | Repository reconstruction (7 parallel read-only workers → discovery.md + manifest.md) | COMPLETE |
| Gate | Discovery gate: independent critic challenge (opus), handoff, STOP | **PASSED (post-correction)** — run stopped here per discovery-only mode |
| 2 | Product thesis & system-approach review | COMPLETE (reviews/product-and-approach.md) |
| 3 | Phase-level source review (7 phases) | COMPLETE — all seven phase docs VERIFIED |
| 4 | Runtime & baseline validation | COMPLETE (local half; open empirical items need xLights install / API key — see verification.md) |
| 5 | Cross-cutting synthesis | **HELD — user pause before next stage** |
| 6 | Modernization assessment | COMPLETE (reviews/modernization.md; judgment half folds into Stage 8) |
| 7 | Adversarial verification | COMPLETE — pipelined per-phase; all verdicts in verification.md; authors applied all revisions |
| 8 | Remediation design & readiness | HELD (follows Stage 5) |

## Stage 1 worker decomposition (ultrawork parallel wave, all sonnet, read-only)

| Worker | Scope | Task |
|---|---|---|
| worker-1 | pyproject/uv workspace, Makefile, scripts/, utils/, CI/release, .gitignore boundaries | #2 |
| worker-2 | CLI entry points, core/pipeline orchestration, config, caching, logging, API clients | #3 |
| worker-3 | core/audio deterministic analysis (BeatGrid, energy, structure, harmonic, lyrics, phonemes) | #4 |
| worker-4 | core/agents LLM planning, runtime prompt packs, schemas, provider adapters | #5 |
| worker-5 | core/sequencer, curves, templates, moving heads, display, formats/xlights | #6 |
| worker-6 | core/feature_engineering, feature_store (SQLite), recipes, embeddings, reporting | #7 |
| worker-7 | tests/fixtures/validation scripts, docs toolchain, history signals (TODOs, dead paths) | #8 |

Synthesis (task #9, orchestrator/fable) → critic challenge (task #10, opus) → handoff
and stop (task #11).

## Discovery gate record (2026-08-13)

Independent critic challenge (opus, non-author) returned **PASS-WITH-CORRECTIONS on
all five sections** (A coverage, B internal consistency, C phase boundaries, D scope,
E unknowns). Every load-bearing claim spot-checked against source held; two were
understated. Six blocking corrections were required and have been applied:

1. Test-coverage positive signal corrected — `core/formats/xlights/` effectively
   untested; `core/sequencer/rendering/` second zero-coverage package (discovery §5,
   manifest).
2. `.xsq` template-content loss promoted from hypothesis to **confirmed production
   defect**; §4 reclassified (discovery §4–5).
3. Reviewer + verifier ownership per phase written down (table below).
4. Phase 4 split — seven-phase decomposition adopted (discovery §9).
5. Missing unknowns added: model-ID resolution, licensing/IP, image-gen spend,
   secondary credentials (discovery §6–7).
6. H5 cut (verdict-anchoring); H2 restated as open question Q2 ("is the LLM
   load-bearing?"); Stage 2 charter seeded with user/cost/competition questions
   (discovery §8).

Non-blocking refinements (status hygiene, counts, nuance on token-budget and
session-id defect shapes, `current-state.md` stale-claim attribution, cross-phase seam
owners) also applied. **Gate: PASSED (post-correction) — Stage 1 closed.**

## Stage 3 phase decomposition (revised at gate; reviewer ≠ verifier, enforced)

| # | Phase slug | Scope summary | Author (Stage 3) | Verifier (Stage 7) |
|---|---|---|---|---|
| 1 | foundation-and-orchestration | pipeline framework/definitions, config, caching, session, api clients, io/logging/parsers/utils, packaging, setup shims | general-purpose (opus) "phase1-author" | critic-type (opus), distinct instance "phase1-verifier" |
| 2 | deterministic-audio-analysis | core/audio all | general-purpose (sonnet) "phase2-author" | code-reviewer (opus) "phase2-verifier" |
| 3 | llm-agents-and-planning | agents runner/prompts/providers/judging/planners, **agents/assets**, agents/{analytics,context,logging}, sequencer/planning | general-purpose (opus) "phase3-author" | critic-type (opus) "phase3-verifier" |
| 4 | moving-heads-rendering | sequencer/moving_heads, curves, resolvers, sequencer/rendering, timing, vocabulary | general-purpose (opus) "phase4-author" | code-reviewer (opus) "phase4-verifier" |
| 5 | display-rendering-and-xlights-io | sequencer/display, templates/group, theming, sequencer/models, formats/xlights | general-purpose (opus) "phase5-author" | critic-type (opus) "phase5-verifier" |
| 6 | corpus-intelligence | feature_engineering, feature_store, recipe_builder, profiling, reporting | general-purpose (sonnet) "phase6-author" | code-reviewer (opus) "phase6-verifier" |
| 7 | interfaces-and-engineering | CLI, Makefile/CI, scripts/utils, tests architecture, docs, knowledge trees, licensing | general-purpose (sonnet) "phase7-author" | critic-type (opus) "phase7-verifier" |

Rules: an author never verifies its own phase; security-reviewer (opus) joins
verification for phases 1, 3, 5 (network/LLM/XML trust boundaries). Cross-phase seams
(token race, vocabulary contract, agents/assets) have owners per discovery §9. No
Haiku anywhere.

## Notes

- Known-test-failures memory (memories/learnings/known-test-failures.md) is reported,
  not trusted — re-verify at Stage 4.
- `changes/archive/group_planner_v3_failed/` is referenced from
  `packages/twinklr/core/pipeline/stages.py` but absent from the repository (predates
  change tracking) — flagged as a history signal for Stage 1.
- No Haiku-tier agents at any stage (user directive).
