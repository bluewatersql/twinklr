# Active Changes

_Last updated: 2026-08-16._

- **twinklr-reactivation-review** — **ACTIVE: implementation phase (build campaign).**
  The review completed 2026-08-13 (all 8 stages, adversarially verified, verdict
  REQUIRES_STABILIZATION); the owner then authorized execution of the
  [reactivation proposal](twinklr-reactivation-review/reviews/reactivation-proposal.md)
  as a multi-agent build campaign living in
  [`twinklr-reactivation-review/build/`](twinklr-reactivation-review/build/plan/00-overview.md)
  (plan + 56 per-task specs). **Status: Phases 0 and 1K are complete. All Phase 1P
  implementation tasks, all 13 Phase 2P offline implementations, and all four Phase 2K
  tooling implementations are merged and independently verified at `6b2b34a`, but
  Phases 1P, 2P, and 2K still have owner-gated exit evidence.** Phase 1P needs its
  recorded human judgment and empirical xLights acceptance; Phase 2P needs its remaining
  live calibration and three-arm evidence (the owner accepted T1/T8/T9 on 2026-08-16);
  Phase 2K needs real-layout, real-corpus, human-curation, and preferred-style evidence.
  The owner explicitly authorized P3-T1, P3-T2, and P3-T3 before those empirical exits
  on 2026-08-16. P3-T1 is merged and independently verified at `5eebcb2`; P3-T2 is
  merged and independently verified at `5365f70`; P3-T3 is independently verified and
  approved for integration, including its canonical `twinklr display` command and
  offline file-only layout source. The owner's latest continuation authorizes P3-T4 as
  the next offline task only. Phase 4 has not started. The overall change
  therefore remains active.
  Live execution state, process rules, and pending owner actions:
  **[build/plan/HANDOFF.md](twinklr-reactivation-review/build/plan/HANDOFF.md)**.
  Review artifacts:
  [Findings](twinklr-reactivation-review/reviews/findings.md) ·
  [Verification record](twinklr-reactivation-review/reviews/verification.md).
  Durable truths promoted to `context/current-state.md` and
  `memories/learnings/reactivation-review-2026-08.md`.

When starting a new change, create `changes/<slug>/` per the conventions in
[INDEX.md](INDEX.md) and list it here with: name, status, one-line purpose, and links to
its spec / current plan / latest handoff.
