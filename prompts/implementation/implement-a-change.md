# Implement a Change

Use when executing against an active `changes/` record.

1. Read the change's brief or spec, current plan, and latest handoff.
2. Inspect current code, tests, and config in the affected area. Run
   `git status --short --branch` and confirm you own the branch or worktree.
3. Make the smallest complete change that satisfies the acceptance criteria, following
   [context/engineering/conventions.md](../../context/engineering/conventions.md) and the
   idioms in [memories/patterns/code-patterns.md](../../memories/patterns/code-patterns.md).
   Strict types; Pydantic models own LLM-facing schemas.
4. Add or update tests for changed behavior.
5. Validate with the narrowest check that proves the change, then run `make validate`.
   There are no accepted failures; report real command output.
6. Record assumptions, scope expansion, and validation results in the change folder as
   you go.
7. When durable behavior changes, update the owning `context/` page.
8. End the session with [../handoff/complete-a-handoff.md](../handoff/complete-a-handoff.md).
