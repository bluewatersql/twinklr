---
type: context
area: overview
updated: 2026-08-13
---

# Twinklr — Current State

_Verified 2026-08-13 from repository evidence (docs, source tree, git history)._

Twinklr is an AI-powered choreography engine: audio file in, native xLights `.xsq`
sequence out. LLMs plan creative intent (what should happen); deterministic code renders
precision (curves, DMX values, timing). See [product/overview.md](product/overview.md).

## Implemented

- **Audio analysis pipeline** (deterministic) — tempo/beats (BeatGrid), energy, section
  structure, harmonic content, lyrics with multi-source fallback (embedded tags, LRCLib,
  Genius, WhisperX), phonemes/visemes. `packages/twinklr/core/audio/`
- **Audio profiling & lyrics agents** (LLM) — musical interpretation and creative
  guidance. `packages/twinklr/core/agents/audio/`
- **Multi-agent choreography planning** (LLM) — iterative planner → heuristic validator →
  LLM validator → judge loop. See
  [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md).
- **Rendering & compilation** (deterministic) — template compiler, curve generation,
  DMX export for moving heads; display sequencer for RGB/pixel elements.
  `packages/twinklr/core/sequencer/`, `packages/twinklr/core/curves/`
- **Feature engineering pipeline + SQLite feature store** — incremental, store-driven
  analysis of xLights sequence corpora into style profiles and recipes.
  `packages/twinklr/core/feature_engineering/`, `feature_store/`;
  deep reference: [Pipeline Guide](../docs/pipeline_guide.md).
- **xLights export** — native `.xsq` read/write. `packages/twinklr/core/formats/xlights/`
- **CLI** — `twinklr run` executes the moving-heads pipeline end-to-end.
  `packages/twinklr/cli/`

## Known issues

- Four pre-existing test failures on `main`, unrelated to recent work — see
  [memories/learnings/known-test-failures.md](../memories/learnings/known-test-failures.md).
- A superseded group-planner v3 attempt is referenced in
  `packages/twinklr/core/pipeline/stages.py` (comment pointing at
  `changes/archive/group_planner_v3_failed/`); that archive predates change tracking and
  is not present in the repository.

## Active work

None currently — see [changes/ACTIVE.md](../changes/ACTIVE.md). Recent commits are
documentation/branding polish.

## Key constraints

- Python **3.12 only** (3.13+ unsupported) —
  [memories/constraints/python-3.12-only.md](../memories/constraints/python-3.12-only.md)
- Pipeline failure policy is **fail-fast** with cache-based restartability — see
  [architecture/pipeline.md](architecture/pipeline.md).
- Quality gates: `make validate` must pass —
  [engineering/conventions.md](engineering/conventions.md)
