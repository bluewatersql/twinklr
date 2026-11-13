---
type: context
status: active
area: governance
updated: 2026-11-12
---

# Multi-Agent Operating Model

The coordination rules are in
[AGENTS.md → Parallel development](../../AGENTS.md#parallel-development) and
[Review](../../AGENTS.md#review). This page adds the operating detail.

## Roles

Roles describe responsibilities, not vendors or models: investigator, planner,
implementer, test engineer, reviewer, integrator. One agent may hold several roles over
time, but never author and reviewer of the same work.

- The **integrator** (usually the orchestrating session) owns Git state: branches, merges,
  pushes, and the final `make validate`. Workers edit files in the tree they were given
  and report back, under the Git rule in `AGENTS.md`.
- A **reviewer** inspects the actual diff, the acceptance criteria, tests, and validation
  evidence. An agent's narrative does not replace Git evidence.
- An acceptance check must be able to fail: show that it discriminates on a pre-fix or
  adversarial case before trusting a pass.

## Workstreams

A workstream is one change folder with one owner at a time.

- Every substantive task has exactly one `changes/` folder; scope expansion is recorded
  there.
- Its row in [changes/ACTIVE.md](../../changes/ACTIVE.md) names the branch or worktree and
  the next action. Update the row when either changes, so parallel streams can see each
  other without reading each other's history.
- Streams that touch the same files are sequenced by the integrator, not raced.
- Record branch, commit, and PR references in the handoff. Leave unrelated local changes
  alone and state the baseline you started from.

## Validating inside a worktree

The virtual environment is an editable install bound to the checkout that created it, so
tools run from another checkout's environment can import and validate the wrong tree.
Give each worktree its own environment: run `make install` (equivalent to
`uv sync --extra dev --extra anthropic --all-packages`) inside the worktree, then run the gate there. A bare
`uv sync` drops the dev tools.

When an exact lint count matters, run Ruff with `--no-cache`. Golden files change only
through their explicit regeneration path, with each changed hunk attributed.
