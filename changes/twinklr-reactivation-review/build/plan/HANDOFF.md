# Build-campaign handoff — current execution state

_Last updated: 2026-08-26 after all eight Phase 3 offline task implementations and
P4-T1 through P4-T6 were independently verified and integrated. P2K-T2's offline
owner-run readiness remediation was independently approved on the Standards and Spec
axes and integrated at `03b75e9`; its empirical owner-corpus exits remain open. P4-T7's
repository-only preflight is independently approved and integrated, while P4-T7 itself
remains optional, incomplete, and NO-GO.
P3-T6 empirical xLights GUI acceptance remains
open, with all GUI dates/checks deferred until a meaningful end-to-end show is fully
working.
P3-T4's two live attempts both failed safely: attempt 1 at the provider schema boundary,
and attempt 2 with HTTP 400 because `temperature` is unsupported by `gpt-5.6-sol`.
Exactly one provider request and no retry/fallback/schema repair occurred in each;
`$3.320000` is committed, the two-attempt cap is exhausted, no third attempt is
authorized, and live acceptance remains open. P3-T7+ and
task-bounded live/paid work are authorized. P3-T7 is independently approved offline/in
code and integrated at `70b3305`. Its one-shot live proof passed with one request, no
retry, a valid 1024×1024 PNG, a zero-call scoped cache replay, and measured cost
`$0.00622`; the terminal sealed ledger forbids another attempt. P3-T8's remediated offline implementation is integrated at `82438cf`; its GUI preview, live judge, human review, calibration, and
real completed record remain deferred to that end-to-end milestone. Maintained by the
orchestrating agent; update this file at every
pause or phase boundary._

## Next-agent handoff — 2026-08-26 session closeout

Start here. This section supersedes older status prose below when the two disagree;
older entries remain as dated audit history.

### Exact repository state

- Integration baseline immediately before this handoff edit: `main` at
  `ac6ffbce12c0385e2b9b86f8f2dd1c415833b8b9`. The committed handoff itself is the next
  documentation-only commit; use the commands below rather than treating `ac6ffbc` as
  the post-handoff HEAD.
- Nothing from this session was pushed. Immediately before this handoff commit, `main`
  was 52 commits ahead of `origin/main`.
- There is one worktree: `/Users/ondeck/work/github/twinklr`. The temporary P4-T7 and
  P2K-T2 worktrees and their integration branches were removed after merge.
- Historical `codex/p2k-*` and `codex/p2p-*` local branches still exist. They predate
  this closeout and were not deleted because branch deletion was not part of the task.
- No subagent is still doing work. Completed agent records may remain visible in the
  orchestration UI, but there is no running worker to resume.
- The current accepted quality snapshot is single-owned by
  [context/current-state.md](../../../../context/current-state.md): exact-tip validation
  for integrated source `03b75e9` left 1,361 files unchanged, Ruff clean, mypy clean
  across 721 source files, and 5,637 passed / 39 skipped at 89% coverage. Closeout
  `ac6ffbc` changes documentation only.

Quick verification:

```bash
git status --short --branch
git log -6 --oneline
git worktree list
```

### Work completed in this session

1. **P4-T7 repository-only prerequisite preflight**
   - The first freeze `2fff098` was independently rejected because its P2K report gate
     was incomplete, its future archive profiling plan could delete a sibling owner
     directory, and it omitted the exact temporal aligner seam.
   - Remediation `c79566e` was independently approved and integrated. It records five
     exact re-entry artifacts, corrects the unsupported vendor-history premise, and
     requires hash-verified archive copies in isolated task-owned scratch before any
     future profiling.
   - Status closeout `bc7e270` records the preflight as integrated. **P4-T7 itself is
     still optional, incomplete, and NO-GO/deferred.** The preflight is not a corpus
     run, task completion, prototype, or feasibility verdict.
   - Canonical records:
     [active P4-T7 spec](../specs/phase-4-compounding/P4-T7-mh-idiom-mining-exploration.md)
     and [repository preflight](../specs/phase-4-compounding/P4-T7-repository-preflight.md).

