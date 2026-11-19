---
type: evidence
status: recorded
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# Recovered whole-song render review

The owner requested continuation of the full render evaluation after the previous
chat repeatedly failed with API error `Audio input is not available`. The failure
occurred during audio-clip inspection, after the repaired sequences were committed
and exported. Recovery started from clean `main` at `c73d3480`. Local decoding and
waveform analysis remained available; no new provider request was needed.

## Finding and repair

A fresh full-video scan reproduced an audible, unlit opening in Hey Come Look At
My House. The source audio measures about -11 to -15 dBFS between 0.25 and 1.5 s;
its full-section house foundation did not start until 1.540 s, the first detected
downbeat. Sampled frames confirmed darkness before that entry. This conflicts with
the accepted [display foundation rule](../../../../memories/decisions/display-stays-lit.md).

`4f8ceb6d` retains an opening section's pickup boundary and lets its BASE placement
at bar 1 beat 1 with SECTION duration cover that pickup. Accents, later starts,
shorter durations, expanded coordination windows and moving-head timing retain
their beat references. `a1326e31` corrects the section-map documentation.

The new regression failed with `1540 != 0` before the fix. After the fix,
`pytest tests/unit/sequencer/display/composition/ -q --no-cov` passed 175 tests.
An independent agent reviewed an archive of `4f8ceb6d`, ran 222 composition and
show-coordination tests, and checked nonzero pickup starts, later sections and
SEQUENCED/RIPPLE/CALL_RESPONSE windows. Verdict: approved for code correctness,
with the documentation correction above. This is not a human look verdict.

## Artifact comparison

New deliverables live under
`/Users/ondeck/xlights/_twinklr_verify/recovery-review-2026-11-19/`.
Previous deliveries remain in the [repair record](repaired-previews.md).
The replay uses the saved typed display plans and original moving-head effects.
Comparing every exported effect after resolving settings and palette references
found only these five changes:

| Song | Effect placements | Changed foundation starts |
|---|---:|---|
| Dance Jams | 36,927 | Display background: 1.400 s → 0 |
| Need A Favor | 29,514 | House and megatree star: 2.040 s → 0 |
| Hey Come Look At My House | 21,327 | Display and mini trees: 1.540 s → 0 |

The scratch replay initially exposed a generic parser round-trip behavior: absent
DMX palette references became palette zero. The replay now preserves the original
moving-head XML nodes exactly, checks that their database entries are retained,
and exports new previews from those corrected sequences. No moving-head setting,
cue timing, effect endpoint or display palette changed. `sequence-diff.json` and
the replay script are local artifacts beside the new sequences.

## Preview export correction

The first new exports clipped the scene at column 500 of a 1280-pixel frame,
including the static green ground grid. The clipping persisted for varying opening
intervals. An independent read-only artifact review ruled out XML element ordering,
layout/network/background differences, and audio remuxing. Bringing the app forward
alone did not fix it. The House Preview pane was 500 pixels wide; widening it beyond
1280 pixels before export produced a full-width opening frame. The final export
uses that pane size, then restores the prior pane width. No choreography, camera,
fixture calibration, or production show data is changed by that UI workaround.

## Final checks

All three final MP4s contain 1280×720 video at 50 fps and source audio remuxed
from time zero. FFmpeg decoded both streams in full without errors. The waveform
check uses normalized cross-correlation on half-second windows, sampled every
second with a ±500 ms search. A control with an injected 24 ms delay was detected
correctly in all four test windows.

| Song | Video frames checked | Audio windows | Maximum audio offset | Minimum correlation | Audible dark intervals ≥1 s |
|---|---:|---:|---:|---:|---:|
| Dance Jams | 12,926 | 255 | 0 ms | 0.99371 | 0 |
| Need A Favor | 9,870 | 193 | 0 ms | 0.99787 | 0 |
| Hey Come Look At My House | 7,046 | 140 | 0 ms | 0.97821 | 0 |

The dark-interval scan operates on 160×90 decoded frames: it subtracts each
region's first-percentile pixel baseline, counts house pixels at least 35 levels
above that baseline (12 required), and beam pixels (3 required). Either region
qualifies. Audible frames use a one-second smoothed RMS threshold of -35 dBFS.
This is a visibility screen, not a creative score or a guarantee of brightness
on hardware. The far-right green floor grid is present in all 29,842 frames,
with at least 19 qualifying pixels per frame in the checked region; the export
clipping is absent from the final videos.

Visually inspected the 25 interior section boundaries and 36 strongest selected
spectral changes in before/at/after contact sheets, then the final opening and
cue sheets. The four repaired Dance Jams cues remain present. Need A Favor's
chorus house effects and Hey's formerly dark sections remain visible. The
foundation now shows in Hey at 0.5 and 1.0 s. Some musical changes receive a
subtle response rather than a large accent; no human musicality or look verdict
is inferred from these measurements. The local scripts, contact sheets,
per-song JSON measurements and preview SHA-256 hashes accompany the outputs.

Fixture output stayed off. The scratch instance was closed, the preview pane
width restored, and both production show-file SHA-256 checks passed.

The fresh full gate passed on `a1326e31` in a clean isolated checkout:
`UV_NO_SYNC=1 UV_OFFLINE=1 PYTEST_ADDOPTS='-n 8 --dist loadfile' make validate`.
Formatting, lint and type checks passed; pytest reported **7,798 passed,
30 skipped, 43 warnings**, with **91% coverage**, in 777.02 seconds.
The checkout remained clean. The complete output is saved as `validation.log`
beside the new deliverables. The skips and warnings are retained in that log.
An earlier baseline gate on `c73d3480` was stopped when the pickup fix superseded
it; it is not counted as a pass.
Owner look judgment and physical fixture verification remain `PENDING-OWNER`.
