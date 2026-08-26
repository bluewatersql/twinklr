# Build-campaign handoff — current execution state

_Last updated: 2026-08-26 after P3-T6's independently approved offline/code candidate
was integrated at `c9620db`. P3-T6 empirical xLights GUI acceptance remains open.
P3-T4's one live attempt remains rejected
at the provider schema boundary; `$1.66` is committed and the remaining `$0.09` cannot
fund another audited attempt. Live acceptance remains open and no further P3-T4 live
attempt is authorized. P3-T7+ remains unauthorized. Maintained by the
orchestrating agent; update this file at every
pause or phase boundary._

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
| 3 — Show convergence | **P3-T1–P3-T6 MERGED AND INDEPENDENTLY APPROVED OFFLINE/IN CODE** (6/8 integrated) | P3-T6's standards-, specification-, and adversarial-approved candidate was integrated at `c9620db`. Its empirical xLights GUI acceptance remains open. This does not waive Phase 1P/2P/2K exits, close P3-T4 live acceptance, authorize live work, or authorize P3-T7+. Earlier commits: P3-T5 `f006468`; P3-T4 `558153c`; P3-T3 `33cce57`; P3-T2 `5365f70`; P3-T1 `5eebcb2`. |
| 4 — Compounding | **NOT STARTED** | No Phase 4 implementation has started. |

The overall `twinklr-reactivation-review` change remains **ACTIVE**. Finishing an
offline implementation lane is not the same as satisfying its phase exit criteria.

### Repository and quality-gate evidence

- Canonical current repository and quality-gate evidence is maintained in
  [context/current-state.md](../../../../context/current-state.md); do not fork its
  rolling snapshot into this execution handoff.
- No implementation or test failure is being carried as an accepted baseline.
- The P3-T6 remediation candidate on `codex/p3t6-unified-export` from `e1ed146`
  passed the complete offline suite: **5352 passed, 38 skipped** at 88% coverage;
  immutable goldens **74 passed, 8 skipped**; review-focused **38 passed**; broader
  focused formats/display/MH/injection/transition/CLI/golden **231 passed, 8 skipped**;
  Ruff/format clean; mypy clean across **731 source files**; and `git diff --check`
  clean. Formal first review rejected the prior snapshot; this remediation enforces the
  sole 20 ms header, immutable EffectDB zero, trace-v2-only typing, atomic writer
  prevalidation, and coherent deterministic grouped-MH provenance. The expected golden
  changes are the 20 ms declaration, explicit palette zero, and trace-v2 rows (four MH
  plus eight display in the combined fixture); emitted effect semantics otherwise stay
  pinned. Frozen 23-file implementation/test/golden manifest SHA-256:
  `b2869b67704179b47d0126863b3ae5ff97c909d8c43725d6d39bf789c7d0bf48`. Standards,
  specification, and adversarial review independently approved this exact candidate
  offline/in code; it was integrated at `c9620db`. Empirical xLights GUI acceptance
  remains open.

  Exact frozen implementation/test/golden manifest:

  ```text
  packages/twinklr/cli/main.py
  packages/twinklr/core/api/xlights/injection.py
  packages/twinklr/core/formats/xlights/sequence/emission.py
  packages/twinklr/core/formats/xlights/sequence/exporter.py
  packages/twinklr/core/formats/xlights/sequence/fresh.py
  packages/twinklr/core/formats/xlights/sequence/models/xsq.py
  packages/twinklr/core/formats/xlights/sequence/parser.py
  packages/twinklr/core/formats/xlights/sequence/registry.py
  packages/twinklr/core/formats/xlights/sequence/trace.py
  packages/twinklr/core/sequencer/display/export/effectdb_registry.py
  packages/twinklr/core/sequencer/display/export/writer.py
  packages/twinklr/core/sequencer/display/palette/registry.py
  packages/twinklr/core/sequencer/display/renderer.py
  packages/twinklr/core/sequencer/moving_heads/delivery.py
  packages/twinklr/core/sequencer/moving_heads/export/xsq_adapter.py
  tests/golden/fixtures/combined_show_drop.trace.json
  tests/golden/fixtures/display_pipeline_first.xsq
  tests/golden/test_combined_show_golden.py
  tests/golden/test_delivery_artifacts.py
  tests/unit/cli/test_display_command.py
  tests/unit/formats/xlights/sequence/test_emission.py
  tests/unit/sequencer/display/export/test_writer.py
  tests/unit/sequencer/moving_heads/test_export_core.py
  ```
- The integrated P3-T5 candidate has fresh final author evidence: focused
  CLI/coordination/ownership/integration/golden `54 passed`; immutable goldens `74 passed,
  8 skipped`; full offline suite `5337 passed, 38 skipped`; Ruff/format clean; mypy
  clean across 728 source files; `git diff --check` clean. The owner accepted all nine
  recorded decisions before integration at `f006468`. No live/provider/xLights/audio
  work was performed. P3-T6 is integrated at `c9620db`; its empirical GUI acceptance
  remains open, and P3-T7+ is unauthorized.
