---
type: learning
status: active
created: 2026-02-01
updated: 2026-08-13
confidence: confirmed
tags: [testing, baseline]
---

# Verified Quality-Gate Baseline on `main` (2026-08-13, commit aa8d325)

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

Do not treat any of these 120 as regressions caused by new work, and do not claim
the suite is green. Remediation: reactivation-review roadmap items RM-0.1..0.4.
