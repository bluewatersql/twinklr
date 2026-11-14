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

## Kickoff preparation — 2026-11-13

The owner asked for the plan to be updated with documentation and test obligations and
for any other gap to be closed before kickoff, and stated that the change will start
from `main` in a clean worktree once the display fixes on
`fix/display-brightness-floor` are complete. Plan documents only; no project code,
test, schema or published documentation was changed. Edits were made in worktree
`twinklr-mh-true-up-prep` on branch `docs/mh-true-up-kickoff-prep`, cut from `main` at
`f067a56`.

Source drift: between the plan's pin `9c55c2e` and `f067a56`, no file under
`packages/twinklr/core/config/models.py`, `sequencer/moving_heads/` or
`agents/sequencer/moving_heads/` changed. The display-fix branch was not inspected;
the kickoff checklist in the [implementation brief](../implementation-brief.md) repeats
the diff against the real starting commit.

What changed:

- New [implementation brief](../implementation-brief.md): scope, Phase 0 acceptance
  criteria, approvals still pending, and the kickoff checklist. Added a row to
  `changes/ACTIVE.md`.
- [README](README.md#documentation-registry-and-test-surfaces): a shared rule and a
  table of the repository guards that bind code to documentation and to the
  config-field inventory.
- [P0](phase-0-foundation.md):
  - T1 now owns the inventory-registry records for `job.schema_version` and the new
    `job.moving_heads` paths, the reworded fixed-policy test, and corrections to
    `docs/user-guide.md`, `docs/overview.md` and `docs/pipeline_guide.md`, which state
    the schema version as fixed at 3.0. It names the rejection site, the exception
    type and a stage-level failure test.
  - T2 adds a `control` discriminator to `MHDiagnostic` (all five P0 diagnostics share
    one code), maps each control to its source and the existing test that pins it,
    names where the grid and version-stamp constants come from, puts the plan's
    non-serialized but functional omitted-intent flag into the identity, and states
    how the pipeline exposes both results without touching sidecars.
  - T3 records which cases run through the legacy pipeline and which are input-only,
    how input-only data is held without P1 types, and that a legacy
    `UnsupportedRigShapeError` for a head count is a baseline outcome.
  - T4 gives the reference arm a complete resolution order and builds sections
    through the selector's existing private builder, so the selector file is not edited.
  - A file-ownership table, and an exit that names the evidence record's path and
    contents.
- P1–P5: a closing section each, listing the registry, guard-test and documentation
  surfaces known today. Two are design gaps rather than bookkeeping: P1.1 must decide
  how physical-only fixture/template fields are evidenced in the inventory, and P2.4
  must define how `physical_v2/` catalog documents are admitted without reaching the
  legacy planner, selector or registry-count tests.

Independent review of these amendments (separate agent, read-only, given the diff and
acceptance criteria): changes requested, then all thirteen findings applied. Five were
factual or coverage errors: the fine-channel control row misdescribed what the builder
emits, the omitted-intent flag was left open though the source shows it is functional,
the 8-head golden was misdescribed, `docs/pipeline_guide.md` was missing from T1, and
the `fine_carry` case could not be built from the harness rig type. The rest tightened
predicates, the reference arm's resolution order, a run command, and the P2 and P5
notes. The reviewer verified the remaining repository claims against source and ran
no tests. The corrections were not re-reviewed.

Checks run on the amended documents: local links and anchors resolve, code fences
balance, 31 task headings remain, `git diff --check` is clean. No test suite or
`make validate` was run; nothing outside `changes/` was edited.

Decision left with the owner: the brief keeps `identity.py` in Phase 0 because the
Phase 0 evidence record consumes it. The go-ahead to begin Phase 0 is still pending.

## Phase 0 implementation — 2026-11-13

Status: **Phase 0 complete on `feat/mh-true-up-p0`; not merged to `main`.** Worktree
`twinklr-mh-true-up`, cut from `main` at `b498ed9`. The owner's go-ahead covered Phase 0
only; Phase 1 needs its own.

Delivered, each implemented test-first by one agent and reviewed by a separate one:

| Task | Commit | Result |
|---|---|---|
| P0-T1 render policy | `4c608ac` | `JobConfig.moving_heads.mode`, schema `3.0 \| 3.1`, `physical_v2` rejected before any output; inventory records and three documents updated |
| P0-T2 diagnostics and identity | `1631679` | `audit_legacy_controls`, `render_fingerprint`, lazy pipeline accessors |
| P0-T3 synthetic cases | `afbe160` | Eight in-memory cases under `tests/support/` |
| P0-T4 reference arm | `2617525` | `build_reference_plan`; the frozen selector file is untouched |

Validation: `make validate` on `1631679` passed, 5882 passed and 39 skipped, tree clean
before and after; no golden or regression file changed. Evidence:
[evidence/2026-11-13-p0-baseline](../evidence/2026-11-13-p0-baseline/README.md). The
handoff and evidence documents were committed after that gate run and are
documentation only.

Changes to the plan made during implementation, all recorded in
[phase-0-foundation.md](phase-0-foundation.md):

- The fingerprint takes transition settings as a required input and ignores
  template-id spelling. Review showed transitions change emitted segments and were
  missing from the specified signature.
- Control predicates corrected against source: movement intensity can be requested by
  the template itself and exempts hold-only steps; calibrated limits are reported per
  fixture; the dimmer-floor diagnostic states a range, not a reached value; the shutter
  diagnostic covers only targeted fixtures.
- `render()` resolves a section's preset through `resolve_section_preset`, a verbatim
  move shared with the audit. This is the only edit to the default render path.
- Channels 48 and 49 are plain integers in the synthetic cases.

Open items:

- **Owner: merge `feat/mh-true-up-p0` to `main`.** Not done; no instruction to merge.
- **Owner: merge `fix/install-anthropic-extra` (`6e9a8cb`).** `make install` and CI
  omit the `anthropic` extra, so the gate fails at collection in a fresh environment.
  The fix passed `make validate` in its own worktree (5763 passed, 39 skipped).
- **Owner decision:** a `physical_v2` job passes config validation and is rejected at
  render, after planning has run. Rejecting at job load until Phase 1 would avoid the
  wasted provider spend.
- **Phase 1:** `reporting/evaluation/rerender.py` always renders `legacy_v1`; the
  P1.2 phase map must not build from `BeatGrid.extended_to_duration()`. Both are in the
  P1 plan.
- Low review notes left as is: `render_fingerprint` requires the plan's templates to be
  registered; the audit calls one private dimmer-handler method; test-support typing
  is loose.

Knowledge promotion: checked. Phase 0 changes no accepted behavior beyond the three
documents T1 corrected, so nothing is promoted to `context/` or `memories/`.

Next action: owner go-ahead for Phase 1, then its kickoff recheck.

## Phase 1 implementation — 2026-11-14

Status: **Phase 1 complete on `feat/mh-true-up-p1`; not merged to `main`, not pushed.**
Worktree `twinklr-mh-true-up`, cut from `main` at `bb78227`. The owner's go-ahead covered
Phase 1 only; Phase 2 needs its own.

Delivered: an opt-in `physical_v2` moving-head renderer (job schema `3.1`). A physical
job compiles against an exact musical phase map, plans dark reposition transactions,
encodes complete fixture frames on a 20 ms grid and delivers an `.xsq` whose trace
carries the render identity. Default `legacy_v1` output is byte-identical. Tasks,
commits and review rounds are in the
[exit evidence](../evidence/2026-11-14-p1-exit/README.md); decisions made during
execution are in
[phase-1-fixture-fidelity.md](phase-1-fixture-fidelity.md#decisions-and-carry-forwards-recorded-during-execution).

Validation: `make validate` on `b4ed49d0` passed, 6355 passed and 39 skipped, tree clean
before and after; no golden or regression file changed. The closeout documents were
committed after that gate run and are documentation only.

Owner decisions taken during the phase: reject an unrenderable physical job before
planning (P1.0, later generalized); live provider calls authorized (none made);
`twinklr run` gains `--layout`; silent song edges deferred to Phase 2.

Open items:

- **Owner: merge `feat/mh-true-up-p1` to `main`, and push.** Not done; no instruction.
  `main` is also still ahead of `origin/main` from the Phase 0 merge.
- **Owner: xLights render on an expendable show.** The
  [request](../evidence/2026-11-13-p1-xlights-request/README.md) lists the profiles, the
  command and the frames to check. Outcome `PENDING-OWNER`.
- **Owner: hardware accuracy and changed-look acceptance.** `PENDING-OWNER`.
- **Owner, no objection recorded:** the default `max_effects` is 1,000,000, raised from
  the planned 100,000 by the integrator.
- **Phase 2 carries:** a policy for silent song edges (physical mode refuses most real
  audio until then); physical template families (no production template is physical);
  gate dry-compile cost at catalog size; binding planner intensity; reposition
  fallbacks selectable from config; a producer for `locks`.
- **Low, left as is:** a lit cue at time zero that needs a move fails with a misleading
  reason; a cue with an unauthored dimmer whose default byte is dark is treated as lit;
  any `Dmx*` model passes the layout check; emission's overlap scan is quadratic in
  effect count and unmeasured on long shows.

Knowledge promotion: `context/current-state.md` now names the opt-in physical path and
its limits. No decision is promoted to `memories/`: the physical path has no empirical
acceptance yet, and its design decisions live in the phase plan until it does.

Next action: owner go-ahead for the merge, the xLights test, and Phase 2.
