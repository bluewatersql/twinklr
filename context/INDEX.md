# Twinklr Context Index

`context/` is current truth: what Twinklr is and how it works today. Active work lives in
`changes/`, learned knowledge in `memories/`, reusable procedures in `prompts/`. Each page
is a concise summary that links into `docs/` and source for depth.

Start with [current-state.md](current-state.md) and [../changes/ACTIVE.md](../changes/ACTIVE.md).

## Topic routing

Load only what the task needs.

| Topic | Read | When |
|---|---|---|
| Repository authority, agent workflow | [../AGENTS.md](../AGENTS.md), [agents/authority-model.md](agents/authority-model.md), [agents/context-loading.md](agents/context-loading.md) | Agent rules, adapters, knowledge structure |
| Parallel agents and workstreams | [agents/operating-model.md](agents/operating-model.md) | Delegating, worktrees, integrating, reviewing |
| Agent memory | [agents/memory-policy.md](agents/memory-policy.md) | Deciding what a local memory is worth; promoting knowledge |
| Evidence discipline | [agents/guardrails.md](agents/guardrails.md) | Investigating a failure and proving a fix |
| Product | [product/overview.md](product/overview.md) | Goals, scope, what the product is for |
| Pipeline and subsystems | [architecture/pipeline.md](architecture/pipeline.md) | Stage order, failure policy, caching, where a subsystem lives |
| Planning agents | [architecture/multi-agent-planning.md](architecture/multi-agent-planning.md) | The planner/heuristics/judge loop, categorical planning, schema injection, providers |
| Engineering conventions | [engineering/conventions.md](engineering/conventions.md) | Toolchain, commands, quality gates, local config files |
| Terminology | [glossary.md](glossary.md) | xLights, DMX, templates, BeatGrid, recipes, FE |
| Live and owner-gated runs | [../changes/twinklr-reactivation-review/runbooks/README.md](../changes/twinklr-reactivation-review/runbooks/README.md), [../docs/qa-runbook.md](../docs/qa-runbook.md) | Before any paid, live, xLights, or owner-data step |
| Evaluation records | [../evaluations/INDEX.md](../evaluations/INDEX.md) | What a run produced at a given commit; pending human judgments |
| Decisions and lessons | [../memories/INDEX.md](../memories/INDEX.md) | Why things are the way they are; before working in a covered area |
| Audio analysis depth | [../docs/audio_profile/index.md](../docs/audio_profile/index.md), [../docs/pipeline_guide.md](../docs/pipeline_guide.md) | Audio features, profiling, pipeline internals |
| Feature engineering depth | [../docs/feature_engineering/index.md](../docs/feature_engineering/index.md) | Corpus mining, feature store, recipes |
| Using and developing | [../docs/user-guide.md](../docs/user-guide.md), [../docs/developer-guide.md](../docs/developer-guide.md) | Installation, configuration, CLI, development setup |

When sources disagree, follow the authority order in
[../AGENTS.md](../AGENTS.md#source-of-truth) and correct the stale page.

## Promotion rules

Task discoveries stay in `changes/<change>/` until reviewed and useful beyond that task.
Then: current truth → the owning `context/` page (and `current-state.md` if operationally
significant); decision → `../memories/decisions/`; validated lesson →
`../memories/learnings/`; durable limitation → `../memories/constraints/`; validated
technique → `../memories/patterns/`; agent procedure → `../prompts/`; agent rule →
`../AGENTS.md` or `agents/`; tool-specific mechanic → that tool's adapter. Workflow:
[../prompts/handoff/session-closeout.md](../prompts/handoff/session-closeout.md).

## Metadata convention

Knowledge documents carry a small YAML frontmatter (Obsidian-compatible, plain Markdown
otherwise):

- `type` — `context` · `change` · `plan` · `review` · `handoff` · `decision` ·
  `learning` · `constraint` · `pattern`
- `status` — `proposed` · `active` · `accepted` · `blocked` · `complete` · `historical` ·
  `closed`
- `area` (context and change documents) — `overview` · `product` · `architecture` ·
  `engineering` · `governance` · `reference`
- `created` / `updated` — `updated` is the last substantive knowledge review; do not bump
  it for formatting-only edits
- `confidence` (memories only) — `confirmed` (verified against `main` with citations) ·
  `reported` (plausible, unverified) · `refuted-on-main`
- Optional: `change`, `owner`, `tags` (only for cross-cutting labels that no folder,
  property, or link expresses)

Index and navigation files (`INDEX.md`, `ACTIVE.md`, `HOME.md`, `README.md`) carry no
frontmatter. New change documents get theirs from
[../changes/_templates/](../changes/_templates/); memory and context documents start from
[../templates/](../templates/). Historical documents are not retrofitted.
