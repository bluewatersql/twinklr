# Active Changes

_Last updated: 2026-08-26._

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
  merged and independently verified at `5365f70`; P3-T3 is merged at `33cce57` after
  independent verification and owner acceptance of its canonical `twinklr display`
  command and offline file-only layout source. On 2026-08-16 the owner accepted the
  exact four-field contract, its invariants, and the AC2 amendment that treats P3-T4's
  recursive typed/by-name readers as the task boundary while reserving emitted behavior
  for P3-T5. P3-T4 was independently approved offline and in code review, then integrated
  at `558153c`. The owner also authorized only the capped P3-T4 live macro probe (at most
  three attempts, subject to one cumulative `$1.75` cap). The dedicated fail-closed
  harness passed audit. Its first live attempt made one request and was safely rejected
  by OpenAI with HTTP 400 `invalid_json_schema` because `ThemeRef.scope` had a `$ref`
  sibling `description`; no retry or fallback occurred. Usage was unavailable, so the
  full `$1.66` reservation remains committed and the remaining `$0.09` cannot fund a
  second attempt. The general `$ref` normalization fix is integrated and offline-verified.
  On 2026-08-26 the owner authorized exactly one second audited request under
  authorization `p3-t4-second-attempt-owner-approved-2026-08-26`, with exact additional
  `$1.660000` preauthorization, a `$3.32` cumulative hard cap, and a two-attempt lifetime
  cap. After independent audit and clean-commit preflight, attempt 2 made exactly one
  provider request on 2026-08-26. OpenAI returned HTTP 400 because `temperature` is not
  supported by `gpt-5.6-sol`; there was no retry, fallback, logical request, schema
  repair, or usage metadata. Both `$1.660000` reservations are therefore committed
  (`$3.320000` total), the two-attempt lifetime cap is exhausted, no third attempt is
  authorized, and live acceptance remains open. An offline remediation now normalizes
  request parameters through an explicit model-capability policy so `gpt-5.6-sol`
  omits temperature while retaining reasoning effort; it does not create live
  acceptance or another attempt. The
  owner subsequently accepted all nine P3-T5 decisions, and P3-T5 was integrated at
  `f006468`. P3-T6's remediated candidate then received independent standards,
  specification, and adversarial approval offline/in code and was integrated at
  `c9620db`. Phase 3 now has six of eight tasks integrated. These integrations do not
  waive the outstanding Phase 1P/2P/2K exits, close P3-T4 live acceptance, or authorize
  P3-T5 live work or any paid/local empirical action. On 2026-08-26 the owner accepted
  P3-T6's amended offline unified-emission contract. Its empirical xLights GUI
  acceptance remains open. The owner authorized P3-T7+ and task-bounded live/paid work
  on 2026-08-26. All xLights GUI dates/checks remain deferred until a meaningful,
  fully working end-to-end show exists; their empirical gates and all earlier empirical
  exits remain open.
  Phase 4 has not started. The overall change
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
