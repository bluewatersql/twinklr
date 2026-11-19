---
type: handoff
status: active
area: research-and-planning
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Handoff — Moving-head technical design and implementation plans

## Start here — current state, 2026-11-19

The [recovered whole-song review](../evidence/2026-11-19-combined-review/recovery-review.md)
continues the session that failed with the chat API's audio-input error. It found
and repaired a display foundation that waited for the opening downbeat, and records
the independent code review and the xLights preview-size export correction.
The replacement artifacts are under
`~/xlights/_twinklr_verify/recovery-review-2026-11-19/`.
The full gate on `a1326e31` passed with 7,798 tests, 30 skips and 91% coverage.
All 29,842 final video frames were scanned; 588 audio comparisons measured
zero offset, and no audible dark interval lasting at least one second remained.
Implementation and evidence are integrated on `main`.
Human look acceptance and physical verification remain open.

Phase 3 was fast-forwarded to `main` and pushed to GitHub on 2026-11-19 at
`8b8075c7` on owner approval. The owner also approved the saved-plan fixture preview
and one fresh paid planner run. The single renderer
cutover and W0–W10 restore the planner's song intent through palette, colour and gobo,
intensity, transitions, beat and lyric events, variation, density and per-part modifiers.
The merged renderer revision is 22. See [current state](../../../context/current-state.md)
for the implemented behavior and the [owner decision list](owner-decisions-pending.md)
for open choices.

| Work | Commit | Evidence |
|---|---|---|
| Arrangement first tries all planned units, and protects the first flash | `2a1272fa`, `cd13034a` | [W10b/c](../evidence/2026-11-18-w10bc-motif-variation/README.md) |
| Density recovered and integrated | `763ae663`, `ca0f2683` | [W10d](../evidence/2026-11-18-w10d-density/README.md) |
| Modifiers recovered and integrated | `4a0dfaca`, `d08ef508` | [W10e](../evidence/2026-11-18-w10e-modifiers/README.md) |

The [interruption assessment](capacity-recovery-2026-11-18.md) records how Claude stopped.
The [integration evidence](../evidence/2026-11-18-p3-recovery/README.md) records the recovered
code, independent reviews, verification and viewing output. Both side worktrees are clean.
Temporary backups preserved the pre-recovery worktree contents and indexes.

### What remains, in order

1. The approved fresh paid `twinklr run` completed 7/7 stages and rendered ten
   planner-requested modifiers. The [live evidence](../evidence/2026-11-19-p3-final-live/README.md)
   records the finished sequence and the dark song tail. Fresh output look review
   remains open.
2. The [owner decision list](owner-decisions-pending.md) retains the individual look and
   product decisions that the saved-plan fixture preview did not exercise.
3. Early entry repositioning, which could let a variation and the next section's downbeat
   hit coexist. Today the variation gives way. See D1 in the [W10b/c record](../evidence/2026-11-18-w10bc-motif-variation/README.md).
4. Decide how to park a head that cannot go dark after its final cue. The renderer
   refuses that case today.
5. Arrangement render cost when units give way. The common path tries all units in
   one pass and the fallback tries individual choices in plan order. A possible
   improvement is trying plan-order prefixes, followed by the existing retry pass.
   That can change which arrangement wins a tie and needs its own behavior checks.
6. Owner judgment on SPARSE's hard-cut swaps, BUSY's accents, the modifier looks,
   calibrated hardware, and the rest of the [owner decision list](owner-decisions-pending.md).
7. Provider acceptance of the OpenAI planner schema, real xLights `inject`/`regenerate`
   on an approved scratch sequence, and physical fixture verification remain open.
8. Earlier carries remain open: three songs at 147.7 BPM, the three-arm experiment and
   Phase 5, four other Claude schemas that lack server-side enforcement, and audio
   beyond the beat grid. Planner caches re-key and `regenerate` refuses sequences
   injected before the cutover. See [cache learning](../../../memories/learnings/model-dump-hashes-rekey-caches.md).
