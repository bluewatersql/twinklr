# Independent arrangement restoration review — 2026-11-20

Verdict: APPROVED for code review of the current working-tree implementation, after the narrow fixes below. Full clean-tree validation and artifact verification remain the integrator’s responsibility; this is not owner visual acceptance or physical calibration. No source edits or Git mutations performed by reviewer.

Scope: 37 historical named arrangements restored on the sole current renderer; existing 25 catalog JSON files preserved. Reviewed compiler dark-edge handling, period selection, path orientation, phase folding, source-contract fixtures, reference aims and authored optical states.

Resolved findings:
- Mirror reference aims initially faced inward; current rank*35 reference pans face outward.
- Historical sine-pan/cosine-tilt circles now use reverse=True and phase_cycles=-0.25, retaining traversal direction.
- Five-beat dramatic pulse cadence retained; dark edges permit explicit pulse reset without growing arrangement cycles. Ambient periodic noise closes its eight-bar cycle.
- A clipped tail shorter than both dark edges initially raised an uncaught ValueError. Compiler now omits this wholly dark instance before compiling; regression passes.
- Historical fast shutter in figure8_mirror_strobe, prism gobo in accent_snap_tunnel_hit, and blue color in ambient_random_wash were initially omitted. All three now exist as typed authored states; fixture contracts check them, and emitted-frame tests assert their declared synthetic rig words on lit frames. Preview neutralization is a separate scratch concern.

Independent evidence collected in this review:
- All 25 pre-existing catalog JSON files byte-identical to HEAD during review.
- Historical Git-source AST independently matched all 37 IDs and 43 step identities, targets, durations/offsets, movement types, geometry types and dimmer types in the source-derived fixture.
- Arrangement and restored-path focused suite: 63 passed in 10.26s before final optical-state fixes.
- Clipped-tail regression after its fix: 1 passed in 0.29s.
- Final narrow checks, three intrinsic-state emitted-frame cases plus clipped-tail regression: 4 passed in 1.04s.

No remaining blocking code findings in the reviewed scope. Exact historical DMX parity is neither claimed nor established; synthetic degree aims and declared state words are not calibration of an owner rig. Full suite was deliberately not rerun by reviewer.

## Preset follow-up: 577b242c → d4868e87

Approved. Read-only review confirms the delta adds only presets to 32 restored moving catalog documents, plus an accurate evidence note. All 32 base template objects and all other document-root data are identical between commits; existing catalog families are not touched. Independently checked all 256 presets: patches target exactly the moving steps, narrow/wide scale nonzero extents by 0.5/1.5, slow/fast scale movement period by 2/0.5, leaving static steps and intrinsic channels unchanged. The unchanged catalog-wide variation contract independently passed (1 test). This does not certify every variant on every rig; existing physical admission remains authoritative. Fresh full gate and preview verification remain pending.


## Inventory assertion and closeout documentation follow-up

Approved the exact loader inventory assertion update from 25 to 62 (previous 25 plus
all 37 historical arrangements); the targeted test independently passed in 0.08s.
Reviewed documentation counts, source provenance, preview disclosures and copied
review records. Corrections verified: 122 effect/pause label samples are distinct
from 16 exact boundary checks; artifact approval is recorded; availability in other
meters is qualified by the whole-period admission gate. Full final gate and commit
provenance remain the integrator's responsibility.
