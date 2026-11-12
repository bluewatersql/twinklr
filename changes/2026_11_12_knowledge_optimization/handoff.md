---
type: handoff
status: active
area: governance
change: 2026_11_12_knowledge_optimization
updated: 2026-11-12
---

# Handoff — Knowledge Optimization

Status: written and reviewed; uncommitted, awaiting owner review
Branch / worktree: `chore/knowledge-optimization` (from `main` `790b52b`)
Commit: none yet
PR: none
Implementing agent / model: Claude Code orchestrating session
Reviewing agent / model: independent critic subagent (read-only)

## Summary

The agent router, context, memories index, prompts, and change templates were restructured
for parallel agents and workstreams and aligned to the OnDeck layout. Documentation only.
Scope, non-goals, and two decisions for the owner to confirm are in [brief.md](brief.md).

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|---|---|---|
| `AGENTS.md` routes and states each rule once | Met | Review found one duplicated rule (worker Git rule); unified in `AGENTS.md` |
| `current-state.md` and `ACTIVE.md` agree with the campaign handoff | Met after review fixes | Review confirmed counts, boundaries, and run metrics; three accuracy findings fixed |
| Relative links resolve | Met | Ad-hoc link and anchor check: no broken link in changed files; 7 pre-existing broken links in historical files are unchanged |
| Independent review, findings addressed | Met with exceptions below | Verdict was "changes requested"; all major and minor findings 1–7 and 9–11 fixed |
| `make validate` passes | Not run | It refuses a dirty tree; see Validation |

## Files Changed

- Rewritten: `AGENTS.md`, `CLAUDE.md`, `context/INDEX.md`, `context/current-state.md`,
  `changes/INDEX.md`, `changes/ACTIVE.md`, `memories/INDEX.md`, `prompts/INDEX.md`,
  `prompts/handoff/session-closeout.md`.
- Edited: `HOME.md`, `context/engineering/conventions.md`,
  `context/architecture/multi-agent-planning.md` (Ollama status),
  `evaluations/README.md` and campaign runbook 03 (labels and one link), campaign
  `HANDOFF.md` (one dated note under "Start here").
- Created: `context/agents/` (5 pages), `changes/shared/agent_guardrails.md`,
  `changes/_templates/` (brief, implementation-plan, review, handoff),
  `memories/inbox/README.md`, `prompts/planning/`, `prompts/review/`, `prompts/research/`,
  `prompts/handoff/complete-a-handoff.md`.
- Moved: `templates/change.md` → `changes/_templates/brief.md`, `templates/handoff.md` →
  `changes/_templates/handoff.md`, `prompts/implementation/implement-and-validate.md` →
  `implement-a-change.md`.

## Decisions, Assumptions, Deviations From Plan

- A test pins the phrase `planner/heuristics/judge` in `context/INDEX.md`
  (`tests/unit/config/test_documented_config.py`); the routing table keeps it.
- Existing change folders, memory file names (including `python-3.12-only.md`), and
  decision file names were left alone because historical documents link to them.

## Validation

| Command | Exact result |
|---|---|
| `uv run --frozen ruff format --check .` | 1367 files already formatted |
| `uv run --frozen ruff check . --no-cache` | All checks passed |
| `uv run --frozen mypy .` | Success: no issues found in 723 source files |
| `uv run --frozen pytest tests/ -q --no-cov` | 1 failed, 5717 passed, 39 skipped (the failure was the pinned phrase above) |
| `uv run --frozen pytest tests/unit/config/test_documented_config.py -q --no-cov` (after the fix) | 6 passed |

Failed or skipped validation: `make validate` was not run because it requires a clean
tree and nothing is committed. The full test suite was not rerun after the review fixes,
which touched Markdown only.

## Open Items

- Owner to confirm the two decisions in the brief (ladder order; OnDeck guardrails 6 and
  10 not carried over).
- Review finding not fixed: runbook 03 names a future folder
  `changes/mh-idiom-mining-feasibility/`, which predates the dated naming convention.
- Review questions for the owner: whether the post-refactor MH run is confirmed as the
  "meaningful end-to-end show" that unblocks runbook 04; whether the P2P-T7 Demucs smoke
  is accepted as closing that exit.
- OnDeck has `make agent-check` and `make docs-link-check`; Twinklr has neither. The link
  check here was a throwaway script.

## Next Action

1. Owner reviews the diff.
2. Commit on `chore/knowledge-optimization`, run `make validate`, record the result here.
3. Merge to `main`, then move this change's row in `changes/ACTIVE.md` to "Recently closed".

## Knowledge Promotion

None needed beyond the change itself: the governance pages are the promoted result.
