# Prompts — Reusable Agent Workflows

`prompts/` holds the procedures agents follow to perform work in this repository: the
**how**, kept separate from what is true (`context/`), what is changing (`changes/`), and
what we learned (`memories/`).

Check this index before inventing a substantial workflow. Prompts reference authoritative
context instead of restating it; when a prompt disagrees with `AGENTS.md` or `context/`,
the canonical source wins and the prompt is fixed.

## Workflows

| Prompt | Use when |
|---|---|
| [planning/start-a-change.md](planning/start-a-change.md) | Beginning any substantive task; creates or locates the `changes/` record |
| [planning/subagent-task-brief.md](planning/subagent-task-brief.md) | Delegating a task to a subagent, especially several in parallel |
| [implementation/implement-a-change.md](implementation/implement-a-change.md) | Executing against an active change |
| [review/review-a-change.md](review/review-a-change.md) | Independent review of a diff against its acceptance criteria |
| [handoff/complete-a-handoff.md](handoff/complete-a-handoff.md) | Ending a work session on an active change |
| [handoff/session-closeout.md](handoff/session-closeout.md) | Closing a change or significant session: promote knowledge, update indexes |
| [research/recover-failed-agent-run.md](research/recover-failed-agent-run.md) | Resuming after another agent's run failed or was interrupted |

## Conventions

- One prompt per file, with a stable descriptive name. No `-v2` or `-final` variants;
  extend the existing prompt.
- Templates for change documents live in [../changes/_templates/](../changes/_templates/);
  prompts link to them rather than embedding copies.
- New prompt files are added to this index.

These are **agent workflow prompts**. The product's runtime LLM prompt packs live in
`packages/twinklr/core/**/prompts/` and are application source code.
