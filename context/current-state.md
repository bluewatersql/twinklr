---
type: context
status: active
area: overview
updated: 2026-11-18
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
  structured output, compiled and enforced live on 2026-11-17); the moving-head renderer renders all of it but
  the parts' modifiers, a known regression (below).
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
    role table without one; a role the palette lacks is repaired to PALETTE_PRIMARY) and gobo as its
    nearest tagged state, turned only in the dark; a change at a boundary the heads play
    lit through dips dark (adding at most half a beat of darkness, riding any already there) before the section, else turns in the
    section's first dark window, else keeps the previous colour (recorded, and repaired
    for the planner). The offer also publishes each template's dark phases and the
    states its overlay masks cannot reach and, per pair of templates, the heads that always enter one dark after the other. Renderer revision 6 (W3/W4 second review). ([user guide](../docs/user-guide.md#how-a-sections-colour-and-gobo-reach-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w3-w4-offer-colour/README.md))
  - **Intensity on the dimmer** (W5, 2026-11-17, not yet seen by the owner). `as_authored`,
    SLOW, SMOOTH and FAST play the template as authored; DRAMATIC (every half bar in
    4/4, every bar in 3/4) and INTENSE (every beat) add a beat-locked pulse, every lit
    run (a reveal after any darkness) starting on an accent: over a level below full a
    raised floor and an accent, over a full level (every catalog family) a
    dip-and-return, the authored level on the accent easing to 75% / 60% of it between
    (more movement, not more light: about 0.80 / 0.74 of it on average); dark frames and
    every other channel untouched; a slow dimmer gets a smaller pulse, a dimmer latency
    an earlier one, a head without a dimmer none. Under `twinklr show` the heads' macro
    focal role moves a section's intensity a step (LEAD up, REST at most as
    authored) where every moving-head target holds it. The values are a proposal for the
    owner's W5 view; whether peak and LEAD sections should be brighter on average (a
    headroom variant is prepared for comparison) is the owner's open question. Renderer
    revision 7.
    ([user guide](../docs/user-guide.md#how-a-sections-intensity-reaches-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w5-intensity/README.md))
    The W5 re-review fixes (W6/W7 round) start no accent on a lit run's last frames,
    take a beat accent just after a reveal in place of the reveal's own, give a run its
    own accent only after half a beat of darkness, and blend the headroom and full
    shapes between 80% and 100% of full.
  - **Events and lyric cues** (W6/W7 and its fix round, 2026-11-17, not yet seen by the
    owner). Each section's events play on its frames, per head, on the frame nearest the
    beat, `bar N beat B` counted from bar N's downbeat (a pickup shifts nothing; the
    renderer, cue binder, repair and prompt agree): `closed` dark to the next shutter
    event or the section's end, `open` ends it; strobes (the fixture's own where the
    head's shutter has a state tagged for the speed, else 2 / 4 / 8 flashes a beat on
    musical time through the dimmer, or the shutter, slowed beat by beat where the
    darkness cannot follow); `pulse` lit the first half of each beat; `hit` a dip and
    snap to full where the head is lit before the beat, a flash and duck where it is
    revealed on it, scaled by the bound lyric cue's emphasis, counted played only where
    visible, lit from a dimmer dark phase, moved only where every head is dark (a
    cue-bound hit to the beat nearest its lyric, another later first); colour and gobo
    changes revealed on the beat after a dark lead of at most half a beat (a head dark on
    the beat shows it from its next reveal), moved within a bar where no head would show
    it within a beat, else not played. The trace records every event
    per head (unplaceable ones too) and every lyric cue with its offset from the lyric;
    the offer says what each event plays at the song's tempo; repair records, with the
    render's tests, what will play otherwise. Renderer revision 18.
    ([user guide](../docs/user-guide.md#how-a-sections-events-reach-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w6-w7-events/README.md))
  - **Transitions** (W8, 2026-11-17, not yet seen by the owner). Each boundary plays its
    ENTRY (or the previous section's EXIT; an ENTRY replaces an EXIT it meets) on a
    window placed by its mode, length (beats from the bar's downbeat) and split:
    `snap` dark just before the boundary and in place lit on it, `crossfade` the light
    handing over at half the lower level with the aim easing, `morph` every continuous
    channel easing, `sweep` the old look holding to the split point then travelling lit,
    `fade_via_black` out, change in the dark, up, `blackout` dark over the window;
    per-channel strategies override. A wheel never turns lit (a lit transition across a
    colour change dips dark at its split point, in place of the boundary's dip); a lit
    move too fast for the head moves dark; events in the window play (it yields, starts
    only after every visible event before it has been seen, and a dark mode ends before
    an incoming hit), hits play on it, and no transition loses a hit (a head that would
    plays none); intensity resumes after it on an accent. The song's first ENTRY and last EXIT play against the heads at rest. A
    transition counts as played on a head only where its frames differ from the plan
    rendered without transitions (else traced `nothing`, warned). Repair shortens one
    longer than its parts and records what plays otherwise; the trace lists each per
    head. Renderer revision 18.
    ([user guide](../docs/user-guide.md#how-a-sections-transitions-reach-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-17-w8-transitions/README.md))
  - **Motif and variation** (W10b/W10c, 2026-11-18, not yet seen by the owner). Each
    family template plays a three-by-three grid of variants (reach narrow/base/wide by
    rate slow/base/fast), each admitted on its own dry compile; one that plays the same
    as its base after its own base is not offered. Every later carrier of a motif varies
    the section that introduced it by one step (code derives each relation and source,
    from the macro thread where it lists the section, overwriting whatever arrives); a
    restatement returns to the introduced look, part by part; a variation without a motif
    steps from the previous section on its template. A step that cannot play plays the
    look it steps from, traced and repaired (`recorded`); a motif's colour and gobo are
    never changed. The trace's `arrangement` and the evaluation report say per section the
    relation and the variant played; `regenerate` says which kept sections a re-plan
    moves to another variant. A variation variant the rig is too slow for at the
    catalog's strength (a speed or range limit) is fitted to it by reach only, never its
    period (wide x1.4-x1.2; fast toward `narrow`'s reach at the halved period; render
    identity), and no two offered variants play alike. A colour or gobo change shown
    only briefly moves to a beat where it is shown half a beat (never losing a head that
    showed it, never worse than the unmoved outcome), else is traced `brief`. The song
    outranks the arrangement: the arrangement is built up greedily from the reference
    (every variation step off); a variation that makes any event worse gives way
    (render-decided, repair-predicted). Renderer revision 18.
    ([user guide](../docs/user-guide.md#how-a-sections-motif-and-variation-reach-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-18-w10bc-motif-variation/README.md))
  - **Density** (W10d, 2026-11-18, not yet seen by the owner). Density plays on the light:
    REST is dark (a synthetic `closed` the planner's events still play through), SPARSE
    darkens half the heads (mirror partners together) in turn on the played variant's
    cycle, BUSY adds an accent each bar on each head's first lit beat; BALANCED is
    unchanged. SPARSE keeps every head as BALANCED around each event and BUSY drops its
    accents there; each SPARSE or BUSY section is an arrangement unit, so it plays
    BALANCED (traced) wherever it would make any event worse. Repair records what does not
    play as asked and BUSY over a quarter of the song. Whether density should mean light (as built) or movement
    is put to the owner. Renderer revision 19.
    ([user guide](../docs/user-guide.md#how-a-sections-density-reaches-the-lights),
    [record](../changes/2026_11_12_mh_true_up/evidence/2026-11-18-w10d-density/README.md))
  - **Not rendered yet: modifiers.** Accepted and ignored (a per-section trace diagnostic
    says so); no renderer has rendered them. The owner has directed that all of the song
    intent be rendered on this renderer, with nothing cut from the planner contract; the
    remaining work is modifiers
    ([song-intent rendering](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)).

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
