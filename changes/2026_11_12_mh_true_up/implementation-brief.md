---
type: plan
status: active
area: engineering
change: 2026_11_12_mh_true_up
owner: Christopher Price
created: 2026-11-13
updated: 2026-11-16
---

# Moving-head true-up — implementation brief

Phase 0 ran on `feat/mh-true-up-p0` (cut from `main` at `b498ed9`) and merged to `main`
as `bb78227` on 2026-11-13. Phase 1 ran on `feat/mh-true-up-p1` in worktree
`twinklr-mh-true-up`, cut from `main` at `bb78227`, and merged to `main` as `52191b15`
on 2026-11-14. Phase 2 ran on `feat/mh-true-up-p2` in the same worktree, cut from
`main` at `d6096254` on 2026-11-14, and merged to `main` on 2026-11-16.

## Goal

Implement the moving-head true-up in the phases designed under [plan/](plan/README.md),
starting with Phase 0: make legacy behavior, ineffective controls and comparison inputs
explicit without changing any rendered output.

## Background

The [research brief](brief.md) authorized research and planning only and is complete.
The [report](report.md) and the [phase plans](plan/README.md) were each independently
reviewed. This brief is the implementation record the change needs before code work
begins; it does not replace the phase plans, which own the task detail.

## Scope

Phase 0, tasks P0-T1 through P0-T4, as written in
[plan/phase-0-foundation.md](plan/phase-0-foundation.md), including the documentation
and inventory-registry updates listed there. Later phases are in scope for the change
but each starts only on its own owner go-ahead, after the preceding phase's exit.

## Non-Goals

