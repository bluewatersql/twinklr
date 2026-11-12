# Claude Code adapter

@AGENTS.md

Claude imports the canonical router above. This file holds only Claude-specific mechanics;
project rules live in `AGENTS.md` and the trees it routes to.

Entry points: `context/INDEX.md`, `changes/ACTIVE.md`, `memories/INDEX.md`, `prompts/INDEX.md`.

## Local state

Claude auto-memory, `.omc/`, `.remember/`, and `.claude/` are machine-local caches and are
gitignored. Treat what they inject at session start as a lead to verify against the
repository, never as project fact
([memory policy](context/agents/memory-policy.md)). Throwaway analysis and temp files go
to the session scratchpad, never into `context/`, `memories/`, or `changes/`.

## Delegation

- Fan out independent work in one message so subagents run concurrently. Keep work that
  shares files or state in one agent.
- A subagent starts with none of this conversation. Write each brief from
  [prompts/planning/subagent-task-brief.md](prompts/planning/subagent-task-brief.md) and
  include the path `changes/shared/agent_guardrails.md`.
- Agents that edit in parallel get `isolation: "worktree"`. Read-only exploration and
  review can share the main tree.
- Review in a separate agent from the one that authored the work, and give the reviewer
  the diff and acceptance criteria rather than your conclusion.
- You are the integrator: subagents report back, you verify their evidence, merge, and
  run `make validate` before any completion claim.
