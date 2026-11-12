---
type: decision
status: accepted
created: 2026-11-12
updated: 2026-11-12
confidence: confirmed
tags: [moving-heads, rendering, xlights, regression, owner-acceptance]
---

# Moving-Head Rendering Matches the Pre-Clean-Up Look

_Directed by the owner on 2026-11-12: the moving-head output was tested and accepted in
xLights before the 2026-08 clean-up and must render at that level again._

## Decision

The look the owner accepted before the clean-up (commit `5d64e47`, 2026-04-04) is the
reference for moving-head pan, tilt and dimmer output. A renderer change that alters that
look for an existing template needs the owner to see it in xLights first. A passing test
suite is not acceptance.

## What was found

One saved plan was rendered with the `5d64e47` code and with the current code, on the same
beat grid and rig, and both `.xsq` files were rendered by xLights 2026.19 against the
owner's show folder. The DMX output differed for almost every template:

- The fan spread between heads collapsed (mean pan spread 81 DMX to 19 on the fan sweeps).
- Tilt geometry flattened and beams sat low instead of pointing up.
- Movement ran faster and wider where a template or plan named a non-SMOOTH intensity.
- Dimmer curves sat brighter at the dim end.

## What was reverted (commit `aa0d39a`)

| Clean-up item | Restored behaviour |
|---|---|
| P4-F9 calibrated window | The rig's pan/tilt limits are not applied to emitted movement |
| P4-F1 intensity argument | Movement renders from the SMOOTH entry unless the step's params carry `intensity` |
| P4-M6 centring | `center_curve` rescales to full range |
| P4-M5 terminal anchor | Movement curves close on their start value |
| P4-F14 phase wrap | Phase shift wraps by modulo |
| P4-M1 template floor | The template `dimmer_floor_dmx` is not applied |
| P4-F8 dimmer ladder | Dimmer SLOW and FAST carry the SMOOTH values |

After the revert, 31 of the 37 templates render the same pan, tilt and dimmer output as
`5d64e47`, up to frame-sampling differences.

## What was kept, pending the owner's eyes

Six templates still differ from `5d64e47`, because the old output looked broken there:

- `split_lr_sweep_counter`, `stomp_tilt_bias_pulse`, `build_drop_recover` and
  `intro_main_outro_phrase` play every step at its declared offset. Before, steps ran one
  after another and idle heads sat dark at pan 0.
- `wave_scattered_fade_out` and `wave_vertical_spotlight_fade` fade out. Before, they
  faded in.
- `ambient_random_wash`, and any section shorter than its template's cycle, render.
  Before, they rendered nothing.

One combination has never been seen by the owner: `build_drop_recover`'s `build` step now
renders, and with modulo phase wrap restored, heads 2 to 4 drop from about 55% to 10%
dimmer partway through it.

## Consequences

- Plan-level `intensity` (schema v2) still changes the dimmer. It no longer changes
  movement speed or reach.
- The rig's `limits` are not enforced on emitted pan/tilt, as before the clean-up.
- Colour, shutter and gobo emission are clean-up-era additions and remain. They depend on
  the fixture config's wheel maps matching the real fixture.

## Open items for the owner

- **Movement limits are not a safety clamp.** `MovementLimits` in the fixture config
  describes a safe window, but emitted pan/tilt can leave it, as it could before the
  clean-up. If a rig needs a hard clamp, it has to be added as an explicit opt-in.
- **Movement intensity is accepted and ignored.** Preset and plan intensity values, and
  the per-pattern intensity tables in `libraries/movement.py`, do not reach movement
  output.
- **Template `defaults` no longer reach the output.** They are recorded in segment
  metadata only.

## How to repeat the comparison

Render one plan with both trees, render each `.xsq` with
`xLights -hl -s <show folder> -od <dir> <file.xsq>`, and compare the fixtures' channels in
the two `.fseq` files.