2. **P2K-T2 offline owner-run readiness hardening**
   - Readiness audit found six blockers: incomplete threshold sensitivity, count-only
     idempotence, incomplete provenance, unbound final reports, unsafe/ambiguous command
     behavior, and no private MH-manifest contract.
   - The first implementation freeze `64ce517` was independently rejected on both
     Standards and Spec axes. Reviewers reproduced live-catalog-child output acceptance,
     symlink-following cleanup, coercive manifest truthiness, runtime/report family-cap
     mismatch, stale decision/report binding, and malformed/duplicate decisions.
   - Remediation `9059ff7` (rebased as `9536206`) added strict Pydantic V2 evidence
     models, protected-root/no-follow cleanup, stable entity-key/content idempotence,
     complete configured-plus-two-nearby sensitivity for all retained numeric values,
     runtime-accurate family grouping, current/staged artifact binding, exactly eight
     typed owner decisions, and one redacted accepted-P2K + private-MH re-entry binding.
   - Standards and Spec reviewers approved the replacement. The rebased integration was
     finalized at `03b75e9`; docs closeout is `ac6ffbc`.
   - Focused adversarial matrix: 41 passed. Clean full gate: 1,361 files unchanged,
     Ruff clean, mypy 721, 5,637 passed / 39 skipped with 43 resource warnings.
   - No owner corpus, private MH manifest, network, provider, live catalog, or paid
     service was accessed. **This makes the tooling safe and reviewable; it does not
     satisfy P2K-T2's empirical exit.**
   - Operator runbook: [feature-engineering workflow](../../../../scripts/docs/feature_engineering.md).

3. **Review and integration discipline**
   - Every author freeze was independently reviewed; rejected snapshots remain recorded
     as rejected rather than silently rewritten.
   - The final P2K rebase preserved all approved P4-T7 preflight history. A narrow final
     clarification supersedes the preflight memo's stale “five decisions” language:
     current artifact 4 is strict `OWNER_DECISIONS.json` with exactly eight entries, and
     the dead anti-affinity constant is not a sensitivity/decision item.
   - No live/provider/corpus/xLights/audio action occurred during these lanes.

### Current blockers and owner decisions

#### 1. Strict Phase 4 exit: real local Ollama schema smoke

This is the only strict Phase 4 exit blocker under the accepted contract. P4-T7 is
optional and does not itself block phase closure; P4-T1's WhisperX/TorchCodec runtime
deferral is an accepted non-blocking owner amendment.

Read-only inspection at closeout:

- Ollama is installed at `/opt/homebrew/bin/ollama`, version `0.32.9`.
- `ollama list` contains only cloud entries: `kimi-k3:cloud`,
  `deepseek-v4-pro:cloud`, and `glm-5.2:cloud`.
- There is **no already-pulled local model**, so the accepted one-request local-only
  smoke cannot run yet.

Do not infer authority to download a multi-gigabyte model. The next agent needs one of
two explicit owner choices:

1. authorize pulling a named local Ollama model, then run exactly one schema smoke; or
2. explicitly amend/waive the Phase 4 contract so offline implementation is accepted
   and real local schema validity remains deferred.

After a named model is already pulled and Ollama is running, the accepted smoke command
is:

```bash
TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 \
TWINKLR_OLLAMA_MODEL=<already-pulled-local-model> \
TWINKLR_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1 \
uv run pytest tests/local_only/test_ollama_structured_outputs.py -q --no-cov
```

The test permits one provider attempt, disables fallback/repair, and proves schema
validity only for that exact installed model. If it fails or the result is ambiguous,
record the exact outcome and do not retry or pull another model without renewed owner
direction. See the [P4-T2 contract](../specs/phase-4-compounding/P4-T2-local-provider-option.md).

#### 2. P2K-T2 empirical owner-data exit

The implementation is ready, but the following evidence still does not exist:

1. a real owner-corpus mining manifest from the hardened command;
2. an unchanged-corpus rerun with matching entity-key/content digests and no duplicate
   identity or row growth;
3. non-empty support, stability, distinct-pack, effective-threshold, and nearby-
   sensitivity evidence;
4. strict `OWNER_DECISIONS.json` containing exactly eight dated keep/change/defer
   decisions and rationales.

Do not search, open, parse, or mine private/local corpus content merely because the
tooling is integrated. Wait for the owner to provide the explicit unified corpus path,
music-index-or-none choice, and dedicated new output directory.
Then follow the linked runbook exactly: run the same owner command twice, verify the
unchanged-rerun manifest, generate reports, complete all eight decisions, bind them, and
independently review the resulting accepted P2K evidence. Never write raw/private corpus
or derived vendor curves into Git. A private MH manifest is a separate P4-T7 admission
prerequisite; it is not required to complete P2K-T2's own empirical exit.

