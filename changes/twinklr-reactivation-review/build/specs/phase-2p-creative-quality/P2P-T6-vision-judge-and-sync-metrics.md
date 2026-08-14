# P2P-T6 — Vision judge + deterministic sync metrics

Phase: 2P (Creative Quality, Measured) · Lane: E (evaluation harness, parallel) · Executor: opus · Verifier: opus · Depends on: P2P-T5, P1P-T10

⚖ **Owner-decision-bearing.** The owner reviews: the rubric's four categories and
their criteria, the calibration outcome against human spot-checks, and the per-song
cost budget. This harness scores every future change to the system, so its rubric is
a durable choice, not an implementation detail.

## Objective

Score any rendered sequence automatically: sample frames from P2P-T5's video preview,
send them to a rubric-driven VLM judge **together with Twinklr's own timestamped
structure as text**, and separately compute musical sync deterministically from the
beat grid and effect timestamps. The judge never scores sync. Target cost ≈$0.13–0.15
per song, so humans sample rather than gate.

## Evidence & background

Findings: **D11 (new — vision-judged evaluation loop)**, **SF-4** (evaluation harness:
writer deleted, CLI unbridged, no result ever committed).
Sources: `changes/twinklr-reactivation-review/reviews/reactivation-proposal.md` D11,
§5, §6; `.../reviews/findings.md` SF-4; `.../reviews/verification.md` "Phase 6"
(P6-F3 checkpoint-writer archaeology).

### The judging constraints, quoted (D11, research accessed 2026-08-13)

> **Judge**: OpenAI has no native video input (feature request closed as
> not-planned) → ffmpeg frame sampling at 2–4 fps or 9–16-frame labeled contact
> sheets; 1,500-image/512 MB request limits make a full song fit in one call.
> Cost: ≈$0.13/song at 720p·2fps on gpt-5-mini; ≈$0.66 on terra-class. Gemini is
> the one native-video+audio option but samples at 1 FPS — too coarse for
> beat-level judgment.

### The deterministic-sync principle (quoted — this is the design's spine)

> **Design principle (from the literature)**: VLM judges are weakest exactly at
> high-FPS audio-visual sync (Omni-Judge finding; AV-SyncBench separates temporal
> from semantic for the same reason). **So: musical sync is measured
> deterministically** — Twinklr knows the beat grid and every effect's timestamps —
> **and the VLM judges only what code can't**: does the show read well, are models
> coordinated, palette coherent, sections distinct, variety vs monotony. Frames are
> sent WITH Twinklr's own timestamped structure as text, so the judge verifies
> claims rather than guessing.

Reinforced in §5 (risks) and §6 (non-goals):

> **VLM judge validity**: novel territory; calibrate against human spot-checks
> before trusting trends; never let it judge sync (deterministic metrics own that).

> No VLM-judged *sync* (deterministic forever).

**This is non-negotiable and structural, not a policy note.** The rubric must contain
no sync criterion, the prompt must not ask about timing accuracy, and the response
model must have no field into which a sync judgment could be written.

### The rubric (quoted origin + the skeleton to embed)

> **Rubric**: adapt AutoMV's 4-category × 12-criterion pattern to lighting
> (musicality-by-proxy, coordination, color/palette, variety & pacing). Human
> spot-checks stay (all sources: model judges lag experts). **No prior art exists
> for VLM-judged light shows — this is novel and cheap enough to iterate freely.**

**Rubric skeleton — implement exactly these four categories.** Criteria wording is
the executor's to refine with the owner; the category set is fixed.

| # | Category | What it asks the VLM (scored 0–10) | Explicitly NOT asked |
|---|---|---|---|
| 1 | **Musicality-by-proxy** | Does the visual energy trajectory match the song structure Twinklr states in the accompanying text — do the sections the text calls "drop"/"chorus" look bigger than the ones it calls "verse"/"intro"? Are transitions between named sections visible? | Whether effects land *on* the beat (deterministic metric owns this) |
| 2 | **Coordination** | Do the fixtures act as an ensemble — mirrored/fanned/chased deliberately — rather than independently? Do groups the text names as coordinated appear coordinated? | Sub-frame timing offsets between fixtures |
| 3 | **Color / palette coherence** | Is the palette coherent within a section and deliberate across sections? Do colour changes align with the named section boundaries? Any clashing or muddy combinations? | Exact DMX values (deterministically known) |
| 4 | **Variety & pacing** | Across the whole song, is there enough variation to hold attention without becoming chaotic? Are any two sections indistinguishable? Does anything repeat past the point of monotony? | Beat-level repetition rate |

