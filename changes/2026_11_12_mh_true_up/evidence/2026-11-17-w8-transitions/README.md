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
independent reader).

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
nothing. The planner's prompt gives each length in milliseconds at the median beat and how
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
