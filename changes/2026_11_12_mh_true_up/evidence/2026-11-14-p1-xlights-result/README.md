---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-14
updated: 2026-11-14
---

# Phase 1 xLights transport result — 2026-11-14

Answers the [request](../2026-11-13-p1-xlights-request/README.md). Authorized by the
owner on 2026-11-14 ("test in xlights as previous") and run by the integrator the way
the earlier xLights checks in this repository were run: a headless xLights render to
FSEQ, decoded and compared byte for byte.

This is a transport result: what xLights renders from the physical `.xsq`. It says
nothing about real fixtures or about how the result looks.

## Result

**xLights 2026.19 reproduced every byte Twinklr encoded**, in both sequences, on both
models, on every whole frame.

| Check | Result |
|---|---|
| 16-bit carries | Pass. Pan coarse and fine (channels 1, 2) match on all frames; 42 coarse-byte carries per model in the first cue, the count the request lists |
| Channel 17 | Pass. Byte 8 on cue frames, 64 elsewhere; never 0 |
| Sliders 17–48 | Pass. In the 48-channel sequence channels 19–48 hold their marker byte on every frame |
| Effect count | The `.xsq` holds 101 effects per model, 202 per sequence, and the render consumed them into the expected bytes. xLights was not asked to re-save the sequence, so its own count after an import is not observed |

| Sequence | Frames compared | Bytes compared | Mismatches |
|---|---|---|---|
| `p1_linear_reveal` (18-channel footprint) | 180 | 6,480 | 0 |
| `p1_linear_reveal_48ch` (48-channel footprint) | 180 | 17,280 | 0 |

In the 18-channel sequence, channels 19–48 of each model stayed 0: nothing leaks past
the footprint.

## Findings

1. **xLights drops the final partial frame.** The sequence is 3.615 s; xLights rendered
   180 frames (0–3580 ms). Twinklr encodes a 181st frame at 3600 ms, parked dark, which
   xLights never plays. It is harmless, and it confirms that the last whole frame is the
   last one that matters.
2. **The layout check read the wrong attribute.** A DMX model written by xLights
   2026.19 has no `parm1`; its channel count is `DmxChannelCount`. `twinklr run
   --layout` therefore refused every real model ("declares no channel count (parm1)").
   Fixed on `fix/mh-layout-dmx-channel-count` and re-run: the scratch layout passes with
   `layout_check: performed` and identical bytes, and the owner's 16-channel models are
   refused by name against the 18-channel synthetic profile.
3. **Layout values xLights writes for a DMX model** (xLights 2026.19, the owner's
   moving-head models): `DisplayAs="DmxMovingHeadAdv"`, `StringType="Single Color
   White"`, `DmxChannelCount="16"`, `versionNumber="8"`. Other DMX models in the same
   layout are `DisplayAs="DmxGeneral"`. The `Dmx` prefix and the `Single Color` prefix
   the check accepts are therefore observed; other `StringType` spellings are not.
4. **The owner's moving-head models are 16 channels wide.** A physical profile that
   uses offsets above 16 needs a wider model in the layout; the check now reports that
   instead of failing on `parm1`.

## Method

- Commit `df9b4364` (the Phase 1 branch tip; `main` after the merge has the same tree).
- Sequences: the request's script, unchanged, run without a layout argument.
- Show folder: a scratch folder, `~/xlights/_twinklr_verify/p1_show`, holding only two
  models, a one-universe inactive controller and a silent 3.62 s WAV. The owner's show
  files were read, not written. The two models are copies of the owner's `Dmx MH1` and
  `Dmx MH2` elements as xLights wrote them, with three attributes changed by hand:
  `StartChannel` (1 and 49), `DmxChannelCount` (48) and `Controller` (empty).
- Render: `xLights -hl -q -s <scratch show> -od <scratch show>/out <sequence>.xsq`, once
  per sequence. Each wrote a version 2.2 FSEQ, 96 channels, 20 ms step, zstd.
- Comparison: the FSEQ was decoded and every channel of every frame compared with the
  frames `RenderingPipeline.frames` holds for the same render. Model channel `n` of
  `Dmx MH1` is FSEQ channel `n`; of `Dmx MH2`, `48 + n`.

## Limits

- The models were widened to 48 channels by editing `DmxChannelCount` by hand. xLights
  accepted and rendered them, but no 48-channel model was created in the xLights UI.
- Headless batch render only. Opening the sequence in the xLights UI, the model
  preview, and a re-save were not exercised.
- Two models, 3.6 seconds, 202 effects. Behaviour near the 1,000,000-effect budget is
  still unmeasured.
- No real fixture was driven. Hardware accuracy and look acceptance remain
  `PENDING-OWNER`.