Each category yields a 0–10 score plus a short justification that **cites frame
indices or section names from the supplied text**. Ungrounded praise is a calibration
failure signal, not a score.

### Deterministic sync scorer

Twinklr knows the beat grid (`sequencer/timing/beat_grid.py::BeatGrid` — verified
present, exposing `beat_boundaries`, `bar_boundaries`, `snap_to_nearest_beat`,
`snap_to_nearest_bar`) and every effect's start/end timestamps. Compute, without any
model:

- **On-grid rate** — fraction of effect starts within a tolerance window of a beat
  (and separately of a downbeat/bar line).
- **Mean absolute offset** — ms between each effect start and its nearest grid point,
  and the distribution (not just the mean; a bimodal offset is a different defect
  from a constant one).
- **Section-boundary alignment** — do effect boundaries coincide with detected
  section boundaries.
- **Density per section** — effects per bar, so "nothing renders here" (the P4-F4
  class: 1-bar sections rendered nothing for all 37 templates) is caught numerically.

These are the metrics that must NOT move to the VLM, ever.

### Cost budget (enforced, not aspirational)

- **Target ≈$0.13–0.15 per song**, per D11's arithmetic: ≈$0.13/song at 720p · 2 fps
  on a mini-class judge; ≈$0.66 on terra-class.
- The harness computes the estimated cost **before** issuing the call (frames ×
  resolution × model price) and refuses to exceed a configured per-song cap without
  an explicit override flag. Default cap: **$0.20/song**.
- A per-run (multi-song) cap exists too. P3-F28b's lesson is explicit: an LLM- or
  data-determined list length must never directly determine the number of paid calls
  without a cap. Here the analogue is frame count — bound it.
- Cost accounting must use per-call `response.usage`, not a differenced shared
  counter. P3-F24/P1-F27: "every per-stage token figure the shipped pipeline reports
  is already wrong today". P1P-T9 fixes the runner side; this harness must consume the
  fixed path, not reintroduce the delta pattern.

### What exists to build on

SF-4: the evaluation harness's writer was **deleted, not never-built** (P6-F3, git
archaeology) and P1P-T10 restores it plus bridges the `eval-report` CLI. The
`reporting/evaluation/` package exists (`generator.py`, `collect.py`, `render.py`,
`compliance.py`, `models.py`, `cli.py`, …, verified in tree). This task adds a scoring
producer to that harness — it does not build a second reporting system.

Constraint inherited from P1P-T10 and repeated verbatim from the plan overview:

> - Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts
>   are not replayable) (P1P-T10).

So: scores are computed against artifacts produced by the current schema. Do not
build replay of historical checkpoints.

## Current behavior

- No evaluation result has ever been committed to the repository (SF-4).
- `ComparisonReport` has zero producers and zero tests; the harness "measures
  self-consistency only".
- Quality assessment is manual and unrecorded.

## Target behavior

1. **Frame sampling.** ffmpeg extracts frames from P2P-T5's exported video at a
   configured rate (2–4 fps) or composes 9–16-frame labeled contact sheets. Labels
   carry the timestamp so the judge can cite them. Sampling rate and resolution are
   configuration, because they are the cost dial.
2. **Structure-as-text companion.** Every judge call includes Twinklr's own
   timestamped structure: section names with start/end times, the plan's per-section
   intent, and the beat/downbeat grid summary — "so the judge verifies claims rather
   than guessing".
3. **Rubric judge.** One call per song where possible (the 1,500-image / 512 MB
   request limits make a full song fit), returning the four category scores +
   justifications in a strict response model. Model: the mini-class judge named by
   D6/P2P-T10 for the cost tier; the model id comes from config, never hardcoded
   (P2P-T10 owns consolidating the 29+ hardcoded sites — do not add a new one).
4. **Deterministic sync scorer** producing the metrics above from the BeatGrid + the
   rendered artifact, with zero model involvement.
5. **One combined result record** — VLM category scores, deterministic sync metrics,
   cost actually spent, model id, rubric version, and the artifact hash — written
   through the P1P-T10 evaluation writer so results are comparable across runs and
   committable.
