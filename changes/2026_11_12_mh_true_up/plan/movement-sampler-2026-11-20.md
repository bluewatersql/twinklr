---
type: plan
status: complete
area: engineering
updated: 2026-11-20
---

# Sequential movement sampler

Owner request: regenerate the moving-head sample with all movement effects in
sequence, pauses between effects, and effect-name video overlays. Color wheel and
dimmer are neutral unless intrinsic to a movement routine. No paid planning or
hardware output is needed. Existing CI/Pages pause remains in force.

Root owns scratch generation and documentation on `codex/movement-sampler`.
Use the current production renderer and emitter, without changing application
source. Cover every pan/tilt movement shape (including periodic/finite sweep),
then each catalog pan/tilt family and its named reach/rate variants. Zoom Wave optical modulation is outside this movement-focused request; its
sine-pan component is covered by the movement shapes. Use a four-head
synthetic preview profile so the entire movement vocabulary can be shown without
claiming admission or calibration on the owner's physical rig.

Each example receives eight seconds and a two-second dark pause; the finite
movements hold their destination. Preserve required dark returns and wheel-flick
masking. Generate an XSQ, matching profile and timeline, and an xLights-rendered fixture
preview with burned-in movement names, named variants, and pause labels. The
video must visualize the exact emitted pan/tilt/dimmer/color bytes, not a separately
invented motion. Generated files stay local under
`~/xlights/_twinklr_verify/movement-sampler-2026-11-20/`.

Acceptance: catalog/shape coverage manifest; consecutive non-overlapping slots;
all pause frames dark; visible movement in each non-hold example; complete XSQ
parse and frame agreement; playable full-length video with names and pauses;
independent artifact review and dated evidence. No new application-code gate is
needed for this artifact-only run; disclose that the full gate was not rerun.

Review caught six snap presets whose motion finished during initial entry darkness.
For each snap, render a two-second lead-in before the section and place the final
half-second of its dark preposition inside the existing two-second pause, after
the previous routine has returned to neutral. Keep slot durations unchanged.
Require every non-hold case to change pan/tilt while lit on every head, rather than
counting dark repositioning as demonstrated movement. No renderer changes.

Completed: all 62 entries compile, all non-hold examples move while lit, all
pauses are dark, all emitted bytes match, and xLights exported the full sequence.
The labeled video fully decodes; its 124 effect/pause label samples and 62 chapters
match the timeline. The portable show ZIP passes CRC and media-path checks.
See [evidence](../evidence/2026-11-20-movement-sampler/README.md).
