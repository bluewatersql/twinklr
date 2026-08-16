# Build-campaign handoff — current execution state

_Last updated: 2026-08-16 during P3-T1 authoring under the owner's explicit sequencing
exception. Maintained by the orchestrating agent; update this file at every pause or
phase boundary._

## What this campaign is

Multi-agent execution of the accepted
[reactivation proposal](../../reviews/reactivation-proposal.md) (v3, decisions D1–D13).
The dependency graph and agent model live in [00-overview.md](00-overview.md); task
contracts live under `../specs/`. Appended implementation handoffs in task specs are
dated evidence snapshots. They may still say “pending independent verification” from
their authoring moment; this handoff owns the current campaign status.

## Current snapshot

| Phase | Current status | Evidence / remaining boundary |
|---|---|---|
| 0 — Foundation honesty | **COMPLETE** (7/7) | Completion record in [01-phase-0-foundation.md](01-phase-0-foundation.md) |
| 1K — Knowledge edges | **COMPLETE** (5/5) | Completion record in [03-phase-1k-knowledge-edges.md](03-phase-1k-knowledge-edges.md) |
| 1P — Render truth | **IMPLEMENTATION MERGED AND VERIFIED** (12/12); **phase exit not complete** | The recorded human judgment and empirical xLights acceptance evidence remain pending; see [02-phase-1p-render-truth.md](02-phase-1p-render-truth.md). |
| 2P — Creative quality | **OFFLINE IMPLEMENTATION MERGED AND VERIFIED** (13/13); **phase exit not complete** | The owner accepted T1/T8/T9 on 2026-08-16. T6 calibration/live evidence, T13/D1 evidence, and other live checks remain pending; see [04-phase-2p-creative-quality.md](04-phase-2p-creative-quality.md). |
| 2K — Catalog growth | **TOOLING IMPLEMENTATION MERGED AND VERIFIED** (4/4); **phase exit not complete** | Tooling is ready, but coverage/corpus/curation/style exit criteria require the author's real layout, corpus, preferences, and judgments; see [05-phase-2k-catalog-growth.md](05-phase-2k-catalog-growth.md). |
| 3 — Show convergence | **P3-T1 AUTHORED; INDEPENDENT VERIFICATION PENDING** | On 2026-08-16 the owner explicitly authorized P3-T1 before the outstanding empirical exits. This narrow sequencing exception does not waive any Phase 1P/2P/2K exit criterion and does not authorize later Phase 3 tasks. |
| 4 — Compounding | **NOT STARTED** | No Phase 4 implementation has started. |

The overall `twinklr-reactivation-review` change remains **ACTIVE**. Finishing an
offline implementation lane is not the same as satisfying its phase exit criteria.

### Repository and quality-gate evidence

- Canonical current repository and quality-gate evidence is maintained in
  [context/current-state.md](../../../../context/current-state.md); do not fork its
  rolling snapshot into this execution handoff.
- No implementation or test failure is being carried as an accepted baseline.
- Nothing was pushed as part of this milestone.

### Phase 2P offline implementation record

All 13 task implementations are merged and independently verified: schema-v2 intent
and renderer wiring, data-first templates, lyric MomentCues, xLights preview client,
vision/sync evaluation, opt-in stems, fixed-gate MIR A/B, iterative-judge repair, model
retargeting, strict structured outputs, live-injection workflow, and the deterministic
selector/three-arm experiment harness. P2P-T8's precommitted offline gate recommends
retaining the current DSP default because neither optional model candidate produced
complete admissible local evidence. The runtime default remains `dsp`; the owner accepted
that recommendation on 2026-08-16. See the accepted
[MIR decision record](../../../../memories/decisions/keep-dsp-after-mir-ab.md).

P2P-T13 produced an evidence-preserving experiment implementation, **not an experiment
result**. There is no D1 verdict, proposal update, D1 decision record, or three-arm
evaluation artifact. The exact owner protocol and caps remain in
[P2P-T13-three-arm-comparison.md](../specs/phase-2p-creative-quality/P2P-T13-three-arm-comparison.md).

### Phase 2K tooling implementation record

