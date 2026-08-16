# Memories — Shared Project Memory

Git-tracked, agent-agnostic project memory. This is **not** Claude auto-memory or ChatGPT
memory — those are machine-local supplemental caches (see the memory protocol in
[AGENTS.md](../AGENTS.md)).

## Categories

- **[decisions/](decisions/)** — durable architectural/engineering decisions and their rationale
  - [llm-plans-intent-renderer-implements-precision.md](decisions/llm-plans-intent-renderer-implements-precision.md) — accepted boundary; includes the dated narrow-channel baseline and the 2026-08-14 schema-v2 implementation resolution (D1 comparison still pending)
  - [keep-dsp-after-mir-ab.md](decisions/keep-dsp-after-mir-ab.md) — accepted P2P-T8 decision: retain the current DSP rhythm/structure default because model arms did not produce complete local evidence
  - [lane-blend-mode-overrides-recipe.md](decisions/lane-blend-mode-overrides-recipe.md) — accepted P3-T2 precedence: lane blend intent uniformly overrides recipe blend metadata in the emitted sub-layer space
  - [typed-macro-coordination-contract.md](decisions/typed-macro-coordination-contract.md) — accepted P3-T4 decision: exact four-field typed macro contract, palette/focal precedence, amended AC2 typed-reader boundary, and P3-T5 behavioral-consumption ownership
- **[learnings/](learnings/)** — non-obvious discoveries from previous work
  - [reactivation-review-2026-08.md](learnings/reactivation-review-2026-08.md) — historical `aa8d325` review conclusions (readiness, verified defect classes, external facts, strengths), with a pointer to current campaign truth
  - [known-test-failures.md](learnings/known-test-failures.md) — historical gate baseline at `aa8d325` (2026-08-13): 120 failures classified; superseded by the green integrated campaign gate
  - [simplification-pass-2026-02.md](learnings/simplification-pass-2026-02.md) — stale auto-memory case study: a claimed simplification pass that never landed on `main`
- **[constraints/](constraints/)** — limitations that repeatedly shape design
  - [python-3.12-only.md](constraints/python-3.12-only.md)
- **[patterns/](patterns/)** — known-good reusable implementation patterns
  - [code-patterns.md](patterns/code-patterns.md)
- **[inbox/](inbox/)** — staging for candidate knowledge awaiting review/promotion

## What does NOT belong here

Temporary TODOs, transient error output, speculative ideas, conversation transcripts,
current project truth (→ `context/`), active work (→ `changes/`), local agent state, or
machine-specific configuration.

## Updating

Search first; update existing files rather than duplicating; record provenance/date in
frontmatter (start from [templates/memory.md](../templates/memory.md) or
[templates/decision.md](../templates/decision.md); schema:
[engineering conventions](../context/engineering/conventions.md)); link related
documents; keep this index current. Uncertain findings go to `inbox/` until validated.
Workflow: [prompts/handoff/session-closeout.md](../prompts/handoff/session-closeout.md).
