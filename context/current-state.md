---
type: context
area: overview
updated: 2026-08-14
---

# Twinklr — Current State

_Verified 2026-08-13 from repository evidence (docs, source tree, git history)._

Twinklr is an AI-powered choreography engine: audio file in, xLights artifacts out — a
fresh `.xsq`, standalone `.xtiming` timing tracks, and an `.xmap` mapping hint, which the
user imports into their own show. LLMs plan creative intent (what should happen); deterministic code renders
precision (curves, DMX values, timing). See [product/overview.md](product/overview.md).

## Implemented

- **Audio analysis pipeline** (deterministic) — tempo/beats (BeatGrid), energy, section
  structure, harmonic content, lyrics with multi-source fallback (embedded tags, LRCLib,
  Genius, WhisperX), phonemes/visemes. P2P-T8 put rhythm/structure production behind
  selectable, source-versioned adapters and a five-fixture offline A/B harness; the
  current DSP remains the accepted default because the optional model arms did not
  produce complete local gate evidence. `packages/twinklr/core/audio/`
- **Audio profiling & lyrics agents** (LLM) — musical interpretation and creative
  guidance. `packages/twinklr/core/agents/audio/`
- **Multi-agent choreography planning** (LLM) — iterative planner → heuristic
  validation (with deterministic auto-repair on the display path) → judge loop; the
  formerly-documented separate LLM-validator role was removed from code. See
  [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md).
- **Rendering & compilation** (deterministic) — template compiler, curve generation,
  DMX export for moving heads; display sequencer for RGB/pixel elements.
  `packages/twinklr/core/sequencer/`, `packages/twinklr/core/curves/`
- **Feature engineering pipeline + SQLite feature store** — incremental, store-driven
  analysis of xLights sequence corpora into style profiles and recipes.
  `packages/twinklr/core/feature_engineering/`, `feature_store/`;
  deep reference: [Pipeline Guide](../docs/pipeline_guide.md).
- **xLights delivery** — writes a self-contained `.xsq`, one `.xtiming` per timing track
  (these import standalone, with no model mapping), and an `.xmap`. Since P1P-T11 no
  export path reads a user sequence; the `.xsq` parser is analysis-only (`profiling/`).
  `packages/twinklr/core/formats/xlights/`
- **CLI** — `twinklr run --audio ... --config ...` executes the moving-heads pipeline
  end-to-end. It takes no input sequence, and the fixture config supplies the rig the
  planner is told about. `packages/twinklr/cli/`

## Known issues

- **`main` does not pass its own quality gates from a clean checkout** (verified
  2026-08-13 at `aa8d325`): 120 test failures (classified — 60 tests for nonexistent
  scripts, 52 needing gitignored template data, 8 environmental), 4 mypy errors,
  150 ruff errors, 13 unformatted files. See
  [memories/learnings/known-test-failures.md](../memories/learnings/known-test-failures.md)
  (the earlier four-failure claim is refuted).
- The 2026-08 reactivation review found verified correctness defects on the shipped
  render path and a wide dead-configuration class; readiness classification
  **REQUIRES_STABILIZATION** with a dependency-ordered roadmap — see
  [memories/learnings/reactivation-review-2026-08.md](../memories/learnings/reactivation-review-2026-08.md)
  and the review under
  [changes/twinklr-reactivation-review/](../changes/twinklr-reactivation-review/).
- A superseded group-planner v3 attempt is referenced in
  `packages/twinklr/core/pipeline/stages.py` (comment pointing at
  `changes/archive/group_planner_v3_failed/`); that archive predates change tracking and
  is not present in the repository. (`stages.py` itself is confirmed dead code.)

## Active work

None currently — see [changes/ACTIVE.md](../changes/ACTIVE.md). The
twinklr-reactivation-review change completed 2026-08-13; remediation has not started
(review-only — no production code was changed).

## Key constraints

- Python **3.12 only** (3.13+ unsupported) —
  [memories/constraints/python-3.12-only.md](../memories/constraints/python-3.12-only.md)
- Pipeline failure policy is **fail-fast** with cache-based restartability — see
  [architecture/pipeline.md](architecture/pipeline.md).
- Quality gates: `make validate` must pass —
  [engineering/conventions.md](engineering/conventions.md)
