---
type: decision
status: accepted
created: 2026-11-17
updated: 2026-11-17
confidence: confirmed
tags: [moving-heads, rendering, owner-acceptance, single-path]
---

# Moving Heads Have One Renderer

_Owner direction of 2026-11-16 ("no backwards compat. no tech debt … only a single path
exists") and the owner's look acceptance the same day ("Look accepted, start the
cutover"), both recorded in the
[implementation brief](../../changes/2026_11_12_mh_true_up/implementation-brief.md).
Carried out on `feat/mh-true-up-p3` in commits `0ec65d47`, `079831df` and `24c22b79`;
verified there at `24c22b79`._

## Decision

The renderer that compiles templates against each fixture's `physical_profile` into
complete 20 ms DMX frames is the only moving-head renderer. The curve-based renderer, its
37 built-in templates, the `moving_heads.mode` and schema-version switches, transitions
and `template-export` were deleted, not kept beside it. The look the owner accepted on
2026-11-16 (one song, their rig, the xLights house preview) replaces the pre-clean-up
look as the moving-head reference. That render applied no planner intensity, colour,
events or cues, so the acceptance covers the templates' motion and timing, not the
absence of song intent; W4–W9 of the song-intent plan add it, each with an owner view.

## Context

Phases 1 and 2 of the moving-head true-up built the profile-based renderer as an opt-in
(`physical_v2`) beside the old curve-based one (`legacy_v1`, the default). Keeping both
meant two template formats, two render paths behind every command, and two sets of
goldens. The owner ruled for one path, to be cut over only after seeing a real-audio
render in xLights. That render
([record](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-p3-viewing-render/README.md))
was accepted the same day.

## Rationale

- A replacement removes what it replaces (shared guardrail 9): no alias, version switch
  or compatibility reading of old keys, records or saved plans.
- Removing a renderer must not change what the surviving one renders. Each cutover step
  was proved with a byte matrix against the commit before it
  ([pattern](../patterns/render-output-proof.md)).

## Consequences

- Every fixture needs a `physical_profile` and a settled initial state; a job naming a
  removed key is refused by name with what to do. What the renderer requires and
  refuses is summarized in [current state](../../context/current-state.md#implemented).
- **The cutover regressed the song intent.** The deleted renderer had an intent layer
  (intensity to dimmer, section colour to a wheel byte, shutter and gobo events, lyric
  moment cues moved onto events, section transitions, and in `twinklr show` the macro
  palette and focal role). The surviving renderer had no counterpart, and the cutover's
  proof only showed that the surviving renderer's bytes did not change. At `24c22b79`
  the renderer applies each section's template, preset and bars only.
- **The owner rejected cutting that intent** (2026-11-17, recorded in the
  [Phase 3 plan](../../changes/2026_11_12_mh_true_up/plan/phase-3-arrangement.md#2026-11-17-owner-direction--the-planners-song-intent-must-be-rendered-not-cut)):
  all of it is rendered on the single path, and a field leaves the planner contract only
  on the owner's word. The work is W0–W9 of [song-intent rendering](../../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md); the T1
  design draft that cut the unread fields is withdrawn.
- `tests/regression/test_mh_pins.py` is the moving-head output guard. Changing pinned
  output, like changing the accepted look, needs the owner first.
- Upgrades across the cutover re-keyed caches and refused old live plans
  ([learning](../learnings/model-dump-hashes-rekey-caches.md)).
- The accepted look is not a hardware result: no real fixture was driven and the
  profile timings were chosen, not measured. Nor does it accept the missing song intent:
  that render applied no planner intensity, colour, events or cues.

## Related

- [Superseded: pre-clean-up look](mh-render-matches-pre-cleanup-look.md)
- [C1.2 deletion](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-2-deletion/README.md),
  [C1.3 model narrowing](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-3-model-narrowing/README.md),
  [C1.4 renames](../../changes/2026_11_12_mh_true_up/evidence/2026-11-17-c1-4-renames/README.md)
- [Phase 3 plan](../../changes/2026_11_12_mh_true_up/plan/phase-3-arrangement.md),
  [song-intent rendering](../../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)
- [Prove behaviour parity before deleting a replaced implementation](../learnings/prove-parity-before-deleting.md)
