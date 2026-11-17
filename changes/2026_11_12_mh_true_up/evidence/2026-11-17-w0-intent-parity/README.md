---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# W0: intent-parity harness — 2026-11-17

Task W0 of [song-intent rendering](../../plan/song-intent-rendering.md). The old
moving-head renderer (tag `mh-last-with-legacy-renderer`, `5d50580c`, mode `legacy_v1`,
the default there) was run on synthetic inputs, one intent at a time, and what it did is
recorded as renderer-independent facts. A standing test asserts each regression row's
parity target on the current renderer. Worktree `feat/mh-true-up-p3`; first pass on
`9e7205cf`, fix round (§ "Fix round") on `7c31919d` after an independent review.
Nothing committed. No provider, network or xLights process was used, and no owner data:
the only files read under `~/xlights` are the project's own P3 verification output named
in § "What xLights played" (read only, as the coordinator authorised). `make validate`
was not run (the brief forbids it).

## What was added

| Path | What |
|---|---|
| `scripts/extract_mh_intent_parity.py` | Extracts `git archive` of the tag into a temporary directory (recording the commit `git get-tar-commit-id` reads from the archive), imports `twinklr` from it instead of the editable install, renders each row's plan pair with the old renderer, serialises every fixture segment with the old exporter (`DmxSettingsBuilder`) and samples the slider and value-curve settings on the 20 ms frame grid, per xLights layer, before emission quantisation. Writes the facts with each row's annotation (status, task, parity target, citations, old behaviour not carried over) and the layer finding. Documented in `scripts/README.md`. |
| `tests/regression/baselines/mh_intent_parity.json` | The output: provenance, the layer finding (`layer_playback`), setup, and 34 rows with plan inputs as data (`intent`, `neutral_intent`), facts, parity target, citations at the tag. Generated twice: byte-identical. |
| `tests/regression/test_mh_intent_parity.py` | The standing test. Each regression row rendered on the current renderer through a public entry — `RenderingPipeline`; `twinklr run`'s `MovingHeadRenderingStage` with the macro plan in state, read back from the delivered `.xsq` (palette-role rows); the combined show stage's moving-head render (show rows) — and checked on encoded frames only: named wheel states per frame and commanded darkness. Everything that knows the planner contract or a stage's call shape is in one block ("Plans and calls"). `PENDING` holds the strict xfails; a guard asserts each prefix in `PREFIXES` is used by exactly one test and every regression row is covered once. |
| `layer_playback.py` (beside this record) | The layer analysis below: decodes the `.fseq` (v2, zstd, sparse; the repository has only a byte comparer, `api/xlights/fseq.py`) and compares it with both layers of the `.xsq`. |

Inputs, both sides: eight 4/4 bars of 500 ms beats with the first beat 15 ms off the
frame grid (`m.bars_grid`, as `test_mh_pins.py`'s steady grid); one section over bars
1-4 (transitions: bars 1-4 and 5-8); four heads.

- Old side: built-ins `fan_pulse` (held fan, PULSE dimmer authored DRAMATIC, no wheels),
  `hold_center_out_breathe` (PULSE authored SMOOTH, per-head phase offsets) and
  `wave_fan_hold` (incoming section of the transition rows); a rig with pan 1, tilt 3,
  dimmer 5, shutter 6, colour 7, gobo 8 and explicit maps (`shutter_map` closed 64 / open
  8 / strobe 100, 140, 190; colours white 0, red 14, blue 26, magenta 40, amber 52, cyan
  66; gobos open 0, dots 10, stars 20).
- Current side: `mirror_wings` (lit once revealed, white, gobo open, dimmer 1.0) and two
  test-only templates registered by the test: `parity_partial_hold` (dimmer held at 0.5,
  so a raised level can show) and `parity_authored_pulse` (its own 0.3–0.8 pulse over two
  beats). Rig: `m.family_rig` plus a `green` colour state (`parity_rig`), with a
  test-side `STATE_HEX` standing in for W1's `hex` tags. Transition rows enter
  `mirror_wings` from `finite_snap_hold`. Macro palettes: `core.rgb_primary` for the run
  rows (first stop `#FF1744` → red, second `#00E676` → green), `spec.cosmic_night` for the
  show rows (first stop `#0D47A1` → blue, so a fixed "red" cannot pass).

"Neutral" on the old side is the old model's explicit neutral (SMOOTH, palette role
PRIMARY, no events, no hint); that model could not set one intent while leaving the
others unset. Each row compares only the channel its intent drives; colour rows compare
against the omitted-intent plan (template as authored).

