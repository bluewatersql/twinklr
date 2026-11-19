---
type: plan
status: active
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Three-song combined review and cleanup

The owner asked for a synced `main`, removal of retired workspaces and generated
debug artifacts, and a combined house and moving-head sequence and preview for
each of the three test songs. Authorization is in the
[implementation brief](../implementation-brief.md#approvals).

## Run scope

Run `twinklr show` against the released Phase 3 implementation at `9309142b`
using Claude Opus 5.5 and the four-head fixture config used in the final Phase 3
run. Use distinct sessions for Need A Favor, Dance Jams Final Audio, and Hey Come
Look At My House. Need A Favor and Dance Jams are named in current test evidence.
Hey Come Look At My House is the inferred third because it has an earlier house
preview. Keep deliverables and inputs in a local scratch show.

The owner layout has seven aliases that also claim moving-head channels. Its
combined preflight rejected those overlapping owners before using a provider.
The scratch copy removes those seven aliases and retains the fixture group
`90 - Moving Heads` as sole owner of its four physical models. Keep all display
models. Verify the source layout and network files still match their starting
hashes.

A song is complete when the coordinated sequence parses, contains effects for
the house and the four-head rig, and yields a playable house MP4 with audio from
the scratch xLights instance. Record any planner or renderer limitation. A
preview is a review artifact and does not constitute a hardware result or look
verdict. No live fixture output is in scope.

## Live replay correction

Need A Favor returned 15 unique narrative asset directives across successful
section plans. The song-level model accepts at most four, and aggregation
passed all 15 through. Keep the established four-asset budget and first-seen
order after deduplication. Preserve all section plans and references to retained
assets. Share the model's limit with aggregation and extraction. Reproduce with
a stage-level test, then retry from the existing planning caches.

## Cleanup

Verify worktrees for tracked changes and untracked files before removing them.
Five feature or validation worktrees and six old Claude worktrees are retired.
The corresponding work shipped on `main`. Six original tips have different
commit IDs from their integrated copies, so their exact histories are retained
under `refs/archive/twinklr-cleanup-2026-11-19/`. Retired worktree files and
obsolete generated artifacts go to Trash. Keep tracked regression fixtures,
owner media and corpora, reusable configs and assets, and the new deliveries.

## Outcome

All three combined sequences rendered in xLights and produced decodable previews
with audio. The [dated run record](../evidence/2026-11-19-combined-review/README.md)
lists the outputs, the scratch coordination corrections, and the validation gate.
The subsequent owner review rejected the results. The
[Dance Jams quality audit](../evidence/2026-11-19-combined-review/dance-jams-quality-audit.md)
records the reproduced coordination blackout, dropped transition cues, and recovery checks.

## Repair

The owner requested a fix. Use Dance Jams to reproduce and verify the repair
before generating new previews for the other two songs. Work on the combined
coordination schedule first. Sequence or ripple the named LEAD and SUPPORT
groups, retain the other groups as a steady bed at their assigned brightness,
and preserve display foundation effects beneath the step pattern. Keep explicit
call/response windows and fixture safety rules. Do not add another rendering path.
Keep zone and split targets together as teams. Share steps for short sections
and overlap half a beat for ripple so two teams still trade prominence.

Confirm a named group and the moving heads still get scheduled on a graph longer
than the music section, and verify that named accents still rotate on actual
beat boundaries. Inspect the previously missed Dance Jams cues in the revised
trace and preview. Verify the preview's audio against the original soundtrack.
The earlier approvals cover the three source tracks, live replanning, and xLights
exports from the expendable layout. Preserve the failed runs as evidence and keep
real fixture output disabled.

The [repair record](../evidence/2026-11-19-combined-review/repaired-previews.md)
identifies all three replacement previews, the Dance Jams cue checks, and the
recorded scratch edits. The owner look review remains open.
