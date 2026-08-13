---
type: decision
status: accepted
created: 2026-08-13
updated: 2026-08-13
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

## Related

- [context/architecture/multi-agent-planning.md](../../context/architecture/multi-agent-planning.md)
- [context/architecture/pipeline.md](../../context/architecture/pipeline.md)
