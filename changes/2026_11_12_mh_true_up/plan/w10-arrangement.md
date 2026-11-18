# W10 — render motif, variation, density and modifiers (plan, 2026-11-17)

**Status.** Design revised after an independent critic (PROCEED WITH CHANGES); W10a built
([record](../evidence/2026-11-17-w10a-variants/README.md)); W10b/W10c and W10d built (As
built notes below). Linked from
[song-intent-rendering.md](song-intent-rendering.md#work-sequence).

**Integrator decisions (2026-11-17, reversible; the owner may overrule any).**

| # | Question | Decision |
|---|---|---|
| I1 | REST | Dark (owner D3); the planner and judge prompts are corrected to say so |
| I2 | A restated motif on another template | Carry the reach/rate class; colour and gobo are fed back, never overwritten (the contract has no "unset"); no accent replay |
| I3 | Equal `motif_id`s | The same idea, with or without a macro plan |
| I4 | Variation's source; a disagreeing `preset_id` | With a motif, the motif source's part at the same index; without, the previous section on the same family, else the part's own preset; a disagreeing `preset_id` is recorded and fed back |
| I5 | `wide`/`fast` | Authored for all seven families, with the four combinations |
| I6 | Modifier key | Stays a free string; the prompt and repair learn a closed set |
| I7 | Critic M1–M9 | As written in the sections below |


Proposal against `1eca8998`, revised with the critic's findings (PROCEED WITH CHANGES) and the
integrator's decisions of 2026-11-17. Integrator decisions are reversible; owner look questions are
PENDING-OWNER. "Proposed" marks every value nobody has chosen.

## 0. Constraints from the code

- **Presets are the variant mechanism.** A family's `presets[].step_patches` deep-merge into its steps;
  `StepPatch` carries only `movement`, `dimmer`, `timing` (`models/template.py:669-684`). All seven
  families declare `narrow` (extents) and `slow` (period); the two touch disjoint keys.
- **The gate** (`pipeline.admit_templates`) dry-compiles every declared rung; the effective-variant
  ladder is base then presets in declared order. A family is admitted when a rung passes.
- **Render identity hashes the plan dump and every template doc** (`identity._plan_payload`,
  `templates`): new catalog presets move every fingerprint of a plan using that family (no frame);
  a new plan field must stay out of the payload at its default.
- **Macro motif threads** carry one `evolution` per thread (`planning/models.py:113-121`) and reach
  the MH planner only in its prompt; relation and source are derived at plan time and carried on
  the plan as code-owned fields (as `cue_ms`).
- **The colour/gobo contract has no "unset"**: `as_authored` is the planner's explicit choice
  (`models.py:244-250`), so code may not overwrite it.
- **Per-head darkness is new.** `dark_spans` and `closed` are rig-wide (`pipeline.py:194-200`,
  `events.apply_section_events`); `_dark_over_spans` raises on a head with no commandable darkness
  (`pipeline.py:300-305`).
- **Repair predicts the render** (`rig_repair.py:1-7`; wheel plays `:511`, `:753`, `:906-907` read the
  variant's dark phases) and must keep doing so for every rule below.

## 1. Variation (W10a catalog, W10c resolution)

**Audience.** The section moves visibly tighter (NARROW), broader (WIDEN), at half rate (SLOWER) or at
double rate (FASTER) than what it varies.

**Grid.** Reach `narrow | base | wide` × rate `slow | base | fast`: nine variants per family, authored
in the catalog as presets `narrow`, `slow` (as today), `wide`, `fast`, and the four combinations
`narrow+slow`, `narrow+fast`, `wide+slow`, `wide+fast` (each exactly the merge of its two single
patches, a test pins that). `wide` = extents × 1.5, `fast` = period halved (proposed).
- **Off the ladder.** The effective variant and admission stay the base → `narrow` → `slow` ladder;
  the six new ids are never a fallback (they ask for more, or would admit a family the ladder
  refuses). Every variant is dry-compiled by the gate; the offer publishes each admitted one.
- **Speeds multiply in combinations** (critic M9: cascade `wide+fast` 204 BPM at 720°/s against `fast`
  alone 306), so every combination is dry-compiled, never inferred from its parts.
- **Offer-wide data stays honest per variant.** Entry dips and `dark_entries` are measured over
  every admitted variant; `excluded` (overlay masks) stays over the ladder's variants, and where a
  variation variant excludes more wheel states the offer records them for that variant
  (`TemplateOffer.variant_excluded`) and the render's colour resolution reads the variant it
  plays (W10a), so no existing plan's frames move.

**Source (integrator decision 4).** With a motif: the motif source's part at the same index (the last
source part where it has fewer). Without one: the previous section using the same template family
(the prompt says "relative to where it appeared before"), else the part's own `preset_id` (else the
family's effective variant). One step on one axis; off the grid, or not admitted on this rig and
song, is recorded and plays the source variant. A planner `preset_id` that disagrees with its
variation is recorded and fed back; the variation's resolution plays.

**Where.** Repair (plan time) writes the resolved variant into the part's `preset_id`; the render
plays presets as today. Fixed repair order (critic M5): motif relation → variation/preset → density
darkness → existing event/wheel/transition repair, each reading the resolved variant's phases.

**Owner look questions (PENDING-OWNER).** `wide` ×1.5 and `fast` ×2; `finite_snap_hold` SLOWER/FASTER
barely differ (its one move is 1 beat; `slow` 2, `fast` 0.5).

## 2. Density (W10d)

**REST (owner D3): dark.** A synthetic section-wide `closed` in `apply_section_events`, so it follows
the closed rules exactly (`events.py:343-346`, `:1406`, `:1420`). Planner intent wins: a planner `open`
ends it, a planner hit lights a head from the darkness (`lit_from_dark`); on the same frame the planner
event takes precedence over the synthetic closed. Repair records REST on heads `offer.dark` excludes
(never a refusal; those heads play as BALANCED, traced) and records look intent that cannot be seen
in a fully dark REST (colour, gobo, intensity). Transitions into/out of REST see a dark look (the W8
machinery: handover at dark, `nothing` where dark on both sides).

**SPARSE: half the heads lit, alternating on the variant's own cycle.** Heads are grouped by their
folded distribution slot (`topology.py` fold `min(i, n-1-i)`), so mirror partners stay together; the
two halves of the slots alternate per cycle of the section's resolved variant (`whole_period_cycle`),
never per bar. Rejected at plan time and recorded (playing BALANCED) where any head would be dark for
the whole section (a section shorter than two cycles, or a one-slot rig). ONCE families
(`finite_snap_hold`): the move is lit on every head and only the hold alternates. No tempo fallback.
New mechanism: per-head darkness spans, commanded like `_dark_over_spans` on the head's own cues,
skipping heads with no commandable darkness (recorded). Hits on a darkened head follow the hit rules
(the head is dark between its cues: no hit there; the lost-hit invariant is against the SPARSE render
without transitions, so it holds). Transitions see the darkened heads as dark looks. Offer: a per
family note of the cycle SPARSE alternates on; repair overlays SPARSE darkness on the variant's
published phases before wheel/hit predictions.

**BALANCED.** Identity.

**BUSY: one accent per bar, on each head's first lit beat of the bar** (critic M3: cascades are dark on
the downbeat, `events.py:1406`, `:1539-1549`), decided per head by `apply_hits`' own visibility rule;
HIGH emphasis where intensity is shaped (DRAMATIC already accents the downbeat, `intensity.py:146-153`).
An accent that is not visible per the played rule is traced as such (no blanket "adds nothing under
INTENSE"). Density accents never enter `yield_spans` (critic M2): an accent inside a planned transition
window or a planner event's seen span is dropped and recorded. Planner intent wins. Never a strobe.
Traced as `density_accents`. The 25 % BUSY budget is repair feedback (lowest energy first), not a
refusal.

**Multi-part (critic M6).** Allowed; density counts bars and cycles across the whole section.

**Prompts (critic M8).** Planner `developer.j2:169-173`, `user.j2:259` and judge `developer.j2:89`,
`user.j2:148` define density as movement; rewrite them to say exactly what renders (dark; half the
heads alternating per cycle; the template's own; an accent each bar). The integrator puts the meaning
to the owner.

**As built (W10d, 2026-11-18; evidence
[2026-11-18-w10d-density](../evidence/2026-11-18-w10d-density/README.md)).** `density.py`,
renderer revision 20; BALANCED renders the same frames. Departures from §2, each recorded
here:
- *SPARSE yields to the song.* SPARSE runs after the part's events, so its darkness
  changes no event's own decisions; every head plays as BALANCED over what `pipeline.worse`
  judges an event by (`density.sparse_protected`: a strobe's or `pulse`'s first 25 frames,
  half a beat each side of a hit, a colour or gobo change's lit run as BALANCED shows it).
  The lit run cannot be narrowed: `worse` counts any shorter run as "shown more briefly",
  so a narrower protection would only turn a partial SPARSE into a whole-section
  give-way. Repair does not overlay SPARSE darkness for its event predictions (§2's
  "repair overlays"): the events are BALANCED's or the section gives way.
- *SPARSE's lit rule and fallback.* "Every head lit at least once" is judged on the
  frames (three running, as a hit's lit run), per part; the alternation restarts in each
  part on that part's variant's cycle. Fallback order: every cycle, every half cycle, then
  the part plays BALANCED (traced, repair predicts it from the variant's dark phases).
  §2's "rejected at plan time" became this render-decided fallback; a one-slot rig still
  plays BALANCED. The ONCE template's first cycle (its move) is lit on every head.
- *REST on heads that cannot go dark.* A `closed` (REST's or the planner's) on such a
  head is traced `not_played` instead of failing the render (`events._plan_shutter`), and
  repair records REST there; but the transaction pass cannot park such a head after its
  last cue (`compile/preposition.py` `_dark_commands`), so no render of such a rig reaches
  REST today. Tested at the events layer and in repair.
- *BUSY's first lit beat* is read on the head's frames as played, a transition's own
  cues included, so an accent whose beat falls inside a transition's window is dropped
  (traced) rather than moved past it; an accent is also dropped where its beat or frames
  fall inside a planner event's seen span widened by a beat (one rule with SPARSE).
- *Give-way* (after f9894cc8): each SPARSE or BUSY section is an arrangement unit
  (`pipeline._density_units`, key `density:<section>`, after its variation, candidate
  "planned", reference BALANCED), traced "density gave way to <event>". BUSY gives way
  whole: `worse` names events, not the accents near them, and the accents already keep
  clear of events and transitions. REST is not a unit. Revision 20.
- *Review and owner-rig fixes (revision 20).* REST decides its boundary and entry on the
  part without REST and keeps cues its entry leaves dark, so its hits play on every head
  that plays them at BALANCED (lit from the dark where the head's wheels hold still
  around them); SPARSE keeps off the planned transitions' reach at its part's edges (from
  the plan as given, so the render without transitions agrees) and off a colour still lit
  from an earlier part; BUSY's accents are decided once on the plan without transitions
  and dropped only inside a transition that plays on the head. Where a density unit is in
  the plan, every unit's first candidate is tried at once first
  (`ArrangementUnit.together`).
- *Offer and contract.* `RigOffer.sparse_halves` (left out of dumps when None) and a
  per-template cycle note in the prompt; the `density` field's description and the
  planner and judge prompts now say what renders (re-keys the planner cache).
- *Trace* `section_looks[].arrangement.density`, per part.

## 3. Motif (W10b)

**Relation (integrator decision 3).** Equal `motif_id`s are the same idea, with or without a macro
plan. With a thread: its first section in plan order introduces, later ones take the thread's
`evolution` (a repeated INTRODUCE becomes RESTATE, traced). Without one: plan order (first introduces,
later restate). A section naming a motif no thread lists is recorded and treated by plan order. No
refusals (the earlier "forward reference refused" is removed). Code-owned `motif_source_id`,
`motif_relation` on `PlanSection`, left out of the identity payload when null.

**What carries it (integrator decision 2).** RESTATE: the source's variant class per part (§1
source rule); VARY: plus the one variation step; RESOLVE: SLOWER, else NARROW, else restate. A
different template than the source's is kept (explicit intent): the reach/rate class carries, and the
mismatch is fed back. Colour and gobo are never overwritten (no "unset" in the contract): where the
restating section's colour or gobo differs from the source's, repair feeds it back. No accent replay.

**Order.** W10b (motif) lands before W10c (variation resolution), since the source is derived first.

**As built (W10b/W10c, 2026-11-18; evidence
[2026-11-18-w10bc-motif-variation](../evidence/2026-11-18-w10bc-motif-variation/README.md)).**
Departures from §1 and §3, each recorded here:
- *Where.* Repair does not write the resolved variant into `preset_id`. One resolver
  (`arrangement.resolve_arrangement`) runs in the render and in repair, so they agree by
  construction, and a saved or injected plan renders its motif and variation without a
  re-repair. Repair records a named preset the resolution replaces.
- *Source is the introducer* (integrator decision, 2026-11-18, after 5b708b26). Every
  later carrier steps from the motif's introducing section (first carrier in plan order),
  not the previous carrier: steps never accumulate, RESTATE returns to the introduced
  look, RESOLVE steps from it. The lost "build" arc (a last chorus going further than the
  first) is a PENDING-OWNER look question. Multi-part rule unchanged (same index in the
  introducer).
- *The introducing section* steps from its own preset (else the effective variant), with
  or without a variation; a section without a motif steps from the previous section on
  its family when it has a step, else its own preset.
- *Variant fitting* (integrator decision, 2026-11-18, after the owner-rig render at
  2c961b58): the catalog's x1.5 and /2 are targets; a variation variant that fails the
  gate is fitted to the rig (`fitting.py`), offered at the strongest passing strength,
  in render identity. Revision 15. Revised after the owner render and review (revision
  16): a fit never changes the period (a 3-beat `fast` slid its reveals off the beat);
  only the reach is reduced (wide x1.4 → x1.2; fast toward `narrow`'s extents at the
  halved period); only speed and range failures are fitted; no two offered variants play
  alike; FASTER falls back to a narrower reach.
- *The song outranks the arrangement* (integrator decision after the owner render at
  bcefff0f, revision 17): a variation may never make a lyric-bound or planned event worse
  than its source variant; revision 18 builds the arrangement up greedily from the
  reference (every step off), unit by unit in plan order, accepting the first candidate
  under which no event is worse (`pipeline.worse`, `ArrangementUnit`); repair predicts
  where a variation may give way. FASTER falls back one reach step at most; near-twin variants (3 degrees) are
  not offered.
- *Code-owned relation* (W10b/c review M1): plan time derives and overwrites
  `motif_relation`/`motif_source_id`; the render derives them again, keeping only a
  plan-time RESOLVE (only a macro thread gives one; the render has no macro plan).
- *Plays as base.* A ladder variant (`narrow`, `slow`) whose frames equal the base's here
  stays admitted for a section naming it, but no variation steps to it
  (`TemplateOffer.plays_as_base`); a variation variant that does is not offered (W10a
  review M1).
- *Per-variant data* (W10a review H1, M3): the ladder's entry dips and dark entries are
  1eca8998's; variation variants' are published apart (`variant_entry_dips`,
  `variant_dark_entries`), replacing §1's "measured over every admitted variant".
- *Parity rows* are not added: the parity baseline holds only old-renderer facts and the
  old renderer never rendered motif or variation; pins and tests stand in.

## 4. Modifiers (W10e, redesigned against the code; critic M7)

The key stays a free string (integrator decision 6). `direction` via `transform.reverse` is refused
on most families (`template.py:192-208`: transform only on relative shapes), `StepPatch` has no
`distribution` field (`compile/preset.py:28-44`, `patch.py:36`), and aim/spread are relative ops a
static merge cannot express. Proposed: a computed patch layer in code (after the preset), each key a
function of the step (`aim: low|high` → `start_tilt_deg ± 10°`; `spread: unison|wave|wide_wave` →
`distribution.spread_cycles` 0 / authored / ×2 where the step has a distribution; `direction: reverse`
only where the step's shape takes a transform). The offer publishes per family only the keys and
values that change frames there, proven by a test per family and key that the bytes change; unknown
or not-offered keys are recorded and fed back. Gate admission per offered value.

## 5. Cross-cutting

- **Revision.** `RENDERER_REVISION` bumps in each task that changes output for an existing input.
- **Trace.** `section_looks[].arrangement{motif, variation, density, modifiers}`, only where set; the
  "not rendered" diagnostic loses a name per task and goes with the last.
- **Cache.** Each task that changes a prompt or the offer re-keys the planner cache (paid re-plan).
- **Tests the critic asked for.** Per family × rule a byte change; under SPARSE every head lit at
  least once per variant; transitions into/out of REST and BUSY in all modes with window lengths
  asserted; repair = render for SPARSE, REST and composite variants; multi-part motif + variation;
  REST on a rig with heads that cannot go dark; `wide+fast` gate refusal; gate time before/after.

## 6. Tasks and order

| # | Task | Depends on | Size |
|---|---|---|---|
| W10a | Catalog `wide`/`fast` + four combinations, off the ladder; gate admission; per-variant offer data; render reads its variant's exclusions; gate timing | — | M |
| W10b | Motif relation + code-owned fields + feedback | W10a | M |
| W10c | Variation resolution in repair (source rule, grid, feedback); prompt lists admitted variations | W10b | M |
| W10d | Density: REST, SPARSE (per-head darkness), BUSY accents, budget; prompts and judge | W10a | L (2 commits) |
| W10e | Modifiers: computed patch layer, offer, repair | W10a | M |
| W10f | Remove the diagnostic; docs, context, pins | all | S |

## 7. PENDING-OWNER

All open owner questions are collected in one list:
[owner decisions pending](owner-decisions-pending.md).

1. The meaning of density as rendered (dark / half the heads alternating per cycle / the template /
   an accent a bar), against the prompts' "movement" wording.
2. Looks: `wide`/`fast` extents and rate; SPARSE's alternation; BUSY's accent per bar; SPARSE on
   `finite_snap_hold`; snap SLOWER/FASTER.
3. Cost: gate wall time with nine variants (W10a measures it); a restricted grid if it is too slow.
