---
type: plan
status: active
area: governance
change: 2026_11_12_knowledge_optimization
owner: Christopher Price
created: 2026-11-12
updated: 2026-11-12
---

# Knowledge Optimization

Branch/worktree: `chore/knowledge-optimization`

## Goal

Make the agent-facing knowledge (`AGENTS.md`, `CLAUDE.md`, `context/`, `memories/`,
`prompts/`, `changes/` indexes and templates) work well for several agents and several
workstreams at once, and align its structure with the OnDeck repository's practices.

## Background

The owner asked for three things: optimize for multi-agent, multi-workstream use; optimize
for the current Claude model; align to the OnDeck structure and practices
(`~/work/github/ondeck`: `AGENTS.md`, `context/agents/`, `changes/_templates/`,
`changes/shared/agent_guardrails.md`, `prompts/`).

Problems found in the previous state:

- `context/current-state.md` (256 lines) and `changes/ACTIVE.md` (108 lines) each carried
  one unbroken chronological narrative of the build campaign. Every agent paid for it at
  session start, the two copies had drifted, and several statements were stale after the
  2026-11-12 owner decisions (P3-T4 "remains open", Ollama smoke "unclaimed").
- Nothing described how parallel agents coordinate: ownership, worktrees, integration,
  or how to brief a subagent. The only rules were at the end of a 789-line handoff.
- `AGENTS.md` and a prompt pointed at `known-test-failures.md` as "known pre-existing
  failures", but that file is a historical baseline and `main` is green.
- `memories/inbox/` was referenced but did not exist in Git.

## Scope

- Rewrite `AGENTS.md` as a router with the OnDeck section model; reduce `CLAUDE.md` to
  Claude-specific mechanics.
- Add `context/agents/` (authority, context loading, memory policy, operating model,
  evidence discipline) and `changes/shared/agent_guardrails.md`.
- Rewrite `context/current-state.md` as a snapshot and `changes/ACTIVE.md` as a
  one-row-per-workstream table. History stays in the campaign handoff.
- Add topic routing, promotion rules, and the metadata convention to `context/INDEX.md`.
- Add `changes/_templates/` (brief, implementation plan, review, handoff) and the missing
  workflow prompts (start a change, subagent brief, review, handoff, recovery).
- Restructure `memories/INDEX.md`; add `memories/inbox/README.md`.

## Non-Goals

- No source code, test, Makefile, or CI change.
- No rewrite of historical change documents, including the campaign `HANDOFF.md`.
- No renaming of existing change folders or memory files (inbound links from history).
- No new facts: every status statement is carried from an existing tracked record.

## Decisions for the owner to confirm

- The source-of-truth ladder now ranks implemented code above `context/` (previously
  `context/` ranked above code), matching OnDeck.
- OnDeck guardrails 6 (no feature flags, version bumps, or compatibility mechanisms
  without owner approval) and 10 (unreleased product, no consumers) were not carried
  over: they are owner rulings about OnDeck and nothing in this repository states them
  for Twinklr.

## Acceptance Criteria

- [x] `AGENTS.md` routes to every tree and states authority, loading, parallel work,
      owner-gated actions, validation, and done criteria once each.
- [x] `current-state.md` and `ACTIVE.md` agree with the campaign handoff's 2026-11-12
      state and contain no chronological narrative.
- [x] Every relative Markdown link in the changed files resolves.
- [x] Independent review of the diff, findings addressed (one exception, in the handoff).
- [x] `make validate` passes (5718 passed, 39 skipped at `6f2a9f6`).

## Constraints

Documentation only. No owner-gated action is needed.

## Relevant Context

- OnDeck reference: `~/work/github/ondeck/AGENTS.md`, `context/agents/`,
  `changes/INDEX.md`, `changes/_templates/`, `prompts/`.
- Campaign state: `changes/twinklr-reactivation-review/build/plan/HANDOFF.md`.

## Validation Plan

| Command | Purpose |
|---|---|
| Relative-link check over tracked Markdown outside historical change folders | No broken links from moves and renames |
| `make validate` | Repository gate |

## Implementing Agent / Model

Claude Code (orchestrating session).

## Reviewing Agent / Model

Independent reviewer subagent; see `handoff.md`.
