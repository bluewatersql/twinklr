---
type: pattern
status: active
created: 2026-11-17
updated: 2026-11-17
confidence: confirmed
tags: [moving-heads, rendering, verification, refactor]
---

# Proving a Refactor Leaves Render Output Unchanged

Used for every moving-head change meant to keep output identical: the gate-time cut, the
per-preset admission, the profile defaults, and the three cutover steps that deleted the
old renderer, narrowed the shared models and renamed the survivor (2026-11-16 and
2026-11-17, `feat/mh-true-up-p3`). Each found zero unintended differences, and each
review reran it independently.

## Technique

1. **Fix a baseline commit,** usually a tag or the commit before the change
   (`mh-last-with-legacy-renderer` for the deletion). Export it with `git archive` into a
   scratch directory so both trees run side by side without touching the worktree.
2. **Render one configuration matrix on both trees.** The cutover's covered 360
   configurations, each rendering two plans. Record, per render: the encoded frames,
   segments, every delivered file (`.xsq`, `.xtiming`, `.xmap`), the gate result, the
   fingerprint and the record and trace hashes.
3. **Compare leaf by leaf and classify every difference.** A difference must be one the
   change intends (for example the fingerprint, because a hashed dump lost a field) and
   must vanish once that field is normalized out of the record and trace. Anything else
   is a defect.
4. **Rerun after every fix round** and compare the reruns with each other as well as
   with the baseline.
5. **Commit a guard, not the matrix.** The matrix scripts live in session scratch. What
   stays in the repository is `tests/regression/test_mh_pins.py`: frame and `.xsq`
   hashes rendered from the baseline, checked by mutating one byte of each render to
   show every pin can fail. A change that alters pinned output must say so and why.

## Why

Unit tests show that code still does what its tests ask; they do not show that thousands
of rendered bytes are unchanged after deleting or renaming the code around them. The
matrix gives that evidence directly, and its classified differences are the list of
user-visible consequences the owner must be told (see
[model dumps re-key caches](../learnings/model-dump-hashes-rekey-caches.md)).

## Limit

It proves the surviving path did not change. It does not prove that deleting a replaced
implementation lost nothing: the cutover passed it and still removed the old renderer's
whole intent layer. Before deleting a replaced implementation, also prove behaviour
parity on the same inputs ([learning](../learnings/prove-parity-before-deleting.md)).

## Related

- Records: [C1.2](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-2-deletion/README.md#6-fingerprint-change-and-byte-proof),
  [C1.3](../../changes/2026_11_12_mh_true_up/evidence/2026-11-16-c1-3-model-narrowing/README.md#6-proof-that-output-is-unchanged),
  [C1.4](../../changes/2026_11_12_mh_true_up/evidence/2026-11-17-c1-4-renames/README.md#4-proof-that-output-is-unchanged)
- [Moving heads have one renderer](../decisions/mh-single-renderer.md)
