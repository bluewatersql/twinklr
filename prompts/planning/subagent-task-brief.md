# Subagent Task Brief

Use when delegating a task to a subagent. The brief is everything the subagent knows: it
has none of your conversation. One brief per task; concurrent briefs own disjoint files
([AGENTS.md → Parallel development](../../AGENTS.md#parallel-development)).

## Brief shape

- **Objective** — the outcome and why it matters, in a paragraph. State what done looks
  like, not the steps to get there.
- **Read first** — `changes/shared/agent_guardrails.md`, the change's brief or task spec,
  and the specific context pages, memories, and source files that matter. Give paths.
- **Already known** — what you have established or ruled out, so it is not rediscovered.
- **Modify / Create** — the explicit files the agent may edit or add. Anything else is out
  of scope; the agent reports the need instead of editing.
- **Constraints** — acceptance criteria, boundaries not to cross, and any owner-gated
  action that is not authorized for this task (live provider calls, owner-local data,
  xLights mutation).
- **Validation** — the exact commands to run and where to run them (its own worktree).
- **Git** — whether the agent may commit. The default is the worker rule in
  [AGENTS.md → Parallel development](../../AGENTS.md#parallel-development).
- **Report back** — summary, files touched, each validation command with its actual
  outcome, deviations from the brief, blockers, and anything inferred rather than
  verified. No claim without evidence.

## Sizing

Delegate work that is independent and can be verified from its report. Keep work that
shares files or needs your running context in your own session. For a review, give the
reviewer the diff and the acceptance criteria, not your conclusion.