No change to default rendering, accepted goldens, the frozen deterministic selector
policy (`deterministic_selector.py` is not edited) or the three-arm experiment. No physical renderer, new effect family, planner
schema or evaluation harness in Phase 0. The non-goals in
[plan/architecture.md](plan/architecture.md#1-goals-and-boundaries) apply to every phase.

## Acceptance Criteria

Phase 0 (met 2026-11-13; evidence in
[evidence/2026-11-13-p0-baseline](evidence/2026-11-13-p0-baseline/README.md)):

- [x] P0-T1–T4 merged, each test-first and each reviewed in a context separate from
  its author.
- [x] `make validate` passes in the owned worktree after the last commit, with fresh
  output recorded.
- [x] No golden or regression file changed.
- [x] `job.schema_version`, `job.moving_heads` and `job.moving_heads.mode` have live
  inventory records, and `docs/user-guide.md`, `docs/overview.md` and
  `docs/pipeline_guide.md` state the schema version correctly.
- [x] The dated evidence record described in the plan's exit section exists.
- [x] Handoff and the `changes/ACTIVE.md` row reflect the result.

Phase 1 (met from offline evidence 2026-11-14; evidence in
[evidence/2026-11-14-p1-exit](evidence/2026-11-14-p1-exit/README.md)):

- [x] P1.0–P1.6 merged to the phase branch, each test-first and each reviewed in a
  context separate from its author.
- [x] `make validate` passes on the phase branch after the last code commit.
- [x] No golden or regression file changed; `legacy_v1` output is unchanged.
- [x] Every added config field has a live inventory record and a documented row.
- [x] The phase-exit conditions in the plan are met from offline evidence, with a dated
  evidence record. xLights transport proof, hardware accuracy and changed-look
  acceptance are recorded as `PENDING-OWNER`, not inferred.

Phase 2 (met from offline evidence 2026-11-16; evidence in
[evidence/2026-11-16-p2-exit](evidence/2026-11-16-p2-exit/README.md); tasks in
[plan/phase-2-composition.md](plan/phase-2-composition.md)):

- [x] P2.0, P2.1–P2.3, P2.4a–c and P2.5 merged to the phase branch, each reviewed in a
  context separate from its author. Test-first with one disclosed exception: the
  `on_unplayable` follow-up wrote production code before its tests and proved them by
  mutation.
- [x] `make validate` passes on the phase branch after the last code commit.
- [x] No golden or regression file changed; `legacy_v1` output, legacy planner session
  ids, the 16 Phase 0 render fingerprints and the two Phase 1 request fingerprints are
  unchanged, and a beat grid Phase 1 accepted renders the same physical frames (its trace
  gains only the keys P2.0 lists).
- [x] `physical_v2` accepts the 961-grid silent-edge sweep with the covered span
  reported, holds every fixture dark outside it and never infers tempo.
- [x] The six physical families compile deterministically on the synthetic rig matrix,
  are offered only under `physical_v2` and only on a rig that can render them (a rig
  lacking what one family needs still gets the others), and the 37-entry registry
  assertions are unchanged.
- [x] Each section's entry window is sized from a bound the fuzz shows dominates the
  transaction pass, the dip is skipped where eligible, and the plan-dependent failures
  the plan lists are documented, not claimed solved. Whether the remaining dips look
  acceptable is `PENDING-OWNER`.
- [x] Every added config field has a live inventory record and a documented row.
- [x] Each Phase 1 carry-forward is closed in the P2 task the plan names, or remains
  deferred to the later phase it names. Exception, disclosed: the gate dry-compile cost
  (carry 1) was measured and reduced but is over its 20 s target; carried to Phase 3.
- [x] The phase-exit conditions in the plan are met from offline evidence, with a dated
  evidence record that includes the measured pre-planning gate time. xLights transport
  of the six families passed on owner authorization
  ([result](evidence/2026-11-16-p2-xlights-result/README.md)); hardware accuracy, the
  zoom pilot's real-profile result and changed-look acceptance are recorded as
  `PENDING-OWNER`, not inferred.

## Constraints

- [Execution guardrails](../shared/agent_guardrails.md) and the global requirements in
  [plan/architecture.md](plan/architecture.md#1-goals-and-boundaries).
- Phase 0 needs no owner-gated action: no provider call, owner-local data, xLights
  session or hardware. Its tests are synthetic and offline.
- Later phases contain owner-gated steps (expendable-show xLights renders, fixture
  observations, human review). Each needs its own recorded authorization at that time;
  nothing in this brief grants one.

## Approvals

| Item | State |
|---|---|
| Start the change from `main` in a clean worktree after the display fixes | Owner direction, 2026-11-13 |
| Begin Phase 0 implementation | Owner go-ahead, 2026-11-13 ("commit them on that branch and merge to main. then start phase 0"). Covers Phase 0 only |
| Merge Phase 0 and the install fix to `main` | Owner direction, 2026-11-13 ("Merge phase 0 and install fix to main") |
| Begin Phase 1 implementation | Owner go-ahead, 2026-11-13 ("Proceed with Phase 1"). Covers Phase 1's offline work only; its owner-gated steps (expendable-show xLights render, fixture observation, look acceptance) are not authorized by it |
| Reject `physical_v2` at job load | Owner direction, 2026-11-13: added to Phase 1 as task P1.0 |
| Paid/live provider (API) calls | Owner authorization, 2026-11-13 ("online/live api call approved as needed"). Covers provider requests this change needs; no cost cap was stated, so each use is kept to the minimum that answers the question and is logged with its purpose in the evidence record. Does not cover owner-local data, xLights mutation, hardware or taste verdicts |
| Layout input for `twinklr run` | Owner direction, 2026-11-14 ("add --layout to run"): added to Phase 1 so the xLights model check can run for a physical job |
| Silent song edges in the physical phase map | Owner direction, 2026-11-14 ("defer silent edges to phase 2"). Phase 1 exits with `physical_v2` refusing a grid with more than one beat of silence or fade at either end |
| Merge Phase 1 to `main` and push | Owner direction, 2026-11-14 ("merge and push") |
| xLights test of the Phase 1 physical output | Owner authorization, 2026-11-14 ("test in xlights as previous"): the expendable-show render in [the request](evidence/2026-11-13-p1-xlights-request/README.md), run the way earlier xLights checks in this repository were run. Expendable show folder or scratch sequence only |
| Default `max_effects` of 1,000,000 | Owner approval, 2026-11-14 ("1,000,000 budget approved") |
| Begin Phase 2 implementation | Owner go-ahead, 2026-11-14 ("then proceed to phase 2"). Covers Phase 2's offline work; its owner-gated steps need their own authorization |
| Run Phase 2 to completion without check-ins | Owner direction, 2026-11-15 ("continue with autoplot and ultraqwork without stopping until finished"). Covers Phase 2's offline tasks and closeout; integrator decisions made under it are recorded in the Phase 2 plan for the owner to reverse |
| Merge Phase 2 to `main` and push when complete | Owner direction, 2026-11-16 ("continue. commit. merge and push when completer"). Applies once Phase 2's tasks are reviewed, committed and `make validate` passes. Does not cover xLights runs, hardware, look verdicts or starting Phase 3 |
| xLights test and recording of the Phase 2 families | Owner authorization, 2026-11-16 ("run the test in xlights as screen record the results"). Run on a scratch show; [result](evidence/2026-11-16-p2-xlights-result/README.md). Does not cover hardware or a look verdict |
| Cut the gate time, then begin Phase 3 | Owner direction, 2026-11-16 ("cut the gate time, then proceed to phase 3"). Covers the gate-time reduction and Phase 3's offline work on `feat/mh-true-up-p3`, cut from `main` at `7356b376`. Phase 3's owner-gated steps (owner media, xLights acceptance, taste verdicts, merge and push) need their own authorization; live provider calls stay under the 2026-11-13 row |
| Single path for moving heads | Owner direction, 2026-11-16 ("no backwards compat. no tech debt … only a single path exists"). Reverses the architecture's "`legacy_v1` remains the default" and its opt-in design. Chosen scope: the cutover is Phase 3's first task; the old renderer, its templates, the `mode` and schema-version switches and the old planner contract are removed **after** the owner has viewed a real-audio physical render in xLights and accepted it. Phase 3 planner work has one contract from the start. The deterministic selector and the three-arm experiment are ported to the physical families, not kept beside them. The rule is added to the shared guardrails |
| Viewing render and old-renderer reference: inputs | Owner direction, 2026-11-16 ("Use what we have been using"), answering which song and rig to use. Read as the inputs of the 2026-11-12 runs: `data/music/11 - Need A Favor.mp3`, the owner-rig fixture config and job/app configs under `artifacts/live-validation/`, and the layout of the owner's show folder `~/xlights`, read only. Rendering happens in an expendable copy under `~/xlights/_twinklr_verify/`; the owner's show folder and sequences are not written. Live planner calls fall under the 2026-11-13 row and are logged. The physical profile written for the rig uses chosen, unmeasured timings. No look verdict is implied |
| Run Phase 3 without check-ins | Owner direction, 2026-11-16 ("continue. autopilot. ultrawork. superpowers"). Covers the offline Phase 3 work in progress (family adaptation, profile defaults, the offline gate rerun) and the viewing render with its old-renderer reference under the inputs row above. Does not cover deleting anything from the old renderer (waits for the owner's look acceptance), merge or push, hardware, or a look verdict. Integrator decisions made under it are recorded in the Phase 3 plan for the owner to reverse |
| Look acceptance of the physical renderer; start the cutover | Owner verdict, 2026-11-16: "approved", clarified as "Look accepted, start the cutover", with bar placement confirmed by ear ("Yes, they line up"), after viewing the Need A Favor side-by-side preview ([record](evidence/2026-11-16-p3-viewing-render/README.md)). Authorizes the single-path cutover on `feat/mh-true-up-p3`: removing the old renderer, its templates, switches and the tests and goldens that pin its output, and superseding [mh-render-matches-pre-cleanup-look](../../memories/decisions/mh-render-matches-pre-cleanup-look.md). Does not cover merge or push, hardware, or testing live `inject`/`regenerate` against a running xLights show |
| Fix the plan-schema rejection | Owner direction, 2026-11-16 ("fix the plan schema rejection while I review the video"). Up to three small live requests to confirm the provider accepts the schema |
| Song intent must be rendered, not cut | Owner direction, 2026-11-17 ("no color and nothing ties to the lyrics....hard fail....and misses the whole intent of an ai sequencer"; "some how we went from true up...to dumb down ... get it together and fix it"). The planner's song intent (colour, intensity, lyric and musical accents, variation, transitions) is rendered on the single path; nothing leaves the planner contract without the owner's word. Plan: `plan/song-intent-rendering.md` |
| Fast-tempo test song | Owner direction, 2026-11-17 ("if you need a fast pace song to test use the `data/songs/Dance Jams Final Audio.mp3` as a test file"; the file is at `data/music/Dance Jams Final Audio.mp3`). Covers reading that file for local audio analysis, gate runs, planning and viewing renders of this change. It is owner-local data: never copied into a repository; outputs only under the scratchpad or `~/xlights/_twinklr_verify/` |
| Phase 0 keeps `identity.py` (render fingerprint) | Kept as planned. Its Phase 0 consumer is the evidence record; say so if it should move to Phase 1 instead |

## Kickoff checklist

Run by the integrator when the go-ahead is given, before the first task brief is sent:

- [x] `main` contains the display fixes; create the worktree and branch from it and run
  `make install` inside it
  ([validating inside a worktree](../../context/agents/operating-model.md#validating-inside-a-worktree)).
- [x] Record the starting commit here and in the handoff. Starting commit: `b498ed9`.
- [x] Run `make validate` once on the untouched worktree and record the result, so a
  later failure can be attributed. Result: 5763 passed, 39 skipped, after installing
  the `anthropic` extra by hand (see the evidence record).
- [x] Diff the starting commit against `f067a56` for the paths in the Phase 0
  [file ownership table](plan/phase-0-foundation.md#file-ownership-and-ordering). If
  any changed, re-read the affected plan section and correct it before dispatch.
  Result: no Phase 0 path changed. The display fixes added
  `BeatGrid.extended_to_duration()`, recorded for P1.2 in its plan.
- [x] Set this brief and the Phase 0 plan to `status: active`, and update the
  `changes/ACTIVE.md` row with the branch.
- [x] Write each task brief from
  [subagent-task-brief](../../prompts/planning/subagent-task-brief.md), including the
  guardrails path.

## Relevant Context

[context/architecture/pipeline.md](../../context/architecture/pipeline.md),
[context/engineering/conventions.md](../../context/engineering/conventions.md),
[context/agents/operating-model.md](../../context/agents/operating-model.md).

## Relevant Decisions

- [mh-render-matches-pre-cleanup-look](../../memories/decisions/mh-render-matches-pre-cleanup-look.md):
  the legacy look Phase 0 must leave untouched.
- [unified-xlights-emission-contract](../../memories/decisions/unified-xlights-emission-contract.md):
  the shared emission core later phases export through.

## Relevant Source Areas

`packages/twinklr/core/config/models.py`,
`packages/twinklr/core/sequencer/moving_heads/`,
`packages/twinklr/core/agents/sequencer/moving_heads/`, `tests/config_effects_registry.py`,
`tests/golden/`, `docs/user-guide.md`, `docs/overview.md`, `docs/pipeline_guide.md`.

## Validation Plan

| Command | Purpose |
|---|---|
| Per-task `uv run pytest ...` commands in the phase plan | Prove each task while iterating |
| `uv run pytest tests/unit/config -q` | Inventory, documented-config and discriminator guards after P0-T1 |
| `uv run pytest tests/golden tests/regression -q` | Legacy output unchanged |
| `make validate` | Completion gate, run on a committed tree in the owned worktree |

## Implementing Agent / Model

One implementing subagent per task, briefed by the integrator. T1 then T2 in one
worktree; T3 and T4 in their own worktrees, in parallel.

## Reviewing Agent / Model

A separate reviewing agent per task, given the diff and the task's acceptance criteria.
The integrator merges and runs the gate.
