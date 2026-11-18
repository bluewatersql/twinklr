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

## Review fixes (after f9894cc8)

**Why.** The review of `f9894cc8` found two HIGH defects:

- A FASTER whose step variant the rig does not admit never tried its narrower reach. The
  step resolves to the source, which played the same as the accepted arrangement, so it
  was accepted and the loop stopped there.
- `worse` judged a strobe, pulse or `closed` on its first 25 frames only, so a variation
  that removed later flashes was accepted (15 of 292 plans in the review's sweep).

**Built (`934b2635`, revision 19).**

- A candidate that plays the same as the accepted arrangement is skipped, not accepted.
  The unit keeps it, with its own trace, only when no other candidate plays and none is
  worse.
- The fallback's note says why the step does not play: "FASTER: 'wide+fast' … is not
  admitted …; faster here needs a narrower reach: it plays 'fast'".
- `worse` judges a shutter event over the span the reference traced on each head:
  - a strobe or pulse by its flashes (lit runs) and its lit frames;
  - a `closed` by its lit frames.

**Evidence.** Both repros of the review behave correctly:

- `probe_faster.py`: the FASTER now plays `fast`.
- `repro_span.py`: the section gives way, and every head keeps its reference flashes.

Each repro is a test in `tests/integration/test_mh_song_outranks.py`, and both fail on
`f9894cc8`. `variation_regress.py`: 0 of 288 on plain and on allowed150. The related
suites pass (611).

## The song outranks the arrangement, revised (after 08c50a92: review)

**Why.** Blame misattributed (the owner's chorus_2 gave up `wide` for an event the break
cost), the four-pass limit had no fallback, and a one-bar clamp counted in frames lost
events in plans with no variation (fuzz seeds 4, 688, 810, 216).

**Built (revision 18).** No blame. `RenderingPipeline._choose_arrangement` builds the
arrangement up from the reference R (every unit at "reference": each part plays what it
would with its section's variation NONE, inherited variants included): unit by unit in
plan order, each candidate (the step, then a FASTER step's one-step-narrower reach) renders
the whole song with the units accepted so far plus it; the first under which `worse(R,
trial)` is empty is accepted, else the unit stays at its reference, traced "the variation
gave way to <the first worse event>". Once every unit is decided, each that gave way is
tried again with the later acceptances in place, until none changes. The final render is
the last accepted trial, reused; renders are cached by resolved arrangement; the
transition-free copy never chooses. Tie-break: where two units cannot both play, the
earlier in plan order keeps its choice.

- `pipeline.worse(reference, trial) -> list[str]` (public): an event or a head missing; a
  head losing it; a hit farther from its cue or beat, or a flash peak lower; a colour or
  gobo shown later or more briefly; a `closed` with more lit frames, a strobe or pulse with
  fewer (over 25 frames from its frame, played or not); a transition no longer playing on a
  head. One frame of tolerance.
- Units are generic (`ArrangementUnit(key, order, candidates)`, `register_arrangement_units`,
  `unit_choice`, `unit_gave_way`); `_variation_units` is the only kind today.
- Move rules improve only on the unmoved outcome: a hit move keeps every head that played
  it on its own beat (unless it moves for heads a transition would lose it on); a colour or
  gobo move keeps every head the rule as it was showed it on; moves are bounded in beats.
  Repair mirrors both. Repair's wording: "the variation may give way".

**Acceptance.**
- Reviewer's `strict_worse.py`, 200 plans per setup: 0 worse on plain, plain170, slow79
  and slow3/4 (run before and after the retry pass, 0 errors).
- `variation_regress.py`: 0 of 288 on plain and on allowed150.
- `restore_measure.py` (on `worse`): 37 sections flagged in 100 plans (17 plain, 20 slow79),
  none a configuration the render can play at no cost. 12 are no reinstatement: the
  repair-predicted "asked" variant equals what the section plays after giving way, so the
  trial is the final arrangement. 25 reinstate a motif introducer or family predecessor
  while its carriers keep the plays they resolved from its reference variant; the unit
  re-resolves them, and every unit candidate is worse. Re-measured as units (the section
  with what re-resolves from it), 0 of 37 are free.
- Fuzz vs 5825ff0a (1,200 plans, every event per head): 0 lost that played before
  (seeds 4, 688, 810, 216 included), 6 gained.
- `recount_shown`: frame-checked before an EXIT blackout and before the next section's
  entry repositioning (`test_shown_time_matches_the_encoded_frames`).

**Cost (REALISTIC, the reviewer's `timing.py`).** Without variation: 3.4 s, 2 passes. With
variation: 25.9 s, 14 passes = 7 arrangement renders (1 reference, 4 candidates, 2
retries of the break-like chorus_1 after chorus_2 was accepted), the final reused; was
26.8 s / 14 passes. Without the retry it would be 5 renders.

**Strobe question (owner look list, not changed).** A strobe only adds darkness (a square
wave through the dimmer or shutter, or the fixture's strobe state on frames whose shutter
is open), so it never lights a frame the template holds closed: a probe over 81 template
pairs and two strobe speeds on the owner-like 150 degree/s rig found 0 such frames. With an
EXIT transition (blackout or snap) on the section, the strobe's lit phases play over the
transition's dark window on every head (180 cases): by the rule as written ("a closed,
strobe or pulse commands darkness over its whole span, which a transition never cuts
into"). If the owner's break has a transition there, frame 191 is that rule; if the
template itself closes the shutter there, it is a bug not reproduced synthetically.

## The song outranks the arrangement (after bcefff0f: owner render and review)

**Why.** At bcefff0f the owner's break played FASTER as `narrow+fast` and lost chorus_2's
first-downbeat hit on two heads (D1), moved both lyric hits a beat before their lyrics
(D2), and the review found a variation worsened an event in 30-41 % of plans with events.
Integrator decision: a variation may never make a lyric-bound or planned event worse than
the source variant does.

**Built.** `RenderingPipeline._settle_arrangement`: a plan with a variation step and events
renders once with every step off (the reference), then as resolved; every event worse than
the reference (lost on a head, a hit farther from its lyric or beat, a colour or gobo
change shown later or more briefly, by more than a frame) is laid at its own section where
that varies, else at the section before it (an entry's darkness reaches across the
boundary); that section takes its next candidate (`arrangement.GiveWay`: a FASTER step's
one-step-narrower reach, else its source variant: "the variation gave way to its hit at
bar 6 beat 3 (lost on MH1, MH4)"), traced in `arrangement` and the diagnostics; the plan
renders again, at most `ARRANGEMENT_PASSES` (4) times. **Cost:** a plan with a variation
step and events renders at least three times (reference, trial, final; each with its own
transition-free render where it has transitions), one more per give-way round; a plan
without either renders as before. Repair predicts the give-way for the planner from the
published dark phases (`rig_repair._give_way`: an event record the source variant does not
have, and a first-downbeat hit newly entering dark, this section's or the next's); the
render decides on its own frames.

**Acceptance (the reviewer's `variation_regress.py`, 288 plans per rig):** 0 plans worse on
the plain rig and 0 on the 150 degree/s narrowed rig (were 69 and 70). Outcomes, plain:
the asked variant plays in 157, the variation gives way in 71, it cannot play (off the
grid, not offered) in 60; narrowed 150 degree/s: asked 96, a narrower-reach fallback 2,
gave way 72, cannot play 118. **Repair agreement** on 216 plans per rig: 204 (plain) and
195 (narrowed) agree with the render; the misses are first-beat hits whose loss depends on
the boundary's exact phase (the offer's dark entries are claims over every phase).

**Also in this round.**
- A cue-bound hit that must move prefers the beat after its own where that is at or after
  the lyric, else the nearest (`events.apply_hits`, repair mirrors it). The review's "within
  one beat of the lyric" would never pick a later beat over a nearer earlier one when the
  lyric is nearest its own beat, so the rule reads from the hit's own beat. No pinned or
  REALISTIC frame moved.
- A colour or gobo move never loses a head that showed the change on its own beat; moves
  (and hit moves) stay within one bar counted in frames.
- `shown_for_ms` is recounted on the planned frames (`events.recount_shown`): an EXIT or
  repositioning laid after the events now ends it (D3).
- FASTER falls back one reach step at most (from `wide`: `fast`, never `narrow+fast`).
- Near-twins: variants with the same darkness, level and wheels whose aim differs by under
  3 degrees on every frame (`TWIN_POSE_DEG`) play alike; the later is not offered.
- **D1 (the early entry):** no rule lets an event pull a head's dark repositioning before
  the boundary; the entry window only opens after it, and only a transition (`snap`,
  `blackout`, ...) darkens the outgoing look. Not built. It would take an event-led early
  entry in `_enter_section` (darken the outgoing part's tail by the worst-case entry bound
  on heads whose next downbeat event would be lost, where that tail cuts no protected
  event), with the gate's placement checks, repair's dark-entry prediction and tests.
  Under this round's rule the break gives way instead.
- **D4 (strobe newly lit frames):** not reproduced on synthetic rigs (a strobe into a
  crossfade and a downbeat hit, plain and owner-like 150 degree/s): a strobe only darkens
  its own frames, so frames "newly lit vs event-free" must come from the event-free render
  being darker there for another reason (a transition window or a repositioning that the
  events move); that it comes and goes with the variant fits. Finding which needs the
  owner render's records; left open.
- **D5 (PENDING-OWNER):** at the halved period the cascade's stagger is half a beat, so
  MH2/MH3 reveal on the off-beat eighth in every window: acceptable look?

## Variant fitting revised (after 5825ff0a: owner render and review)

**Why.** On the owner's rig the 3-beat `fast` (the old rate ladder) slid the break's
reveals off the beat (12 of 13 windows half a beat off; hits moved, a colour shown for
9 frames). Integrator decision: a fit never changes the period.

**Built.** `fitting.py` reduces only the reach: `wide` and the wide part of `wide+slow` /
`wide+fast` x1.4, x1.3, x1.25, x1.2 of the base's extent; `fast` keeps the halved period
and steps its extents a quarter, a half and three quarters of the way to the family's own
`narrow` extents (its floor; at `narrow`'s it would be `narrow+fast`, so it is then not
offered). Whole-beat periods are gone. Only a speed or allowed-range failure is fitted;
a mask or dark-repositioning failure, at the catalog or at a reduced reach, fails with
its own reason. Never fitted: `narrow+fast`, the snap's fast variants (its rate does not
show; a fitted `wide+fast` would be a weaker `wide`), zoom (no variant patches it). The
fit carries what the catalog strength broke (`because`) into the offer, the trace and
repair (review M2: "outside the operable range" where the range forced it; the old
"the rig's speed allows no more" is gone). **No two offered variants play alike:** the
gate compares each variation variant's entered frames with every earlier variant's and
leaves out a twin ("plays the same as 'narrow' here"); on every rig the snap's
`narrow+fast` and `wide+fast` now go (as its `fast` did). **FASTER** whose variant is not
offered plays the same rate at the next narrower reach that is (`wide+fast` → `fast` →
`narrow+fast`), noted "faster here needs a narrower reach" in the trace and repair (chosen
over "cannot play": it is the honest nearest faster look).

**Seen rule (review).** A colour or gobo change passed when a head showed it lit for 3
frames running within a beat; nothing measured how long it stayed lit, so the template's
own darkness could follow after 9 frames. Now (`events.SHOWN_FOR_BEATS` = 0.5): a change
no head shows for half a beat on its own beat moves, within the existing move bounds, to
the beat where the most heads do; where none does it plays as before and every head is
traced `brief` ("shown for N ms"); repair predicts both from the published dark phases
and feeds them back. **Hits:** not changed. A hit's moment is its flash, whose
`visible_frames` frames are already required lit and visibly different; a decay cut by the
template's darkness still reads as a hit, so the colour rule's preference is not needed.
**Found and fixed on the way:** repair read the base's dark phases for a part that names
an admitted preset (no motif or variation), so on a `fast` cascade its colour-event moves
disagreed with the render in 12 of 48 probe cases (also at 5825ff0a); it now reads the
named variant's (48 of 48 agree, 80 of 80 across five families).

**Admission on `allowed_rig` at 150 degree/s** (synthetic):

**79.5 BPM** (gate 4.62 s at 2c961b58 -> 5.13 s)

| Template | Fitted | Not offered (why) |
|---|---|---|
| finite_snap_hold | - | `fast` (plays as base), `narrow+fast` (plays as 'narrow'), `wide+fast` (over the speed (not fitted)) |
| fly_in_cascade | `fast` half period at x0.75 | `wide+fast` (over the speed at every reduced reach) |
| fly_out_cascade | `fast` half period at x0.75 | `wide+fast` (over the speed at every reduced reach) |
| masked_wheel_flick | - | - |
| mirror_wings | - | `wide+fast` (over the speed at every reduced reach) |
| target_orbit | `wide+fast` x1.4 | - |

**120 BPM** (gate 2.13 s at 2c961b58 -> 2.32 s)

| Template | Fitted | Not offered (why) |
|---|---|---|
| finite_snap_hold | - | `fast` (over the speed (not fitted)), `narrow+fast` (plays as 'narrow'), `wide+fast` (over the speed (not fitted)) |
| fly_in_cascade | - | `wide` (over the speed at every reduced reach), `fast` (over the speed at every reduced reach), `narrow+fast` (over the speed (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| fly_out_cascade | - | `wide` (over the speed at every reduced reach), `fast` (over the speed at every reduced reach), `narrow+fast` (over the speed (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| masked_wheel_flick | - | `wide+fast` (over the speed at every reduced reach) |
| mirror_wings | `wide` x1.3; `fast` half period at x0.679 | `wide+fast` (over the speed at every reduced reach) |
| target_orbit | `fast` half period at x0.9 | `wide+fast` (over the speed at every reduced reach) |

**170 BPM** (gate 1.31 s at 2c961b58 -> 1.57 s)

| Template | Fitted | Not offered (why) |
|---|---|---|
| finite_snap_hold | - | `wide` (over the speed at every reduced reach), `fast` (over the speed (not fitted)), `narrow+fast` (plays as 'narrow'), `wide+fast` (over the speed (not fitted)) |
| fly_in_cascade | `wide+slow` x1.4 | `wide` (over the speed at every reduced reach), `fast` (over the speed at every reduced reach), `narrow+fast` (over the speed (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| fly_out_cascade | `wide+slow` x1.4 | `wide` (over the speed at every reduced reach), `fast` (over the speed at every reduced reach), `narrow+fast` (over the speed (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| masked_wheel_flick | `fast` half period at x0.75 | `wide` (dark repositioning (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| mirror_wings | - | `wide` (over the speed at every reduced reach), `fast` (over the speed at every reduced reach), `narrow+fast` (over the speed (not fitted)), `wide+fast` (over the speed at every reduced reach) |
| target_orbit | `wide` x1.3 | `fast` (over the speed at every reduced reach), `wide+fast` (over the speed at every reduced reach) |

On `family_rig` (nothing fitted) gate time is unchanged (5.40/3.21/3.10 s ->
5.42/3.34/3.21 s at 79.5/120/170 BPM).

**Tests** (`tests/integration/test_mh_variant_fitting.py`, all on narrowed rigs):
reach-only ladders and floors per variant; a fitted patch keeps the catalog period;
on 150 degree/s heads at 79.5 BPM in 4/4 and 3/4 the cascades' fitted `fast` reveals on
exactly the frames the catalog `fast` does on fast heads, never a frame over the speed;
fit, cause and strength in offer, trace and repair; a range-forced fit says so; a
repositioning failure is not fitted; no two offered variants alike; FASTER to a narrower
reach; fitted strength is identity; a hair's breadth either side of 140.48 degree/s;
`zoom_wave` on a zoom rig narrowed to 10..38 (admitted; its `wide` fitted at 60 degree/s).
`tests/unit/sequencer/moving_heads/test_seen_rule.py`: moved for brevity, traced brief,
kept on a well-shown beat, each with repair agreeing.

## Variant fitting (after 2c961b58)

**Why.** On the owner's 150 degree/s heads at 79.5 BPM the gate refused most variation
variants (cascades `wide` by 0.1 % of the speed limit, `fast`), so chorus_1's WIDEN and
break's FASTER played base. Integrator decision: variants are fitted to the rig by code.

**Built** (`sequencer/moving_heads/fitting.py`, the gate in `pipeline.admit_templates`):
a variation variant of a template whose ladder passes that fails the gate (it differs from
its base only in extents and period, so it fails on a speed, a range or a repositioning)
is retried at reduced strengths, strongest first, and admitted at the first that passes:
reach x1.4, x1.3, x1.25, x1.2 of the base's extent (each widened extent the same share of
the way from base to the catalog's x1.5); rate on the next whole beat longer than the
catalog's period, up to 3/4 of the base's (a 4-beat movement: 2, then 3 beats; the snap's
1-beat move has no such beat, so its `fast` is never fitted); a combination reach-major
(every rate at x1.5, then at x1.4, ...). Narrowing and slowing parts keep their values.
Below x1.2 reach or 3/4 of the period nothing is offered; the "plays the same as base"
check applies to fitted variants too. Fitted patches are derived in code from the base
and the catalog target. `TemplateOffer.fitted` carries the strength; the render plays the
fitted preset (`_section_preset`), its strength is in the fingerprint (a substitution
`"wide fitted {...}"`), the trace says it (`section_looks[].fitted`), the planner prompt
lists fitted variants, and repair records each part that plays one. A variation that
does not play now also warns in the trace's diagnostics. Revision 15; pins re-recorded
fingerprint-only, every frame held.

**Also:** `full_travel_ms` (W8) now divides the operable range by the speed: on
`allowed_rig` pan 750 → 396 ms, tilt 375 → 174 ms (the owner's reported 3600/1800 ms
become about 1977/847 ms); unchanged on rigs whose allowed range is the physical one.

**Admission on `allowed_rig` at 150 degree/s** (synthetic; the owner's geometry differs,
so the variants refused there differ in detail):

| BPM | Fitted | Not offered (why) |
|---|---|---|
| 79.5 | cascades `fast` 3-beat, `wide+fast` x1.2 / 3-beat; `mirror_wings`, `target_orbit` `wide+fast` 3-beat; snap `wide+fast` x1.25 | snap `fast` (plays as base) |
| 120 | cascades `narrow+fast` 3-beat; `masked_wheel_flick` `wide+fast` 3-beat; `mirror_wings` `wide` x1.3, `fast` 3-beat; `target_orbit` `fast` 3-beat, `wide+fast` x1.4 / 3-beat | cascades `wide`, `fast`, `wide+fast`; snap `fast`, `wide+fast`; `mirror_wings` `wide+fast` — over the speed at every strength (the cascades' base already moves at ~the limit: x1.1 still exceeds it) |
| 170 | cascades `wide+slow` x1.4; `masked_wheel_flick` `fast` 3-beat, `wide+fast` x1.25 / 3-beat; `mirror_wings` `narrow+fast` 3-beat; `target_orbit` `wide` x1.3, `fast` 3-beat | most `wide`/`fast` (over the speed at every strength; the cascades' and `mirror_wings`' own base fails here, they play `narrow`); `masked_wheel_flick` `wide` (dark repositioning) |

Gate time on that rig: 4.62 → 6.11 s (79.5), 2.13 → 2.89 s (120), 1.31 → 1.83 s (170);
on `family_rig` (nothing fitted) unchanged (5.40 → 5.39, 3.21 → 3.19, 3.10 → 3.13 s).
Byte matrix (567 configs, 13,041 renders) against the W10b/c baseline: frames, segments,
`.xsq`, `.xmap`, normalised trace and record, and gate data identical.

**Tests** (`tests/integration/test_mh_variant_fitting.py`, all on `allowed_rig`): the
ladder's order and minimums; a fitted patch derived from base and target; on 140 degree/s
heads at 79.5 BPM the cascades play `wide` at x1.4 and `fast` on 3 beats (the strongest
passing; synthetic geometry needs 140 where the owner's needs 150), visibly wider (pan span
over x1.2 the base's) and unlike base, never a frame step over the head's speed plus one
word, named in the offer, the trace and repair; the fitted strength is render identity; a
fast enough rig fits nothing. `test_the_offer_times_a_full_crossing_over_the_allowed_range`.

**PENDING-OWNER:** does a fitted x1.2-x1.4 reach or a 3-beat rate still read as the
variation asked for?

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

All open owner questions are collected in one list:
[owner decisions pending](../../plan/owner-decisions-pending.md).

1. Look: does a WIDEN / FASTER variation read as "the same idea, bigger / quicker"
   across templates (verse_2 → chorus_1, break, chorus_2 on the owner song)?
2. Look: is "only reach and rate carry a motif across templates" enough to read as a motif?
3. Look: the off-grid case (WIDEN from an introduced `wide` plays `wide`): acceptable, or
   step the other axis?
4. The snap family's rate (design note above).
5. The lost "build" arc: with every carrier one step from the introducer, a last chorus
   cannot go further than the first (two WIDENs play the same). Acceptable, or should a
   later carrier be allowed a second step?
