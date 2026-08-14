---
type: learning
status: historical
created: 2026-08-13
updated: 2026-08-14
confidence: confirmed
tags: [review, architecture, baseline]
---

# Reactivation Review 2026-08 — Durable Conclusions

> **Historical review baseline.** The numbered conclusions below describe the
> adversarially verified `aa8d325` baseline and explain why the review verdict was
> **REQUIRES_STABILIZATION**. They are preserved as findings, not silently rewritten as
> current behavior. The active build campaign has since completed Phases 0 and 1K,
> merged and independently verified all Phase 1P and Phase 2P offline implementations
> plus all Phase 2K tooling, and reached a green integrated gate at `6b2b34a`. Phase 1P,
> 2P, and 2K exit evidence remains owner-gated. Current truth lives in
> [context/current-state.md](../../context/current-state.md); unfinished owner gates and
> Phases 3–4 live in the campaign
> [handoff](../../changes/twinklr-reactivation-review/build/plan/HANDOFF.md).

_Provenance: `changes/twinklr-reactivation-review/` (baseline `aa8d325`; every major
conclusion adversarially verified by a non-author; full audit trail in
`reviews/verification.md`). This memory is the pointer + the handful of baseline truths
that must outlive the change. Review-time readiness: **REQUIRES_STABILIZATION**._

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
8. **Licensing is a non-issue by owner decision** (personal, non-commercial
   project). No LICENSE exists; add one only if distribution is ever wanted.
   Courtesy rule: don't redistribute vendor-derived content; learning from
   purchased material for personal use is normal use.
8b. **The corpus pipeline is the project's learning system** (owner-corrected
   reading, v2 proposal §0.3): propensity learns effect↔element-type affinity,
   taxonomy learns choreographic function, mining learns layered idioms — it is how
   the system knows what megatree/arch/icicle choreography looks like. Its four
   broken edges (uuid identity, the unreachable apply edge, the unwired
   active-learning label loop, the deleted eval writer) are repair targets, NOT
   grounds for extraction. v1's "extract to sibling repo" recommendation is
   superseded.
9. Verified strengths worth building on: schema/taxonomy auto-injection, judge
   verdict enforcement, BeatGrid authority, atomic cache commits, display writer
   dedup+trace, the existing 587-LOC `.xsq` validator, `timeline.py`, the audio DSP
   core, staged recipe promotion.
