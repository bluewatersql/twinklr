# P0-T4 — Minimal CI

Phase: 0-foundation · Lane: A (config/tooling, serial: T1→T2→T3→T4) · Executor: sonnet ·
Verifier: opus · Depends on: P0-T1, P0-T2, P0-T3

## Objective

Add a GitHub Actions workflow that runs the project's quality gates
(`uv sync` → `ruff format --check` → `ruff check` → `mypy` → `pytest`) on every push/PR,
check-only (no mutation), plus a version-consistency check across the repository's
version declaration sites; and add the missing `git diff --exit-code` guard so
`make validate` (and any CI-safe variant of it) fails loudly if a quality-gate step
silently mutates tracked files instead of just reporting.

## Evidence & background

- **Finding SF-7** (`changes/twinklr-reactivation-review/reviews/findings.md`):
  "Engineering system: no quality-gate CI; validate mutates; packaging nonfunctional
  ... FIX → RM-0.*."
- **Finding P7-F6** (revised; `reviews/verification.md` §"Phase 7"): "`make validate`'s
  mutate-then-test design is unsafe to reuse verbatim as a CI gate" — REVISED
  MEDIUM (was HIGH): "the git-clean checkpoint guard this finding calls for **already
  exists in the Makefile**, just not wired to `validate`" —
  `lint-fix-unsafe-apply` (`Makefile:79-87`, re-verified below) implements exactly a
  `git diff --quiet && git diff --cached --quiet || { echo Error: uncommitted
  changes...; exit 1; }` checkpoint before mutating. "`make lint` (`ruff check .`, no
  `--fix`), `make type-check` (`mypy .`), and `make test` (`pytest tests/ -v`) are each
  already non-mutating, CI-safe targets on their own today — a CI workflow could call
  all three directly right now with no Makefile changes. The one missing piece for a
  fully check-only CI variant of `validate` is formatting: `ruff format .` (mutating)
  has no check-only sibling (`ruff format --check .`) anywhere in the file."
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`,
  full `Makefile` read, 365 lines):
  - `.github/workflows/` contains exactly one file, `jekyll-gh-pages.yml` (confirmed via
    `ls .github/workflows/`), which builds/deploys the Jekyll docs site on push to
    `main` and manual dispatch. It runs no `ruff`, `mypy`, `pytest`, or `uv` command of
    any kind — confirmed by reading the full file (37 lines): only
    `actions/checkout@v4`, `actions/configure-pages@v5`,
    `actions/jekyll-build-pages@v1`, `actions/upload-pages-artifact@v3`,
    `actions/deploy-pages@v4`.
  - `Makefile:79-87` — the `lint-fix-unsafe-apply` target's guard, re-read verbatim:
    ```makefile
    lint-fix-unsafe-apply: ## Apply unsafe fixes with git checkpoint (undo with: git restore .)
    	@echo "$(YELLOW)→ Creating git checkpoint...$(NC)"
    	@git diff --quiet && git diff --cached --quiet || { \
    		echo "$(RED)Error: You have uncommitted changes. Commit or stash first.$(NC)"; \
    		exit 1; \
    	}
    	@echo "$(BLUE)→ Applying unsafe fixes...$(NC)"
    	@uv run ruff check . --fix --unsafe-fixes
    	@echo "$(GREEN)✓ Unsafe fixes applied$(NC)"
    	@echo "$(YELLOW)→ To undo: git restore .$(NC)"
    ```
    This pattern (pre-flight `git diff --quiet` check, not a post-hoc `--exit-code`
    check) exists nowhere on `validate` (`Makefile:148-175`, full target re-read below)
    or any of `lint`/`format`/`type-check`/`test`.
  - `validate` (`Makefile:148-175`, re-read verbatim): runs, in order,
    `uv run ruff format .` (mutating), `uv run ruff check . --fix` (mutating),
    `uv run mypy .` (non-mutating), `uv run pytest tests/ -v` (non-mutating), tracking a
    single `$$EXIT_CODE` across all four and reporting pass/fail at the end. It has no
    git-state check at all, before or after.
  - `lint` (`Makefile:64-67`) = `uv run ruff check .` — no `--fix`, confirmed
    non-mutating. `type-check` (`Makefile:95-98`) = `uv run mypy .` — confirmed
    non-mutating. `test` (`Makefile:104-107`) = `uv run pytest tests/ -v` — confirmed
    non-mutating. `format` (`Makefile:90-93`) = `uv run ruff format .` — mutating, no
    check-only variant exists in the file today (confirmed: `grep -n "format --check"
    Makefile` → 0 hits).
  - Version declaration sites (re-confirmed, 4 files / values, per phase-1 review
    §4.9 "Version drift", cross-checked directly): root `pyproject.toml:5` → `"0.2.0"`;
    `packages/twinklr/core/pyproject.toml:3` → `"0.1.0"`;
    `packages/twinklr/cli/pyproject.toml:3` → `"0.1.0"`;
    `packages/twinklr/core/__init__.py:3` → `__version__ = "0.2.0"`. **Four
    declarations, two distinct values, no sync mechanism** — confirmed via direct
    `grep -n "^version"`/`grep -n "__version__"` across all four files. The plan's task
    table describes this as "version-consistency check across the 5 version declaration
    sites" — this spec finds and confirms exactly **4** sites, not 5; re-verify on your
    checkout (`grep -rn "^version = \|__version__" pyproject.toml packages/twinklr/*/pyproject.toml packages/twinklr/core/__init__.py packages/twinklr/cli/`)
    before building the check, in case a 5th site exists that this pass missed (e.g. a
    `packages/twinklr/cli/__init__.py` `__version__`, not confirmed present or absent by
    this evidence pass — check directly).

## Notes for spec authors (from `build/plan/00-overview.md`, copied verbatim)

> `make validate` equivalents (check-only forms until P0-T4 lands the guard) must pass at
> every merge; golden tests (once P1P-T1 exists) must pass for any lane touching
> render/export code.

This task **is** the point at which that "check-only forms" caveat resolves — after this
task lands, later phases' merge gates should reference the real CI workflow this task
adds, not an ad hoc check-only invocation.

## Current behavior

- No CI enforces `ruff`, `mypy`, or `pytest` at any point (push, PR, or otherwise). Every
  quality gate is local-manual only.
- `make validate` mutates the working tree via `ruff format .` and `ruff check . --fix`
  before running the non-mutating checks, and reports success/failure based on the
  *post-mutation* state, with **no** git-cleanliness guard anywhere in the target.
- `make lint`, `make type-check`, `make test` are each already non-mutating in isolation
  but nothing composes them into a single CI-safe command with a `ruff format --check`
  equivalent for the formatting step.
- The workspace declares its version in 4 (possibly 5 — re-verify) separate places with
  no automated check that they agree, and they currently disagree (`0.2.0` root vs.
  `0.1.0` both sub-packages).

## Target behavior

- A new GitHub Actions workflow (e.g. `.github/workflows/ci.yml`) runs on `push` and
  `pull_request`, provisions the toolchain via `uv` (the phase-7 review's own
  recommendation: "`astral-sh/setup-uv` (official action) ... is the natural,
  lowest-friction addition. No case for a heavier alternative"), and runs, check-only,
  in order: `uv sync --extra dev --all-packages` → `ruff format --check .` →
  `ruff check .` → `mypy .` → `pytest tests/ -v` → the version-consistency check. Any
  step failing fails the workflow; nothing in the workflow mutates the checked-out tree.
- `make validate` (local, unchanged interactive behavior — format + lint-fix + type-check
  + test, mutating) gains a `git diff --exit-code` (or equivalent pre-flight `git diff
  --quiet`, matching the existing `lint-fix-unsafe-apply` idiom) guard so that if a
  developer runs `make validate` against a dirty tree, or a mutation step produces
  unexpected changes, this is surfaced rather than silently absorbed into "success."
  The phase-7 review is explicit this should **not** turn `validate` into a check-only
  target (that ergonomic choice is correct and should not be changed) — the guard is
  about honesty of the mutate-then-report pattern, not about removing mutation.
- A new `make version-check` (or equivalent) target and/or a small script verifies all
  version declaration sites agree, runnable both locally and from CI.

## Implementation approach

**1. Version-consistency check.**

Write a small script (e.g. `scripts/check_version_consistency.py`, or a `Makefile`
target using `grep`/`sed` if that's simpler and sufficiently robust — executor's choice)
that reads every version declaration site (re-confirm the exact count/sites per Evidence
above — start from the 4 confirmed, verify whether a 5th exists) and exits non-zero with
a clear diff if they disagree. Wire it as a new `Makefile` target
(e.g. `version-check: ## Verify version declarations agree across all sites`) so it's
locally runnable, and call that target from the new CI workflow. Do **not** use this
task to *fix* the current version drift (`0.2.0` vs `0.1.0`) — that's a product decision
outside this task's scope (bumping/aligning versions is not "foundation honesty," it's a
release decision); the check should fail loudly today (documenting the drift honestly)
and the fix is deferred. Confirm this framing with the orchestrator if it's ambiguous —
default to "check exists and correctly fails on current drift" as the acceptance bar,
not "versions are unified."

**2. CI workflow.**

Create `.github/workflows/ci.yml` (do not touch `jekyll-gh-pages.yml` — separate,
unrelated workflow, already working, out of scope):

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  quality-gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v... # pin a version; check current stable tag
        with:
          python-version: "3.12"
      - name: Sync workspace
        run: uv sync --extra dev --all-packages
      - name: Format check
        run: uv run ruff format --check .
      - name: Lint
        run: uv run ruff check .
      - name: Type check
        run: uv run mypy .
      - name: Test
        run: uv run pytest tests/ -v
      - name: Version consistency
        run: make version-check   # or the equivalent direct invocation
```
Adjust exact action versions/pins to whatever is current and stable at implementation
time — this is illustrative structure, not a literal pin list. Confirm the `uv sync`
network-flakiness note from Stage 4 ("first attempt failed on network — scipy timeout +
DNS loss — classified ENVIRONMENTAL and retried successfully with
`UV_HTTP_TIMEOUT=180`") — consider setting `UV_HTTP_TIMEOUT` in the workflow env to
reduce CI flakiness from the same class of transient failure, though this is a
robustness nicety, not a hard requirement.

Depends on **P0-T1, P0-T2, P0-T3 landing first** (per this task's own `Deps` column) —
without them, this CI workflow would be red from the moment it's added, which defeats
its purpose as a gate. Confirm all three have landed (or land in the same change) before
merging this workflow.

**3. `make validate` git-diff guard.**

Add a pre-flight guard to `validate` (`Makefile:148-175`) using the same idiom already
proven in `lint-fix-unsafe-apply` (`Makefile:79-87`) — a `git diff --quiet && git diff
--cached --quiet || { ...error...; exit 1; }` check. Place it at the **start** of
`validate`, before the four mutating/checking steps, so a developer running `validate`
against a dirty tree gets a clear, actionable error instead of a report that conflates
their pre-existing uncommitted changes with whatever `ruff format`/`ruff check --fix`
produces. This matches the finding's framing: "the concern here is architectural, not a
bug: it mutates the working tree ... with no `git diff --exit-code` or equivalent guard
on `validate` itself." Do not add a *post*-mutation check that would block the target
from ever succeeding when it does its job (format/fix are supposed to change files) —
the guard is about the *starting* state being clean, matching
`lint-fix-unsafe-apply`'s existing pattern exactly, not about a post-run diff.

## Acceptance criteria

- `.github/workflows/ci.yml` exists, triggers on `push`/`pull_request`, and runs
  `uv sync` → `ruff format --check .` → `ruff check .` → `mypy .` → `pytest tests/ -v` →
  version-consistency check, all check-only (no step mutates tracked files).
- The new CI workflow is green against the tree once P0-T1..T3 have landed (verify by
  running the same commands locally in the stated order).
- `.github/workflows/jekyll-gh-pages.yml` is unmodified.
- `make validate` gains a pre-flight `git diff --quiet && git diff --cached --quiet`
  guard (or equivalent) matching `lint-fix-unsafe-apply`'s existing idiom, and running
  `make validate` against a dirty tree now fails fast with a clear message instead of
  proceeding.
- A `make version-check` (or equivalently named) target exists, is callable standalone,
  and correctly fails today (documenting current version drift) until a future task
  chooses to align the versions.
- `make lint`, `make type-check`, `make test`, `make format` remain unchanged in
  behavior (this task adds, it does not alter, those targets).

## Tests

No new pytest tests — this is CI/Makefile infrastructure. Validation is functional: run
the new CI steps and the new `make validate`/`make version-check` targets locally and
confirm their exit codes match the stated acceptance criteria (dirty tree → `validate`
fails at the guard; clean tree with the current version drift → `version-check` fails
with a clear diagnostic; clean tree, all gates passing → CI workflow green end to end).

## Verification commands

```bash
# Simulate the new CI workflow locally, in order
uv sync --extra dev --all-packages
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/ -v
make version-check   # should fail today, documenting the 0.2.0/0.1.0 drift

# Confirm the validate guard
git status  # ensure a dirty tree for this test
make validate   # should fail immediately at the new guard, not proceed to ruff format

git stash  # clean the tree
make validate   # should proceed normally (mutating as designed) and report pass/fail

# Confirm jekyll workflow untouched
git diff .github/workflows/jekyll-gh-pages.yml   # expect no output
```

## Effort & risk

**S–M** (small to medium). Main risks: (1) pinning `astral-sh/setup-uv`'s action version
— use whatever is current/stable at implementation time, don't guess a specific SHA that
may be stale by the time this lands; (2) the version-consistency check must correctly
distinguish "5 sites, need to re-audit" from this spec's confirmed 4 — re-run the grep
in Evidence before finalizing the site list, since a missed site would make the check
falsely pass; (3) sequencing — this task is explicitly gated on T1–T3 landing; do not
merge the CI workflow before confirming a clean local run of all four gate commands,
since a red CI workflow from day one undermines its purpose as a gate for every later
phase.
