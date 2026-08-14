---
type: decision
status: accepted
created: 2026-08-13
updated: 2026-08-14
---

# LLMs Plan Intent; Deterministic Code Implements Precision

_Recorded 2026-08-13; the decision itself predates this record and is reflected
throughout the codebase and docs._

## Decision

The LLM layer decides *what* should happen (template selection, categorical intensity and
duration, creative arc). Deterministic code decides *how* (curve math, DMX values, exact
timing, `.xsq` format compliance). The LLM never emits DMX values, milliseconds, or
angles directly.

## Context

Direct LLM generation of numeric lighting data is unreliable: hallucinated values,
prompt/schema drift, and unverifiable output. Choreography quality is a creative problem;
fixture control is a precision problem.

## Rationale

- Categorical vocabularies (WHISPER…PEAK, HIT…SECTION) are stable for LLMs to reason in
  and trivially resolvable by the renderer.
- Templates as complete tested units bound the LLM's action space to known-good output.
- Pydantic schema auto-injection keeps the contract between planner and renderer drift-free.

## Consequences

- New capability = new template/curve/renderer code plus categorical vocabulary, not
  prompt engineering for numbers.
- Validation splits into cheap heuristics (structure) and LLM judging (semantics).
- The renderer is the sole owner of fixture math; changes there never require prompt changes.

## Historical reality check (2026-08-13, baseline `aa8d325` — adversarially verified)

At the review baseline, the **principle stood but its description of reality was false
for the shipped moving-heads path.** Verified then: the shipped LLM decided only
`template_id` + `preset_id` (~67 distinguishable outcomes); it emitted no categorical
intensity or duration enums that reached rendering (the categorical vocabulary was
never imported by the renderer — `Intensity` and `IntensityLevel` were unrelated enums
with no converter); the creative arc (MacroPlan) reached the renderer only as prose in
a downstream prompt. The description matched the unshipped display pipeline. This is a
preserved baseline observation, not a statement about the current renderer. See
[changes/twinklr-reactivation-review/reviews/final-assessment.md](../../changes/twinklr-reactivation-review/reviews/final-assessment.md)
and roadmap RM-2.3 for the original finding.

## Implementation resolution (2026-08-14, integrated snapshot `6b2b34a`)

Phase 2P widened the shipped moving-head channel to match this decision. Schema-v2
sections carry categorical intensity, color, shutter, gobo, segmentation, and lyric
MomentCue intent; the renderer resolves those fields through fixture-aware deterministic
handlers into exact curves and DMX output. The template registry also accepts validated
data-form `TemplateDoc` records alongside Python factories, without transferring fixture
math to the model.

This implementation resolution does **not** settle D1's standing-default question. A
deterministic selector and evidence-preserving three-arm harness now exist, but the
owner-accepted calibration, real comparison, blind human review, and verdict are still
pending. Until that experiment runs, no comparison outcome or default-policy change may
be inferred from the widened channel's offline tests.

## Related

- [context/architecture/multi-agent-planning.md](../../context/architecture/multi-agent-planning.md)
- [context/architecture/pipeline.md](../../context/architecture/pipeline.md)
