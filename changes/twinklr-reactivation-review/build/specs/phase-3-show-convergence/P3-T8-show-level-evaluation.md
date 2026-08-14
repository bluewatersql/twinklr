# P3-T8 — Show-level evaluation

Phase: 3 (Show Convergence / M3) · Lane: Finale · Executor: sonnet · Verifier: opus ·
Depends on: P3-T5, P2P-T6

## Objective

Phase 2P built a vision-eval harness that scores moving-head output. Phase 3 produces
a fundamentally different artifact: a coordinated show where moving heads and display
elements are supposed to work together. This task extends the harness to score display
and combined shows, adds coordination-across-parts criteria to the rubric, produces the
**first recorded combined-show evaluation with a human judgment beside it**, and routes
those results back into the knowledge loop — the beginning of D5's fourth supply arm.

## Evidence & background

Drivers: **D11** (vision-judged evaluation loop), **D5(d)** (evaluation feedback as the
fourth supply arm), **SF-4** (the evaluation harness: writer deleted, CLI unbridged, no
result ever recorded), **P6-F3** (the checkpoint writer's archaeology and the schema-
drift trap). Detail: `reactivation-proposal.md` §3 (D11, D5) and §4 (M3);
`.../reviews/phases/corpus-intelligence.md`; `.../reviews/verification.md` §"Phase 6".

### D11, quoted (the design constraints that bind this task)

> - **Render**: xLights' `exportVideoPreview` is an implemented xlDo command (verified
>   in source; upstream ships `BatchVideoExport.lua` doing exactly
>   `openSequence→renderAll→exportVideoPreview→closeSequence`). Frame-stepped (faster
>   than realtime), audio muxed in, fps = sequence frame rate. Constraint: needs a
>   **windowed** xLights (`--headless` renders fseq only, no video) — fine on the
>   owner's Mac; Linux CI unproven.
> - **Judge**: OpenAI has no native video input … → ffmpeg frame sampling at 2–4 fps or
>   9–16-frame labeled contact sheets; 1,500-image/512 MB request limits make a full
>   song fit in one call. Cost: ≈$0.13/song at 720p·2fps on gpt-5-mini; ≈$0.66 on
>   terra-class.
> - **Design principle (from the literature)**: VLM judges are weakest exactly at
>   high-FPS audio-visual sync (Omni-Judge finding; AV-SyncBench separates temporal from
>   semantic for the same reason). **So: musical sync is measured deterministically** —
>   Twinklr knows the beat grid and every effect's timestamps — **and the VLM judges
>   only what code can't**: does the show read well, are models coordinated, palette
>   coherent, sections distinct, variety vs monotony. Frames are sent WITH Twinklr's own
>   timestamped structure as text, so the judge verifies claims rather than guessing.
> - **Rubric**: adapt AutoMV's 4-category × 12-criterion pattern to lighting
>   (musicality-by-proxy, coordination, color/palette, variety & pacing). Human
>   spot-checks stay (all sources: model judges lag experts). **No prior art exists for
>   VLM-judged light shows — this is novel and cheap enough to iterate freely.**

From §5 (risks), binding here too:

> **VLM judge validity**: novel territory; calibrate against human spot-checks before
> trusting trends; never let it judge sync (deterministic metrics own that).

And from §6 (non-goals): "no VLM-judged *sync* (deterministic forever)."

### D5(d), quoted

> **D5 — Knowledge supply** *(unchanged from v2)*: mining + LLM generation as
> complementary arms into one curated catalog; seeds from hand-authoring; evaluation
> feedback as the fourth arm once D11 lands.

