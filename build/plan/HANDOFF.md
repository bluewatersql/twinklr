# Build-campaign handoff — current execution state

_Last updated: 2026-08-14 ~03:50 AST (session date 2026-08-13→14). Maintained by the
orchestrating agent; update this file at every pause or phase boundary._

## What this campaign is

Multi-agent execution of the accepted reactivation proposal
(`changes/twinklr-reactivation-review/reviews/reactivation-proposal.md`, v3 — decisions
D1–D13). Plan: `build/plan/00-overview.md` (dependency graph, agent model, 56 tasks
across 7 phase files). Specs: `build/specs/<phase>/<task>.md` — several specs carry
appended **routed notes / backlog additions / completion handoffs**; specs are living
documents and always read FULLY, including appendices.

## Execution status by phase

| Phase | Status | Evidence |
|---|---|---|
| 0 — Foundation honesty | **COMPLETE** (7/7) | COMPLETION RECORD in `01-phase-0-foundation.md`; commits f0ae952…eeeb4c6 |
| 1K — Knowledge edges | **COMPLETE** (5/5) | COMPLETION RECORD in `03-phase-1k-knowledge-edges.md`; commits 3fb3ee8…64c048a |
| 1P — Render truth | **11/12 merged; T12 in final verification** | see below |
| 2P / 2K / 3 / 4 | Not started | specs exist for all tasks |

### Phase 1P task ledger (merge commits)

- T1 golden harness / T2 rig configs / T3 intensity+movement (CRITICAL, 582ff54) /
  T4 one time grid (CRITICAL, bd07df5) / T7 metadata+lyrics / T9 cache identity —
  merged earlier this session.
- **T5** scheduler+preset+calibration truth — **d193be0** (118 files; flipped reserved
  pins blackout/floor/8-head/transition-blend; 2 extra defects found in flight:
  FADE_OUT inversion, hash-seed-dependent transition DMX).
- **T6** channel-default policy — **83a0d89** (declared defaults emitted; floor-16 rule
  gone; ChannelDefaults DELETED with pinned rationale; **golden README known-wrong
  section now EMPTY** — all 78 goldens pin correct behavior).
- **T8** audio DSP correctness — **34697eb** (8 fixes; validator WIRED; first
  ground-truth audio assertions; AUDIO_FEATURES_CACHE_VERSION bumped — one-time
  cache recompute; measured MIR baselines routed to P2P-T8 spec).
- **T10** evaluation writer + bridge — **881348c** (checkpoint writer at MH stage seam;
  `twinklr eval-report` bridged; first committed evaluation in
  `evaluations/2026-08-13-golden-fixture-mh4-minimal/`).
- **T11 ⚖** delivery v1 — **5c74992** (OWNER APPROVED 2026-08-14): fresh .xsq +
  per-track .xtiming + .xmap; `--xsq` template-merge RETIRED (rejected loudly);
  CLI takes fixture config (hardcoded 4-head rig gone). Owner also answered the open
  contract question: **bare .xsq imports; rgbeffects.xml NOT required** (recorded in
  T12 spec, 6fd4bd2).