#### 3. P4-T7 optional exploration

Do not begin P4-T7 until all five re-entry artifacts in the active spec exist and are
accepted. Once admitted, the plan remains capped at 165 analysis minutes / 180 absolute
minutes and at most five sequences. The accepted sample must contain at least three
sequences from at least two independently hashed packs and at least two distinct DMX
fixture/layout profiles; it sets no maximum pack count or reviewed-window count. Profile
only hash-verified copies inside newly created task-owned scratch; never profile owner
archives in place. Missing isolation, hash equality, path containment, fixture-semantic
join coverage, or curve-decode coverage is an immediate stop. A future result must still
be framed as pursue-now / pursue-later / no, with evidence; the current repository has
no such feasibility verdict.

### Other boundaries that must survive every continuation

- **P3-T4:** two live attempts are sealed and exhausted; `$3.320000` is committed; no
  third attempt is authorized. Offline temperature-capability remediation does not
  reopen the cap or create live acceptance.
- **P3-T7:** the one-shot image proof succeeded and its sealed terminal ledger forbids
  another run. Never rerun it.
- **xLights GUI:** all GUI dates/checks remain deferred until a meaningful, fully
  working end-to-end show exists. Deferral does not waive the empirical gates.
- **P3-T8 / P2P-T6 / P2P-T13:** no real vision judgment, calibration, completed record,
  three-arm result, or D1 verdict may be inferred from offline fixtures.
- **WhisperX/TorchCodec:** optional runtime execution remains owner-deferred and
  unavailable against the current default FFmpeg 9. Do not claim runtime readiness.
- **Repository:** no push was performed. Ask before pushing. Preserve unrelated legacy
  branches and ignored/local state unless the owner explicitly asks to remove them.

### Recommended continuation order

1. Read this section, [context/current-state.md](../../../../context/current-state.md),
   [changes/ACTIVE.md](../../../ACTIVE.md), and the relevant P4-T2/P2K-T2/P4-T7 specs.
2. Obtain the owner's explicit Ollama decision (named-model pull or empirical waiver).
3. If a pull is authorized, record expected download/disk impact before starting, verify
   the model is local, run the one-request smoke once, and independently audit the
   evidence before changing Phase 4 status.
4. If the owner instead supplies real P2K/MH inputs, follow the hardened runbook; keep all
   private outputs outside Git and require independent evidence review before admitting
   P4-T7.
5. Continue non-GUI end-to-end work toward one meaningful fully working show; only then
   schedule the deferred xLights GUI evidence.
6. Before any phase closure, re-audit every phase exit explicitly. Merged tooling is not
   empirical acceptance.

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
| 2K — Catalog growth | **TOOLING IMPLEMENTATION MERGED AND VERIFIED** (4/4); **phase exit not complete** | P2K-T2's Standards+Spec-approved offline owner-run readiness contract is integrated at `03b75e9`. The real owner-corpus run, unchanged-corpus idempotent rerun evidence, non-empty distributions, and exactly eight owner decisions remain open; see [05-phase-2k-catalog-growth.md](05-phase-2k-catalog-growth.md). |
| 3 — Show convergence | **P3-T1–P3-T8 OFFLINE IMPLEMENTATIONS MERGED** (8/8 integrated); **EMPIRICAL EXITS OPEN** | P3-T7 is integrated at `70b3305`; its one-shot image proof passed with one request, zero retry, zero-call cache replay, and `$0.00622` measured cost. P3-T6 is integrated at `c9620db`; its xLights gate remains deferred. P3-T8 is integrated at `82438cf`; preview/live-judge/human/calibration/real-record evidence remains deferred. P3-T4 exhausted two failed audited attempts, `$3.320000` is committed, no third is authorized, and live acceptance remains open. Earlier commits: P3-T5 `f006468`; P3-T4 `558153c`; P3-T3 `33cce57`; P3-T2 `5365f70`; P3-T1 `5eebcb2`. |
| 4 — Compounding | **IMPLEMENTATION IN PROGRESS** (6/7 integrated) | P4-T1 is integrated at `56d9aa0`; P4-T2 is integrated through `3765bd9`/`40e8e55`; P4-T3 through P4-T5 are integrated at `bf6bba5`, `3e7f679`, and `05f24d0`; P4-T6 is independently verified and integrated at `da8f19d`. P4-T2's real Ollama smoke remains unclaimed pending explicit local opt-in. P4-T7's independently approved repository-only preflight is integrated at `c79566e`, but full execution remains optional, incomplete, and NO-GO/deferred pending accepted P2K-T2 owner-corpus evidence and an accepted, sufficient private MH corpus manifest. The preflight is not P4-T7 completion or a feasibility verdict. Exact records: [P4-T2](../specs/phase-4-compounding/P4-T2-local-provider-option.md), [P4-T3](../specs/phase-4-compounding/P4-T3-dead-tail-retirement-wave-1.md), [P4-T4](../specs/phase-4-compounding/P4-T4-duplication-collapse.md), [P4-T5](../specs/phase-4-compounding/P4-T5-dead-config-final-sweep.md), [P4-T6](../specs/phase-4-compounding/P4-T6-documentation-truth-pass.md), and [P4-T7](../specs/phase-4-compounding/P4-T7-mh-idiom-mining-exploration.md). |