The four tooling changes are merged and independently verified:

- P2K-T1 coverage report tooling — `25ea555`
- P2K-T2 corpus mining/distribution and threshold-review tooling — `1bd56c3`
- P2K-T3 targeted generation and human-admission tooling — `df2b295`
- P2K-T4 style-group fingerprints, propensity refresh, and selection plumbing — `64bc4d1`

These commits make the owner sessions executable and auditable. They do not assert that
the author's catalog has reached coverage, that real corpus thresholds were decided,
that any generated recipe was admitted, or that preferred-style artifacts exist.

## Owner/local gates still pending

The owning task specs contain the exact commands and safety constraints; do not copy or
improvise their runbooks here.

### Earlier empirical checks

1. Add the human judgment to
   `evaluations/2026-08-13-golden-fixture-mh4-minimal/judgment.md`.
2. Run the Phase 1P xLights acceptance suite in both documented show-directory modes
   against an expendable show and record the result.

### Phase 2P

The owner accepted the P2P-T1 schema contract, P2P-T8 DSP-retention recommendation,
and P2P-T9 iteration/threshold policy on 2026-08-16. The remaining decision-bearing
reviews and evidence gates are requirements, not implied approvals from merge:

1. [P2P-T6](../specs/phase-2p-creative-quality/P2P-T6-vision-judge-and-sync-metrics.md):
   review the four-category rubric and criteria, calibration outcome, and
   per-song cost budget. First run the capped one-song live provider/xLights proof and
   complete an owner-accepted, hash-pinned blinded calibration with at least five
   independent shows.
2. [P2P-T13](../specs/phase-2p-creative-quality/P2P-T13-three-arm-comparison.md): only
   after accepted T6 calibration, freeze a manifest of at least eight
   songs, run exactly 5N sequences within the frozen cost caps, complete the blinded
   human ranking, independently verify the evidence, and then have the owner review the
   verdict and human spot-checks before any D1 result is recorded.

The remaining empirical checks are also pending:

3. P2P-T5: exercise preview rendering against the owner's windowed xLights instance.
4. P2P-T7: run real Demucs separation on supported Apple Silicon hardware and observe
   MPS/CPU-fallback behavior.
5. P2P-T10/P2P-T11: run the bounded live model-retarget and structured-output probes;
   record evidence before promoting any provider conclusion.
6. P2P-T12: run live injection only against an expendable scratch sequence and discard
   it afterward.

### Phase 2K

1. Run the coverage report against the author's real layout and curate until the
   element-type × role × energy gap count is zero.
2. Run idempotent mining over the author's real corpus and record the owner-authored
   threshold keep/change/defer log.
3. Run live targeted recipe generation and explicit human admission/rejection sessions;
   do not promote candidates without the session evidence.
4. Supply the author's style-group declaration, generate per-style fingerprints, rebuild
   propensity from stable corpus identities, and verify planner consumption on real data.

## Continuation order

1. Independently verify and integrate P3-T1 under the owner's 2026-08-16 sequencing
   exception. Do not infer authorization for P3-T2 or other Phase 3 tasks.
2. Complete the Phase 1P human-judgment and empirical xLights exit evidence.
3. Complete the P2P-T6 owner review and calibration gate; T1/T8/T9 were accepted on
   2026-08-16.
4. Run the P2P-T13 owner protocol and record a D1 outcome only if its evidence validates.
5. Complete the Phase 2K owner-data sessions and coverage exit criteria.
6. Reassess Phase 1P, 2P, and 2K exit criteria explicitly; do not mark a phase complete
   merely because its code/tooling is merged.

Phase 4 remains downstream of Phase 3.

## Binding orchestration rules

- Use executor/verifier separation; an author never approves their own work.
- Workers do not run git state or mutation commands. The orchestrator owns integration.
- Verify from a worktree-local synced environment; shared editable installs can point at
  the wrong checkout.
- Use Ruff with `--no-cache` when a count matters.
- Acceptance metrics must discriminate on a pre-fix or adversarial case.
- Golden changes use only the explicit regeneration path and require hunk attribution.
- Owner judgment, paid/live calls, calibration, and local data are never fabricated.
