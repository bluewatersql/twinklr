# P3-T5 — MH + display coordination

Phase: 3 (Show Convergence / M3) · Lane: W (wiring) · Executor: opus · Verifier: opus
· Depends on: P3-T3, P3-T4

## Objective

Twinklr's two renderers currently run as two pipelines that happen to analyse the same
audio. This task makes **one show plan drive both**: a single run produces moving-head
choreography and display choreography from one macro arc, one BeatGrid, and one
layout, with section-level coordination that is visible in golden output — the drop
where the moving heads sweep, the megatree spirals, and the arches chase, all from one
plan. This is the convergence M3 exists for.

## Evidence & background

Drivers: **D3** (macro planner as the cross-element coordination spine) and program
**M3** in `reactivation-proposal.md`; the contract it coordinates through is
**P3-T4**. Enabling repairs already landed: **CF-2 / P4-F2 / P4-M3** (three misaligned
grids — fixed at the consumer level by P1P-T4 and at the source by P2P-T8),
**P5-F1/F2/F12** (composition timing — P3-T1), **P5-F3/M1** (blend modes and effect
fallback — P3-T2), the CLI/apply-edge wiring (P3-T3).

### What M3 promises

From `reactivation-proposal.md` §4:

> **M3 [convergence] — Part 2 ships**: display composition repairs; display pipeline
> CLI-reachable consuming catalog + macro arc + user layout; MH+display coordinated;
> unified export core; **assets revival (D13)**; injection workflow across both parts.
> *Exit*: one command → coordinated, learned, evaluated show for the user's layout;
> evaluation feedback begins flowing into the loop (D5's fourth arm).

And the phase's own exit criterion
(`changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`):

> one command, one song, the user's layout → coordinated MH + display show importable
> into xLights (or injected live)

### Why coordination is a macro concern

From `reactivation-proposal.md` D3:

> repair to a structured contract; it is the cross-element coordination spine ("arches
> answer the megatree" is a macro statement).

P3-T4 delivers the typed fields that carry it: `focal_arc` / `focal_roles`
(LEAD/SUPPORT/REST per section), `call_response_pairs` (explicit "X calls, Y answers"
with `step_unit` + `step_duration`), `coordination_intent` (`CoordinationMode`), and
`palette_arc` / `palette_role`. **This task is the first consumer of those fields on
both back-ends** — P3-T4's acceptance criterion #2 ("zero unread fields") depends on
this task landing.

### The grid situation this task inherits

CF-2 (CRITICAL) was three misaligned grids: the planner's nominal-tempo floored
conversion (`agents/sequencer/moving_heads/context.py::_ms_to_bar`), the renderer's
average grid, and the timing tracks' detected grid. P1P-T4 fixed the consumers ("after
this task all three agree") and P2P-T8 upgraded the source. P3-T1 removed the display
side's fourth divergence (expansion's constant `60000/tempo_bpm` vs
`beat_boundaries`). **This task must not introduce a fifth**: both renderers take the
same `BeatGrid` instance from pipeline state, and neither re-derives beat timing.

### Current structure (verified)

- `pipeline/definitions/common.py::build_common_stages` (`:18`) builds the shared
  prefix: `AudioAnalysisStage` → `AudioProfileStage` + `LyricsStage` →
  `MacroPlannerStage(display_groups=…)`.
- `pipeline/definitions/moving_heads.py::build_moving_heads_pipeline` (`:22`) appends
  `MovingHeadStage` (`:65`) and `MovingHeadRenderingStage` (`:78`).
- `pipeline/definitions/display.py::build_display_pipeline` (`:44`) appends the group
  planner FAN_OUT, aggregate, holistic, asset resolution, and `DisplayRenderStage`.
- Both already consume the same macro stage; **the common prefix is the seam this task
  builds on** — it exists, it is just never used to build one pipeline.
- `DisplayRenderStage` already reads `beat_grid`, `choreo_graph`, `xlights_mapping`,
  `sequence`, and `macro_plan` from context state (`pipeline/display_stages.py`,
  `:194-215`, `:331-345`).

## Current behavior

- `twinklr run` executes the moving-heads pipeline. After P3-T3, a separate command
  executes the display pipeline. Two runs, two analyses, two macro plans, two BeatGrids
  (each cached separately), two output files with no relationship to each other.
- Nothing in either renderer knows what the other is doing at any moment in the song.
  "Coordination" exists only as prose inside a prompt.
- The macro plan's coordination fields (after P3-T4) have no consumer.

## Target behavior

1. **One command, one plan, both renderers.** A single invocation runs the common
   prefix once (analysis → profile + lyrics → macro), then drives both the moving-head
   branch and the display branch from that one macro plan, and emits both renderers'
   output into **one** sequence (see P3-T6 for the shared export core; until it lands,
   into one `XSequence` object through the existing writers).
2. **Shared BeatGrid, by identity.** Both branches read the same `BeatGrid` object from
   pipeline state. A test asserts identity (`is`), not equality — the failure mode CF-2
   documents is two grids that *look* similar and drift.
3. **Shared layout.** One `ChoreographyGraph` + `XLightsMapping` (from P3-T3's layout
   source) serves both branches; the moving-head fixture rig and the display elements
   are two views of one show, not two configurations.
4. **Coordination fields are consumed on both sides.** Specifically:
   - `focal_roles` / `focal_arc`: the section's LEAD target gets the dominant treatment
     in both renderers; REST targets are demonstrably quieter (fewer/lower-intensity
     events).
   - `call_response_pairs`: when a pair names an MH group and a display group, the two
     renderers alternate on the pair's `step_unit`/`step_duration` — the call's effects
     and the response's effects do not overlap in time.
   - `coordination_intent`: the section's `CoordinationMode` reaches the display
     composition path (it already has the enum) **and** biases the MH template/segment
     selection for that section.
   - `palette_arc` / `palette_role`: both renderers resolve colour from the same stop,
     so a section's MH colour intent and display palette agree.
5. **Section-level coordination is provable from the output.** The golden artifact for
   a drop section shows, from one plan: an MH movement on the fixtures, a spiral-class
   effect on the megatree element, and a chase-class effect on the arch elements, with
   consistent section boundaries and a shared palette. The assertion is on the emitted
   sequence, not on the plan.
6. **Either branch alone still works.** Running display-only or MH-only remains
   possible (for iteration and for P2P-T13's arms); the combined path is additive, not
   a replacement that couples the two into one unrunnable unit.
7. **One run, one cost.** Analysis, profile, lyrics, and macro planning execute **once**
   per combined run — not once per branch. Assert on stage-execution counts.

**Non-goals**

- Do **not** unify the export writers here — that is P3-T6 (Lane X), which merges after
  P3-T2. If T6 has landed, use it; if not, keep the two writers and make them write
  into the same `XSequence`, and note the seam.
- Do **not** change composition math, template selection algorithms, or DMX channel
  policy.
- Do **not** build the evaluation of the combined show — P3-T8.
- Do **not** enable assets (P3-T7 owns the gate).
- Do **not** invent new coordination vocabulary. P3-T4's contract is the vocabulary;
  if something is missing, that is a change to P3-T4's spec, not a local addition.

## Implementation approach

Files expected to change:

- `packages/twinklr/core/pipeline/definitions/` — a combined show pipeline built from
  `build_common_stages` + both branches. Prefer composing the existing builders over
  copying their stage lists; a third divergent wiring of the same stages is exactly the
  duplication class CC-6 records.
- `packages/twinklr/cli/main.py` — the combined command (or a flag on P3-T3's command;
  the surface decision is P3-T3's, extend it consistently).
- `packages/twinklr/core/agents/sequencer/moving_heads/` — consume the coordination
  fields on the MH planning side (context/orchestrator inputs, not new prompt prose).
- `packages/twinklr/core/sequencer/display/composition/` — consume
  `coordination_intent` and `call_response_pairs` where the composition path already
  has the concepts (`CoordinationMode`, `CoordinationConfig.group_order`,
  `step_unit`/`step_duration`).
- `packages/twinklr/core/pipeline/display_stages.py` / MH render stage — shared
  `XSequence` and shared grid plumbing.

Design decisions already made — do not relitigate:

- The coordination channel is the **typed macro contract** (P3-T4), not a new
  side-channel and not prompt prose. CF-3's whole point is that prose is not a channel.
- The shared prefix is `build_common_stages`. It already exists and already ends at the
  macro planner.
- Display consumes the catalog and the layout as established by P3-T3; MH consumes the
  fixture config as established by P1P-T11.

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both
> halves (P1P-T4).

> Cross-lane file conflicts are called out in the task tables; when unavoidable, the
> later lane rebases.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: Lane W is `T3 → T4 → T5`; Lane A
(T7, assets) is "independent until T5" — so T7 rebases here if it merges later.

## Acceptance criteria

1. One command produces both MH and display output for one song and one layout, in one
   process, with the analysis/profile/lyrics/macro stages each executing exactly once
   (assert on stage results, not on wall-clock).
2. `assert mh_beat_grid is display_beat_grid` holds in the combined run.
3. Both renderers' section boundaries derive from the same macro `sections` list; a
   test asserts identical boundary ms on both sides.
4. Coordination consumption, each with its own assertion on **emitted output**:
   - LEAD/SUPPORT/REST: the LEAD target's emitted event count (or intensity sum) for a
     section exceeds SUPPORT's, which exceeds REST's.
   - `call_response_pairs`: emitted call-target effects and response-target effects for
     the pair are time-disjoint within the section, alternating on the declared step.
   - `coordination_intent`: changing a section's mode from `UNIFIED` to `SEQUENCED` in
     the plan fixture changes the emitted display timing pattern for that section (and
     the MH selection for that section) — a fixture-diff test.
   - `palette_role`: the MH colour intent and the display palette for a section resolve
     from the same `PaletteStop` (assert on the resolved values).
5. P3-T4's "zero unread fields" test passes with every coordination field now having a
   named reader.
6. Display-only and MH-only runs still work and produce output identical to what they
   produced before this task (given the same plan fixture).
7. No new grid: `grep -rn "60_000.0 /\|60000 /" packages/twinklr/core/sequencer/` shows
   no new occurrence introduced by this task, and existing ones are unchanged or
   reduced.

Golden-diff expectations (**this is the task's headline artifact**):

- Commit a **combined-show golden** for one deterministic plan fixture: one `.xsq` (or
  its normalized text form) containing both MH fixture effects and display element
  effects, plus the trace sidecar.
- BEFORE (from P3-T3's display golden + the MH golden): two unrelated files; no
  cross-part relationship assertable.
- AFTER: one file; for the designated drop section, assert the presence of (a) an MH
  movement effect on the fixture element, (b) a spiral-class effect on the megatree
  element, (c) a chase-class effect on the arch elements, (d) all three within the same
  section boundary ms, (e) resolved from the same palette stop.
- MH-only and display-only goldens unchanged.

## Tests

1. `tests/integration/test_combined_show_pipeline.py::test_single_run_drives_both`
   (marked `@pytest.mark.integration`) — fake provider, deterministic plan fixture;
   asserts stage-execution counts, shared grid identity, and both outputs present.
2. `…::test_stages_execute_once` — the shared-prefix guarantee.
3. `tests/unit/sequencer/test_focal_roles_consumed.py` — LEAD/SUPPORT/REST assertion on
   emitted events, both renderers.
4. `tests/unit/sequencer/test_call_response_across_parts.py` — time-disjoint
   alternation for an MH↔display pair.
5. `tests/unit/sequencer/test_coordination_intent_reaches_both.py` — the
   fixture-diff test for `UNIFIED` vs `SEQUENCED`.
6. `tests/unit/sequencer/test_shared_palette_stop.py` — MH colour intent and display
   palette resolve from one stop.
7. `tests/golden/test_combined_show_golden.py` — the committed combined artifact, with
   the five drop-section assertions above.
8. Regression: `tests/golden/` MH and display goldens unchanged; display-only and
   MH-only integration tests still pass.

All tests must run from a clean clone against the tracked catalog (P1K-T3) and a fake
LLM provider. No test may require `data/templates`.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/sequencer/ -v
uv run pytest tests/integration/test_combined_show_pipeline.py -v
uv run pytest tests/golden -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline
```

LOCAL-ONLY:

- **xLights GUI**: import the combined `.xsq` into xLights 2026.15 and confirm both
  parts appear on their expected models with correct section alignment. Follow the V4
  protocol from the phase review: "(a) generate a `.xsq`; (b) open in current xLights
  and record whether it loads, warns, or migrates; (c) **save from xLights and diff the
  saved file against the generated one**." Record the result in the PR body.
- **Live injection** (if P2P-T12 has landed): drive the combined plan into a running
  xLights via `addEffect` and confirm both parts arrive. Optional; not blocking.
- **Live LLM**: one combined end-to-end run for the owner demo. **Test budget: one
  live combined run at the configured models (analysis + profile + lyrics + macro +
  both planners, single pass).** All automated verification uses fakes at $0.

## Effort & risk

**Size: L.** Cross-cutting by construction; touches both renderers and the pipeline
definitions.

**Main risk: coordination that exists only in the plan.** The failure mode this whole
program is built around is output produced with no sink — a plan that *says* "arches
answer the megatree" while the renderers each do their own thing would pass any
plan-level test and fail the product. *Mitigation*: every coordination acceptance
criterion above asserts on **emitted output**, not on plan content, and the combined
golden is the deliverable.

**Secondary risk: re-splitting the grid.** Two branches, two stage graphs, and an easy
temptation to let each derive its own timing. *Mitigation*: the identity assertion
(`is`, not `==`) plus the grep guard.

**Third risk: silent double-spend.** A naive combined pipeline re-runs the common
prefix per branch, doubling LLM cost on the one path the owner will actually use.
*Mitigation*: acceptance criterion #1 asserts execution counts. Note that per-stage
token attribution is only trustworthy after P1P-T9 / P2P-T9 (CC-4: the profile∥lyrics
gather race), so assert on **stage executions**, not on token totals.
