---
type: evidence
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W8 — section transitions rendered

**Provenance.** Implemented by an executor agent on 2026-11-17 in the worktree
`twinklr-mh-true-up`, branch `feat/mh-true-up-p3`, from `0e02e969`, together with the
second review's follow-ups to W6/W7 (Part A, recorded in the
[W6/W7 record](../2026-11-17-w6-w7-events/README.md#fix-round-2-second-review-of-0e02e969-2026-11-17)).
Uncommitted; the integrator commits. Plan of record: [song-intent rendering](../../plan/song-intent-rendering.md),
task W8 and the field mapping (transitions keep their modes, their own length, the curve
as a category, the split as a category, and per-channel strategies). Read first: the W0
record's transition rows and `layer_playback.py`; the old renderer at tag
`mh-last-with-legacy-renderer` through `git show` only (`compile/transition_planner.py`:
CROSSFADE alone was split by its ratio, every other mode centred on the boundary, the mode
otherwise read only for SNAP; `compile/channel_blender.py`: the per-channel strategies).
No provider call, no network, no xLights, nothing under `~/xlights`, `data/` or
`artifacts/`; every rig, song, plan and palette here is synthetic or the repository's
catalog (the test song's transitions are taken as a shape only, on the synthetic
`REALISTIC` fixture). `make validate` was not run (the integrator's); the commands it wraps
were run one by one (§ Verification).

**The owner has not seen any of it**: every mode's look, every value in the tables below,
is a proposal for the W8 view (§ Look questions, PENDING-OWNER). Nothing here was an
acceptance verdict.

## What was built

| Area | Change |
|---|---|
| `sequencer/moving_heads/transitions.py` (new) | The window (`window_for`), what each mode does on each channel (`MODE_STRATEGIES`, per-channel overrides, `resolved_strategies`), the curve as a progress (`easing`), one head's transition (`play_head`): its own window, its dark cut, the transition's own cues, the joins the transaction pass must play, the fallbacks; the trace reader (`describe_transitions`) |
| `pipeline.py` | At each section's first part, the boundary's transition (`_play_boundary`) before the boundary dips and the entry window: the outgoing cues cut, the incoming cut, the transition's own cues entering with the incoming section; a head the transition plays on keeps its cues (`_enter_section(played=…)`) and skips the boundary's dip (`boundaries[].in_transition`); the song's last EXIT after the loop; the transition's cues darkened over show rests, left out of intensity, lit again on the outgoing look's shaped level, included in hits; `section_looks[].transitions`; the "not rendered" diagnostic lists only motif, variation, density, modifiers |
| `rig_repair.py` | `_transition_repairs`: length shortened to what the parts hold (adjusted); an EXIT the next ENTRY replaces, a strategy a channel cannot take, a lit transition across a colour or gobo change (recorded); a strategy for a channel no head has dropped (adjusted) |
| `song_intent.py` | `RigOffer.beats_per_bar`, `RigOffer.full_travel_ms` (pan, tilt: the slowest head's whole-range travel); the prompt's `transitions` (each length in ms at the median beat); `describe_look` adds the transitions; `RENDERED_INTENT_FIELDS` gains `entry`, `exit` |
| Prompts | Planner developer: what each mode, strategy, length, curve and split plays, the precedence, the dark cut, events and intensity in a window; planner user: each length in ms and the whole-range travel time; judge developer: how transitions render |
| Reporting | `eval-report` prints the transitions (`describe_look`); "not rendered yet" now says no renderer has rendered them |
| Tests | `test_transitions_render.py` (29), parity rows (4 turned green), `TRANSITION_PINS`, repair and prompt tests |

## Each mode (`transitions.py`)

The window, in beats of the song's meter from the bar's downbeat (`BEAT` 1 beat,
`HALF_BAR` half a bar, `BAR` … `EIGHT_BARS`); `split` is the share of the window the
outgoing look takes, its point the split point:

| Mode | Window | Pan, tilt (zoom follows pan) | Dimmer | Wheels, shutter |
|---|---|---|---|---|
| `snap` | at most `length` before the boundary | moved in the dark before the boundary | cut | turned in that darkness |
| `crossfade` | `split` of `length` before the boundary, the rest after | `smooth`: eased along the curve, halfway at the split point (the boundary) | `crossfade`: down to the handover level (`CROSSFADE_FLOOR` 0.5 of the lower look's level) at the boundary, up to the incoming level | a wheel that differs turns in a dark cut at the split point; shutter switches there |
| `morph` | centred on the boundary | `smooth`, halfway at the split point | `smooth` | as `crossfade` |
| `sweep` | centred | `sweep`: the outgoing aim held to the split point, then travelled to the incoming one along the curve | `sweep`: the outgoing level held, then eased with the aim | as `crossfade` |
| `fade_via_black` | `split` of `length` before, the rest after | `fade`: moved in the dark | faded to dark by the boundary, dark as long as the transaction pass needs, faded up after | turned in the dark |
| `blackout` | `split` of `length` before, the rest after | moved in the dark | dark over the window, cut in at its end | turned in the dark |

**Per-channel strategies** (`channels`): `smooth` eases the channel (halfway at the split
point); `crossfade` hands the level over (on pan or tilt it plays as `smooth`); `snap`
changes it at the split point (pan, tilt or a wheel in a dark cut there); `fade_via_black`
the same with the light fading into and out of the cut along the curve; `sequence` with the
cut made by the shutter (closed before the cut, the dimmer held; a head without a shutter
state that extinguishes cuts on the dimmer). A wheel or the shutter cannot blend: `smooth`
or `crossfade` on one plays as `snap`. Under `blackout` every strategy changes in the dark.
Each one played otherwise is traced (`strategies_played_otherwise`) and recorded by repair.

**The curve** (`easing`): a curve that rises over its cycle is the change's progress
(overshoot kept: the back, bounce and elastic easings, which the curve library's point model
refuses, are read from the easing functions its generators use); one that falls is turned
over (`square`, `pulse`); one that neither rises nor falls (`sine`, `hold`, the movement
waves, `musical_accent`) plays as `linear`, traced `curve_played`. A step curve makes a lit
jump, which the speed check turns into a dark cut (below).

**Each head's own window** stays inside the cues that run unbroken into the boundary on each
side (the transaction pass moves a head only between its cues; a lit blend across a
cascade's dark gap would ask a cue to jump), and from rest starts no earlier than the head
can be revealed. **The boundary's window** stays inside the two parts it joins, after the
previous boundary's window, before the incoming part's first event that commands darkness
or a wheel and after the outgoing part's last (the event plays; each clamp traced).

**The dark cut** lasts what the transaction pass needs between the transition's last lit
frame and its next (`worst_case_entry_ms`, recomputed on the placed cut's own poses until
it holds), placed by `split` around the split point (`fade_via_black` from the boundary,
`snap` up to it). Every join is checked with the pass's own `entry_feasible`; every frame
step of the transition's own cues, lit or dark, against the head's travel speed (and
`follow_lag`).

**Fallbacks**, per head, each traced: a move faster than the head travels moves in a dark
cut at the split point (`fallback`); a cut that does not fit the window, or a join the pass
cannot play, plays no transition on that head (`not_played`): the boundary's own entry
(its dip, its entry window). A `snap` where nothing needs darkness, or into a part the head
enters dark, plays nothing (traced `plays: nothing (…)`).

## Edges and precedence

Both edges name one boundary. Where a section's EXIT meets the next section's ENTRY, the
ENTRY plays; the trace's entry says `replaces`, repair records the EXIT. An EXIT plays where
no ENTRY follows (the same bytes as an ENTRY of the same transition there: test
`test_an_exit_plays_the_same_change_as_an_entry_and_an_entry_replaces_it`). The song's first
ENTRY and last EXIT play inside the section against the heads at rest: the run's initial
pose (`moving_heads.initial_states`), dark, with the section's own wheels (the transaction
pass turns them before the first cue); the whole length lies inside the section (from its
start; up to its last cue's end, so a section cut at the grid's end ends its EXIT there).

## Composition order (as built)

1. Per part: template compile, the section's held colour and gobo, show rests, events
   (as W6/W7); W4's boundary change (dip, deferral, kept).
2. At a section's first part: the boundary's transition: the outgoing part's cues cut at
   the head's window start (`snap`: at its darkness), the incoming cut at its window end,
   the transition's own cues between; W4's **dip** is replaced on every head the transition
   plays on (its darkness turns the wheel; a lit mode's dark cut, `fade_via_black`'s or
   `blackout`'s darkness, `snap`'s lead); W4's **deferral** and **kept** states stay (the
   incoming look already holds the old state at the window's end, so the transition plays
   lit). The incoming section's **entry window** is skipped on those heads (the transition
   was checked against the transaction pass).
3. After every section: the song's last EXIT.
4. Intensity per lit run, transitions left alone: the incoming section's first lit frame
   after the window starts a run, so it resumes on an accent. The transition is then lit
   again with the outgoing look scaled by intensity's gain on its last frame before the
   window (no jump at the window's start).
5. Hits, on the transition's cues too: a hit inside a window plays on the transition's
   level.
6. The transaction pass and the encoder.

A show's rest darkens the transition's cues (`_dark_over_spans`), before and after the
relight.

## Worked examples (MH1, owner-like rig, `finite_snap_hold` orange into `mirror_wings` blue, BAR, linear, split QUARTER)

Scratch `w8/worked_examples.py`, output `w8/worked_examples.txt`: the dimmer byte, the aim
in degrees (pan, tilt) and the colour state, sampled across each window; the boundary is
bar 5's downbeat; the colour change makes every lit mode dip dark at its split point.

```text
### 78.3 BPM, boundary bar 5 at 12280 ms
- none: no transition
  ms    [11620, 11780, 11940, 12100, 12260, 12420, 12580, 12740, 12900, 13060, 13220, 13380, 13540, 13700, 13860]
  dim   [255, 255, 255, 255, 255, 0, 0, 0, 0, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (-1, 31), (-1, 31), (-1, 31), (-1, 31), (-12, 40), (-22, 45), (-30, 43), (-34, 37), (-35, 27)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- snap: window [9220, 12280] split 12280 MH1: dark before the boundary, in place lit on its frame dark [11940, 12280]
  ms    [8980, 9220, 9460, 9700, 9940, 10180, 10420, 10660, 10900, 11140, 11380, 11620, 11860, 12100, 12340]
  dim   [255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (35, 26)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue']
- crossfade: window [11500, 14580] split 12280 MH1: the light hands over at the split point, the aim eases across; a dark cut at the split point (color turns) dark [12200, 12500]
  ms    [11260, 11500, 11740, 11980, 12220, 12460, 12700, 12940, 13180, 13420, 13660, 13900, 14140, 14380, 14620]
  dim   [255, 255, 177, 98, 0, 0, 49, 75, 102, 129, 155, 182, 208, 235, 255]
  aim   [(0, 55), (0, 55), (5, 51), (11, 47), (16, 44), (17, 35), (14, 31), (5, 35), (-7, 43), (-18, 47), (-27, 42), (-29, 29), (-25, 19), (-13, 20), (3, 33)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- morph: window [10740, 13800] split 11500 MH1: every continuous channel eases across; a dark cut at the split point (color turns) dark [11420, 11720]
  ms    [10500, 10740, 10980, 11220, 11460, 11700, 11940, 12180, 12420, 12660, 12900, 13140, 13380, 13620, 13860]
  dim   [255, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (6, 51), (11, 47), (15, 44), (19, 41), (21, 40), (23, 39), (24, 32), (19, 25), (8, 28), (-6, 38), (-20, 46), (-31, 41), (-35, 27)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- sweep: window [10740, 13800] split 11500 MH1: the outgoing look holds to the split point, then the head travels lit to the incoming one; a dark cut at the split point (color turns) dark [11420, 11720]
  ms    [10500, 10740, 10980, 11220, 11460, 11700, 11940, 12180, 12420, 12660, 12900, 13140, 13380, 13620, 13860]
  dim   [255, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (4, 52), (7, 50), (11, 47), (14, 41), (13, 34), (6, 34), (-5, 41), (-18, 46), (-30, 42), (-35, 27)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- fade_via_black: window [11500, 14580] split 12280 MH1: fades to dark at the boundary, changes in the dark, fades up dark [12280, 12620]
  ms    [11260, 11500, 11740, 11980, 12220, 12460, 12700, 12940, 13180, 13420, 13660, 13900, 14140, 14380, 14620]
  dim   [255, 248, 170, 92, 13, 0, 13, 44, 75, 107, 138, 169, 200, 232, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (18, 28), (23, 15), (8, 24), (-9, 38), (-24, 45), (-33, 39), (-34, 25), (-27, 15), (-14, 19), (3, 33)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- blackout: window [11500, 14580] split 12280 MH1: dark over the whole window dark [11500, 14580]
  ms    [11260, 11500, 11740, 11980, 12220, 12460, 12700, 12940, 13180, 13420, 13660, 13900, 14140, 14380, 14620]
  dim   [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255]
  aim   [(0, 55), (0, 55), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (0, 30), (3, 33)]
  color ['orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- first ENTRY morph BAR: window [80, 3080] MH1: comes up from rest (the initial pose, dark): every continuous channel easing
  ms    [0, 240, 480, 720, 960, 1200, 1440, 1680, 1920, 2160, 2400, 2640, 2880, 3120]
  dim   [0, 27, 68, 110, 135, 149, 163, 176, 190, 204, 217, 231, 245, 255]
  aim   [(0, 0), (3, 2), (6, 4), (2, 11), (-6, 21), (-15, 26), (-22, 23), (-23, 16), (-19, 11), (-9, 17), (5, 30), (19, 40), (31, 40), (35, 28)]
- last EXIT fade_via_black BAR: window [21480, 24540] MH1: comes to rest (the initial pose, dark): a fade, dark from the split point
  ms    [21240, 21480, 21720, 21960, 22200, 22440, 22680, 22920, 23160, 23400, 23640, 23880, 24120, 24360]
  dim   [255, 248, 163, 78, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  aim   [(31, 42), (35, 30), (31, 17), (19, 16), (2, 13), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
### 129.0 BPM, boundary bar 5 at 7460 ms
- none: no transition
  ms    [6800, 6960, 7120, 7280, 7440, 7600, 7760, 7920, 8080, 8240, 8400, 8560, 8720, 8880, 9040]
  dim   [255, 255, 255, 255, 255, 0, 0, 0, 255, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (-2, 32), (-2, 32), (-17, 43), (-31, 43), (-35, 29), (-29, 16), (-15, 18), (3, 32), (20, 44)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- snap: window [5600, 7460] split 7460 MH1: dark before the boundary, in place lit on its frame dark [7120, 7460]
  ms    [5460, 5600, 5740, 5880, 6020, 6160, 6300, 6440, 6580, 6720, 6860, 7000, 7140, 7280, 7420, 7560]
  dim   [255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (35, 30), (33, 21)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue']
- crossfade: window [7000, 8860] split 7460 MH1: the light hands over at the split point, the aim eases across; a dark cut at the split point (color turns) dark [7380, 7680]
  ms    [6860, 7000, 7140, 7280, 7420, 7560, 7700, 7840, 7980, 8120, 8260, 8400, 8540, 8680, 8820, 8960]
  dim   [255, 255, 177, 100, 0, 0, 47, 73, 98, 124, 149, 175, 200, 226, 251, 255]
  aim   [(0, 55), (0, 55), (5, 51), (11, 47), (14, 45), (15, 32), (14, 32), (6, 34), (-4, 42), (-16, 47), (-25, 44), (-29, 33), (-27, 21), (-18, 18), (-4, 27), (12, 40)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- morph: window [6520, 8380] split 6980 MH1: every continuous channel eases across; a dark cut at the split point (color turns) dark [6900, 7200]
  ms    [6380, 6520, 6660, 6800, 6940, 7080, 7220, 7360, 7500, 7640, 7780, 7920, 8060, 8200, 8340, 8480]
  dim   [255, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (5, 51), (11, 47), (14, 45), (20, 41), (21, 40), (22, 39), (24, 35), (21, 26), (13, 25), (1, 34), (-14, 43), (-26, 45), (-34, 35), (-33, 21)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- sweep: window [6520, 8380] split 6980 MH1: the outgoing look holds to the split point, then the head travels lit to the incoming one; a dark cut at the split point (color turns) dark [6900, 7200]
  ms    [6380, 6520, 6660, 6800, 6940, 7080, 7220, 7360, 7500, 7640, 7780, 7920, 8060, 8200, 8340, 8480]
  dim   [255, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (6, 51), (6, 50), (10, 48), (13, 44), (14, 36), (10, 33), (0, 38), (-12, 45), (-25, 46), (-34, 35), (-33, 21)]
  color ['orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- fade_via_black: window [7000, 8860] split 7460 MH1: fades to dark at the boundary, changes in the dark, fades up dark [7460, 7800]
  ms    [6860, 7000, 7140, 7280, 7420, 7560, 7700, 7840, 7980, 8120, 8260, 8400, 8540, 8680, 8820, 8960]
  dim   [255, 244, 166, 89, 11, 0, 0, 14, 48, 82, 115, 149, 183, 217, 250, 255]
  aim   [(0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (0, 55), (14, 19), (10, 22), (-6, 35), (-21, 45), (-32, 42), (-35, 29), (-31, 17), (-20, 16), (-4, 26), (12, 40)]
  color ['orange', 'orange', 'orange', 'orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- blackout: window [7000, 8860] split 7460 MH1: dark over the whole window dark [7000, 8860]
  ms    [6860, 7000, 7140, 7280, 7420, 7560, 7700, 7840, 7980, 8120, 8260, 8400, 8540, 8680, 8820, 8960]
  dim   [255, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 255]
  aim   [(0, 55), (0, 55), (0, 55), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (1, 30), (12, 40)]
  color ['orange', 'orange', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue', 'blue']
- first ENTRY morph BAR: window [80, 1880] MH1: comes up from rest (the initial pose, dark): every continuous channel easing
  ms    [0, 140, 280, 420, 560, 700, 840, 980, 1120, 1260, 1400, 1540, 1680, 1820, 1960]
  dim   [0, 17, 57, 97, 131, 144, 158, 171, 184, 198, 211, 224, 238, 251, 255]
  aim   [(0, 0), (2, 1), (5, 3), (3, 9), (-4, 19), (-13, 25), (-20, 25), (-23, 18), (-21, 12), (-14, 13), (-2, 24), (13, 36), (25, 42), (34, 35), (34, 22)]
- last EXIT fade_via_black BAR: window [13040, 14900] MH1: comes to rest (the initial pose, dark): a fade, dark from the split point
  ms    [12900, 13040, 13180, 13320, 13460, 13600, 13740, 13880, 14020, 14160, 14300, 14440, 14580, 14720, 14860]
  dim   [255, 243, 158, 73, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  aim   [(31, 42), (35, 30), (31, 18), (21, 16), (4, 12), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)]
```

## The owner's test song's transitions on the `REALISTIC` fixture

The transitions the test song's plan chose (shape only) on the synthetic `REALISTIC`
fixture (78.3 BPM, 62 bars, two pickup beats, owner-like rig, its events and lyric cues
bound by the binder); scratch `w8/realistic_table.py`, `w8/realistic_table.txt`; test
`test_the_realistic_plan_plays_its_transitions_honestly`.

| Section, edge | What plays (every head) |
|---|---|
| intro ENTRY crossfade TWO_BARS, ease_in_sine, HALF | from rest inside the section (1540–7680 ms): dark to the split point (the handover from a dark look is dark), then the light comes up along ease_in_sine (MH1 `0 … 8, 40, 91, 158, 234`) |
| verse_1 ENTRY morph BAR, ease_in_out_sine, HALF | the window starts on the boundary (32200 ms): the intro's `closed` runs to its end (the window yields); from dark into the flick, a dark cut at the split point (32800–33100 ms) where the colour turns WARM → PRIMARY, lit around it (`0, 3, 15, 37, 67, 0, 0, 173, 205, 231, 248, 255`); repair recorded the cut |
| verse_2 ENTRY crossfade HALF_BAR, ease_out_quad, QUARTER | starts on the boundary (verse_1's `pulse` runs to its end); the light comes up from verse_1's dark half-beat (handover from dark) along ease_out_quad; no colour turn (verse_1 ends on its WARM colour event, verse_2 is WARM) |
| chorus_1 ENTRY snap BEAT | nothing: `fly_out_cascade` enters dark on every head (traced `nothing`) |
| break ENTRY snap BEAT | nothing: `fly_in_cascade` enters dark |
| chorus_2 ENTRY crossfade BEAT, ease_out_quad, QUARTER | starts on the boundary (the break's `strobe_medium` runs to its end); a dark cut on the boundary (160940–161260 ms) for ACCENT → PRIMARY, then the light up to INTENSE's level (`215, 228, …, 255`); repair recorded the cut |
| chorus_2 EXIT blackout BEAT, HALF | the song's end: after the part's colour event at 61.4, dark over the window to rest (187780–188520 ms) |

Every transition is traced on every head; every wheel byte change is dark (the test's
independent reader). Superseded in two rows by § Fix round 1: chorus_2's ENTRY crossfade
plays on no head (its dark cut would cover the hit on 53.1, H4), and the closing blackout
starts at 188160 ms, after the colour on 61.4 has been seen (H3); the snaps are now
`nothing` by the played rule (H2).

## Repair and the planner

`rig_repair._transition_repairs` (run after the cue binder, with the gate's offer), per
transition:

| Case | Repair |
|---|---|
| An EXIT the next section's ENTRY meets | recorded on the EXIT's section: the ENTRY plays |
| Longer than the parts it joins hold, by its placement (a `snap` before the boundary; split by `split`; centred) | adjusted to the longest length that fits; where even a beat does not, recorded (the render plays what fits) |
| A per-channel strategy for a channel no head has (no colour wheel, no gobo wheel, no shutter, no dimmer) | adjusted: dropped; one only some heads have, recorded |
| A strategy a channel cannot take (a wheel or the shutter `smooth`/`crossfade`, an aim `crossfade`, any under `blackout`) | recorded with what it plays |
| A `crossfade`, `morph` or `sweep` across a colour or gobo change (the outgoing section's state at its end, after its last colour or gobo event, against the incoming's at its start, per head) | recorded: the wheel turns in a dark cut at the split point, lit around it, no transition where the window is shorter than that |

Not predicted (the render's trace says): a lit move too fast for the head (it needs both
templates' poses at the boundary, which the offer does not carry), a dark cut that does not
fit the window, a window clamped by events or the head's unbroken cues, a `snap` that plays
nothing. (Fix round 1 predicts the `snap` that plays nothing and the clamp by events seen
before the window; § Fix round 1.) The planner's prompt gives each length in milliseconds at the median beat and how
long the slowest head takes to cross its whole pan and tilt range, says what each mode,
strategy, curve and split plays, the precedence, the dark cut, and how events, hits and
intensity compose; the judge is told the same in short.

## Parity rows turned green

`tests/regression/test_mh_intent_parity.py`: `transition_in_crossfade`,
`transition_in_morph`, `transition_in_sweep`, `transition_in_fade_via_black` pass with their
markers removed (`PENDING` is empty) and no assertion changed: 26 passed, nothing xfailed;
`--runxfail` the same. The rows' windows are the old renderer's (CROSSFADE −500…+1500 ms,
the others ±1000 ms at 120 BPM), which the placement above reproduces.

## Decisions (proposals; the owner may overrule any)

1. **Both edges are one boundary; ENTRY wins** where an EXIT meets it (one defined
   precedence; the EXIT is recorded, never silently lost).
2. **Placement:** CROSSFADE, FADE_VIA_BLACK and BLACKOUT split by `split` (the old renderer
   split CROSSFADE); MORPH and SWEEP centred (as the old renderer, and the parity rows ask
   it), `split` then placing their split point; SNAP's length bounds its dark lead.
3. **SWEEP holds, then travels; MORPH eases from the start** — distinct even on a linear
   curve (the old renderer drew them identically).
4. **A wheel never turns lit**: a lit mode across a colour or gobo change dips dark at its
   split point (the plan's "falls back to a dark dip"), lit around it, rather than giving
   up the whole transition; the dark cut replaces W4's dip.
5. **Events win**: the window yields to a shutter or wheel event inside it; hits play on it.
6. **A transition is per head inside the head's unbroken cues**: on cascades it often
   plays on the heads lit at the boundary only (the others are dark there).
7. **SNAP equals no transition where nothing needs darkness** (the plain cut): it differs
   where the incoming section enters through a dark window (that darkness moves before the
   boundary) or a wheel turns. Its curve and split have no frames to shape (said in the
   prompt).
8. **At the song's edges** the other look is the heads at rest; the window lies inside the
   section.
9. **Curves** that do not rise play as `linear`; ones that fall are turned over.
10. `CROSSFADE_FLOOR` 0.5.

## Revision, fingerprints, caches

- **`RENDERER_REVISION` 9 → 10**, once for Part A and W8: a plan with transitions renders
  differently (and Part A's event changes).
- **Pins:** every pin re-recorded fingerprint only; every frame and `.xsq` hash unchanged
  (no pinned plan has a transition, or an event Part A changes). New **`TRANSITION_PINS`**
  (`lit`: crossfade, morph, sweep with a per-channel dimmer crossfade, crossfade, closing
  morph, steady grid; `dark`: fade_via_black, snap, blackout with a `sequence` dimmer,
  fade_via_black, closing fade_via_black, variable grid; both across red into blue and a
  gobo change). Combined-show golden moving-head fingerprint `8fd209c4…` → `fdc28b5b…`.
- **Planner cache:** re-keyed (the prompt packs changed, and the offer gained
  `beats_per_bar`, `full_travel_ms`, `HeadWheels.changes`): every song plans again once
  (paid).
- **Plans:** the contract is unchanged (no schema change); a saved plan with transitions
  renders anew; checkpoints re-render under revision 10.

## Byte matrix

Scratch `w8/matrix_w8.py` (the W6/W7 harness: 9 rigs × 3 fixture timings × 7 grids,
the two pickup grids among them, × 3 policies = 567 configurations), with renders added:
plan C without its transition (`cn`), plan D without its transition at every level
(`dn_*`), and plan E (eight two-bar sections, every mode in turn as an ENTRY, lengths
BEAT…TWO_BARS, five curves, four splits, colours red/blue/as authored in turn, a closing
EXIT). 23 renders per configuration, run on three trees: `git archive 0e02e969` (base),
the tree after Part A alone (scratch `w8/partA_tree`), and this tree (`w8/final_tree`, the
packages identical to the worktree's). Comparisons `w8/compare_partA.txt`,
`w8/compare_partB.txt` (every leaf: frames, segments, normalised record and trace,
`.xsq`, `.xtiming`, `.xmap`).

**Part A (base → Part A tree):**

- identical in all 567: the gate; plans A and B; plan D and D without its transition at
  every level (no events); plan E (transitions not rendered by either tree);
- plan C (events) at every level and C without its transition: different in 63, every one
  on `fam4_tagged` (the only rig whose wheels are tagged, so colour events play), every
  grid; identical in the other 504;
- no render errored; every colour and gobo byte change of plans C and E on the Part A tree
  dark through close latency and settle (567 each).

**Part B (Part A tree → this tree):**

- **identical in all 567, every plan without a transition**: the gate; plans A and B; plan
  C without its transition (events, DRAMATIC); plan D without its transition at all six
  levels. W8 changes no byte of a plan without transitions, the pickup grids included;
- different in all 567, by design: plan C and D at every level (each carries one
  crossfade) and plan E;
- **no render errored** on this tree; every colour and gobo byte change of every plan C
  (six levels), C without its transition and plan E render is dark through close latency
  and settle (the harness's independent reader): 567 each.

A robustness sweep before it (scratch `w8/sweep_transitions.py`: 120 three-section plans,
every mode on the first ENTRY, a middle ENTRY and the last EXIT, over six families, four
grids (78.3 BPM, 129 BPM with two pickup beats, 3/4, variable), three splits, five curves,
four lengths, colour changes): no error, no lit wheel change, no lit pan or tilt step beyond
the head's travel speed, every transition traced; where a head played no transition the
reason was the window being shorter than the dark cut a colour change needed.

## Tests

- `tests/unit/sequencer/moving_heads/test_transitions_render.py` (29 cases): the anchor
  without a transition; each mode at a repositioning boundary read from the bytes (SNAP's
  darkness before the boundary, CROSSFADE's handover and monotone halves, MORPH moving from
  the window start and SWEEP holding to its split point, FADE_VIA_BLACK down/dark/up,
  BLACKOUT dark over its window); every pair of modes and no transition differ; EXIT equals
  ENTRY and the ENTRY replaces it; the first ENTRY from rest (three modes) and the last EXIT
  to rest; a colour change across a crossfade (dark cut, wheel turned dark, in place of the
  dip); an event clamping the window and a hit playing on it; intensity resuming on an
  accent with no jump at the window start; a show rest; the window on pickup grids (4/4,
  3/4) and a variable grid; an aim `snap` strategy; a wheel strategy that blends; wheel
  strategies `fade_via_black` and `sequence` shaping the cut; a lit move too fast (110°/s:
  BEAT falls back to a dark cut, BAR plays lit); repair shortening; multi-part sections;
  a last section cut at the grid's end; the trace line; the realistic plan.
- `test_rig_repair.py`: transition repairs (EXIT replaced, a channel the rig lacks
  dropped, a blending wheel strategy, a lit morph across a colour change).
- `test_song_intent.py`: the transitions offer (3/4 lengths, whole-range travel).
- `test_mh_pins.py`: `TRANSITION_PINS`; `test_mh_intent_parity.py`: the four rows green.
- Updated where the work made them untrue: `test_prompts.py` (the morph guidance kept),
  `test_vision_judge.py` and `test_report.py` (entry renders; "not rendered" wording).

## Look questions for the owner (PENDING-OWNER)

1. **CROSSFADE's handover** at half the lower look's level on the boundary: is a single
   beam's crossfade a visible dip, or should it hold full and only move?
2. **MORPH vs SWEEP**: MORPH moves from the window's start, SWEEP holds then travels. Is
   that the distinction wanted?
3. **A colour change across a lit transition** dips dark at the split point (180 ms on the
   owner's timings). Acceptable, or should such a boundary use FADE_VIA_BLACK by default?
4. **Cascades**: a transition plays on the heads lit at the boundary; the others enter
   dark as the template does. Should the cascade's dark heads join the transition?
5. **SNAP** is the plain cut where nothing needs darkness (identical to no transition).
6. **The song's edges**: the first ENTRY comes up from the heads' rest pose; the last
   EXIT returns them to it (MORPH, SWEEP) or fades (FADE_VIA_BLACK).
7. Proposals: `CROSSFADE_FLOOR` 0.5, the placements, the curve mapping.

## Verification (this tree, fresh, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 7135 passed, 30 skipped, nothing xfailed (was 7090 / 30 / 4 xfailed at `0e02e969`) |
| `uv run pytest tests/regression/test_mh_pins.py -q --no-cov` | 54 passed (every fingerprint re-recorded, frames and `.xsq` unchanged; 2 new transition pins) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 26 passed; `--runxfail`: 26 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1307 files already formatted |
| `uv run mypy .` | No issues in 654 source files |
| Byte matrix (base `0e02e969`, Part A tree, this tree) | as § Byte matrix |

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w8/`
(`matrix_w8.py`, `compare_w8.py`, `run_matrix.sh`, `compare_partA.txt`,
`compare_partB.txt`, `sweep_transitions.py`, `worked_examples.py`/`.txt`,
`realistic_table.py`/`.txt`, `record_transition_pins.py`, `parity_probe.py`,
`a1_agree.py`, `a2_agree.py`, `partA_probes.txt`).

## Fix round 1 (review of `82bd2b0a` and the owner-rig render, 2026-11-17)

**Provenance.** The independent review of `82bd2b0a` returned REQUEST CHANGES, and the
owner-rig render of the real Need A Favor plan (the coordinator's evidence under the
session's `p4view/transitions/`, read only for its trace and frames) found three more
defects. Fixed by the executor agent in the same worktree, uncommitted; the review's
scripts (`w8rev/tools/`) were rerun against this tree. No provider call, no network, no
xLights, nothing under `~/xlights`, `data/` or `artifacts/`; `make validate` not run (the
integrator's). Every value below is still a proposal for the owner's W8 view.

### H1: a colour or gobo event inside a window crashed the render

`pipeline._event_spans` started a wheel event's span half a beat before its frame
(`frame_ms - round(half_beat_ms)`, off the 20 ms grid), and `window_for` copied the clamp
unquantized, so the transition's cues fell off the frame grid (`ValueError … off the 20 ms
frame grid`; the reviewer's repro: 120 BPM, `mirror_wings` into `mirror_wings`, ENTRY
crossfade BAR split HALF, `color blue` on 5.2; 122 of its 1,200 fuzzed plans).
Fixed at the source: every event span is floored at its start and ceiled at its end to the
frame grid, and `window_for` ceils a `not_before` clamp and floors a `not_after` one.
The repro renders; the reviewer's fuzzer (`fuzz.py`, the same 1,200 seeds) on this tree:
**0 errors, 0 lit wheel changes, 0 lit moves beyond the head's speed**. Tests:
`test_a_colour_event_inside_a_window_off_the_frame_grid_renders_on_the_grid` (the
repro) and `test_random_plans_with_events_inside_transition_windows_render_honestly`
(12 seeded random plans: templates, parts, intensity, both edges' transitions of every
mode, length, curve and split, events near the boundaries, a show's rest; no render
raises, no wheel byte changes lit, every transition traced on every head with what it
plays or why not, every window on the frame grid).

### H2: blackout dark over its whole window; the played rule

- **`blackout` is dark over its whole window on every head**, as a show's rest is, whether
  or not the head has a cue there: it no longer narrows to the head's unbroken cue runs
  (`transitions._sides`). The reviewer's `probe_blackout.py` (`fly_out_cascade` into
  `fly_in_cascade` and `mirror_wings` into `fly_in_cascade`, TWO_BARS): 0 lit frames in the
  window on every head (was 25 to 50 on each at `82bd2b0a`). Test
  `test_blackout_is_dark_over_its_whole_window_where_a_head_has_no_cue`.
- **A transition counts as played on a head only where its frames differ from the
  transition-free render.** A render whose plan has transitions renders the same plan
  without them once more (no output files, its warnings silenced: they are the render's
  own) and compares each head's frames over the transition's window and darkness
  (`RenderingPipeline._transitions_played`); where they are identical the head's entry is
  replaced by `plays: nothing: <why>` (a `snap`: "the plain cut: its darkness before the
  boundary changes no frame"; a `blackout`: "the head is dark over the window without it").
  `_attempt` also says `nothing` up front where it knows (a `snap` into a head that enters
  dark; a `snap` with nothing to move or turn; a head dark on both sides between its
  cues; an empty window, such as the song's first ENTRY `snap`). A per-section warning
  counts the heads a transition played nothing or did not play on. **Cost:** a plan with
  transitions renders twice (a plan without them is untouched).
- **Repair** records a `snap` that is the plain cut (`rig_repair._plays_nothing`): the
  song's first ENTRY, and on the heads the gate found always enter the incoming template
  dark after the outgoing one (`RigOffer.dark_entries`). **The prompt** says it: the
  developer prompt that `snap` ignores `curve` and `split` and `blackout` ignores `curve`,
  and that a `snap` is the plain cut on the song's first ENTRY and into a template the
  heads enter dark; the user prompt lists the rig's template pairs a `snap` is the plain
  cut on (`_transitions_for_prompt`'s `dark_entries`).

### H3: events must be seen before a transition begins

The integrator's decision, as implemented (`pipeline._seen_until`, `_event_spans`): a
colour or gobo event (from its first reveal on any head) and a hit keep a minimum visible
time, until the later of half a beat after the reveal (the hit's beat) and, for a
cue-bound event, the cue's own time plus a quarter beat; a darkening or handover window
starts after it, on the frame grid (never past the boundary: the outgoing look ends
there). Where what is left of the window is shorter than its mode needs
(`transitions.MIN_WINDOW_FRAMES`, proposed: four frames for the blending modes and
`fade_via_black`, one for `snap` and `blackout`), the transition plays on no head, traced
`not_played` with the reason on the window and on every head. Repair predicts it
(`rig_repair._yields_to_events`, from the event's beat and lyric: "at least", since a head
dark on its beat reveals later) and records the clamp, and that the transition does not
play where too little is left.

The owner-render case on the synthetic `REALISTIC` fixture (78.3 BPM, two pickup beats):
chorus_2's NEUTRAL colour on 61.4, bound to its lyric 40 ms after the beat, is revealed at
187760 ms; it must be seen until max(187760 + 383, 187794 + 192) = 188143 ms, so the
closing blackout starts at 188160 ms (was 187780): white is lit for 20 frames before it
(was one frame in the owner render, 186580 → 186600). Asserted in
`test_the_realistic_plan_plays_its_transitions_honestly` (window start, white lit on every
head from the reveal to it, dark over the window), and render against repair in
`test_repair_predicts_a_window_yielding_to_an_event_seen_before_it` (a cue-bound colour
seen past the boundary: at 120 BPM the crossfade keeps a quarter beat and plays; at 240
BPM it keeps 60 ms and plays on no head; repair says the same).

### H4: a transition's darkness may not lose an event

A head whose transition would darken (its dark cut, or a lit move's fallback cut) a hit
that plays on it without the transition plays no transition: its boundary's own entry,
traced `not_played` ("its darkness (…) would cover the hit at bar … beat …, which plays on
this head without the transition"); `HeadContext.protected` carries the incoming part's
hits in the window. On `REALISTIC`, break → chorus_2's ENTRY crossfade BEAT (one-sided:
the break's `strobe_medium` runs to the boundary) needs a dark cut on 160940–161260 ms
for ACCENT → PRIMARY, which would cover the hit on 53.1 (160940 ms): no head plays the
crossfade, and the hit plays lit (255) on every head (asserted in the realistic test).
In the owner render only MH1 and MH4 took the fallback; on the synthetic fixture the
colour turn makes all four need the cut.

### M1: a one-sided crossfade

Where events clamp a crossfade's window to one side of the boundary (its split point on
the window's edge) there is no handover point: the level eases from the outgoing look to
the incoming one along the curve (traced "clamped to one side of the boundary: the level
eases …"), no lit-to-lit jump at either edge. The reviewer's `repro_clamp.py`: every case
eases (the `closed` cases end dark, traced "it ends dark"). Test
`test_a_crossfade_clamped_to_one_side_eases_its_level_without_a_jump`.

### M2: `snap` turns the wheels held at its cut

`snap` read the outgoing wheel state at the window's start, not at its dark cut; on a
`masked_wheel_flick` outgoing section (its flick colour changes inside the window) the
transaction pass then could not join the cut. It now reads the state one frame before
the cut (re-read as the cut is sized). The reviewer's `probe_snapflick.py` (BAR, red into
blue): all four heads play the snap (was MH2 and MH4 `not_played`, "cannot play the dark
cut … in time"). Test `test_snap_turns_the_wheels_held_at_its_dark_cut`.

### M3: the trace says what the frames show

- `dark_outlasts_window_to_ms` only where the darkness runs past the window's end (was
  written wherever a head's window shrank).
- `plays` is derived from the levels: a lit mode whose last level is 0 says "it ends dark
  (the incoming look is dark there)", whose first is 0 "it starts dark"; a one-sided
  crossfade says so (above).
- `curve_played` only for the modes the curve shapes (not `snap`, `blackout`), and the
  prompt now states what those two ignore (above; the earlier claim in § Decisions 7 that
  the prompt said it was untrue at `82bd2b0a`).

### M4: A1's three-frame rule

Recorded in the [W6/W7 record](../2026-11-17-w6-w7-events/README.md#w8-fix-round-a1s-three-frame-rule-m4-2026-11-17):
the wheel turns and the head shows the new state from its first lit frame however short;
the three-frame run only counts "shown within a beat".

### M5: the intro's ENTRY crossfade replaces pre-positioning (confirmed, intended)

Without a transition the render pre-positions the heads in the dark before the first cue
(frames differ 160–1020 ms) and the heads are lit at full from 1540 ms, moving with
`target_orbit`. With the intro's ENTRY crossfade (TWO_BARS, HALF, from rest) the
transition's own cues start from the rest pose, so nothing pre-positions: the heads move
from rest inside the window, dark until its split point (4620 ms), and the light comes up
from 4740 ms along ease_in_sine (MH1 level 1, 27, 112, 255 at 4740, 5500, 6500, 7660 ms).
While lit in the window the head's largest step is 186 16-bit words a frame, on the
window's last frame at full, against up to 150 for the template's own orbit after it:
the head eases onto the moving orbit, it does not swing at full (scratch `w8fix/m5.py`).
Whether that look is wanted is the owner's (PENDING-OWNER, § Look questions 6).

### M6: a move that changes nothing

Colour 49.1 on `REALISTIC` was traced as moved to 49.3 (+1520 ms) though the frames
equal those of playing it on its own beat (every head is dark from 49.1 and first lit at
49.3 either way). Where every head's cues on the new beat equal those on its own beat,
the move changes no frame: `moved.changes_nothing` says so and the lines read "first
seen at bar 49 beat 3, +1520 ms: the heads are dark from its own beat until then" (the
lyric-cue line "first seen at" in place of "played at"). Rendered frames do not change.

### LOW

- The prompt's and repair's "after a `closed`, where the heads are lit" (self-
  contradictory) now reads "on a beat where the heads are lit (the `open` that ends a
  `closed` is one: the wheel turns in its darkness)".
- The broad `except Exception` in `transitions.easing` is gone: every curve in the library
  samples (25 played names, checked).
- `_attempt` is split (`_sides`, a `_Sides` dataclass for the two looks and the head's
  window, `_dark_cut`, `_lighting`, `_own_cues`, `_ends`; no closures);
  `_play_boundary` no longer mutates `cues`/`kept` or rebuilds indices mid-loop (it returns
  a `_BoundaryPlay`; `_outgoing_of` reads the outgoing cues and how each head stands
  before them, `_cut_outgoing` replaces the cut cues once); `_transitions_for_prompt`'s
  imports are at module level.
- Repair still cannot predict the lit-move fallback (it needs the templates' poses at the
  boundary, which the offer does not carry) or a dark cut over an incoming hit (H4):
  recorded in `_transition_repairs`' docstring and the user guide; the trace records both.

### Revision, pins, caches

- **`RENDERER_REVISION` 10 → 11.**
- **Pins:** every pin re-recorded fingerprint only, refusing any moved frame: `PINS`,
  `MULTI_PIN`, `GATED_PIN`, `INTENT_PIN`, `FAST_INTENT_PIN`, `INTENSITY_PINS`,
  `EVENT_PINS` and `TRANSITION_PINS` frames and `.xsq` unchanged. Combined-show golden
  moving-head fingerprint `fdc28b5b…` → `ec32a76a…`.
- **Planner cache:** re-keyed (the developer and user prompts changed, and the prompt's
  offer gains `transitions.dark_entries`): every song plans again once (paid).
- **Contract:** unchanged (no schema change).

### Byte matrix, fuzzing and identity (fix round)

- **Byte matrix** (scratch `w8fix/matrix_fix.py`: the W8 harness, 567 configurations,
  with plan F added: plan E's eight sections with events inside the windows, each section's
  first beat a hit and its second a colour change, its third beat from the end a hit and its
  last beat a colour change bound to a lyric 40 ms after it). Base `git archive 82bd2b0a`
  against this tree (`w8fix/compare_fix.txt`, `w8fix/compare_fix_frames.txt`):
  - **every plan without a transition identical in all 567** (every leaf): the gate, plans
    A and B, plan C without its transition (`cn`), plan D without its transition at all six
    levels (`dn_*`);
  - **plan F: 567 of 567 errored at `82bd2b0a`** (`ValueError`: a segment off the 20 ms
    frame grid, H1, or "no value is defined at … ms"), **none on this tree**, every wheel
    byte change dark through close latency and settle in all 567;
  - frames different, by design: plan C (one crossfade, events) in 63 (all
    `fam4_notopo`), plan D (one crossfade) in 330, plan E (every mode) in 501; traces
    differ wherever a transition plays (the new trace keys and `nothing` outcomes);
  - **attribution:** with M1 (the one-sided crossfade) switched off in a scratch copy
    (`w8fix/noM1`), plans D and E equal `82bd2b0a` frame for frame in 24 of 24 gated
    configurations sampled (six rigs × four grids) and plan C on `fam4_notopo` in 3 of 3:
    every frame difference sampled is M1 (a head whose window starts on the boundary,
    clamped by its cue runs or by events, now eases its level instead of starting at the
    handover); no lit dimmer jump at a played window's edge in those plans on either tree;
  - no render errored on this tree; every wheel byte change dark in every plan C (six
    levels), C without its transition, E and F render: 567 each.
- **The reviewer's fuzzer** (`w8rev/tools/fuzz.py`, seeds 0–1199, on the final tree):
  0 errors (122 at `82bd2b0a`), 0 lit wheel changes, 0 lit moves beyond the head's speed;
  lit dimmer jumps above 100 at a played window's edge in 13 seeds (38 of the 1,078 that
  rendered at `82bd2b0a`). Of the 13, 12 vanish with the plan's events stripped: a hit's
  flash or a strobe's first flash on the window's edge frame (the event's own look); the
  thirteenth (seed 1132) is a crossfade with a `pan fade_via_black` strategy whose window
  events clamp to 340 ms, its dark cut taking all but two frames, so the light fades
  255 → 128 → dark in two frames (recorded, not changed: the fade is as long as the window
  leaves).
- **Transition-free identity** (the reviewer's `ident.py`, 648 renders: three rigs × nine
  grids × four levels × plans A, B and C, with and without a show's rest): plans A and B
  identical to both `0e02e969` and `82bd2b0a` in 324 of 324 (162 more are the harness's
  invalid `SUBTLE` level, refused alike on every tree); plan C (events, no transition)
  differs from `82bd2b0a` in 108, every one a render where `82bd2b0a` traced a head
  "never shows it lit" (M4: the wheel now turns for lit runs shorter than three frames).
- **The reviewer's repros** on this tree: `repro_offgrid.py` renders; `probe_blackout.py`
  0 lit frames inside any blackout window; `repro_clamp.py` every clamped crossfade eases;
  `probe_snapflick.py` every head plays the snap; `probe_a1c.py` 0 problems.

### Verification (this tree, fresh, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest -q --no-cov` | 7157 passed, 30 skipped (7135 at `82bd2b0a`; 22 new cases) |
| `uv run pytest tests/regression/test_mh_pins.py tests/golden -q --no-cov` | 62 passed, 1 skipped (every fingerprint re-recorded; frames and `.xsq` unchanged) |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 26 passed; `--runxfail`: 26 passed (baseline and assertions unchanged) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1307 files already formatted |
| `uv run mypy .` | No issues in 654 source files |

New tests: `test_transitions_render.py` the off-grid repro, blackout over cue gaps (2),
the played rule, snap's cut wheels, the one-sided crossfade, repair against render for a
yield (2) and the first-ENTRY snap, the seeded random plans (12), and the realistic test's
H3 and H4 assertions; `test_events_render.py` the short-lit-run wheel change (M4). Run on
`82bd2b0a`'s code with these test files: every one of the 11 targeted cases fails there,
and 8 of the 12 random plans (a first-ENTRY `snap` traced on no head); the other 4 random
plans pass on both trees.

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w8fix/`
(`matrix_fix.py`, `run_matrix.sh`, `matrix_base.jsonl`, `matrix_fix.jsonl`,
`compare_fix.txt`, `compare_fix_frames.txt`, `noM1/`, `dcheck.py`, `ccheck.py`,
`djump.py`, `fz2/`, `id_fix_*.jsonl`, `realistic.py`, `m4.py`, `m5.py`, `m6.py`,
`seed.py`, `edge_noev.py`).

### Look questions added (PENDING-OWNER)

8. **Seen before a transition**: half a beat after a colour, gobo or hit, and a quarter beat
   after its lyric, before a darkening or handover window begins (the integrator's rule);
   the minimum window (four frames; a frame for `snap` and `blackout`).
9. **A head that would lose a hit** to its transition's darkness plays no transition (its
   plain entry): on `REALISTIC` the break → chorus_2 crossfade then plays on no head.
10. **The intro from rest** (M5): dark until the split point, the head easing onto its
    moving orbit as the light comes up, instead of pre-positioned and lit at full from the
    boundary.

## Fix round 2 (second review of `3115b545`, 2026-11-17)

**Provenance.** The second review confirmed every first-round finding fixed with no
regression and asked for the items below; its scripts (`w8rev2/tools/`) were rerun against
this tree. Same worktree, same executor, uncommitted; no provider call, no network, no
xLights, nothing under `~/xlights`, `data/` or `artifacts/`; `make validate` not run (the
integrator's). Every value is still a proposal for the owner's W8 view.

### H1: the seen rule, for every event that shows something, in one place

`events.seen_until` states the rule once: an event stays visible until half a beat after it
is shown and, bound to a lyric cue, a quarter beat after the cue, whichever is later.
`events.yield_spans` (which the render and the repair both read) says, per kind, from where
it is shown: a colour or gobo change from its reveal; a hit from the frame it plays on (the
latest head's, as the plan renders without transitions); an `open` from its frame (it had
a one-frame span); a strobe or `pulse` from its start, for a full beat or to its own end
(its commanded span, which a window never cuts into, always reaches that far). The
review's repro (`repro_open_seen.py`: `closed` 4.1, `open` on bar 4's last beat, ENTRY
blackout / fade_via_black / morph BAR HALF, at 120 BPM, 78.3 BPM with two pickup beats and
3/4): the `open`'s light is now lit 13 frames (20 at 78.3) before the window, where it was
one. A strobe on the last beat still ends with its own last flash (two lit frames) on the
boundary: its span already runs to the boundary, which the window starts at. Test
`test_an_open_before_a_blackout_is_seen_for_half_a_beat`.

### H2: no transition loses a hit, and the reason is true

The invariant is on outcomes. `RenderingPipeline.render` now renders a plan with
transitions **first** without them (`transition_free`), and that render's per-head hit
frames (`hit_frames`) drive the render with them:

- `apply_hits(required=…)`: a hit's beat serves only where every head that plays it
  without transitions can show it there; else it moves, by the hit's own rules, to the beat
  where they all do (traced `moved`, reason "a head that plays it without the transitions is
  dark on its beat with them"); a hit decided with the transitions applied.
- `HeadContext.protected`, per head, the frame the hit plays on without transitions, from
  the window's start through the part it enters (a dark cut may outlast the window): the
  reason "its darkness (a–b ms) would cover the hit at bar … beat …, which plays on this
  head at t ms without the transition" is then true by construction.
- A pass that still loses a hit on a head (`_lost_hits`, by comparing the two renders'
  `hit_frames`) gives up the transition nearest that hit on that head and renders again,
  at most `TRANSITION_PASSES` (3) times; only the last pass's warnings are logged.

The review's repro (`repro_lost_hit.py`: 170 BPM, `target_orbit` → `zoom_wave`, hit on
5.2, ENTRY fade_via_black BAR HALF, the zoom rig): all four heads play the transition and
the hit (moved to 5.3 on all four, 6360 ms), where MH1 and MH2 gave up the transition and
lost the hit, with a false reason. Test
`test_no_head_loses_a_hit_to_a_transition_and_its_reason_is_true`, and the random-plans
test now asserts the invariant on all 12 seeds.

### M1: dark modes end before an incoming hit; shortened, not dropped

`DARK_MODES` (`snap`, `fade_via_black`, `blackout`) add the incoming part's hits (from the
earliest frame they play on without transitions) to the events they end before. Where a
dark cut would still cover a hit's frame, a `fade_via_black` or `blackout` moves its
darkness to end on that frame where it still fits after the window's start, the change
turning inside it ("fades to dark before the boundary, changes in the dark, and is lit on
it for its hit"); only otherwise does the head play none (the true reason above). The
review's sweep (`sweep_ev.py`, 15,876 renders): heads not playing a dark mode for a hit
2,352 blackout and 1,117 fade_via_black at `3115b545`, **0 and 4** now. Repair reads both
sections' events (M3). Test `test_a_dark_mode_ends_before_an_incoming_hit_instead_of_being_dropped`.

### M2: a side too short to fade cuts

`transitions.MIN_SIDE_FRAMES` (proposed: 4) applies per side: a fade into or out of a dark
cut shorter than that cuts (`_Light.cut_sides`; traced "cuts to dark at the boundary,
changes in the dark, fades up", or "…cutting into it and fading out" on a lit mode's dark
cut), and a `crossfade` with either side of its handover shorter eases its level across
the window (the round-1 one-sided form, now also for a side of a frame or two). The
review's case (170 BPM, a cue-bound hit on 4.4 with its lyric 0.6 beat later, ENTRY
fade_via_black BAR HALF: window [5620, 6360], boundary 5660): the light holds then cuts to
dark at the boundary, where it faded 255 → 128 → 0. Test
`test_a_fade_side_too_short_to_fade_cuts_and_says_so`. The sweep's 84 window-edge jumps
(all such fades) are gone.

### M3: repair and render share the placement

`rig_repair._yields_to_events` now builds the window with the render's own function
(`transitions.window_for`, the clamp and the minimum) over the render's own spans
(`events.yield_spans` on `events.section_events`), from the plan's beats, for both
sections' events (outgoing: everything seen; incoming: what commands darkness or a wheel,
and hits for the dark modes). It records each event clamp in the render's words ("the
window yields: it starts after the part it leaves plays its hit at bar 4 beat 4"), that the
transition does not play where the minimum is not left, and, where events shorten a
window, that a head needing longer in the dark plays none there. The review's
`repair_vs_render.py` (5 grids × 3 events × 2 lyric bindings × 6 modes × 3 lengths × 2
template pairs, 1,080 cases): **0 disagreements** on whether the window yields and whether
it plays (92 at `3115b545`: rounding at the seen time, a seen time past the boundary, the
incoming side unread). Remaining (counted, not fixed: they need the templates' poses and
wheels at the boundary, which the offer does not carry): **54 cases where heads do not
play for their own darkness need** — 18 where a lit mode's dark cut for a move does not fit
the window left (on all four heads), 36 where a `snap`'s dark lead does not (on one to four
heads); in each, repair says the window yields and that "a head that needs longer in the
dark … plays no transition", but not which heads. Test `test_repair_and_render_agree_on_what_a_transition_yields_to` (60
cases: 120 and 170 BPM × a hit, a colour change and an `open` after a `closed` on the last
beat, bound or not to a late lyric, × 6 modes).

### LOW

- **A hit's seen time** counts from the frame it plays on (the latest head's, from the
  transition-free render), not its beat.
- **The second render is quiet without touching logger state**: `render_log` (`held()`, a
  context variable for that render's call) collects what the render path logs through
  `render_log.warn`/`note` — the pipeline's warnings and the scheduler's loop-overrun
  warning; `logging.disabled` is never set. Test
  `test_the_second_render_logs_nothing_and_leaves_the_logger_alone`.
- **The played rule compares the whole song per head**, laying each differing frame at the
  transition playing on that head nearest it (`_transitions_played`); the second render
  happens only when the plan has transitions.
- **Cost**: a plan with transitions renders twice (a pass more where a head would lose a
  hit). On `REALISTIC` (62 bars, 7 transitions, owner-like rig) the reviewer's
  `double_render.py`: 2.44 s with transitions (2.49 s again) against 1.21 s without;
  frames, fingerprint and trace deterministic across runs, the plan object untouched, one
  warning with transitions as without (none twice). The integrator's measure on the
  owner's song (before this round): render stage 17.2 s with transitions against 7.0 s
  without.

### Revision, pins, caches

- **`RENDERER_REVISION` 11 → 12.**
- **Pins:** every pin re-recorded fingerprint only, refusing any moved frame (`PINS`,
  `MULTI_PIN`, `GATED_PIN`, `INTENT_PIN`, `FAST_INTENT_PIN`, `INTENSITY_PINS`,
  `EVENT_PINS`, `TRANSITION_PINS`): frames and `.xsq` unchanged. Combined-show golden
  moving-head fingerprint `ec32a76a…` → `e509125a…`.
- **Planner cache:** re-keyed (the developer prompt changed): every song plans again once
  (paid). **Contract:** unchanged.

### Byte matrix, sweeps and fuzzing (fix round 2)

- **Byte matrix** (`w8fix2/matrix_fix.py`, the round-1 harness with plan F, 567
  configurations; base `git archive 3115b545`; `w8fix2/compare_fix.txt`,
  `w8fix2/compare_fix_frames.txt`): **identical on every leaf in all 567**: the gate, plans
  A and B, plan C without its transition, plan D (one crossfade, no events) at all six
  levels, with and without its transition. Different, by design: plan F (events inside
  every window) in 567; plan E (every mode) in 54, every one the per-side minimum (M2:
  equal to `3115b545` with `MIN_SIDE_FRAMES` set to 1 in a scratch copy, `w8fix2/noM2`,
  54 of 54); plan C at every level in 18 (`fam4_notopo` on the two 3/4 grids, every timing
  and policy: one rig, plan and meter), not M2 (they differ from `3115b545` with it off
  too): examined on `fam4_notopo/base/waltz/default`, a hit `3115b545` lost to the
  crossfade (H2: the hit on 6.1 plays on 5.1 without the transition; the crossfade's dark
  cut for the colour turn covered it, so no head played it; now the heads whose cut would
  cover it play no transition there, with that reason, and the hit plays on all four). No render errored on either
  tree; every wheel byte change dark in plans C (six levels), C without its transition, E
  and F: 567 each.
- **The review's events sweep** (`sweep_ev.py`, 6 grids × 9 event sets × 7 × 7 template
  pairs × 6 modes, 15,876 renders; `w8fix2/out_an_ev.txt`): 0 errors, 0 lit wheel changes,
  0 lit moves beyond speed, 0 windows off the grid; **0 events lost** to a transition (8 at
  `3115b545`); **0 trace-against-frames mismatches** over the whole song; heads not
  playing a dark mode for an incoming hit 0 blackout / 4 fade_via_black (2,352 / 1,117).
  Its seen check flags 7 renders (one outgoing case, 170 BPM, `fly_out_cascade` with a
  hit on 4.4 into a blackout, against each of the 7 incoming templates): that hit plays on 4.3 (moved earlier: no
  head shows 4.4), so it is seen from 4.3 and the window starts after that; the check
  reads the planned beat. Its 243 window-edge "jumps" are all the incoming hit's own
  dip-and-snap (153 → full) on the frame the dark mode now ends on (84 at `3115b545`, all
  two-frame fades, now gone).
- **The review's fuzzer** (`fuzz.py`, seeds 0–1199, with a lost-hit check added,
  `w8fix2/fuzz_lost.py`): 0 errors, 0 lit wheel changes, 0 lit moves beyond speed, **0
  hits lost**; window-edge dimmer jumps in 9 seeds (13 at `3115b545`; 710, 1047, 1061 and
  1132 gone with M2), each a hit's or strobe's own flash on the edge frame (round 1's
  check: they vanish with the events stripped).
- **Transition-free identity** (`ident.py`, 648 renders): plans A, B and C (events, no
  transition) identical to `3115b545` in 486 of 486 (the other 162 the harness's invalid
  level, refused alike).
- **The review's probes**: `repro_open_seen.py` (H1, above), `repro_lost_hit.py` (H2,
  above), `repair_vs_render.py` (M3, above), `double_render.py` (LOW, above),
  `probe_m4.py` 1,296 head outcomes, 0 problems.

### Tests and verification (fix round 2; this tree, fresh, after the last code edit)

New in `test_transitions_render.py`: the `open` seen before a blackout (H1); no head loses
a hit and the reason is true (H2, the review's repro on its rig timings); a dark mode
ends before an incoming hit (M1); a fade side too short cuts (M2); repair and render agree
on what a transition yields to (M3, 60 cases); the second render logs nothing and leaves
the logger alone (LOW); the random-plans test asserts no hit lost (12 seeds). Run on
`3115b545`'s code with this test file: the H1, H2, M1 and M2 cases fail there, 34 of the
60 agreement cases, and the 12 random plans (there the new `transition_free` attribute does
not exist, so these say nothing about that tree's hits); the logging case passes on both.

| Command | Result |
|---|---|
| `uv run pytest -q --no-cov` | 7222 passed, 30 skipped (7157 at `3115b545`; 65 new cases) |
| `uv run pytest tests/regression/test_mh_pins.py tests/golden -q --no-cov` | 62 passed, 1 skipped |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 26 passed; `--runxfail`: 26 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1308 files already formatted |
| `uv run mypy .` | No issues in 655 source files |

Scratch (session-local, not committed):
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w8fix2/`
(`matrix_fix.py`, `run_matrix.sh`, `matrix_base.jsonl`, `matrix_fix.jsonl`,
`compare_fix.txt`, `compare_fix_frames.txt`, `noM2/`, `attrib_ce.py`, `cdiff.py`, `sw/`
and `out_an_ev.txt` (the events sweep), `fz/` and `fuzz_lost.py`, `fuzz_summary.txt`,
`id/`, `repair_vs_render2.py`, `rvr_final.txt`, `base_3115/`).

### Look questions added (PENDING-OWNER)

11. **The seen rule for every kind** (an `open` held half a beat before a transition
    darkens it; a strobe's own last flash on the boundary).
12. **A dark mode before an incoming hit**: shortened to end on the hit (a
    `fade_via_black` then goes dark before the boundary and is lit on it for the hit).
13. **`MIN_SIDE_FRAMES` 4**: a shorter fade cuts; a crossfade with a short side eases
    across instead.
14. **A hit moved so no head loses it** (the review's case: on 5.3 on all four heads,
    where without the transition it is on 5.3 too).

## Fix round 3 (third review of `fd85b8db`: plan repair, 2026-11-17)

**Provenance.** The third review approved the render side and asked for these repair
changes; its scripts (`w8rev3/tools/`) were rerun against this tree. Same worktree, same
executor, uncommitted; no provider call, no network, no xLights, nothing under
`~/xlights`, `data/` or `artifacts/`; `make validate` not run (the integrator's).

### M-1: repair placed the song's last EXIT off the beat grid

Repair sized the closing boundary from the song's last frame (`beat_grid.duration_ms`,
past the covered beat grid); `transitions._at` then returned None and `window_for`
silently fell back to the part's start, so a one-beat blackout looked like the whole last
part ("it leaves 10420 ms …"). Now:

- **One shared placement:** `transitions.part_frames` (a part's frames from the detected
  downbeats, as the compile context places it) and `transitions.closing_boundary_ms` (the
  last part's end, no later than `cue_limits`' end) are used by the render (its part
  windows; its closing boundary, then the part's cues' own end where earlier) and by
  repair (`rig_repair.played_window`, new: the window repair reads, by the render's own
  functions).
- **`window_for` never falls back silently:** where the detected beats do not reach the
  window's length from its boundary it stops at the grid's first or last beat and records
  why in `clamped`.
- The review's repro (`repro_exit_room.py`, 120 BPM and 78.3 BPM with two pickup beats, a
  colour on 8.3, EXIT blackout BEAT): repair now says nothing it should not (it said "it
  leaves 1900 ms …" at 78.3); on `REALISTIC`, repair's closing window is 188160–188520 ms,
  the render's. Test `test_repair_places_the_songs_last_exit_where_the_render_does`
  (the review's case: repair's window, start, end and boundary, equal the render's).

### M-2: the darkness caveat only where it can be true

"A head that needs longer in the dark … plays no transition" is now said only for `snap`
and the lit modes, and only where the time left is below the most darkness the offer
bounds (`rig_repair._darkness_bound_ms`: the slowest head's full pan or tilt travel plus
the slowest wheel change, which includes going dark and the state's settle; where the
offer lacks a term it is said, unbounded). Never for `blackout` or `fade_via_black`. The
review's `repair_vs_render.py` (1,080 cases): warned 376 (818 at `fd85b8db`), heads
skipping 54, **every one of them warned** (54 of 54), warned on a dark mode 0; and still
0 disagreements on whether the window yields and whether it plays. The bound is the
offer's, not the head's exact need (its axis latency and settle are not in the offer);
in this sweep it covers every skip. The agreement test now asserts both directions
(warned ⊇ skipped; never warned for `blackout` or `fade_via_black`).

### LOW

- **Hits still lost after the last pass** are traced (`hits_lost_to_transitions`: the
  boundary, the head, why) and warned (a diagnostic and a log warning), never kept
  silent. Test `test_hits_a_transition_still_loses_after_the_last_pass_are_traced_and_warned`
  (a sweep into `mirror_wings` with a hit on 4.1 and two gobo changes, which needs a
  second pass: with `TRANSITION_PASSES` patched to 1 the loss is traced and warned on all
  four heads; with the default, nothing is lost).
- The 12 random-plan tests are named and described as smoke tests
  (`test_smoke_random_plans_with_events_inside_transition_windows`).

### No frame changed; no revision bump

The byte matrix (`w8fix3/matrix_fix.py`, the round-2 harness, 567 configurations × 23
renders) against `fd85b8db`'s run: **13,041 of 13,041 renders identical** in frames,
`.xsq` and normalised trace (`w8fix3/compare_frames.txt`). `RENDERER_REVISION` stays 12;
pins and the golden fingerprint unchanged. The planner prompts did not change, so **the
planner cache key is unchanged**. Repair's recorded reasons change for plans with
transitions (their wording and when the caveat appears).

### Verification (this tree, fresh, after the last code edit)

| Command | Result |
|---|---|
| `uv run pytest -q --no-cov` | 7224 passed, 30 skipped (2 new cases; the agreement cases gained the caveat assertions) |
| `uv run pytest tests/regression/test_mh_pins.py tests/golden -q --no-cov` | 62 passed, 1 skipped |
| `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov` | 26 passed; `--runxfail`: 26 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1308 files already formatted |
| `uv run mypy .` | No issues in 655 source files |

Run on `fd85b8db`'s code with this test file: the two new cases fail there (the closing
window and the lost-hit trace do not exist) and 8 agreement cases (the caveat on a
`blackout` or `fade_via_black`). Scratch:
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w8fix3/`
(`matrix_fix.py`, `matrix_fix.jsonl`, `compare_frames.txt`, `rvr_final.txt`,
`minpass*.py`, `realexit.py`, `base_fd85/`).
