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
  reversal or a tilt translation of the variant's path: no head moves faster, and every
  dark gap between a head's own cues keeps its time and travel.
- **The offer** (`pipeline._admit_modifiers`, one call in `admit_templates`). Per admitted
  template, each value its steps take (`modifiers.candidates`) is compiled on the
  effective variant at bar 1 over the song (range, speed, topology) and compared with the
  unmodified compile over the first bar and two cycles by the twin rule
  (`_cues_alike`: the same cues, every channel equal but the aim, every aim within
  `TWIN_POSE_DEG`); it is offered unless it fails or plays alike. On every other admitted
  variant an `aim` is excluded where that variant's compiled tilt range, moved 10
  degrees, would leave a head's operable range (`modifiers.aim_fits`, no compile). A
  spread that moves the darkness (the cascades: their lit window follows the head's
  phase) publishes each admitted variant's dark phases with it, from a compile over its
  first three cycles (checked equal to the whole-song compile's for the unmodified
  variants on six rigs and meters). New `TemplateOffer` fields, left out of dumps when
  empty: `modifiers`, `modifier_refusals`, `modifier_exclusions`, `modifier_phases`.
- **Play** (`modifiers.resolve_modifiers`, one function for the render and repair). A part
  plays each offered value that fits its variant, in the order spread, direction, aim;
  every other entry is not applied with why and the template's valid set: unknown key,
  unknown value, a second entry for a key (the first counts), not offered here (with the
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
- **Identity.** `RENDERER_REVISION` 18 (history note in `identity.py`). The modifiers each
  section plays are hashed (`render_fingerprint(modifiers=...)`, only when any play: the
  offer decides what plays and is not otherwise identity). A plan without modifiers
  renders the same frames: every pin's frames and `.xsq` hash is unchanged; the 137
  fingerprints in `tests/regression/test_mh_pins.py` and the combined-show golden's were
  re-recorded for the revision alone.
- **Prompts.** Planner `developer.j2` says what modifiers are and what each looks like;
  `user.j2` lists, per template, the values that play here (`offer_for_prompt`'s
  `modifiers`); the judge's `developer.j2` and `user.j2` mention them. Characters before
  → after: planner developer 17098 → 17544, planner user 23600 → 23850 (plus one
  rendered line per offer, about 60 characters a template), judge developer 9457 →
  9606, judge user 6397 → 6417. The offer and prompt packs are in the planner cache key,
  so every song plans again once (paid).

## The song outranks the arrangement: integration point

Not built here, by the brief: another agent is replacing `_settle_arrangement`. A part's
modifiers switch off through one hook, `RenderingPipeline._modifiers_give_way`
(`{flattened section id: "the event, in words"}`), read by `_part_modifiers`, which both
the render and `fingerprint` call; the trace then says "the part's modifiers gave way to
…" and the frames are the plan's without them
(`test_a_parts_modifiers_give_way_through_one_hook`). Until the new settling sets it, a
modifier that makes an event worse than the same plan without it still plays, and
repair does not predict such a give-way. The settling's reference render should switch
every part's modifiers off (all ids in the hook) and accept a part's modifiers as one
unit.

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

Run in the worktree after the last edit, 2026-11-18 (the worktree's `.venv` synced
offline with `--extra dev --extra anthropic --all-packages` first; it had no pytest):

- `uv run pytest -q --no-cov -p no:cacheprovider`: 7487 passed, 30 skipped (full suite).
- `uv run ruff check .`: all checks passed. `uv run ruff format --check .`: 1316 files
  already formatted. `uv run mypy packages`: no issues in 654 source files.
- New: `tests/integration/test_mh_modifiers.py`, 68 tests: per family what it takes and
  why not; what each modifier changes; the gate's offer on four rigs and tempos (3/4
  included), without a topology, and on two heads (spreads play alike, not offered); per
  family and offered value a byte change against the plan without it, on the 720°/s rig
  and the allowed 150°/s rig, every frame inside range, speed and wheel darkness; every
  admitted variant (fitted `fast` included) with one value of each key, and a WIDEN motif
  carrier; aim excluded on the snap's `wide` on heads allowed to 80°; a two-part section;
  repair = render on two plans x three meters/tempos x two rigs (unknown key and value,
  duplicates, not offered, case-blind spelling); repair reading a spread's darkness and
  the render agreeing on a hit; failed modifiers change no frame; what plays is
  identity; the give-way hook; the prompt line and the report lines. Each render test
  runs on both rigs.
- Changed: `tests/regression/test_mh_pins.py` (137 fingerprints) and
  `tests/golden/fixtures/combined_show_drop.json` (1) re-recorded for revision 18, each
  frame, `.xsq` and trace hash unchanged; `tests/unit/sequencer/moving_heads/compile/test_paths.py`
  counts the gate's placement compiles with the modifier offer stubbed (its own bar-1
  compiles are not placements).

## Known limits, for the integrator

- **Entry dips and dark-entry claims ignore modifiers.** `entry_dips`,
  `variant_entry_dips` and `RigOffer.dark_entries` are measured over the unmodified
  variants. The render sizes every entry from the poses it plays, so nothing plays wrong,
  but an aimed part enters from up to 10 degrees outside the logged dip's envelope, and
  repair's boundary predictions (`dark_entry_heads`) read the unmodified claim.
- **Placements of a modified variant are not planned again** (argued above, and covered
  by render tests on three rigs at 79.5, 120 and 170 BPM in 4/4 and 140 BPM in 3/4,
  every frame inside range, speed and wheel darkness); a `--template-dir` template whose
  dark gaps depend on where a head is at a cut could still refuse a render under
  `on_unplayable: error`.

## PENDING-OWNER

1. The aim offset (10 degrees) and whether `low`/`high` read as a lower or higher look on
   the owner's rig.
2. `wave` (a quarter cycle) and `wide_wave` (twice the template's spread): do they read
   as a wave, and a wider one?
3. `unison` on the cascades (every head lit on the same stretch) and on the wings (the
   mirror kept): the intended look?
4. `direction: reverse` on the snap drops from its lifted aim and holds low, and on the
   flick and zoom wave sways the other way first: do they read as "reversed"?
5. Whether modifiers fall under "the song outranks the arrangement" as variations do
   (the brief says yes; the hook is ready, the settling is not plugged in).
6. The cost: a paid re-plan of every song once (prompt and offer changed).
