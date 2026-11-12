---
type: context
status: active
area: overview
updated: 2026-11-12
---

# Twinklr — Current State

A snapshot, not a history. Dated narrative, commit-by-commit records, and exact task
contracts live in the active change
([campaign handoff](../changes/twinklr-reactivation-review/build/plan/HANDOFF.md)).

Twinklr is an AI-powered choreography engine: audio file in, xLights artifacts out — a
fresh `.xsq`, standalone `.xtiming` timing tracks, and an `.xmap` mapping hint, which the
user imports into their own show. LLMs plan typed creative intent; deterministic code
resolves exact timing, curves, fixture channels, DMX values, and file-format details.
See [product/overview.md](product/overview.md).

## Implemented

- **Audio analysis** — deterministic rhythm, energy, structure, harmonic, lyrics,
  phoneme, and viseme analysis. Rhythm and structure sit behind source-versioned adapters;
  custom DSP is the default
  ([decision](../memories/decisions/keep-dsp-after-mir-ab.md)). Opt-in Demucs stems add
  drum, bass, and vocal features with explicit full-mix fallback.
  `packages/twinklr/core/audio/`
- **Audio profiling and lyrics agents** — musical interpretation, lyric MomentCues, and
  typed creative context for planning. `packages/twinklr/core/agents/audio/`
- **Multi-agent planning** — macro planning plus iterative moving-head and display
  planning, deterministic heuristic repair, and a judge whose verdicts feed the next
  revision. Schema-v2 sections carry categorical intensity, color, shutter, gobo, and
  lyric MomentCue intent.
  [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md)
