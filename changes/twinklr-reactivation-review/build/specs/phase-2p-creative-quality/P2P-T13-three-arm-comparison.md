# P2P-T13 — Three-arm comparison

Phase: 2P (Creative Quality, Measured) · Lane: Finale (after ALL lanes) · Executor: opus · Verifier: opus (+ owner reads verdict) · Depends on: P2P-T1..T12 (all lanes merged)

⚖ **Owner-decision-bearing — this is the task the phase exists to reach.** The owner
reads the verdict and the human spot-checks, and the outcome is recorded in the
reactivation proposal and a decision record. The executor runs the protocol; it does
not choose the criteria, which are fixed below.

## Objective

Build the deterministic selector arm, run all three arms over the song set, score
every run with P2P-T6's harness, take human spot-checks, and record the D1
standing-default verdict. This is the evidence that decides how much of the planning
job the LLM keeps.

## Evidence & background

Findings: **D1**, **CF-3**, **Stage 2 §4** (deterministic-selector observation),
**P4 §10 / V3** (the annotation table — annotations verified populated and
discriminating), **P3-F14** (`recommended_sections` withheld from the LLM),
**P4-F8** (preset space ≈67), **P4-F1** (all movement rendered SMOOTH),
**P3-F24 / P1-F27** (token figures wrong), **P3-M-A** (judge-strictness arm would
compare identical configs), **P3-M-B** (`max_iterations=0` crashes).
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D1,
D11, §5; `.../reviews/phases/moving-heads-rendering.md` §10;
`.../reviews/phases/llm-agents-and-planning.md` §6, §11.1;
`.../reviews/verification.md` "Phase 3", "Phase 4".

### D1 — the standing-default language, VERBATIM

Copy this sentence into the decision record and the proposal update, unaltered:

> **D1 — LLM's role in section planning** *(unchanged)*: widen the channel, with the
> deterministic selector built as baseline/fallback/regression arm; standing default
> if blind evaluation shows parity.

