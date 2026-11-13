---
type: plan
status: active
area: engineering
change: 2026_11_12_mh_true_up
owner: Christopher Price
created: 2026-11-13
updated: 2026-11-13
---

# Moving-head true-up — implementation brief

Branch/worktree: `feat/mh-true-up-p0` in worktree `twinklr-mh-true-up`, cut from `main`
at `b498ed9` on 2026-11-13, after the display fixes (`885dba2`) merged. Tasks T3 and T4
run in their own worktrees on `feat/mh-true-up-p0-t3` and `feat/mh-true-up-p0-t4`.

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
