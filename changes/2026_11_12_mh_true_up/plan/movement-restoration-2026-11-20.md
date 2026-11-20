---
type: plan
status: active
area: engineering
updated: 2026-11-20
---

# Restore the movement vocabulary

Owner correction, 2026-11-20: replacing the original templates must not remove
movement behaviors. The 62-entry sample mostly demonstrates speed/reach presets
and is not accepted as complete movement coverage. This supersedes its coverage
claim, while preserving its technical verification as historical evidence.

Root owns `codex/restore-movement-vocabulary`, starting at `6277bf8a`.
Independent reviewer `/root/pickup_review` reads only. No parallel source edits.

Goal: recover the original movement vocabulary on the single current renderer,
then deliver a sequential, labeled native xLights sample with two-second dark
pauses. Distinct motion and fixture coordination come first; speed/reach variants
are not counted as additional movement behaviors.

Scope: inventory all 29 defined original movement patterns (plus NONE), including
their use by the 37 removed templates; map each to current or restored behavior.
Add only missing deterministic path capabilities and authored JSON families,
keeping typed degrees, exact musical phase, speed/range checks, and the existing
emitter. Preserve current family output. Restore choreography intent rather than
obsolete schemas or the deleted renderer. Original names that share behavior must
be identified honestly rather than counted as distinct kernels. No provider calls,
hardware output, or changes to house rendering. CI/Pages remain paused.

Initial reproduction: constructing `Movement(shape="bounce", mode="periodic", …)`
fails because the current contract admits only hold, sine_pan, sine_tilt, linear,
circle, lissajous and sweep. Historical source `0ec65d47^` has triangle, pulse and
noise-based movements, plus fixture geometry/distribution that the new catalog
omits. The earlier sample covered only current families and repeated their presets.

Acceptance:
- An explicit old-to-current coverage table with no silently dropped movement.
- Kernel tests distinguish angular travel, held positions, organic paths and
  smooth paths, and exercise transforms, periodic joins and physical rejection.
- Restored families load through the normal catalog and render through production
  code. Tests check actual movement/coordination, not just file counts.
- Existing output pins remain unchanged. Run focused tests, independent review,
  then clean-tree `make validate` before integration; disclose any failed checks.
- Regenerate the sample from the final catalog with one representative per
  behavior, neutral white/light unless intrinsic, dark pauses and names. Verify
  XSQ/frame agreement, native visibility and labeled video/package integrity.
- Record evidence/handoff and correct context/catalog docs. Owner look judgment
  stays separate from technical checks.

Affected areas: Movement schema, compile/step path kernels, catalog templates,
focused movement/catalog tests, catalog documentation, dated change evidence,
context and movement single-renderer decision. No tracked deletions planned.

Standing authorization: this owner's correction restores movement functionality;
the earlier sample/video request covers the expendable synthetic xLights show;
commit/merge/sync direction remains in force. No paid work is needed.

## Implementation decision after inventory

Historical patterns were not 29 unique paths. The lost kernel classes are constant-
speed angular reversals, repeating pose switches with dwell, and organic noise.
Add `polyline` (explicit phase/x/y knots, periodic endpoints must match, finite
paths hold their ends) and `organic` (deterministic periodic Perlin trajectories).
Polyline authors triangle, ramped pose switches and fan open/close without separate
alias kernels. Finite ramps replace the old pulse's impossible instantaneous jumps;
physical rate checks remain authoritative. Existing shapes/output stay unchanged.

Restore fan and alternating-tilt geometry using the existing named per-fixture
position presets, with explicit admission failure when the rig has not defined them.
Do not turn a fan into centered parallel motion. The synthetic sample supplies those
presets. Named catalog routines combine these paths, aims and distributions; their
speed/reach presets remain secondary. The old SPIRAL and CROSS_PATTERN were identical
Lissajous scalars on both axes, not a real changing-radius spiral. Record that mapping
honestly rather than claim those implementations had behavior they never rendered.

## Implementation and delivery status

`493518db` implements polyline/organic motion and eighteen restored arrangements;
`af774e99` adds public-field accountability tests. Independent code and artifact
reviews approved. The 24-entry replacement sample (4:02) has passed byte, native
visibility, pause, label and package checks. Full local gate remains in progress;
see [dated evidence](../evidence/2026-11-20-movement-restoration/README.md).
