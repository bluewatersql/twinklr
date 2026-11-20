# Independent centered-preview review — 2026-11-20

Verdict: APPROVED for corrected front-view framing and delivery integrity. Owner acceptance remains PENDING-OWNER; this is not physical calibration.

Visual review inspected the upright symmetric probe and 24 native frames across angular pan, angular tilt, target orbit, INNER pendulum, scattered wave and split counter-sweep. The prior sideways bias is corrected: pan sweeps cross center, fixture formations are easier to distinguish, and INNER isolation is clear. xLights source confirms why: GetPosition(midpoint) produces negative half travel; old OrientZero values cancelled this into the +x reference beam, while new pan180/tilt45 offsets rotate neutral emission upward. Display ranges, channel maps and direction flags remain unchanged.

Important limitation: the frontal camera compresses depth. Tilt-only motion can read mainly as beam-length change, particularly near vertical aims. This is projection rather than missing motion or altered rates. The angled companion addresses this limitation and is approved in the follow-up below.

Independent final front-delivery checks: frames.npz, timeline, fixture profile, job and media are identical to the prior arrangement delivery; XSQ is identical apart from media location. Labeled video is1280x824,50fps,32000frames,640seconds,61chapters; hash matches delivery record. Chapter1 includes the2second intro; other boundaries match. Twelve exact boundary label frames pass(maxMAE below1). ZIP CRC and all bundled files match corrected scratch artifacts, including pan/tilt orientation180/45 and camera yaw0/pitch10; media is portable silence.wav. Native audit records61visible cases,dark sampled pauses and0bright edge pixels; delivery check records122label samples.

All61bases, full arcs and neutral-light/blackout-reveal disclosures carry forward unchanged. No source edits, UI changes, provider calls or rerenders performed by reviewer.

## Angled companion — final review

APPROVED as a complementary depth view, with owner acceptance still pending. Inspected 16 native frames across angular tilt, orbit, INNER pendulum and scattered wave. At yaw 45 / pitch 20, tilt changes visible beam direction as well as length; the depth dimension is easier to judge than in the frontal view. INNER isolation and scattered crossings remain legible. The front view remains better for symmetric formation comparison.

Independently confirmed identical model definitions and identical XSQ content after media-path normalization between front and angled shows. Only camera projection changes; no altered DMX, rates or travel ranges. Final labeled companion independently reports 1280×824, 50 fps, 32,000 frames and 61 chapters; SHA-256 matches its delivery record. Integrator’s full decode and 122 label comparisons pass. Final native audit has 61 visible cases, zero bright edge pixels and pause-region maximum 1/255.

Reviewed the changed pause mask against the actual dark reference image. Four fixed 15×15 boxes at 320×180 cover only the head/yoke neighborhoods; the remainder of the full image is tested. This is appropriate because the oblique camera places one fixture body above the former fixed 108-row cutoff. Zero dimmer bytes already established for every separator independently corroborate darkness; the mesh exclusion does not substitute for that channel check.

No blocking framing or delivery defects found in either final view.
