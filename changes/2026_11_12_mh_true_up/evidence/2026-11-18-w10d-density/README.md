---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-18
updated: 2026-11-18
---

# W10d — density rendered

**Provenance.** Implemented by an executor agent on 2026-11-18 in the worktree
`twinklr-mh-density` (branch `feat/mh-true-up-p3-density`) from `08c50a92`, uncommitted;
the integrator commits and runs `make validate`. Plan:
[w10-arrangement.md](../../plan/w10-arrangement.md) §2 (its "As built (W10d)" notes record
where the build departs from it). No provider call, no network, no xLights, nothing under
`~/xlights`, `data/` or `artifacts/`. Every value is a proposal; nothing here has been
viewed (PENDING-OWNER, below).

**Test environment note.** The worktree's `.venv` lacked the `dev` extras: `pytest`,
`pytest-cov`, `mypy`, `ruff` were installed from the local uv cache
(`uv sync --extra dev --inexact --offline`); `matplotlib`, `pandas`, `pytest-asyncio`,
`anthropic`, `types-pyyaml` and their dependencies were not in the cache, so the test runs
put the main checkout's installed copies of those packages on `PYTHONPATH` (and
`types-pyyaml`'s stubs on `MYPYPATH`) from a scratch directory of symlinks. No package was
downloaded and the main checkout's environment was not changed.

## What was built

