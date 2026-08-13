# Claude Code Instructions

@AGENTS.md

## Claude-specific directives

- **Auto-memory is supplemental.** Claude's per-project auto-memory and any local state in
  `.omc/` or `.remember/` are machine-local caches. They are never authoritative for
  project facts. Durable discoveries flow: session discovery → review/validation →
  `memories/` (see the memory protocol in AGENTS.md and
  `prompts/handoff/session-closeout.md`).
- **Delegation.** For multi-file implementation work, prefer subagents/parallel execution;
  keep authoring and review as separate passes. Verification (`make validate`) happens
  before any completion claim.
- **Scratch output.** Write throwaway analysis and temp files to the session scratchpad,
  never into `context/`, `memories/`, or `changes/`.
