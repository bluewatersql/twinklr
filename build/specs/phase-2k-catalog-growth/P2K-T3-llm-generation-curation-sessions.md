# P2K-T3 — LLM-generation curation sessions

⚖ **Owner-decision-bearing.** This task builds TOOLING and a SESSION PROTOCOL for a
human (the owner) to review LLM-generated candidates one at a time and admit or
reject each with a stated reason. It does **not** authorize an autonomous agent to
decide which generated recipes are good and promote them — no code path introduced
by this task may call `promote_staged_recipes` (or any successor) without a
human-authored admit decision behind every promoted `recipe_id`. This mirrors T2's
owner-decision framing and the plan's explicit instruction
(`build/plan/05-phase-2k-catalog-growth.md:23-24`): "This phase's 'executor' for
T2/T3 sessions is really the OWNER plus tooling; specs define the tooling + session
protocol, not autonomous agent authoring of taste."

Phase: 2K (M2-K) · Lane: — · Executor: sonnet (tooling) + OWNER (session) ·
Verifier: sonnet · Depends on: P1K-T4, P1K-T5, P2K-T1

## Objective

Wire the `recipe_builder` LLM-generation arm to target T1's coverage gaps instead of
its current catalog-internal-only gap analysis, then run a human admission session
over the resulting staged candidates that records an admit/reject reason for every
one — closing the gap where today's `--promote` blindly promotes every staged file
with no per-candidate decision or reason captured at all.

## Evidence & background

- Plan task (`05-phase-2k-catalog-growth.md:19`): "recipe_builder generation arm
  (now in the provider framework, sol-tier) targeted at T1's coverage gaps; staged →
  human admission sessions; per-session log of admit/reject reasons feeds prompt
  refinement."
- D6 (`reactivation-proposal.md:164-166`): "sol planning / terra judge... explicit
  `reasoning.effort`" — this task's generation calls must go through the provider
  framework at the sol tier per D6, **after P1K-T5 lands** (P1K-T5 moves
  `recipe_builder/generation.py` off its current raw/hardcoded-default client onto
  the provider framework — do not duplicate that migration here; this task only
  supplies the sol-tier config and the coverage-gap targeting on top of it).
- **Current `--promote` behavior has zero per-candidate review (verified,
  `scripts/demo_recipe_builder.py`)**: `_promote()` calls
  `promote_staged_recipes(staged_dir=..., templates_dir=...)`
  (`demo_recipe_builder.py:278+`), and `promote_staged_recipes()`
  (`packages/twinklr/core/recipe_builder/promotion.py:51-91`) iterates **every**
  `*.json` file in `staged_dir` and copies it into `builtins/` + appends to
  `index.json`, skipping only on ID collision or JSON parse failure — there is no
  parameter to promote a subset, and no mechanism anywhere that records why a human
  did or didn't want a given staged candidate in the live catalog. The only
  "review" that happens today is eyeballing the demo script's printed staged-recipe
  summary (`demo_recipe_builder.py:244-259`) before deciding to re-run with
  `--promote` — an all-or-nothing gate with no reason capture.
- `admission.py::admit_candidates()` (`recipe_builder/admission.py:52-91`) already
  produces `AdmissionDecision(subject_id, decision, reasons: list[str])` — but this
  is the **automated, rule-based** staging decision (accepted_to_stage /
  review_required / rejected, driven purely by `ValidationIssue` severity,
  `admission.py:23-43`), not a human's final admit-to-catalog decision. Candidates
  marked `review_required` are exactly the ones needing the human session this task
  builds; `accepted_to_stage` candidates still benefit from a human pass before
  promotion, since passing deterministic validation is not the same as being a good
  creative fit for a coverage gap.
- **Opportunity model has no element-type field** (`recipe_builder/models.py:70-91`):
  `target_effect_type`, `target_energy`, `target_template_type`, `target_motions` —
  no field for the layout element type T1's coverage report identifies gaps against.
  `generate_candidates(opportunities: list[Opportunity], analysis, catalog_recipes,
  llm_client, dry_run, model, temperature)` (`recipe_builder/generation.py:616-624`)
  consumes exactly this `Opportunity` list — so without an `Opportunity` field
  carrying element-type, T1's gaps cannot reach the LLM prompt.
- `random.shuffle(candidates)` at `generation.py:277` is unseeded (P6-M1/determinism
  finding) — P1K-T5 owns seeding it; this task does not touch that line, only cites
  it as a known, separately-owned source of run-to-run variation in which exemplars
  the LLM sees.
