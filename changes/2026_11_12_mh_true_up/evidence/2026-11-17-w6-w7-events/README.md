---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W6 and W7 — the plan's events and lyric cues rendered; intensity re-review fixes

**Provenance.** Implemented by an executor agent on 2026-11-17 in the worktree
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`, from `7c6c2b08`. Uncommitted; the
integrator commits. Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md),
tasks W6 and W7, under the owner's ruling that song intent is rendered, never cut (the
owner has called the absence of event rendering a hard fail). Also, as a separate part
(§ Intensity re-review fixes), the second independent review of W5 (`7c6c2b08`), items
N1–N6. No provider call, no network, no xLights, nothing under `~/xlights`, `data/` or
`artifacts/`; every rig, song, plan and palette here is synthetic or the repository's
catalog. The owner's test-song plan was read (read-only) for its shape only; the fixture
built from it is synthetic. `make validate` was not run (reserved for the integrator);
the commands it wraps were run one by one (§ Verification).

**The owner has not seen any of it**: the W6/W7 view is pending (§ What the owner should
look for). Every value in the tables below is a first proposal for that view.

## What was built

| Area | Change |
|---|---|
| `sequencer/moving_heads/events.py` (new) | The one resolver for events: the tables, `section_events` (a plan section's events on the grid), `apply_section_events` (closed/open, strobes, pulse, colour and gobo events, inside the section compile), `apply_hits` (after intensity), the trace helpers (`cue_summary`, `events_message`, `describe_events`, `describe_lyric_cue`) |
| `sequencer/moving_heads/pipeline.py` | Per part: the plan section's events, carried wheel states from an earlier part merged into the held states, `apply_section_events` after the show's rests inside `compile_section` (so every W4 recompile replays them), the event wheel channels in the boundary's intent channels and the events' final states in the next boundary's; hits after intensity; trace `section_looks[].events` and `lyric_cues`; a warning per section where an event did not play as asked; the "not rendered yet" diagnostic no longer lists events, their cue binding or moment cues; `rendered_palettes` also counts a palette-role colour event; a wheel turned in a gap is checked against the transaction pass (`entry_feasible`) |
| `song_intent.py` | The rate tables (`STROBE_FLASHES_PER_BEAT`, `PULSE_PERIODS_BEATS`), `flash_widths`, `strobe_flashes`, `pulse_period`, `can_darken`; `RigOffer.dark` and `RigOffer.flash_ms`; the prompt's `events` block (`_events_for_prompt`); `RENDERED_INTENT_FIELDS` gains `events` and `moment_cues`; `describe_look` adds the event lines |
| `agents/.../models.py`, `moment_cues.py` | `PlanEvent.cue_emphasis` (code-owned, `SkipJsonSchema`: not in the response schema, whose pinned hash is unchanged), set by the binder for a bound event, cleared for every other; N6 (§ below) |
| `agents/.../rig_repair.py` | `_event_records`: an event the render plays other than asked is kept and recorded (strobe or pulse slower at this tempo or not at all, a hit on heads without a dimmer or on a beat its template is dark on, a wheel change too soon after the previous one) |
| Prompts | Planner user prompt: the "Events" block of What This Rig Can Show (what each action plays at the song's median beat); developer prompt: what each action plays, and that a kept-but-different event is reported; judge: such an event is the rig's limit, not an ignored moment; N5 wording (§ below) |
| Reporting | `eval-report` `played` lines gain one per event and one per lyric cue of the section; `not_rendered` and the vision judge's `not_rendered_yet` no longer list events or moment cues |
| `identity.py` | `RENDERER_REVISION` 7 → 8 |
| `intensity.py` | N1–N4 (§ below) |
| Tests | `test_events_render.py` (new, 27 tests, 32 cases), event repair, offer and prompt tests, the intensity re-review tests, the event pins, the parity file's `PENDING` and rig tags, the ledger (`strobe` now plays a frame) |
| Docs | User guide § "How a section's events reach the lights" and the passages that listed events as not rendered or described intensity's threshold; developer guide, overview, QA runbook, README, glossary, product overview, multi-agent planning, `context/current-state.md`, the plan's W0 table |

## Each action (the tables, `events.py` / `song_intent.py`)

Every event lands on the frame nearest its beat (the beat's time quantised as the
compiler places a template's own beat edges), per head, inside its section; the trace
records, per event and head, what played (time, shape) or why not.

| Action | Plays | Values (proposed) |
|---|---|---|
| `closed` | dark from the beat until the next shutter event (`open`, a strobe, `pulse`) or the section's end, commanded on the cue's own path by the W4 machinery (`_dark_over_spans`: the dimmer at zero where it extinguishes, else the closed shutter). **Decided:** a `closed` without `open` holds to the section's end, across its later parts, as the old renderer held it; the next section plays as authored | — |
| `open` | ends a `closed`, strobe or `pulse`; recorded per head | — |
| `strobe_slow/_medium/_fast` | from the beat to the next shutter event or the section's end. A head whose shutter has a state tagged for that speed: the shutter at that state on its lit frames (a frame the template holds closed stays closed), if every change holds its settle around the template's own shutter changes. Otherwise a square wave on musical time, **dark first** (the first dark frame is the beat's, as the parity row asks; the flashes fall between the subdivisions), through the dimmer where its zero extinguishes, else the closed shutter | flashes per beat 2 / 4 / 8 (eighths, sixteenths, thirty-seconds); each phase boundary on the frame nearest it |
| — slowed | a rate whose half period is shorter than the darkness path follows halves (8 → 4 → 2 → 1), recorded `degraded`; below one a beat, not played, recorded | dimmer: one frame, or `ceil(1000 / travel_speed_per_s)` ms (a full swing); shutter: close latency + closed settle, open latency + open settle, frame-rounded |
| `pulse` | lit for the first half of each beat, dark for the second, from the beat to the next shutter event or the section's end; reveals on the beats | period 1 beat (2, 4 where the path cannot follow), duty 0.5 |
| `hit` | see § The hit | `HITS` below |
| `color` / `gobo` | the held colour (pattern) changes at the beat, resolved as the section's (palette role or named colour → nearest offered state of the template's heads; pattern → its tagged state), until the next such event or the section's end; carried into later parts as their held state | dark lead = the wheel change time (`wheel_change_ms`) |

**Wheel event placement, in order** (`events._turn`): (1) the cue before the beat
carries the dark lead: `_dip_span` rides darkness it already commands (a `closed`, a
template's dimmer dark) and adds at most half the beat before the beat (`dark_dip` with
`added_ms`), the wheel turns `settle` before the beat and the head reveals on the beat;
(2) the head is dark on the beat (between its template's cues: a cascade's dark phase, an
overlay mask) or the beat starts a cue after a gap: the cue after the gap holds the new
state and the transaction pass turns it in the gap, **if `entry_feasible` says the gap
still fits** (without that check a 160 ms gap with a 300 ms settle refused the render:
`RenderRefusedError … needs 380 ms … has 160 ms`, reproduced in scratch
`gap_without_check.py`); (3) else the first dark window after the beat long enough
(before the next event of that wheel), recorded `deferred` with `late_ms`; (4) else not
played, recorded. Inside a template overlay (`masked_wheel_flick`'s flick) the event
takes over the overlay's state from the beat for the rest of that flick; later flicks
play as authored. At a part's first frame the boundary machinery (W4) turns it: the
event's channel joins the boundary's intent channels.

### Worked example in frames (MH1, `mirror_wings`, 4/4, first beat 15 ms off the grid; scratch `w67/tempo_examples.py`)

Bar 3 beat 1: 120 BPM at 4015 ms → frame 4020; 78 BPM at 6168.8 ms → frame 6160. `D` dark,
`L` lit, from two frames before the beat, an `open` at bar 4 beat 1:

| | 120 BPM (beat 500 ms), frames 3980… | 78 BPM (beat 769 ms), frames 6120… |
|---|---|---|
| `closed` | `LLDDDDDDDDDDDDDDDDDDDDDDDDDD` | `LLDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD` |
| `strobe_slow` | `LLDDDDDDLLLLLLDDDDDDDLLLLLLD` | `LLDDDDDDDDDDLLLLLLLLLLDDDDDDDDDLLLLLLLLLL` |
| `strobe_medium` | `LLDDDLLLDDDLLLDDDLLLLDDDLLLD` | `LLDDDDDLLLLLDDDDDLLLLLDDDDDLLLLDDDDDLLLLL` |
| `strobe_fast` | `LLDLLDLLDDLDDLDDLDDLLDLLDLLD` (31 ms phases: 1–2 frames) | `LLDDDLLDDDLLDDLLLDDLLLDDLLLDDLLDDDLLDDDLL` |
| `pulse` | `LLLLLLLLLLLLLLDDDDDDDDDDDDDL` | `LLLLLLLLLLLLLLLLLLLLLLDDDDDDDDDDDDDDDDDDD` |

Colour event (red, at bar 3 beat 1) on owner-like timings (close latency 20 ms, every
state settling in 150 ms: a 180 ms change, inside half a beat at both tempos):

| | 120 BPM | 78 BPM |
|---|---|---|
| dimmer 0 (dark commanded) | 3840 ms (beat − 180) | 5980 ms |
| wheel white → red (optically dark) | 3860 ms | 6000 ms |
| settled, revealed red at full | 4020 ms (the beat's frame) | 6160 ms |

## The hit (`events.apply_hits`, `HITS`)

| Emphasis (the bound lyric cue's; unbound `MED`) | Contrast into the beat | Decay |
|---|---|---|
| `LOW` | 0.25 of the top | 0.25 beat |
| `MED` | 0.40 | 0.5 beat |
| `HIGH` | 0.60 | 0.75 beat |

Pre-dip: over the quarter beat before the beat (at least two frames), easing as `s²`;
never dark; only on lit frames of the same run and inside the section.

**Design at full level, and how it follows the intensity level.** A hit reads the level
the section plays (`L`, after intensity) and writes: the dimmer's top on the beat's frame;
after it `L + (top − L)(1 − p)²` over the decay (`p` the share elapsed, never below `L`);
before it, where `top − L(beat − 1 frame) < contrast × top`, a pre-dip to
`top × (1 − contrast)`, never deeper than the level already is (`min`). So:

- **at full** (every catalog family as authored): `L` = top, so the hit is the pre-dip
  and the snap back to full on the beat (120 BPM, MED: `255, 255, 252, 244, 230, 210, 184,
  153 | 255, 255, …`); a HIGH cue cuts to 102 (40%);
- **below full** (a template's lower level, or the headroom variant's 0.82 identity
  levels): the hit rises above the section's level and decays back (half level, MED at
  120 BPM: `128 … 128 | 255, 231, 213, 197, 183, 170, 159, 150, 142, 136, 132, 129, 128`);
  under the headroom variant this happens without any code change, because the hit
  follows `L`;
- **with DRAMATIC/INTENSE**: an accent already puts the top on an accented beat; the hit
  is the same one accent (no second peak; frames after it never fall below intensity's
  own, and fall monotonically to the next beat); its pre-dip is never deeper than where
  intensity already sags (120 BPM INTENSE + HIGH: `163, 161, 157, 151, 142, 131, 118, 102 |
  255, 254, 251, …` against INTENSE alone `163, 161, 159, 157, 156, 154, 154, 153 | 255,
  247, 239, …`).

**On a dark beat.** Per head: lit on the beat's frame (or one of the two after: a
template's envelope starts its lit window on the first frame at or after its phase) for at
least three frames → plays there (`HIT_LATE_FRAMES` 2, `HIT_MIN_LIT_FRAMES` 3: a hit on a
lit window's last frames would flash and go dark, the N1 problem). Dark through the dimmer
inside a cue (a `closed` event, a template's dimmer at zero), the shutter open, no wheel
moving in that dark run, not a show's rest, and the close latency plus a frame left dark
after → **lit for the hit**, easing back to dark (`lit_from_dark`). A hit is one moment for
the rig: heads dark there between their template's cues (they reposition or turn a wheel)
do not play it, recorded. **Only where no head can show it on its beat** does it move, on
every head, to the nearest beat within a bar inside the part (ties later), recorded
`moved`; else not played.

**Decided differently from the brief:** the brief says a template's own dark phase lights
for the hit. A cascade's dark phases and an overlay's masks are gaps between cues where
the transaction pass repositions the head or turns a wheel; lighting there breaks the
dark-transaction rule, so those heads do not play it (or, where every head is dark, the
hit moves). A template's dark phase *inside* a cue (dimmer at zero) does light for the
hit.

## Composition order (as built)

1. template compile with the section's held colour/gobo (W4) and overlays;
2. the show's rests (`dark_spans`) on the cues' paths — before events, so no event can
   relight a rest (the brief listed rests after events; this order gives the same frames
   and needs no special case);
3. shutter events (`closed`, strobes, `pulse`), then colour and gobo events in time
   order (a change rides a `closed`'s darkness) — steps 1–3 are `compile_section`, which
   W4's retries recompile, so events replay identically;
4. W4: overlay fallback, boundary dips, deferrals, kept states; entry windows;
5. intensity shaping per lit run (W5, N1–N4);
6. hits, on the level the section now plays;
7. the transaction pass and the encoder.

Events never move a wheel while lit (checked by an independent reader on every test
render, the realistic plan and every plan-C render of the byte matrix), never fight a
rest, stay in their section (a part's carry-over is the section's), and an event at a
part's first frame turns through the boundary machinery.

## Repair and degradation rules

| Case | Render | Plan repair (`_event_records`, fed back) |
|---|---|---|
| Strobe speed the rig's tags lack | square wave (dimmer or shutter) | — (not a repair) |
| Strobe/pulse faster than the darkness follows | slower rate, `degraded` | recorded with the rate it plays |
| Darkness cannot flash at all, or no head can go dark | not played | recorded |
| Hit on heads without a dimmer | not played there | recorded |
| Hit on a beat every head is dark on | moved to the nearest beat within a bar | recorded from the published dark phases (frame tolerances as the render) |
| Hit on a beat some heads are dark on | plays on the lit ones | recorded |
| Colour/gobo the part's template cannot show | not played on that head | W3 rules (dropped where no head shows it) |
| Colour/gobo too soon after the previous | late or not played | recorded (gap < slowest head change) |
| Colour/gobo that cannot dip | turned in the gap / next dark window (late) / not played | the W4 boundary rule for section starts |

The plan keeps every event (the render decides and traces). The gate's admission and
entry-dip bound are unchanged for every rig and plan (byte matrix: gate identical in
405/405). The published dark phases come from the gate's bar-1 compile and miss a cycle's
leading darkness, so the hit repair can under-report (seen on `fly_in_cascade`, bar 45
beat 3 below); it never refuses.

## The realistic plan (the owner's test song's shape, synthetic)

Fixture (`test_events_render.py`, `REALISTIC`; scratch `w67/naf.py`): 78.3 BPM, 62 bars,
the family rig with a colour wheel of 11 tagged colours, a gobo wheel of `open` only, no
strobe states, close/open latency 20 ms, every wheel state settling 150 ms, dimmer
extinguishes; no macro palette (the fixed role table: PRIMARY red, ACCENT magenta, WARM
amber → nearest **orange**, NEUTRAL white); lyric cues 40 ms after their beats, bound by
the binder. No gate (the test); the scratch probe ran the gate and repair too.

| Section / event | What plays (every head unless named) |
|---|---|
| intro (`target_orbit`, SLOW) `closed` 7.3 | dark from 19940 ms to the section's end (30660 ms) |
| intro `hit` 8.2, HIGH cue | inside the `closed`: **lit for the hit** from the dark at 22240 ms, 255 easing to dark over 0.75 beat (28 frames), dark again |
| verse_1 (`masked_wheel_flick`) colour WARM 15.4, MED cue | orange revealed on the beat (45220 ms): MH1, MH3 (flick red = section red, no mask) after a 180 ms dark dip; MH2, MH4 (flick blue) **take over their flick**, the transaction turning red → orange in the mask gap before it |
| verse_1 `pulse` 18.1 | a dimmer pulse, lit the first half of every beat, 52120 ms to the section's end |
| verse_2 (`target_orbit`, FAST) `hit` 21.1 | every head repositions dark into the section on 21.1: **moved to 21.2** (62100 ms, the reveal), no pre-dip (dark before) |
| verse_2 colour PRIMARY 30.1, HIGH cue | red on the beat (88900 ms) after a 180 ms dip |
| chorus_1 (`fly_out_cascade`, DRAMATIC) hits 32.1, 36.1, 40.1 | every head dark on each downbeat (the cascade's dark phase; 32.1 also the entry): **moved to beat 2** (95820, 108080, 120340 ms) on MH1, MH4 (their window opens there); MH2, MH3 dark then, not played. Repair recorded all three |
| break (`fly_in_cascade`, DRAMATIC) hit 44.1, HIGH cue | every head dark on 44.1 (MH2/MH3's window ends there, MH1/MH4's opens on beat 3): **moved to 43.4** on MH2, MH3 (one beat early, their window's start); MH1, MH4 not played. Repair recorded |
| break hit 45.3 | MH1, MH4 at 136440 ms (their window starts a frame after the beat's frame); MH2, MH3 dark, not played (repair did not see it: the leading-darkness gap above) |
| break hit 46.1, HIGH cue | as 44.1: **moved to 45.4** on MH2, MH3 (137200 ms) |
| break colour WARM 49.1 | MH2, MH3 orange on the beat after a 180 ms dip; MH1, MH4 dark on the beat: orange from their next reveal, 1560 ms later (recorded `late`) |
| break `strobe_medium` 52.1 | dimmer strobe, 4 flashes a beat (96 ms phases), 156340 ms to the section's end (159400) |
| chorus_2\|A (`mirror_wings`, INTENSE) hit 53.1 | on the part's first frame (159400 ms), with INTENSE's own accent there: one accent; no pre-dip (it would leave the section) |
| chorus_2\|B (`finite_snap_hold`) hit 60.2, HIGH cue | 181620 ms, pre-dip from 181440 ms to 40%, 255, decay 0.75 beat over INTENSE |
| chorus_2\|B colour NEUTRAL 61.4, MED cue | white on the beat (186220 ms) after a 180 ms dip |

Every lyric cue (7) is traced with the heads and times that played it. Every wheel byte
change is dark from the close latency before through the settle after; against the same
plan without events, every newly dark frame lies in a shutter event's span or a colour
event's bounded lead, and every newly lit frame follows a hit (both checked by
`test_the_realistic_plan_*`, reading the plan, not the trace). Look question: the
downbeat hits on the cascades land a beat away or on two heads (below).

## Intensity re-review fixes (N1–N6, review of `7c6c2b08`)

| # | Finding | Fix | Evidence |
|---|---|---|---|
| N1 (HIGH) | A beat accent on a lit run's last frame flashed full before dark (`…154, 255, 0`) | `accent_starts`: no beat accent where less than a quarter beat or three frames of the run follow it (`ACCENT.tail_beats`, `tail_frames`) | Reviewer's `tailflash.py`: before (on `7c6c2b08`) 18 template × grid × level cases (`fly_in/out_cascade` at 78, 140, 170 BPM and variable, `masked_wheel_flick` variable; 2–24 runs each); after: 0. `test_every_lit_window_of_a_cascade_comes_in_on_an_accent` over 120, 78, 140, 170 BPM and a variable grid (20 cases): the last two frames of every run never rise |
| N2 (MEDIUM) | A run starting 2–3 frames before a beat hit twice | the run's own accent gives way to a beat accent at most a quarter beat after its first frame (`near_beat_beats`); the frames before it follow the previous beat accent | `test_a_reveal_just_before_a_beat_takes_the_beat_accent` (reveal 2480 ms, beat 2520 ms: one 255, on the beat) |
| N3 (MEDIUM) | 0.84 → INTENSE mean 0.917, 0.86 → 0.638 | the headroom and full gains blended over `FULL_BLEND` = (0.8, 1.0) of the top by the run's highest level | sweep (held 0.50–1.00, steps 0.02; scratch `w67/sweep.py`): INTENSE 0.681 … 0.896 (0.80) … 0.877, 0.858, 0.841 … 0.741 (1.00); DRAMATIC 0.586 … 0.869 (0.80) … 0.795 (1.00); the largest step 0.019 per 0.02. `test_the_shaped_level_has_no_jump_as_the_authored_level_nears_full` |
| N4 (LOW) | Short flicks each got an opening accent and lost the beat | a run's own accent only after at least half a beat of darkness (`reopen_after_beats`) | `test_short_flicks_keep_the_beat`: full only on beat frames |
| N5 (LOW) | "LEAD plays one step hotter"; stranded `as_authored` bullet | user prompt and user guide: "one step up the intensity ladder … at full level more movement in the light, not more light"; the developer prompt's bullet list restored (`as_authored` in the list, the full-level paragraph after it); `context/current-state.md` "LEAD up" | prompt test |
| N6 (LOW) | `moment_cues._bind` computed the dark-from time its own way | it reads the renderer's `cue_limits` (covered span, clamped to the song and the frame grid) | `test_context_grid`: `dark from 182740 ms` (was 182750, off the frame grid) |

**Decided differently:** the band is 0.80–1.00, not the suggested 0.75–0.95: the W5
parity row on a template authored at 0.3/0.8 requires that no lit frame plays below the
authored level, so the blend may not start below 0.8. **Monotone, as asked, cannot be
met in full:** with "never below the authored level" for headroom runs and the accepted
dip-and-return at full, the floor at an authored 0.8 (≈ 0.83 under INTENSE) is above the
floor at full (0.60), so no continuous mapping is non-decreasing over 0.8–1.0. What holds:
continuous everywhere, rising to 0.8, falling smoothly from 0.8 to 1.0 (no jump). The
headroom variant (below) is monotone by construction.

**Pins:** every frame hash, `INTENSITY_PINS` included, is unchanged: N1–N4 move no frame
on the steady 120 BPM grid the pins use (the byte matrix confirms: event-free DRAMATIC and
INTENSE renders differ from `7c6c2b08` only on the variable grid, 72 of 405
configurations; identity levels in none). No intensity pin was re-recorded for frames;
the unit tests above guard N1–N4.

**H2 headroom variant** regenerated for this tree: scratch
`w67/headroom_variant.patch` (one file, `intensity.py`, +17/−11; `git apply --check`
clean; the old `w5/headroom_variant.patch` no longer applies: its context named
`HEADROOM_BELOW`). The N1–N4 logic applies to it unchanged (the start rules sit outside
the table; its identity levels' steady gains blend to the same constant), and the
reviewer's `tailflash.py` finds no tail flash on a patched copy. Mean lit levels (the
reviewer's `variant.py`, 120 BPM): `mirror_wings` as authored 0.820, DRAMATIC 0.919,
INTENSE 0.935, REST 0.698, LEAD 0.919; `fly_in_cascade` 0.820 / 0.935 / 0.935 / 0.698 /
0.935; held 0.84 → 0.690 / 0.870 / 0.891; held 0.86 → 0.706 / 0.873 / 0.890. The
product, for comparison: `mirror_wings` 1.000 / 0.795 / 0.741; held 0.84 → 0.839 / 0.850
/ 0.858, held 0.86 → 0.859 / 0.842 / 0.841 (continuous now; was 0.917 / 0.638).

## Revision, fingerprints, caches

- **`RENDERER_REVISION` 7 → 8**: a plan with events renders differently (W6/W7), and an
  intensity on a non-steady grid differs (N1–N4). Every render fingerprint changes.
- **Pins:** all 42 family pins, `MULTI_PIN`, `GATED_PIN`, `INTENT_PIN`, `FAST_INTENT_PIN`
  and the 3 `INTENSITY_PINS` re-recorded fingerprint only (scratch `w67/rerecord_pins.py`
  checks frames and `.xsq` before rewriting); every frame and `.xsq` hash unchanged.
  Combined-show golden moving-head fingerprint `de596d6a…` → `e88c6efa…`; effects and
  trace hashes unchanged.
- **New pins** `EVENT_PINS` (`test_events_on_a_tagged_rig_are_pinned`, steady grid,
  tagged family rig): `mirror_wings` with a HIGH cue-bound hit, a colour event, a gobo
  event, `strobe_fast` ended by `open`; `masked_wheel_flick` at INTENSE with a hit, a pulse
  and a `closed` to its end — `dimmer_strobe` (no strobe states: `936770…`, frames
  `333612…`, `.xsq` `762065…`) and `tagged_strobe` (a state per speed: `42eed5…`, frames
  `8c46d4…`, `.xsq` `e456c9…`). Both renders pass the independent wheel check.
- **Plans:** `PlanEvent.cue_emphasis` appears in every dump of an event (`null` unless
  bound), so a plan with events hashes differently; plans without events dump as before.
  The response schema (and its pinned hash) is unchanged.
- **Planner cache:** re-keyed for every song (prompt packs, and the offer's new `dark` and
  `flash_ms`): every song plans again once (paid).
- **Checkpoints:** palettes now also recorded for a section whose colour event names a
  palette role; older checkpoints re-render with what they recorded, and their fingerprint
  differs anyway (revision 8).

## Parity rows turned green

`tests/regression/test_mh_intent_parity.py`, xfail markers removed, no assertion changed:
`shutter_closed_open`, `shutter_strobe_slow`, `shutter_strobe_medium`,
`shutter_strobe_fast`, `shutter_pulse`, `cue_bound_shutter_event` (W6), `gobo_event`,
`gobo_two_events`, `cue_bound_gobo_event` (W7). One change in the "Plans and calls" block:
`parity_rig` tags its gobo states with their patterns (open, dots, stars), as W0
anticipated for W1's tags ("with W1's tags the rig helper carries them"); without them no
gobo is offered and a gobo event cannot play on that rig. Suite: 22 passed, 4 xfailed (W8);
`--runxfail`: the 4 W8 rows fail on their own targets.

## Byte matrix (scratch `w67/matrix_w67.py`, `compare_w67.py`)

The W5 harness with plan C carrying eight events per section on this tree (strobe, `open`,
two hits, a colour, a gobo, `closed`, `pulse`) and plan D (plan C without events) at every
level, on `git archive 7c6c2b08` and on this tree: 405 configurations (9 rigs × 3 fixture
timings × 5 grids × 3 policies), 14 renders each; final run after the last code change
(the first run found a crash on 9 waltz configurations — a `None` reveal as a time floor
— fixed, with a test, before this run).

- **Identical in all 405:** the gate (admitted, exclusions, entry dips); plans A and B
  (frames, segments, normalised record and trace, `.xsq`, `.xtiming`, `.xmap`); plan D
  (no events) as authored, SMOOTH, SLOW and FAST (the same leaves); every `.xtiming` and
  `.xmap`.
- **Plan D at DRAMATIC and INTENSE:** identical in 333, different in 72 — every one on the
  variable grid (N1–N4 move dimmer levels there; the steady, fast, edge and waltz grids are
  unchanged).
- **Plan C (events):** different in all 405 by design; **no render errored** on either
  tree; on this tree every colour and gobo byte change of every plan-C render (405 × 6
  levels) is dark from the close latency before through the settle after (an independent
  reader in the harness).

## Tests

- New `tests/unit/sequencer/moving_heads/test_events_render.py` (27 tests, 32 cases): closed/open, closed
  to the section's end; strobes at 120 and 78 BPM (dark first, 2/4/8 flashes a beat, ordered);
  a tagged strobe; a shutter-only rig (latency respected, slower rate recorded); a slow
  dimmer; pulse reveals on beats; hits (pre-dip at full, emphasis, one accent with
  DRAMATIC/INTENSE, lit from a `closed`, moved off a show's rest, a cascade, cue-bound with
  its emphasis and lyric-cue trace, a referenced cue without an event); colour and gobo
  events at 120 and 78 BPM on owner-like timings (bounded lead, reveal on the beat, held),
  successive colours, riding a `closed`, a late turn and a drop at 170 BPM, a flick taken
  over, a gap too short for the turn (no refusal under the strict policy), carry across
  parts, a part that never shows the change; the realistic plan (two tests); the
  diagnostic; palette identity for a colour event. Every wheel change is checked dark by
  an independent reader of the encoded frames.
- `test_intensity_render.py`: the cascade test over five grids (N1), N2, N3 sweep, N4
  flicks; the near-full test re-judged for the blend.
- `test_rig_repair.py` (event records), `test_song_intent.py` (offer `dark`, `flash_ms`,
  strobe rates), `test_prompts.py` (the Events block), `test_mh_state_tags.py` + ledger
  (`strobe` now changes what a section plays), `test_report.py`, `test_vision_judge.py`
  (events no longer unrendered), `test_context_grid.py` (N6), `EVENT_PINS`.

## What the owner should look for (W6/W7 view; PENDING-OWNER)

Render a song on a tagged rig with a plan that has events (e.g. the owner's test song):

1. **Hit at full level** is a dip into the beat and a snap back (120 BPM MED: about 120 ms
   from 100% to 60%, then full). Does it read as a hit, or should a hit on a full family
   do something else (e.g. a brief blackout before the beat, or the headroom variant)?
   Proposals: `HITS` contrasts 0.25/0.40/0.60, decays 0.25/0.5/0.75 beat,
   `HIT_PRE_DIP_BEATS` 0.25.
2. **Hits on cascades**: only the heads lit on the beat play it; a downbeat where the
   cascade is dark moves to the nearest lit beat (a beat early or late). Acceptable, or
   should a lyric hit light the cascade's dark heads anyway (it would show them flying
   back), or prefer the later beat?
3. **Strobes**: dark-first square waves (2/4/8 a beat). At 120 BPM `strobe_fast` alternates
   1–2 frame phases (31 ms): a hard flicker. On the xLights preview the dimmer strobe shows;
   a fixture's own strobe state does not.
4. **`closed` without `open`** holds to the section's end (decided, as the old renderer).
5. **Colour events** dip ≤ half a beat before the beat (180 ms on the owner's timings);
   a head dark on the beat shows it at its next reveal; a flick in progress is taken over.
6. **Intensity re-review**: cascades no longer flash on their last frame; a level just
   below full now pulses between the two shapes.

Proposals (all in `events.py`, `song_intent.py`, `intensity.py`): `STROBE_FLASHES_PER_BEAT`,
`PULSE_PERIODS_BEATS`, `HITS`, `UNBOUND_EMPHASIS`, `HIT_PRE_DIP_BEATS`, `HIT_MOVE_BARS`,
`HIT_MIN_LIT_FRAMES`, `HIT_LATE_FRAMES`, `ACCENT` start rules, `FULL_BLEND`.

## Cut, deferred, decided differently

- Emphasis scales hits only; strobe and pulse rates stay the planner's choice (the brief
  allowed "where sensible").
- A hit does not light a template's dark phase that is a gap between cues (honesty;
  above).
- Strobes and `closed` are not led by the dimmer's latency (a pure delay; the first dark
  command is on the beat's frame, as the parity rows ask).
- The hit repair reads the published dark phases, which miss a cycle's leading darkness:
  it can under-report; the render decides and traces.
- Composition order: rests before events (same frames, simpler); hits after intensity.
- `changes/ACTIVE.md`'s row was not touched (the integrator's).

## Verification (this tree, fresh, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 7020 passed, 30 skipped, 4 xfailed (was 6955 / 30 / 13 at `7c6c2b08`) |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 52 passed (every fingerprint re-recorded, frames and `.xsq` unchanged; 2 new event pins) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 22 passed, 4 xfailed; `--runxfail`: 4 failed (the W8 transition rows, on their targets), 22 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1305 files already formatted |
| `uv run mypy .` | No issues in 653 source files |
| Byte matrix (`w67/run_matrix.sh`, base `7c6c2b08`; `compare_w67.py`) | As § Byte matrix |
| Reviewer tools (`w5rev/tools/tailflash.py`, `shape.py`, `reveal.py`, `compose.py`, `w4low.py`) | tailflash 0 cases (base 18), shape 0 problems; outputs in `w67/intensity_rereview_tools.txt` |
| Headroom variant (`w67/headroom_variant.patch`) | `git apply --check` clean; applied to a scratch copy: tailflash 0, mean levels above |

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w67/`
(`matrix_w67.py`, `compare_w67.py`, `run_matrix.sh`, `compare_out.txt`,
`tempo_examples.py`/`.txt`, `naf.py`, `naf_out.txt`, `sweep.py`, `rerecord_pins.py`,
`record_event_pins.py`, `pin_honesty.py`, `gap_probe.py`, `gap_without_check.py`,
`render_prompt.py`, `prompt_events.txt`, `headroom_variant.patch`, `tailflash_base.txt`).
