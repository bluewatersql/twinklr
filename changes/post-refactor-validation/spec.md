---
type: change
status: active
area: quality
created: 2026-08-29
updated: 2026-08-29
---

# Post-refactor functional validation

_Spec for `changes/post-refactor-validation/`. Implementation plan:
[plan.md](plan.md). See [changes/INDEX.md](../INDEX.md) for lifecycle/closure rules._

## Objective

Prove — with fresh, reproducible evidence — that after the large
`twinklr-reactivation-review` refactoring wave (Phases 3–4: unified emission core,
duplication collapse, dead-code retirement, schema-v2 intent, config accountability, ML
chain bump), the project **still works end to end and produces output at least equal to
its prior-state functionality**. Once parity is demonstrated, capture that output as the
**locked regression baseline** going forward.

This is an internal validation checkpoint, not a new feature. It exists because the
[reactivation-review handoff](../twinklr-reactivation-review/build/plan/HANDOFF.md) is
explicit that _merged tooling and passing offline tests are not empirical acceptance_,
and because no automated or manual regression currently compares current pipeline output
against the pre-refactoring outputs in `artifacts/`.

## Problem statement (why now)

Established from repository evidence on 2026-08-29:

1. **No successful live end-to-end show exists post-refactoring.** The only live
   macro-planning path (P3-T4) failed its two authorized attempts (schema `$ref`
   boundary, then HTTP 400 unsupported `temperature`) and is capped/exhausted. The
   handoff's "reach one meaningful non-GUI end-to-end show" milestone is still open.
2. **The E2E automated tests are offline with the LLM mocked.** `tests/integration/*_e2e`
   and `tests/golden/` exercise the real pipeline executor/emission/serialization
   deterministically, but every planning stage is stubbed (`AsyncMock`/`patch`). Live
   provider, vision, and xLights tests exist only under `tests/local_only/` and
   `tests/golden/test_xlights_acceptance.py` and are **skipped in CI**.
3. **Nothing validates against `artifacts/`.** The Feb–Mar 2026 generated outputs
   (`02_rudolph…`, `11_need_a_favor`, `titanium…`, `need_a_favor`) predate the Aug 2026
   refactoring, are gitignored, and no test references them. There is zero regression
   coverage of semantic drift introduced by the refactoring.

## Scope

**In scope**

- A thorough current-state code review to establish the true functional inventory (what
  works, what is stubbed, what is partially complete) — Phase 0, informs the rest.
- An offline structural regression harness comparing current pipeline output to a curated
  set of pre-refactoring `artifacts/` baselines.
- Automated, CI-runnable full-pipeline E2E via cached/replayed provider responses, plus
  offline provider-contract smokes for the failure classes that killed P3-T4.
- **Authorized live** end-to-end validation runs (owner granted live-call authorization
  on 2026-08-29) to demonstrate prior-state functional parity.
- Locking the validated output as the tracked regression baseline and defining
  human-QA-readiness criteria.

**Out of scope**

- New product features or creative-quality improvements.
- Closing owner-taste empirical exits that require human judgment (P2P-T6 calibration
  ranking, P2P-T13/D1 verdict) beyond running their mechanics — those remain owned by
  `twinklr-reactivation-review`.
- xLights GUI acceptance dates (deferred until the meaningful E2E show exists; this change
  is a prerequisite to scheduling them, not a substitute).
- Re-opening any sealed ledger (P3-T4 no third attempt; P3-T7 terminal image proof).

## Relationship to `twinklr-reactivation-review`

This change is a validation layer over that campaign's outputs. It does not supersede its
phase exits; it produces the empirical E2E evidence several of them depend on. Durable
results promote back into `context/current-state.md` and, where relevant, the reactivation
change's phase exits.

## Success criteria

1. A written functional inventory distinguishing working / stubbed / partial features,
   with file-level evidence.
2. A green offline regression harness proving structural parity (within declared
   tolerances) against curated `artifacts/` baselines, wired into `make validate`.
3. A CI-runnable full-pipeline E2E (audio → plan → render → `.xsq`) using replayed
   provider fixtures, plus offline provider-contract smokes that catch the P3-T4 failure
   classes.
4. At least one **live** full-pipeline show run producing valid `.xsq`/timing artifacts,
   with cost recorded, demonstrating parity with prior-state functionality.
5. A locked, tracked baseline and an explicit, owner-reviewed human-QA-readiness checklist.
