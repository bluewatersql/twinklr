---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-18
updated: 2026-11-18
---

# W10e — a part's modifiers rendered

**Provenance.** Implemented by an executor agent on 2026-11-18 in the worktree
`twinklr-mh-modifiers` (branch `feat/mh-true-up-p3-modifiers`) from `08c50a92`,
uncommitted; the integrator commits. Plan: [w10-arrangement.md](../../plan/w10-arrangement.md)
§4 (its "As built" note records the departures). No provider call, no network, no
xLights, nothing under `~/xlights`, `data/` or `artifacts/`; `make validate` not run (the
integrator's). Every value is a proposal; nothing here has been viewed (PENDING-OWNER,
below).

## What was built

- **A closed set, computed in code** (`sequencer/moving_heads/modifiers.py`) on the
  variant a part plays, its preset applied, fitted or not; `PlanModifier{key, value}` and
  the contract are unchanged (the key stays a free string, read case-blind):
  - `spread`: the phase distribution that owns pan and tilt. `unison` (spread 0, a
    two-winged template keeps its mirror), `wide_wave` (spread x2), `reversed` (the
    wave from the other end) where the heads move in a wave; `wave` (a new quarter-cycle
    distribution over pan and tilt) where they move together.
  - `direction: reverse`: a time reversal of the path: `PathTransform.reverse` on the
    circle and the figure-eight, the extent negated on a sway (and on its sine zoom, so
    the beam stays widest at the same side), start and end swapped on a finite move. A
    periodic sweep has none (`Movement` refuses it: it runs the same both ways).
  - `aim: low | high`: every step's start tilt -/+10 degrees.
  No key duplicates a typed field (reach and rate are `variation`; colour, gobo,
  intensity, events and transitions have their own). Each is a phase shift, a time
  reversal or a tilt translation of the variant's path: no head moves faster. (The first
  build also claimed every dark gap between a head's own cues keeps its travel; the review
  showed that false for gaps set in time, see "Review round" below.)
- **The offer** (`pipeline._admit_modifiers`, one call in `admit_templates`). Per admitted
  template, each value its steps take (`modifiers.candidates`) is compiled on the
  effective variant at bar 1 over the song (range, speed, topology) and compared with the
  unmodified compile over the first bar and two cycles by the twin rule
  (`_cues_alike`: the same cues, every channel equal but the aim, every aim within
  `TWIN_POSE_DEG`); it is offered unless it fails or plays alike. On every admitted
  variant an `aim` is excluded where that variant's compiled tilt range, moved 10
  degrees, would leave a head's operable range (`modifiers.aim_fits`, no compile), and a
  `spread` or `direction` where the variant has dark gaps and its first three cycles with
  the value cannot be planned (review round, below). A
  spread that moves the darkness (the cascades: their lit window follows the head's
  phase) publishes each admitted variant's dark phases with it, from a compile over its
  first three cycles (checked equal to the whole-song compile's for the unmodified
  variants on six rigs and meters). New `TemplateOffer` fields, left out of dumps when
  empty: `modifiers`, `modifier_refusals`, `modifier_exclusions`, `modifier_phases`.
- **Play** (`modifiers.resolve_modifiers`, one function for the render and repair). A part
  plays each offered value that fits its variant, in the order spread, direction, aim;
  every other entry is not applied with why and the template's valid set: unknown key,
  unknown value, a second entry for a key another entry already plays, not offered here (with the
  gate's reason), does not fit the variant played, or the part's modifiers gave way. The
  render compiles `modifiers.played_template` (the preset applied, the modifiers on top);
  with none applied it compiles exactly as before.
- **Repair** (`rig_repair._modifier_repairs`, after the motif/variation repairs and before
  events, wheels and transitions): each modifier that does not play is `recorded` with
  the render's own reason plus "the part plays without it"; the plan keeps it. Event
  predictions read the dark phases a played spread gives the part's variant: the two
  `_phases` reads now take the part's own offer (`part[3]`, the same templates for a part
  without modifiers).
