---
type: evidence
status: active
area: engineering
updated: 2026-11-20
---

# Restored movement vocabulary and replacement sample

## Owner correction and scope

On 2026-11-20 the owner rejected losing movement behaviors when the original
renderer/templates were replaced, and rejected treating 60+ speed/reach examples
as distinct movement coverage. The previous sampler's transport checks remain
valid, but its complete-coverage claim is superseded. Work follows the
[restoration plan](../../plan/movement-restoration-2026-11-20.md).

The [coverage inventory](../../../../catalog/templates/moving_heads/movement-coverage.md)
accounts for all 29 original named patterns plus NONE and all 37 removed template
uses at `0ec65d47^`. Original duplicate curves, misleading names, light-only variants,
rig-specific aim consolidations and narrative composition are identified explicitly.
This is movement restoration on the single renderer, not old-renderer byte/look parity.

## Implementation

`493518db` adds typed phase/x/y polyline knots for angular travel and explicit
travel/dwell, plus periodic deterministic Perlin motion. The normal exact musical
phase, transforms, degree limits, per-frame speed checks and DMX emitter remain
in force. Repeated polyline paths must close exactly; finite paths hold endpoints.
Finite travel replaces old instantaneous pose pulses deliberately. Existing shape
behavior and the original seven family documents are unchanged.

Eighteen authored routines bring the catalog to 25 families including optical Zoom
Wave. Restored arrangements include Bounce Fan, alternating Zigzag, Pop Lock/Hit,
organic meander, traveling waves, Fan Iris, mirrored radial fan, chevron pendulum,
asymmetric orbit and simultaneous LEFT/RIGHT counter-sweeps. Two labeled static
references show fan and tunnel aims. Aim-dependent routines require explicit named
per-fixture rig position presets and refuse missing aims; the preview supplies
synthetic positions rather than installing defaults on owner hardware.

Review found symmetric polyline reversal could be advertised as a change when it
was a no-op. The modifier now compares both paths at all transformed breakpoints,
including finite and shifted paths, before offering reversal. Independent sampling
covered 60 shifted/rotated/finite/periodic configurations. Review also found the
missing split-counter arrangement; it was added with explicit simultaneous halves.

`af774e99` registers the four new public configuration paths with emitted-frame
behavior tests. These tests change each knot field through the production renderer
and verify changed DMX output. This fixes the configuration-accountability failures
found by the first full gate attempt.

## Fresh checks

- Initial focused path/production tests: 26 passed; after arrangement and symmetry
  additions: 36 passed.
- Broad family/path/pin run: 209 passed and one old assumption failed (static
  references were assumed to have reach/rate presets). The test now asserts that
  static references have no presets and was rerun successfully. Original pinned
  fingerprints, frame bytes and XSQ output were unchanged.
- First full gate on `493518db`: stopped after two config-inventory failures were
  identified; 2,005 tests had passed. No passing full gate is claimed for that run.
- After the accountability fix: all config inventory and restored production tests
  passed, 233 total.
- The next full gate exposed one old CLI test that still expected the original
  seven template IDs. It was stopped, the assertion was updated to all 25 current
  IDs, and the focused CLI/restored tests passed (26). No full pass is claimed.
- Planning metadata now separates static/organic low-energy routines from
  high-energy bounce/pop-lock/zigzag. Motion-producing data is unchanged.
- Final clean-tree full `make validate`: PENDING. Command:
  `UV_NO_SYNC=1 UV_OFFLINE=1 PYTEST_ADDOPTS='-n 8 --dist loadfile' make validate`.
- Independent reviewer `/root/pickup_review` approved code `493518db`, the narrow
  `af774e99` additions, and final delivery artifacts, with no remaining findings.
  The reviewer independently ran the focused tests, verified counterphase and
  symmetry, and accepted the explicit inventory scope without claiming old look parity.

Remote CI and Pages remain paused on owner direction. No provider calls, audio
analysis or hardware output occurred.

## Native sample and delivery

Local scratch root:
`~/xlights/_twinklr_verify/movement-restored-2026-11-20/`.

- `movement-sampler-labeled.mp4`: native xLights video with a separate title strip,
  24 routines/reference entries once each, 8 seconds per entry and 2 seconds dark
  between them. Total 242 seconds (4:02), including the initial two-second pause.
  H.264, 1280×824, 50 fps, 12,100 frames, 24 chapter markers; silent by design.
- `movement-sampler-show.zip`: portable XSQ with matching expendable preview layout,
  network, explicit synthetic profile/aims/job, relative `silence.wav`, and timeline.
- `movement-sampler.xsq`, `frames.npz`, `timeline.json`, `verification.json`,
  `video-audit.json`, `delivery-verification.json`: replay and transport evidence.
- Scratch `generate.py`, `setup-show.py`, `export.py`, `label-video.py`,
  `audit-video.py`, `verify-delivery.py`: reproducibility orchestration.

The sampler renders source `493518db`; subsequent changes affect tests, documentation
and routine planning metadata, not the frame-producing fields.
The sequence independently reconstructs to all 774,400 frame bytes. Every non-static
entry moves while lit on every head; every pause is dark. The finite snap uses the
previous sample's verified dark lead-in so its movement is shown while lit.

xLights 2026.20 rendered/exported the entire sequence. The native audit sampled
1,210 frames at 5 fps: every entry has visible beam pixels, every pause is dark in
the beam region, and no sampled bright beam pixels touch the top/side edges. All 24
contact-sheet rows were visually inspected. The label video fully decodes; all 48
sampled effect/pause strips match the source titles (max mean pixel error 0.850/255).
ZIP CRC and relative media-path checks pass. The independent reviewer checked
fourteen exact label boundaries, every chapter boundary and package content agreement.

Final labeled-video SHA-256:
`3d52b1a7c9e9a8e3f02e532587239b1f9238ab994c8534229ee760407d300c6f`.

The preview pane was widened for native export and restored afterward. Fixture
output was off, xLights closed, and both production show files passed their original
SHA-256 checks. Generated artifacts remain outside the repository.

These checks establish behavior, transport and visibility. Owner playback/taste
judgment and physical-fixture acceptance remain PENDING-OWNER.
