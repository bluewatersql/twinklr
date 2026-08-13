# P0-T6 — Onboarding truth

Phase: 0-foundation · Lane: C (onboarding/docs, independent of Lane A after T1) ·
Executor: sonnet · Verifier: sonnet · Depends on: —

⚖ **Owner-decision-bearing.** This task contains one product-level fork the owner should
confirm before or during implementation: whether to adopt `pydantic-settings` for
env/config layering (the plan's recommendation) or to simply delete the non-functional
`.env` documentation option. See "Implementation approach" step 1 for what the owner
reviews.

## Objective

Resolve the `.env` illusion one way — either by adopting `pydantic-settings` for
env/config layering (recommended, and it additionally fixes the env-read-once and
empty-string-API-key findings as a side effect) or by deleting the documented `.env`
option — fix `make env-check`'s false "✓ OPENAI_API_KEY is set" report, and fix the two
`PipelineContext` docstring constructor examples that currently raise `TypeError` if a
reader copies them verbatim.

## Evidence & background

- **Findings P7-F1/P1-F3 (consolidated)** and **P1-F17/F19**, **P1-M2**
  (`changes/twinklr-reactivation-review/reviews/findings.md`).
- **P7-F1** (REVISED MEDIUM, was HIGH; `reviews/verification.md` §"Phase 7"):
  "`docs/user-guide.md` 'Option 2: .env file' documents a non-functional setup path" —
  "CLI failure is loud with remedy printed; the deceptive part is `make env-check`'s
  '✓ set' after grepping only the file. Prefer deleting the `.env` option + fixing
  env-check over adding python-dotenv."
- **P1-F3** (`reviews/phases/foundation-and-orchestration.md` §4.7): "`.env` is never
  loaded. No `dotenv` import exists in `packages/` or `scripts/`. `.env.example`
  documents four variables; a user who copies it to `.env` and runs `twinklr run` is
  told `OPENAI_API_KEY environment variable not set`."
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`):
  - `grep -rn "load_dotenv\|dotenv" packages/ scripts/` → **zero hits**. No `.env`
    loading mechanism exists anywhere in application code.
  - `.env.example` (full file, re-read) documents four variables:
    `OPENAI_API_KEY` (required), `GENIUS_ACCESS_TOKEN`, `ACOUSTID_API_KEY`, `HF_TOKEN`
    (all optional).
  - `docs/user-guide.md:65-99` (full "Environment Setup" section, re-read) presents
    "Option 1: Environment variable" (`export OPENAI_API_KEY=...`, works) and
    "Option 2: .env file" (`cp .env.example .env` + edit, **does not work** — nothing
    loads it) as equally-weighted, then documents `make env-check` as verifying ".env
    exists with OPENAI_API_KEY."
  - `Makefile:320-339` (`env-check` target, full body re-read):
    ```makefile
    env-check: ## Check environment setup
        ...
        @if [ -f ".env" ]; then \
            echo "  ✓ .env exists"; \
            if grep -q "OPENAI_API_KEY" .env; then \
                echo "  ✓ OPENAI_API_KEY is set"; \
            else \
                echo "  ⚠ OPENAI_API_KEY not found in .env"; \
            fi \
        else \
            echo "  ⚠ .env not found (copy from .env.example)"; \
        fi
    ```
    This greps the **file's contents** for the literal string `OPENAI_API_KEY` — it
    reports "✓ OPENAI_API_KEY is set" whenever the key **name** appears in `.env` at
    all, including with an **empty value** (`OPENAI_API_KEY=` — exactly what a user gets
    by copying `.env.example` unedited satisfies this grep) — and never checks the
    actual process environment, which is what the running CLI actually reads via
    `os.getenv("OPENAI_API_KEY")` (`cli/main.py:158`).
  - `packages/twinklr/cli/main.py:158-166` (re-read): the CLI's own failure mode is
    loud — `api_key = os.getenv("OPENAI_API_KEY")`, and if unset,
    `console.print("[red]ERROR: OPENAI_API_KEY environment variable not set[/red]")`
    plus the exact `export` remedy. This is the actually-honest signal; `env-check` is
    the deceptive one, per P7-F1's revised framing.
  - `packages/twinklr/core/config/models.py:430-433` (P1-F19): `llm_api_key: SecretStr =
    Field(default_factory=lambda: SecretStr(os.getenv("OPENAI_API_KEY", "")), ...)` — a
    missing key silently becomes an **empty-string** `SecretStr`, which fails only at
    the first LLM API call (a late, confusing failure for any caller that isn't the CLI,
    e.g. `scripts/*.py` or tests instantiating `AppConfig` directly), not at config-load
    time.
  - `packages/twinklr/core/config/loader.py:20,117-139` (P1-F17, re-read in full): a
    process-global `_app_config_cache`, populated on first `load_app_config()` call
    against the default path, and never invalidated — `_load_env_vars_into_config` (for
    AcoustID/Genius, not `OPENAI_API_KEY`, which is read directly via the
    `llm_api_key` default factory each time `AppConfig()` is constructed, not through
    this env-merge path) only runs on the cache-miss path. Environment variables are
    therefore effectively read once per process for the cached-default-path case, with
    no invalidation if the environment changes mid-process.
  - No `pydantic-settings` dependency currently exists in the workspace (`grep -n
    "pydantic-settings\|pydantic_settings" pyproject.toml
    packages/twinklr/core/pyproject.toml` → zero hits).
  - **`PipelineContext` docstring constructors** (P1-M2), both re-confirmed to raise
    `TypeError` by direct execution against the current tree:
    1. `packages/twinklr/core/pipeline/context.py:40-46` (the class's own docstring
       Example):
       ```python
       >>> context = PipelineContext(
       ...     provider=provider,
       ...     app_config=app_config,
       ...     job_config=job_config,
       ...     cache=fs_cache,
       ...     output_dir=Path("artifacts/demo"),
       ... )
       ```
    2. `packages/twinklr/core/pipeline/__init__.py:31` (package-level docstring
       Example): `>>> ctx = PipelineContext(provider=provider, config=config)`

    Both fail identically:
    `PipelineContext.__init__() got an unexpected keyword argument 'provider'`
    (confirmed via direct `uv run python -c "..."` execution against both exact
    snippets). The reason: `PipelineContext` (`context.py:20-69`) is a `@dataclass`
    whose **only** init field is `session: TwinklrSession` (plus optional
    `checkpoint_dir`, `output_dir`, `state`, `metrics`, `cancel_token`); `provider`,
    `app_config`, `job_config`, and `cache` are **read-only `@property` accessors**
    (`context.py:71-105`) that derive from `self.session`, not constructor parameters —
    a reader who copies either docstring example verbatim gets an immediate `TypeError`
    instead of a working `PipelineContext`. The one call site elsewhere in the docs that
    gets it right, `docs/pipeline_guide.md:694` —
    `PipelineContext(session=session, output_dir=Path("output/"))` — is correct and
    should be used as the reference for the fix (it uses the real field name,
    `session`).

## Notes for spec authors

No verbatim plan text is scoped to this task beyond what's captured in the plan's task
table row (`build/plan/01-phase-0-foundation.md` P0-T6). The "Notes for spec authors"
section in that file applies to T2/T3/T7, not T6 — no additional verbatim text to carry
here.

## Current behavior

- `docs/user-guide.md` presents a `.env`-file setup path that cannot work — no code
  anywhere loads `.env`.
- `make env-check` reports a false "✓ OPENAI_API_KEY is set" whenever the string
  `OPENAI_API_KEY` appears anywhere in `.env`, including as an empty, unedited
  placeholder from `.env.example` — it never checks the actual process environment the
  CLI reads from.
- A missing `OPENAI_API_KEY` silently becomes an empty-string credential rather than a
  config-load-time error, so non-CLI callers get a late, confusing failure at the first
  API call instead of an early, clear one.
- Environment-derived config values are cached process-globally on first load with no
  invalidation mechanism.
- Both documented ways to construct a `PipelineContext` in code comments/docstrings
  (`pipeline/context.py`'s own class docstring, `pipeline/__init__.py`'s package
  docstring) raise `TypeError` if executed as written.

## Target behavior

- The `.env` story is resolved one way, consistently, across code and docs (see
  Implementation approach step 1 for the fork):
  - **If adopting `pydantic-settings`**: `.env` is actually loaded (via
    `pydantic-settings`' built-in `.env` support), `docs/user-guide.md`'s "Option 2"
    becomes true, and the empty-string-key default (P1-F19) and env-read-once caching
    (P1-F17) are resolved as part of adopting `pydantic-settings`' settings-source
    layering (env > `.env` > file > defaults, with `pydantic-settings`' own validation
    surfacing a missing required key at settings-construction time rather than silently
    defaulting to `""`).
  - **If deleting the `.env` option**: `docs/user-guide.md` no longer presents `.env` as
    a working setup path; only "Option 1: Environment variable" remains, and
    `.env.example` is either deleted or re-labeled (e.g. as a reference list of variable
    names only, not an instruction to `cp` it) to avoid implying it's consumed
    automatically.
- `make env-check` tests the **actual process environment** (e.g.
  `[ -n "$$OPENAI_API_KEY" ]` or an `uv run python -c "import os; assert
  os.environ.get('OPENAI_API_KEY')"` check), not file contents, and reports accurately
  whether a `twinklr run` invocation in the current shell would find the key.
- Both `PipelineContext` docstring examples show a constructor call that actually works
  when copy-pasted (matching the pattern already correct at
  `docs/pipeline_guide.md:694`: `PipelineContext(session=session, ...)`).

## Implementation approach

**1. ⚖ Owner decision: pydantic-settings adoption vs. `.env` deletion.**

The plan recommends `pydantic-settings` adoption (`build/plan/01-phase-0-foundation.md`
P0-T6 row: "recommended: `pydantic-settings` adoption for env/config layering per P1 §7,
which also fixes env-read-once and empty-string-key findings; alternative: delete the
documented `.env` option"). This is a real scope fork:

- **pydantic-settings path** is larger: it touches `AppConfig`'s base class (currently
  plain `pydantic.BaseModel`-derived `ConfigBase`, `models.py:170` — re-verify exact
  line before editing), requires choosing a settings-source precedence order, and
  changes how `llm_api_key`/`acoustid_api_key`/`genius_access_token` are populated
  (moving off the current `default_factory=lambda: SecretStr(os.getenv(...))` pattern
  and off `_load_env_vars_into_config` in `loader.py`). It is the more thorough fix and
  the one that also resolves P1-F17/F19 as stated in the plan, but it is a real
  cross-cutting config-layer change, not a doc fix.
- **Deletion path** is smaller: edit `docs/user-guide.md` to remove "Option 2", decide
  `.env.example`'s fate, and leave the config-loading code untouched (P1-F17/F19 remain
  open, to be picked up elsewhere if ever prioritized).

If the orchestrator/owner has not given an explicit steer by the time this task is
executed, **default to the deletion path** for this Phase 0 task (smaller, lower-risk,
matches Phase 0's "small, evidence-backed" framing from the phase doc's goal statement)
and flag the `pydantic-settings` adoption as a candidate for a later phase (it is not
listed as a named task in any other phase doc as of this writing — note this gap to the
orchestrator rather than silently expanding this task's scope). If the owner has
signaled a preference (check `changes/ACTIVE.md` and any recent handoff notes before
starting), follow that instead.

**2. Fix `make env-check`.**

Regardless of which path is chosen in step 1, replace the file-content grep with a real
environment check. Minimal fix (works standalone in `make`):
```makefile
env-check: ## Check environment setup
	...
	@echo "$(YELLOW)Environment File:$(NC)"
	@if [ -n "$$OPENAI_API_KEY" ]; then \
		echo "  ✓ OPENAI_API_KEY is set in the current shell"; \
	else \
		echo "  $(RED)✗ OPENAI_API_KEY is not set in the current shell$(NC)"; \
		echo "  $(YELLOW)→ export OPENAI_API_KEY='your-key-here'$(NC)"; \
	fi
```
Adjust wording/structure to fit the existing `env-check` target's surrounding style
(`Makefile:320-339`) — the point is the check must query the real environment
(`$$OPENAI_API_KEY` in Make, which reads the shell's exported env) rather than grepping
a file. If the deletion path (step 1) is chosen, also remove any remaining `.env`-file
existence-check lines from `env-check` that no longer correspond to a documented setup
option.

**3. Fix the docs (`docs/user-guide.md:65-99`) per whichever path step 1 resolves to.**

- Deletion path: remove "Option 2: .env file" entirely; keep "Option 1"; update the
  `env-check` description to match its new (real) behavior.
- pydantic-settings path: update "Option 2" to reflect the now-working mechanism (likely
  unchanged instructions, since `cp .env.example .env` + edit was always the intended
  UX — only the "does it actually work" claim changes from false to true); update
  `env-check`'s description similarly.

**4. Fix the two `PipelineContext` docstring examples.**

In both `packages/twinklr/core/pipeline/context.py:40-46` and
`packages/twinklr/core/pipeline/__init__.py:31`, replace the broken kwarg lists with the
correct, working form — model it on `docs/pipeline_guide.md:694`'s already-correct
usage:
```python
>>> context = PipelineContext(session=session, output_dir=Path("artifacts/demo"))
```
(`pipeline/context.py`'s docstring may retain its richer example structure — e.g.
showing `context.state["has_lyrics"] = ...` afterward — just fix the constructor call
itself; `pipeline/__init__.py`'s shorter package-level example should similarly use
`session=` in place of `provider=`/`config=`.) After editing, **execute both docstring
examples verbatim** (e.g. via `python -m doctest` on the two files, or a manual
`uv run python -c` paste) to confirm they no longer raise — do not just "read" the fix
as plausible; both examples require a `TwinklrSession` instance to actually construct
successfully in a doctest context, so if full doctest execution isn't practical (no
importable `session`/`provider`/`app_config` in scope), at minimum confirm the kwarg
names used exist on the real dataclass (`session`, `checkpoint_dir`, `output_dir`,
`state`, `metrics`, `cancel_token` — the only real init fields per
`context.py:57-69`) and that this exact form was already proven to work at
`docs/pipeline_guide.md:694`.

## Acceptance criteria

- `docs/user-guide.md`'s Environment Setup section describes only working setup paths
  (either `.env` genuinely works, or it is no longer presented as an option).
- `make env-check` reports `OPENAI_API_KEY` status based on the real process
  environment, not a file-content grep; verified by testing both a shell with the
  variable exported and one without.
- If the pydantic-settings path was chosen: `packages/twinklr/core/pyproject.toml`
  declares the new dependency, `AppConfig`'s settings-layering is real and testable, and
  P1-F17 (env-read-once)/P1-F19 (empty-string-key) no longer reproduce (verified: a
  missing `OPENAI_API_KEY` now fails at settings-construction/validation time, not
  silently defaulting to an empty-string `SecretStr` that only fails at first API call).
- If the deletion path was chosen: `.env.example` and any `.env`-file instructions in
  docs no longer imply automatic loading; `grep -rn "cp .env.example" docs/` (or
  equivalent) returns no hits, or the surviving reference is clearly reframed as
  "manually export these" rather than "the app reads this file."
- Both `PipelineContext` docstring examples use `session=` (the real field) and no
  longer reference `provider=`/`app_config=`/`job_config=`/`cache=`/`config=` as
  constructor kwargs.
- `uv run pytest tests/ -v` shows no new failures introduced by this task's changes
  (scoped against P0-T2's post-repair baseline if that task has already landed).

## Tests

- Add a regression test (or extend an existing `config`/`pipeline` test file) asserting
  that `PipelineContext(session=<mock_session>)` — the corrected form — succeeds, to
  prevent the docstring/reality drift from silently recurring. TDD is not strictly
  applicable here (this is a doc-accuracy fix, not new behavior), but a smoke test
  pinning the *correct* constructor shape is cheap and directly relevant, since existing
  tests already use `PipelineContext(session=mock_session)` throughout
  (`tests/unit/pipeline/test_pipeline.py:107` and others) — no new test may be strictly
  necessary if this coverage already exists; confirm before adding a duplicate.
- If the pydantic-settings path is chosen, add tests asserting: (a) a missing
  `OPENAI_API_KEY` in both env and config file produces a clear validation error rather
  than an empty-string `SecretStr`; (b) `.env` values are actually picked up (a test
  writing a temp `.env` and confirming it's read). TDD: write these tests first,
  confirm they fail against the current `os.getenv("OPENAI_API_KEY", "")` default
  before implementing the pydantic-settings change.

## Verification commands

```bash
# env-check accuracy, both states
unset OPENAI_API_KEY && make env-check   # expect an honest "not set" report
export OPENAI_API_KEY=test-value && make env-check   # expect an honest "set" report

# PipelineContext docstring correctness
grep -n "PipelineContext(" packages/twinklr/core/pipeline/context.py packages/twinklr/core/pipeline/__init__.py
uv run python -c "
from twinklr.core.pipeline.context import PipelineContext
from unittest.mock import MagicMock
PipelineContext(session=MagicMock())  # should not raise
print('OK')
"

uv run pytest tests/ -v
uv run mypy .
```

## Effort & risk

**S (deletion path) or M–L (pydantic-settings path)** — the effort band depends entirely
on the step-1 decision, which is why this task is marked ⚖. Main risks: (1) picking the
pydantic-settings path without confirming it's actually in scope for Phase 0 risks
turning a "small, evidence-backed" foundation task into a cross-cutting config-layer
migration — flag this explicitly to the orchestrator rather than silently absorbing the
larger scope; (2) the `PipelineContext` docstring fix is low-risk but easy to under-test
— actually execute the corrected examples, don't just eyeball that the kwargs look
plausible, since this exact defect (a docstring that reads correctly but fails on
execution) is what caused the original bug.