- **T12** xLights acceptance (LOCAL-ONLY) — **IN FLIGHT, uncommitted**. Suite built
  (`tests/golden/test_xlights_acceptance.py`, `xlights_client.py`, conftest marker
  `requires_xlights`); xLights NOT installed on this machine → all 7 tests SKIP with
  explicit relaunch instructions. First verifier pass REJECTED on 3 discrimination
  gaps (identical Q1 arms; no-op xtiming assertion; runbook gap); executor fixed all
  three (env-var-gated arms via `TWINKLR_XLIGHTS_SHOWDIR_MODE`; independent
  marker-math assertion verified byte-for-byte; autouse `new_sequence()` fixture).
  **Awaiting verify-1p-t12's final verdict.** On APPROVE: pathspec-commit
  (tests/golden/* + README), then write the Phase 1P COMPLETION RECORD in
  `02-phase-1p-render-truth.md` (same shape as Phase 0/1K records).

### Current tree / gates (at last measurement)

- HEAD: 2e77f9d (+ uncommitted T12 suite files). ~35 commits on main this session;
  **nothing pushed to any remote** (owner has not requested push).
- Full suite: **4823 passed / 25 skipped / 0 failed** (7 of the skips are the new
  xLights acceptance tests). Goldens 72 passed / 7 skipped. ruff format --check +
  ruff check `--no-cache` clean; mypy clean (679 files).

## Owner actions pending (do not let these die)

1. **`evaluations/2026-08-13-golden-fixture-mh4-minimal/judgment.md` is
   PENDING-OWNER** — the spec's "recorded human judgment" is deliberately not
   fabricated; owner writes it.
2. **Empirical xLights pass** — xLights 2026.15 is not installed on this machine.
   When the owner runs it (see runbook in `tests/golden/README.md`, both
   `TWINKLR_XLIGHTS_SHOWDIR_MODE` arms), the suite's Q1–Q4 get real answers; update
   the README run record.
3. Push to remote — only on owner request.

## Orchestration model (how to continue this work)

One orchestrator (team lead) + per-task **executor/verifier pairs** (named
`exec-<task>` / `verify-<task>`; models per the phase plan tables — verifiers for
CRITICAL/⚖ tasks are opus). Verify → REJECT/remedy cycles until APPROVE → orchestrator
commits → shut the pair down (owner directive: clean up resources as tasks complete).
⚖ tasks (owner-facing contract changes) get verified, then the commit is HELD for the
owner's direct review.

### Binding process rules (learned the hard way; do not relearn)

- **Workers never run git state commands** — no `git add`/`rm`/commit/stash. The
  orchestrator commits via **pathspec form** (`git add -A -- <paths> && git commit --
  <paths>`) after checking lane separation (pre-staged deletions were twice swept
  into the wrong commit before this rule).
- **Worktree verification requires an own synced venv** (`uv sync` in the worktree,
  then `python -m pytest`) — the shared venv resolves twinklr packages from the main
  checkout's editable install and silently falsifies pre-fix probes.
- **ruff counts only trusted with `--no-cache`** (stale .ruff_cache deflated counts
  3–10×).
- **Acceptance metrics must DISCRIMINATE**: before trusting any metric, prove it
  FAILS on pre-fix code (disposable worktree at the baseline SHA). Executors state
  the discriminating test per fix; verifiers spot-check several themselves.
- **Golden discipline**: `--regen-goldens` is the only write path; every changed hunk
  must be attributed to a named fix; unattributable hunks stop the task. Reserved
  known-wrong pins are flipped only by their owning task. `tests/golden/README.md`
  is the pin registry and MUST be updated when pins change (T5 was rejected for
  missing this).
- **Routed notes**: discoveries outside a task's mechanism are appended to the OWNING
  task's spec (see appends in P1P-T5/T6/T11, P2P-T2, P2P-T8 specs for the shape) —
  never silently dropped. Completion handoffs may be appended to the task's own spec
  (P1P-T8 precedent).
- **Spec citations drift** — the tree moves fast; executors re-verify line citations
  against the current HEAD before editing.
- Format-check the exact file set before committing (one unformatted file nearly
  reached CI twice).
- Transient API stalls mid-stream happen; the resume protocol is: verify actual tree
  state (`git status`), continue from the verified point, work in smaller turns.

## What's next (after T12 closes Phase 1P)

Per `00-overview.md`: **Phase 2P (creative quality) ∥ Phase 2K (catalog growth)** —
disjoint file scopes, same pairing model. Notable pre-routed context waiting in those
specs: P2P-T2 carries three routed notes (SLOW-period constant-render;
single-head-rig raw ValidationError — discharges the remainder of T5's note; plus its
own scope); P2P-T8 carries the measured MIR baselines (tempo-grid quantization,
+1-frame beat bias — baseline-specific, re-measure after any detector swap; t=0 click
undetected); P2K-T2 carries a PromotionPipeline threshold discrepancy; P4-T4 carries
the _merge_headers case-append bug. Phase-boundary bookkeeping when 1P completes:
COMPLETION RECORD in the phase plan, this file updated, `changes/ACTIVE.md` reviewed,
durable-lesson promotion per AGENTS.md if any lesson transcends the build campaign.
