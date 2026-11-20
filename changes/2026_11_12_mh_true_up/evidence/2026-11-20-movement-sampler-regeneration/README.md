# Fresh movement sampler regeneration — 2026-11-20

Owner requested: “ok. regenerate the sample sequence and video as before”.
Generated all cases afresh from `22fac0fb`; no cached case frames copied, no source
or catalog changes. Scratch show authorization and commit/merge/sync direction
remain in force. No provider requests or hardware output; CI/Pages stay paused.

Local deliverables (generated artifacts remain outside Git):
`/Users/ondeck/xlights/_twinklr_verify/movement-sampler-regenerated-2026-11-20/`

- `movement-sampler-labeled.mp4`: 24 named entries, eight seconds each, two-second
  dark separators, 242 seconds total. Includes two labeled static aim references;
  excludes optical-only Zoom Wave and repeated speed/reach variants.
- `movement-sampler.xsq` and portable `movement-sampler-show.zip`, containing
  matching synthetic four-head layout, profile/job, timeline and relative silence media.
- Generation/export/label/audit scripts and logs, `verification.json`,
  `video-audit.json`, `delivery-verification.json`, and visual contact sheet.

Fresh checks passed: all 774,400 emitted channel bytes agree with the sequence;
12,100 frames at 50 fps; every non-static case moves while lit; all pause frames
have zero dimmer. Native video decoded and sampled at 5 fps: all 24 entries have
visible beams, all separators dark, zero bright edge pixels. Labeled video fully
decoded; 1280 × 824, 242 seconds, 24 chapters, all 48 effect/pause label samples
matched. ZIP CRC and relative media path passed. Labeled Bounce Fan frame inspected.
Video SHA-256: `3d52b1a7c9e9a8e3f02e532587239b1f9238ab994c8534229ee760407d300c6f`.

xLights native render/export succeeded with output off. Preview pane restored and
application closed. Original production layout/network SHA-256 values unchanged.
Full `make validate` was **not rerun** for this artifact/documentation-only task;
source gate on `4453160c` previously passed (7,858 passed, 30 skipped), recorded in
[restoration evidence](../2026-11-20-movement-restoration/README.md).
Independent artifact review by `/root/pickup_review`: **approved, no findings**.
Reviewer independently checked all bytes, lit movement per head, pauses, metadata,
chapter timing, 14 exact label boundaries and ZIP consistency. The review is saved
as `independent-review.md` in the scratch root. Owner visual judgment remains
PENDING-OWNER.