- **Providers** — OpenAI (default; Responses API strict structured outputs), Claude
  (`llm_provider: anthropic`), and Ollama cloud (`glm-5.3:cloud` through the loopback
  daemon; by owner policy no local model is used). All three have completed a live moving-head run; see
  [Live evidence](#live-evidence).
- **Rendering and compilation** — moving-head templates resolve schema-v2 intent into
  exact fixture behavior; Python factories and validated JSON `TemplateDoc` files share
  one collision-safe registry. The display sequencer renders RGB/pixel effects with
  BeatGrid-exact coordination, and lane blend intent overrides recipe blend metadata
  ([decision](../memories/decisions/lane-blend-mode-overrides-recipe.md)).
  `packages/twinklr/core/sequencer/`, `packages/twinklr/core/curves/`
- **xLights delivery and iteration** — self-contained `.xsq`, `.xtiming`, and `.xmap`
  output; a pinned automation client for preview rendering; guarded `inject` and
  `regenerate` workflows that own only reserved Twinklr layers. Display and moving-head
  output share one emission core
  ([decision](../memories/decisions/unified-xlights-emission-contract.md)).
  `packages/twinklr/core/formats/xlights/`, `packages/twinklr/core/api/xlights/`
- **CLI** — `twinklr run` (moving heads) and `twinklr display` are branch-only;
  `twinklr show` runs one planning prefix and emits coordinated MH + display effects into
  one sequence ([decision](../memories/decisions/coordinated-show-contract.md)).
  `packages/twinklr/cli/`
- **Evaluation tooling** — checkpoint and `eval-report` writing, deterministic beat/effect
  sync metrics, frame and contact-sheet preparation, a four-category vision judge,
  calibration contracts, and a deterministic selector with a three-arm comparison harness.
  The tools exist; their owner experiments have not run.
  `packages/twinklr/core/reporting/`
- **Feature engineering, catalog, and curation** — content-hash-stable corpus identities,
  SQLite feature store, tracked catalogs, coverage reporting, targeted recipe generation,
  human admission logs, per-style fingerprints, and propensity loading into planner
  context. The tools exist; their real-data exits have not run.
  `packages/twinklr/core/feature_engineering/`, `packages/twinklr/core/feature_store/`,
  `packages/twinklr/core/recipe_builder/`

## Quality gate

This page owns the rolling gate snapshot. Latest recorded full gate: `6f2a9f6`
(2026-11-12), `make validate` green with 5,718 passed, 39 skipped
([record](../changes/2026_11_12_knowledge_optimization/handoff.md)); the skips are
optional or local-only boundaries. Last recorded coverage: 89% at `03b75e9` (2026-08-30).
There are no accepted failures. The gate includes an offline regression harness (`tests/regression/`):
moving-head replay-render parity and a hermetic display replay.

## Live evidence

| Date | Run | Result | Record |
|---|---|---|---|
| 2026-08-29 | OpenAI, `Need A Favor`, owner 4-head rig | Valid `.xsq`; meets or exceeds the pre-refactor baseline (396 effects vs 262) | [run notes](../changes/post-refactor-validation/notes/live-run-prereqs.md), [QA runbook](../docs/qa-runbook.md) |
| 2026-11-12 | Claude `claude-opus-5-5`, every role | 6/6 stages, about $0.95; on par with the baseline (251 effects vs 262; indicative, different song); human judgment PENDING-OWNER | [evaluation](../evaluations/2026-11-12-claude-baseline-live-run/README.md) |
| 2026-11-12 | Ollama cloud `glm-5.3:cloud`, every role | 6/6 stages, 0 schema repairs; on par with the baseline (256 effects vs 262; indicative, different song) | [evidence](../changes/twinklr-reactivation-review/evidence/2026-11-12-p4-t2-ollama-cloud-pipeline/README.md) |

Provider behavior learned from these runs is in
[live-provider-run-lessons.md](../memories/learnings/live-provider-run-lessons.md). The
points that shape current behavior:

- Claude refuses to compile the five planner schemas (`compiled grammar is too large`).
  The adapter resends those requests once with the schema in the prompt only and validates
  client-side, so planner output on Claude has no server-side schema guarantee. The owner
  kept this fallback and deferred a schema redesign.
- Ollama Cloud does not enforce `response_format`; the schema travels in the prompt.
- On OpenAI, strict mode passes for 7 of 8 roles; `audio_profile` shows runaway output.

## Active work

One change is active: the
[twinklr-reactivation-review build campaign](../changes/ACTIVE.md). Its code and tooling
are merged and independently verified. What remains is empirical evidence and owner
decisions, not implementation.

| Phase | Implementation | Exit still needs |
|---|---|---|
| 0 Foundation, 1K Knowledge edges | Complete | — |
| 1P Render truth | 12/12 merged | Human judgment on the golden fixture; xLights import acceptance |
| 2P Creative quality | 13/13 merged | Vision-judge calibration (T6); three-arm experiment and D1 verdict (T13); preview and injection checks against a real xLights (T5, T12); owner decision on the T10 live-smoke gap; T11 strict mode for `audio_profile` |
| 2K Catalog growth | 4/4 merged | Real layout coverage, owner-corpus mining with eight threshold decisions (T2), curation sessions, style fingerprints |
| 3 Show convergence | 8/8 merged | xLights GUI acceptance (T6); combined-show preview, live judge, human review, calibration, and a real completed record (T8) |
| 4 Compounding | 6/7 merged | Owner call on whether the Ollama cloud run closes T2; T7 is optional and NO-GO until 2K-T2 evidence and a private MH corpus manifest are accepted |

Commands for every remaining exit:
[owner runbooks](../changes/twinklr-reactivation-review/runbooks/README.md). Do not infer
any of these outcomes from offline fixtures, merged tooling, or implementation tests.

## Known gaps

- No CI end-to-end test replays recorded provider responses through the live planning
  path; regression coverage stops at render-replay parity.
- End-to-end authoring-time savings have not been measured.
- Moving-head templates and display recipes share a catalog home but not a schema.

## Permanent boundaries

- **P3-T4 live macro probe** — the two-attempt ledger is sealed and exhausted; no third
  attempt. Live acceptance was closed by owner decision on 2026-11-12
  ([decision](../memories/decisions/p3-t4-live-acceptance-superseded.md)).
- **P3-T7 image proof** — passed once; its sealed ledger forbids another run.
- **WhisperX/TorchCodec** — optional runtime execution is owner-deferred and unavailable
  against the current default FFmpeg 9. Do not claim runtime readiness.
- **Owner-gated actions** — paid or live provider calls, owner-local audio, layout, and
  corpus data, xLights mutation, and human judgment follow
  [AGENTS.md → Owner-gated actions](../AGENTS.md#owner-gated-actions) and the protocols in
  the active change.

## Key constraints

- Python **3.13 only** —
  [constraint](../memories/constraints/python-3.12-only.md)
- Pipeline failure policy is **fail-fast** with cache-based restartability —
  [architecture/pipeline.md](architecture/pipeline.md)
- `make validate` must pass before any completion claim —
  [engineering/conventions.md](engineering/conventions.md)
