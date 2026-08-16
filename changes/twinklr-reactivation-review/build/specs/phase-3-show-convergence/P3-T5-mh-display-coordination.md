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
both back-ends' emitted output.** P3-T4 owns the recursive typed/by-name projection,
prompt, cache, and validation readers; its amended acceptance criterion #2 does not
depend on this task landing.

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
3. **Shared layout.** One parsed layout produces the canonical full macro graph, one
   `XLightsMapping`, exact dedicated-MH ownership, and the non-MH display partition.
   The moving-head fixture rig and display elements are two ownership views of one
   show, not separately invented configurations.
4. **Coordination fields are consumed on both sides.** Specifically:
   - `focal_roles` / `focal_arc`: the section's LEAD target gets the dominant treatment
     in both renderers; REST targets are demonstrably quieter (fewer/lower-intensity
     events).
   - `call_response_pairs`: when a pair names an MH group and a display group, the two
     renderers alternate on the pair's `step_unit`/`step_duration` — the call's effects
     and the response's effects do not overlap in time.
   - `coordination_intent`: the section's `CoordinationMode` reaches the display
     composition path **and** changes emitted MH segment/timing structure for that
     section without changing the existing MH template-selection algorithm.
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

- Do **not** unify the export writers here — that is P3-T6 (Lane X). P3-T5 pulls forward
  only unconditional positional registry seeding/preservation so display append cannot
  corrupt existing MH references. General export-core merge, quantization, trace,
  injection, and layer policy remain P3-T6.
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
     the emitted MH segment/timing structure, without changing its selected template) —
     a fixture-diff test.
   - `palette_role`: the MH colour intent and the display palette for a section resolve
     from the same `PaletteStop` (assert on the resolved values).
5. P3-T4's recursive typed/by-name reader test remains green, and every behavioral
   coordination field additionally reaches an emitted-output assertion here.
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

1. `tests/integration/test_combined_show_pipeline.py` — shared-prefix execution counts,
   BeatGrid identity, one sequence, real macro-derived MH colour, and a real two-section
   segmented/transition-enabled MH render.
2. `tests/unit/sequencer/test_show_coordination.py` — focal budgets, call/response,
   coordination-mode emission, palette projection, flattened/transition identities,
   cache idempotence, and irregular-grid property matrices.
3. `tests/unit/pipeline/test_show_pipeline_wiring.py` — canonical graph/partition and
   fail-closed layout/fixture ownership reconciliation.
4. `tests/unit/cli/test_show_command.py` — additive command plus catalog/FE/style input
   and absence/error behavior.
5. `tests/golden/test_combined_show_golden.py` — the committed normalized XSequence and
   trace-sidecar artifacts with the drop-section assertions above.
6. Regression: the immutable `tests/golden/` suite plus display-only and MH-only wiring/
   integration tests remain green.

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

## Implementation, owner acceptance, and integration record — 2026-08-16

The implementation was authored in an isolated P3-T5 worktree based on `3f1f236`, with
separate adversarial and verifier passes. No provider, network, audio processor, xLights
process, or live/paid surface was used. After the final remediation and gate evidence
below, the owner explicitly accepted all nine decisions. P3-T5 was subsequently
integrated at `f006468`.

### Accepted owner decisions

The owner accepted all nine on 2026-08-16:

1. The additive combined surface is `twinklr show`; `twinklr run` and `twinklr display`
   retain their branch-only behavior.
2. One parsed layout produces the canonical macro graph. A dedicated fixture group is
   reconciled by exact active direct membership, and the display planner receives the
   non-MH partition. Missing, inactive, extra, nested, overlapping, or ambiguous
   ownership fails before provider work. Duplicate declarations anywhere in the raw
   model or model-group collections, duplicate dedicated-group members, and slash-
   qualified submodel references are rejected before any map/set collapse or whole-
   model comparison. The layout-derived group ID remains canonical; no synthetic
   `MOVING_HEADS` target is invented for differently named layout groups.
3. Focal-role normalization is deterministic at the emitted boundary: display
   aggregate activation budgets are weighted `LEAD=1.0`, `SUPPORT=0.65`, `REST=0.15`
   per concrete target regardless of unequal event counts; MH categorical projections
   are `INTENSE`, `SMOOTH`, and `SLOW` respectively. For each section/target, raw
   activation is `sum(intensity * duration_ms)`; the common base is the minimum
   `raw / role_weight`, and every target scales down to `base * role_weight`.
   Unmentioned targets default to SUPPORT.
4. The effective palette stop/section override is resolved once. Display receives its
   ordered colors, while MH receives the closest fixture-neutral wheel preset using a
   stable declared RGB table and declaration-order tie break.
5. Expanded call/response teams are call-first, grid-derived, clipped, disjoint, and
   deep-copied. A concrete target reused across pairs, reversed/self-overlap after
   expansion, or an empty/unknown target fails closed. Unpaired targets retain
   full-section SUPPORT behavior, and a section too short to contain both phases fails
   explicitly for BEAT, BAR, and PHRASE steps. Typed pairs are valid if and only if the
   section coordination intent is `CALL_RESPONSE`; either half of that equivalence
   missing fails closed.
6. The acceptance phrase “MH selection” is interpreted as emitted segment/timing
   structure. The candidate does not change the MH template-selection algorithm, in
   accordance with this task's non-goal.
7. One original tracked `Spirals` recipe is added solely to make the required combined
   golden honest and clean-clone reproducible.
