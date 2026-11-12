---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Context Loading

The session-start sequence is [AGENTS.md → Context loading](../../AGENTS.md#context-loading).
Routing by topic lives only in [context/INDEX.md → Topic routing](../INDEX.md#topic-routing).

Load in layers and stop when the implementation surface and acceptance criteria are clear:

1. **Always:** `AGENTS.md`, the guardrails, `context/INDEX.md`, `context/current-state.md`,
   `changes/ACTIVE.md`.
2. **Per workstream:** the one change folder the task belongs to — its brief or spec, the
   current plan, and the latest handoff. Other active changes are someone else's stream;
   read their `ACTIVE.md` row only, to avoid colliding with them.
3. **Per topic:** the `context/` pages and memories the routing table names for the task.
4. **Then the code.** Read current source and tests, and run `git status --short --branch`.

Long campaign records (for example a multi-hundred-line handoff) are audit history. Read
their "start here" section and follow links to the task spec you need; do not load them
end to end.
