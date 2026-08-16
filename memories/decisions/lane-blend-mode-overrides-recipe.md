---
type: decision
status: accepted
created: 2026-08-16
updated: 2026-08-16
confidence: confirmed
tags: [display, composition, xlights, blend-mode]
---

# Lane Blend Mode Overrides Recipe Blend Metadata

_Provenance: P3-T2 implementation and corpus-independent contract tests on 2026-08-16._

## Decision

For display composition, `LanePlan.blend_mode` wins over a compiled recipe layer's
blend metadata for every emitted sub-layer in that lane, including asset overlays.
Blend modes are registered only in the `allocate_sub_layer` index space used by
`RenderEvent` placement.

## Context

The previous engine wrote lane choices using a legacy BASE=0/RHYTHM=2/ACCENT=4 index
space but placed events in six-layer lane blocks. RHYTHM and ACCENT lane choices could
not reach their events, while BASE recipe and lane choices depended on first-wins loop
order. Fixing the index mismatch required an explicit precedence rule.

## Rationale

Lane intent is the planner's composition-level instruction and is therefore the
narrower authority for how a lane combines with the show beneath it. Applying it to
every depth is uniform across BASE, RHYTHM, and ACCENT and eliminates ordering effects
when multiple recipes occupy the same lane/depth. The rejected alternative—recipe wins
with lane as a default—would preserve recipe-specific styling but would still allow a
planner's explicit lane choice to disappear whenever a recipe supplies its required
blend field.

## Consequences

- Recipe blend metadata remains available in `CompiledEffect`, but the composition
  engine does not use it while the lane-wins contract is active.
- A non-Normal lane mode on the first emitted layer of an element cannot be honoured:
  xLights compacts it to layer 0, which has nothing below it to blend with. Composition
  emits a diagnostic instead of silently pretending the mode was applied.
- If time-separated sections request conflicting modes for the same physical
  element/sub-layer, the first registered method remains deterministic and the later
  unhonoured request emits a diagnostic. A future per-event blend representation would
  be required to honour both.

## Related

- [P3-T2 specification](../../changes/twinklr-reactivation-review/build/specs/phase-3-show-convergence/P3-T2-blend-modes-and-effect-fallback-truth.md)
- [Current project state](../../context/current-state.md)
- [Phase 3 plan](../../changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md)
