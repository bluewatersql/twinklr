# Active Changes

_Last updated: 2026-11-18._

One row per workstream. Keep rows short: status, where the work lives, and the next
action. Detail and history belong in the change folder.

## Active

| Change | Status | Branch / owner | Next action | Start here |
|---|---|---|---|---|
| [`twinklr-reactivation-review/`](twinklr-reactivation-review/spec.md) | **Build campaign: code complete, empirical exits open.** Phases 0 and 1K are complete. Phases 1P, 2P, 2K, and 3 have every implementation task merged and independently verified, but their owner, live, xLights, and real-data exits are not met. Phase 4 has 6 of 7 tasks merged; P4-T7 is optional and NO-GO. | `main`; integrator is the orchestrating session | Owner actions, in [runbook order](twinklr-reactivation-review/runbooks/README.md): decide whether the 2026-11-12 Ollama cloud pipeline pass closes P4-T2; watch `rendered.xsq` and record the Claude-baseline judgment; xLights GUI acceptance (runbook 04); P2K-T2 owner-corpus run (runbook 02). | [build/plan/HANDOFF.md](twinklr-reactivation-review/build/plan/HANDOFF.md) |
| [`2026_11_12_knowledge_optimization/`](2026_11_12_knowledge_optimization/brief.md) | Restructure of the agent router, context, memories, and prompts for multi-agent, multi-workstream use, aligned to the OnDeck layout. Documentation only. | `chore/knowledge-optimization` | Owner review, then merge and close. | [handoff.md](2026_11_12_knowledge_optimization/handoff.md) |
| [`2026_11_12_mh_true_up/`](2026_11_12_mh_true_up/implementation-brief.md) | Moving-head true-up. Phases 0–2 merged to `main` (last `7356b376`). Phase 3 is on `feat/mh-true-up-p3` (head `cd13034a`, renderer revision 20; not merged, not pushed). It has one moving-head renderer (cutover C1.1–C1.5). The song intent the cutover lost is rendered again: colour and gobo, intensity, events and lyric cues, transitions, show palette and focal role, motif and variation with rig-fitted variants. The song outranks the arrangement: a variation gives way where it would make an event worse. Density (`feat/mh-true-up-p3-density`) and modifiers (`feat/mh-true-up-p3-modifiers`) are on side branches, to be wired in as arrangement units. Hardware results and every look verdict since 2026-11-16 are `PENDING-OWNER`; live `inject`/`regenerate` is proven against a fake only. | `feat/mh-true-up-p3`, worktree `twinklr-mh-true-up`; side branches as listed | Integrator: recover both unfinished side-branch merges after the Claude spend-limit interruption; [exact state and steps](2026_11_12_mh_true_up/plan/capacity-recovery-2026-11-18.md). Complete review and the combined validation gate before merging density and modifiers into the branch. Owner: answer the [owner decisions](2026_11_12_mh_true_up/plan/owner-decisions-pending.md) and decide the merge; then authorize a real end-to-end paid run (the planner contract and caches changed). The rest, in order, is in the handoff. | [plan/handoff.md](2026_11_12_mh_true_up/plan/handoff.md) |

Standing boundaries for the campaign (sealed P3-T4 and P3-T7 ledgers, owner-gated live
work) are in [context/current-state.md](../context/current-state.md#permanent-boundaries).
The per-phase table is in
[context/current-state.md](../context/current-state.md#active-work); the dated record of
every attempt, authorization, and commit is in the campaign handoff.

## Recently closed

| Change | Outcome |
|---|---|
| [`post-refactor-validation/`](post-refactor-validation/spec.md) | Closed 2026-11-01. Proved the refactored engine works end to end with a live moving-head show that meets or exceeds the pre-refactor baseline, and locked offline regression baselines. Unfinished items and where each went: [plan.md § Closeout](post-refactor-validation/plan.md#closeout--2026-11-01). |

To start a change, follow
[../prompts/planning/start-a-change.md](../prompts/planning/start-a-change.md).
