---
type: learning
status: active
created: 2026-08-13
updated: 2026-08-13
confidence: confirmed
tags: [review, architecture, baseline]
---

# Reactivation Review 2026-08 — Durable Conclusions

_Provenance: `changes/twinklr-reactivation-review/` (baseline `aa8d325`; every major
conclusion adversarially verified by a non-author; full audit trail in
`reviews/verification.md`). This memory is the pointer + the handful of truths that
must outlive the change. Readiness: **REQUIRES_STABILIZATION**._

1. **Only the moving-heads path ships.** Display pipeline (~8.3k LOC), corpus/FE
   stack (~24k with profiling), and the evaluation harness are complete but
   unreachable from the CLI. Docs describe the union; the runtime delivers one path.
2. **The LLM→renderer channel is two strings wide** (`template_id` + `preset_id`,
   ~67 distinguishable outcomes). MacroPlan reaches rendering only as prompt prose;
   the shipped planner is lyric-blind (prompt reads nonexistent fields); the
   categorical vocabulary never reaches the renderer. The accepted LLM/deterministic
   decision is implemented in name only (see the decision record's reality-check).
3. **The renderer has a verified output-corruption cluster** (intensity always
   SMOOTH — pinned by a test; three misaligned time grids; sub-4-bar sections render
   nothing; BLACKOUT renders full brightness on drops; calibration annihilated;
   channels zero-filled against the repo's own `shutter_default=255`). Any
   quality comparison at baseline measures noise — repair-to-measurable first.
4. **Dead configuration is a class, not incidents** (~20 documented knobs inert or
   crashing). The user guide is not a reliable behavior description until roadmap
   RM-1.5 lands.
5. **No evaluation result has ever been committed**; the checkpoint writer eval-report
   needs was deleted (restorable ~10 lines, but historical artifacts are not
   replayable — schema drifted).
6. **Cache keys include model IDs but not prompt content**: model retarget is
   cache-safe; prompt edits will silently serve stale plans once session-ID reuse is
   fixed — land prompt hashing in the same change.
7. **External facts (2026-08-13, cited in `reviews/modernization.md`)**: gpt-5.6
   family current (`terra` is the recommended default target); `gpt-5-mini` retires
   2026-12-11, `gpt-image-1.5` 2026-12-01; xLights 2026.15 has first-party AI
   services but **no auto-choreography** (thesis space unoccupied) and a documented
   HTTP automation API (`addEffect`, `importXLightsSequence`); version stamps ≥2020
   accepted; `.xtiming` import is mapping-free (smallest viable deliverable).
8. **No LICENSE has ever existed** — blocks distribution independent of all code
   work; vendor-corpus mining has a rights gate before any resumption.
9. Verified strengths worth building on: schema/taxonomy auto-injection, judge
   verdict enforcement, BeatGrid authority, atomic cache commits, display writer
   dedup+trace, the existing 587-LOC `.xsq` validator, `timeline.py`, the audio DSP
   core, staged recipe promotion.