- `recipe_builder`'s own safety framing (`pipeline.py:113-118`, `__init__.py:1-7`,
  `"The live library is never modified by this package"` outside a deliberate
  second `--promote` invocation) is the existing design this task must preserve,
  not weaken — this task adds a human decision gate, it does not remove the existing
  staged-only default.

## Current behavior

- `recipe_builder.evidence.identify_opportunities()` derives `Opportunity` objects
  purely from `CatalogAnalysis` (effect-type/energy/template-type distributions
  computed from the catalog alone, `evidence.py:197-355`) — it has never had any
  visibility into the author's actual layout or which element types are underserved.
- `generate_candidates()` produces `RecipeCandidate` objects via LLM (when a client
  is supplied) or a deterministic fallback (`generation.py:616+`), using
  `Opportunity.description`/targets to build the prompt via
  `format_analysis_for_prompt()` (`recipe_builder/evidence.py`, imported at
  `generation.py:19`).
- `admit_candidates()` classifies every candidate by validation-issue severity only
  — it has no concept of a human's creative judgment.
- `write_staged_outputs()` writes accepted/review-required candidates to
  `staged_recipes/*.json` (`admission.py:100-135`).
- `promote_staged_recipes()` promotes the entire `staged_recipes/` directory
  unconditionally (see Evidence above) — no selective promotion, no reason log.

## Target behavior

1. **Coverage-gap targeting.** Extend `Opportunity`
   (`recipe_builder/models.py:70-91`) with an optional
   `target_element_type: str | None = None` field (backward compatible — existing
   opportunity construction sites unaffected). Add a function that reads T1's
   coverage-report JSON (`P2K-T1-coverage-report-tooling.md`'s output schema) and
   emits `Opportunity` objects for each gap cell, with `category` set to whichever
   existing `Opportunity.category` literal fits best (likely
   `"missing_template_type"` or a new literal `"missing_layout_coverage"` if none
   fits cleanly — adding a literal to that `Literal[...]` union is in scope if
   needed, since it is additive and does not change existing values), `priority`
   derived from the gap's prominence rank (T1's pixel-weighted ranking, normalized
   into the existing `0.0-1.0` range), and `target_template_type`/`target_energy`/
   `target_element_type` set from the cell. Feed these gap-derived opportunities
   into `generate_candidates()` **alongside** (not instead of) the existing
   catalog-internal opportunities from `identify_opportunities()` — both are valid
   generation triggers; do not delete the existing gap-detection path.
2. **Prompt threading.** Ensure `target_element_type`, where set, reaches the LLM
   prompt (via `format_analysis_for_prompt()` or a small addition to the system/user
   prompt construction in `generation.py`) so the model is told which display
   element type the candidate should suit — today's prompt has no element-type
   awareness at all (verified: `SYSTEM_PROMPT` in `generation.py:48+` lists xLights
   effect types and their parameters, nothing about display models/element types).
3. **sol-tier, provider-framework generation.** Once P1K-T5 lands, this task's
   generation calls use the provider framework's sol-tier config (explicit
   `reasoning.effort` per D6) instead of the current bare `model: str = "gpt-4.1"`
   parameter (`generation.py:622`) — this task supplies the config wiring on top of
   P1K-T5's framework migration; do not re-implement the provider-framework client
   construction here.
