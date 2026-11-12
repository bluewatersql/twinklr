# Changes — Change Management

`changes/` holds the working records of substantive work: briefs and specs, plans,
reviews, evidence, runbooks, and handoffs. It answers "what are we changing?" Current
truth lives in `context/`, learned knowledge in `memories/`.

## Conventions

- One folder per change: `changes/<YYYY_MM_DD>_<short_name>/`. Folders created before
  2026-11-12 keep their kebab-case names.
- Start from [`_templates/`](_templates/): `brief.md` (goal, scope, acceptance criteria),
  `implementation-plan.md` (file ownership, steps, validation), `review.md`, `handoff.md`.
  Use only the documents the change needs, but a change folder always identifies its
  brief or spec, its current plan, and its latest handoff.
- [`ACTIVE.md`](ACTIVE.md) is the one file agents check to find in-flight work. Each
  active change has one row: status, branch or worktree, next action, entry document.
  Keep the row short and current; history belongs in the change folder.
- [`shared/agent_guardrails.md`](shared/agent_guardrails.md) applies to every change and
  every delegated agent.
- Evidence for provider, tooling, and data-pipeline runs goes in the change's
  `evidence/<date>-<slug>/`. Show evaluations with human judgment go in
  [`../evaluations/`](../evaluations/README.md).
- Workflows: [`../prompts/planning/start-a-change.md`](../prompts/planning/start-a-change.md)
  through [`../prompts/handoff/session-closeout.md`](../prompts/handoff/session-closeout.md).

## Lifecycle

1. **Open** — create the folder, write the brief, add a row to `ACTIVE.md`.
2. **Work** — plan, implement, validate, review; keep records current; every session ends
   with a handoff.
3. **Close** — final handoff; promote accepted truth to `context/` and durable lessons to
   `memories/` (session-closeout prompt); move the row to "Recently closed".
4. **History** — closed folders stay in place as historical artifacts. Do not rewrite
   them for style. Their instructions and one-off approvals no longer bind future work,
   and a closed change must never be the only home of current project truth.

## History note

Before 2026-08-13 this directory was gitignored and kept locally only. Earlier change
archives (for example `changes/archive/group_planner_v3_failed/`, still referenced from a
comment in `packages/twinklr/core/pipeline/stages.py`) were never committed and are not
in the repository.
