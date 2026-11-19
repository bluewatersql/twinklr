---
type: plan
status: active
area: engineering
change: 2026_11_12_mh_true_up
updated: 2026-11-19
---

# House musical synchronization

The owner rejected the recovered previews: moving heads look closer to sync, but
the house flashes appear unrelated to the song and expected transitions are absent.
This is a failed house look judgment, not a pending verdict. The earlier waveform
and visibility checks establish transport alignment and coverage only.

## Goal and scope

Trace the rejected house output from source musical events through the saved display
plan, timing resolution, recipes and xLights rendering. Reproduce off-beat flashes
and missing transition responses before choosing a repair. Preserve moving-head
effects and the existing typed intent / deterministic precision boundary. Use the
three already-authorized songs and scratch show; no production-show mutation or
physical fixture output. Reuse plans for diagnosis before spending on replanning.

Root owns `codex/house-musical-sync` from `03213e9e`, implementation, tests and
evidence. Independent review uses a read-only snapshot after the repair. No deletion
is planned. Potential source areas are display composition, recipe compilation,
display planning context, and their tests; narrow ownership after diagnosis.

## Acceptance and validation

- Identify concrete musical events and unrelated rendered house changes in the
  rejected preview, with timings and the responsible plan/recipe/effect.
- A failing replay or regression exercises each confirmed cause; changing the
  responsible input or implementation changes that observable result.
- Rendered rhythmic intent follows the authoritative musical timing, and requested
  section/phrase transitions produce a visible response at their intended boundary.
- Re-export and inspect the repaired house alongside the source audio; report
  remaining limitations explicitly. Audio-file alignment, effect counts and light
  coverage alone cannot satisfy this criterion.
- Moving-head payloads and timing remain unchanged unless a separate confirmed
  shared cause requires a documented scope decision.
- Independent review, targeted tests and clean-tree `make validate` before a
  technical completion claim. Owner taste acceptance remains separate; do not
  substitute an automated score for the owner's verdict.

## Current state

Confirmed causes: recipe PULSE intent never received the detected beat grid or lane
clock; coordination restarted fade-in on sliced rhythmic events; palette CUT retained
one-second BASE fades; planner bar positions used nominal tempo instead of the
renderer grid, and timed lyric cues/audio objectives were omitted from house context.
Regression tests reproduced those failures. Root is repairing these owners and
passing the same musical evidence to planning, refinement and section judging.
No planner output schema or moving-head implementation changes are intended.

A saved-plan xLights replay verifies the brightness envelope reaches the actual
preview. It is diagnostic, not an accepted look. Fresh house-only planning uses the
same three authorized song bundles, cached audio profiles, macro plans and grids.
The 2026-11-13 and 2026-11-19 approvals in the implementation brief cover these
provider calls, whose purpose is to exercise the repaired timed musical context.
Each section gets at most two planner iterations, with results retained for replay.
Existing MH XML is preserved exactly. No additional analysis or fixture output.

Known separate limitations: placement timing_hint and recipe timing_offset_beats
are not implemented by this repair; the rejected saved plans all used ON_BEAT.
Untimed decorative textures and Strobe pixel selection remain effect-native.
They must not be described as beat-driven. Owner taste verdict remains REJECTED
for the prior previews; new results require a new owner judgment.


## Rendered accent follow-up

Fresh Favor verse_1 exposes a further planning-input omission: the shaped recipe
construction existed but no planner template rendered it. Names saying "hit"
concealed Meteors particle streams that barely changed the house at 43.04, 45.32,
and 54.40 seconds. A scratch native warmup experiment did not make these robust
impacts; no warmup behavior is being added to production. Expose the existing
ACCENT recipe constructions to planning, refinement and judging, and require an
available solid On hit for an indispensable immediate arrival. Keep motif textures
as companions. Replan only the demonstrated failed verse, retain its first attempt,
and verify its actual pixel response. This keeps creative choice in the LLM and
uses the existing catalog/render path; no injected global flashes or replacements.

Full validation also found optional musical-context guards missing from old prompt
contexts, and a replay metric changed from 30 to 32 EffectDB entries because pulsed
layers now disable native shimmer and fades. Update only the current replay metric
`tests/regression/baselines/02_rudolph_display.replay.metrics.json` after checking
the added settings variants (four added and two retired; net two). Preserve the historical XSQ, original metrics,
recipe snapshot, effect vocabulary, layer counts and timing pins.
