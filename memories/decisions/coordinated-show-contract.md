---
type: decision
status: accepted
created: 2026-08-16
updated: 2026-08-16
confidence: confirmed
tags: [show, coordination, moving-heads, display, beat-grid, xlights]
---

# Coordinated Show Contract

_The owner accepted all nine P3-T5 decisions on 2026-08-16; the final offline candidate
was integrated at `f006468`. This record does not authorize P3-T6 or live work._

## Decision

1. `twinklr show` is the additive combined command; `twinklr run` and `twinklr display`
   retain their branch-only behavior.
2. One parsed xLights layout owns the canonical macro graph. Moving-head fixture models
   reconcile against one exact active direct whole-model group, while display planning
   receives the non-MH partition. Duplicate model/group declarations, duplicate members,
   nested/submodel references, missing members, extras, and overlapping ownership fail
   before provider work.
3. Emitted focal activation is deterministic per concrete target. Display targets use
   LEAD/SUPPORT/REST weights `1.0/0.65/0.15`; raw activation is
   `sum(intensity * duration_ms)`, the per-section base is the minimum
   `raw / role_weight`, and each target scales down to `base * role_weight`. Unmentioned
   targets default to SUPPORT. MH projects the same roles to INTENSE/SMOOTH/SLOW.
4. A section palette override wins over its active palette stop. Display receives the
   ordered colors; MH uses the closest fixture-neutral wheel preset with stable
   declaration-order tie breaking.
5. Typed call/response pairs are valid if and only if the coordination mode is
   CALL_RESPONSE. Expanded teams are call-first, BeatGrid-derived, clipped, disjoint,
   and fail closed on unknown, empty, repeated, reversed, self-overlapping, or too-short
   declarations. Unpaired targets retain full-section SUPPORT behavior.
6. P3-T5's “MH selection” acceptance phrase means emitted segment/timing structure; the
   task does not replace the existing MH template-selection algorithm.
7. The tracked deterministic Mega Tree `Spirals` recipe is part of the clean-clone
   combined golden contract.
8. P3-T5 narrowly preserves pre-existing EffectDB/palette positions when appending
   display effects so one XSequence cannot corrupt MH refs. General export-core merging,
   quantization, trace/injection unification, and arbitrary-document policy remain P3-T6.
9. The combined command retains P3-T3's effective catalog edge: tracked recipes, optional
   local extensions, then FE-promoted recipes; FE/style inputs reach the planner;
   missing/empty catalogs and planner/renderer ID mismatches fail before provider work.

## Context

Before P3-T5, the macro contract carried focal, palette, call/response, and coordination
intent, but MH and display rendering had separate timing and export paths. A naive serial
composition also replaced positional EffectDB entries and could silently retarget MH
effects. The accepted contract creates one behavioral seam without pulling P3-T6's
general export unification forward.

## Rationale

- One graph and one authoritative BeatGrid prevent cross-branch identity and timing
  drift.
- Concrete-target budgets keep focal ordering meaningful despite unequal recipe event
  counts.
- Fail-closed ownership and pair/mode rules prevent ambiguous physical output.
- One effective palette decision gives both backends a shared color source while still
  respecting fixture-specific wheel capabilities.
- The narrow registry-preservation prerequisite makes the P3-T5 sequence safe without
  pre-implementing P3-T6.

## Consequences

- Combined planning executes the common audio/profile/lyrics/macro prefix once and joins
  the MH and display branches at one final in-memory XSequence barrier.
- Cached/fresh coordination is idempotent; compiler IDs containing `|coord-` remain raw
  unless they have the exact coordinator-owned terminal suffix.
- The implementation integrated at `f006468` does not constitute P3-T4 live acceptance
  or any Phase 1P/2P/2K empirical exit.
- P3-T6 and later Phase 3 work require separate owner authorization.

## Related

- [P3-T5 specification](../../changes/twinklr-reactivation-review/build/specs/phase-3-show-convergence/P3-T5-mh-display-coordination.md)
- [Phase 3 plan](../../changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md)
- [Pipeline architecture](../../context/architecture/pipeline.md)
- [Typed macro contract](typed-macro-coordination-contract.md)
