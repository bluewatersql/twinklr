---
type: decision
status: accepted
created: 2026-11-12
updated: 2026-11-12
confidence: confirmed
tags: [macro-planner, live-run, acceptance, p3-t4]
---

# P3-T4 Live Macro Acceptance Is Closed by Later Live Runs

_Accepted by the owner on 2026-11-12, choosing option 1 ("Accept") of
[runbook 05 §7](../../changes/twinklr-reactivation-review/runbooks/05-phase-2p-and-3-live-evidence.md).
The 2026-11-12 Claude baseline run, made under runbook 05 §2 and not as P3-T4 work, is
cited as additional corroborating evidence. The decision itself involved no new spend._

## Decision

The P3-T4 live macro-contract acceptance item is **closed**. Two later live end-to-end runs
supersede it as the evidence; both exercised the macro planner with a real song:

- **2026-08-29, public OpenAI.** The post-refactor-validation live moving-head run on
  `11 - Need A Favor` passed, with sophistication at or above the pinned baseline
  ([live-run-prereqs.md](../../changes/post-refactor-validation/notes/live-run-prereqs.md)).
- **2026-11-12, Claude `claude-opus-5-5`.** Run on `Hey Come Look At My House`.
  - The `MacroPlan` validated on the planner's second iteration and the macro judge
    approved it at 7.6.
  - The full run passed 6/6 stages.
  - [Evaluation](../../evaluations/2026-11-12-claude-baseline-live-run/README.md).

## Boundaries that still hold

- **The P3-T4 ledger stays sealed.** The two audited attempts and the `$3.320000`
  commitment stand as recorded. No third attempt is authorized. Nothing in the canonical
  ledger or the frozen probe harness (`macro_planner/live_probe.py` and its fixtures) is
  run, edited, moved or re-sealed.
- **The failure classes are fixed and covered offline.** Both attempt failures (a `$ref`
  sibling schema, and `temperature` sent to reasoning models) are fixed in code with
  offline tests.
- **What this does not cover.** The superseding runs exercise the moving-head `twinklr run`
  path. Live `twinklr display` and `twinklr show` evidence remains with P3-T8 and the
  xLights GUI gates ([runbook 04](../../changes/twinklr-reactivation-review/runbooks/04-xlights-gui-and-human-acceptance.md)).
  This decision does not close those.

Related: [typed-macro-coordination-contract.md](typed-macro-coordination-contract.md) ·
[P3-T4 spec](../../changes/twinklr-reactivation-review/build/specs/phase-3-show-convergence/P3-T4-macro-structured-contract.md)
