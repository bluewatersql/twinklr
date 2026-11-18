---
type: learning
status: active
created: 2026-11-18
updated: 2026-11-18
confidence: confirmed
tags: [moving-heads, testing, verification]
---

# Moving-head defects hide on idealized test rigs

Building the moving-head renderer on `feat/mh-true-up-p3`, between 2026-11-17 and
2026-11-18, cost three rounds of rework. Each round was caught by a realistic render or a
before/after comparison, not by the test suite.

- **Allowed range equal to physical hides gate defects.** Every synthetic rig allowed the
  full physical range, so the gate crashed on the owner's rig, whose allowed ranges are
  narrower. The fix is in `2c961b58`. Test rigs now narrow their ranges asymmetrically
  with `tests.support.moving_heads.allowed_rig` (`tests/support/moving_heads.py:1330`).
- **Fast, symmetric heads hide slow-head defects.** At the synthetic rigs' speed every
  repositioning fits its window, so none of these showed until the heads moved at about
  150°/s (the owner's layout limit):
  - events lost to dark entries;
  - variants that cannot travel their reach in their period (fitting, `5825ff0a`);
  - a FASTER step the rig does not admit (`934b2635`).

  Test every new mechanism on `allowed_rig` with slow heads, and in 3/4 and at fast tempos.
- **Owner-rig renders found what tests did not.** Renders of the owner's song found:
  - a lost downbeat hit;
  - lyric hits moved before their lyrics;
  - a variation given up for an event it did not cost (`08c50a92`, `f9894cc8`).

  Render the owner's song after each feature that changes what plays. The method is in
  the true-up
  [handoff](../../changes/2026_11_12_mh_true_up/plan/handoff.md#how-to-validate-and-review).
- **Judge a rule change by comparing events before and after.** Unchanged pins and green
  tests did not show that a one-bar move clamp counted in frames lost events in plans
  with no variation. A comparison of 1,200 fuzz plans on two trees, recording which head
  plays each event, did show it. Run that comparison for any change to a move, give-way
  or judging rule. For the arrangement, `pipeline.worse` does the per-event judging.

Related: [prove-parity-before-deleting](prove-parity-before-deleting.md) (the same lesson
for a deletion), [render-output-proof](../patterns/render-output-proof.md) (a byte matrix
proves that output did not change, not that a change was right),
[W10b/c record](../../changes/2026_11_12_mh_true_up/evidence/2026-11-18-w10bc-motif-variation/README.md).
