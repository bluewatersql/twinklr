---
type: decision
status: accepted
created: 2026-08-16
updated: 2026-08-16
confidence: reported
tags: [macro-planner, coordination, palette, motifs, focal-arc]
---

# Typed Macro Coordination Contract

_Accepted by the owner on 2026-08-16, including the exact invariants and AC2 amendment;
independently approved offline/in code and integrated at `558153c`. The owner later
accepted P3-T5's emitted-behavior policy and approved that offline candidate for
integration._

## Decision

`MacroPlan` has exactly four top-level fields: `sections`, `palette_arc`,
`motif_continuity`, and `focal_arc`. The legacy story, layering, asset-requirement, and
primary/secondary-focus models are deleted because they had no structured behavioral
consumer; cross-element intent is represented by typed palette, motif, focal-role,
call/response, and coordination fields instead.

Palette precedence is deterministic: a section's `PaletteRoleRef.override` wins over
the active ordered `PaletteStop`; the first stop starts at the first section and later
stops follow section order. A section ThemeRef's optional `palette_id` is null or equals
that resolved palette. Feature-engineering color-arc context is advisory and does not
override this contract.

Each section has exactly one LEAD `FocalRole` and exactly one matching
`FocalAssignment`; their typed `PlanTarget` values are equal. Motif evolution is
thread-wide, and an empty motif-continuity list is valid only when sections reference no
motifs.

`PlanTarget(type=ZONE)` retains the established choreography contract: its ID is a
`ChoreoTag`, and it resolves through `ChoreoGroup.tags`. `GroupPosition.zone` /
`DisplayZone` is physical spatial metadata and does not become targetable merely because
it is present on a group.

## Context

The prior macro output solicited strategic prose and layer fields that reached the
renderer only through prompts. P3-T4 needed a strict structured-output contract that
could cross pipeline seams losslessly without authorizing P3-T5's display behavior.
The accepted specification's exact four-field table conflicts with later prose about
retaining a partial story model, so the normative table and dead-field discipline were
applied and the discrepancy is surfaced for owner review.

## Rationale

- One exact contract prevents the display and moving-head paths from inventing parallel
  meanings.
- Active-stop and override rules eliminate ambiguous palette precedence.
- Matching focal declarations prevent two sources from naming different leads.
- Intrinsic reference validation catches malformed plans; external graph/catalog
  validation catches environment-dependent IDs.
- Full typed objects participate in downstream prompt and cache derivation, preventing
  song-level-only edits from disappearing at list-shaped seams.

## Consequences

- The full `MacroPlan` is retained in pipeline state; only `sections` are used as the
  fan-out payload.
- Group planning consumes a typed per-section projection containing the section,
  palette stop, resolved palette, relevant motif threads, and focal assignment.
- Moving-head and holistic planning derive prompt and cache inputs from the full plan.
- P3-T4 provides a recursive, mutation-discriminating leaf registry plus actual
  typed/by-name prompt, cache, and validation readers for the complete contract.
- `call_response_pairs` and `coordination_intent` are read by P3-T4's projections,
  prompts, validation, and cache keys, but P3-T5 remains the binding plan's first
  emitted-display behavioral consumer of those fields. The owner amended AC2 so P3-T4's
  acceptance boundary is its recursive mutation-discriminating typed/by-name projection,
  prompt, validation, and cache consumption; this amendment did not substitute a fake
  emitted-behavior sink. P3-T5 now supplies that emitted consumer under the separately
  accepted coordinated-show contract, without authorizing live work or P3-T6+.
- The owner authorized only the bounded live macro-planner probe, capped at three
  attempts and one cumulative `$1.75` task budget. After harness-audit GO, attempt 1
  reached OpenAI exactly once and received HTTP 400 `invalid_json_schema` because the
  `ThemeRef.scope` node combined `$ref` with sibling `description`. No retry, JSON-object
  fallback, or schema repair occurred. Provider usage was unavailable, so the audited
  ledger conservatively committed the complete `$1.66` reservation. The remaining
  `$0.09` cannot fund another `$1.66` reservation; live acceptance remains open despite
  the subsequently integrated and offline-verified schema remediation. No further
  P3-T4 live attempt is authorized.

## Related

- [P3-T4 specification](../../changes/twinklr-reactivation-review/build/specs/phase-3-show-convergence/P3-T4-macro-structured-contract.md)
- [Phase 3 plan](../../changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md)
- [LLM intent / deterministic precision boundary](llm-plans-intent-renderer-implements-precision.md)
- [Coordinated show contract](coordinated-show-contract.md)
