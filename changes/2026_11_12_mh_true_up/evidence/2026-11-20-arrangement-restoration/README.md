# Arrangement restoration — 2026-11-20

Owner authorized fixing the audited gaps and requested the updated sequence/video.
All 37 historical IDs at `5d50580c` now have strict current-schema catalog JSON,
using the existing renderer. Existing 25 files remain unchanged. Total 62 templates;
the movement sample shows 61 bases, excluding Zoom Wave. This count is unrelated
to the old 62-entry preset sampler.

Restored contracts: per-step target groups; all named formation combinations with
shipped synthetic reference aims; sine-pan/organic-tilt scattered waves; 6-bar build/
drop/recover, 8-bar intro/main/outro and two-way crossfade step ordering; original
repeat modes and pulse/fade/hold/blackout intent. Exact historical DMX/frame parity
is not claimed. Explicit safe degree extents replace old normalized DMX scaling;
noise is periodic, ambient noise closes its eight-bar cycle, finite pose transfers
replace jumps. Five-beat dramatic pulse cadence is retained. Half-beat dark edges
around changed steps or discontinuous pulse repeats give the existing transaction
planner time for physical repositioning. Rig aims remain explicit owner authoring.

Source-derived fixture contracts cover all37 historical IDs. Fresh focused tests:
88 passed in13.31s, plus321 config/step/topology checks in2.94s; mypy passed661 files.
Initial tests exposed a too-long ambient noise cycle, overly fast chaos reach and
missing reposition gaps between steps. Those defects were fixed; no physical checks
were weakened. Independent early review corrected mirror aim ordering and circle
traversal direction. Review also found and fixed a short clipped-tail exception and omitted intrinsic
blue/prism/fast-shutter states. These now have contract and emitted-frame tests.
Latest arrangement suite: 52 passed in 11.55s. Independent code and artifact review
approved; full gate is running on `d4868e87`.

Preview root: `/Users/ondeck/xlights/_twinklr_verify/movement-arrangements-2026-11-20/`.
The preview uses neutral white light except intrinsic masks/flick, and labels the
two authored blackout routines as motion revealed. Authored templates retain their
light programs; preview overrides live only in scratch. Longer arcs get full cycles,
including both orders of Crossfade Between Steps, with two-second dark separators.
No paid calls, hardware output or production-show changes. CI/Pages remain paused.
Owner visual judgment stays PENDING-OWNER.

The first full gate on `577b242c` found that restored moving arrangements lacked the
catalog-required narrow/slow/wide/fast and combined presets. The run was interrupted
after that failure to avoid spending time on an invalid snapshot. Added the existing
reach/rate ladder to every restored moving arrangement; static arrangements keep no
movement presets. The unchanged catalog-wide variant contract test then passed.
Base arrangements and preview frames are unchanged by these preset additions.


## Delivery checks

Delivered `movement-sampler-labeled.mp4` and `movement-sampler-show.zip` in the
preview root above: 61 labeled cases, 640 seconds, 32,000 frames at 50 fps, 1280×824.
All 37 historical IDs plus the earlier 24 bases appear once; seven are static aim
references. Zoom Wave is excluded. This is arrangement coverage, not a claim of 61
unique motion kernels. Full 6/8-bar arcs and both crossfade step orders are shown.

`verification.json` records all 2,048,000 emitted channel bytes matching XSQ,
all separators dark and motion present in every non-hold case. `video-audit.json`
records every case visible and no bright beam clipping at the top/side edges in
3,200 sampled frames. `delivery-verification.json` confirms 122 effect/pause label
samples, 61 chapters, successful ZIP CRC and portable relative media paths. The
independent review additionally checked 16 exact first/last boundary frames.
The MP4 muxer begins the first chapter at zero, including the two-second intro;
all remaining chapter starts and every chapter end match the manifest.

Video SHA-256: `cb2d9f529e945e741c7ad690d643a37253c2b08ad8a58ad94d674b9076ea1766`.
Rendered from clean `577b242c`; final source `d4868e87` adds only the missing
reach/rate preset ladders. Independent comparison proved all base objects unchanged,
so the delivered base preview represents the final source without another render.

[Independent code review](independent-code-review.md) and
[independent artifact review](independent-artifact-review.md) both approved.
Production layout/network hashes remained unchanged; xLights was closed after
export with fixture output off. No owner taste judgment or calibration is claimed.


The gate on `d4868e87` also exposed a stale loader test asserting 25 catalog entries.
Its exact inventory assertion now expects the verified 62 (25 + 37); the unchanged
loading/idempotence checks and all 20 loader tests pass (0.10s). Independent review
approved the count correction and independently reran the affected test (0.08s).
This changes no renderer, catalog or preview bytes. The complete gate will rerun
on the committed correction; no failed run is treated as a passing gate.