One module, `sequencer/moving_heads/density.py`, with thin call sites. Rules in full:
[user guide](../../../../docs/user-guide.md#how-a-sections-density-reaches-the-lights).

- **REST (dark).** `density.with_rest` adds a synthetic `closed` (event index
  `REST_INDEX = -1`) on the section's first beat to the section's shutter events in
  `apply_section_events`, so REST follows the closed rules; it never enters
  `events.yield_spans` (a transition does not yield to it). Same-frame precedence: the
  synthetic event sorts first, so a planner shutter event on that frame gives it an empty
  span and wins. Planner events still play (an `open` ends it, a strobe or `pulse` flashes,
  a hit lights from the dark, a colour or gobo change turns in the dark). A `closed` on a
  head without commandable darkness is now traced `not_played` instead of raising
  (`events._plan_shutter`; the same guard fixes a planner `closed` on such a head).
- **SPARSE (half the heads dark in turn).** `density.sparse_halves` splits the rig by
  folded distribution slot (even, odd), from the declared or derived topology;
  `density.play_sparse` runs after the part's events (inside `compile_section`, so every
  recompile and the boundary, deferral and transition passes see the darkness), on the
  cycle of the variant the part plays (`whole_period_cycle` over the resolved, fitted
  preset), ONCE templates lit for their first cycle; every head as BALANCED over what
  `pipeline.worse` judges an event by (`sparse_protected`, narrowed after the merge of
  f9894cc8: a strobe's or `pulse`'s first 25 frames, half a beat each side of a hit, a
  colour or gobo change's lit run); fallback every cycle → every half cycle → BALANCED,
  traced.
- **BUSY (an accent each bar).** `density.play_busy`, after the hits: per head and bar,
  the first beat lit three frames running (`events._lit_start` on the head's frames as
  played, a transition's own cues included), played with `events._play_hit` (MED, HIGH
  under DRAMATIC/INTENSE); dropped where its beat or frames fall inside a transition's
  window on that head or a planner event's widened seen span; not played where not
  visible; each traced.
- **Arrangement units (after merging f9894cc8).** `pipeline._density_units`, registered
  with `register_arrangement_units`: one unit per SPARSE or BUSY section, key
  `density:<section>`, order `(section index, 1)` (after its variation), candidate
  "planned"; at "reference" the section plays BALANCED. The render reads
  `unit_choice`/`unit_gave_way`; a section that gives way is traced "density gave way to
  <event>" (kept when a trial render is reused, `_retrace_arrangement`). BUSY gives way
  whole: `worse` names events, not accents, and the accents already keep clear of every
  event and transition, so a per-accent candidate would cost renders for nothing it can
  name. REST is not a unit. The interim `density_give_way` hook and
  `density.DensityGiveWay` are removed. `worse`'s 25-frame shutter window is
  `density.JUDGED_SHUTTER_FRAMES`, so SPARSE protects what it judges.
- **Trace.** `section_looks[].arrangement.density` per part (REST: `dark_ms`, `ended_by`,
  `lit`; SPARSE: `cycle_bars`, `alternates`, `units`, `fallback`, `lit_share`,
  `lit`; BUSY: `emphasis`, `placed`, `dropped`, `not_visible`, `no_lit_beat`,
  `no_dimmer`; a part that gave way: `gave_way`); a diagnostic where density plays
  BALANCED or leaves heads lit. `song_intent.describe_look` prints it, so the evaluation
  report's "played" lines carry it; `RENDERED_INTENT_FIELDS` lists `density`;
  `_unrendered_intent_message` no longer names it.
- **Repair** (`rig_repair._density_repairs`, after the arrangement's repairs, before the
  section's events): REST without darkness (all or some heads), a fully dark REST's
  unseen colour/gobo/intensity, REST's colour and gobo events predicted with its darkness
  (`_event_records(rest=True)`); SPARSE with no second half or no darkness, per part the
  unit it swaps on (`_sparse_misses` over the variant's published dark phases); BUSY
  without dimmers; BUSY over a quarter of the song, lowest energy first. All `recorded`.
- **Offer and prompts.** `RigOffer.sparse_halves`; `offer_for_prompt(...)["density"]`
  (darkness, halves, each template's cycle) and a **Density** entry (one line per level) in
  the planner's rig section. Planner `developer.j2` defines each level by what renders (REST dark, not
  "the heads mostly hold"); planner `user.j2` reconciles the macro "Motion density" hint
  (movement through template and variation, light through `density`); judge
  `developer.j2` and `user.j2` say what each level renders. `PlanSection.density`'s
  description and `Density`'s docstring now say the same (re-keys the planner cache).
- **Identity.** `RENDERER_REVISION` 18 at 16d1b0f6; 19 after merging f9894cc8 (which
  also took 18), with both history notes. At each step only fingerprints were
  re-recorded (every pin and the golden checked against both parents: every frame and
  `.xsq` hash equal). Pins: all 137 failing pins
  failed on the fingerprint alone and were re-recorded; every frame and `.xsq` hash is
  unchanged (`tests/regression/test_mh_pins.py`, 138 passed after). The combined-show
  golden's moving-head fingerprint was re-recorded; its effects and trace hashes are
  unchanged.

## Verification (numbers)

Per family, an 8-bar section at 120 BPM on four heads (the zoom pilot rig; the same rig
at 150 degree/s with allowed ranges narrower than physical, gated and repaired), frames
that differ from BALANCED summed over heads, and lit frames before → after:

| Family | REST | SPARSE | BUSY |
|---|---|---|---|
| finite_snap_hold | 3208 changed, lit 3100 → 0 | 1400, lit 3100 → 1700, cycle 1 bar | 208, 32 accents |
| fly_in_cascade | 800, lit 800 → 0 | 400, lit 800 → 400, cycle 2 bars | 320, 32 accents |
| fly_out_cascade | 800, lit 800 → 0 | 400, lit 800 → 400, cycle 2 bars | 320, 32 accents |
| masked_wheel_flick | 2434 (slow rig 2458), lit 2300 → 0 | 1217 (1229), lit 2300 → 1150 | 208, 32 accents |
| mirror_wings | 3204, lit 3100 → 0 | 1602, lit 3100 → 1550 | 208, 32 accents |
| target_orbit | 3204, lit 3100 → 0 | 1602, lit 3100 → 1550 | 208, 32 accents |
| zoom_wave | 3204, lit 3100 → 0 | 1602, lit 3100 → 1550 | 208, 32 accents |

Both rigs give the same numbers except where noted. No accent was dropped or invisible in
these plain sections; with events and transitions they are (tests below). SPARSE over a
part of 1-4 bars (both rigs, every family): 1 bar → BALANCED on the 2-bar-cycle families
(12) and every half cycle on the snap (2); 2 bars → every half cycle (12) or every cycle
(the snap, 2); 3-4 bars → every cycle (28); repair predicted each.

New tests (all on the fast rig and on `allowed_rig` at 150 degree/s):

- `tests/unit/sequencer/moving_heads/test_density_render.py` (REST and SPARSE, 62):
  REST dark over its section with nothing else changed; the planner's events inside REST
  (hit lit from dark, `open` ends it, `closed`, strobe); same-frame precedence for `open`,
  `strobe_medium`, `pulse`, `closed`; a colour change in a fully dark REST not seen, and
  repair saying so; REST on a head that cannot go dark (events layer and repair); REST over
  two parts; transitions into and out of REST in all six modes (window 2000 ms ± a frame,
  equal to BALANCED's; fades fall to dark by the window's end, rise from dark out of it);
  SPARSE halves alternating on the variant's cycle (mirror partners equal, lit half as
  BALANCED, every head lit), on `slow`'s cycle, half-cycle fallback, the ONCE move lit,
  one mirror pair plays BALANCED (and repair), never worse for events, a head that cannot
  go dark stays lit, transitions in all six modes keep their windows; a SPARSE or BUSY
  section `worse` faults gives way to BALANCED's frames (traced); REST is no unit.
- `tests/unit/sequencer/moving_heads/test_density_busy_render.py` (BUSY, 37): accents on
  each head's first lit beat of every bar (checked against the BALANCED frames), only the
  dimmer changing; MED/HIGH by intensity for all six levels; not-visible accents traced
  one by one (a slow dimmer); dropped inside an event's seen span and a transition window,
  events as BALANCED, windows unchanged; transitions in all six modes keep their windows;
  two parts accent every bar; the 25 % budget fed back lowest energy first.
- `tests/integration/test_mh_density.py` (156): all seven families × REST/SPARSE/BUSY
  differ from BALANCED; SPARSE lights every head on every admitted variant; repair =
  render for SPARSE's unit over 1-4 bar parts; SPARSE and BUSY leave every event as
  BALANCED (`pipeline.worse` empty) and repair's event records unchanged; the first ENTRY
  snap plays nothing under each level (render and repair); two parts each on their own
  variant's cycle; every density with motif, variation, events and each intensity level.

Every render test also asserts: no pan, tilt or zoom word outside the operable range; no
axis faster than its travel speed between two lit frames; every wheel turn inside a dark
window; and on frames lit in both, pose and wheels equal to BALANCED's.

After the last edit (2026-11-18): `uv run pytest -q --no-cov -p no:cacheprovider` 7674
passed, 30 skipped, 0 failed (18 min 47 s); `uv run ruff check .` passed; `uv run ruff
format --check .` 1318 files formatted; `uv run mypy packages` no issues in 654 files with
the `types-pyyaml` stubs on `MYPYPATH` (without them, 3 `import-untyped` errors for `yaml`
in untouched files, because this worktree's `.venv` lacks the stubs). `make validate` not
run (the integrator's). One run before the last edit failed the prompt guard
`test_deleted_prompt_contracts_and_literal_enum_fallbacks_do_not_return` (two density
values on one prompt line); the planner's rig density line became three sub-bullets and
the judge line names the looks, not the values.

## After merging f9894cc8: density in the arrangement's loop

**Strict check** (`scratchpad/w10d/strict_density.py`, adapted from the arrangement
review's `strict_worse.py` with density as the variable; an independent outcome reader on
the frames, not `worse`): 200 random plans of up to six sections of 2-6 bars, 1-3 events
each (hits, lyric-bound hits, colour, gobo, strobe, pulse, closed/open), transitions on
about a third, density SPARSE/BUSY/BALANCED, no motif or variation (so density is the only
unit), each compared with the same plan at BALANCED:

| Setup | Plans | Worse | Errors | Deterministic | SPARSE played / gave way / BALANCED fallback | BUSY played |
|---|---|---|---|---|---|---|
| plain rig, 120 BPM | 100 | 0 | 0 | 100 | 196 / 5 / 20 of 221 | 232 of 232 |
| allowed_rig at 150 degree/s, 79.5 BPM, 2 pickup beats | 100 | 0 | 0 | 100 | 211 / 3 / 7 of 221 | 232 of 232 |

SPARSE gave way to: a hit lost on a head (4), a transition that stopped playing on a head
(3), a hit played farther from its beat (1). The BALANCED fallbacks are parts too short
for either unit (repair predicts them). Mean whole-song renders per plan 5.6 (the
reference and one per SPARSE or BUSY section); final render 5.6 s against 0.9 s at
BALANCED on the plain rig, 8.8 s against 1.4 s on the slow one (four sweeps in parallel
on a shared machine).

**REALISTIC** (the owner's test song's shape, 62 bars at 78.3 BPM, owner-like rig, its
seven transitions, its events, a motif with NARROW and FASTER carriers, and SPARSE, SPARSE,
BUSY, REST, BUSY on five sections): 7 arrangement renders (the reference, 2 variation
units, 4 density units), 38.5 s wall; the same plan at BALANCED 3 renders, 14.0 s (a
shared machine). Every density unit and both variations played; REST dark.

After the merge and the wiring, last edit first: `uv run pytest -q --no-cov -p no:cacheprovider`
7678 passed, 30 skipped, 0 failed (25 min 20 s, a shared machine); `uv run ruff check .`
passed; `uv run ruff format --check .` 1318 files formatted; `uv run mypy packages` no
issues in 654 files (the worktree's environment now has every dev extra).

## After merging c2198e26: review and owner-rig fixes

Merged main at c2198e26 (934b2635: a same-playing candidate is skipped; `worse` judges a
strobe, `pulse` or `closed` over its whole traced span, counting flashes).
`RENDERER_REVISION` 20; every pin's and the golden's frame and `.xsq` hashes equal both
parents'.

- **REST hits (review HIGH).** REST enters as BALANCED would: its boundary
  (`_boundary_change`) and entry window (`_enter_section`'s `decide_on`) are decided on the
  part compiled without REST, and a cue the window leaves dark is kept
  (`apply_entry_window`'s `keep_dark`), so a hit inside REST finds BALANCED's cues. A head
  is lit for it from REST's darkness wherever its wheels hold still and its shutter is open
  around the hit (`_forced_frames`'s `local`), and a cue starting a frame or two after the
  beat counts, as for a lit head. Every head of the rig now has an outcome per hit (one
  without a cue in the part says so). The reviewer's REST plans (`density_strict.py`,
  seeds 0-59 on the plain and the slow rig, 120 plans): hits lost against BALANCED 46 head
  cases → **0** (seeds 6 and 39 of `rest_detail.py` included). Colour and gobo changes
  REST keeps unseen (104 head cases there) are by design: each head's trace adds
  `rest` ("the section's REST keeps the head dark here: …") and repair records each such
  event (it does not play, or shows from its next reveal).
- **SPARSE and transitions (owner-rig defect).** SPARSE keeps every head as BALANCED over
  the reach of the planned transitions at the part's edges, taken from the plan as given
  (`RenderingPipeline._planned`, `_transition_reach`), so the render without transitions
  keeps off the same frames and the played rule compares like with like: a transition
  plays on every head it plays on at BALANCED, and the trace is the frames'. Tested on
  target_orbit with an ENTRY crossfade (`test_sparse_keeps_off_a_transition_that_plays_at_balanced`).
- **SPARSE and a colour lit from the section before (review MEDIUM-1).** Where an earlier
  part's colour or gobo change is still lit as the part starts, every head plays as
  BALANCED until its first dark frame.
- **SPARSE and the new `worse`.** Strobes and pulses are protected over their whole span
  (`worse` counts their flashes there), replacing the 25-frame window.
- **BUSY and transitions (review MEDIUM-2).** Accents are decided once, on the plan
  without its transitions: in the render an accent plays only where that render placed it,
  and is dropped inside a transition only on a head the transition plays on. Played status
  under BUSY equals BALANCED's (`test_busy_never_changes_what_a_transition_plays`).
- **Mirror pairing (review LOW).** SPARSE's darkness is one span list per half, so mirror
  partners get the same spans. On masked_wheel_flick with a section colour the partners'
  own masks differ (the `flick` preset gives alternate heads different states, so their
  overlay masks fall differently), and so do their whole dark masks; with no colour they
  match. Not SPARSE's doing.
- **Lit share.** The trace says what it measures (`lit_share_of`: the part's frames as
  compiled, before its entry window, transitions, intensity and hits), which is why the
  owner-rig frames read lower.
- **One trial for every unit.** Where a density unit is in the plan, the arrangement first
  tried every unit on its first candidate at once (`ArrangementUnit.together`, 2484b50d);
  where that played nothing worse one trial settled it. A plan without density built unit
  by unit as on main: 80 random variation plans rendered the same frames as c2198e26
  (`varhash.py`, below). Superseded after merging cd13034a, whose optimistic first trial
  does the same for every plan; `together` is removed (below).

**Numbers after these fixes.**

| Check | Result |
|---|---|
| `strict_density.py` (as above, 200 plans) plain rig | 0 worse, 0 errors, all deterministic; SPARSE played 177, gave way 0, BALANCED fallback 44 of 221; BUSY played 232 of 232; mean 2.0 arrangement renders a plan |
| `strict_density.py` allowed_rig 150 degree/s, 79.5 BPM | 0 worse, 0 errors; SPARSE played 187, gave way 2 (a hit lost, a hit farther from its beat), fallback 32 of 221; BUSY 232 of 232; mean 2.1 renders |
| reviewer's `density_strict.py` plans (seeds 0-59 × plain and slow) | REST: 0 hits lost (was 46 head cases); SPARSE and BUSY: 0 worse plans (SPARSE was 2) |
| 80 random variation plans without density, frames against c2198e26 | 80 of 80 identical, 625 renders on both |
| REALISTIC (as above) | 2 arrangement renders, 9.7 s wall (was 7 renders, 38.5 s); the same plan at BALANCED 3 renders, 11.8 s |

SPARSE's BALANCED fallbacks rose (20 → 44 of 221 on the plain rig) because short parts are
now covered by what they must keep (a planned transition's window at each edge, a
strobe's or pulse's whole span, a colour's lit run): nothing is left to darken, traced
"nothing would go dark". Its give-ways fell to 0 and 2.

After the last edit (merge of c2198e26 and these fixes): full suite 7696 passed, 30
skipped, 0 failed (20 min 31 s); `ruff check .` passed; `ruff format --check .` 1318
files formatted; `mypy packages` no issues in 654 files.

## After merging cd13034a

Main's `_choose_arrangement` tries every unit as planned in one trial first (accepted whole
where `worse` finds nothing worse; `_greedy_only` for tests), which replaces this branch's
`ArrangementUnit.together`: removed. `worse` also flags a strobe or pulse whose first
flash on a head comes later; SPARSE already keeps every head as BALANCED over a strobe's
or pulse's whole span, so its first flash never moves, and BUSY's accents never darken a
frame. `RENDERER_REVISION` 21 (main took 20); fingerprints re-recorded only.

## Not built, or not as asked

- **Per-accent give-way for BUSY** is not built: the unit interface takes whole
  candidates, and `worse` reports events, not accents (see Arrangement units).
- **REST on a rig with heads that cannot go dark** cannot be rendered end to end: the
  transaction pass refuses any render on such a rig when it parks the head after its
  last cue (`compile/preposition.py` `_dark_commands`, raised as "cannot park"). Tested
  at the events layer and in repair.

## PENDING-OWNER

1. **The meaning of density.** The owner has been asked whether density should mean light
   (as built: REST dark, SPARSE half the heads in turn, BUSY an accent a bar) or movement
   (what the prompts said before), and has not answered.
2. **Does SPARSE read as sparse, or as broken heads?** Half the heads go dark for a whole
   template cycle (two bars on six families) and swap; on a cascade a head is lit once in
   two cycles.
3. **SPARSE on `finite_snap_hold`.** Every head plays the move lit; then the static hold
   blinks pair by pair every bar (the template's one-bar cycle). On the frames this reads
   as an alternating chase on still heads; whether that is sparse or a new look is the
   owner's call. Alternative if it reads wrong: keep the hold lit on every head (SPARSE
   would then do nothing on a one-move template, traced).
4. **Is a hit every bar too much over a chorus?** BUSY puts a MED (HIGH under DRAMATIC or
   INTENSE) hit on each head's first lit beat of every bar.
5. **REST as full darkness**, the whole section, events aside.
6. **SPARSE pauses after a colour change** for the change's lit run: on a template lit
   throughout (mirror_wings), SPARSE stops after a colour change until the template next
   goes dark. Narrower is not possible without giving way: `worse` counts any shorter
   lit run as "shown more briefly", so the whole section would play BALANCED instead.
7. **SPARSE swaps are hard cuts** (owner-rig render): on one frame one pair goes from full
   to dark as the other comes in at full. Keep the hard swap, or a short cross-dip?
8. **BUSY accent shape and depth.** It is the planner's own hit (`events._play_hit`, as
   `apply_hits` plays it) at MED (HIGH under DRAMATIC or INTENSE): with room before the beat
   a pre-dip and a snap to full; at a cascade's window start (dark before the beat) a flash
   and a duck, e.g. `255 255 255 255 90 87 84 81 91 101 … 195` on the owner's rig: four
   frames at full, a duck to 35 % recovering over about half a beat, which is the HIGH
   shape (contrast 0.60, four frames, decay 0.75 beat: those sections are DRAMATIC or
   INTENSE; MED is 0.40, three frames, half a beat), in chorus_2 under INTENSE a dip to 26
   then full. Is that shape and depth right for an accent every bar?
9. **SPARSE's lit share** is traced on the part's compiled frames; say if the trace should
   count the frames as delivered instead.
