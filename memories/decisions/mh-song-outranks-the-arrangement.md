---
type: decision
status: accepted
created: 2026-11-18
updated: 2026-11-18
confidence: confirmed
tags: [moving-heads, rendering, arrangement]
---

# The Song Outranks the Arrangement

_Integrator decision on 2026-11-18, after an owner-rig render in which a variation lost a
downbeat hit. It is reversible by the owner and is listed in
[owner decisions pending](../../changes/2026_11_12_mh_true_up/plan/owner-decisions-pending.md)
(V7). Built on `feat/mh-true-up-p3` in `08c50a92`, revised in `f9894cc8` and `934b2635`._

## Decision

A section's arrangement choice may never make any of the song's events worse than the
reference arrangement does. Today the choice is a variation step; density and modifiers
plug in the same way. The reference is the song with every choice at its source: each
part plays what it would with variation NONE.

The render builds the arrangement up from the reference, unit by unit in plan order:

- it keeps the first candidate under which no event, transition or head is worse
  (`pipeline.worse`);
- a unit with no such candidate gives way, traced with the first event it would have
  worsened;
- units that gave way are retried with the later acceptances in place.

The tie-break: where two units cannot both play, the earlier one in plan order keeps its
choice. Repair predicts, for the planner, where a variation may give way; the render
decides on its own frames.

## Context

Variants change when each head is dark, so a variation can move or drop a hit, delay a
colour, or cut flashes, sometimes in the next section. The first build blamed one section
for a worse event. It misattributed blame (the owner's chorus_2 gave up its variation for
nothing) and needed a pass limit with no fallback.

## Rationale

The planner's events are bound to the song (lyrics, beats). A variation is an
arrangement nicety. Losing a lyric hit to a wider sweep inverts their priority. Building
up greedily from the reference never blames: by construction it is never worse than the
reference, and it never gives up a choice that costs nothing given the earlier ones.

## Consequences

- **Render cost.** One reference render plus one per distinct candidate tried. The
  owner's song takes 16–28 s against 6.5 s without the loop.
- **A variation can silently not play;** the trace and the diagnostics say why.
- **New arrangement features must register as units** (`ArrangementUnit`,
  `register_arrangement_units` in `sequencer/moving_heads/pipeline.py`) and be judged
  only by `worse`.
- **Every move rule may only improve on the unmoved outcome.**

## Related

[context/current-state.md](../../context/current-state.md#implemented),
[user guide](../../docs/user-guide.md#how-a-sections-motif-and-variation-reach-the-lights),
[W10 plan](../../changes/2026_11_12_mh_true_up/plan/w10-arrangement.md),
[W10b/c record](../../changes/2026_11_12_mh_true_up/evidence/2026-11-18-w10bc-motif-variation/README.md).