M3's exit criterion names the same thing: "evaluation feedback begins flowing into the
loop (D5's fourth arm)."

### What already exists after Phase 2P (do not rebuild)

`changes/twinklr-reactivation-review/build/plan/04-phase-2p-creative-quality.md`:

- **P2P-T5** — "Preview render client … `loadSequence→renderAll→exportVideoPreview→
  closeSequence` … windowed-instance management on macOS; fseq-compare (`--fseqcmp`) as
  the CI-tier deterministic check (video export can't run headless)."
- **P2P-T6** — "ffmpeg frame sampling (2–4 fps / contact sheets) → gpt-5-mini rubric
  judge (4 categories adapted from AutoMV: musicality-by-proxy, coordination, palette
  coherence, variety/pacing) fed WITH Twinklr's timestamped structure as text;
  deterministic sync scorer (beat grid vs effect timestamps — the VLM never judges
  sync, per Omni-Judge warning); calibration protocol vs human spot-checks;
  ~$0.13–0.15/song budget enforced."

**This task extends that harness. It does not build a second one.**

### The recording mechanism, and its trap

SF-4 (`reviews/findings.md`): "Evaluation harness: writer deleted (restorable ~10
lines, schema drift trap), CLI unbridged, ComparisonReport zero producers/tests,
measures self-consistency only, **no result ever committed**".

P1P-T10 restored the checkpoint writer and bridged `eval-report` into `twinklr`, and
committed the repo's first evaluation result. The trap, from `verification.md`
§"Phase 6":

> TRAP: the inner plan schema drifted (historical `templates:[...]` vs today's
> `template_id` XOR `segments`) — historical artifacts are NOT replayable; the restored
> writer must serialize today's model.

And the corresponding overview constraint:

> Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts are
> not replayable) (P1P-T10).

The same discipline applies to the combined-show record this task writes: serialize
today's models, do not invent an archival format that will drift.

## Current behavior

- After P2P-T6, one evaluation path exists and it is shaped around moving-head output:
  a rendered preview, sampled frames, a 4-category rubric, and a deterministic sync
  score against the beat grid.
- Nothing evaluates display output. Nothing evaluates whether the two parts coordinate.
- No combined-show result has ever been recorded, and no human judgment has ever been
  recorded beside one for a combined show.
- Evaluation results feed nothing back into the catalog or the curation loop.

## Target behavior

1. **The harness accepts display and combined shows.** The render client drives a
   sequence containing display elements (and both parts together) through the same
   `loadSequence→renderAll→exportVideoPreview→closeSequence` flow; the frame sampler and
   judge are agnostic to which parts are present. Where a part is absent, its criteria
   are reported as N/A rather than scored zero.
2. **The rubric gains coordination-across-parts criteria.** Added to the existing four
   categories (musicality-by-proxy, coordination, palette coherence, variety/pacing) or
   as a fifth category — the executor picks and records the choice. The criteria must at
   minimum cover:
   - *Focal clarity*: at any moment, is it visually clear what is leading? Does it match
     the plan's `focal_arc` / `focal_roles` (P3-T4)?
   - *Call-and-response legibility*: when the plan declares a `CallResponsePair`
     spanning moving heads and display, does the exchange read as an exchange?
   - *Cross-part palette agreement*: do the moving heads and the display elements
     appear to be in the same colour world in the same section?
   - *Section-transition agreement*: do both parts change together at section
     boundaries?
   - *Mutual interference*: do the parts fight each other (competing focus, washed-out
     contrast) rather than complement?
3. **Sync stays deterministic, and now spans parts.** The deterministic scorer gains a
   **cross-part alignment metric** computed from the emitted timestamps and the shared
   BeatGrid — e.g. the distribution of |MH event start − paired display event start| for
   plan-declared pairs, and section-boundary agreement between parts. The VLM never
   scores sync or alignment; it scores whether the result *reads*. This is
   non-negotiable per D11 and §6.
4. **The judge verifies rather than guesses.** Frames are accompanied by Twinklr's own
   timestamped structure as text — including, for combined shows, the plan's declared
   coordination (focal roles, call-response pairs, palette stops per section) — so the
   judge is checking claims against frames.
5. **A first combined-show evaluation is recorded and committed.** One combined show,
   scored by the harness, with the deterministic metrics, the rubric scores, and the
   sampled-frame provenance, written through the P1P-T10 record path and **committed to
   the repository**. This is the repo's first combined-show result.
6. **A human judgment is recorded beside it.** Structured (per-category human score +
   free-text), stored in the same record, so calibration has a first data point. D11's
   own risk line requires it: "calibrate against human spot-checks before trusting
   trends."
7. **Results flow into the loop (D5's fourth arm begins).** At minimum: evaluation
   results are queryable per recipe/template so that a curation session (P2K-T3) can ask
   "which admitted recipes appear in high-scoring vs low-scoring shows". A full
   feedback-driven ranking is Phase 4 territory; what ships here is the **join** — the
   evaluation record carries the recipe/template ids used, so the arm can begin.
8. **CI tier stays deterministic.** Video export needs a windowed xLights and cannot run
   in CI; the CI tier stops at the deterministic metrics (and `--fseqcmp` where P2P-T5
   provides it). The vision half is LOCAL-ONLY and scheduled.

**Non-goals**

- Do **not** rebuild the render client, the frame sampler, or the judge (P2P-T5/T6).
- Do **not** implement automated catalog re-ranking from scores — the arm begins here,
  it does not close here (Phase 4 / D5).
- Do **not** let the VLM judge sync, alignment, or timing under any framing.
- Do **not** evaluate generated asset imagery aesthetically (P3-T7's scope note).

## Implementation approach

Files expected to change (re-verify locations — P2P-T5/T6 create most of these):

- The evaluation harness package created by P2P-T6 — rubric definition, judge prompt
  templates, the deterministic scorer, and the result model.
- The record/report path from P1P-T10 (`eval-report` CLI bridge + checkpoint writer
  seam) — extended to carry combined-show fields.
- `packages/twinklr/core/reporting/evaluation/` — including `rerender.py`, which the
  phase-5 review names as a third export caller ("`rerender.py:131` passes
  `template_xsq=xsq_path`; needs the same treatment; easy to miss") and which must work
  with P3-T6's unified export core.

Design decisions already made — do not relitigate:

- Deterministic sync/alignment; VLM for readability only. (D11 design principle; §6
  non-goal.)
- Rubric shape adapted from AutoMV's 4-category × 12-criterion pattern.
- Cost target ≈$0.13–0.15/song; humans sample rather than gate.
- Records serialize **today's** models (the P6-F3 schema-drift trap).

Sequencing constraints copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`:

> Checkpoint writer must serialize **today's** `PlanSection` (historical artifacts are
> not replayable) (P1P-T10).

