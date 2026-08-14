# Twinklr — Agent Instructions

Twinklr is an AI-powered choreography engine that turns an audio file into a synchronized
[xLights](https://xlights.org) light-show sequence (`.xsq`). The core principle: **LLMs plan
creative intent; deterministic code handles precision.** Python 3.12, uv workspace,
Pydantic V2, OpenAI Responses API.

This file is the canonical bootstrap for **all** coding agents (Claude Code, Codex/ChatGPT,
Cursor, future tools) and is a **router, not an encyclopedia**. Durable knowledge lives in
the directories it points to. Humans navigate the same knowledge via [HOME.md](HOME.md)
(Obsidian entry point).

## Context-loading protocol

Before substantial work:

1. Read this file.
2. Read [context/INDEX.md](context/INDEX.md), then [context/current-state.md](context/current-state.md).
3. Decide which domains your task touches and read **only** the relevant context documents.
   Do not bulk-load every context file.
4. Read [changes/ACTIVE.md](changes/ACTIVE.md). If your work belongs to an active change,
   read its specification, current plan, and latest handoff.
5. Search [memories/](memories/INDEX.md) for related decisions, learnings, constraints,
   and patterns.
6. Check [prompts/INDEX.md](prompts/INDEX.md) for an existing workflow before inventing one.
7. Inspect the source code relevant to the task; expand context only as needed.

## Knowledge placement

| Kind of information | Canonical home |
|---|---|
| Fact / current project truth | `context/` |
| Active or proposed change (specs, plans, reviews, handoffs) | `changes/` |
| Durable learning, decision, constraint, or pattern | `memories/` |
| Reusable agent procedure / workflow | `prompts/` |
| Human-facing product & developer documentation (published site) | `docs/` |
| Dated evaluation results (`eval-report` output + human judgment) | `evaluations/` |

One source owns each fact. `context/` summarizes and links into `docs/` rather than
duplicating it; `docs/` remains the deep human-facing reference and GitHub Pages site.

## Source-of-truth hierarchy

When sources conflict, prefer (highest first):

1. The accepted specification of a currently **active** change (`changes/`)
2. Current context documentation (`context/`)
3. Accepted decision records and durable memories (`memories/`)
4. Repository implementation and tests, where they establish current reality
5. `README.md` and `docs/`
6. Historical change documents
7. Agent-native memory (Claude auto-memory, ChatGPT memory, `.omc/`, `.remember/`)

Never silently pick between conflicting authoritative sources — resolve the conflict from
repository evidence and update the canonical source.

## Memory protocol

Agent-native memory is a machine-local supplemental cache, **never** project authority.
Shared project memory is the Git-tracked `memories/` tree.

Do not promote speculation, temporary debugging state, unverified assumptions, or
ephemeral task details into `memories/`. When you make a durable discovery:

1. Search `memories/` (and `context/`) for existing coverage.
2. Update the existing file rather than creating a duplicate.
3. Record provenance and date in frontmatter.
4. Link related context/change documents.
5. Update [memories/INDEX.md](memories/INDEX.md).

Uncertain-but-valuable findings go to `memories/inbox/` pending review. Use
[prompts/handoff/session-closeout.md](prompts/handoff/session-closeout.md) at the end of
substantial work.

## Change-management protocol

- Active work lives in `changes/<slug>/` (spec, plan, reviews, handoffs, notes).
  Conventions: [changes/INDEX.md](changes/INDEX.md). Active list: [changes/ACTIVE.md](changes/ACTIVE.md).
- Continue prior work from the change's latest handoff, not from memory.
- When a change completes: promote accepted architecture/behavior into `context/`,
  promote durable lessons into `memories/`, mark the change closed in `ACTIVE.md`, and
  leave its artifacts in place as history. A closed change must never be the only home of
  current project truth.
- Historical change documents are history — do not rewrite them for style.

## Development quality gates

All work must pass before completion claims:

```bash
make validate   # format + lint-fix + type-check + test
```

Gate specifics, toolchain, local config files, and documentation frontmatter conventions:
[context/engineering/conventions.md](context/engineering/conventions.md). Known
pre-existing failures:
[memories/learnings/known-test-failures.md](memories/learnings/known-test-failures.md).
New knowledge documents start from the blank starters in `templates/`.

## Definition of done

Substantial work is complete only when **all** of these hold (proportional to the work —
no documentation churn when no durable knowledge changed):

- implementation done and `make validate` passes with fresh output as evidence
- the change's artifacts in `changes/<slug>/` reflect reality (status, handoff if pausing)
- durable truth changes promoted to `context/`; durable lessons to `memories/`
- stale documentation touched by the work corrected or removed
- indexes updated ([changes/ACTIVE.md](changes/ACTIVE.md), affected `INDEX.md` files)

## Repository hygiene

Respect `.gitignore`. Never commit: IDE/Obsidian workspace state, caches, logs, generated
artifacts (`data/`, `artifacts/`), local configs (`config.json`, `job_config.json`,
`fixture_config.json`), credentials (`.env`), agent session state (`.claude/`, `.cursor/`,
`.omc/`, `.remember/`), or OS metadata. Generated/local files are never project context
merely because they exist in the working directory.

Note: `packages/twinklr/core/**/prompts/` are **runtime LLM prompt packs** (application
source code), not agent workflow prompts — they do not belong in the root `prompts/` tree.

## Documentation hygiene

Do not duplicate durable information across `AGENTS.md`, `CLAUDE.md`, `README.md`,
`context/`, `changes/`, `memories/`, `prompts/`, or `docs/`. Move content to its canonical
owner and link to it. Tool-specific files (`CLAUDE.md`) contain only tool-specific behavior.
