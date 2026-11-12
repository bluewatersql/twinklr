---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Agent Authority Model

The Git repository is authoritative. Chat history, model memory, local auto-memory, and
generated summaries are advisory until reviewed and written to a tracked canonical file.
The precedence ladder is [AGENTS.md → Source of truth](../../AGENTS.md#source-of-truth);
this page says how to apply it.

- Ranks 1 (active accepted change) and 2 (implemented code, tests, config, schemas) answer
  different questions: what should be true, and what is true. When an active spec says X
  and the code does Y, that is unfinished work or a defect. Surface it in the change
  record; never resolve it silently in either direction.
- Documentation that conflicts with code and tests: inspect the implementation, then fix
  the document.
- Task scope that conflicts with context: record the decision in the active change before
  changing behavior.
- Two context pages that conflict: resolve from repository evidence and correct one.
- Model or plugin memory that conflicts with tracked files: ignore the memory.
- A tool adapter that differs from `AGENTS.md`: `AGENTS.md` wins and the adapter is fixed.

Empirical outcomes have their own rule. An offline test, a fixture, or a merged tool is
evidence about the code. It is never evidence that a live provider run, an xLights import,
a calibration, or a human judgment happened. Those outcomes exist only where a dated
evidence or evaluation record says so
([owner-gated actions](../../AGENTS.md#owner-gated-actions)).

A conclusion becomes project truth only when written to the correct tracked location with
evidence: source references, tests, command output, accepted decisions, or recorded runs.
