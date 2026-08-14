# Twinklr Implementation Program — Plan Overview

_2026-08-13. Executes
[reactivation-proposal.md (v3)](../../reviews/reactivation-proposal.md).
Every task traces to verified findings (`reviews/phases/*.md`, `verification.md`,
finding IDs like P4-F1/CF-2) or proposal decision points (D1–D13). This folder is the
**plan** (what, in what order, run by which agents); `changes/twinklr-reactivation-review/build/specs/` holds the
**per-task specifications** (how, exactly)._

> **Continuing this work? Start at [HANDOFF.md](HANDOFF.md)** — live execution state,
> per-phase status, binding process rules, and pending owner actions.

## Program map

```
Phase 0  Foundation honesty          (gates green from clean checkout)      — serial-ish, small
   │
   ├────────────► Phase 1P  Render truth (Track P / M1)   ─────────┐
   │                                                                │
   └────────────► Phase 1K  Knowledge edges (Track K / M1-K)  ──────┤   1P ∥ 1K fully parallel
                                                                    ▼
                  Phase 2P  Creative quality, measured (M2)  ───────┐
                  Phase 2K  Catalog growth (M2-K)            ───────┤   2P ∥ 2K mostly parallel
                                                                    ▼
                  Phase 3   Show convergence (M3: display + assets + coordination)
                                                                    ▼
                  Phase 4   Compounding (M4: ML/Py bump, local provider, debt, docs)
```

| Phase | Plan doc | Tasks | Exit criterion (summary) |
|---|---|---|---|
| 0 | [01-phase-0-foundation.md](01-phase-0-foundation.md) | P0-T1..T7 | CI green from a clean clone; packaging produces real wheels |
| 1P | [02-phase-1p-render-truth.md](02-phase-1p-render-truth.md) | P1P-T1..T12 | Correct, importable MH show; first recorded evaluation |
| 1K | [03-phase-1k-knowledge-edges.md](03-phase-1k-knowledge-edges.md) | P1K-T1..T5 | Idempotent corpus; label loop live; seed catalog in git |
| 2P | [04-phase-2p-creative-quality.md](04-phase-2p-creative-quality.md) | P2P-T1..T13 | Widened channel live; vision-eval harness scoring every run; 3-arm verdict |
| 2K | [05-phase-2k-catalog-growth.md](05-phase-2k-catalog-growth.md) | P2K-T1..T4 | Catalog coverage: every element type × role × energy range |
| 3 | [06-phase-3-show-convergence.md](06-phase-3-show-convergence.md) | P3-T1..T8 | One command → coordinated MH+display show for the user's layout |
| 4 | [07-phase-4-compounding.md](07-phase-4-compounding.md) | P4-T1..T7 | Modern chain; debt retired; docs describe reality |

## Multi-agent execution model

**Roles per task** (no exceptions):
- **Executor** — implements exactly one task in an isolated git worktree
  (`isolation: worktree`), on the model tier the task table names (sonnet =
  mechanical/bounded; opus = design-bearing or cross-cutting). TDD where the spec
  defines behavior: failing test first.
- **Verifier** — a different agent (never the executor) reviews the diff against the
  spec's acceptance criteria + runs the spec's verification commands. Opus for
  CRITICAL/HIGH-finding tasks, sonnet otherwise.
- **Orchestrator** — merges lanes, resolves disputes, owns gate reviews at phase
  exits.

**Lanes** — tasks in the same lane share files and run serially; different lanes run
in parallel worktrees. Each phase doc defines its lanes and the merge order. Rules:
- A lane's tasks land as one PR-style merge per task (small, reviewable diffs).
- Cross-lane file conflicts are called out in the task tables; when unavoidable, the
  later lane rebases.
- `make validate` equivalents (check-only forms until P0-T4 lands the guard) must
  pass at every merge; golden tests (once P1P-T1 exists) must pass for any lane
  touching render/export code.

**Sequencing constraints inherited from the review** (violating these re-breaks
verified behavior — spec authors must copy the relevant ones into each spec):
- P4-F1 intensity fix + F1a data fill-in + P4-M6 frequency-amplitude land **together** (P1P-T3).
- Metadata client fix + MusicBrainz rate limiter land **together** (P1P-T7).
- Deterministic session-ID + cache-root anchoring + prompt-content hashing land **together** (P1P-T9).
- FSCache tests migrate **before** the sync-adapter deletion (Phase 4 debt task).
- CF-2 grid fix spans agents-context (`_ms_to_bar`) and sequencer — one task, both halves (P1P-T4).
- Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts are not replayable) (P1P-T10).
- Model retarget must set `reasoning.effort` explicitly and include the out-of-framework
  call site `normalization/llm_review.py` (P2P-T10).

**Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
must re-verify cited line numbers before editing (the tree will drift as phases land)
— specs cite symbol + file, with line numbers as hints only.

## Conventions

- Task IDs: `P<phase>-T<n>` (e.g., `P1P-T3`). Specs live at
  `changes/twinklr-reactivation-review/build/specs/phase-<slug>/P*-T*-<kebab-title>.md`, one file per task.
- Every spec follows the template in [`changes/twinklr-reactivation-review/build/specs/README.md`](../specs/README.md).
- Findings referenced by ID resolve in
  `changes/twinklr-reactivation-review/reviews/findings.md` (consolidated) and
  `reviews/phases/*.md` (detail).
- Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
  each spec's stated test budget; live-LLM and xLights-GUI tests are marked
  `LOCAL-ONLY` in specs and excluded from CI.
- Status tracking during execution: check-boxes in phase docs are updated by the
  orchestrator at merge time (single-writer rule; executors never edit plan docs).
