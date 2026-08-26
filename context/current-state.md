---
type: context
area: overview
updated: 2026-08-26
---

# Twinklr — Current State

_Repository evidence and active sequencing verified 2026-08-26. All eight Phase 3
offline implementations and five of seven Phase 4 tasks are integrated; Phase 3 and the
earlier empirical exits remain open._

Twinklr is an AI-powered choreography engine: audio file in, xLights artifacts out — a
fresh `.xsq`, standalone `.xtiming` timing tracks, and an `.xmap` mapping hint, which the
user imports into their own show. LLMs plan typed creative intent; deterministic code
resolves exact timing, curves, fixture channels, DMX values, and file-format details.
See [product/overview.md](product/overview.md).

## Implemented

- **Audio analysis pipeline** — deterministic rhythm, energy, structure, harmonic,
  lyrics, phoneme, and viseme analysis. Rhythm/structure production is behind explicit,
  source-versioned adapters with a five-fixture offline A/B harness. The runtime default
  remains custom DSP; the owner accepted P2P-T8's fixed-gate retention recommendation
  on 2026-08-16 because the optional model arms did not produce complete admissible
  evidence. Opt-in Demucs stems can add drum, bass, and
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
  registry. The display sequencer renders RGB/pixel effects; its coordination expansion
  now preserves local BeatGrid timing, sub-beat offsets, exact round-robin slots, and
  gap-free overlap resolution. P3-T2 also applies lane blend intent
  uniformly in the emitted sub-layer space, validates recipe effect types against the
  exact runtime registry before event construction, and makes every retained effect
  substitution visible in warnings, trace entries, and counts.
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
  reserved Twinklr layers. Display and moving-head output now share one renderer-neutral
  emission core for positional registries, effect timing, layer translation, and trace
  provenance. Live xLights acceptance remains an explicit local-only gate.
  `packages/twinklr/core/formats/xlights/`, `packages/twinklr/core/api/xlights/`
- **CLI** — `twinklr run` and `twinklr display` retain branch-only iteration, while
  `twinklr show` runs one common planning prefix and emits coordinated MH + display
  effects into one sequence after strict layout/fixture ownership reconciliation. Live
  iteration, catalog coverage, and recipe-builder command surfaces expose the other
  guarded workflows. `packages/twinklr/cli/`

## Quality-gate state

The latest accepted integrated baseline is main `05f24d0`: `make validate` formatted
**1,352 files**, completed with **5,593 passed, 39 skipped** at **89% coverage**, clean
Ruff lint, and mypy success across **719 source files** after P4-T4 and P4-T5 integration.
The skips cover explicit optional/local-only boundaries rather than accepted
implementation regressions. Exact task contracts and durable verification evidence are
owned by the [P4-T1](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md),
[P4-T2](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T2-local-provider-option.md),
[P4-T3](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T3-dead-tail-retirement-wave-1.md),
[P4-T4](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T4-duplication-collapse.md),
and [P4-T5](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T5-dead-config-final-sweep.md)
specs.

The review baseline at `aa8d325` did fail its own gates. That is historical evidence,
not the current state; its fully classified record is preserved in
[known-test-failures.md](../memories/learnings/known-test-failures.md).

## Active work and open boundaries

