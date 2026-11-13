# P5 Evidence and Release Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Establish which output, physical-behavior and authoring-value claims the
moving-head changes actually support, and keep unproven capabilities opt-in.

**Architecture:** Add a purpose-specific evidence manifest and frame comparator beside
existing evaluation utilities. Compare independently specified synthetic expectations,
Twinklr commands and xLights-rendered frames; keep fixture observations and blinded
human studies as separately attributed evidence. Preserve the existing three-arm
experiment and whole-file FSEQ comparator unchanged.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest, standard-library binary reading;
the upstream `fseq_convert` tool only for explicitly prepared offline evidence.

**Spec:** [Shared contracts](architecture.md), [report P5](../report.md#phase-p5--validate-the-product-claims-and-decide-what-to-ship).

## Global constraints

- Python 3.13 only; uv workspace; Pydantic V2 for public/LLM-facing data.
- `legacy_v1` remains the default; physical behavior changes require explicit opt-in.
- The emitted effect grid remains 20 ms; timing markers remain source-exact.
- No evaluation run, provider spend, owner-data access or hardware/show operation is
  authorized by writing this plan. Missing observations stay `PENDING-OWNER`.
- Never rewrite an accepted golden or fixed experiment protocol to make a new arm pass.
- Follow all [shared requirements](architecture.md#1-goals-and-boundaries).

## Review focus

1. Encoder and expected-value generator sharing the same bug — T2 uses handwritten
   vectors and independently rendered frames, including deliberate corruptions.
2. Correct local channel offsets compared against the wrong universe/model patch —
   T1/T2 validate an explicit global mapping and unequal channel values.
3. Motor-command derivatives presented as actual physical motion — T3 keeps measured
   arrival and command estimates separate; unknown measurements cannot pass.
4. Attractive sampled video hiding one bad 20 ms frame — T2 checks every frame;
   contact sheets are review aids only.
5. Failed runs or unfavorable preferences disappearing from results — T3/T4 retain
   all preregistered case IDs, failures and unavailable evidence.

## Technical design

### Existing seams and bounded source extension

[Current FSEQ comparison](../../../packages/twinklr/core/api/xlights/fseq.py) compares
whole-file bytes and does not parse frames. Keep that public function unchanged.
[Physics diagnostics](../../../packages/twinklr/core/reporting/evaluation/physics.py)
estimate motion from normalized values and configured nominal limits; they cannot
establish actual arrival. [Preview sampling](../../../packages/twinklr/core/reporting/evaluation/vision_frames.py)
is too sparse for channel correctness. Existing
[xLights acceptance tests](../../../tests/golden/test_xlights_acceptance.py) check
import/settings behavior; they are not the new rendered-channel oracle. The frozen
[three-arm experiment](../../../packages/twinklr/core/reporting/evaluation/three_arm.py)
owns its particular arm definitions, thresholds and preconditions. Reuse ordinary
utilities where appropriate, not its protocol under changed meanings.

New `mh_frame_evidence.py` reads **uncompressed, nonsparse FSEQ v1.0 only**, after
validation. xLights' pinned [FSEQ reader/writer](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/src-core/render/FSEQFile.cpp)
defines little-endian `PSEQ` header fields: data offset at byte 4 (u16), minor/major
at 6/7, fixed-header length at 8 (u16), channel count at 10 (u32), frame count at
14 (u32), and frame interval at 18 (u8); v1's fixed header is 28 bytes. Validate
header size, version, offset, channel/frame counts and payload length before reads.
Read rows by seeking/streaming; do not materialize a show-wide matrix. Unsupported
version, malformed/truncated input or 20 ms cadence mismatch raises a typed error.
Declare a 2 GiB input limit and 65,536-channel limit for this pilot; reject larger
inputs explicitly instead of silently truncating. These are evidence-tool bounds,
not claims about FSEQ or xLights limits.

For compressed **nonsparse** source evidence, use the upstream
[converter](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/fseq_convert/fseq_convert.cpp)
as a separate, recorded preprocessing operation:

```bash
fseq_convert -i rendered.fseq -o rendered-v1.fseq -f 1 -n
```

Pin converter revision, command, input and output hashes. The comparator never runs
it or xLights implicitly. The pinned converter chooses its default output channel
count from the packed source count; `-n` alone does **not** safely expand all sparse
channel positions. Reject sparse sources for this pilot rather than applying this
recipe to them. Obtain a fresh nonsparse render or separately validate a future
explicit-range conversion with a high-offset sparse counterexample.

At this pinned revision the metadata-printing branch checks `-f`, despite declaring
`-j` as the JSON option. The read-only command `fseq_convert -i rendered.fseq -f 1`
(no `-o`) prints source metadata. Record its JSON object and source hash; v2 input
must have empty `SparseRanges`, the correct channel extent and 20 ms `StepTime`.
If source metadata is absent, contradictory or sparse, conversion evidence is
unavailable rather than trusted. The evidence adapter checks the prepared v1 header
against recorded source `NumFrames`, `ChannelCount` and `StepTime` before comparison.

A native-backend experiment compares both independently
rendered outputs against the known intended channels; matching two wrong streams
is insufficient. No general FSEQ parser, compression codec or new live controller
is in scope.

### Evidence contracts

Proposed models in `reporting/evaluation/mh_true_up_models.py`:

- `MHStudyManifest(schema_version='mh-study.v1', study_id, purpose, cases, arms,
  input_hashes, software_versions, protocol_hash, authorization_refs, thresholds)`.
  Purpose is `transport`, `physical_trial`, `creative_review`, or `authoring`.
  Case IDs, arms, thresholds and exclusions are fixed before the run; amendments
  create a new protocol hash with a reason. Absence of authorization permits only
  synthetic/offline inputs. A reference is a record locator, not invented approval.
- `FixtureChannelPatch(fixture_id, offsets_to_fseq: dict[int,int])` maps one-based
  model-relative offsets to **zero-based absolute FSEQ channel indexes**. Require
  every declared fixture offset, unique output ownership and indexes in range.
  It comes from the exact synthetic show patch, not guessed universe arithmetic.
- `FseqConversionRecord(source_path, source_hash, source_metadata, converter_revision,
  command, output_hash)` retains the upstream metadata described above. Implement
  `validate_prepared_fseq(path: Path, conversion: FseqConversionRecord | None) -> None`:
  direct v1 evidence needs no conversion record; converted evidence must provide one,
  verify both file hashes, reject nonempty sparse ranges and compare source/output
  frame count, channel count and interval. The manifest explicitly declares whether
  evidence is direct or converted; it cannot omit the record for a converted file.
- `EvidenceResult(case_id, arm_id, kind, status, metrics, artifact_hashes, reason)`:
  status is `pass|fail|pending|unavailable`; metrics use explicit units and nullable
  values, never zero for absent data. Preserve failure records in aggregates.
- `FixtureObservation(case_id, fixture_id, command_identity, fixture_model, mode,
  profile_hash, observed_at, observer, arrival_error_ms, settle_ms,
  unintended_lit_travel, timing_uncertainty_ms, method, evidence_refs)` stores
  externally observed values. Unknown values remain null; observer/source fields
  are mandatory for a measured claim.
- `HumanJudgment(case_id, presentation_id, reviewer_id, criterion_scores,
  preferred_presentation, comments, recorded_at)` and
  `AuthoringObservation(case_id, arm_id, active_seconds, correction_count,
  regeneration_count, accepted_by, retained_locked_fraction, evidence_refs)` are
  imported observations, never generated by a language model.

`read_fixture_frames(path: Path, patches: Sequence[FixtureChannelPatch], *,
expected_frame_ms: int=20) -> Iterator[EncodedFixtureFrame]` uses P1's frame type,
yielding stable time/fixture order after `validate_prepared_fseq`. It does not call the encoder. `compare_frames(
expected: Iterable[EncodedFixtureFrame], actual: Iterable[EncodedFixtureFrame])
-> FrameComparison` compares coverage, timing and all declared bytes, reporting
counts plus the first 100 mismatches and a hash of the full streamed difference.
Missing frames or channels are failures, not zeros.

### What is compared and what passes

| Claim | Required evidence and proposed gate |
|---|---|
| Exact channel transport | Every expected byte at every frame equals independently rendered xLights output; zero mismatches/missing frames |
| Resolution/mapping | Handwritten coarse/fine carry, endpoint, inversion and nonadjacent-channel vectors; continuous round-to-nearest error ≤0.5 LSB plus floating-point epsilon before physical interpolation error |
| Cue timing | Ordinary aligned cues differ from requested times by ≤10 ms; dark/settle scheduling satisfies its outward-rounded feasibility contract even when musical timing conflicts |
| Dark reposition | Every frame reserved for reposition/settle is dark under declared semantic visibility rules; intentional illuminated effect movement is excluded from this metric |
| Locks | Zero changed mapped bytes in locked intervals, including fine bytes; exact signatures where P4 promises direct effect retention |
| Unsupported input | Zero silent capability drops or unreported substitutions; intentional fallback counts and reasons remain visible |
| Physical arrival | Dated fixture-specific observation with clock uncertainty; selected profile's arrival/settle tolerances must be declared before the trial; no universal default tolerance |
| Authoring benefit | Proposed pilot target: ≥20% lower paired median active edit time with no correctness regressions; report every pair, failures and human acceptance |

The authoring target is a product hypothesis, not an existing requirement or empirical
result. Before an authorized pilot, the owner accepts/amends it in the manifest.
Command speed/acceleration summaries are diagnostic only unless a separately
measured physical model supports the inference. Source defaults never become
calibration evidence. If video timing uncertainty exceeds the declared arrival
tolerance, the observation is inconclusive, not a pass.

Use P0's synthetic matrix for transport. Exercise 1/2/3/4/6/8 heads, channels17/48/49,
coarse/fine carries, missing heads, variable tempo/3-beat meter, finite cutoffs,
unknown initial states and locked transition boundaries. Include negative cases
that must fail before emitting any partial output. Measure sequence bytes,
effect count, render duration and peak memory for 30 s and 4 min synthetic cases
at 2/8 heads; P1's declared output budget decides admission, not an after-the-fact
performance claim.

Use three separate comparison purposes:

1. **Transport:** identical physical intent and patch, compare command/DMX/native
   supported subsets. Legacy cannot be forced to express new fine-resolution intent.
2. **Creative:** legacy Twinklr, P0 `reference_legacy_v1`, and proposed Twinklr on
   identical authorized song/rig conditions. P3's arrangement reference is a separately
   named additional arm when relevant. Retain each arm's actual capability limits.
3. **Authoring:** identical stated revision tasks with permitted differences and
   locked regions; measure active work to owner acceptance, corrections and retained
   work. Randomize/counterbalance presentation and workflow order.

Proposed exploratory pilot: at least eight song/rig cases covering quiet, rhythmic,
build/drop and recurring-phrase material, with two contrasting rig configurations
represented. Choose and record cases before seeing outputs. Human criteria: motif
recognition, phrase contrast, restraint, focal clarity, visible transition artifacts
and overall preference. Blind arm labels for visual review; retain the random seed
and reveal mapping after judgments. Report paired medians and individual cases,
not a market-wide superiority or significance claim from this small pilot.
Competitor workflows are separate descriptive comparisons when their inputs/output
constraints differ. Failure to complete a case remains a failure with its time cost.

## Implementation tasks

### P5-T1 — Typed study manifests and bounded rendered-frame evidence

**Files:** Create `packages/twinklr/core/reporting/evaluation/mh_true_up_models.py`,
`mh_frame_evidence.py` in that directory; create
`tests/unit/reporting/evaluation/test_mh_frame_evidence.py` and
`test_mh_study_models.py` in its corresponding test directory. Preserve
`api/xlights/fseq.py` and existing comparison tests unchanged.

**Interfaces:** Produce the models and `read_fixture_frames` defined above; consume
P1 `EncodedFixtureFrame`. No other P2–P4 production dependency is needed.

- [ ] Write handcrafted binary-header tests with two frames and unequal bytes:
  coarse/fine mapped to offsets 1/4, FSEQ indexes 3/6; require exact reconstructed
  `(time_ms,fixture_id,channels)` at 0 and 20 ms without invoking the production encoder.
- [ ] Add truncated payload, unsupported major2, wrong cadence, invalid/duplicate
  mapping and null-observation tests; all reject or preserve unknown as specified.
  Include a conversion record with a sparse range at an absolute offset above its
  packed channel count: reject it even if the resulting v1 file is structurally valid.
  Missing source metadata or mismatched source/output frame counts also rejects.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_mh_frame_evidence.py tests/unit/reporting/evaluation/test_mh_study_models.py -q`;
  require failures for missing interfaces, then implement bounded streaming and models.
- [ ] Rerun those tests plus `uv run pytest tests/unit/api/xlights/test_fseq_compare.py -q`;
  expect all pass with old whole-file comparison behavior unchanged.
- [ ] Independent review checks header offsets against pinned upstream; integrator
  commits `feat(mh): add bounded rendered-frame evidence and study contracts`.

### P5-T2 — Independent transport and invariant comparisons

**Files:** Create `packages/twinklr/core/reporting/evaluation/mh_true_up.py` and
`tests/unit/reporting/evaluation/test_mh_true_up.py`; create
`tests/integration/test_mh_transport_evidence.py`. Extend P0 synthetic test support
only through the designated integrator.

**Interfaces:** `compare_frames` above and `evaluate_transport(manifest:
MHStudyManifest, expected: Iterable[EncodedFixtureFrame], actual:
Iterable[EncodedFixtureFrame]) -> tuple[EvidenceResult,...]`; emit data, not a pass
based on caller-provided booleans. Physical/creative observations are separate inputs.

- [ ] Write a known vector of words `[255,256,257,65535]`, inverted complements,
  shutter closed64/open8 and defaults on every footprint offset. Compare handwritten
  expected bytes to emitted settings and separately to a prepared FSEQ fixture.
- [ ] Deliberately corrupt one fine byte, one frame timestamp, one mapped patch
  index and one locked byte; assert each fails with the right location. Test a
  dimmer-zero frame versus a closed-shutter frame against their declared semantics.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_mh_true_up.py tests/integration/test_mh_transport_evidence.py -q`;
  observe discriminating failures, then implement comparisons and invariant counters.
- [ ] Rerun; require repeatable results and separate unsupported/pending states.
  Record future scratch-render steps and exact artifacts needed; do not invoke live
  xLights from default unit/integration tests.
- [ ] Reviewer checks oracle independence; integrator commits
  `feat(mh): compare rendered transport and locked-frame invariants`.

### P5-T3 — Observation import and paired review protocol

**Files:** Create `packages/twinklr/core/reporting/evaluation/mh_study.py` and
`tests/unit/reporting/evaluation/test_mh_study.py`; add the executed protocol/evidence
record under this change's future `evidence/` directory when authorized.

**Interfaces:** `build_blind_presentations(manifest: MHStudyManifest, *, seed: int)
-> tuple[BlindPresentation,...]` returns case/presentation IDs and a separately
stored arm mapping; `summarize_study(manifest: MHStudyManifest, observations:
Sequence[FixtureObservation | HumanJudgment | AuthoringObservation]) -> StudySummary`
returns per-case coverage, comparisons, failures and unavailable claims.

- [ ] Write `test_presentation_order_is_seeded_and_labels_blinded`,
  `test_missing_case_is_retained_pending`, `test_measurement_uncertainty_blocks_arrival_claim`,
  `test_failed_authoring_case_is_not_dropped`, and
  `test_protocol_change_requires_new_identity`. Use invented synthetic test records
  explicitly marked test data, never evidence of human acceptance.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_mh_study.py -q`;
  require failure, then implement imports, deterministic assignment and paired summaries.
- [ ] Rerun; require correct coverage and medians. Hand-author the future pilot
  manifest with empty authorization/observation fields clearly pending; no requests
  or collection occurs as a side effect.
- [ ] Reviewer checks failed-case handling and claim scope; integrator commits
  `feat(mh): record blinded review and authoring-study evidence`.

### P5-T4 — Read-only report generation and feature-level release gates

**Files:** Create `packages/twinklr/core/reporting/evaluation/mh_true_up_cli.py` and
`tests/unit/reporting/evaluation/test_mh_true_up_cli.py`; produce JSON/Markdown
reports under the run's ignored artifact directory. Update accepted context/docs
only after actual owner adoption, using the repository closeout workflow.

**Interfaces:** `write_study_report(summary: StudySummary, output_dir: Path)
-> tuple[Path,Path]`; module CLI
`uv run python -m twinklr.core.reporting.evaluation.mh_true_up_cli report --manifest PATH --evidence DIR --output DIR`.
This reads prepared evidence and writes reports; it never triggers providers,
conversion, rendering or hardware. Exit0 means report generation succeeded, not
feature acceptance; JSON exposes each gate's `pass|fail|pending|unavailable` status.

- [ ] Write `test_missing_evidence_remains_pending`, `test_cli_has_no_live_side_effects`,
  `test_failure_and_negative_judgment_are_reported`, and
  `test_native_backend_cannot_pass_without_rendered_parity`.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_mh_true_up_cli.py -q`;
  verify failures, then implement deterministic report output and feature gates.
- [ ] Rerun; independent review verifies every claim links its dated/hash-identified
  evidence, with no aggregate score concealing a hard correctness failure.
- [ ] Integrator commits `feat(mh): report evidence-backed moving-head release gates`,
  runs fresh clean-tree `make validate`, and records actual results.
- [ ] Once separately authorized studies exist, record owner decisions per feature:
  retain opt-in, ship as supported, or revise. A default change requires its own
  migration/rollback decision; do not change defaults in this evaluation task.

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; see the
[shared rule](README.md#documentation-registry-and-test-surfaces). Recheck at P5 kickoff.

- **No config inventory change is planned.** P5's models are study and evidence
  records, not fields on the four inventoried config roots. If a task adds one anyway,
  the shared rule applies.
- **Existing guards.** `tests/unit/api/xlights/test_fseq_compare.py` and
  `tests/unit/reporting/evaluation/test_three_arm_experiment.py` pin the whole-file
  comparator and the frozen experiment; P5-T1 and P5-T2 run them unchanged.
- **Documents.** P5-T4's own rule stands: accepted context and docs change only after
  owner adoption. Until then the report command is documented by its `--help` and this
  change's records. On adoption it is added to `docs/user-guide.md` beside the
  existing FSEQ comparison section, stating that exit 0 means the report was written,
  not that a feature was accepted. Executed studies with human judgment are recorded
  under `evaluations/` per its README, not only in this change folder.

## Exit, limitations and rollback

The harness can complete on synthetic/offline evidence while fixture and taste
claims remain pending. A feature cannot be called physically validated without
its fixture record or product-improving without its human/authoring evidence.
Native/GDTF/Blender experiments retain separate decisions; a NO-GO does not conceal
core feature failures or block unrelated supported features. Unsupported runtime
versions and measurement limits are listed with affected claims.

Rollback excludes the proposed feature/policy from admission and preserves its
evidence, including negative results. No regeneration of accepted goldens, change
to frozen experiment arms, automatic provider rerun or deletion of a failed study
is part of rollback.