> **Verification currency**: evidence in specs is from baseline `aa8d325`. Executors
> must re-verify cited line numbers before editing (the tree will drift as phases
> land) — specs cite symbol + file, with line numbers as hints only.

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass
> at every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

> Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
> each spec's stated test budget; live-LLM and xLights-GUI tests are marked
> `LOCAL-ONLY` in specs and excluded from CI.

From `changes/twinklr-reactivation-review/build/plan/06-phase-3-show-convergence.md`: T8 is the phase **Finale** — it
merges last and its committed result is the phase's evidence that the exit criterion
("evaluation results + human judgments recorded for display output") is met.

## Acceptance criteria

1. The harness scores a **display-only** sequence end to end, and a **combined**
   sequence end to end, without code branching on "which part is this" outside one
   explicit capability check.
2. The rubric contains the five coordination-across-parts criteria above (or documented
   equivalents), each with a scoring definition a human can apply to the same frames.
3. The deterministic scorer emits a cross-part alignment metric: for every plan-declared
   `CallResponsePair` spanning parts, the timing offset distribution; and per-section,
   the boundary agreement between parts. Computed from emitted timestamps and the
   shared BeatGrid — **never** from the VLM.
4. `grep`-level guard: the judge prompt templates contain no request to score sync,
   timing, alignment, or "on the beat". A test asserts this over the template files —
   the constraint is easy to violate by accident when writing a rubric about
   coordination.
5. The judge payload for a combined show includes the plan's declared focal roles,
   call-response pairs, and palette stops as text alongside the frames.
6. **A committed combined-show evaluation record exists in the repository**, containing:
   deterministic metrics, rubric scores per category, the model and sampling parameters
   used, the recipe/template ids present in the show, and the sampled-frame provenance.
7. **A committed human judgment exists** for the same show, in the same record, with
   per-category human scores and free text.
8. A calibration line is computed and recorded: per-category agreement between the human
   judgment and the VLM scores for that show. One data point is enough to establish the
   mechanism; the record must make it accumulable.