The overall `twinklr-reactivation-review` change remains **ACTIVE**. Finishing an
offline implementation lane is not the same as satisfying its phase exit criteria.

### Repository and quality-gate evidence

- Canonical current repository and quality-gate evidence is maintained in
  [context/current-state.md](../../../../context/current-state.md); do not fork its
  rolling snapshot into this execution handoff.
- No implementation or test failure is being carried as an accepted baseline.
- The P3-T8 first offline snapshot was formally rejected. Its remediated candidate on
  `codex/p3t8-evaluation` from `1ecea0c` verifies all completed-record evidence before
  report/join consumption, shares the provider hard-limit preflight with rubric-v1,
  expands contact-sheet grounding ranges, and covers unmatched/non-spanning/ambiguous-
  ownership metrics adversarially. Fresh author gates: rejection core **25 passed**;
  evaluation/CLI/integration focus **163 passed**; immutable goldens **74 passed, 8
  skipped**; full offline suite **5,390 passed, 38 skipped** at 88%; Ruff/format and
  `git diff --check` clean; mypy clean across **737 source files**. Frozen 24-file
  implementation/test/prompt manifest SHA-256:
  `b75fcc9f565cb77888946f8f8da5a0ec4983176d2ef140460ac7584fe2b860a0`.
  Independent review approved this remediated snapshot offline/in code, and it was
  integrated at `82438cf`. No live/provider/xLights/audio work or completed real record
  was created; those empirical requirements remain deferred.
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
  remains open and deferred to the meaningful end-to-end milestone. P3-T7+ and its
  task-bounded live/paid work are authorized.
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
  before a call, enforces one request per attempt and now two attempts total, applies a
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
- The owner-authorized second-attempt amendment raises the cumulative P3-T4 hard cap to
  exactly `$3.32`: attempt 1's committed `$1.660000` plus exactly one additional
  `$1.660000` preauthorization. It binds authorization
  `p3-t4-second-attempt-owner-approved-2026-08-26` to the preserved HMAC-sealed ledger,
  prior unsigned-ledger hash `97c38f6c...babcdc`, and prior-attempt hash
  `29802ebe...3b562`. Missing/reset/tampered history fails closed; no third attempt is
  authorized regardless of outcome or metered cost.
- Missing, zero-default, partial, inconsistent, or out-of-bound token usage never releases
  an attempt's `$1.66` reservation; it is recorded as unavailable.
- Attempt 1 had no trustworthy usage, so its full `$1.660000` reservation is permanently
  committed. The canonical owner-local ledger and attempt-1 object must remain unchanged.
  The amendment atomically sealed its authorization and in-progress attempt 2 and
  required a clean committed source manifest before the call.
- Attempt 2 made exactly one provider request. OpenAI returned HTTP 400
  `invalid_request_error` because `temperature` is unsupported by `gpt-5.6-sol`. There
  was no retry, JSON-object fallback, logical request, schema repair, response metadata,
  or usage. Its full `$1.660000` reservation remains committed; cumulative reserved and
  committed spend is `$3.320000`. The two-attempt cap is exhausted, no third attempt is
  authorized, and live acceptance remains open.
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
- The pre-execution second-attempt amendment candidate had fresh offline author evidence:
  adversarial harness `50 passed`; broader planning/provider/schema regression `408
  passed`; full suite `5365 passed, 38 skipped`; `1361` files already formatted; Ruff
  clean; mypy clean across `731` source files; and `git diff --check` clean. No
  provider/network/live call was made by those gates.
