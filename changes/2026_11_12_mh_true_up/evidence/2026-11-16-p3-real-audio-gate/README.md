---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# First real-audio gate on the owner's rig — 2026-11-16

The viewing render for the single-path cutover (P3-C0) was stopped at its offline
check. No provider request was made, xLights was not started and nothing was written
under the owner's show folder. This records why. It is a gate result, not a look or
hardware result.

## Inputs

Authorized by the owner on 2026-11-16 ("Use what we have been using"):
`data/music/11 - Need A Favor.mp3`; the owner-rig fixture config under
`artifacts/live-validation/`; the layout of `~/xlights`, read only. Code at `4fd507e9`.

## Rig, from the layout and fixture config

Four heads, `Dmx MH1`–`Dmx MH4`, 16 channels each, one left-to-right row. Pan 16-bit on
channels 11/12 over 540°, tilt 16-bit on 13/14 over 270°, dimmer 3, shutter 2, colour
wheel 1, gobo 4. No zoom channel. The xLights models limit both motors to 150°/s.

The physical profile written for it is synthetic. Chosen, not measured: travel 150°/s
(the layout's limit; the owner confirmed that figure the same day), axis latency 20 ms,
settle 60 ms, colour and gobo settle 150 ms, visibility latency 20 ms, pan not
inverted, and the initial state (centred, dark).

## Result

| Fact | Value |
|---|---|
| Beat grid | 156.6 BPM, 492 beats, 164 bars of 3 |
| Meter confidence | 3/4 at 0.35; 2/4 0.30, 4/4 0.25, 6/8 0.18 |
| Beat intervals | 313 / 383 / 430 ms (min / median / max) |
| Covered span | 0–186,954 ms of 197,400 ms; the last 10.4 s held dark |
| Gate time | 4.5 s |
| Admitted | `finite_snap_hold` only (entry dip up to two beats) |

| Excluded family | Reason given by the gate |
|---|---|
| `target_orbit` | 3/4: pan jumps across the cue with no time between cues |
| `mirror_wings` | Base needs 150.45°/s; both presets fail in 3/4 |
| `fly_out_cascade`, `fly_in_cascade` | Pan needs 157.25°/s at a 340 ms beat |
| `masked_wheel_flick` | Needs 420 ms to darken, change and settle; the beat gives 380 ms |
| `zoom_wave` | No zoom axis |

With other chosen timings, tried at the gate only: the cascades need more than 202°/s
on this grid; the orbit, wings and zoom wave cannot be admitted at any speed while the
grid is 3/4.

## Reading

- The grid is doubtful: the meter was chosen at 0.35 confidence, and the integrator
  believes, unverified, that the song is near 78 BPM in 4/4.
- The families are excluded outright by a low-confidence grid or a head a few degrees
  per second short. They do not adapt.
- The old renderer depends on neither, which is why this song has always rendered.

No defect was found against documented behaviour; the finding is that the documented
behaviour is not fit to be the only path. The owner chose the same day to fix
robustness first (a sane grid when meter confidence is low or tempo is doubled;
families that adapt to tempo and fixture speed), then run the viewing render on this
song and rig at 150°/s.

## Old-renderer reference

Re-rendering the saved 2026-11-12 plan (session `sess_d1af8801f86a49ca`) with the
current code and no provider call reproduces
`~/xlights/_twinklr_verify/TWINKLR_need_a_favor_final.xsq` with every effect line
identical; only the media path and the group element name (`90 - Moving Heads`, after a
later fixture-config edit) differ. 921 effect elements.

## Profile fields that could default

Reported by the agent that wrote the profile, for the profile-defaults task (C1.0):
axis units and the dimmer range; default bytes; pan and tilt ranges and windows
(derivable from the existing calibration fields or the layout); channel offsets and
wheel bytes (already in `dmx_mapping`); footprint; travel speed (the layout's limit);
discrete state ranges and per-state settle; default, closed and open states;
extinguishing states; one profile shared by identical heads; identical initial states;
topology from `position_index`.

## Not done

Both renders, the xLights render and byte comparison, and the videos. Working files
are in the session scratch directory, not committed.
