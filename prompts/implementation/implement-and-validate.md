# Workflow: Implement and Validate a Change

Standard procedure for code changes in this repository.

1. **Load context** per the protocol in [AGENTS.md](../../AGENTS.md): current state →
   relevant domain docs → [changes/ACTIVE.md](../../changes/ACTIVE.md) → related
   `memories/`.
2. **Anchor in a change.** For non-trivial work, create or continue `changes/<slug>/`
   with at least a `spec.md`; resume from the latest `handoff.md` if one exists.
3. **Implement** following
   [context/engineering/conventions.md](../../context/engineering/conventions.md) and the
   confirmed idioms in
   [memories/patterns/code-patterns.md](../../memories/patterns/code-patterns.md).
   Strict types; Pydantic models own LLM-facing schemas.
4. **Validate** — run `make validate`. Zero new ruff/mypy/pytest failures; the only
   acceptable failures are those already listed in
   [memories/learnings/known-test-failures.md](../../memories/learnings/known-test-failures.md).
   Paste real command output in your report — never claim green without fresh evidence.
5. **Close out** with [handoff/session-closeout.md](../handoff/session-closeout.md):
   handoff notes into the change directory, durable knowledge promoted, indexes updated.
