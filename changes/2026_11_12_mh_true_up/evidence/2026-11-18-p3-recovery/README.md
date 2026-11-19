---
type: handoff
status: active
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-18
---

# Phase 3 recovery and integration

`feat/mh-true-up-p3` now has density and modifiers at renderer revision 22.
The reviewed implementation is `d08ef508`. It integrates the recovered density merge
`763ae663` and modifier merge `4a0dfaca`. The archive of their interrupted state lives
in two local temporary recovery folders. The side worktrees are both clean.
The [interruption assessment](../../plan/capacity-recovery-2026-11-18.md) records
what was present before the recovery.

The combined renderer tests its batch of planned arrangement choices against both
the song events and the modifier cue-drop guard. It registers modifiers from the
template's offered values before choosing a variant, so a modifier can play when
the chosen fallback permits it. Repair reads modifier-aware phases when predicting
SPARSE density. The obsolete unrendered-intent diagnostic in `sequencer/moving_heads/pipeline.py`
was removed now that every planner intent field has a render path. Existing frame
and sequence hashes are unchanged on the pinned plans. The revision bump updates
their fingerprints.

## Independent review

| Review | Verdict | Coverage |
|---|---|---|
| Density at `763ae663` | Approved | 15 focused tests passed. Verified REST hits, SPARSE protection, BUSY transition status, shared optimistic arrangement path, and all 133 pin entries plus the combined golden aside from fingerprints. |
| Modifiers at `4a0dfaca` and `d08ef508` | Approved at `d08ef508` | Seven branch tests passed. Confirmed the optimistic guard and reproduced the variant fallback omission at `4a0dfaca`. Verified the modifier plays on `d08ef508` after the variation yields. A strict-error synthetic sweep at `4a0dfaca` found no modifier-only exception across four tempos. |

Both reviews were by agents independent of the integration author. The modifier
reviewer also approved the regression test and the transition test change that
renders each mode once while preserving the frame comparisons.

## Validation

- Regression, golden and rendering-stage suites: 190 passed, 1 skipped.
- The modifier fallback regression passed independently.
- The revised transition test passed independently in 1.62 s without coverage.
  It uses the same frame indices and pairwise assertions and renders once per mode.
- Focused combined suites: 355 passed. These covered density, modifiers, arrangement,
  rig repair, the rendering pipeline and evaluation reporting.
- Full `make validate` on `d08ef508`: format, lint and mypy passed. Pytest
  reported 7,785 passed and 30 skipped in 3704.49s (1:01:44). The validation
  worktree stayed clean. Both later test changes and the documentation were checked
  separately. The gate reported 91% coverage.
- Independent combined arrangement sweep: 16 deterministic plans across the plain rig
  and a narrowed 150°/s rig. Neither sweep found a worse song event or transition
  against its reference.
- Compared 137 pin records, including the individual pins and full combined golden,
  against both parents. All frame and sequence hashes were identical.

## Offline replay and xLights

Replayed the previously authorized saved Need A Favor plan and its cached macro,
audio profile and lyric context on `d08ef508` in an expendable show. Lyric cue
binding was rerun. Network requests were disabled for the replay. The saved plan
requests SPARSE on the intro and BUSY on chorus 1, break and chorus 2, plus motif
variation. The trace shows the intro crossfade playing on all four heads and records
seven lyric cues. The saved plan requests no modifiers.

- Twinklr emitted 9,870 frames per head at 20 ms and an XSQ with SHA-256
  `370f3f49fcb5227160b12d4e75f2ce3f20f275eba480993a7b47a75c2518055e`
  before relinking its media path inside the scratch show. The render stage took
  35.16 s during concurrent validation and executed 19 pipeline passes.
- xLights 2026.20 rendered the scratch XSQ to FSEQ in headless mode. The comparison checked
  631,680 bytes, with zero mismatches and zero frames beyond the FSEQ.
- Both owner show layout and network files passed their before/after SHA-256 check.
- House preview export stalled while backing up application preferences and was
  stopped before launching the GUI. A local synchronized fixture preview from
  the byte-verified frames shows pan, tilt, dimmer and wheel color with the song.
  It is H.264/AAC at 960 by 480, 50 fps and 197.4 seconds. The file is
  `~/xlights/_twinklr_verify/p4_view/phase3_recovered.pwGxi9DO/phase3_need_a_favor_fixture_preview.mp4`.

The owner approved the fixture preview and authorized the Phase 3 merge, push
and one fresh paid planner attempt on 2026-11-19. The preview covers the saved plan
and fixture output. Modifier look, hardware and live xLights injection and
regeneration remain open.
