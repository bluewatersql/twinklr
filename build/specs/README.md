# Task Specifications

_One spec per plan task. Generated from `build/plan/*.md` + the verified review
evidence (`changes/twinklr-reactivation-review/reviews/`). File naming:
`phase-<slug>/<TASK-ID>-<kebab-title>.md`._

## Spec template (mandatory sections)

```markdown
# <TASK-ID> — <Title>

Phase: <phase> · Lane: <lane> · Executor: <model> · Verifier: <model> · Depends on: <ids>

## Objective
One paragraph: the outcome, in behavior terms.

## Evidence & background
Finding IDs + the verified mechanics (quoted or tightly summarized so the executor
cannot re-derive a different bug). File/symbol references (line numbers are hints
from baseline aa8d325 — re-verify before editing).

## Current behavior
What the code does today (verified).

## Target behavior
What it must do after this task. Explicit non-goals where scope could creep.

## Implementation approach
Files/symbols to touch; design decisions already made (don't relitigate); the
sequencing constraints that apply (copied from the plan overview, verbatim).

## Acceptance criteria
Checkable statements. For render-path tasks: golden-diff BEFORE/AFTER expectations.

## Tests
New/changed tests, with the behavior each pins. TDD where behavior is definable
in advance (failing test first).

## Verification commands
Exact commands the verifier runs (check-only forms). LOCAL-ONLY markers for
xLights-GUI / paid-API steps.

## Effort & risk
S/M/L + the main risk and its mitigation.
```

## Rules

- Specs are self-contained: an executor with no session history must be able to
  implement from the spec + the referenced evidence docs alone.
- Every sequencing constraint from `build/plan/00-overview.md` that touches the task
  is copied into the spec verbatim.
- ⚖-marked tasks (owner-decision-bearing) say so at the top and name what the owner
  reviews.
- No spec authorizes remote pushes, paid API calls beyond its stated test budget, or
  edits outside its file list without orchestrator sign-off.
```
