# Changes — Change Management

Home of active and historical change work: specifications, implementation plans, design
docs, reviews, test plans, handoffs, and implementation notes.

## Conventions

- One directory per change: `changes/<short-kebab-slug>/`.
- Typical contents: `spec.md` (what & why — start from
  [templates/change.md](../templates/change.md)), `plan.md` (implementation plan),
  `reviews/`, `handoff.md` (latest state for the next session/agent — start from
  [templates/handoff.md](../templates/handoff.md)), plus working notes. Use only the
  documents the change actually needs.
- [ACTIVE.md](ACTIVE.md) lists currently active changes and is the only file agents must
  check to find in-flight work. Keep it current.
- Historical changes stay here untouched as history — do not rewrite them for style.

## Lifecycle

```
propose (spec) → plan → implement (notes, reviews, handoffs) → close
```

On close:

1. Promote accepted architecture/behavior into `context/` — a closed change must never be
   the only home of current project truth.
2. Promote durable lessons into `memories/` (see
   [prompts/handoff/session-closeout.md](../prompts/handoff/session-closeout.md)).
3. Mark the change closed in [ACTIVE.md](ACTIVE.md); leave its artifacts in place.

## History note

Before 2026-08-13 this directory was gitignored and kept locally only. Earlier change
archives (e.g. `changes/archive/group_planner_v3_failed/`, still referenced from a comment
in `packages/twinklr/core/pipeline/stages.py`) were never committed and are not present in
the repository. From now on, `changes/` is Git-tracked shared knowledge.
