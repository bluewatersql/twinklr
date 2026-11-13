---
type: decision
status: accepted
created: 2026-11-12
updated: 2026-11-13
confidence: confirmed
tags: [display, rendering, group-planner, brightness, xlights, owner-acceptance]
---

# The Display Stays Lit in Every Section

_Directed by the owner on 2026-11-12 after the first `twinklr display` run on the real
layout: verses were dim and the last 20 seconds were almost black._

## Decision

A quiet section is expressed with lower intensity, less motion and fewer accents. It is
never expressed by leaving most of the display unlit. Three mechanisms enforce this.

- **Visible brightness floor.** Event intensity maps to xLights brightness through
  `display/brightness.py`: intensity 0.0 is 35% brightness and the range above it is
  linear to 100%. Intensity still drives effect energy and density unchanged. The same
  mapping sets the `On` effect level. A palette's own intensity scaler composes with
  it but cannot take an event below 35%.
- **Focal-role dimming is separate from the floor.** In a combined show, show
  coordination records the LEAD / SUPPORT / REST scale (1.0 / 0.65 / 0.15) as
  `RenderEvent.brightness_scale` and leaves `intensity` alone. The export multiplies the
  lit brightness by it, down to a 10% floor. A resting group is dim on purpose, so the
  lead keeps its declared contrast (about 87% against 13% at a strong intensity).
  Where one group carries far more activity than its role allows, coordination dims it
  further, but only halfway toward the next role down (LEAD no lower than 0.825,
  SUPPORT no lower than 0.40). Between events planned at the same intensity LEAD is
  always brighter than SUPPORT, which is brighter than REST, and a brief resting event
  cannot darken the lead. The summed brightness-over-time ratios are exact only while
  no group reaches that bound. The scale is relative to what the planner asked for: a
  lead planned at a quiet level can still render dimmer than a support planned at a
  loud one, as it could before.
- **Display composition reaches the end of the song.** `BeatGrid.extended_to_duration()`
  continues beats and bars at the average beat duration past the last detected beat, and
  a section that runs past the last bar ends at its own end time. `DisplayRenderer` uses
  the extended grid for composition only. Show coordination and the moving-head path keep
  the detected grid, so moving-head output is unchanged and both parts of a combined show
  slice against the same schedule.
- **Foundation coverage rule.** The section plan validator rejects a plan whose BASE lane
  has no full-coverage placement that starts on the section's first beat, lasts the whole
  section, and targets a group holding at least 40% of the display's pixels
  (`FOUNDATION_TOO_NARROW`, `FOUNDATION_TOO_SPARSE`). Twinkle, snow, meteor and similar
  particle effects do not count as full coverage. Zone targets, split targets and
  coordination windows do not count, because the validator cannot see which group they
  light or for how long. Rule 12 of the planner system prompt states the same requirement.
  The rule is skipped when no group in the layout reaches 40% and for a section shorter
  than one bar.

## What was found

Measured on `Hey Come Look At My House` (140.9 s) against the owner's layout, rendered by
xLights 2026.19. The figure is the mean channel value (0–255) over pixel channels.

| Cause | Evidence |
|---|---|
| Intensity was used directly as brightness | The quietest BASE level rendered at 12–15% brightness |
| Beat detection stopped at 134.1 s | Sections ending later were clamped there; nothing rendered for the last 6.8 s |
| The planner put the final section's foundation on matrices, snowflakes and floods only | Those targets hold 24% of the display's pixels; mean value 0.2–0.6 for the last 20 s |
| A display-wide foundation used a twinkle recipe | Mean value 6 across that verse although 74% of channels were touched |

| | Whole song | Darkest 2 s window |
|---|---|---|
| Before | 13.3 | 0.0 |
| After (live Claude run, 7 sections, all planned first pass) | 52.6 | 15.7 |
| Owner's hand-made sequence of the same song | 29.6 | 4.8 |

The concrete per-energy lane recipes in the planner prompt (BASE on outlines and windows
for the whole section) were replaced by abstract wording in `7bf495a` (2026-08-14). Rule
12 restores the coverage part of that guidance.

## Follow-up fixes (2026-11-13)

- Section-relative bar and beat references now resolve from the detected downbeats.
  `TimingResolver` matches each bar start to its nearest beat, so a grid whose first
  beat is not a downbeat no longer places effects up to a bar early. `Hey Come Look At
  My House` starts on a downbeat (167 of 167 bars already aligned), so this is covered by
  unit tests only.
- A fresh live Claude plan with the final Rule 12 wording: 7 sections, all planned in
  one iteration, six approved at 7.4–7.8 (the 0.6 s outro has no verdict), 735,296
  tokens. Rendered by xLights: mean 49.9, darkest 2 s window 13.0.

## Open items for the owner

- The result is now brighter overall than the owner's own sequence, and the chorus is
  about three times as bright. Whether to lower the floor or the top end is a taste call.
- The 40% threshold and the list of sparse effects were chosen from this one song and
  layout.
- The 10% floor for a resting group and the halfway bounds on role dimming are first
  values, not calibrated ones. No combined show has been rendered on the real layout.
- Bar 1 beat 1 of a section resolves to the beat nearest the bar start, while the
  section's own start is the exact bar boundary. If detected downbeats sit off the
  beats, the two can differ by a few milliseconds. Not reproduced.
- Extending the grid for the moving-head path would let moving-head sections past the
  last detected beat render. It was left out to keep moving-head output unchanged
  ([decision](mh-render-matches-pre-cleanup-look.md)).