- Independent review rejected amendment candidate `f0557b9`: its clean-manifest
  preflight excluded untracked files, allowing a root `sitecustomize.py` or a file under
  a transitive source root to bypass the gate. Two discriminators failed before the fix
  and pass after changing the preflight to `--untracked-files=all`. The rejected commit
  is preserved as audit history; its pins are invalid for execution. No provider/live
  call or canonical-ledger mutation occurred. Fresh remediation gates and pins must be
  recorded from the follow-up clean commit before independent re-review.
  Fresh remediation author gates are harness `52 passed`, full offline suite `5367
  passed, 38 skipped`, `1361` files already formatted, Ruff clean, mypy clean across
  `731` source files, and `git diff --check` clean.
- Post-call offline root-cause remediation centralizes optional OpenAI generation
  parameters in one explicit model-capability policy used by runner dispatch, provider
  requests, serialized probe evidence, and probe identity. `gpt-5.6-sol` omits
  temperature while retaining reasoning effort; known temperature-supporting models
  keep configured temperature. Unsupported-parameter HTTP 400 remains terminal with one
  provider request even when retry/fallback settings are enabled. TDD red evidence was
  captured independently at the provider, runner, and probe identity seams. No
  provider/network/live call or canonical-ledger mutation occurred during remediation,
  and it cannot reopen the exhausted attempt cap. Fresh gates: focused `149 passed`;
  full offline suite `5373 passed, 38 skipped`; `1362` files already formatted; Ruff
  clean; mypy clean across `732` source files; and `git diff --check` clean.

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

1. Preserve P3-T4's sealed two-attempt ledger and permanent no-third-attempt boundary;
   do not infer live acceptance from the offline provider-capability fix.
2. Preserve P3-T7's terminal sealed one-shot ledger and accepted proof evidence; never
   rerun the image proof. Continue only through later tasks' separately audited caps.
3. Continue non-GUI end-to-end work toward one meaningful fully working show. Defer all
   xLights GUI dates/checks until that milestone; deferral does not satisfy or waive them.
4. Complete the P2P-T6/P2P-T13 and Phase 2K owner-data protocols when their prerequisites
   are met. Record no empirical outcome without its evidence.
5. Reassess Phase 1P, 2P, 2K, and Phase 3 exits explicitly; do not mark a phase complete
   merely because its code/tooling is merged.

P3-T1/P3-T2/P3-T3 are complete and independently verified. P3-T4's owner-approved
contract/invariants, AC2 amendment, and general schema remediation were independently
approved offline/in code and integrated at `558153c`. Both audited live attempts failed
safely; attempt 2 was HTTP 400 unsupported `temperature` with one provider request and
no retry/fallback/schema repair/usage. `$3.320000` is committed, the two-attempt cap is
exhausted, live acceptance remains open, and no third attempt is authorized. P3-T5's nine
decisions are owner-accepted and its offline candidate is integrated at `f006468` while
the earlier empirical exits remain open. P3-T6 is independently approved offline/in code
and integrated at `c9620db`; its empirical GUI acceptance is open and deferred until a
meaningful end-to-end show is fully working. P3-T7's independently approved code and
P3-T8's independently approved offline evaluation code are integrated. P3-T7's one-shot
asset proof passed; P3-T8's GUI/live/human evidence remains deferred. P3-T7+ and
task-bounded live/paid work are authorized. P3-T2 deliberately leaves
`resolved_color`, `timing_offset_beats`, and parameter-range/settings escaping work to
their existing P3-T5/P3-T8 or display-review owners; it does not silently close them.

Phase 4 work has started under the owner's P3-T7+ authorization. P4-T1 is independently
approved and integrated at `56d9aa0`; P4-T2's implementation and redirect-hardening
remediation are integrated through `3765bd9`/`40e8e55`; and P4-T3's independently
verified remediation is integrated at `bf6bba5`. P4-T4 is independently verified and
integrated at `3e7f679`; P4-T5 is independently verified and integrated at `05f24d0`;
and P4-T6 is independently verified and integrated at `da8f19d`, bringing Phase 4 to
six of seven tasks integrated. P4-T7 full execution is NO-GO/deferred pending P2K-T2's
owner-corpus empirical exits and an accepted, sufficient private moving-head corpus
manifest. Its independently approved repository-only preflight is integrated at
`c79566e`; the preflight is not completion and makes no feasibility verdict. P4-T2's
real Ollama schema smoke remains unclaimed pending explicit local opt-in. Optional
WhisperX/TorchCodec runtime execution remains deferred and unavailable against the
default FFmpeg 9.

