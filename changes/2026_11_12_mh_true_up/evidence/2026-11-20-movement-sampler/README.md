---
type: evidence
status: complete
area: engineering
updated: 2026-11-20
---

# Sequential movement sampler

Owner requested the moving-head sample sequence regenerated with movement effects
shown sequentially, pauses between entries, and video effect-name labels. Color
wheel and dimmer behavior are only retained where intrinsic to the routine.

Source is `e0376f66`; no application source, template catalog or tests changed.
Scratch artifacts are local at
`~/xlights/_twinklr_verify/movement-sampler-2026-11-20/`.
Remote CI and Pages remain disabled. No provider calls or hardware output.

## Coverage and construction

62 entries, eight seconds each, with two seconds dark between entries and a
two-second opening pause: 622 seconds total, 31,100 frames at 50 fps.

- Eight shape/mode demonstrations: hold reference, sine pan, sine tilt, finite
  linear, circle/ellipse, Lissajous, periodic sweep, finite sweep.
- Six pan/tilt routines, each at base plus eight named reach/rate presets:
  Finite Snap Hold, Fly-In Cascade, Fly-Out Cascade, Masked Wheel Flick,
  Mirror Wings, and Target Orbit.
- Optical zoom modulation is outside the clarified movement scope; Zoom Wave's
  sine-pan component is represented by the sine-pan shape.

Production `RenderingPipeline` creates the frames, and the shared production
emitter exports their DMX runs. Test-support constructors supply a clearly
synthetic four-head, 16-channel preview profile with 720 degrees/second axis
limits. This demonstrates the vocabulary; it does not claim those variants are
admitted on the owner's physical rig. The matching expendable xLights layout
maps pan 1/2, tilt 3/4, dimmer 5, color 7. It has no live output. White is the
neutral color; masked wheel flick retains its required color/masking behavior.
Authored dark returns and parking remain intact.

Independent review found six finite-snap variants initially finished their motion
before the 500 ms startup darkness ended. The scratch sampler now renders snaps
with a two-second settled lead-in, placing its final half-second inside the
preceding pause after the previous routine returns to neutral. All snap variants
now move while lit. Slot lengths did not change; production renderer code did not
change. The first attempt's case frames are retained separately.

## Validation and review

`verification.json` records 1,990,400 emitted bytes independently reconstructed
from the exported XSQ and matched to the frame array. Every pause has dimmer zero.
Every non-hold example changes pan/tilt while lit on each head. The reviewer
(`/root/pickup_review`) independently confirmed coverage, byte identity, dark
pauses, lit movement, prelude equivalence and splice speeds below the profile
limit, then approved the corrected frame/XSQ artifacts.

xLights 2026.20 loaded, rendered and exported the final 622-second sequence in the
scratch show. Camera motor orientation and framing were checked on a short native
export first. The final native-video audit sampled at 5 fps: every entry has
visible beam pixels; every pause has no beam pixels in the beam region; no sampled
bright beam pixels touch the top/side frame edges. Contact sheets for the eight
shapes and six base routines were visually inspected. These observations establish
sample transport/visibility, not a human taste or hardware acceptance verdict.

The pane width was restored after export. The API confirmed fixture output off
and xLights closed. Both production show files, `xlights_rgbeffects.xml` and
`xlights_networks.xml`, passed their original SHA-256 checks afterward.

The full repository gate was not rerun for this artifact/documentation-only task.
The prior full gate on `a5e52265` is recorded in the
[house repair evidence](../2026-11-19-house-musical-sync/README.md#completion-gate).
Fresh validation is the artifact checks here, final decode/metadata checks, and
`git diff --check`.

## Deliverables

- `movement-sampler-labeled.mp4`: native xLights preview plus a burned-in title
  strip naming each effect/preset, pause labels, and chapter markers.
- `movement-sampler.xsq`: the matching sequence with effect-name/pause timing tracks.
- `movement-sampler-show.zip`: sequence, matching preview layout/profile, silent
  media and timeline; use its expendable show rather than a physical rig layout.
- `timeline.json`, `frames.npz`, `verification.json`, `video-audit.json`, and
  `movement-contact-sheet.jpg`: local replay and verification evidence.
- `generate.py`, `setup-show.py`, `export.py`, `label-video.py`, `audit-video.py`:
  reproducibility scripts. These are scratch orchestration, not application paths.

Final labeled video fully decoded without errors: H.264, 1280×824, 50 fps,
31,100 frames, 622 seconds, 62 chapter markers. All 124 sampled effect/pause
labels matched their source title images (maximum mean absolute pixel error
0.844 on a 0–255 scale after encoding/scaling). The portable ZIP passed its CRC
check and its XSQ references the included `silence.wav` relatively. The final
labeled preview frame was visually inspected. `delivery-verification.json`
records metadata and the video SHA-256. Application behavior is unchanged.

Final independent delivery review (`/root/pickup_review`, 2026-11-20) approved
the video and portable show package with no blocking findings. The reviewer
verified video metadata, all 62 chapter names, ten exact-boundary effect/pause
labels, ZIP integrity, packaged file agreement, and the relative media path. The
first chapter includes the two-second introduction.
