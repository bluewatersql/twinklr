---
type: plan
status: active
area: engineering
updated: 2026-11-20
---

# Restore audited template arrangements

Owner instruction: “fix the gaps”, followed by a request for the updated preview/video.
Root owns `codex/restore-template-arrangements`, based on `108f40c2`; independent
reviewer reads only. No parallel source edits and no tracked deletions.

Restore all 37 historical named arrangements as strict current TemplateDoc JSON,
retaining the existing 25 families unchanged. This preserves selectable arrangements,
including intentionally similar motion with different light programs, without a second
renderer or old-schema compatibility. Historical factory source at `5d50580c` owns
fixture targets, step schedules, repeat modes, phase orders, formation distinctions
and light intent. Current physical degree contracts and safety checks stay authoritative;
old DMX curves are not a calibration or an exact physical-output reference.

Add the missing sine-pan/organic-tilt path and explicit step fades on the existing
compiler. Reference named rig aims for all formations, with a shipped synthetic
reference rig showing each arrangement; never infer calibrated owner aims. Preserve
INNER/LEFT/RIGHT selections, sequential 6/8-bar arcs, crossfade arrangement order,
phase direction, blackout/hold/pulse/fade intent. Disclose deliberate safe changes from
old discontinuous curves and parameter bugs rather than claiming byte parity.

Acceptance: all 37 source IDs selectable; source-derived contracts cover targets,
schedules, repeat, movement combinations and formations; emitted-frame tests prove
INNER isolation and hybrid axes, both orders of the multi-step routine, all families
render with their reference aims, missing aims refuse. Existing seven family files and
output pins remain unchanged. Independent code review and clean-tree make validate.
Then fresh sequential sample with names, two-second dark pauses, enough time for the
complete arcs, and video/package verification. For the movement preview, neutral
light may reveal blackout-only motion, explicitly labeled; authored templates retain
blackout. No color-wheel changes unless intrinsic to the existing flick.

Affected files: template schema/step compiler, catalog JSON and reference fixture
positions, test support and source-derived fixture contracts, focused tests, coverage
and current-state documents, evidence/handoff. No provider requests, hardware output
or house changes. Expendable preview and commit/merge/sync remain owner authorized.
CI/Pages stay paused. Human look judgment and physical calibration stay PENDING-OWNER.
