# Phase 0 — Foundation Honesty

_Goal: a clean checkout passes its own quality gates; packaging works; onboarding
docs tell the truth. Everything here is small, evidence-backed, and unblocks every
later phase. Proposal M0; roadmap RM-0.x._

**Exit criteria:** fresh clone → `uv sync` → CI pipeline (P0-T4) green; `uv build`
produces non-empty wheels with no tree pollution; no doc instructs a workflow that
does not work.

## Lanes

- **Lane A (config/tooling)**: T1 → T2 → T3 → T4 (serial: each changes gate outcomes).
- **Lane B (packaging)**: T5 (independent).
- **Lane C (onboarding/docs)**: T6, T7 (independent of A after T1).

## Tasks

| ID | Title | What (summary) | Evidence | Deps | Executor | Verifier |
|---|---|---|---|---|---|---|
| P0-T1 | Fix the mypy gate | Rename the reused loop variable in `recipe_builder/admission.py` (`candidate` rebound across loops → 4 attr-defined errors; runtime correct). Whole-repo mypy goes green with one rename. | P6-M3, Stage 4 baseline | — | sonnet | sonnet |
| P0-T2 | Structural test repair | Delete the 60 tests targeting nonexistent `scripts/build/*` tools; add a `requires_template_data` marker + fixture-presence skip for the 52 `data/templates`-dependent tests AND commit a minimal tracked template fixture set so a representative subset runs everywhere; vendor/pre-fetch the NLTK `averaged_perceptron_tagger_eng` resource for offline runs. | CC-2, CC-7, Stage 4 classification | — | sonnet | opus |
| P0-T3 | Format/lint baseline | One `ruff format` commit; triaged `ruff check --fix` commit; unify ruff/mypy config so `packages/twinklr/core` gets the root strict ruleset (today it resolves the weak 7-family core config — empirically confirmed); delete or align `pyrightconfig.json`. Budget for the new-rule wave. | P1-F20 (CONFIRMED), Stage 4 | P0-T1, P0-T2 | sonnet | sonnet |
| P0-T4 | Minimal CI | GitHub Actions check-only pipeline: `uv sync` → `ruff format --check` → `ruff check` → `mypy` → `pytest` (+ version-consistency check across the 5 version declaration sites). Add the missing `git diff --exit-code` guard to `make validate` (pattern already exists in-file at `lint-fix-unsafe-apply`). | SF-7, P7-F6 (revised) | P0-T1..T3 | sonnet | opus |
| P0-T5 | Packaging that works | Adopt the `uv_build` backend per package; delete the `find_packages("../..")` setup.py shims (they produce EMPTY wheels + a nested source-tree copy — empirically confirmed); fix `make build` paths. Acceptance: wheels contain code; `git status` clean after build. | P1-F23 (CONFIRMED), CC-2 | — | sonnet | sonnet |
| P0-T6 | Onboarding truth | Resolve the `.env` illusion one way (recommended: `pydantic-settings` adoption for env/config layering per P1 §7, which also fixes env-read-once and empty-string-key findings; alternative: delete the documented `.env` option) + fix `make env-check`'s false "✓ OPENAI_API_KEY is set"; fix the two `PipelineContext` docstring constructors that raise TypeError. | P7-F1/P1-F3 (consolidated), P1-F17/F19, P1-M2 | — | sonnet | sonnet |
| P0-T7 | Kill the trivially-dead config | Delete (not wire) the config surfaces already adjudicated dead-with-no-intent: `TokenBudgetManager` class, `OrchestrationStateMachine`, `pipeline/stages.py`, `checkpoint`/`checkpoint_dir` fields (superseded by P1P-T10's writer), inert `critical`/`fail_fast`/`PARALLEL`/`CONDITIONAL`-redundancy in the executor per P1-F5/F6/M4. Larger dead-code retirement waits for Phase 4 (sequencing traps). | CC-1 subset, P1-M4, P1 §6 | P0-T4 (CI protects) | sonnet | opus |

## Notes for spec authors

- T2's tracked-fixture decision is design-bearing: pick the smallest recipe/template
  set that lets `test_engine.py`-class tests assert real behavior (coordinate with
  P1K-T4's seed catalog — same data, one home).
- T3 must record the expected new-violation count from applying strict rules to core
  BEFORE the fix commit (honest diff).
- T7 explicitly must NOT touch: `success_threshold`, `max_iterations`, `judge_agent`,
  channel/fixture defaults, `Template.defaults` — those get WIRED (not deleted) in
  P1P/P2P tasks.
