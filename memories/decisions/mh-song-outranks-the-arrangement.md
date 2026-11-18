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
(V7). Built on `feat/mh-true-up-p3` in `08c50a92`, revised in `f9894cc8` and `934b2635`. The combined renderer and verification are
recorded in the [Phase 3 integration evidence](../../changes/2026_11_12_mh_true_up/evidence/2026-11-18-p3-recovery/README.md)._

## Decision

An arrangement choice may never make a song event or transition worse than the
reference. The reference uses the source variant, BALANCED in place of SPARSE or
BUSY, and no modifiers. REST remains part of the plan.

The renderer first tries all planned units together. It accepts that render if
`pipeline.worse` reports no worsened event or transition and the modifier cue-drop
check passes. Otherwise it builds up the arrangement in plan order. It keeps the
first candidate that passes those checks, traces what made a unit yield, and retries
yielded units after accepting later choices. In this fallback, an earlier conflicting
unit gets first choice. Repair predicts where units may yield. The renderer decides
from the frames.

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

- **Render cost.** The common path renders the reference and a combined trial. The
  fallback renders each distinct candidate tried. See the integration evidence for
  the current replay and the handoff for the timing follow-up.
- **Trace.** Diagnostics and the arrangement trace explain a choice that gives way.
- **New arrangement features register as units** (`ArrangementUnit` and
  `register_arrangement_units`). Every trial preserves song outcomes under
  `pipeline.worse`. An added modifier also cannot drop more of a cue in its part or
  the following part.
- **Every move rule may only improve on the unmoved outcome.**

## Related

[context/current-state.md](../../context/current-state.md#implemented),
[user guide](../../docs/user-guide.md#how-a-sections-motif-and-variation-reach-the-lights),
[W10 plan](../../changes/2026_11_12_mh_true_up/plan/w10-arrangement.md),
[W10b/c record](../../changes/2026_11_12_mh_true_up/evidence/2026-11-18-w10bc-motif-variation/README.md).