9. The [three-song combined run and workspace cleanup](combined-review-2026-11-19.md)
   produced three previews. The owner rejected them for long dark stretches, poor
   sync, and missed transitions. The
   [Dance Jams quality audit](../evidence/2026-11-19-combined-review/dance-jams-quality-audit.md)
   reproduces the 35-second coordination blackout and records the missed cues.
   The [replacement run](../evidence/2026-11-19-combined-review/repaired-previews.md)
   verifies the repaired scheduling, four Dance Jams cues, and the three new
   previews. Owner look review and physical verification remain open.

### Commits since the C1.5 documents

The table covers code and record commits. It continues the
[cutover table](#commits-on-the-branch-through-c15) further down.

| Work | Commits | Record |
|---|---|---|
| Do not merge before song intent; plan revised | `7c31919d` | [song-intent rendering](song-intent-rendering.md), [gap inventory](../evidence/2026-11-17-song-intent-gap-inventory/README.md) |
| W0 intent-parity harness | `af504809` | [record](../evidence/2026-11-17-w0-intent-parity/README.md) |
| W1 profile tags | `10f3ac49` | [record](../evidence/2026-11-17-w1-profile-tags/README.md) |
| W2 planner contract (Claude compiles; three live probes) | `1f953f96`, `85595b98`, `5c2a20d8`, `2cdb19e8`, `897c4501`, `89e4208d`, `f9e348da`, `9deb95df` | [record](../evidence/2026-11-17-w2-planner-contract/README.md) |
| W3/W4 rig offer, section colour and gobo | `e611164f`, `cbf4a684`, `f0e2cff6` | [record](../evidence/2026-11-17-w3-w4-offer-colour/README.md) |
| W5 intensity, focal role (W9 half) | `9d607f45`, `7c6c2b08` | [record](../evidence/2026-11-17-w5-intensity/README.md) |
| W6/W7 events and lyric cues; intensity re-review | `c0ee6a40`, `0e02e969` | [record](../evidence/2026-11-17-w6-w7-events/README.md) |
| W8 transitions | `82bd2b0a`, `3115b545`, `fd85b8db`, `1eca8998` | [record](../evidence/2026-11-17-w8-transitions/README.md) |
| W10a wide and fast variants | `d1125419` | [record](../evidence/2026-11-17-w10a-variants/README.md) |
| W10b/c motif and variation | `5b708b26` | [record](../evidence/2026-11-18-w10bc-motif-variation/README.md), [plan](w10-arrangement.md) |
| Motif steps from its introducer | `e922bc52` | same record |
| Gate on rigs whose allowed range is narrower than physical | `2c961b58` | same record |
| Variants fitted to the rig | `5825ff0a` | same record |
| Fitted variant keeps its period; colour shown long enough | `bcefff0f` | same record |
| The song outranks the arrangement (blame; superseded) | `08c50a92` | same record |
| Arrangement built up from the reference; move rules only improve | `f9894cc8` | same record, "revised (after 08c50a92)" |
| Every candidate tried (a FASTER the rig does not admit plays its narrower reach); strobe, pulse and `closed` judged over their whole span | `934b2635` | same record, "Review fixes (after f9894cc8)" |
| W10d density | `763ae663`, `ca0f2683` | [record](../evidence/2026-11-18-w10d-density/README.md) |
| W10e modifiers | `4a0dfaca`, `d08ef508` | [record](../evidence/2026-11-18-w10e-modifiers/README.md) |

### How to validate and review

- **Validation runs in its own worktree.** The integrator checks out a commit there in a
  detached HEAD (`twinklr-mh-validate*`) and runs `make validate`. Implementing agents
  never run it in their own tree. `make validate` rewrites files and needs a clean tree;
  see the [operating model](../../../context/agents/operating-model.md).
- **Reviewers work on a `git archive` of the commit under review,** extracted into a
  scratch folder. To compare with an earlier commit, archive that commit as well. Each
  reviewer writes measurement scripts and hands them over. The authoring agent reruns
  them on its fix, and the next reviewer reruns them again.
- **The measures that settled each round:**
  - an event-level before/after comparison of the same plans on two trees: which head
    plays each event, and when;
  - seeded fuzz plans on several rigs and grids, including slow heads (150°/s), narrowed
    allowed ranges, 3/4 and fast tempos;
  - for the arrangement, `worse(reference, render)` over every event, transition and head.
- **Owner-rig renders.** This is a method; its paths are session-local and are not
  recorded here.
  1. Render the owner's song from its saved plan (`final.json`, read in place) with the
     owner-rig fixture and job configs (owner-local, authorized for this change).
  2. Gate offline with no provider call.
  3. Write the sequence into an expendable xLights show under `~/xlights/_twinklr_verify/`,
     never the owner's show.
  4. Check that xLights reproduces the bytes.
  5. Export the house-preview video for the owner.

  The [P3 viewing render](../evidence/2026-11-16-p3-viewing-render/README.md) is the worked
  example. The owner's rig profile timings are chosen, not measured.

### Lessons that cost time

These lessons are promoted to `memories/` (see below).

- **Unrealistic test rigs hid defects.** The synthetic rigs' allowed ranges equalled their
  physical ranges, so the gate crashed on the owner's rig (`2c961b58`). The fast,
  symmetric heads hid every defect that needs slow heads: losses at variant entry,
  fitted variants, events lost to dark entries. Test every new mechanism on
  `tests.support.moving_heads.allowed_rig` with heads at about 150°/s.
- **Owner-rig renders found what the tests did not.** Examples: the lost downbeat hit,
  lyric hits moved before their lyrics, and chorus_2 giving up its variation for nothing.
  Plan for a render of the owner's song after each feature.
- **Judge a rule change by comparing events before and after,** on the same plans across
  two trees. Unchanged pins or green tests did not show that a move rule lost events
  (seeds 4, 688, 810, 216) or that blame was misattributed.

### Commits on the branch through C1.5

Code and record commits from `main` through C1.5. The handoff-only commits `6caf7cba`
and `462ad93e` are left out.

| Work | Commits | Record |
|---|---|---|
| Gate-time cut | `3113d062`, `512ae0cc` | [plan](phase-3-arrangement.md#gate-time-cut--2026-11-16-commits-3113d062-and-the-test-follow-up) |
| Cutover inventory and owner decisions | `f476bb2b`, `a8d621d9`, `4fd507e9`, `b0942c0b` | [inventory](cutover-inventory.md) |
| Per-preset admission (D9) | `647eed83` | plan |
| Beat-grid fix | `5145fb3d`, `8b23a36d`, `16b3e170`, `3431c7ba`, `9e956fd7` | [record](../evidence/2026-11-16-p3-beat-grid-fix/README.md) |
| Family adaptation; profile defaults (C1.0) | `068f9971`, `dcc14ddf`, `d2f49251` | plan |
| Viewing render; look accepted | `824dce1d`, `b5cbc658` | [record](../evidence/2026-11-16-p3-viewing-render/README.md) |
| Claude schema decided before sending | `10dbd93f` | viewing-render record, follow-up |
| C1.1d selector and three-arm port | `c1f3023e`, `1f74d63f`, `fd087908` | [record](../evidence/2026-11-16-c1-1d-selector-port/README.md) |
| C1.1c live `inject`/`regenerate` | `19f0a9c2` | [record](../evidence/2026-11-16-c1-1c-live-port/README.md) |
| C1.1b `eval-report` | `12e9f83a` | [record](../evidence/2026-11-16-c1-1b-eval-port/README.md) |
| C1.1a `twinklr show` | `6fe8b0ba`, `5d50580c` | [record](../evidence/2026-11-16-c1-1a-show-port/README.md) |
| C1.2 old renderer deleted | `0ec65d47` (tag `mh-last-with-legacy-renderer` = `5d50580c`, local) | [record](../evidence/2026-11-16-c1-2-deletion/README.md) |
| C1.3 shared models narrowed | `079831df` | [record](../evidence/2026-11-16-c1-3-model-narrowing/README.md) |
| C1.4 names of the second path removed | `24c22b79` | [record](../evidence/2026-11-17-c1-4-renames/README.md) |
| C1.5 documents, context, memories, scripts | `9e7205cf`; reviewed (changes requested), corrections in a follow-up commit | [record](../evidence/2026-11-17-c1-5-docs-context/README.md) |

## Planning handoff — 2026-11-12

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

## After Phase 1 — 2026-11-14

- Phase 1 merged to `main` as `52191b15` and pushed, on owner direction. `make validate`
  on the merged tree: 6355 passed, 39 skipped.
- xLights transport test run on owner authorization: xLights 2026.19 reproduced every
  encoded byte ([result](../evidence/2026-11-14-p1-xlights-result/README.md)). It found
  that xLights writes a DMX model's channel count as `DmxChannelCount`, not `parm1`, so
  `twinklr run --layout` refused every real model. Fixed on
  `fix/mh-layout-dmx-channel-count`, reviewed separately; the layout profiler's DMX
  channel count had the same defect and is fixed with it.
- Owner approved the 1,000,000-effect default and gave the go-ahead for Phase 2.
- Still `PENDING-OWNER`: hardware accuracy, look acceptance, xLights UI behaviour and
  scale near the effect budget.
- Noted, not fixed: `ModelProfile.channel_count` in the layout profiler infers from
  `parm1 × parm2` and misreports a DMX model that has no `parm1`; it feeds the profiling
  report only.

Next action: Phase 2 kickoff recheck, then P2 tasks.

## Phase 2 implementation — 2026-11-16

Status: **Phase 2 complete on `feat/mh-true-up-p2` and merged to `main` on owner
direction of 2026-11-16.** Phase 3 needs its own go-ahead.

Delivered, all opt-in under `physical_v2`: silent song edges held dark; named position
and attribute presets; rig topology with independent phase domains; relative paths and
finite (`ONCE`) motion; visibility windows and masked wheel overlays; per-fixture
section-entry repositioning with declared fallbacks; a pre-planning gate that offers
only templates the rig can render; seven physical families in
`catalog/templates/moving_heads_physical/` (six plus the `zoom_wave` pilot); a zoom
axis with a DMX subrange. Default `legacy_v1` output is byte-identical. Tasks, commits
and review rounds are in the
[exit evidence](../evidence/2026-11-16-p2-exit/README.md); decisions are in
[phase-2-composition.md](phase-2-composition.md#decisions-and-carry-forwards-recorded-during-execution).

Validation: `make validate` on `9d0fb9ce` passed, 6800 passed and 39 skipped, tree
clean before and after; no golden or regression file changed. The closeout documents
were committed after that run and are documentation only.

xLights: the six families were rendered on a scratch show on owner authorization;
xLights 2026.20 reproduced all 376,384 bytes and a house-preview video was exported
([result](../evidence/2026-11-16-p2-xlights-result/README.md)).

Integrator decisions the owner has not confirmed (listed in the exit evidence):
`on_unplayable` defaults to `"dark"`; an unknown entry bound fails any template;
families are 4/4 only; the gate-time target was missed and carried forward.

Open items:

- **Owner: look acceptance** of the families, section-entry dips, dark song edges and
  dark-dropped cues. `PENDING-OWNER`. The preview video is at
  `~/xlights/_twinklr_verify/p2_show/out/`.
- **Owner: hardware accuracy,** and the zoom pilot on a real fixture profile
  (`zoom_pilot_profile_payload` is the 16-channel synthetic starting point).
  `PENDING-OWNER`.
- **Gate time:** 36–62 s before planning on 8 heads against a 20 s target. Known safe
  cut: cache path and phase values for periodic kernels. Do this before Phase 3 adds
  variants to the gate.
- **Phase 3 carries:** binding planner intensity to family variants (P3-T3);
  per-preset eligibility (P3-T2); render feasibility in planner validation (P3-T3).
- **Not yet exercised:** a full `twinklr run` with a live planner on the physical
  path, and any real-audio beat grid.

Knowledge promotion: `context/current-state.md` now describes the physical path as it
stands. No decision is promoted to `memories/`: the path still has no hardware or look
acceptance.

Next action: owner review of the preview video and the integrator decisions, then a
go-ahead for Phase 3.


## Phase 3 in progress — 2026-11-16

Status: **Phase 3 started on `feat/mh-true-up-p3` (cut from `main` at `7356b376`); not
merged.** The plan of record is [phase-3-arrangement.md](phase-3-arrangement.md): its
original text is superseded where its dated amendments say so. Read the amendments
first.

What changed the phase's shape, all owner decisions of 2026-11-16:

- **Single path.** No backward-compatibility layers; the physical renderer becomes the
  only moving-head path ([guardrail 9](../../shared/agent_guardrails.md)). The old
  renderer is deleted only after the owner views a real-audio physical render and
  accepts it. The inventory for that cutover is
  [cutover-inventory.md](cutover-inventory.md).
- **Robustness first.** The first real-audio gate on the owner's rig admitted one
  family of seven ([evidence](../evidence/2026-11-16-p3-real-audio-gate/README.md)), so
  the beat grid and family adaptation are fixed before any viewing.
- Targets cut from Phase 3; density simplified; the deterministic selector and the
  three-arm experiment are ported at the cutover, not kept beside a new one;
  `regenerate` re-renders the whole song; profile fields get defaults.

Done and committed on the branch:

| Work | Commits | State |
|---|---|---|
| Gate-time cut (57 s → 17 s in 4/4, output identical) | `3113d062`, `512ae0cc` | Reviewed twice; `make validate` passed on `3113d062` |
| Per-preset admission (D9) | `647eed83` | Reviewed; `make validate` passed |
| Beat-grid fix (meter, tempo octave, downbeats) | `5145fb3d`, `8b23a36d`, `16b3e170`, `3431c7ba` | Reviewed twice and verified; [record](../evidence/2026-11-16-p3-beat-grid-fix/README.md); full gate not yet run on the branch with it |

In progress when this was written (uncommitted or on side branches):

- **Family adaptation** (variant ladder, whole-period cycles, renderer revision 2), in
  the worktree, under its review fix round: gate time outside 4/4, the render
  fingerprint, entry-dip fixpoint, tests and docs.
- **Profile defaults (C1.0)** on `feat/mh-profile-defaults` in an agent worktree.

Next actions, in order:

1. Land the family adaptation (re-review, commit), cherry-pick profile defaults after
   review, run `make validate` on the branch.
2. Rerun the offline gate for Need A Favor on the corrected grid with the owner rig
   at 150°/s.
3. Viewing render and old-renderer reference on the corrected grid, in the expendable
   show `~/xlights/_twinklr_verify/p3_view/`, with a side-by-side preview video. Inputs
   and limits are in the brief's approvals table. The look verdict is `PENDING-OWNER`.
4. After acceptance only: the cutover (C1), then the planner tasks T1–T5 with one
   contract.

Open for the owner: bar placement by ear on their songs; the three songs left at
147.7 BPM; whether to keep a tempo-change detector (removed as unused); the integrator
decisions listed in the Phase 3 plan.

### Update, later on 2026-11-16

Everything listed as in progress above is committed on `feat/mh-true-up-p3`: the family
adaptation (`068f9971`), profile defaults (`dcc14ddf`), with `make validate` passing on
`dcc14ddf` (7048 passed, 39 skipped) and old-renderer output verified byte-identical.
The viewing render and the old-renderer reference for Need A Favor exist
([record](../evidence/2026-11-16-p3-viewing-render/README.md)); xLights reproduced
every physical byte.

**The change is now waiting on the owner:** look acceptance of the physical render
(`PENDING-OWNER`). Until it is given, nothing is deleted from the old renderer and the
planner tasks T1–T5 do not start. The branch is not merged or pushed.

Next action after acceptance: the cutover, in the order
[cutover-inventory.md](cutover-inventory.md) gives. Work that could proceed without
it: the four findings in the viewing-render record (the provider rejecting the plan
schema is the one with a cost).

## Cutover — 2026-11-16 to 2026-11-17

The owner accepted the look on 2026-11-16 and the cutover ran in five steps: the four
consumer ports (C1.1), the deletion of the old renderer (C1.2), the model narrowing
(C1.3), the renames (C1.4), and documents, context, memories and scripts (C1.5).
C1.1–C1.4 were each written by one agent and reviewed by another. C1.5 was committed as
`9e7205cf` and reviewed by a separate agent (changes requested); the corrections are in a
follow-up commit. Byte matrices against the commit before each of
C1.2–C1.4 found no change to frames or delivered files. The commits, records, validation,
owner-gated items and open questions are in "Start here" at the top of this file.

Knowledge promotion (C1.5): `context/` describes the one renderer; the decision
[mh-single-renderer](../../../memories/decisions/mh-single-renderer.md) supersedes
[mh-render-matches-pre-cleanup-look](../../../memories/decisions/mh-render-matches-pre-cleanup-look.md);
one pattern and one learning were added
([record](../evidence/2026-11-17-c1-5-docs-context/README.md)).
