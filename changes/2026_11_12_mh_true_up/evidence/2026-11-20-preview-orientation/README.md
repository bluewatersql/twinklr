# Centered movement preview — 2026-11-20

Owner rejected the arrangement sampler's viewing orientation: beams pointed to one
side and made movement difficult to judge. Prior byte, pause and package checks
proved integrity but did not establish useful framing; the prior look is REJECTED.

The synthetic xLights model had OrientZero 270 for pan and 135 for tilt, canceling
its midpoint motor angles to 0/0. xLights constructs the beam along local +x, so this
made neutral point sideways. Set pan OrientZero 180 and tilt OrientZero 45: neutral
now points up. Home offsets, ranges, reverse flags and fixture channel data remain
unchanged. The front camera yaw changes 20→0, retaining pitch 10. This matches the
xLights motor/beam transform; it is a display correction, not physical calibration.

Artifacts: `/Users/ondeck/xlights/_twinklr_verify/movement-centered-2026-11-20/`.
`movement-sampler-labeled.mp4` and `movement-sampler-show.zip` contain the corrected
front view. There are 61 entries, 640 seconds and 32,000 frames, with effect labels,
chapters and two-second dark pauses. All 37 historical arrangements are included.
An angled companion is delivered at `depth-view/movement-sampler-labeled.mp4`
with camera yaw 45/pitch 20 to make depth/tilt motion easier to inspect. It retains
the same model orientation, channel bytes, timing, labels and pauses.

Fresh checks: a short fan probe was visually inspected before the full export;
its beam fan is upright, centered and symmetric. `orientation-verification.json`
proves frame bytes unchanged and XSQ differs only by its media path. Exactly nine
layout attributes changed: eight motor zero offsets and one camera yaw. The full
native audit finds all 61 cases visible, all pauses dark, and zero bright edge pixels
at 5 fps. Final video decode, 122 effect/pause label samples, 61 chapters and ZIP CRC/
relative media checks pass. Production layout/network hashes remain unchanged.

Front video SHA-256:
`7ef03e47da1536eb3b91c2429744cfae41107d499de708a1a5088a7bacc1f99c`.

No renderer or catalog source changes. Full application gate is not repeated for
scratch preview/evidence changes; latest source gate remains `caafbf9e`, 7,910 passes.
Front and companion final metadata, full decode and 122 label sample checks pass.
The companion native audit checks the full frame excluding only the four fixture
mesh boxes; the old fixed beam region included a body under this camera projection.
It also finds all 61 cases visible, all pauses dark and zero bright edge pixels.
Companion SHA-256: `850f4246a211fb09798cb9fc426624f1c7e74008c0c7afcb1d9f1738053e434b`.
xLights is closed and production hashes match. [Independent review](independent-review.md) approved both the front view/package
and the angled companion. Owner look judgment is PENDING-OWNER. CI/Pages stay
paused; hardware output stayed off.
