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
  preset), ONCE templates lit for their first cycle; protected spans (`event_spans`,
  `shown_spans`); fallback every cycle → every half cycle → BALANCED, traced.
- **BUSY (an accent each bar).** `density.play_busy`, after the hits: per head and bar,
  the first beat lit three frames running (`events._lit_start` on the head's frames as
  played, a transition's own cues included), played with `events._play_hit` (MED, HIGH
  under DRAMATIC/INTENSE); dropped where its beat or frames fall inside a transition's
  window on that head or a planner event's widened seen span; not played where not
  visible; each traced.
- **Give-way hook (integration point).** `RenderingPipeline.density_give_way:
  dict[str, DensityGiveWay]` (`balanced`: why the section plays BALANCED; `accents`: the
  (head, frame) accents dropped, each with why). Nothing sets it yet; the arrangement's
  give-way loop is to set it (`pipeline.py`, the attribute's docstring says so).
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
- **Identity.** `RENDERER_REVISION` 18, with a history note. Pins: all 137 failing pins
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
  go dark stays lit, transitions in all six modes keep their windows; the give-way hook.
- `tests/unit/sequencer/moving_heads/test_density_busy_render.py` (BUSY, 37): accents on
  each head's first lit beat of every bar (checked against the BALANCED frames), only the
  dimmer changing; MED/HIGH by intensity for all six levels; not-visible accents traced
  one by one (a slow dimmer); dropped inside an event's seen span and a transition window,
  events as BALANCED, windows unchanged; transitions in all six modes keep their windows;
  two parts accent every bar; the 25 % budget fed back lowest energy first; the hook drops
  only the named accents.
- `tests/integration/test_mh_density.py` (156): all seven families × REST/SPARSE/BUSY
  differ from BALANCED; SPARSE lights every head on every admitted variant; repair =
  render for SPARSE's unit over 1-4 bar parts; SPARSE and BUSY leave every event as
  BALANCED (`_worse_events` empty) and repair's event records unchanged; the first ENTRY
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

## Not built, or not as asked

- **Song-outranks loop.** Not built here by instruction: the hook is in place; SPARSE
  and BUSY avoid every event by construction where they can see it. Not covered by
  construction: a hit the BALANCED render moved off its beat (SPARSE protects its planned
  beat and its transition-free frame); a transition whose played status SPARSE's darkness
  changes. The loop is to catch those.
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
6. **SPARSE gives way around a colour change** for the change's whole lit run: on a
   template lit throughout (mirror_wings), SPARSE stops after a colour change until the
   template next goes dark. Keeping it shorter would show the colour "more briefly",
   which the song-outranks rule counts as worse.