6. **Calibration protocol vs human spot-checks.** A documented procedure: score N
   sequences with the harness, have the owner rank/score the same ones blind, report
   agreement (rank correlation + per-category agreement), and record the result. The
   harness is not trusted for trend claims until this is run once. "all sources:
   model judges lag experts."
7. **CI tier vs local tier.** Deterministic sync metrics run in CI (no GUI, no API).
   Video export + VLM judging are LOCAL-ONLY, per D11's render constraint.

### Non-goals

- Judging musical sync with the VLM — forbidden, structurally.
- The three-arm comparison itself (**P2P-T13** consumes this harness).
- Building a second reporting/report-rendering system (extend
  `reporting/evaluation/`).
- Native-video judging or a Gemini path (D11: 1 FPS is "too coarse for beat-level
  judgment", and the deterministic scorer owns beat-level anyway).

## Implementation approach

Files/symbols:

- New: frame sampler (ffmpeg subprocess wrapper), contact-sheet composer, the rubric
  agent (an `AgentSpec` through `AsyncAgentRunner`, so it inherits schema/taxonomy
  auto-injection, logging and the repair loop — **do not** add a fourth
  out-of-framework LLM call site; CC-8 and P3-M-C record the existing ones as a
  defect), the deterministic sync scorer, and the result model.
- `packages/twinklr/core/reporting/evaluation/` — extend with the new producer and
  result type; reuse `models.py` conventions.
- `packages/twinklr/core/sequencer/timing/beat_grid.py` — read-only source of grid
  truth.
- P2P-T5's client — read-only consumer for the video.
- ffmpeg is an external binary: detect it, fail with an actionable message if absent,
  and never assume a specific build.

Sequencing constraints copied verbatim from the plan:

> - Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts
>   are not replayable) (P1P-T10).
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.
> - Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
>   each spec's stated test budget; live-LLM and xLights-GUI tests are marked
>   `LOCAL-ONLY` in specs and excluded from CI.

## Acceptance criteria

1. The rubric implements exactly the four categories in the table above; the response
   model has no field capable of expressing a sync/timing judgment, and the prompt
   contains no sync question. A test asserts both.
2. Judge calls include the timestamped structure text and labeled frames; a rendered
   prompt test asserts the structure block is present and non-empty.
3. The deterministic sync scorer produces on-grid rate, offset distribution,
   section-boundary alignment and per-section density from a fixture artifact + grid,
   with no network access. Runs in CI.
4. Estimated cost is computed **before** the call; exceeding the configured per-song
   cap (default $0.20) aborts unless explicitly overridden; actual cost comes from
   per-call `response.usage` and is recorded in the result.
5. One combined result record is written through the P1P-T10 evaluation writer,
   including rubric version and artifact hash, and is committable.
6. The calibration protocol is documented and executed once: N ≥ 5 sequences scored
   by the harness and ranked blind by the owner, with agreement reported and recorded.
   The harness's documentation states plainly that its scores are uncalibrated until
   this exists.
7. A LOCAL-ONLY end-to-end run on one real song produces a result for **≤ $0.20**,
   evidenced by the recorded cost.
8. `make validate` check-only forms pass; the default suite requires neither ffmpeg
   output nor an API key.

## Tests

TDD where definable in advance:

1. `test_rubric_has_no_sync_criterion` — asserts the response model's fields and the
   rendered prompt contain no sync/timing judgment surface. The structural guard for
   the design's central principle.
2. `test_sync_metrics_on_known_grid` — a synthetic grid + synthetic effect timestamps
   with a known answer (e.g. all effects exactly on beat → on-grid rate 1.0; all
   offset by a fixed 40 ms → mean offset 40 ms, zero variance). Ground-truth
   assertions, which the repo has almost none of (CC-7).
3. `test_sync_metrics_detect_empty_section` — a section with zero effects reports
   zero density (the P4-F4 class, caught numerically).
4. `test_cost_estimate_blocks_over_cap` — frame count × price over cap aborts before
   any call is issued (asserted with a fake provider that fails if called).
5. `test_structure_text_accompanies_frames` — rendered-prompt assertion.
6. `test_result_record_round_trip` — through the evaluation writer.
7. `test_ffmpeg_missing_is_actionable`.
8. **LOCAL-ONLY** `test_end_to_end_score_one_song` — budget: **one song, one judge
   call, ≤ $0.20**. Excluded from CI.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit -k "sync_metrics or rubric or vision_judge" -q