4. **Human admission session tooling.** Build a session tool (CLI, following this
   phase's established convention — coordinate with P1K-T4/P2K-T1 on whether it's a
   subcommand or a script) that, given a `staged_recipes/` directory from a
   generation run:
   - Presents each staged candidate one at a time (recipe name, effect family,
     energy, template type, target element type if set, layer summary — reuse the
     existing per-recipe summary format from `demo_recipe_builder.py:250-259` as a
     starting point) together with the automated `AdmissionDecision` and its
     `reasons` for context.
   - Prompts the human for an admit/reject decision and a free-text reason for
     **every** candidate — no default/skip that silently admits or rejects.
   - Writes a session log artifact (JSON or JSONL, one row per candidate:
     `{recipe_id, opportunity_category, target_element_type, automated_decision,
     human_decision: "admit"|"reject", reason, timestamp}`) alongside the run's
     other artifacts (same `output_dir`/`run_name` convention as
     `recipe_builder.pipeline.PipelineConfig`).
   - Filters promotion to exactly the human-admitted `recipe_id`s. Extend
     `promote_staged_recipes()` with an optional `candidate_ids: set[str] | None =
     None` parameter (default `None` preserves today's promote-everything behavior
     for any other caller, e.g. P1K-T4's end-to-end verification) — when a session
     log is available, the new session tool calls it with the admitted ID set,
     never with `None`.
5. **Feed the log forward.** The session log's `reason` field, especially on
   `reject`, is exactly the "per-session log of admit/reject reasons feeds prompt
   refinement" the plan calls for — this task's deliverable stops at producing that
   log durably; actually revising `SYSTEM_PROMPT` based on accumulated reasons is
   this phase's iterative curation work (subsequent sessions), not a one-shot code
   change in this task. Do not have the agent unilaterally rewrite the prompt from
   a single session's rejections — that would be exactly the "autonomous agent
   authoring of taste" this task is scoped to avoid.

## Implementation approach

- Files touched: `recipe_builder/models.py` (`Opportunity.target_element_type`,
  possibly one new `category` literal), a new function (e.g.
  `recipe_builder/evidence.py::opportunities_from_coverage_gaps()` or a sibling
  module) reading T1's report schema, `recipe_builder/generation.py` (prompt
  threading for `target_element_type`), `recipe_builder/promotion.py`
  (`candidate_ids` filter parameter), and a new session-tool entry point (CLI
  script or subcommand per the phase's converging convention).
- Do not modify `admission.py`'s automated classification logic — the human
  session tool consumes its output as context, it does not replace it.
- Depends on P1K-T4 for the "first-class command" surface this session tool should
  plug into, P1K-T5 for the provider-framework/sol-tier generation call, and
  P2K-T1 for the coverage-report schema this reads. Re-verify all three landed
  interfaces before wiring — they are concurrent work.

## Acceptance criteria

- [ ] `Opportunity` carries an optional `target_element_type`; existing
  construction call sites are unaffected (field is optional, backward compatible).
- [ ] A function converts T1's coverage-gap cells into `Opportunity` objects with
  correct field mapping and prominence-derived priority.
- [ ] Generated candidates targeting a coverage gap carry that element-type context
  into the LLM prompt (verifiable via a dry-run/deterministic-fallback test — no
  live LLM call required for this criterion).
- [ ] The session tool requires an explicit admit/reject + reason for every staged
  candidate before it will promote anything — there is no path that promotes a
  candidate absent from the session log.
- [ ] `promote_staged_recipes(candidate_ids=...)` promotes exactly the given ID set;
  calling it with `candidate_ids=None` preserves today's promote-everything
  behavior (regression check against P1K-T4's end-to-end verification).
- [ ] The session log is written durably (JSON/JSONL under the run's output
  directory) with one row per candidate reviewed, including the human's reason.
- [ ] No code path in this task calls `promote_staged_recipes` without a
  human-authored session log behind the ID set passed to it.

## Tests

- Unit test: `opportunities_from_coverage_gaps()` against a small synthetic
  coverage-report fixture, asserting field mapping (element type, role, energy,
  priority ordering) is correct.
- Unit test: `promote_staged_recipes(candidate_ids={...})` promotes only the given
  IDs from a fixture `staged_dir` with several files, and existing
  `promote_staged_recipes(...)` (no `candidate_ids`) call sites still promote
  everything (regression fixture reusing `recipe_builder`'s existing promotion
  tests where possible).
- Unit test: session-log writer produces one row per candidate with all required
  fields, given a scripted sequence of admit/reject inputs (mock the interactive
  prompt — do not require a live terminal in CI).
- Dry-run/deterministic-fallback test: `generate_candidates()` given an
  `Opportunity` with `target_element_type` set produces a prompt/candidate that
  reflects that targeting (assert on the constructed prompt text or the
  deterministic-fallback candidate's tags/metadata, whichever is inspectable
  without a live LLM call).

## Verification commands

```bash
uv run mypy packages/twinklr/core/recipe_builder/
uv run ruff check packages/twinklr/core/recipe_builder/
uv run pytest tests/unit/recipe_builder/ -q
uv run python scripts/demo_recipe_builder.py --dry-run --phase generation  # deterministic fallback, no LLM cost
# LOCAL-ONLY, owner session, real cost: live LLM generation + interactive admission session
uv run python <session-tool-entry-point> --staged-dir <run-output>/staged_recipes --run-dir <run-output>
```

## Effort & risk

**L**, owner-session-gated for the actual curation pass; the tooling build itself is
M. Main risk: building the human-admission tool as a true interactive CLI session
that is also unit-testable — mitigate by separating the interactive I/O loop from
the decision-recording/promotion-filtering logic (test the latter with scripted
inputs, not a real terminal). Secondary risk: scope creep into rewriting the LLM
prompt based on session results — the acceptance criteria explicitly stop this
task's code changes at logging reasons durably, not acting on them; a verifier
should reject any `SYSTEM_PROMPT` rewrite bundled into this task's diff.
