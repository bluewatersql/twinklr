---
type: context
status: active
area: overview
updated: 2026-11-17
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
  revision. Moving-head sections carry 1-3 template parts and categorical song intent
  (intensity, colour, gobo, timed events tied to lyric MomentCues, motif variation,
  density, entry/exit transitions; contract of 2026-11-17, sent to Claude as an enforced
  structured output, compiled and enforced live on 2026-11-17); the moving-head renderer renders each
  section's colour and gobo and not yet the rest of the intent, a known regression
  (below).
  [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md)
- **Providers** — OpenAI (default; Responses API strict structured outputs), Claude
  (`llm_provider: anthropic`), and Ollama cloud (`glm-5.3:cloud` through the loopback
  daemon; by owner policy no local model is used). All three have completed a live moving-head run; see
  [Live evidence](#live-evidence).
- **Moving-head rendering** — one renderer
  ([decision](../memories/decisions/mh-single-renderer.md)). It compiles JSON
  `TemplateDoc` templates against each fixture's `physical_profile` into complete 20 ms
  frames, written as constant DMX effects over model-relative channels 1–48, and plans
  dark repositioning between cues. What it requires and refuses:
  - Job schema `3.1` only. `moving_heads.mode`, `transitions` and schema `"3.0"`, and
    every fixture or template key Twinklr no longer reads, are refused by name when the
    file loads; there are no aliases. The exception: fixture fields retired before
    2026-08 (`dmx_universe`, `dmx_start_address`, `channel_count`, `capabilities`,
    `movement_speed`, a channel `config`) are dropped with a warning
    (`config/fixtures/removed_fields.py:28-40`).
  - Every fixture needs a `physical_profile` and a settled `moving_heads.initial_states`
    entry, and its own xLights model; otherwise the job is refused when its fixtures
    load, before analysis. Profiles default what is safe; timings and initial states are
    never defaulted.
  - The `render_preflight` gate, right after audio analysis and before any planner,
    dry-compiles every offered template and preset on the rig over the song. A family
    is offered through its first passing variant; a run with nothing left is refused.
  - Seven families in `catalog/templates/moving_heads/` load on every run (six plus the
    `zoom_wave` pilot, which needs a zoom axis); `--template-dir` adds JSON templates.
    Families play in any meter (a repeating cycle grows to whole periods).
  - Silent song edges are held dark; a cue it cannot play honestly is kept dark
    (`on_unplayable`, default `"dark"`).
  - **Song intent rendered so far: section colour and gobo** (W3/W4, 2026-11-17, not
    yet seen by the owner). Profiles tag what each wheel and shutter state shows (`hex`,
    `pattern`, `strobe`; W1; `offer: false` for a state with no such meaning), and
    `twinklr run` and `show` write paste-ready tags for untagged states to
    `profile_tags.txt`, noting it in one line. The gate computes the **rig offer** from
    the tagged states (colours, each section's palette roles on the wheel, gobos,
    strobe speeds, hit, wheel change time), the planner is shown it, and a colour or
    gobo no head can show is repaired. Each head plays the section's colour (a palette
    role through the section's macro palette, under `run` and `show` alike; the fixed
    role table without one; a role the palette lacks plays PRIMARY) and gobo as its
    nearest tagged state, turned only in the dark; a change at a boundary the heads play
    lit through dips dark for at most half a beat before the section, else turns in the
    section's first dark window, else keeps the previous colour (recorded, and repaired
    for the planner). The offer also publishes each template's dark phases and the
    states its overlay masks cannot reach. Renderer revision 4. ([user guide](../docs/user-guide.md#how-a-sections-colour-and-gobo-reach-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w3-w4-offer-colour/README.md))
  - **Intensity on the dimmer** (W5, 2026-11-17, not yet seen by the owner). `as_authored`,
    SLOW, SMOOTH and FAST play the template as authored; DRAMATIC (every half bar in
    4/4, every bar in 3/4) and INTENSE (every beat) add a beat-locked pulse: over a level
    below full a raised floor and an accent, over a full level (every catalog family) a
    dip-and-return, full on the accent and easing to 75% / 60% between; dark frames and
    every other channel untouched; a slow dimmer gets a smaller pulse, a dimmer latency
    an earlier one, a head without a dimmer none. Under `twinklr show` the heads' macro
    focal role moves a section's intensity a step (LEAD hotter, REST at most as
    authored). The values are a proposal for the owner's W5 view. Renderer revision 5.
    ([user guide](../docs/user-guide.md#how-a-sections-intensity-reaches-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w5-intensity/README.md))
  - **Known regression: the rest of the song intent is not rendered yet.** The planner's
    shutter and gobo events, lyric moment cues bound to events, section transitions,
    motif variation, density and modifiers are accepted and ignored (a per-section trace
    diagnostic says so). The renderer deleted in the cutover rendered events and entry
    transitions. The owner has directed that all of it be rendered on this renderer,
    with nothing cut from the planner contract; the remaining work is W6–W9 ([song-intent rendering](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)). The renderer is not
    complete until then.

  `twinklr run`, `show`, `eval-report`, `inject` and `regenerate` all use it;
  `regenerate` re-renders the whole song. Gate time on eight heads and a four-minute
  song: about 12–13 s in 4/4, 27–31 s in 3/4 (measured 2026-11-16). Output is guarded by
  `tests/regression/test_mh_pins.py`, which pins the render fingerprint and encoded
  frames of every family variant and one delivered `.xsq`. xLights reproduces its bytes.
  The owner accepted its look for one song on their rig in the house preview on
  2026-11-16. That render applied no planner intensity, colour, events or cues: the
  acceptance covers the templates' motion and timing, not the absence of song intent,
  which W4–W9 add with owner views (W4's, colour and gobo, is pending). There is no hardware result, and the profile timings
  used were chosen, not measured ([record](../changes/2026_11_12_mh_true_up/evidence/2026-11-16-p3-viewing-render/README.md)).
  `inject` and `regenerate` have been run only against a fake xLights client.
  Reference: [user guide](../docs/user-guide.md#job_configjson-job-config),
  [catalog README](../catalog/templates/moving_heads/README.md).
  `packages/twinklr/core/sequencer/moving_heads/`
- **Display rendering** — RGB/pixel effects with BeatGrid-exact coordination; lane blend
  intent overrides recipe blend metadata
  ([decision](../memories/decisions/lane-blend-mode-overrides-recipe.md)).
  Display output keeps every section lit: a brightness floor, a beat grid extended to the
  end of the song, and a foundation-coverage rule in the group planner
  ([decision](../memories/decisions/display-stays-lit.md)).
  `packages/twinklr/core/sequencer/display/`, `packages/twinklr/core/curves/`
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
the moving-head output pins and a hermetic display replay. The unmerged
`feat/mh-true-up-p3` branch has its own gate record in its
[change handoff](../changes/2026_11_12_mh_true_up/plan/handoff.md).

## Live evidence

| Date | Run | Result | Record |
|---|---|---|---|
| 2026-08-29 | OpenAI, `Need A Favor`, owner 4-head rig | Valid `.xsq`; meets or exceeds the pre-refactor baseline (396 effects vs 262) | [run notes](../changes/post-refactor-validation/notes/live-run-prereqs.md), [QA runbook](../docs/qa-runbook.md) |
| 2026-11-12 | Claude `claude-opus-5-5`, every role | 6/6 stages, about $0.95; on par with the baseline (251 effects vs 262; indicative, different song); human judgment PENDING-OWNER | [evaluation](../evaluations/2026-11-12-claude-baseline-live-run/README.md) |
| 2026-11-12 | Ollama cloud `glm-5.3:cloud`, every role | 6/6 stages, 0 schema repairs; on par with the baseline (256 effects vs 262; indicative, different song) | [evidence](../changes/twinklr-reactivation-review/evidence/2026-11-12-p4-t2-ollama-cloud-pipeline/README.md) |
| 2026-11-16 | Claude `claude-opus-5-5`, `Need A Favor`, owner 4-head rig, the current moving-head renderer | 29,631 effects; xLights reproduced every moving-head byte; look accepted by the owner for this song, rig and house preview: the templates' motion and timing, with no planner intensity, colour, events or cues applied (not a hardware result) | [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-16-p3-viewing-render/README.md) |

The three earlier runs rendered moving heads with the renderer deleted on 2026-11-16;
their effect counts are not comparable with the current renderer's.

Provider behavior learned from these runs is in
[live-provider-run-lessons.md](../memories/learnings/live-provider-run-lessons.md). The
points that shape current behavior:

- Claude refuses to compile the five planner schemas (`compiled grammar is too large`).
  The adapter recognizes them before sending (union-parameter limit and a schema-size
  proxy) and sends them once with the schema in the prompt only, validated client-side, so
  planner output on Claude has no server-side schema guarantee. The owner deferred a
  schema redesign.
- Ollama Cloud does not enforce `response_format`; the schema travels in the prompt.
- On OpenAI, strict mode passes for 7 of 8 roles; `audio_profile` shows runaway output.

## Active work

Active changes are listed in [changes/ACTIVE.md](../changes/ACTIVE.md). The moving-head
true-up's single-renderer cutover is complete on the unmerged branch `feat/mh-true-up-p3`
([handoff](../changes/2026_11_12_mh_true_up/plan/handoff.md)), with a known regression:
the planner's song intent is only partly rendered (section colour and gobo, W4). Its next
work is rendering the rest, tasks W5–W9 of
[song-intent rendering](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md). The table below is the
twinklr-reactivation-review build campaign: its code and tooling are merged and
independently verified, and what remains is empirical evidence and owner decisions, not
implementation.

| Phase | Implementation | Exit still needs |
|---|---|---|
| 0 Foundation, 1K Knowledge edges | Complete | — |
| 1P Render truth | 12/12 merged | Human judgment on the golden fixture (it rendered the moving-head renderer deleted on 2026-11-16, and its golden files went with it; whether this exit still applies is the owner's call); xLights import acceptance |
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