And the plan-change trigger it maps to, also verbatim (§5, "What would change the
plan"):

> D11 scores + spot-checks showing deterministic parity (D1 default flips —
> absorbed)

**Read precisely.** "Standing default if blind evaluation shows parity" means the
deterministic selector becomes the default when the arms are *indistinguishable* —
parity favours the deterministic arm. The LLM arm keeps the default only by being
*better*, not by tying. The evaluation must be **blind**: the human spot-checker does
not know which arm produced which sequence.

### Preconditions — the experiment is invalid without these

The review is explicit that this comparison could not have been run before certain
fixes. Verify each has merged before running anything:

1. **P4-F1 and P4-F8** (Phase 1P, T3 and T5). From §10:
   > the A/B experiment Stage 2 proposes cannot distinguish the arms until P4-F1 and
   > P4-F8 are fixed — both arms currently render through the same two-outcome preset
   > bottleneck.
2. **P3-F5, P3-F7, P3-F14** (this phase, T4 / T9 / T1). From §11.1:
   > P3-F5 (planner blind to lyrics), P3-F7 (judge blind to its own history), and
   > P3-F14 (`recommended_sections` withheld) mean the current system is not a fair
   > representative of "LLM-driven planning". Stage 2's resolving experiment should run
   > *after* these three fixes, or its LLM arm measures a broken configuration.
3. **P3-F24** (P1P-T9): per-arm token/cost figures are wrong until per-call usage is
   threaded out. "cost comparison is blocked".
4. **P3-M-A** (P2P-T9): a judge-strictness arm "would compare two identical
   configurations and report a null result that means nothing".
5. **P3-M-B** (P2P-T9): `max_iterations=0`, the knob the macro-ablated arm wants,
   crashes at its documented value.
6. **A cache confounder** (fingerprint addendum): "min_pass_score is in planner keys
   yet behaviorally inert (M-A) — a threshold change forces full uncached re-plans
   that cannot differ (experiment confounder)." After T9 wires the threshold this is
   resolved; confirm it.

**If any precondition is unmet, stop and report.** Running early produces a number
that looks like evidence and is not.

### The deterministic selector's data — verified discriminating (P4 §10 / V3)

The selector is buildable on the annotations as they stand:

> **Population: 37/37 complete.** Every template has a non-empty `energy_range`,
> `recommended_sections`, and `tags`. Zero sparse or missing annotations. Category
> distribution: 9 LOW / 18 MEDIUM / 10 HIGH.

> **Discrimination — section join.** 12 distinct section labels; the join is genuinely
> partitioning, not degenerate: verse 17, chorus 14, drop 11, build 8, peak 6,
> bridge 6, intro 5, breakdown 2, groove 2, outro 2, ambient 1, lift 1.

> **Discrimination — energy join.** Coverage is continuous and well-shaped across
> 0–100: 5 templates match at energy 10, 10 at 30, 19 at 50, 12 at 80, 6 at 100.
> Energy 0–4 has zero matches (a trivial gap; the lowest `energy_range` floor is 5).
> Combining `recommended_sections ∩ energy_range` narrows a typical
> `(chorus, energy=70)` query to a handful of candidates.

## Current behavior

No comparison has ever been run. No evaluation result has ever been committed
(SF-4). "nothing in this codebase records a single human judgment about output
quality, so 'comparable choreography' has no measurable meaning yet."

## Target behavior

### 1. The deterministic selector arm

A pure-code section planner producing the same `ChoreographyPlan` (schema v2) shape
the LLM arm produces:

- **Candidate filter**: `recommended_sections` contains the section's role **∩**
  `energy_range` contains the section's energy.
- **Fallback ladder** when the intersection is empty: relax to energy-only, then to
  role-only, then to the category matching the energy band. Never return nothing —
  this arm is also the *fallback* per D1, so it must always produce a plan.
- **Variety constraints**: no template repeats in consecutive sections; a cap on total
  repeats per song; distinct choices for sections with distinct roles. Encode the
  constraints explicitly and make them configurable — they are the arm's only
  "creative" content and should be inspectable.
- **Deterministic**: seeded where any choice is arbitrary. CC-8 records unseeded
  shuffles as an existing defect class; an unseeded selector cannot be an experimental
  control.
- Schema-v2 intents (intensity/color/shutter/gobo) are produced from the same
  annotations by explicit rules, so the arms are compared on the same channel width.
  If an intent cannot be derived deterministically for a field, the arm emits null and
  the renderer's fixture default applies — record which fields those are.

### 2. The three arms

| Arm | Definition |
|---|---|
| **A — deterministic** | The selector above. No LLM call on the planning path (audio profile/lyrics analysis may still run; see "held constant" below). |
| **B — full LLM** | The shipped path with everything this phase fixed: widened schema, lyric MomentCues, judge memory, `recommended_sections` rendered, iteration retained (D4). |
| **C — macro-ablated** | Full LLM planning with the macro planner removed from the chain, testing whether the macro stage's prose-only influence is worth its 2–6 calls (P3-F1: its only non-prose effect on the shipped path is cache invalidation). |

### 3. The experiment protocol

**Song set.** N ≥ 8 songs, fixed and listed by name/hash in the decision record before
the first run. Composition requirement: at least two clearly different genres, at
least one track with prominent lyrics and one instrumental, at least one with a
non-4/4 or tempo-varying feel, and at least one the owner knows well enough to judge
confidently. Songs are the owner's own local audio; nothing is redistributed.

**Seeds and determinism.** Arm A is seeded and re-runnable to identical output. Arms B
and C use a fixed model, fixed `reasoning.effort`, and fixed temperature per role
(from P2P-T10's config). LLM sampling is not reproducible; run **2 independent runs
per song for arms B and C** so within-arm variance is visible, and report it. Arm A
needs one run per song.

**Held constant across arms:** the audio analysis (same cached features, same grid
source per P2P-T8's decision, same stems setting per P2P-T7), the fixture rig, the
renderer, the export path, and the evaluation harness version. Only the planning stage
differs. Record the analysis cache keys so this is verifiable rather than asserted.

**Total run count:** N songs × (1 + 2 + 2) = 5N sequences (40 at N=8).

**Scoring.** Every sequence is scored by P2P-T6: the four VLM rubric categories plus
the deterministic sync metrics. **Sync is never judged by the VLM** — that principle
holds here as everywhere.

**Cost cap.** Judging: 5N × ≤$0.20 = **≤$8.00 at N=8**. Planning for arms B and C:
budget **≤$25.00 total** across the experiment (2 runs × 2 arms × 8 songs at
`gpt-5.6-sol` planning rates, with the phase's repair-loop ceiling reduced by
P2P-T9/T11). **Hard cap for the whole task: $40.00.** Exceeding it requires
orchestrator sign-off. Report actual spend from per-call `response.usage` — the P3-F24
fix is what makes this figure meaningful.

**Human spot-checks, blind.** The owner reviews a randomized subset — **at least one
song's full set of arms, plus 5 randomly drawn sequences** — with arm identity hidden,
and ranks them. Record the ranking and the agreement with the harness's ordering. D11:
"humans sampling instead of gating"; §5: "calibrate against human spot-checks before
trusting trends".

### 4. What "parity" means — fixed before the numbers exist

Parity is declared when **all** of the following hold on the song set:

- The difference in **mean total rubric score** (the four categories summed) between
  arm A and arm B is **within 0.5 points on the 0–40 scale**, and
- the difference is **smaller than the within-arm variance of arm B** across its two
  runs per song (i.e. the arms differ by less than the LLM differs from itself), and
- the **blind human ranking shows no consistent preference** — the owner does not
  correctly identify the LLM arm as better at a rate meaningfully above chance on the
  spot-check subset, and
- **deterministic sync metrics** are equal or better for arm A (these are objective;
  if arm A is worse on sync, it is not parity).

If parity holds → **the deterministic selector becomes the standing default**, per
D1's verbatim language, with the LLM arm retained as an option and as the source of
the widened intents.

If arm B beats arm A beyond that band → the LLM arm keeps the default, and the
deterministic selector stays as the documented baseline/fallback/regression arm.

Arm C is evaluated against arm B on the same basis, and answers a separate question:
whether the macro planner earns its calls.

**No post-hoc criterion changes.** If the protocol turns out to be under-powered
(e.g. variance swamps everything), say so and report an inconclusive result — an
honest null is a result; a moved goalpost is not.

### 5. Recording the verdict

- Update `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md`'s D1
  with the outcome, quoting the standing-default language and stating which way it
  resolved.
- Write a decision record in `memories/decisions/` per `AGENTS.md`'s memory protocol
  (provenance and date in frontmatter, links to the change documents, `memories/INDEX.md`
  updated).
- Commit the evaluation results through the P1P-T10 writer — these are the repository's
  first comparative results and must be reproducible from the recorded config.
- Whatever the verdict, the deterministic arm **stays in the tree** as the
  baseline/fallback/regression arm. It is not deleted on a loss.

### Non-goals

- Changing any implementation in response to the result. This task measures and
  records; acting on the verdict is separate work.
- Judging sync with the VLM.
- Growing the harness (P2P-T6 owns it).
- Redistributing any song audio.

## Implementation approach

Files/symbols:

- New: the deterministic selector (a planning-stage implementation producing schema-v2
  `ChoreographyPlan`), and the experiment runner that drives arms × songs × runs and
  collects results.
- `packages/twinklr/core/sequencer/moving_heads/templates/library.py` — the registry's
  `TemplateInfo`/metadata is the selector's data source; extend it if the annotations
  needed for filtering are not exposed for listing.
- `packages/twinklr/core/reporting/evaluation/` — results land here through the
  P1P-T10 writer and P2P-T6's producer; `ComparisonReport` currently has zero
  producers and zero tests (SF-4) — this task is its first real producer.
- Arm C needs judge/macro ablation to be configurable, which P2P-T9's
  `max_iterations` fix and the stage graph make possible.

Sequencing constraints copied verbatim from the plan:

> - T13's spec includes the experiment protocol (N songs, arms, seeds, cost cap, what
>   "parity" means) — copy the standing-default language from D1 verbatim.
> - Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts
>   are not replayable) (P1P-T10).
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.
> - Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
>   each spec's stated test budget; live-LLM and xLights-GUI tests are marked
>   `LOCAL-ONLY` in specs and excluded from CI.

## Acceptance criteria

1. The deterministic selector exists, is seeded and reproducible, always produces a
   plan (fallback ladder), applies the variety constraints, and emits schema-v2
   intents where they are derivable.
2. All six preconditions in §"Preconditions" are verified merged, evidenced in the
   handoff. Any unmet precondition stops the run.
3. The song set is fixed and recorded **before** the first run, with hashes.
4. 5N sequences are produced, all scored by P2P-T6, with the analysis held constant
   across arms (verified by recorded cache keys).
5. Actual spend is reported from per-call usage and is within the $40.00 cap.
6. The blind human spot-check is completed on the specified subset, with rankings
   recorded and arm identity provably hidden during ranking.
7. The parity criteria in §4 are evaluated **as written**, and the verdict — including
   an inconclusive verdict — is recorded in the proposal and a decision record, with
   D1's standing-default sentence quoted verbatim.
8. The deterministic arm remains in the tree regardless of outcome, documented as the
   baseline/fallback/regression arm.
9. `make validate` check-only forms pass; the experiment runner and selector are unit
   tested (below) without any network access.

## Tests

Unit-testable parts (TDD):

1. `test_selector_candidate_filter` — `(chorus, energy=70)` narrows to the expected
   candidate set from the annotation table; `(section role with no match)` walks the
   fallback ladder.
2. `test_selector_is_deterministic` — same input + seed → identical plan, twice.
3. `test_selector_always_produces_a_plan` — parametrized across all 12 section labels
   × energies 0, 5, 30, 50, 80, 100, including the energy 0–4 gap the census flags.
4. `test_variety_constraints_hold` — no consecutive repeats; repeat cap respected.
5. `test_selector_emits_schema_v2` — the arm's output validates as the same model the
   LLM arm produces, so the renderer path is genuinely identical.
6. `test_experiment_runner_holds_analysis_constant` — the runner reuses one analysis
   cache entry across arms (asserted on keys, not timing).
7. `test_arm_c_ablates_macro_planner` — the macro stage is absent from arm C's call
   record.

The experiment run itself is **LOCAL-ONLY** and is not a CI test.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit -k "selector or experiment or comparison" -q
uv run pytest -m "not local_only" -q
```

LOCAL-ONLY (owner's Mac; windowed xLights for video export; `OPENAI_API_KEY` set):

```bash
uv run <experiment-runner> --songs <manifest> --arms A,B,C --runs-llm 2 \
    --cost-cap 40.00 --report
uv run <eval-report-cli> --compare                 # writes the comparison result
```

Paid-API budget for this task: **≤ $40.00 total** (planning + judging), reported from
per-call usage.

## Effort & risk

**L.** Main risk: producing a confident verdict from an under-powered experiment. N=8
songs with 2 LLM runs each is enough to see whether the arms differ *obviously*; it is
not enough to resolve a subtle difference, and the parity criteria are written to make
that limitation explicit rather than to hide it (the "smaller than within-arm
variance" clause is doing that work). Mitigation: report variance alongside means,
require the blind human check, and permit an inconclusive verdict. Second risk: an
unverified precondition silently invalidating everything — mitigated by criterion 2
making the check a gate. Third risk: the VLM judge itself being uncalibrated —
mitigated by P2P-T6's calibration protocol being an acceptance criterion there, and by
the human spot-checks here; if the harness disagrees with the owner's blind ranking,
that disagreement is itself the headline finding and must be reported, not smoothed.

## Backlog addition (P1P-T9 verification, 2026-08-13)
Planner temperature is NOT in the planner cache keys (only profile/lyrics key it)
and every call site uses the hardcoded spec default — if any arm varies sampling
temperature, key it first or cached plans will confound the arms.

## Author implementation handoff — 2026-08-14

Status: **IMPLEMENTED, PENDING INDEPENDENT VERIFICATION, EXPERIMENT PENDING-OWNER.**
This is an author handoff, not approval. No provider call, owner audio, xLights run,
human ranking, comparison verdict, proposal update, decision record, or evaluation
result was produced during implementation.

### Reverified preconditions before implementation

The author received and reviewed the fresh combined-baseline precondition audit at
`8aeda12`: **114 passed, 2 expected skips**. All six source/code preconditions passed:

1. P4-F1/P4-F8 render bottlenecks are removed by the Phase 1P T3/T5 renderer and
   template-space implementations and their regression tests.
2. P3-F5/P3-F7/P3-F14 channel fixes are present in the merged T4/T9/T1 prompt,
   context, and judge-memory implementations.
3. P3-F24 attribution is now carried as exact prompt/reasoning/completion usage for
   each logical call, including repair and failure paths, in `async_runner.py` and the
   shared judge controller. T13 converts those records into priced arm call records.
4. P3-M-A is behavioral: the judge threshold participates in acceptance, with the T9
   behavioral tests still passing.
5. P3-M-B is fixed and `max_iterations=0` remains supported. T13 does **not** misuse
   zero iterations as macro ablation: arm C removes the macro stage from the graph.
6. Threshold and sampling temperature now participate in macro and moving-head
   planning cache identities, so changed experiment configuration cannot silently hit
   an incompatible plan cache.

Any regression of one of these checks invalidates the experiment and is a hard stop.

### Implemented evidence seams

- The seeded deterministic selector reads each actual `TemplateDoc.metadata` through
  `REGISTRY.get`, uses the fixed role/energy fallback ladder, enforces configurable
  repeat/role variety, converts profile energy from 0–1 to 0–100 exactly once, and
  preserves authoritative section bars. It explicitly constructs intensity, color,
  shutter, gobo, and moment-cue fields on today's schema-v2 `PlanSection`; tests assert
  `legacy_intent_omitted is False` and observable renderer effect. If a song is longer
  than the template catalog can satisfy under the strict variety rules, it applies the
  frozen relaxation order (distinct roles, repeat cap, consecutive repeat), returns a
  plan deterministically, and records the exact relaxed constraints in each trace.
- The runner freezes the N ≥ 8 manifest before work and records SHA-256 identities for
  audio, analysis payload/cache key, beat grid, stems, fixture config, template set,
  renderer, and evaluation config. One analysis snapshot is reused for all five runs.
- Arms are exactly A1, B1/B2, and C1/C2 per song. B includes the macro stage; C removes
  it with a real stage-graph switch while retaining the moving-head judge loop. Every
  B/C run has a distinct persisted regeneration nonce so planning caches regenerate
  while upstream analysis/profile/lyrics/grid inputs remain frozen.
- Macro and moving-head plan cache identities bind the exact available-template IDs
  and `TemplateDoc.metadata`, the authoritative `BeatGrid`, fixture-planning identity,
  macro-enabled/ablated graph mode, threshold, temperature, model, reasoning, and
  prompt fingerprints. The B/C regeneration nonce is also part of the planning key.
- `PreCallSpendGate` must authorize every planning or vision logical request immediately
  before the provider call and use the shipped provider-bound wrapper to settle an
  exact success-or-failure record before another request can be authorized. Successes,
  failures, retries, and repairs all consume the same caps. The backend result must
  exactly match the gated call ledger; arm C containing a macro call is rejected.
  `arm_call_records_from_iteration` converts current-pipeline `IterationCallRecord`
  evidence into exact priced records bound to model/reasoning/temperature/pricing ID.
  The LOCAL-ONLY CLI supplies an atomic per-run partial-attempt journal, updated on
  every settlement before another call can be authorized, so failed and repair usage
  survives a later owner-backend failure.
- Blind review first selects one complete five-sequence song plus five randomly drawn
  sequences, then deterministically expands the packet only as needed to make five
  independent A-vs-B song comparisons reachable. It randomizes with the frozen seed,
  copies previews to opaque filenames, and exposes no
  source filename, arm, score, metadata, or reasoning. The packet commitment covers
  exact preview bytes, opaque paths, track grouping, ordering, and seed; every preview
  is re-hashed before ranking and finalization. Ranking is packet-hash-pinned and must
  be persisted before the reveal key can be written.
- `ComparisonReport` schema 2 records song/arm/run/cache/hash/call/cost/blind/human/
  parity/calibration evidence and writes through the current evaluation writer. Its
  validator rechecks the accepted calibration artifact and recomputes the exact 5N
  matrix, summaries, spend, parity, human evidence, and signed outcome from bound raw
  run records; supplied derived claims are not trusted. Full serialized P2P-T6
  `VisionEvaluationResult` evidence is retained as the typed current-schema result with
  calibration and evaluation-config hashes; validation requires the vision call-record
  tokens and spend to equal its embedded usage ledger exactly. The JSON writer excludes
  computed fields and round-trips exactly.

### Second verifier-rejection remediation

All six follow-up acceptance blockers were implemented red-first and are covered by
adversarial tests:

1. A run's `SequenceScore` is reconstructed exactly from its embedded calibrated
   `VisionEvaluationResult`; the run plan SHA must equal the typed plan and the vision
   plan SHA, and the blinded artifact path/SHA must be that result's exact preview.
   Report finalization repeats those checks, so scoring, parity, and blind review cannot
   silently refer to different artifacts or plans.
2. The fixed human protocol remains one full five-arm song plus five random sequences.
   A deterministic seeded expansion adds the minimum missing A/B selections needed for
   the precommitted five independent song comparisons. One hundred seed probes verify
   both requirements are simultaneously reachable without weakening the evidence rule.
3. Each frozen role config carries positive prompt/reasoning/completion rates and the
   `token-components-v1` formula, not merely a pricing label. Finalization recalculates
   every record from exact token components; even a self-reported zero-cost million-token
   record is rejected. Multi-call repair/failure usage becomes one independently priced
   and gated settlement per logical request. The provider-bound gate persists each
  settlement before it authorizes the next request.
4. Macro planning, moving-head planning/repair, and vision judging are validated against
   their own model/reasoning/temperature/pricing identities. The full vision result's
   model must equal the frozen vision role, independently of either planning role.
5. Every B/C record persists its planning-input SHA, regeneration nonce, and derived
   planning-cache key. The finalizer recomputes the input from the exact manifest,
   per-song held constants, arm/ablation mode, and role configs, then recomputes the key
   from that input and nonce and requires all B/C keys to be distinct.
6. Blind track groups are reconstructed from reveal-bound song IDs in packet order.
   Recommitting the packet and reveal together after changing a group to `Track-99` is
   still rejected.

These are evidence-integrity constraints only. They do not supply owner calibration,
audio, provider output, a human judgment, parity evidence, or a D1 result.

### Final narrow integrity remediation

The provider and blind-review boundaries are fail-closed:

- Only one pre-call authorization may exist at a time. A second sequential or parallel
  authorization is rejected until the first is settled, and role/kind binding is fixed:
  `vision_judge` uses the judging gate while macro/moving-head planning and repair use
  the planning gate. A provider exception carrying `ProviderOperationError` journals
  its exact failed `ArmCallRecord` before the original exception is rethrown. If exact
  usage is unavailable, the wrapper journals a role-bound, zero-token/zero-cost failed
  record with the frozen `provider_exception_usage_unavailable` status. Invalid normal
  returns (including `None` and non-model objects) also close through that explicit
  unknown-usage record, then raise `ExperimentBlockedError` with the validation or
  settlement cause preserved. The fallback is used only while the authorization is
  still outstanding, preventing double settlement when a gate error already journaled
  the returned evidence. Even an apparent `ArmCallRecord` is serialized and freshly
  validated before settlement, so `model_construct` or non-validating `model_copy`
  cannot bypass token-total or failure-state invariants. Every wrapper-created
  authorization therefore closes once; failed, cancelled, over-reservation, and
  provider-attempt evidence cannot disappear or leave a parallel-call loophole.
- Blind IDs must match the generated opaque `Sequence-NN-<8 hex>` form. Every artifact
  basename is exactly `<blind_id>.mp4`, and all packet items share one staging parent.
  Ranking and finalization re-parse those constraints and require the artifact parent
  to equal the packet file's parent before any bytes are trusted. Recommitting packet
  and reveal hashes cannot make a leaky ID, `Arm-A-source-name.mp4`, or mixed-parent
  packet valid.

Adversarial tests cover outstanding/sequential authorization, concurrent wrapper calls,
cross-kind cap bypasses, exact-usage and unavailable-usage provider exceptions,
exactly-once closure, leaky blind IDs/basenames, mixed parents, and recommitted paths.

The pre-data operational definition of the second parity bullet is fixed as follows:
for each song calculate `abs(B1.total - B2.total)` on the 0–40 rubric scale, then take
the arithmetic mean across songs. The absolute difference between the overall A and B
mean totals must be strictly smaller than that `mean_within_song_abs_delta`. This keeps
both sides in the same units and implements the spec's gloss that the arms must differ
by less than the LLM differs from itself. The 0.5-point boundary is inclusive. Tests
pin the equality boundary and opposing per-song deltas before any experiment data exist.

Human preference uses at most one independent A-vs-B (or C-vs-B) comparison per song,
and only songs whose relevant blinded runs were in the committed packet count. A
precommitted minimum of five independent song comparisons is required before "no
consistent preference" can pass; fewer comparisons yield `INCONCLUSIVE`, never parity.

### Exact LOCAL-ONLY owner protocol — all steps pending

Do not start at step 2. The first gate currently fails because P2P-T6 calibration has
not been owner-accepted.

1. Complete P2P-T6's real calibration on the owner's Mac. Freeze its owner-accepted
   artifact and SHA-256, and set both `calibration_record` fields in the manifest. The
   runner validates the file, accepted decision, hash, and rubric version before it
   calls `backend.analyze`; an absent/rejected/mismatched artifact fails loudly.
2. Create an owner-local manifest containing at least eight named/hashed songs and all
   required composition flags, fixed per-role model/reasoning/temperature plus positive
   prompt/reasoning/completion token rates and the `token-components-v1` pricing formula,
   grid/stems settings,
   fixture hash, evaluation version, seed, and held-constant inputs. Keep the manifest,
   audio, backend adapter, credentials, videos, and generated artifacts local only.
3. Provide an owner-local `module:callable` backend factory implementing
   `ExperimentBackend`. It must use `request.include_macro` as the real graph switch,
   pass `request.regeneration_nonce` to both planning cache seams, reuse the supplied
   analysis snapshot, use `request.spend_gate` around every provider attempt/repair,
   convert current judge-loop usage with `arm_call_records_from_iteration`, render/export
   locally, retain `VisionEvaluationEvidence.from_vision`, and derive scores with
   `SequenceScore.from_vision`. These adapters are shipped; the owner backend wires the
   actual local pipeline to them rather than redefining accounting or evidence rules.
   Each provider operation must return its exact success-or-failure call record to the
   wrapper; a provider exception may not be allowed to bypass usage settlement.
4. After explicit owner approval, run exactly 5N sequences:

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli run \
     --manifest /OWNER/LOCAL/p2p-t13-manifest.json \
     --backend-factory owner_p2p_t13_backend:build_backend \
     --results /OWNER/LOCAL/p2p-t13-results.json --owner-opt-in
   ```

5. Stage the owner-visible blind packet. This command does not persist the reveal key:

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli prepare-blind \
     --results /OWNER/LOCAL/p2p-t13-results.json --seed <FROZEN-SEED> \
     --output-dir /OWNER/LOCAL/p2p-t13-blind
   ```

6. Without opening the results file, source videos, logs, plan prose, or any filename
   other than the opaque packet names, the owner ranks every blind ID. Save the ordered
   IDs as a JSON string list, then persist the ranking before unblinding:

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli record-ranking \
     --packet /OWNER/LOCAL/p2p-t13-blind/blind-review.json \
     --ordered-ids /OWNER/LOCAL/p2p-t13-blind/ordered-ids.json \
     --ranking /OWNER/LOCAL/p2p-t13-blind/ranking.json
   ```

7. Only after `ranking.json` exists, reconstruct and persist the reveal key, revalidate
   the real calibration, compute the frozen criteria, and write through the evaluation
   writer:

   ```bash
   uv run python -m twinklr.core.reporting.evaluation.three_arm_cli finalize \
     --manifest /OWNER/LOCAL/p2p-t13-manifest.json \
     --results /OWNER/LOCAL/p2p-t13-results.json \
     --packet /OWNER/LOCAL/p2p-t13-blind/blind-review.json \
     --ranking /OWNER/LOCAL/p2p-t13-blind/ranking.json \
     --reveal /OWNER/LOCAL/p2p-t13-blind/reveal.json \
     --report /OWNER/LOCAL/p2p-t13-comparison.json
   ```

8. An independent verifier checks the 5N matrix, exact hashes/cache identities, call
   records/spend, blind commitment/ranking timestamps, calibrated harness evidence,
   and the fixed parity computation. Only then may the owner read the verdict and
   authorize the proposal update, decision record, and committed evaluation result.

At N=8 the frozen ceilings are: 40 sequences; judging ≤ $0.20 each and ≤ $8.00 total;
planning ≤ $25.00 total across B/C, divided into a conservative pre-call reservation
of $0.78125 for each of the 32 LLM runs; and planning plus judging ≤ $40.00. Each LLM
run permits at most 12 logical planning requests and 3 provider attempts per logical
request; each sequence permits exactly one vision-judge logical request. Raising any
cap requires orchestrator sign-off and a newly frozen manifest before calls.

### Truthful non-result

P2P-T6 owner calibration acceptance is unmet. Therefore the real manifest, 5N run,
P2P-T6 scoring, blind human ranking, parity outcome, D1 verdict, proposal update,
decision record, and repository evaluation artifact are all **PENDING-OWNER**. The
standing-default sentence in §D1 and the fixed parity criteria in §4 remain unmodified.
No result should be inferred from the offline unit fixtures.

### Fresh author verification evidence

Run from the isolated `8aeda12` author worktree with no network, live provider, owner
audio, or xLights execution:

- `uv run ruff format --check .` — **1,333 files already formatted**.
- `uv run ruff check .` — **all checks passed**.
- `uv run mypy .` — **success: 718 source files**.
- `uv run pytest tests/unit/reporting/evaluation/test_three_arm_experiment.py -q` —
  **35 passed**. This includes all six second-remediation adversarial probes, the final
  narrow fail-closed/neutrality probes, and 100
  deterministic blind-selection seeds.
- Adjacent selector/runner/cache/report regression gate — **199 passed**.
- `uv run pytest tests/unit -k "selector or experiment or comparison" -q` —
  **119 passed, 4,811 deselected**.
- Most recent complete full offline gate (after the preceding narrow remediation and
  before the final malformed-normal-return-only patch) — **5,235 passed, 25 skipped,
  14 deselected, 9 pre-existing profiling deprecation warnings** in 100.09 seconds.

Implementation/evidence manifest for independent review:

- `packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py`
- `packages/twinklr/core/agents/async_runner.py`
- `packages/twinklr/core/agents/shared/judge/controller.py`
- `packages/twinklr/core/agents/sequencer/{macro_planner,moving_heads}/orchestrator.py`
- `packages/twinklr/core/agents/sequencer/moving_heads/{context,deterministic_selector}.py`
- `packages/twinklr/core/agents/sequencer/macro_planner/stage.py`
- `packages/twinklr/core/pipeline/definitions/{common,moving_heads}.py`
- `packages/twinklr/core/sequencer/moving_heads/pipeline.py`
- `packages/twinklr/core/sequencer/theming/catalog.py`
- `packages/twinklr/core/reporting/evaluation/{three_arm,three_arm_cli,render,models,__init__}.py`
- `tests/unit/agents/sequencer/moving_heads/test_deterministic_selector.py`
- `tests/unit/agents/{test_async_runner_token_attribution.py,shared/judge/test_controller.py}`
- `tests/unit/pipeline/definitions/test_definitions.py`
- `tests/unit/reporting/evaluation/test_three_arm_experiment.py`
- this specification handoff.

The focused, static, adjacent, and keyword-broad counts are fresh after the final
patch; the full-suite timing is labeled with its exact currency above. These are
evidence for independent verification, not author approval and not evidence of an
experiment result.