- **Trace and report.** `section_looks[].arrangement.modifiers` = `{asked, applied,
  not_applied: [{modifier, reason}]}` for each part that asks any; a modifier that does
  not play also warns in the diagnostics. `describe_look` prints what plays and what
  does not; the evaluation report's template line lists the modifiers that played
  (`TemplateSelection.modifiers`, previously the plan's entries). `RENDERED_INTENT_FIELDS`
  includes `modifiers`; `_unrendered_intent_message` lists only density.
- **Identity.** `RENDERER_REVISION` 20 after the merge of `f9894cc8` (its 18 kept in the
  history note; 19 is density's). The modifiers each section plays are hashed
  (`render_fingerprint(modifiers=...)`, only when any play: the offer and the arrangement
  decide what plays and are not otherwise identity). A plan without modifiers renders the
  same frames: every pin's frames and `.xsq` hash is unchanged; the 137 fingerprints in
  `tests/regression/test_mh_pins.py` and the combined-show golden's were re-recorded for
  the revision alone (`9be42ccf` for 18, the merge for 20).
- **Prompts.** Planner `developer.j2` says what modifiers are and what each looks like;
  `user.j2` lists, per template, the values that play here (`offer_for_prompt`'s
  `modifiers`); the judge's `developer.j2` and `user.j2` mention them. Characters before
  → after: planner developer 17098 → 17544, planner user 23600 → 23850 (plus one
  rendered line per offer, about 60 characters a template), judge developer 9457 →
  9606, judge user 6397 → 6417. The offer and prompt packs are in the planner cache key,
  so every song plans again once (paid).

## The song outranks the arrangement (after merging `f9894cc8`)

A part's modifiers are one unit of the arrangement loop (`pipeline._modifier_units`,
registered with `register_arrangement_units`): key `modifier:<flattened part id>`, order
`(plan section index, 2)` (after the section's variation, 0, and density, 1), one unit
per placed part whose modifiers play as planned. Its reference plays none of them; its
candidates are `planned` (all), then, where a spread plays with other modifiers,
`without_spread` (all but the spread: the one modifier that moves a template's darkness,
so the likeliest to cost an event; aim and direction move poses only). `_part_modifiers`
reads `pipeline.unit_choice(key)`; the trace says "the modifier gave way to <event>"
from `pipeline.unit_gave_way(key)` (for `without_spread`, whose dropped spread has no
recorded event, "the modifier gave way to the song: with it an event plays worse than
without it, and the part keeps its other modifiers"). `_retrace_arrangement` rewrites
each part's modifier trace and warnings for the final choices, since a reused trial's
trace predates later decisions. Repair (`rig_repair._modifier_give_way`) compares a
section's event predictions with and without its parts' modifiers and says they "may
give way". Its colour-change records at a boundary where either section plays modifiers
end "its parts play modifiers, which this prediction does not count: the render decides
on its own frames", because the dark entries and phases it reads are measured without
them (the cheap half of closing the earlier known limit; the published dips themselves
are unchanged). The known loop bug (an equal-signature candidate breaking) did not
show in these tests: a modifier unit's candidates always differ in signature from the
accepted arrangement, since its choice is part of the signature.

**Acceptance (strict, independent).** The reviewers' `strict_worse.py`, adapted with
modifiers as the variable (scratch `strict_worse_mod.py`): 100 random plans per rig of
up to six sections over 24 bars, each section with 1-3 events (hits, cue-bound hits,
colour, gobo, strobe, pulse, closed/open), colour, intensity and transitions at random,
no motif or variation, and 1-3 offered modifiers per part; each rendered with and
without its modifiers, every event and transition per head compared from the trace and
the frames (a hit lost, farther from its cue or dimmer; a colour or gobo change lost,
later or briefer; lit frames inside a closed span, fewer in a strobe or pulse; a
transition that stops playing), and rendered twice for determinism:

| Rig | Plans | Worse | Errors | Parts: all play / spread gave way, rest play / none | Render mean (max), arrangement renders mean (max) |
|---|---|---|---|---|---|
| family rig 720°/s, 120 BPM | 100 | 0 | 0 | 470 / 54 / 76 of 600 (87% play some) | 7.5 s (14.3), 8.3 (11) |
| allowed_rig 150°/s, 79.5 BPM, 2 pickup beats | 100 | 0 | 0 | 460 / 40 / 100 of 600 (83% play some) | 10.3 s (22.7), 8.5 (13) |

Every section of these plans has events, so these are the survival rates next to
events.

**Realistic song** (`realistic_plan` on `owner_like_rig`, 62 bars at 78.3 BPM, the
reviewers' `timing2.py` with modifiers added: each part every key's last offered value):

| Plan | Wall time | Render passes | Arrangement renders | Modifiers |
|---|---|---|---|---|
| transitions + events | 3.6 s | 2 | 0 | — |
| + variation | 27.3 s | 14 | 7 | — |
| + variation + modifiers | 69.9 s | 34 | 17 | 7 parts; 3 spreads gave way (chorus_1, break, chorus_2 A), the rest play |
| transitions + events + modifiers | 45.2 s | 22 | 11 | the same |

## Review round (REVIEW.md of 9be42ccf), 2026-11-18

- **HIGH-1, fixed at the gate.** An offered `spread=wave` refused (`on_unplayable: error`)
  or darkened MH2 for 4 x 1000 ms on the flick's admitted `wide` (allowed 150°/s, 120 BPM):
  the flick's masks are set in time and the wave meets them at other poses. The gate now
  compiles every offered `spread` and `direction` on every admitted variant that has dark
  gaps (three cycles) and plans that placement (`_plan_placement`, from the song's start
  and from each first-cycle cue, as the variant's own); a failure excludes it on that
  variant ("on wide the dark repositioning between its own cues cannot be planned: MH2 cue
  at 1520 ms: infeasible_transition …"). Exempt: a spread on a template whose only darkness
  is its visibility envelope (the cascades), which follows the head's phase. The reviewer's
  `repro_high.py` now shows the wave excluded on `wide`, repair saying so, and the render
  playing without it under `error`. Test:
  `test_a_modifier_the_variant_cannot_reposition_through_is_not_offered_there`.
- **MEDIUM-1, decided at render.** A spread (or aim, or direction) can drop more of a head's
  first cue at a section's entry (fly_in_cascade + `wide_wave`: MH2/MH3's first cue in the
  entry window). How much depends on where the heads enter from (the section before, or
  the song's start), so the gate cannot decide it in general. The arrangement loop judges a
  modifier unit beside `worse` by `_darkened_by_modifiers(last accepted, trial)`: a head
  whose `dropped_cues` (entry window or unplayable) in the modified part or the part after
  it total more than in the arrangement accepted so far makes the unit give way ("the
  modifier gave way to MH2 loses 500 ms of its cues in section 'a' (dropped at its entry,
  or unplayable)"). Variations are judged as before (the clause looks only at parts whose
  modifier choice differs). Gate-decidable: range (aim), topology (wave), the repositioning
  between a head's own cues (spread, direction). Render-time: a section's entry, and any
  placement the gate's bar-1 and first-cycle checks do not cover. Test:
  `test_a_modifier_that_drops_a_cue_at_an_entry_gives_way`; the byte-change and combine
  tests now also assert `dropped_cues` equal to the plan without modifiers, the combine
  test at 79.5 and 120 BPM.
- **MEDIUM-2, hedged and modifier-aware.** `_boundary_repairs` reads the successor's dark
  phases with its modifiers (`_parts(..., plays)`) and, where either side plays modifiers,
  says the heads "may keep the previous section's colour" / the change "may wait", ending
  "its parts play modifiers, whose entries this prediction does not count: the render
  decides on its own frames". The dark-entry claims themselves are still measured without
  modifiers. `repro_q4.py` now reads "may keep" with the hedge; the render shows MH2/MH3
  blue for 980 ms, so the record is no longer a false statement.
- **LOW-1, fixed.** Only an entry that plays blocks a later one for its key ("the part
  already plays aim (high); only one entry for a key plays"); a first entry that did not
  play no longer blocks the next.
- **LOW-2** (no test bounds the offer's own compile count): not added; the gate-time
  ratio below is measured instead. **LOW-3/4** are pre-existing (unmodified plans too).


## Per-family offer

Every catalog family offers what its steps take wherever nothing stops it; the gate
stopped a value only where the rig lacks a topology (`wave`), where heads cannot show
it (two heads on a two-winged template: one slot, every spread plays alike), and on a
variant whose tilt it would push out of range. The gate on 16-bar songs
(`tests/integration/test_mh_modifiers.py` asserts each row):

| Rig, song | snap, flick, orbit | cascades (in, out) | wings | zoom wave |
|---|---|---|---|---|
| 4 heads 720°/s, 120 BPM 4/4 | spread wave; direction reverse; aim low, high | spread unison, wide_wave, reversed; aim low, high (spreads move the darkness) | spread unison, wide_wave, reversed; direction reverse; aim low, high | — (no zoom) |
| 4 heads allowed, 150°/s, 79.5 BPM | same | same | same | — |
| 4 heads allowed, 720°/s, 170 BPM 3/4 | same | same | same | — |
| zoom rig allowed, 150°/s, 120 BPM | — | — | — | spread unison, wide_wave, reversed; direction reverse; aim low, high |
| no topology, 120 BPM | direction reverse; aim low, high (`wave`: "distribution needs the rig's topology") | not admitted | not admitted | — |
| allowed, tilt to 80°, 150°/s, 120 BPM | as row 1; snap: aim high excluded on `wide` and `wide+slow` (tilt to 87.5°) | as row 1 | as row 1 | — |
| 2 heads, wings only | — | — | no spread ("plays like the template without it") | — |

Why a family does not take the rest (`candidates`, pinned per family in
`test_each_family_takes_what_changes_it_and_says_why_not_the_rest`): the cascades and the
wings and zoom wave already move in a wave (no `wave`); the cascades sweep periodically
(no `direction`); the snap, flick and orbit move every head together (no `unison`,
`wide_wave`, `reversed`).

## Gate time

Measured 2026-11-18 on this tree, the gate run with `_admit_modifiers` stubbed out
("without", the gate of `08c50a92`: nothing else in it changed) and as built ("with"),
interleaved, the best of three (two on the long songs), on a machine shared with other
agents' test runs, so the ratio counts more than the seconds:

| Rig, song | Without | With | Ratio |
|---|---|---|---|
| 4 heads 720°/s, 16 bars 120 BPM 4/4 | 4.29 s | 5.36 s | x1.25 |
| 4 heads allowed, 150°/s, 16 bars 120 BPM | 2.98 s | 3.75 s | x1.26 |
| 4 heads allowed, 150°/s, 16 bars 79.5 BPM | 6.40 s | 7.81 s | x1.22 |
| 4 heads allowed, 720°/s, 16 bars 170 BPM 3/4 | 7.04 s | 7.81 s | x1.11 |
| zoom rig, 7 families, 16 bars 120 BPM | 5.77 s | 6.97 s | x1.21 |
| 8 heads 720°/s, 16 bars 120 BPM | 7.67 s | 9.57 s | x1.25 |
| 8 heads 720°/s, 96 bars 120 BPM 4/4 | 28.04 s | 32.03 s | x1.14 |
| 8 heads 720°/s, 64 bars 120 BPM 3/4 | 30.10 s | 34.18 s | x1.14 |

The first build (every value through the full placement check and entered frames,
dark phases from whole-song compiles) measured x1.47-1.86; the cost went into the
placements and the encoder. What is left is one whole-song compile per value on the
effective variant and, for the cascades' spreads, a three-cycle compile per variant.

## Verification

Run in the worktree after the last edit of the merge with `f9894cc8`, 2026-11-18 (the
worktree's `.venv` synced offline with `--extra dev --extra anthropic --all-packages`
first; it had no pytest):

- `uv run pytest -q --no-cov -p no:cacheprovider`: 7491 passed, 30 skipped (full suite;
  only this count was written into this record afterwards, and no test reads it).
- `uv run ruff check .`: all checks passed. `uv run ruff format --check .`: 1316 files
  already formatted. `uv run mypy packages`: no issues in 654 source files.
- New: `tests/integration/test_mh_modifiers.py`, 67 tests: per family what it takes and
  why not; what each modifier changes; the gate's offer on four rigs and tempos (3/4
  included), without a topology, and on two heads (spreads play alike, not offered); per
  family and offered value a byte change against the plan without it, on the 720°/s rig
  and the allowed 150°/s rig, every frame inside range, speed and wheel darkness; every
  admitted variant (fitted `fast` included) with one value of each key, and a WIDEN motif
  carrier; aim excluded on the snap's `wide` on heads allowed to 80°; a two-part section;
  repair = render on two plans x three meters/tempos x two rigs (unknown key and value,
  duplicates, not offered, case-blind spelling); repair reading a spread's darkness and
  repair saying a spread may give way where it darkens a hit, and the render's unit
  giving way (frames as without it), or only the spread where aim plays beside it;
  failed modifiers change no frame; what plays is identity; the units a plan registers;
  the prompt line and the report lines. Each render test
  runs on both rigs.
- Changed: `tests/regression/test_mh_pins.py` (137 fingerprints) and
  `tests/golden/fixtures/combined_show_drop.json` (1) re-recorded for revision 18, then
  20 at the merge (`repin.sh`'s mapping: 175 fingerprints mapped), each
  frame, `.xsq` and trace hash unchanged; `tests/unit/sequencer/moving_heads/compile/test_paths.py`
  counts the gate's placement compiles with the modifier offer stubbed (its own bar-1
  compiles are not placements).

## Known limits, for the integrator

- **Entry dips and dark-entry claims ignore modifiers.** `entry_dips`,
  `variant_entry_dips` and `RigOffer.dark_entries` are measured over the unmodified
  variants. The render sizes every entry from the poses it plays and the arrangement loop
  judges every event on the frames, so nothing plays worse; repair hedges its boundary
  records where modifiers play, but its predictions still read the unmodified claims.
- **Placements of a modified variant are not planned again** (argued above, and covered
  by render tests on three rigs at 79.5, 120 and 170 BPM in 4/4 and 140 BPM in 3/4,
  every frame inside range, speed and wheel darkness); a `--template-dir` template whose
  dark gaps depend on where a head is at a cut could still refuse a render under
  `on_unplayable: error`.
- **Cost.** Each modifier unit is one more whole-song render per candidate (see the
  realistic song above).

## PENDING-OWNER

1. The aim offset (10 degrees) and whether `low`/`high` read as a lower or higher look on
   the owner's rig.
2. `wave` (a quarter cycle) and `wide_wave` (twice the template's spread): do they read
   as a wave, and a wider one?
3. `unison` on the cascades (every head lit on the same stretch) and on the wings (the
   mirror kept): the intended look?
4. `direction: reverse` on the snap drops from its lifted aim and holds low, and on the
   flick and zoom wave sways the other way first: do they read as "reversed"?
5. The order in which a part's modifiers give way (all, then all but the spread, then
   none), and whether the render time the units add is acceptable (realistic song above).
6. The cost: a paid re-plan of every song once (prompt and offer changed).