The [twinklr-reactivation-review build campaign](../changes/ACTIVE.md) remains active.
Phases 0 and 1K are complete. Phase 1P's implementation tasks, Phase 2P's 13 offline
implementations, and Phase 2K's four tooling implementations are merged and independently
verified, but their owner/live exit criteria are not complete. On 2026-08-16 the owner
accepted the P2P-T1/T8/T9 recommendations and authorized P3-T1, P3-T2, and P3-T3 before
the outstanding empirical exits. P3-T1 is merged and independently verified at
`5eebcb2`; P3-T2 is merged and independently verified at `5365f70`; P3-T3 is merged at
`33cce57` after independent verification and owner acceptance of the canonical
`twinklr display` command and offline file-only layout input. The owner accepted P3-T4's
exact contract/invariants and AC2 amendment and authorized only its capped macro probe.
The audited harness made one live request on 2026-08-16; OpenAI rejected the schema
because `ThemeRef.scope` combined `$ref` with sibling `description`. No retry/fallback
occurred, usage was unavailable, and the conservative `$1.66` commitment leaves only
`$0.09`, insufficient for another audited attempt. The general schema remediation is
integrated and offline-verified at `558153c`, but live acceptance remains open and no
further P3-T4 live attempt was then authorized. On 2026-08-26 the owner approved exactly
one second audited request: authorization
`p3-t4-second-attempt-owner-approved-2026-08-26`, exact `$1.660000` additional
preauthorization, `$3.32` cumulative hard cap, and two-attempt lifetime cap. After
independent audit, attempt 2 made exactly one request and received HTTP 400 because
`temperature` is unsupported by `gpt-5.6-sol`; no retry, fallback, logical request,
schema repair, or usage metadata occurred. The ledger therefore commits both
`$1.660000` reservations (`$3.320000` total). The lifetime cap is exhausted, no third
attempt is authorized, and live acceptance remains open. Offline remediation now makes
temperature optional and uses one explicit OpenAI capability normalization for actual
provider parameters, runner dispatch, serialized request evidence, and probe identity:
`gpt-5.6-sol` omits temperature while retaining reasoning effort, while known
temperature-supporting models retain it. This remediation made no provider call and
does not reopen the attempt cap. The owner accepted all nine P3-T5 decisions,
and P3-T5 was integrated at `f006468`. On 2026-08-26 the owner accepted P3-T6's offline
unified-emission contract. Formal first review rejected the initial snapshot; standards,
specification, and adversarial review then approved the remediation offline/in code, and
it was integrated at `c9620db`. P3-T8's independently approved offline implementation
was integrated at `82438cf`. P3-T7's final corrected freeze
`2caf726b505fb6fc3e17f56165b4884ce0f33a1525f9768d6a880621e16e9192` is independently
approved offline/in code and included in the current integration, bringing Phase 3 to
eight of eight offline task implementations integrated. P3-T6
empirical xLights GUI acceptance remains open. The owner authorized P3-T7+ and
task-bounded live/paid work on 2026-08-26. P3-T7's audited empirical proof passed with
one `gpt-image-2` request, no retry, a valid 1024×1024 PNG, and a scoped cache replay
that made zero additional provider calls. Complete usage priced to `$0.00622`; the
sealed owner-local ledger is terminal and forbids another attempt. xLights GUI dates/checks remain deferred until
a meaningful end-to-end show is fully working; the empirical gates remain open. These
integrations and authorizations do not waive the earlier exits or close P3-T4 live
acceptance. P3-T8's first offline candidate was formally rejected; its remediated
implementation now independently verifies file-backed provenance, rebuilds deterministic
reports, shares provider request limits, and handles contact-sheet grounding. It is
independently approved offline, but supplies no xLights evidence, visual-judge output,
human judgment, calibration, real completed record, or empirical acceptance outcome.
Phase 4 has five of seven tasks integrated. P4-T1 landed at `56d9aa0` after independent
approval and clean-main verification; it coordinates the Python 3.13/ML-chain
modernization and removes the orphaned diarization and unused dependency surfaces. P4-T2
is integrated through implementation `3765bd9` and redirect-hardening remediation
`40e8e55`; its offline provider path is verified, but real Ollama schema validity remains
unclaimed pending the explicit local-only opt-in smoke. P4-T3's independently verified
dead-tail retirement is integrated at `bf6bba5`, with migration/unwiring sequencing and
live-caller retentions preserved. P4-T4's independently verified duplication collapse is
integrated at `3e7f679`; it consolidates provider transport retry ownership, closes HTTP
and cache lifecycles, wires logging and surviving HTTP configuration, and preserves the
separate generic pipeline replay controls. P4-T5's independently verified configuration
accountability sweep is integrated at `05f24d0`; its generated registry accounts for
every external App, Job, FixtureGroup, and TemplateDoc path with an exact effect test,
invariant test, or removal disposition. Under the owner override, optional
WhisperX/TorchCodec runtime execution remains deferred and unavailable against the
current default FFmpeg 9.
Exact contracts and verification evidence live in the [P4-T1](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md),
[P4-T2](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T2-local-provider-option.md),
[P4-T3](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T3-dead-tail-retirement-wave-1.md),
[P4-T4](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T4-duplication-collapse.md),
and [P4-T5](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T5-dead-config-final-sweep.md)
task specs.

The authoritative current task/gate list is the campaign
[HANDOFF.md](../changes/twinklr-reactivation-review/build/plan/HANDOFF.md). Most notably,
there is no Phase 1P human/xLights exit evidence, owner-accepted vision calibration,
real three-arm comparison, D1 verdict, or real-data Phase 2K exit evidence yet. Do not
infer those outcomes from offline fixtures or
implementation tests.

## Key constraints

- Python **3.13 only** (3.14+ unsupported) —
  [python-3.12-only.md](../memories/constraints/python-3.12-only.md)
- Pipeline failure policy is **fail-fast** with cache-based restartability — see
  [architecture/pipeline.md](architecture/pipeline.md).
- Quality gates: `make validate` must pass —
  [engineering/conventions.md](engineering/conventions.md)
- Paid/live provider calls, owner-local audio/layout/corpus data, xLights mutation, and
  human taste judgments require the explicit owner protocols in the active change.
