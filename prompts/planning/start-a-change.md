# Start a Change

Use when beginning any substantive task: nontrivial, multi-file, architecture-sensitive,
pipeline, provider, schema, or documentation-closeout work.

1. Load context per [AGENTS.md → Context loading](../../AGENTS.md#context-loading).
2. Read [changes/ACTIVE.md](../../changes/ACTIVE.md). If an active change already covers
   this work, continue it from its latest handoff instead of opening a new one.
3. Otherwise create `changes/<YYYY_MM_DD>_<short_name>/` from
   [changes/_templates/](../../changes/_templates/). Start with `brief.md`; add
   `implementation-plan.md` when the work has several steps or several agents.
4. Record goal, scope, non-goals, acceptance criteria, constraints, relevant context
   links, affected source areas, and the validation plan. Name any owner-gated action the
   work needs and the authorization that covers it.
5. Record the branch or worktree that owns the work. Parallel agents get isolated
   branches or worktrees and a file-ownership table in the plan.
6. Search [memories/INDEX.md](../../memories/INDEX.md) for decisions, learnings, and
   constraints that touch the area.
7. Add a row to `changes/ACTIVE.md`.