uv run pytest -m "not local_only" -q
```

LOCAL-ONLY (owner's Mac; windowed xLights; `OPENAI_API_KEY` set):

```bash
uv run pytest -m local_only -k "score_one_song" -q     # budget: 1 song, ≤ $0.20
```

Paid-API budget for this task: **≤ $2.00 total** across development and calibration
(≈10 song-scorings at the $0.15 target). Exceeding it requires orchestrator sign-off.

## Effort & risk

**L.** Main risk: the judge's scores look plausible and mean nothing — this is novel
territory with no prior art for VLM-judged light shows. Mitigation: the calibration
protocol is an acceptance criterion, not a follow-up; scores are labeled uncalibrated
until it runs; and every justification must cite a frame or section so ungrounded
output is detectable. Second risk: scope leakage into sync judging — the structural
test (criterion 1) exists specifically because a future prompt edit is the likely
vector. Third risk: cost drift as frame counts grow — bounded by the pre-call
estimate and cap.

## Implementation handoff — 2026-08-14

Author implementation is complete and awaiting an independent verifier. The offline
harness now provides ffmpeg frame sampling/contact sheets, a strict four-category
configured vision role through `AsyncAgentRunner`, hard pre-call song/run budget
reservations, exact per-call usage recording, deterministic rendered-XSQ/grid metrics,
one evaluation-writer record, and the blinded N≥5 calibration calculation/protocol.

No live provider or xLights call and no owner calibration were performed during
implementation. Acceptance criteria 6 and 7 therefore remain deliberately
**owner/local-only**: results cannot declare themselves calibrated without a calibration
record, and the documented one-song command is the only paid proof path. The remaining
integration risk is whether the currently configured mini-tier model accepts the tested
Responses API `input_image` data-URL payload in a live account; the SDK request shape is
covered offline, but only the capped local-only command can prove provider/model support.

Author gate evidence (fresh after the final edit):

- `uv run ruff format --check .` — 1,305 files already formatted
- `uv run ruff check --no-cache .` — passed
- `uv run mypy .` — 707 source files passed
- focused rubric/sync/judge selection — 9 passed, 4,679 deselected
- default offline suite — 4,998 passed, 25 skipped, 11 deselected

### Verifier-reject remediation — 2026-08-14

The first independent verification rejected the author handoff on seven gaps. The author
remediation now pins the vision role to one strict HTTP request (no transport retry,
schema repair, or `json_object` fallback), enforces 1,500-image and 512 MiB encoded-request
preflight limits, settles failed-result usage before raising, and reconciles run budgets
as actual spend plus outstanding reservations. Calibration uses tie-aware ranks and a
permutation test; only a hash-pinned, existing, owner-accepted frozen N≥5 artifact with
rubric/sampling/hashes/cost/date/owner evidence can authorize calibrated status.

Deterministic empty/boundary outputs no longer report invented zero-millisecond evidence.
ffmpeg sampling uses unique directories and a bounded actionable timeout. Grounding is
validated against actual frame/contact-sheet ranges and section names. Preview/XSQ hashes,
current plan identity, config identity, delivered-grid compatibility, and deterministic
prerequisites are established before the paid request. This remediation still performs
no live provider or xLights call and does not manufacture owner calibration evidence.

Fresh remediation gates:

- discriminating remediation selection — 19 passed, 4,683 deselected
- agents + reporting broad batch — 1,173 passed, 1 skipped
- `uv run ruff format --check .` — 1,305 files already formatted
- `uv run ruff check --no-cache .` — passed
- `uv run mypy .` — 707 source files passed
- final default offline suite — 5,012 passed, 25 skipped, 11 deselected

The re-review additionally pinned calibration sample independence: both artifact hashes
and preview hashes must be independently unique across the N≥5 frozen evidence rows.
Changing opaque sequence IDs or ranks cannot make duplicate immutable inputs count as
distinct calibration shows.

Re-review remediation gates: calibration 10 passed; strict/provider selection 10 passed;
agents + reporting broad batch 1,177 passed and 1 skipped; format, no-cache Ruff, and
Mypy (707 source files) passed.