8. The narrow EffectDB/palette positional-preservation prerequisite is pulled forward
   from P3-T6 because appending display output otherwise corrupts MH references. This
   candidate does not add P3-T6 quantization, trace unification, injection unification,
   or a general arbitrary-document merge policy.
9. The combined command preserves P3-T3's effective-catalog edge: tracked recipes are
   overlaid by optional local extensions and then FE-promoted recipes; FE/style inputs
   reach the planner, empty/missing catalogs fail before provider work, and planner/
   renderer recipe IDs must match exactly.

### Implemented seams and evidence

- `show_coordination.py` is the post-plan/pre-export deterministic sink for every P3-T4
  behavioral field. It derives immutable windows only from the exact shared `BeatGrid`,
  expands GROUP/ZONE/SPLIT teams, is idempotent for fresh/cache-hit branch outputs, and
  preserves provider-authored plans through deep copies.
- Compiler identities are reconciled explicitly: flattened `section|segment` names and
  generated transition source/target IDs resolve to their parent macro sections. Real
  transition-enabled segmented rendering is covered end to end; no bare iterator
  failure remains.
- Macro-derived MH intent is revalidated as explicit schema-v2 intent rather than
  retaining the legacy-omission marker, so an effective cyan palette override emits the
  fixture's cyan DMX value instead of coincidentally matching a template default.
- Display idempotence recognizes only the coordinator-owned terminal event suffix
  `|coord-<digits>`. Raw RecipeCompiler IDs terminate in a SHA-256 digest, so local,
  tracked, or FE-promoted template IDs containing `|coord-` remain ordinary inputs and
  still pass through coordination.
- The real combined definition composes the existing display/MH definitions, executes
  `audio/profile/lyrics/macro` once, plans both branches, and joins them at one final
  render barrier. The barrier compiles MH in memory, builds one sequence, then appends
  coordinated display effects.
- `MovingHeadStage` now reuses `context.state['beat_grid']` by identity. The prior
  reconstruction is covered by a discriminator that patches `from_song_features` to
  fail if called.
- The registry regression snapshots MH `ref -> settings` and palette positions before
  display append and requires exact resolution afterward.
- The combined integration runs the actual AudioAnalysisStage on irregular fixture
  boundaries, deterministic provider-boundary fixtures, the real MH compiler, and the
  real display renderer. It asserts one execution of each common stage, one sequence,
  and the exact same grid object through both renderers.
- The accepted normalized golden contains actual `DMX` effects resolving to pan/tilt/
  dimmer/color settings, actual `Spirals` on Mega Tree, and actual `SingleStrand` chase
  on Yard Arches, with call/response windows disjoint on irregular detected beats. Its
  trace sidecar pins every coordinated display event, source template, target, layer,
  and emitted interval.

Fresh author gates after the final changes:

- final CLI/coordinator/ownership/integration/golden approval focus: `54 passed`
- catalog/CLI/display/show definition regression: `64 passed`
- immutable golden suite: `74 passed, 8 skipped`
- full offline suite: `5337 passed, 38 skipped` (9 existing deprecation warnings)
- Ruff format: `1356 files already formatted`; Ruff lint clean
- mypy: success across `728 source files`
- `git diff --check`: clean
- nominal-tempo math grep: one pre-existing display timing-resolver occurrence; no
  increase

The first broad run exposed one expected catalog-coverage fixture delta after adding the
sixth tracked recipe (`2/15 -> 3/15` cells); its deterministic expectation was updated,
and the two subsequent full runs passed. An all-extras environment also exposed the
pre-existing optional-Anthropic mypy import pattern; the canonical/default verifier
environment (and main baseline) omits that optional provider extra and passes. Neither
finding is carried as an accepted implementation failure.

Independent review initially rejected an earlier candidate after reproducing sparse-target
deletion, flattened/transition identity crashes, event-count role inversion, call-only
short sections, a missing P3-T3 catalog edge, and a non-discriminating manually supplied
MH golden color. The remediation added seven failing coordination discriminators and
five failing catalog/CLI discriminators before implementation. All are green in the
fresh gates above.

A second independent review then exposed role aggregation by category rather than by
concrete target, permissive pair/mode mismatches, and lossy normalization of duplicate
or submodel-qualified dedicated-group members. Six coordinator and two ownership
discriminators failed before the second remediation. Parameterized 2/7/100-event
support-target cases now prove exact per-target role ratios and idempotence; mode/pair
equivalence and raw whole-model membership are fail-closed. The final fresh gates above
include this second remediation; a subsequent adversarial pass produced the third
remediation below.

A third adversarial pass found two further lossy-normalization hazards: duplicate model
or model-group declarations outside the dedicated group could be hidden by later maps,
and the display idempotence test treated any `|coord-` substring as coordinator
provenance. Three layout and three recipe-ID discriminators failed before remediation.
Global duplicate-name checks now precede every collection collapse, including the
non-dedicated overlap-masking case. Parameterized tracked/local/FE-style compiler IDs
containing `|coord-` now coordinate normally and remain identical on a second pass. The
fresh gates above include this third remediation.

### Integration boundary

P3-T5 is integrated at `f006468` with the nine decisions above as its binding contract.
The integration does not waive the open Phase 1P/2P/2K empirical exits, does not convert
P3-T4's failed live probe into live acceptance, and does not authorize another P3-T4
attempt. P3-T6 and later Phase 3 implementation remain unauthorized. No P3-T5 live,
paid, xLights, owner-audio, or owner-layout work was performed or inferred from the
offline fixtures.
