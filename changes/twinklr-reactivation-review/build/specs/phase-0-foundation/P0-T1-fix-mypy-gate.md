# P0-T1 — Fix the mypy gate

Phase: 0-foundation · Lane: A (config/tooling, serial: T1→T2→T3→T4) · Executor: sonnet ·
Verifier: sonnet · Depends on: —

## Objective

Make `uv run mypy .` exit 0 from a clean checkout by renaming a reused loop variable in
`recipe_builder/admission.py`. This is the entire mypy gap — no other mypy errors exist
repo-wide.

## Evidence & background

- **Finding P6-M3** (`changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
  §"CANDIDATE FINDINGS"): "The repo-wide mypy gate failure attributable to this phase's
  scope (Stage 4) is a one-variable fix, not a live crash risk: `recipe_builder/admission.py:72`
  and `:105` reuse a loop variable typed `RecipeCandidate`, rebound at `:113` to
  `MetadataEnrichmentCandidate`. Runtime-correct (Python tolerates it; the two loop bodies
  never conflate fields), but a real type-narrowing violation mypy correctly flags."
- **Stage 4 runtime baseline** (`reviews/verification.md` §"Stage 4 runtime baseline"):
  `uv run mypy .` → exit 1, **4 errors** in `recipe_builder/admission.py`
  (`RecipeCandidate` missing `target_recipe_id`/`proposed_metadata_patch` — attr-defined),
  666 files checked. "and in the exact subsystem the last real code commit (`d9c6ae1`,
  2026-04-01) touched."
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`):
  running `uv run mypy .` today produces exactly:
  ```
  packages/twinklr/core/recipe_builder/admission.py:72: error: Incompatible types in assignment (expression has type "MetadataEnrichmentCandidate", variable has type "RecipeCandidate")  [assignment]
  packages/twinklr/core/recipe_builder/admission.py:113: error: Incompatible types in assignment (expression has type "MetadataEnrichmentCandidate", variable has type "RecipeCandidate")  [assignment]
  packages/twinklr/core/recipe_builder/admission.py:119: error: "RecipeCandidate" has no attribute "target_recipe_id"  [attr-defined]
  packages/twinklr/core/recipe_builder/admission.py:121: error: "RecipeCandidate" has no attribute "proposed_metadata_patch"  [attr-defined]
  Found 4 errors in 1 file (checked 666 source files)
  ```
  No other file in the repository has a mypy error.

## Current behavior

`packages/twinklr/core/recipe_builder/admission.py` defines two functions that each
iterate over two different candidate lists using the **same loop-variable name**,
`candidate`:

- `admit_candidates()` (lines 53-96): `for candidate in recipe_candidates:` (line 66,
  inferred type `RecipeCandidate`) followed later in the same function by
  `for candidate in metadata_candidates:` (line 72, inferred type
  `MetadataEnrichmentCandidate`). mypy narrows `candidate` to `RecipeCandidate` from the
  first loop and flags the second loop's rebind as an incompatible assignment (line 72).
- `write_staged_outputs()` (lines 98-131): `for candidate in recipe_candidates:` (line
  105, `RecipeCandidate`) followed by `for candidate in metadata_candidates:` (line 113,
  `MetadataEnrichmentCandidate`) — same pattern, same error at line 113. Because mypy has
  narrowed `candidate` to `RecipeCandidate`, the two attribute accesses inside the second
  loop body — `candidate.target_recipe_id` (line 119) and
  `candidate.proposed_metadata_patch` (line 121), both real fields on
  `MetadataEnrichmentCandidate`, not on `RecipeCandidate` — are flagged as
  `attr-defined` errors.

The code is **runtime-correct**: Python's dynamic typing tolerates the rebinding, and
neither loop body ever accesses a field from the wrong type. This is a pure type-checker
narrowing artifact, not a live bug.

## Target behavior

`uv run mypy .` exits 0 with the same 666 files checked and zero errors. No behavioral
change to `admit_candidates()` or `write_staged_outputs()` — output, control flow, and
all field accesses remain identical.

## Implementation approach

In `packages/twinklr/core/recipe_builder/admission.py`, rename the loop variable in the
**second** loop of each function (the one iterating `metadata_candidates`) to a distinct
name, e.g. `metadata_candidate`, and update the loop body's references accordingly:

- `admit_candidates()`: `for candidate in metadata_candidates:` → `for metadata_candidate in metadata_candidates:`, updating the body's `result_by_id.get(candidate.candidate_id)` → `result_by_id.get(metadata_candidate.candidate_id)`, the fallback `CandidateValidationResult(candidate_id=candidate.candidate_id, ...)` → `CandidateValidationResult(candidate_id=metadata_candidate.candidate_id, ...)`, and `_classify_decision(result)` call unaffected (no `candidate` reference).
- `write_staged_outputs()`: `for candidate in metadata_candidates:` → `for metadata_candidate in metadata_candidates:`, updating `_get_decision_for(candidate.candidate_id, ...)`, `candidate_id=candidate.candidate_id`, `target_recipe_id=candidate.target_recipe_id`, `patch=candidate.proposed_metadata_patch` to use `metadata_candidate`.

Do not rename the first loop's variable (`recipe_candidates` iteration) — it is already
correctly typed and unambiguous once the second loop's name changes. Do not touch any
other file; the finding and the re-verification above both confirm this is the sole
mypy failure repo-wide.

**Re-verify line numbers before editing** — this spec's citations are hints from baseline
`aa8d325`; confirm against `uv run mypy .` output on your checkout before making the
edit, since the tree may have drifted if other Phase 0 tasks landed first.

## Acceptance criteria

- `uv run mypy .` exits 0, checking the same or greater file count, zero errors.
- `git diff` touches only `packages/twinklr/core/recipe_builder/admission.py`, and the
  diff is a variable rename (no logic/behavior change).
- `admit_candidates()` and `write_staged_outputs()` produce byte-identical output to
  before the change for the same inputs (verified by existing tests, not new ones).

## Tests

No new tests required — this is a pure type-annotation-level fix with no behavioral
change. The existing `recipe_builder` test suite
(`tests/unit/recipe_builder/test_admission.py`) already exercises both functions and
must continue to pass unmodified, confirming the rename did not alter behavior.

## Verification commands

```bash
uv run mypy .
uv run pytest tests/unit/recipe_builder/test_admission.py -v
git status   # confirm only admission.py changed
```

## Effort & risk

**S** (extra-small). Risk: near-zero — a mechanical rename confined to one file with
existing test coverage. The only care point is updating all four references inside each
renamed loop body (not just the `for` statement itself), or mypy will report new
`NameError`-adjacent complaints and pytest will fail immediately if a reference is
missed.
