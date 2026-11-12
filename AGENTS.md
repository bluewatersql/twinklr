# Twinklr — Agent Instructions

Twinklr is an AI-powered choreography engine that turns an audio file into a synchronized
[xLights](https://xlights.org) light-show sequence (`.xsq`). The core principle: **LLMs plan
creative intent; deterministic code handles precision.** Python 3.13, uv workspace,
Pydantic V2, with OpenAI, Claude, and Ollama provider adapters.

This file is the canonical cross-agent router (Claude Code, Codex/ChatGPT, Cursor, future
tools). It stays small; depth lives in the trees below. Humans navigate the same knowledge
through [HOME.md](HOME.md).

## Knowledge model

| Question | Tree | Entry |
|---|---|---|
| What is currently true? | `context/` | [context/INDEX.md](context/INDEX.md), snapshot in [context/current-state.md](context/current-state.md) |
| What are we changing? | `changes/` | [changes/ACTIVE.md](changes/ACTIVE.md), conventions in [changes/INDEX.md](changes/INDEX.md) |
| What did we learn? | `memories/` | [memories/INDEX.md](memories/INDEX.md) (decisions, learnings, constraints, patterns) |
| How do we perform work? | `prompts/` | [prompts/INDEX.md](prompts/INDEX.md) |

Two supporting trees: `docs/` is the published human-facing site and deep reference
(`context/` summarizes and links into it); `evaluations/` holds dated `eval-report` runs
with human judgment. One source owns each fact. Do not restate it in adapters, READMEs, or
another tree; link to the owner.

## Source of truth

The Git repository overrides chat history, model memory, local memory, and generated
summaries. When sources conflict, prefer (highest first):

1. The accepted specification of a currently active change in `changes/`.
2. Source code, tests, runtime configuration, and generated schemas (implemented behavior).
3. Current context documentation in `context/`.
4. Accepted decisions and durable memories in `memories/`.
5. `README.md` and `docs/`.
6. Historical change documents.
7. Tool adapters (`CLAUDE.md`, `.claude/`, `.cursor/`) and agent-native memory.

Empirical outcomes (a live run, an xLights acceptance, a calibration, a human judgment)
are a separate matter: they exist only where a dated evidence or `evaluations/` record
says so, whatever any other document claims.

Never silently pick between conflicting authoritative sources: resolve the conflict from
repository evidence, then correct the stale source. How to apply the ladder:
[context/agents/authority-model.md](context/agents/authority-model.md).

## Context loading

For substantive work:

1. Read this file and [changes/shared/agent_guardrails.md](changes/shared/agent_guardrails.md).
   Every delegated agent receives that guardrail path and reads it before working.
2. Read [context/INDEX.md](context/INDEX.md), then [context/current-state.md](context/current-state.md).
3. Read [changes/ACTIVE.md](changes/ACTIVE.md). If the work belongs to an active change,
   read its brief or spec, current plan, and latest handoff. Otherwise start one with
   [prompts/planning/start-a-change.md](prompts/planning/start-a-change.md).
4. Load only the `context/` pages the task needs, using the topic routing in
   `context/INDEX.md`. Do not bulk-load the tree.
5. Search `memories/` for decisions, learnings, and constraints that touch the area.
6. Use an existing `prompts/` workflow when one fits.
7. Inspect the current implementation, tests, and configuration. Run
   `git status --short --branch` before editing.
8. Confirm branch or worktree ownership when other agents are working in parallel.

Summaries and remembered state never substitute for reading current files.

## Memory protocol

Agent-native memory (Claude auto-memory, ChatGPT memory, `.omc/`, `.remember/`, and
similar) is a machine-local cache and is advisory. `memories/` is the shared, reviewed
project memory. Do not promote speculation, temporary debugging state, unverified
assumptions, or ephemeral task detail. To promote a durable discovery, follow
[prompts/handoff/session-closeout.md](prompts/handoff/session-closeout.md): search for an
existing owner, update rather than duplicate, record provenance and date, link related
documents, update the index. Policy:
[context/agents/memory-policy.md](context/agents/memory-policy.md).

## Planning

Create or update a record in `changes/` for nontrivial, multi-file,
architecture-sensitive, pipeline, provider, schema, or documentation-closeout work. A plan
states goal, scope, non-goals, acceptance criteria, constraints, affected source areas,
the validation plan, and file ownership when work runs in parallel. A small single-file
fix may proceed directly when an active change already covers it.

## Implementation

- Make the smallest complete change that satisfies the active acceptance criteria.
- Keep the LLM/renderer boundary: LLMs choose typed, categorical intent; deterministic
  code owns timing, curves, DMX values, and file formats. Pydantic models are the single
  source of LLM-facing schemas.
- Do not silently change public contracts, schemas, CLI behavior, or output formats.
- Do not touch unrelated files or overwrite unrelated local changes.
- Add or update tests for changed behavior.
- Record assumptions and scope expansion in the active change folder.
- Before deleting tracked code, config, or docs, record the paths and rationale in the
  change plan. A "dead code" claim needs importer, config, and doc grep evidence.

Engineering detail: [context/engineering/conventions.md](context/engineering/conventions.md).
Confirmed idioms: [memories/patterns/code-patterns.md](memories/patterns/code-patterns.md).

## Owner-gated actions

These need explicit owner authorization recorded in the active change. Merged tooling and
passing offline tests never stand in for them:

- Paid or live provider requests, and anything that spends against a cost cap.
- Reading, mining, or committing owner-local data (audio, layouts, sequence corpora).
- Mutating a running xLights show; use only an expendable show folder or scratch sequence.
- Human taste judgment, calibration outcomes, and acceptance verdicts. Never fabricate
  one; leave a `PENDING-OWNER` stub.
- Rerunning a sealed one-shot proof. The standing boundaries are listed in
  [context/current-state.md](context/current-state.md#permanent-boundaries).

## Validation

Use the narrowest check that proves the change while iterating, then run the full gate
before any completion claim:

```bash
make validate     # format + lint-fix + type-check + test (the completion gate)
make lint         # ruff check
make type-check   # mypy
make test         # pytest
```

`make validate` rewrites files (format, lint-fix) and refuses to start from a dirty tree,
so commit first and run it in the tree you own. There are no accepted failures on `main`:
a red gate is a defect to fix or disclose. Do not claim a command passed unless it ran
successfully in this session; report failures, skipped checks, and environment limits.

## Review

Authoring and review are separate passes in separate contexts; an author never approves
their own work. Follow [prompts/review/review-a-change.md](prompts/review/review-a-change.md).
Findings go in the change folder or the PR.

## Parallel development

- One implementing agent owns one branch or worktree. Parallel agents use isolated
  branches or worktrees and never edit the same working tree at once.
- A plan names file ownership before parallel edits begin; each delegated task gets a
  brief from [prompts/planning/subagent-task-brief.md](prompts/planning/subagent-task-brief.md).
- One designated integrator merges and resolves competing implementations. Workers may
  read Git state; they do not commit, merge, push, or rewrite history unless their brief
  grants it.
- Each workstream keeps its own row in `changes/ACTIVE.md` and its own handoff, so a
  second stream never has to read the first one's history to start.

Operating detail, including validating inside a worktree:
[context/agents/operating-model.md](context/agents/operating-model.md).

## Handoff and closeout

Every substantive session leaves a handoff in its change folder
([prompts/handoff/complete-a-handoff.md](prompts/handoff/complete-a-handoff.md)). A new
agent must be able to continue from it without reading prior chat. Closing a change also
closes the knowledge loop
([prompts/handoff/session-closeout.md](prompts/handoff/session-closeout.md)): accepted
truth is promoted into `context/`, durable lessons into `memories/`, and the change moves
out of the active table. A closed change must never be the only home of current project
truth. Historical change documents are history; do not rewrite them for style.

## Repository hygiene

Respect `.gitignore`. Never commit IDE or Obsidian workspace state, caches, logs,
generated artifacts (`data/`, `artifacts/`), local configs (`config.json`,
`job_config.json`, `fixture_config.json`), credentials (`.env`), agent session state
(`.claude/`, `.cursor/`, `.omc/`, `.remember/`, `.opencode/`), or OS metadata. A generated
or local file is not project context merely because it exists in the working directory.

`packages/twinklr/core/**/prompts/` are runtime LLM prompt packs (application source), not
agent workflows; they do not belong in the root `prompts/` tree.

## Definition of done

Work is complete when the acceptance criteria are met, `make validate` passes with fresh
output as evidence (or failures are disclosed), the change folder reflects reality
(status, handoff), durable truth is promoted to `context/` and lessons to `memories/`,
stale documentation touched by the work is corrected, and affected indexes are updated.
Keep this proportional: no documentation churn when no durable knowledge changed.
