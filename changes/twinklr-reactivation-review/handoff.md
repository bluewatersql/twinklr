---
type: handoff
status: completed
change: twinklr-reactivation-review
updated: 2026-08-13
---

> **UPDATE (2026-08-14): remediation is now UNDERWAY.** The owner authorized executing
> the reactivation proposal; the implementation lives in this change's
> [`build/`](build/plan/00-overview.md) subtree (plan + specs). Phases 0, 1K, and 1P
> are complete; the live implementation handoff is
> **[build/plan/HANDOFF.md](build/plan/HANDOFF.md)** — that file, not this one, is the
> pickup point for continuing the build campaign. This document remains the REVIEW
> handoff (historical).

> **FINAL (2026-08-13): the review is COMPLETE — all 8 stages.** Stage 5 synthesis
> (`reviews/cross-cutting.md`, `reviews/findings.md`) and Stage 8
> (`reviews/remediation-roadmap.md`, `reviews/final-assessment.md`) are written;
> closeout promotion done (context/current-state.md + multi-agent-planning.md
> corrected; known-test-failures memory replaced with the verified baseline;
> python-3.12 constraint updated; decision record annotated;
> reactivation-review-2026-08 learning added; all indexes + ACTIVE.md updated).
> Readiness: **REQUIRES_STABILIZATION**. Remediation is NOT started and requires new
> authorization; the project decisions awaiting the owner are listed in
> final-assessment.md §11 and roadmap gates RM-G1/G2 + RM-2.2/2.3. The sections below
> are the historical mid-review handoff, retained as history.

# Handoff — Twinklr Reactivation Review

## Current state

