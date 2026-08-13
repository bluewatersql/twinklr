# Prompts — Reusable Agent Workflows

Reusable procedures for agents working on this repository. Check here before inventing a
substantial workflow; avoid near-duplicate variants of the same procedure.

> **Not to be confused with** `packages/twinklr/core/**/prompts/` — those are Twinklr's
> *runtime* LLM prompt packs (Jinja2 application source), part of the product itself.

## Workflows

- **[implementation/implement-and-validate.md](implementation/implement-and-validate.md)**
  — standard workflow for making a code change and proving it with the quality gates.
- **[handoff/session-closeout.md](handoff/session-closeout.md)**
  — end-of-session review: promote durable knowledge to `memories/`/`context/`, write
  handoffs, update indexes. Use after any substantial work.

## Conventions

- Prompts describe *procedure*; they link to `context/` for facts rather than restating
  them.
- Organize by activity (`implementation/`, `handoff/`, and add `planning/`, `review/`,
  `testing/`, `research/`, … as real workflows accumulate). Don't create empty scaffolding.
