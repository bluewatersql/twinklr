---
type: learning
status: historical
created: 2026-02-01
updated: 2026-08-14
confidence: confirmed
tags: [testing, baseline]
---

# Historical Quality-Gate Baseline (2026-08-13, commit `aa8d325`)

> **Historical baseline, not current test status.** The build campaign repaired this
> classified failure set. At integrated snapshot `6b2b34a`, fresh `make validate`
> passed with **5,239 tests passed, 39 skipped**, clean Ruff formatting/lint, and mypy
> success across **718 source files**. Keep the record below because it explains the
> review's starting point; do not use it to waive a new failure or claim that current
> `main` is red.

**The Feb 2026 auto-memory claim of "four pre-existing test failures" is REFUTED in
both directions** by a fresh run (uv-managed Python 3.12.13, clean checkout,
check-only commands; full logs referenced from
[the reactivation review's verification record](../../changes/twinklr-reactivation-review/reviews/verification.md)):

- All four previously-listed tests **pass** (`test_learning_context_formatting`,
  three `test_execute_step_*`).
- The real baseline: **120 failed, 4040 passed, 15 skipped**, and `make validate`
  fails four independent ways (13 files unformatted; 150 ruff errors; 4 mypy errors
  in `recipe_builder/admission.py` — a loop-variable-reuse false positive, runtime
  correct, one-rename fix; the test failures).

Failure classification (all 120 accounted for):

- **60** — tests for six `scripts/build/*` tools that do not exist in the tree
  (never-passing).
- **52** — tests depending on gitignored `data/templates/index.json` (no clean
  checkout can pass them).
- **8** — NLTK resource not downloaded (`averaged_perceptron_tagger_eng`) —
  environmental, but "unit tests need a live download" is itself a defect.

At that baseline, none of these 120 could be treated as a regression caused by the
review itself, and the suite could not be called green. The completed foundation work
subsequently addressed roadmap items RM-0.1..0.4; current gate evidence is owned by
[context/current-state.md](../../context/current-state.md).
