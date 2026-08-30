# Active Changes

_Last updated: 2026-08-29._

- **post-refactor-validation** — **ACTIVE: Phase 3 live run PASSED.** Comprehensive
  current-state code review (all 21 core subpackages, ~126K LOC) + functional inventory
  done. The 49 `make validate` failures were root-caused as environment/test-hygiene only
  (no refactor regressions) and fixed (`ca7ed35`). Landed live-run prerequisites: P2-5
  capability policy for the gpt-5.6 family (`91677ab`), P2-6 session/provider `aclose()`
  (`8f27883`), P2-7 temperature in group/holistic cache keys (`5aecb9e`). **Phase 1**
  offline `.xsq` parity harness (`2565b93`): 264 placed effects vs the baseline's 262.
  **Phase 3** live end-to-end MH run on `11 - Need A Favor.mp3` (public OpenAI, owner's real
  4-MH rig) **succeeded** and emitted a valid `.xsq` that meets/exceeds the pre-refactor
  baseline (placed effects 396 vs 262; distinct DMX settings 365 vs 262; value-curve
  channels 1306 vs 622). Two real code bugs found & fixed en route (`08ce6d5`):
  reasoning/temperature mutual-exclusivity (macro `gpt-5.2` 400) and zero-duration emission
  segments aborting render; plus resolved TLS (proxy CA → `SSL_CERT_FILE`), stale
  `fixture_config.json`/`job_config.json` schema drift, and a too-low 60s agent timeout for
  reasoning models. Live spend ≈ $1–2 of $25. Post-run hardening landed: zero-width
  transitions dropped upstream (`a8ce12b`) and the default agent timeout raised to 300s
  (`d15ee03`). Phase 1 display replay-render parity landed (`a40aab7`): a hermetic replay of
  the resolvable `02_rudolph` plan subset reproduces 10 of the baseline's 11 effect types and
  its 5-layer depth (10 of 38 plan templates were retired from the catalog since Feb 2026, so
  the replay uses a committed self-contained recipe snapshot). Phase 4 human-QA readiness:
  step-by-step [QA runbook](../docs/qa-runbook.md) built and validated, `current-state.md`
  updated with the empirical evidence. Remaining: owner review/sign-off, then close. Live-run
  findings:
  [notes/live-run-prereqs.md](post-refactor-validation/notes/live-run-prereqs.md). Deep
  findings:
  [notes/functional-inventory.md](post-refactor-validation/notes/functional-inventory.md).
  Internal validation checkpoint
  proving the `twinklr-reactivation-review` refactoring left the engine working end to
  end at prior-state functional level, then locking that output as the go-forward
  regression baseline. Five phases: Phase 0 current-state code review & functional
  inventory → offline structural regression vs. `artifacts/` baselines → CI replay E2E +
  provider-contract smokes → authorized live end-to-end show → lock baseline + human-QA
  readiness. Owner authorized live provider/model calls (2026-08-29). Spec:
  [post-refactor-validation/spec.md](post-refactor-validation/spec.md); plan:
  [post-refactor-validation/plan.md](post-refactor-validation/plan.md). Depends on and
  produces empirical E2E evidence for the reactivation-review phase exits below.

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
  `c9620db`. P3-T8's independently approved offline implementation was integrated at
  `82438cf`. P3-T7's final corrected freeze
  (`2caf726b505fb6fc3e17f56165b4884ce0f33a1525f9768d6a880621e16e9192`) is
  independently approved offline/in code and is included in the current integration.
  Phase 3 now has all eight offline task implementations integrated. These integrations do not
  waive the outstanding Phase 1P/2P/2K exits, close P3-T4 live acceptance, or authorize
  P3-T5 live work or any paid/local empirical action. On 2026-08-26 the owner accepted
  P3-T6's amended offline unified-emission contract. Its empirical xLights GUI
  acceptance remains open. The owner authorized P3-T7+ and task-bounded live/paid work
  on 2026-08-26. P3-T7's audited live proof then passed with exactly one
  `gpt-image-2` request, no retry, a zero-call scoped cache replay, and measured cost
  `$0.00622`; the sealed owner-local ledger permanently blocks another attempt. All
  xLights GUI dates/checks remain deferred until a meaningful,
  fully working end-to-end show exists; their empirical gates and all earlier empirical
  exits remain open.
  Phase 4 has six of seven tasks integrated. P4-T1 landed at `56d9aa0`; P4-T2's
  implementation and redirect hardening are integrated through `3765bd9`/`40e8e55`;
  P4-T3 is integrated at `bf6bba5`; P4-T4 is integrated at `3e7f679`; P4-T5 is
  integrated at `05f24d0`; and P4-T6 is integrated at `da8f19d`, each after independent
  verification. P4-T2's real Ollama schema smoke remains unclaimed pending explicit
  local opt-in. P4-T7's independently approved repository-only preflight is integrated
  at `c79566e`; it corrects the unsupported vendor-history premise and records the exact
  corpus-gated re-entry and isolated-offline boundaries. P4-T7 full execution remains
  NO-GO/deferred. P2K-T2's independently Standards- and Spec-approved offline-readiness
  hardening is integrated at `03b75e9`, but its real owner-corpus run, unchanged-corpus
  idempotent rerun evidence, non-empty distributions, and exactly eight owner decisions
  remain open; no accepted, sufficient private moving-head corpus manifest exists. The
  integrated preflight is not P4-T7 completion and makes no feasibility verdict; Phase
  4 remains six of seven tasks integrated and no Phase 4 completion is claimed.
  Optional WhisperX runtime audio execution remains owner-deferred against the current
  default FFmpeg 9; see the
  [active task spec](twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md).
  The overall change
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
