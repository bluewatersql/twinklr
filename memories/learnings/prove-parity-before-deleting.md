---
type: learning
status: active
created: 2026-11-17
updated: 2026-11-17
confidence: confirmed
tags: [refactor, deletion, verification, moving-heads]
---

# Prove Behaviour Parity Before Deleting a Replaced Implementation

Before deleting an implementation that a new one replaces, compare what the two do with
the **same inputs** and account for every behaviour of the old one: carried over,
deliberately dropped on the owner's word, or a gap to close first. Showing that the
surviving implementation's output did not change while the old one was removed proves
only that nothing broke on the new path. It says nothing about what the old path did
that the new one does not.

## What happened

The single-renderer cutover (`feat/mh-true-up-p3`, C1.2 `0ec65d47`, 2026-11-16) deleted
the old moving-head renderer. Every step was proved with a byte matrix showing the
surviving renderer's frames and files were unchanged
([pattern](../patterns/render-output-proof.md)), and the owner accepted the surviving
renderer's look on one song beforehand. No check compared what the two renderers did
with one plan. The old renderer's intent layer (planner intensity, section colour,
shutter and gobo events, lyric moment cues on events, section transitions, and the show's
palette and focal-role projection) had no counterpart, so the cutover removed all of it.
A per-section diagnostic said the intent was "not applied", and a planner-contract draft
then proposed cutting the unread fields. The owner rejected that on 2026-11-17: the
renderer, not the contract, was incomplete
([song-intent rendering](../../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md),
which lists the gap per intent with citations at both commits).

## Practice

- Inventory the old implementation's inputs and what each does to the output (which
  channel, when), with citations, before the deletion is planned.
- Run both implementations on a fixed input that exercises every input field, and record
  each field's effect. A field whose effect disappears is a regression unless the owner
  has said to drop it.
- A diagnostic or log line that says an input "is not applied" is a known gap to track,
  not a design statement.
- Keep the byte matrix too: it proves the surviving path did not change. Parity and
  unchanged bytes answer different questions.

## Related

- [Moving heads have one renderer](../decisions/mh-single-renderer.md)
- [Proving a refactor leaves render output unchanged](../patterns/render-output-proof.md)