P4-T5's first freeze candidate `607bf19` was independently rejected: it used generic
fingerprint/smoke pointers instead of per-field effects, collapsed union alternatives,
silently ignored representative removed keys, and overstated its handoff. The next
candidate, based on P4-T4 integration `3e7f679` and implemented through `be4abba`,
`a942820`, `5526c23`, and freeze record `a2fe16e`, was also independently rejected. It
incorrectly deleted live fixture position offsets and pose-safety behavior, timeline
section gating, and template aim-zone metadata. Remediation `d95f675` restored those
public behaviors with exact per-path tests, and `ffc7dae` recorded a fresh `5591 passed,
39 skipped` freeze, but independent verification rejected that freeze too: the registry
redeclared eight restored dispositions in a trailing override loop, and
`FixtureConfig.is_pose_safe` checked already-clamped DMX values, making its limit checks
ineffective.

Source remediation `18e5d1c` removes the duplicate override declarations while preserving
the eight canonical exact node IDs, and evaluates raw mapped DMX values before output
clamping. A red-first public `FixtureConfig.is_pose_safe` discriminator proves an
out-of-limit raw pose is unsafe even though `degrees_to_dmx` clamps emitted output; the
existing base/instance `avoid_backward` discriminators remain green. The generated
registry continues to enumerate the external `AppConfig`, `JobConfig`, `FixtureGroup`,
and `TemplateDoc` roots by canonical full path and collects every cited pytest node.
Fresh source-remediation gates: focused config/registry `260 passed`; `1352` files already
formatted; Ruff clean; mypy clean across `719` source files; full suite `5592 passed,
39 skipped`; and `git diff --check` clean. No provider, network, live, GUI, or paid call
occurred. Documentation-inclusive refreeze `ce1d9d4` was then independently rejected
because this handoff still reported Phase 4 as three of seven and omitted integrated
P4-T4, while the registry protected exact dispositions by matching test-nodeid
substrings. The final author remediation reported Phase 4 truthfully as four of seven
with P4-T5 pending review, protected an explicit set of all eight canonical config paths,
and pinned every path's final exact node ID. Fresh focused config/registry evidence is `261
passed`; Ruff and `git diff --check` are clean. Independent verification approved the
final remediation, which is integrated at `05f24d0`. The current combined-main gate is
single-owned by [context/current-state.md](../../../../context/current-state.md).

P4-T6 candidate `827c8b6` completed the documentation truth pass and full validation but
was independently rejected for one residual stale label in `docs/user-guide.md`: the
moving-head loop still said `planner -> validator -> judge`. The author remediation
changes that exact wording to `planner -> deterministic heuristics -> judge` and adds a
document-contract regression assertion. The replacement candidate remains pending
independent re-verification and is not integrated.

The remediation audit also aligns `context/INDEX.md` with the heuristic loop, makes the
README distinguish installable optional ML dependencies from the still-deferred and
FFmpeg-9-unavailable WhisperX/TorchCodec runtime, and replaces the user guide's stale
credential/fixture line-number citations with stable symbol references. Regression
assertions protect these statements and cited Python paths.

Author remediation is committed at `6dbf4fa`; its fresh scoped gate is 54 documentation/
model contract tests passing, Ruff `--no-cache` clean, stale/current phrase assertions
clean, zero missing changed-document links, and `git diff --check` clean. The prior full
gate remains applicable because no product source changed. Independent re-verification
approved the remediation, and P4-T6 is integrated at `da8f19d`. The combined-main gate
is single-owned by [context/current-state.md](../../../../context/current-state.md).

P4-T7 then received a safe, read-only prerequisite preflight only. P2K-T2's tooling is
integrated, but its real owner-corpus run, idempotent rerun evidence, non-empty empirical
distributions, and owner-authored threshold decisions remain open. A filename-only scan
found no accessible moving-head corpus manifest or sequence archive in the inspected
local paths. Full P4-T7 execution is therefore **NO-GO / deferred** until those empirical
exits are accepted and a manifest identifies a sufficient accessible MH corpus. No
corpus content was opened, parsed, or mined; this is not P4-T7 completion or a
feasibility verdict. The subsequent repository-only preflight corrected the unsupported
vendor-history premise, pinned five exact re-entry artifacts, and documented a
hash-verified isolated-scratch plan. Independent review approved that prerequisite and
it is integrated at `c79566e`. This approval does not admit or complete P4-T7; the task
remains optional, incomplete, corpus-gated, and NO-GO/deferred.

P2K-T2 offline owner-run readiness candidate `64ce517` was formally rejected on both
independent axes: evidence/contract correctness and implementation-quality/safety. Its
earlier frozen/gate claims below are historical evidence for the rejected candidate, not
current approval. This is tooling readiness only: no
owner corpus, private manifest, network, provider, live catalog, or paid service was
accessed. The real-corpus run, identical rerun, non-empty distributions, completed owner
decisions, and P4-T7 feasibility work remain open.

The remediation makes the owner path fail closed: it requires an explicit unified corpus,
an explicit music-index-or-none declaration, and a new dedicated output directory; a
rerun is allowed only when the previous manifest owns the same path and input fingerprint.
The mining manifest binds corpus/profile/lineage/music/tool/Git provenance plus stable
feature-store entity-key/content digests and rejects duplicate logical/content identity.
Threshold review requires the verified unchanged rerun, raw phrase/role/cluster evidence,
and live-catalog immutability. Eight retained numeric values each receive the configured
and two nearby sensitivity points; the dead anti-affinity literal is removed. Final
`--bind-owner-decisions --accepted-on YYYY-MM-DD` validation consumes a strict JSON
decision record with exactly one typed, dated decision and rationale per value. It checks
the mining-time staged snapshot and current hashes for the mining manifest, candidates,
reports, and promotion evidence before emitting accepted P2K evidence. The owner-local MH
validator then emits one redacted aggregate document binding that accepted P2K evidence
hash with the MH sufficiency declaration.

Fresh author evidence before the documentation-only freeze record: focused owner-run/MH/
threshold suites `20 passed`; related style/promotion/role suites `37 passed`; Ruff
`--no-cache` clean; focused mypy clean across eight source files; `git diff --check` clean;
and full pytest `5617 passed, 39 skipped` with 43 existing resource warnings. The
subsequent clean-tree `make validate` also passed: `1358` files unchanged by formatting,
Ruff clean, mypy clean across `720` source files, and `5617 passed, 39 skipped` with the
same 43 resource warnings. The rejected candidate was not self-approved or integrated.
The replacement remediation requires fresh independent verification after its own clean
freeze.

Replacement author implementation commit `9059ff7` remediated all six formal blockers;
both independent review axes approved its documentation freeze `86e1a6b`. After approval,
the replacement was rebased onto exact `main` base `bc7e270`; rebased implementation
commit `9536206` preserves the approved behavior, and the following documentation-only
commit records the new freeze. The sole logical conflict preserved all repository-preflight
identities/history and its incomplete/NO-GO boundary while adding the approved combined
P2K+MH evidence binding.

Fresh rebased evidence is `41 passed` across the strict evidence, output-safety,
distribution, MH, and owner-command integration suites; changed-document relative links,
`git diff --check`, Ruff, and focused mypy are clean. The clean-tree repository gate passed
with formatting unchanged across `1361` files, Ruff clean, mypy clean across `721` source
files, and `5637 passed, 39 skipped` with 43 resource warnings. The disposable worktree's
undeclared optional Anthropic extra was removed before this gate so it matched the declared
development environment; no provider source was changed. Independent Standards and Spec
review approved the rebased replacement, including the superseding
exactly-eight-decision clarification, and it was fast-forward integrated on `main` at
`03b75e9`. None of the owner-data empirical exits were executed or claimed: the real
owner-corpus run, unchanged-corpus idempotent rerun evidence, non-empty distributions,
and exactly eight owner decisions remain open. P4-T7 remains optional, incomplete, and
NO-GO pending accepted P2K evidence plus an accepted, sufficient private MH corpus
manifest.

## Binding orchestration rules

- Use executor/verifier separation; an author never approves their own work.
- Workers do not run git state or mutation commands. The orchestrator owns integration.
- Verify from a worktree-local synced environment; shared editable installs can point at
  the wrong checkout.
- Use Ruff with `--no-cache` when a count matters.
- Acceptance metrics must discriminate on a pre-fix or adversarial case.
- Golden changes use only the explicit regeneration path and require hunk attribution.
- Owner judgment, paid/live calls, calibration, and local data are never fabricated.
