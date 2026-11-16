---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# Phase 2 xLights transport result and preview recording — 2026-11-16

Authorized by the owner on 2026-11-16 ("run the test in xlights as screen record the
results") and run by the integrator the way the
[Phase 1 check](../2026-11-14-p1-xlights-result/README.md) was run, plus a house-preview
video export through the xLights automation interface.

This is a transport result and a recording for the owner to look at. It makes no
judgment of how the families look, and no real fixture was driven. Look acceptance and
hardware accuracy remain `PENDING-OWNER`.

## Result

**xLights reproduced every byte Twinklr encoded** for the six physical families played
back to back on four heads.

| Check | Result |
|---|---|
| Frames compared | 5,881 per head (0–117,600 ms), 4 heads, 16 channels |
| Bytes compared | 376,384 |
| Mismatches | 0, in both the headless render and the render the xLights UI made before the video export |
| Layout check | `layout_check: performed` against the scratch layout |
| Admission | All six families admitted; no exclusion |
| Unplayable cues | None (`unplayable_totals` empty). Two cues were dropped by section entry windows, as the trace lists |
| Final partial frame | Twinklr's 5,882nd frame (117,620 ms) is not rendered by xLights, as in Phase 1 |

Render fingerprint `f442acc3596e13488ad8e1af5a3b62e814f11b44dfd9167df795fcf2fa650e7d`;
13,460 effects, 1.9 MB `.xsq`; `.xsq` sha256 `bb40363c…156e`.

## Recording

xLights exported its house preview of the sequence to video
(`exportVideoPreview`, the method used for earlier Twinklr previews): 117.6 s, 50 fps,
H.264, 496×768. A cropped and enlarged copy was made with ffmpeg. Both are local files,
not committed:

- `~/xlights/_twinklr_verify/p2_show/out/p2_families.mp4`
- `~/xlights/_twinklr_verify/p2_show/out/p2_families_zoom.mp4`

| Starts | Family (8 bars each, 100 BPM) |
|---|---|
| 0:00 | `fly_out_cascade` |
| 0:19 | `fly_in_cascade` |
| 0:38 | `target_orbit` |
| 0:58 | `mirror_wings` |
| 1:17 | `masked_wheel_flick` |
| 1:36 | `finite_snap_hold` |

Sampled frames show beams lit and dark where the encoded frames say, the wings
mirrored, and the flick's red and blue states on alternate heads. That is a consistency
observation, not a look verdict.

A literal screen recording was not made. Capturing the screen from the terminal raised
a macOS prompt asking to let the terminal's host application record the screen; that
permission is the owner's to grant and was left unanswered.

## Method

- Code: branch `feat/mh-true-up-p2` at `36002f2a` (P2.4c and its record), exported with
  `git archive` so the uncommitted P2.5 work was not used.
- Rig: four heads with a declared topology and a `flick` attribute preset (red on
  heads 1 and 3, blue on 2 and 4).
- Profile: synthetic (`provenance: synthetic`), 16 channels, using the channel map of
  the scratch xLights model: colour wheel 1, shutter 2, dimmer 3, gobo 4, pan 11/12
  (inverted, ±270°), tilt 13/14 (±135°). Travel speed 150°/s to match the model's
  `SlewLimit`, 40 ms settle, 150 ms wheel settle. These timings are chosen, not
  measured from a fixture.
- Song: a synthetic 4/4 grid at 100 BPM (600 ms beats), 48 bars, over a silent WAV.
- Show folder: scratch, `~/xlights/_twinklr_verify/p2_show`. Its four models are copies
  of the scratch `Dmx MH1` element from the Phase 1 show with these attributes changed
  by hand: name, `StartChannel` (1, 17, 33, 49), `DmxChannelCount` (16),
  `DmxShutterOpen` (128, so a closed shutter reads as closed in the preview) and the
  world position. The owner's show folder was not opened or written.
- Headless render: `xLights -hl -q -s <scratch show> -od <scratch show>/out
  p2_families.xsq`; the FSEQ (v2.2, zstd, 64 channels, 20 ms) was decoded and compared
  with `RenderingPipeline.frames`.
- Preview: xLights UI started with `-s <scratch show>`, then
  `XLightsAutomationClient.render_preview` on port 49913.

## Findings

1. **xLights is now 2026.20** (Phase 1 was checked on 2026.19). It migrated the scratch
   layout on open and kept a `xlights_rgbeffects_pre2026.04.xml` copy; bytes still
   match.
2. **All six families play on a 150°/s head at 100 BPM.** Worst-case entry dips
   reported by the gate were 640–800 ms, two beats.
3. **In every dark frame the dimmer is zero as well as the shutter closed**, so a
   preview that ignores the shutter would still show darkness correctly.

## Limits

- One tempo, one rig size, one section order, 8 bars per family, no presets.
- `zoom_wave` (P2.5) is not in this run: it was still under review, and the scratch
  model has no zoom channel.
- Starting the xLights UI changed three keys in the owner's xLights settings:
  `xLightsVersion` (2026.19 to 2026.20, as any launch of the updated app would) and two
  window-layout keys, which were restored from a copy taken beforehand. The saved show
  folder (`LastDir`) was unchanged.
- No real fixture, no real audio, no provider request.