9. The evaluation record can be joined to catalog entries: given a recipe id, a query
   returns the evaluations of shows that used it. (A function plus a test is sufficient;
   no UI.)
10. CI runs the deterministic tier and passes without xLights, ffmpeg-video export, or
    any API key.
11. Cost: a full combined-show vision evaluation stays within the ≈$0.15/song target at
    the configured judge model; the harness enforces its budget and reports actual spend.

## Tests

1. `tests/unit/reporting/evaluation/test_rubric_coordination_criteria.py` — the criteria
   exist and are well-formed (#2).
2. `tests/unit/reporting/evaluation/test_no_vlm_sync_scoring.py` — the prompt-template
   guard (#4). Cheap, and it protects the one design constraint the literature warns
   about.
3. `tests/unit/reporting/evaluation/test_cross_part_alignment_metric.py` — synthetic
   emitted timestamps + a known BeatGrid → expected offsets and boundary agreement (#3).
   Includes a deliberately misaligned fixture that must score badly.
4. `tests/unit/reporting/evaluation/test_judge_payload_includes_plan_claims.py` — (#5),
   asserting on the built payload with a mocked judge.
5. `tests/unit/reporting/evaluation/test_record_schema.py` — the record round-trips
   through today's models (#6/#7) and refuses to load a drifted historical shape rather
   than silently coercing it (the P6-F3 trap).
6. `tests/unit/reporting/evaluation/test_recipe_join.py` — (#9).
7. `tests/integration/test_evaluation_deterministic_tier.py` (marked
   `@pytest.mark.integration`) — the CI tier runs with no xLights and no API key (#10).

All automated tests use fixtures and a mocked judge; zero API calls.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .

uv run pytest tests/unit/reporting/evaluation/ -v
uv run pytest tests/integration/test_evaluation_deterministic_tier.py -v

uv run pytest tests/ -q      # no NEW failures vs the verification.md baseline
uv run pytest tests/golden -v

# the committed artifacts exist and parse
uv run twinklr eval-report <path-to-committed-combined-show-record>
```

LOCAL-ONLY (required to produce the phase's exit evidence):

- **Windowed xLights 2026.15** on macOS: render the combined show's video preview via
  the P2P-T5 client. Per D11: "needs a **windowed** xLights (`--headless` renders fseq
  only, no video)". Linux CI is unproven and out of scope.
- **Vision judge, live**: one combined-show evaluation. **Test budget: one combined-show
  vision evaluation at the configured judge model, ≈$0.15 (hard cap $1.00 for the
  task, covering at most a few retries).** Record actual spend in the PR body.
- **Human judgment**: the owner (or a designated human) scores the same show against
  the same rubric. This is a human deliverable, not a model output, and the task is not
  complete without it.

## Effort & risk

**Size: M.** Mostly extension of an existing harness plus the record/commit work; the
human-judgment step is coordination, not code.

**Main risk: the VLM ends up judging sync anyway.** A rubric about "coordination" slides
into "are they on the beat together" almost by itself, and the literature is explicit
that this is exactly where VLM judges are weakest (Omni-Judge; AV-SyncBench).
*Mitigation*: acceptance #4's template guard is a test, not a review note, and the
cross-part *alignment* metric is deterministic by construction so the judge has no
reason to reach for it.

**Secondary risk: one evaluation proves nothing.** A single scored show with a single
human judgment cannot validate the judge. *Mitigation*: this task's claim is deliberately
modest — it establishes the mechanism, the record format, and the first calibration
point. Trend claims wait for accumulation; the record format is designed to accumulate.

**Third risk: a record format that drifts.** SF-4 and P6-F3 document a working evaluation
capability that was silently dropped in a migration, leaving artifacts that are not
replayable. *Mitigation*: acceptance #5's test refuses drifted shapes loudly, and the
record serializes today's models per the overview constraint.

**Fourth risk: the show is not good enough to evaluate meaningfully.** If P3-T5's
combined output is thin (catalog coverage, per P2K's exit criteria), the first
evaluation measures the catalog rather than the coordination. *Mitigation*: report it as
such. A low score with a correct explanation is a valid result and feeds D5's fourth arm
exactly as intended; a low score reported as a harness failure is not.
