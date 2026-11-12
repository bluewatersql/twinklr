---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Agent Memory Policy

Generated or conversational memory is advisory. It never overrides tracked content,
source, tests, accepted decisions, or active change records. This covers ChatGPT memory
and chat history, Claude project memory and auto-memory, `.omc/`, `.remember/`,
`.memories/`, `.opencode/`, local scratch notes, and plugin, hook, or MCP state. The
agent-state directories are gitignored and stay that way.

The root [`memories/`](../../memories/INDEX.md) tree is different: tracked, reviewed, and
shared by every tool. Promotion goes through
[session closeout](../../prompts/handoff/session-closeout.md); never point an agent's
automatic memory stream at it. Destinations follow the
[promotion rules](../INDEX.md#promotion-rules). An unverified item worth keeping goes to
`memories/inbox/` with the missing verification named.

A local memory is a lead. Verify it against code, tests, logs, or a reviewed change record
before acting on it or promoting it; if it cannot be verified, leave it out. The
[simplification-pass case study](../../memories/learnings/simplification-pass-2026-02.md)
records what happens otherwise: an auto-memory described work that never landed on `main`.

Never store secrets, tokens, credentials, raw model reasoning, chat transcripts, or
unreviewed generated summaries in the repository.
