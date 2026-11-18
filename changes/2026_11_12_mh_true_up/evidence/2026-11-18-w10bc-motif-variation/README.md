---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-18
updated: 2026-11-18
---

# W10b/W10c — motif and variation rendered; W10a review fixes

**Provenance.** Implemented by an executor agent on 2026-11-18 in the worktree
`twinklr-mh-true-up` from `d1125419`, uncommitted; the integrator commits. Plan:
[w10-arrangement.md](../../plan/w10-arrangement.md) §1 and §3 (the "as built" notes there
record where the build departs from it). No provider call, no network, no xLights, nothing
under `~/xlights`, `data/` or `artifacts/`; `make validate` not run (the integrator's).
Every value is a proposal; nothing here has been viewed (PENDING-OWNER, below).

## W10b/W10c — what was built

- **One resolver** (`sequencer/moving_heads/arrangement.py`), called by the render
  (`RenderingPipeline._arranged`, over the gate's admission) and by plan repair
  (`rig_repair._arrangement`, over the offer), so repair and render agree by
  construction. Rules: [user guide](../../../../docs/user-guide.md#how-a-sections-motif-and-variation-reach-the-lights).
- **Motif (W10b).** Equal `motif_id`s are one idea; the first carrier in plan order
  introduces it and is every later carrier's source (integrator decision after
  5b708b26; the first build chained from the previous carrier). The relation comes from
  the macro thread where it lists the section (a repeated INTRODUCE restates), else VARY
  where a variation is set, else RESTATE. `normalize_plan` derives and writes the
  code-owned `PlanSection.motif_relation` and `motif_source_id`, overwriting whatever
  arrived (hidden from the planner schema with `SkipJsonSchema`, left out of the plan dump
  when null), and records a section no thread lists and a repeated introduction. The
  render derives them again, keeping only a plan-time RESOLVE.
- **Variation (W10c).** One step on one axis of the reach/rate grid: a later carrier from
  the introducing section's part at the same index; the introducing section from its own
  preset (else the effective variant); a section without a motif from the previous
  section on its family when it has a step, else its own preset. Steps never accumulate:
  two WIDEN choruses play the same look; RESTATE returns to the introduced look; RESOLVE
  without a variation steps from it slower, else narrower, else restates. A step off the
  grid, to a variant not admitted, or to a ladder variant that plays as the base here plays
  the look it steps from, traced with the reason and recorded by repair.
- **Repair** (`_arrangement_repairs`, first, before the section repairs that read the
  resolved variant's phases): steps that cannot play, a named preset the resolution
  replaces, a named preset not declared or not admitted (review M2), a motif on another
  template than its source's (only its reach and rate carry), a colour or gobo that differs
  from the source's (never changed by code).
- **Trace.** `section_looks[].arrangement` per section with a motif or variation:
  `{"motif": {id, relation, source?}, "variation": {asked, relative_to, from, plays,
  named?, reason?}}`. `_unrendered_intent_message` now names density and modifiers only.
- **Prompts.** Planner `developer.j2` says what renders; planner `user.j2` adds two lines
  (the variation rule with the variants a template does *not* play on this rig and song,
  and a variation variant's first dark moment where it differs); judge `developer.j2` and
  `user.j2` item 4 say what a restatement and a one-step variation are.
- **RENDERER_REVISION 13.**

**Parity rows: not added (pushback).** The parity baseline holds only the old renderer's
facts, and the old renderer never rendered motif or variation, so there is no parity row
to add. In their place: the pins (`tests/regression/test_mh_pins.py`) were re-recorded
fingerprint-only with every frame unchanged, and the new tests below pin the new behaviour.

## W10b/c review fixes (2026-11-18, after 5b708b26)

- **Introducer as source** (integrator decision, above). Pins unchanged (no pin has a
  motif), so `RENDERER_REVISION` stays 13.
- **H1 — the evaluation report agrees with the render.** `RENDERED_INTENT_FIELDS` names
  `motif_id` and `variation`; the report's template line prints the variant the trace
  says plays (`plays: wide`, with the planned preset where it differs), and
  `describe_look` leads a section's "played" lines with the motif relation and source and
  the variant line (asked, from, relative to, the planned preset that does not play, the
  reason a step did not play).
- **M1 — code-owned fields are never trusted.** Plan time overwrites both fields on every
  section (cleared where no motif); the render derives them again (a bogus source never
  plays). The reviewer's repro is a test (`test_relations_arriving_on_the_plan_are_overwritten`).
- **M2 — a snap into a template the heads enter dark** (pre-existing since W8). The render
  plays it (dark just before the boundary, lit on it); repair said "the plain cut" from
  `RigOffer.dark_entries`, and so did the planner prompt. Whether a snap changes a head's
  frames at a later boundary is settled only by the render's frames, so repair now claims
  the plain cut only on the song's first ENTRY, and the prompt's dark-entries snap
  sentence (and the offer's `transitions.dark_entries` list) is removed; the developer
  prompt and the user guide say a snap is the plain cut on the first ENTRY or on a head
  with nothing to move or turn. A probe over 6×6 family pairs at 120 and 170 BPM had 52
  of 144 cases where the old claim contradicted the render. Test:
  `test_repair_never_says_a_snap_is_the_plain_cut_where_the_render_plays_it`.
- **Regeneration.** `RenderingPipeline.arrangement_changes` compares the injected plan's
  resolution with the regenerated one; the rendering stage logs and stores
  `arrangement_warning` (printed by the CLI) naming each kept section part that now plays
  another variant ("s2 part 1 (wide+slow → wide)"). Never a refusal.
- **LOW — an introducing section with a variation** steps from its own preset (chosen:
  a first appearance has nothing before it); stated in the module, both planner prompts
  and the user guide.

## Owner-rig gate crash and confirmation-review LOW items (after e922bc52)

- **Crash.** `rig_offer`'s transition-darkness bound (`dark_change_ms`, W10a LOW-2,
  d1125419) measured each head across its *physical* pan, tilt and zoom range; a head whose
  allowed range is narrower (as the owner's are) cannot be commanded there and
  `dmx_word` raised, taking the pre-planning gate down. It now measures across the
  operable range (`AxisCapability.operable_range`, what the compiler uses). No other code
  added since 1eca8998 reads `physical_min`/`physical_max` (grep of the diff). The
  pre-existing W8 `full_travel_ms` still divides the physical range by the travel speed
  (an overstatement on such rigs, never a raise); left as is and reported.
- **Offer facts never take the gate down.** Chosen: the bound degrades to unknown (None)
  on a `ValueError`, logged once per head; repair already treats an unknown bound as
  "warn on every transition window". Test:
  `test_an_offer_fact_that_cannot_be_computed_is_unknown_not_a_failure`.
- **Coverage.** `tests.support.moving_heads.allowed_rig` narrows pan (-160..125 of
  -270..270), tilt (-20..105 of -135..135) and zoom (10..34 of 10..40); SYNTHETIC
  numbers. `test_a_rig_whose_allowed_ranges_are_narrower_than_physical_runs_end_to_end`
  (family and zoom rigs) runs the gate, the offer, repair and a render with a motif,
  variations and transitions, and checks every frame's pan, tilt and zoom word lies in
  the allowed range; it fails on e922bc52's code.
- **L1** `RENDERER_REVISION` 14 (a motif plan with two varied carriers renders differently
  at 5b708b26 and e922bc52); pins re-recorded fingerprint-only, every frame held.
- **L2** an injected plan read for `regenerate` is normalised on load
  (`with_motif_relations`, no macro thread): an injected RESOLVE or stale source is not
  honoured.
- **L3** no channel carries render-derived facts back to the planner: the render runs once
  after planning ends, and the refinement prompt reads only plan repairs. Left as is.
- **L4** `arrangement_changes` failing logs and the render stands.
- **L5** `PlanSection.motif_relation`/`motif_source_id` descriptions name the introducing
  section.

## W10a review fixes (listed apart)

- **H1 — dark entries and dark windows per variant.** `RigOffer.dark_entries` is again the
  ladder's (base, `narrow`, `slow`) claim, exactly 1eca8998's; each pair involving a
  variation variant has its own claim in `RigOffer.variant_dark_entries`
  (`successor → predecessor → "pv>sv"`), read through `RigOffer.dark_entry_heads(...)`
  with the variants the plan plays. The prompt's dark windows are the ladder's; a
  variation variant whose first dark moment differs gets one added line.
- **M1 — a variant that plays as its base.** The gate compiles each variant as a section
  after a bar of its own base, entered as the render enters a section, two cycles of the
  longer of the two long, and compares the encoded frames with the base's (on all 72
  reviewer rig × grid cases the result equals a whole-song comparison). A variation variant that matches is not offered
  (`preset_exclusions`: "plays the same as base here"; never a refusal, even for a
  template that is not excludable); a ladder variant that matches stays admitted as before
  (the ladder is unchanged) and is listed in `TemplateOffer.plays_as_base`, which no
  variation steps to. On the tagged rig at 78, 120 and 170 BPM the only such variant is
  `finite_snap_hold`'s `fast`; on 220°/s heads at 240 BPM, also its `slow` (ladder).
- **M2 — a named preset the gate did not admit** is recorded and fed back ("…: the part
  plays its effective variant"), as is one the template does not declare.
  `stage.py:581` does not conflict with the no-refusal rule: it refuses only a
  regeneration whose *injected base plan* names a template or preset this run's gate did
  not admit (the kept sections would not render as injected), never planner output. One
  consequence for the integrator: it checks named presets, not resolved variants, so a
  kept motif carrier can resolve differently when its source section is the one being
  regenerated (traced; not refused).
- **M3 — entry dips per variant.** `TemplateAdmission.entry_dips` is the ladder's, entered
  from the ladder alone (1eca8998's numbers); `variant_entry_dips[t][variant]` gives every
  passing variant's dip entered from any passing variant, variation variants included
  (what a plan playing one enters through).
- **LOW — `_lit_move_record` left as is.** A truthful narrower rule needs each template's
  peak lit speed as well as the pose envelope the offer publishes; with the envelope alone
  any narrower rule would under-warn on some pair. Unchanged from d1125419.

## Verification

| Check | Result |
|---|---|
| New tests `tests/unit/sequencer/moving_heads/test_arrangement_render.py` | 58 after the review round (resolver rules, multi-part, off-grid / not admitted / plays-as-base, default identity, byte change per family × variation over all seven families, repair = render on two plans × 2 tempos × 2 head speeds, M1, M2, H1/M3 ladder equality, per-pair dark entries, motif-thread records) |
| Full suite, ruff, format, mypy (after the review round) | 7376 passed, 30 skipped; ruff, format, mypy clean; pins unchanged |
| Reviewer `prompt_compare` (3 rigs × 4 grids) vs 1eca8998 | 0 changed fields other than the two new keys |
| Planner user prompt, owner-like rig, short-grid song | 10,471 → 11,270 chars (+799, two added lines, no existing line changed) |
| Reviewer `repro_dark_entries` | identical to 1eca8998's output |
| Reviewer `repro_unadmitted` | each case now recorded by repair; frames unchanged |
| Reviewer `gate_compare` (72 rig × grid) vs 1eca8998 | admitted, effective, ladder presets and exclusions, entry dips, dark entries identical; differences only in the new variants and the offer's new fields |
| Reviewer `underwarn` (3 rigs) vs d1125419 | identical |
| Repair sweep, 20,736 plans with no motif/variation (3 rigs × 4 grids × 6×6 families × colour × 4 transitions × 3 presets × event) | vs 1eca8998: sections identical; records differ only by d1125419's LOW-4 lit-move records and the new M2 records (96, `masked_wheel_flick` `narrow` not admitted); vs d1125419 the H1 dark-entry records return to 1eca8998's |
| Byte matrix (567 configs, 13,041 renders) vs d1125419 | frames, segments, `.xsq`, `.xmap`, `.xtiming` identical; normalised trace and render record identical; raw trace and record differ by the revision and fingerprint; gate data differs by the H1/M3 numbers (back to 1eca8998's) and M1 |
| Gate wall time vs d1125419 (`gate_time.py`, six rigs, one machine, back to back) | 1.10–1.40× (owner-like 62 bars: 16.6 → 18.1 s) |

## The owner song's saved plan

`11_need_a_favor` (`final.json`, read in place, not copied) carries `spiral` on verse_2,
chorus_1 (WIDEN), break (FASTER) and chorus_2 (WIDEN, two parts); no section names a
preset. It exercises motif and variation as saved: no fresh paid plan is needed for these.
Its saved admission predates W10a, so the render must re-run the gate (with it, every
step would be refused as not admitted). Expected with a gate that admits the steps, every
carrier stepping from verse_2's base: chorus_1 `wide`, break `fast`, chorus_2 both parts
`wide`. It never shows a RESTATE, a RESOLVE, a same-template motif or a named preset
replaced.

## M1 design note (not built): carrying rate on the snap family

`finite_snap_hold` lifts once in a beat and holds; entered after any section the lift is
inside the dark entry window, so its rate is invisible and the gate rightly drops `fast`.
Options for the owner: (a) rate as re-snap period, a LOOP of snaps to a small pose bank
every bar (base), two bars (`slow`), half a bar (`fast`), which makes rate the visible
thing but changes the family from one move to a pattern; (b) rate on the hold, the dimmer
settling or pulsing at the variant's period after the lift; (c) leave snap rate-less and
offer reach only. (a) is the most legible; it is a catalog change with a gate re-run.

## PENDING-OWNER

1. Look: does a WIDEN / FASTER variation read as "the same idea, bigger / quicker"
   across templates (verse_2 → chorus_1, break, chorus_2 on the owner song)?
2. Look: is "only reach and rate carry a motif across templates" enough to read as a motif?
3. Look: the off-grid case (WIDEN from an introduced `wide` plays `wide`): acceptable, or
   step the other axis?
4. The snap family's rate (design note above).
5. The lost "build" arc: with every carrier one step from the introducer, a last chorus
   cannot go further than the first (two WIDENs play the same). Acceptable, or should a
   later carrier be allowed a second step?
