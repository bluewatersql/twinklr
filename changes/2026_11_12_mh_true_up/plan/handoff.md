---
type: handoff
status: complete
area: research-and-planning
change: 2026_11_12_mh_true_up
updated: 2026-11-12
---

# Handoff — Moving-head technical design and implementation plans

Status: **planning deliverable complete; all implementation remains proposed**.
Branch/worktree: `chore/knowledge-optimization`, `/Users/ondeck/work/github/twinklr`.
Source baseline: `9c55c2e72c4bfea30a5ab7ae197579e4feb74485`.
Final observed HEAD: `3629fa904c87ca104654bd54804d356f7f8e3813`.
PR/implementation commits: none created by this task.
Author/integrator: root agent; read-only research contributors: `twinklr_audit` and
`competitor_research`. Independent reviewer: `report_review`; see [review](review.md).

## Summary

The owner asked to continue the moving-head research and develop technical designs
and implementation plans for every proposed phase, in this `plan/` subfolder.
The [index](README.md) now links shared contracts and six phase plans with 31 ordered
tasks, including optional experiments. Plans identify proposed interfaces, files,
dependencies, failure semantics, compatibility, tests, commit/review checkpoints
and exit criteria. No implementation, provider calls, owner-data access, xLights
mutation, fixture trials or human acceptance were performed.

Independent review found and closed four material design issues: 8-bit encoding,
phase coverage at song edges, physical-output interference across xLights layers,
and unsafe sparse-FSEQ conversion assumptions. An exact topology normalization
example also closes an ambiguity. Approval is for planning quality, not architecture
acceptance or proof that the proposed implementation works.

## Acceptance criteria status

| Criterion | Status | Evidence |
|---|---|---|
| Technical design for P0–P5 | Complete as proposals | Six phase documents and shared architecture |
| Ordered, actionable implementation tasks | Complete | 31 tasks with source/test targets and checks |
| Additional research grounds design decisions | Complete | Pinned xLights DMX/FSEQ/converter code; current local contracts |
| Cross-phase dependency and compatibility treatment | Complete | Shared policy/IR, task map, cache and rollback rules |
| Independent review | Complete for planning quality | Review and resolution record |
| No project code changes | Satisfied | Only new documentation in this subfolder this session |
| Implementation/tests/hardware acceptance | Not part of this task | All execution checkboxes remain unchecked |

## Files changed

Created here: `README.md`, `architecture.md`, `phase-0-foundation.md`,
`phase-1-fixture-fidelity.md`, `phase-2-composition.md`, `phase-3-arrangement.md`,
`phase-4-refinement.md`, `phase-5-evaluation.md`, `review.md`, and `handoff.md`.
No existing project files modified or deleted. Parent research documents remain
unchanged. No changes to `changes/ACTIVE.md`, accepted context, schemas, templates,
tests, runtime prompts or code.

## Decisions, assumptions and source drift

- Keep legacy rendering default; propose explicit job schema 3.1 for physical mode
  and independently version planner intent. Reuse the existing segment IR/emitter.
- Encode complete physical fixture states on 20 ms frames; first transport uses
  constant DMX runs. Bound output size rather than silently lowering fidelity.
- Map calibrated physical endpoints separately from allowed operating windows.
  Initial state is explicit run input; unknown speed/optical latency is not zero.
- Use observed beat knots internally; label bounded adjacent-interval estimates at
  song edges. Long uncovered edges require explicit boundary data.
- P4 can begin after P1/P2 without P3. Physical live application is unsupported
  when complete layer/group/patch isolation cannot be established; offline delivery
  remains useful. Existing injection is not transactional.
- P5 keeps whole-file comparison and the frozen three-arm experiment unchanged.
  Its bounded rendered-frame oracle admits direct v1 or proven nonsparse conversion;
  sparse conversion needs separate proof. Source code also shows the pinned
  converter's metadata option branch checks `-f`, despite declaring `-j`.
- Arrangement caps, output budgets and authoring-study targets are explicit proposed
  values, not measurements or accepted product requirements.
- Concurrent commit `3629fa9` arrived during planning. Its diff from the source
  baseline touches audio analysis, layout parsing/choreography, display/show wiring
  and associated tests. No MH encoder/planner/fixture contract changed. Plans retain
  the inspected baseline pin; implementation must recheck shared graph/layout seams
  against its actual starting HEAD. This task did not amend that other work.
- Documentation stayed in the requested `plan/` subfolder and disregarded current
  workstreams as requested. Proposed architecture was not promoted to current truth.

## Validation

| Check run | Actual result |
|---|---|
| Inline Python audit of all plan Markdown: resolve local links/anchors, balance fences, reject completed execution checkboxes, count task headings | PASS:10 files,41 local links,5 anchors,31 tasks; no broken references or completed execution checkboxes |
| Per-file `git diff --no-index --check /dev/null FILE` for each of the10 new documents | PASS: no whitespace diagnostics; expected new-file exit1 accepted only with empty output |
| `git diff --check` | Exit0, no diagnostics |
| `git diff --exit-code` | Exit0, no tracked working-tree differences |
| `git status --short --branch` | Branch `chore/knowledge-optimization`; only untracked `changes/2026_11_12_mh_true_up/` |
| `git rev-parse HEAD` | `3629fa904c87ca104654bd54804d356f7f8e3813` |
| `git diff --stat 9c55c2e72c4bfea30a5ab7ae197579e4feb74485..HEAD` | Six files in concurrent audio/layout/display-related commit; no MH encoder/planner/fixture changes |
| Independent review and focused re-review | Approved for planning quality; all four material findings resolved; final interface amendments did not reopen findings |

Skipped deliberately: `make validate`, pytest, lint/type-check, golden regeneration,
live provider requests, xLights import/render/injection, FSEQ conversion and hardware
trials. This session wrote plans only. `make validate` is a code-mutating completion
gate requiring a clean committed owned tree; no implementation commit or such run
was requested. Every test/command in a phase plan is future work, not a passing result.

## Open items and next action

No research/planning deliverable remains open. Architecture choices and numerical
defaults remain proposals for owner review. Real fixture calibration, arrival,
settling, visual preference and edit-time benefit remain `PENDING-OWNER`.

If implementation is subsequently requested:

1. Read [shared contracts](architecture.md), [P0](phase-0-foundation.md), this handoff
   and the independent review. Recheck current source/guardrails and branch ownership.
2. Use an owned implementation branch/worktree. Begin **P0-T1**, preserving legacy
   defaults and explicit new-mode rejection until the physical path exists.
3. Follow the [task dependency map](README.md#prioritized-implementation-slices).
   Start P5's frame-evidence work once P1 frame types stabilize, rather than waiting
   until every creative feature is implemented.
4. Keep future owner-authorized experiments separately recorded. Do not infer an
   authorization or acceptance from this planning handoff or its status.

## Knowledge promotion

No accepted runtime behavior changed. The source-derived constraints are documented
with provenance in these proposed designs; promoting architecture to `context/` or
durable decisions to `memories/` waits for acceptance and the repository closeout
workflow. The parent report remains the research synthesis; this subfolder owns the
new technical designs and implementation steps.