**Stage 0 (bootstrap) and Stage 1 (repository reconstruction) are complete.** The run
is configured `EXECUTION_MODE=discovery-only`, `RUNTIME_MODE=local-safe`, baseline
`aa8d325bca6e83d9be0853e5842759bc7bcb8d1e` (main, clean worktree at start; the only
working-tree changes are this change's own documents).

Done and verified:

- [execution-plan.md](execution-plan.md) — approved by user 2026-08-13 (amendment: OMC
  autopilot/ultrawork/team execution; no Haiku-tier agents; GPT Sol/Codex unavailable
  in this harness — recorded limitation).
- [spec.md](spec.md), [plan.md](plan.md) created; review listed in
  [changes/ACTIVE.md](../ACTIVE.md).
- Seven parallel read-only discovery surveys (workers 1–7, sonnet) + four targeted
  follow-up passes, all complete. Raw reports live in this session's transcripts; all
  load-bearing claims are synthesized with citations into
  [reviews/discovery.md](reviews/discovery.md).
- [reviews/discovery.md](reviews/discovery.md) — topology, entry-point/execution-path
  map, data-flow, claims-vs-reality table, history signals (confirmed dead code,
  confirmed broken surfaces, confirmed bug patterns, migrations in flight, strengths),
  environment blockers, unknowns, hypotheses H1–H5, phase-decomposition validation.
- [reviews/manifest.md](reviews/manifest.md) — disposition of every first-party area.
- Dormancy premise verified: last product-code commit 2026-04-01 (`d9c6ae1`); all
  subsequent commits touch only docs/knowledge trees; no unmerged branches
  (`git branch -a` → main only).

Gate outcome:

- **Discovery gate PASSED (post-correction).** The independent opus critic returned
  PASS-WITH-CORRECTIONS on all five sections; all six blocking corrections and the
  non-blocking refinements are applied to discovery.md/manifest.md/plan.md. The full
  verdict and correction disposition are recorded in plan.md ("Discovery gate record").
  Notably the critic *strengthened* two findings (`.xsq` template-content loss is a
  confirmed production defect, not a hypothesis; the audio validator emits a spurious
  warning on every run and its results are discarded) and reframed the review's central
  Stage-2 question as: **is the LLM load-bearing at all**, given the fully
  enum/template-bounded action space (discovery §8 Q2).

Headline discovery findings (all cited in discovery.md §4–5):

1. Only the moving-heads path is connected end-to-end; the display pipeline and the
   entire corpus/feature-engineering subsystem are complete but unreachable from the
   CLI (production entrypoint never consumes corpus artifacts).
2. `context/architecture/multi-agent-planning.md` documents an LLM-validator role that
   was removed from code; the live loop is planner → heuristic validation with five
   deterministic auto-repair passes → judge.
3. Cache restartability (documented execution property) is defeated at the CLI by a
   per-run random session UUID in cache keys.
4. `.xsq` round-trip fidelity is unprotected: `extra="ignore"` parsing + full XML
   regeneration loses unknown xLights fields; no version-compat logic; zero round-trip
   tests repo-wide (confirmed).
5. Token budgeting is a no-op end-to-end (two independently broken paths, confirmed);
   per-stage token accounting races under FAN_OUT concurrency (confirmed pattern).
6. No CI enforces any quality gate; several Makefile targets are broken; three-way
   version drift across packaging files.
7. Substantial confirmed-dead-code tail (state machine, legacy stages module,
   diarization, genre classifier, stale-schema context builders, unused Pydantic
   `Section` model, etc.) alongside genuinely strong core mechanisms (schema/taxonomy
   auto-injection, categorical vocabulary contract, judge verdict enforcement, atomic
   cache commits).

## Next steps (updated after Stages 2-4, 6-7 completed 2026-08-13)

**Current state: the review is QUIESCED at a user-ordered pause before Stage 5.**
Stages 2, 3 (all seven phase docs VERIFIED), 4 (local half), 6, and 7 are complete;
all subagents are shut down. The complete adversarially-verified evidence base:
`reviews/product-and-approach.md`, `reviews/modernization.md` (incl. M6b xLights
integration surfaces), `reviews/phases/*.md` (7 files, all VERIFIED),
`reviews/verification.md` (per-phase verdicts + Stage 4 runtime baseline + cache-
fingerprint addendum), plus discovery.md/manifest.md.

1. **Await the user's use/iterate/redo decision** on the evidence base. On "use":
   Stage 5 cross-cutting synthesis (reviews/cross-cutting.md + normalized
   findings.md), then Stage 8 (remediation-roadmap.md, final-assessment.md, closeout
   promotion to context//memories/, ACTIVE.md update).
2. Stage 5 must consolidate duplicates across phases (e.g., P1-F27=P3-F24 token race;
   P7-F1=P1-F3 dotenv; the multi-phase dead-config class) and honor the recorded
   cross-phase sequencing constraints (F2 spans phases 3+4; M6 with F1; P1-F31 after
   F29; MB limiter with the P1-F1 fix; prompt-hashing with the session-ID fix).
3. Stage 4 open empirical items (need resources not on this machine): xLights
   import/stamp/shutter tests (concrete specs in verification.md), json_object-on-5.6
   probe (API key). The known-test-failures memory is REFUTED both directions —
   replace at closeout.

## Gotchas

- `make validate` mutates source (ruff format + lint --fix) — run only in a safe clean
  worktree with before/after `git status` evidence, per the review's runtime protocol.
- Display-pipeline/FE runtime evidence needs locally generated `data/templates/` and
  `data/features/` content that is not in the repository; without it those checks are
  BLOCKED, not failed.
- `OPENAI_API_KEY` is hard-required by the CLI; `.env` is never loaded programmatically
  (shell-side only). Live LLM runs are out of scope without explicit user authorization
  (local-safe).
- The four "known test failures" memory is self-flagged as provenance-suspect — treat
  as unverified report, not baseline truth.
- Worker raw reports exist only in this session's transcripts; everything needed for
  continuation has been promoted into discovery.md/manifest.md. If a claim needs
  re-verification, re-check the cited source paths rather than hunting transcripts.