## Result today

- `uv run pytest tests/regression/test_mh_intent_parity.py -q --no-cov`: **2 passed, 24
  xfailed**. The 2 passing: the anchor (a neutral plan of `mirror_wings` over bars 1-8
  renders exactly `PINS["steady/mirror_wings/base"]`'s frames) and the guard.
- **24 regression rows fail today**, each a `strict=True` xfail: W4 5, W5 4, W6 6, W7 3,
  W8 4, W9 2. With `--runxfail` every one fails on its own target assertion (floor not
  raised, colour `white`, darkens or strobes late, no reveal, gobo not revealed, dark at
  the boundary, no fade, LEAD no hotter, colour `white` where `blue` is due), none on an
  error.
- 10 rows are `recorded`: facts with no render-level target (reasons per row).

## What xLights played (the layer finding)

The old exporter put each transition on a second xLights layer under the untrimmed
section effects, with no `LayerMethod`. Whether the blend was ever visible was
established from the project's own P3 verification output:
`~/xlights/_twinklr_verify/p3_view/out/legacy_need_a_favor.xsq` (sha256 `7d75ab25…`) and
the `.fseq` xLights rendered from it (sha256 `b8070827…`, v2.2, zstd, 64 channels in 4
sparse ranges of 16, 9870 frames of 20 ms). The ranges were matched to heads by
agreement with the base layer away from transitions (0.97–0.98 against 0.58–0.69 for the
others), which is file order. `layer_playback.py` compares every frame inside the 16
transition effects (4 boundaries × 4 heads) with both layers:

| Frames inside a transition effect | Played the base | Either (equal) | Played the transition only | Neither |
|---|---|---|---|---|
| a base effect covers the frame | 6351 | 4112 | 4 | 393 |
| no base effect covers it | — | — | 1668 | 144 |

(channel-frames within ±1). The 393 "neither" are base value curves faster than this
sampling (e.g. MH1 channel 2 at 30920 ms: played 114, base sampled 70, transition 0);
none matches the transition. Example, MH2 across the 129625 ms boundary, channel 11:

| ms | played | base layer | transition layer |
|---|---|---|---|
| 129320 | 123 | 124 | 115 |
| 129520 | 123 | 124 | 113 |
| 129720 | 39 | 39 | 111 |
| 129920 | 42 | 42 | 109 |
| 130320 | 46 | 47 | 104 |

**Finding: the transition layer never played where a section effect existed. Every
boundary between two sections played as a cut.** The transition showed only where a head
had no section effect (MH1 and MH4, 129620–150900 ms, a section without them), as a fade
to or from nothing. So the old renderer's "lit blend" was written but not seen, and the
null-hint "default crossfade on every boundary" was not visible either. The W8 parity
target is therefore the planner's intent (a smooth lit change between sections), not
something the old renderer visibly did; the transition rows say so. Not established: what
xLights does where the base byte is 0 under a non-zero transition byte — no such frame
occurs in this file.

## Rows

Citations are at the tag, under `packages/twinklr/core/`. Every change below lands on
the first 20 ms frame at or after its beat (5 ms after it).

### Intensity — W5 (4 xfail, 3 recorded)

The old renderer wrote the section's intensity onto every step's movement and dimmer
(`sequencer/moving_heads/compile/intent_resolution.py:21-40`). Movement ignored it
(`handlers/movement/default.py:80-88`). The dimmer read it only for a pattern without its
own table (PULSE, FADE_IN, FADE_OUT; `handlers/dimmers/default.py:151-192`), from
`libraries/dimmer.py:50-59`, the period in bars converted to cycles over the step
(`handlers/dimmers/default.py:110-123`).

| Row | Old facts (MH1) | Status |
|---|---|---|
| `intensity_dramatic` | `fan_pulse`: 131–255, peaks at 1.1, 2.2, 3.3, 4.4: every 5 beats, each on a beat. Neutral (SMOOTH): 51–153, one 8000 ms swell | W5 |
| `intensity_intense` | `fan_pulse`: 171–255, a peak on every beat, also across the step's repeat over 8 bars | W5 |
| `intensity_dramatic_on_authored_pulse` | `hold_center_out_breathe` as authored (SMOOTH breathe) 76–153; DRAMATIC 137–230, peaks every 2500 ms (MH1 265 ms after the beat: its phase offset) | W5 |
| `intensity_intense_on_authored_pulse` | `fan_pulse` as authored (DRAMATIC) 131–255 every 5 beats; INTENSE 171–255 every beat | W5 |
| `intensity_slow`, `intensity_fast` | identical to SMOOTH | recorded |
| `intensity_smooth_on_energetic_template` | `fan_pulse` as authored 131–255 five-beat pulse; with SMOOTH a 51–153 four-bar swell | recorded, **owner view at W5** |

Targets (current side, on `parity_partial_hold` and `parity_authored_pulse`): every
frame dark in the neutral render stays dark and every lit one stays lit; no lit frame
below the neutral (authored) level and the lowest lit level higher (a raised floor); the
dimmer pulses with peaks within one frame after a beat; INTENSE a 1-beat period, DRAMATIC
a single whole-beat period of at least 2 beats (on the authored pulse the template sets
the period). The 5-beat period is recorded, not pinned. Not carried over: exact bytes,
the 64-sample pulse shape (`sequencer/models/context.py:148`), replacing the authored
curve with the table's. SLOW and FAST are the identity (the revised plan). The SMOOTH
row records that an explicit SMOOTH used to calm an energetic template; the revised plan
makes SMOOTH the identity so the accepted look is not dimmed — for the owner to judge at
W5's view, not a target.

Open point for W5: `mirror_wings` and the other catalog families hold the dimmer at
1.0, so "never below the authored look" leaves no room to raise a floor or add a pulse
on them; how DRAMATIC/INTENSE show on a full-level template is the W5 table's (and the
owner's) call. The rows here use a half-level template so the target can be met.

### Section colour — W4 (5 xfail, 2 recorded)

Explicit preset or palette role → one preset (`sequencer/moving_heads/pipeline.py:146-157`
fixed role table, `2362-2373`; the old `run` path had no palette input), written as the
step colour (`compile/intent_resolution.py:36-37`), resolved through the fixture's
`color_map` (`handlers/wheels.py:31-59`).

| Row | Old facts (colour channel) | Status |
|---|---|---|
| `color_explicit_blue` | `blue` from the section's first frame to its end | W4 |
| `color_palette_primary` / `accent` / `warm` / `cool` | `red` / `magenta` / `amber` / `cyan`, whatever the song's palette | W4 |
| `color_palette_neutral` | `white`, also the rig default | recorded |
| `color_change_between_sections` | red then blue: the wheel turned at 8020 ms with the dimmer at 51 before and 153 after (lit) | recorded |

Targets: explicit — every lit frame of the section, every head, shows `blue`. Palette
role (through `twinklr run`'s render stage with macro palette `core.rgb_primary`):
PRIMARY the state nearest the first stop (red), ACCENT the state nearest the second
(green), the two differing; WARM and COOL each one non-default state, different from
each other. All: the wheel changes only while dark through its settle time, and the dark
frames differ from the neutral render's only in the window before the reveal (close
latency + settle + half a beat, the revised plan's bound). Not carried over: the fixed
role table. Observed rather than assumed: inside one section the colour is present from
the first frame, so nothing turns; the lit turn happens at a boundary between sections of
different colours (the recorded row), which W4 owns.

### Shutter events — W6 (5 xfail, 1 recorded)

Each event is placed at its bar/beat's grid time (`pipeline.py:2362-2410`), the segment
is split there and the value held until the next event or the section end
(`compile/intent_resolution.py:43-117`); the byte comes from `shutter_map`
(`handlers/wheels.py:118-119`).

| Row | Old facts (shutter channel 6) | Status |
|---|---|---|
| `shutter_closed_open` | `closed` 2020–3020 ms, `open` before and after | W6 |
| `shutter_strobe_slow` / `medium` / `fast` | strobe byte from 2020 ms to the section end (the fixture's own strobe) | W6 |
| `shutter_pulse` | from 2015 ms a 64-point curve alternating 64/8 by sample index: period 190.5 ms; 295 of 300 frames on a byte that names no state | W6 |
| `shutter_event_on_channel_17` | dropped: `warning:shutter channel 17 outside plan-intent window 1-16; dropped` (`handlers/wheels.py:16-22,85-92`) | recorded |

Targets: CLOSED/OPEN — identical to neutral before, first dark frame within one frame of
2.1, dark until 2.3, as neutral after. Strobe — identical to neutral before, first dark
frame within one frame of the event, at least two dark-lit alternations in the following
bar, still strobing after it, more alternations for fast than medium than slow. Pulse —
revealed once per beat within one frame after it (one reveal fewer than beats allowed:
the head is already lit on the event's beat). Not carried over: the fixture's own strobe
rate; the sample-index pulse; the 16-channel window.

### Gobo events — W7 (2 xfail)

`gobo_event` (dots at 2.3): `open` → `dots` at 3020 ms to the section end, dimmer 153 at
the change (a lit turn). `gobo_two_events` (dots at 2.1, open at 3.1): `dots` 2020–4020
ms, then `open`; dimmer 153 and 51 at the changes. Target: each pattern revealed lit
within one frame of its beat and held on every lit frame until the next; lit frames
before the first show the neutral gobo, and darkness differs from neutral only before
each reveal (so "open before" cannot be met by staying dark); the wheel turns only while
dark.

### Lyric moment cues bound to events — W6 (shutter), W7 (gobo)

`bind_lyric_moment_cues` (`agents/sequencer/moving_heads/moment_cues.py:35-66,151-173`,
identical on this branch) moved an event declared at 1.1 to the cue's snapped beat (cue
at 2690 ms → 2515 ms, bar 2 beat 2); it rendered from 2520 ms. Targets: shutter — first
dark frame within one frame of 2515 ms, dark to the section end, identical to neutral
before; gobo — as `gobo_event` at 2515 ms.

### `transition_in` — W8 (4 xfail, 2 recorded)

With `transitions.enabled` (default true, `config/models.py:587-637`) every boundary got
a transition (`pipeline.py:1760-1763,2428-2513,2515-2563`) on a second xLights layer
(`export/xsq_adapter.py:272-292`), blended by the job's per-channel defaults
(`compile/transition_planner.py:192-245`, `compile/channel_blender.py:38-80`). The mode
was read only for SNAP and CROSSFADE's split (`compile/transition_planner.py:130-190`).
Rows: `duration_bars` 1, `fade_out_ratio` 0.25, curve linear.

| Row | Old facts (MH1, as written; see the layer finding for what played) | Status |
|---|---|---|
| `transition_in_crossfade` | effect −500…+1500 ms; dimmer 52→255, pan 70→120, monotonic | W8 |
| `transition_in_morph`, `transition_in_sweep` | effect ±1000 ms; the same blend, identical | W8 |
| `transition_in_fade_via_black` | identical to MORPH: the mode was not honoured | W8 |
| `transition_in_snap` | no transition: a cut | recorded |
| `transition_in_null` | the job default 0.5-bar crossfade, ±500 ms — not visible | recorded |

Targets (the planner's intent, since none of the blends played): CROSSFADE / MORPH /
SWEEP — never dark in the window; on lit frames pan and tilt move no faster than the
profile's travel speed; from the window's end the aim equals the neutral render's
(incoming section); MORPH and SWEEP render differently from each other (the revised plan
gives them distinct renderings; W8 defines how, the test only asserts they differ).
FADE_VIA_BLACK — the dimmer fades down through ≥2 intermediate levels to dark at the
boundary and up through ≥2 after. Not carried over: the mode being ignored, the lit cut.

### `twinklr show` — W9 (2 xfail, 2 recorded)

Reproduced by calling the old `coordinate_moving_head_plan`
(`sequencer/show_coordination.py:69-73,83-98,503-553`) directly on a one-section macro
plan on `spec.cosmic_night`, then the old renderer on the projected plan. Not run: a full
`twinklr show`, and the legacy show stage's slicing to coordination windows
(`pipeline/show_stages.py:224-262`), which a UNIFIED section does not cut.

| Row | Old facts | Status |
|---|---|---|
| `show_palette_color` | plan colour null, overwritten with the preset nearest `#0D47A1`: `blue`, for every focal role | W9 |
| `show_focal_lead` | intensity overwritten to INTENSE: 171–255, a beat pulse | W9 |
| `show_focal_support` / `show_focal_rest` | SMOOTH / SLOW: both 51–153 | recorded |

Targets: palette — with plan colour PRIMARY under the show, every lit frame shows the rig
state nearest the palette's first stop (`blue`, asserted not `red`). Focal role — with
the same plan (intensity neutral, on `parity_partial_hold`), LEAD renders no lit frame
dimmer and some lit frame brighter than SUPPORT; REST no lit frame brighter than SUPPORT;
the same dark frames. The revised plan also makes the focal role a validator rule on the
planner's intensity; W9 may meet this row either way.

## Fix round (review of the first pass)

| Item | Done |
|---|---|
| 1 Palette | Run-mode role rows supply `core.rgb_primary` through `twinklr run`'s render stage and assert PRIMARY/ACCENT follow the first/second stop and differ (green state added); show row on `spec.cosmic_night` (→ blue), old projection rerun for it; the fixed table recorded as not a target |
| 2 Authored pulse | Two W5 rows on a template with its own pulse; SMOOTH-calms-energetic recorded with an owner-view flag |
| 3 DRAMATIC period | A whole-beat period ≥ 2 beats with peaks on beats and a raised floor; 5 beats recorded |
| 4 Tightening | Strobe and cue-bound shutter: first dark frame within one frame; colour and gobo: darkness differs from neutral only in the bounded pre-reveal window; intensity: neutral-lit frames stay lit |
| 5 Transitions | Travel-speed bound and the incoming aim by the window's end; MORPH ≠ SWEEP asserted |
| 6 One block | Transition plans, macro plans and all stage calls in "Plans and calls" |
| 7 Focal role | `show_focal_lead` is a W9 strict xfail on a render effect |
| 8 Two gobo events | `gobo_two_events`, W7 |
| 9 Layer composition | Established from the `.fseq`: the transition never played over a section effect (above) |
| 10 Low | Wording; `plan_color: null` recorded; prefix guard; the script archives the tag itself and records `get-tar-commit-id`; "turned lit" reworded and the two-section fact added; the pulse allowance documented |

## Discrepancies with the plan's gap table

1. **`transition_in` "byte blend over an overlap" was written but not played**: xLights
   showed the section effects over it, so every boundary played as a cut (above). The
   regression for transitions is against the planner's intent, not against a look the
   owner saw.
2. Only SNAP and CROSSFADE's split were read; MORPH, SWEEP and FADE_VIA_BLACK wrote one
   identical blend.
3. Intensity reached only PULSE/FADE dimmer steps; SLOW and FAST equalled SMOOTH; an
   explicit SMOOTH dimmed templates authored hotter.
4. Shutter and gobo events persisted to the next event or the section end.
5. Every explicit plan carried a colour (PRIMARY = red).

## Notes for the following tasks

- W2: the "Plans and calls" block is the only mapping from the fixture's intent onto the
  contract; `{}` must become all-null and keep the anchor green.
- W1/W4: `STATE_HEX` and `parity_rig`'s added `green` stand in for profile tags; with
  W1's tags the rig helper carries them and `nearest_state` reads them.
- Each task deletes its rows from `PENDING`; a row that starts passing turns the suite
  red until then.

Scratch (probes, the first analysis): `/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/w0/`.
