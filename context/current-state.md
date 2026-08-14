---
type: context
area: overview
updated: 2026-08-14
---

# Twinklr — Current State

_Verified 2026-08-14 from the integrated build-campaign snapshot `6b2b34a` and a fresh
full quality-gate run._

Twinklr is an AI-powered choreography engine: audio file in, xLights artifacts out — a
fresh `.xsq`, standalone `.xtiming` timing tracks, and an `.xmap` mapping hint, which the
user imports into their own show. LLMs plan typed creative intent; deterministic code
resolves exact timing, curves, fixture channels, DMX values, and file-format details.
See [product/overview.md](product/overview.md).

## Implemented

- **Audio analysis pipeline** — deterministic rhythm, energy, structure, harmonic,
  lyrics, phoneme, and viseme analysis. Rhythm/structure production is behind explicit,
  source-versioned adapters with a five-fixture offline A/B harness. The runtime default
  remains custom DSP; P2P-T8's fixed offline gate recommends retaining it because the
  optional model arms did not produce complete admissible evidence, but owner review of
  that adoption recommendation is pending. Opt-in Demucs stems can add drum, bass, and
  vocal-derived features with content/model-aware caching and explicit full-mix fallback.
  `packages/twinklr/core/audio/`
- **Audio profiling and lyrics agents** — musical interpretation, lyric MomentCues,
  and typed creative context for planning. `packages/twinklr/core/agents/audio/`
- **Multi-agent choreography planning** — macro planning plus iterative moving-head
  planning, deterministic heuristic repair, and a judge whose prior verdicts feed the
  next revision. Schema-v2 sections carry categorical intensity, color, shutter, gobo,
  and lyric MomentCue intent. Registered OpenAI roles use validated strict structured
  outputs, bounded failure handling, explicit model/reasoning configuration, and prompt-
  and schema-aware cache identities. See
  [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md).
- **Deterministic selector and experiment harness** — a metadata/energy/variety-aware
  non-LLM selector plus a hash-, cache-, cost-, calibration-, and blind-review-bound
  three-arm comparison harness. The harness is implemented; the owner experiment and D1
  verdict have not run.
  `packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py`,
  `packages/twinklr/core/reporting/evaluation/`
- **Rendering and compilation** — moving-head templates resolve schema-v2 intensity,
  color, shutter, gobo, and moment-cue intent into exact fixture behavior. Python
  factories and validated JSON `TemplateDoc` files coexist in one collision-safe
  registry. The display sequencer renders RGB/pixel effects.
  `packages/twinklr/core/sequencer/`, `packages/twinklr/core/curves/`
- **Evaluation tooling** — checkpoint/evaluation writing, deterministic beat/effect sync
  metrics, ffmpeg frame/contact-sheet preparation, a strict four-category vision judge,
  calibration contracts, and single-run/comparison schemas. Live vision calibration and
  the real three-arm result remain owner-gated. `packages/twinklr/core/reporting/`
- **Feature engineering, catalog, and curation tooling** — content-hash-stable corpus
  identities, SQLite feature storage, tracked catalogs, layout-aware coverage reporting,
  quality-distribution/threshold-review evidence, coverage-targeted recipe generation,
  explicit human admission logs, per-style fingerprints, and propensity loading into
  planner context. The tools are implemented; Phase 2K's real layout/corpus/curation/
  style exit evidence is not. `packages/twinklr/core/feature_engineering/`,
  `packages/twinklr/core/feature_store/`, `packages/twinklr/core/recipe_builder/`
- **xLights delivery and iteration clients** — self-contained `.xsq`, standalone
  `.xtiming`, and `.xmap` output; a pinned automation client for preview rendering; and
  guarded `inject`/`regenerate` workflows that plan against the open layout and own only
  reserved Twinklr layers. Live xLights acceptance remains an explicit local-only gate.
  `packages/twinklr/core/formats/xlights/`, `packages/twinklr/core/api/xlights/`
- **CLI** — `twinklr run` executes the moving-head pipeline end to end; live iteration,
  catalog coverage, and recipe-builder command surfaces expose the corresponding guarded
  workflows. `packages/twinklr/cli/`

## Quality-gate state

At integrated snapshot `6b2b34a`, fresh `make validate` evidence is **5,239 passed,
39 skipped**, clean Ruff formatting and lint, and mypy success across **718 source
files**. The skips cover explicit optional/local-only boundaries rather than accepted
implementation regressions. This document owns the canonical current repository and
quality-gate snapshot; the campaign handoff links here instead of duplicating it.

The review baseline at `aa8d325` did fail its own gates. That is historical evidence,
not the current state; its fully classified record is preserved in
[known-test-failures.md](../memories/learnings/known-test-failures.md).

## Active work and open boundaries

The [twinklr-reactivation-review build campaign](../changes/ACTIVE.md) remains active.
Phases 0 and 1K are complete. Phase 1P's implementation tasks, Phase 2P's 13 offline
implementations, and Phase 2K's four tooling implementations are merged and independently
verified, but their owner/live exit criteria are not complete. Phases 3 and 4 have not
started; Phase 3 waits for prior phase exits unless the owner explicitly reassesses
sequencing.

The authoritative current task/gate list is the campaign
[HANDOFF.md](../changes/twinklr-reactivation-review/build/plan/HANDOFF.md). Most notably,
there is no Phase 1P human/xLights exit evidence, owner-approved P2P-T8 adoption decision,
owner-accepted vision calibration, real three-arm comparison, D1 verdict, or real-data
Phase 2K exit evidence yet. Do not infer those outcomes from offline fixtures or
implementation tests.

## Key constraints

- Python **3.12 only** (3.13+ unsupported) —
  [python-3.12-only.md](../memories/constraints/python-3.12-only.md)
- Pipeline failure policy is **fail-fast** with cache-based restartability — see
  [architecture/pipeline.md](architecture/pipeline.md).
- Quality gates: `make validate` must pass —
  [engineering/conventions.md](engineering/conventions.md)
- Paid/live provider calls, owner-local audio/layout/corpus data, xLights mutation, and
  human taste judgments require the explicit owner protocols in the active change.