- The prior P3-T4 author snapshot was formally rejected, then its first remediation was
  narrowly rejected for reinterpreting `PlanTarget.ZONE` as physical `DisplayZone`.
  The frozen author snapshot restores the established `ChoreoTag` contract. Fresh gates:
  focused `494 passed`; Ruff and formatting clean; mypy clean across 720 source files;
  immutable goldens `73 passed, 8 skipped`; relevant broad suite `5238 passed, 39
  skipped`. The immediately preceding coverage-enabled full run passed `5236/39` at
  87%. These are author evidence only; fresh independent verification is still required.
- Nothing was pushed as part of this milestone.
- The dedicated P3-T4 owner probe harness passed its safety audit and uses
  the shipped prompt/runner/orchestrator and production external validator, fails closed
  before a call, enforces one request per attempt and three attempts total, applies a
  frozen USD cap, and atomically writes owner-local evidence outside the repository.
  Offline safety tests pass. Owner live attempt 1 made exactly one provider request and
  received HTTP 400 `invalid_json_schema` because `ThemeRef.scope` contained `$ref`
  beside `description`. There was no retry or fallback.
- After the harness audit's four safety findings, the remediation now uses one canonical
  tamper-evident global ledger, serialized-request preauthorization, pre-await provider
  entry accounting, exact response-metadata validation, and a transitive source/input
  manifest. Fresh author gates: harness `37 passed`; focused regression `534 passed`;
  goldens `73 passed, 8 skipped`; full `5276 passed, 39 skipped`; Ruff/format/mypy clean.
  Those were prerequisite author findings rather than live acceptance evidence.
- The `$1.75` allowance is enforced as one cumulative P3-T4 task budget. Each attempt
  reserves `$1.66`; exact metered cost replaces it only when trustworthy response
  metadata exists. The owner must independently supply the frozen input, catalog, and
  serialized-request hashes, and local `data/templates/` overlays are disabled.
- Missing, zero-default, partial, inconsistent, or out-of-bound token usage never releases
  an attempt's `$1.66` reservation; it is recorded as unavailable and blocks another
  worst-case reservation under the cumulative `$1.75` cap.
- Attempt 1 had no trustworthy usage, so its full `$1.66` reservation is permanently
  committed. The `$0.09` remaining task budget cannot fund another attempt. The canonical
  owner-local ledger and evidence are preserved outside the repository; live acceptance
  remains open rather than being inferred from the offline schema fix.
- The post-attempt general `$ref` remediation has fresh author evidence: the three
  pre-fix discriminators now pass; strict/provider/contract/harness `122 passed`; complete
  P3-T4 planning/provider surface `638 passed`; Ruff/format/mypy clean (`723` source
  files); immutable goldens `73 passed, 8 skipped`; full offline suite `5280 passed, 39
  skipped`. Remediated source-manifest hash is
  `d424435c62c4486c6c0ed1fc77029b46109edb00575a4e53ce934f1f0b451f08`; serialized
  request hash is `ca9147ba044b347d036a222f0e32b1073e674b5be6efd1387d264e9ecce361c0`
  (`38236` bytes). Independent offline/code reviews approved the remediated candidate,
  which was integrated at `558153c`. This does not convert the failed probe into live
  acceptance.

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

1. Complete the Phase 1P human-judgment and empirical xLights exit evidence.
2. Complete the P2P-T6 owner review and calibration gate; T1/T8/T9 were accepted on
   2026-08-16.
3. Run the P2P-T13 owner protocol and record a D1 outcome only if its evidence validates.
4. Complete the Phase 2K owner-data sessions and coverage exit criteria.
5. Reassess Phase 1P, 2P, and 2K exit criteria explicitly; do not mark a phase complete
   merely because its code/tooling is merged.

P3-T1/P3-T2/P3-T3 are complete and independently verified. P3-T4's owner-approved
contract/invariants, AC2 amendment, and general schema remediation were independently
approved offline/in code and integrated at `558153c`. Its failed live attempt leaves
live acceptance open, with no budget or authorization for another attempt. P3-T5's nine
decisions are owner-accepted and its offline candidate is integrated at `f006468` while
the earlier empirical exits remain open. P3-T6 is independently approved offline/in code
and integrated at `c9620db`; its empirical GUI acceptance is open, and P3-T7+ remains
unauthorized. P3-T2 deliberately leaves
`resolved_color`, `timing_offset_beats`, and parameter-range/settings escaping work to
their existing P3-T5/P3-T8 or display-review owners; it does not silently close them.

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
