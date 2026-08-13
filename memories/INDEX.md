# Memories — Shared Project Memory

Git-tracked, agent-agnostic project memory. This is **not** Claude auto-memory or ChatGPT
memory — those are machine-local supplemental caches (see the memory protocol in
[AGENTS.md](../AGENTS.md)).

## Categories

- **[decisions/](decisions/)** — durable architectural/engineering decisions and their rationale
  - [llm-plans-intent-renderer-implements-precision.md](decisions/llm-plans-intent-renderer-implements-precision.md)
- **[learnings/](learnings/)** — non-obvious discoveries from previous work
  - [known-test-failures.md](learnings/known-test-failures.md) — pre-existing failures on `main` (reported Feb 2026; re-verify before relying)
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
