# P0-T3 — Format/lint baseline

Phase: 0-foundation · Lane: A (config/tooling, serial: T1→T2→T3→T4) · Executor: sonnet ·
Verifier: sonnet · Depends on: P0-T1, P0-T2

## Objective

Bring `uv run ruff format --check .` and `uv run ruff check .` to a green, honest
baseline: one formatting commit, one triaged lint-fix commit, and a unified ruff/mypy
configuration so `packages/twinklr/core` is governed by the same (strict, root) ruleset
as the rest of the repository instead of its own separately-resolved weak 7-family
config — with the resulting new-violation count from that unification **recorded before
the fix commit**, per the plan's explicit sequencing requirement.

## Evidence & background

- **Finding P1-F20** (CONFIRMED; `changes/twinklr-reactivation-review/reviews/findings.md`
  SF-7 / cited in `01-phase-0-foundation.md` P0-T3 row): "ruff core-config weakness."
  Elaborated in `reviews/phases/foundation-and-orchestration.md` §4.10 ("Which
  lint/type configuration actually wins — discovery unknown #5, resolved"): "ruff — the
  core package gets the *weak* ruleset. \[UPGRADED to CONFIRMED\] ruff resolves
  configuration *hierarchically and per file*: each file is governed by the nearest
  ancestor `pyproject.toml`/`ruff.toml` containing a `[tool.ruff]` table. For everything
  under `packages/twinklr/core/`, that is `packages/twinklr/core/pyproject.toml:66-82` —
  seven rule families (`E,W,F,I,B,C4,UP`). The root's larger set plus the isort settings
  and `ban-relative-imports` (root `pyproject.toml:50-108`) applies **only** to files
  outside core... The strict configuration is therefore applied to everything *except*
  the product code, which is the inverse of the evident intent... **The Stage 7 verifier
  ran `uvx ruff --show-settings` out-of-repo and confirmed the split empirically**."
- **Stage 4 runtime baseline** (`reviews/verification.md`): `uv run ruff format --check .`
  → exit 1, 13 files would be reformatted (1178 clean); `uv run ruff check .` → exit 1,
  150 errors (8 safe-fixable). "None of the 150 lint errors can be in `core/` under the
  strict families, because those families do not apply there (P1-F20)."
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`):
  - `uv run ruff format --check .` → **13 files would be reformatted, 1178 files already
    formatted**, all 13 inside `packages/twinklr/core/recipe_builder/` (7 files:
    `admission.py`, `enrichment.py`, `evidence.py`, `generation.py`, `pipeline.py`,
    `promotion.py`, `validation.py`) and `tests/unit/recipe_builder/` (6 files:
    `test_admission.py`, `test_boundary.py`, `test_enrichment.py`, `test_generation.py`,
    `test_pipeline.py`, `test_promotion.py`).
  - `uv run ruff check .` (repo root, hierarchical resolution as it runs today) →
    **150 errors, 8 fixable with `--fix`**, dominated by `UP042` (replace-str-enum, 129
    occurrences — confirmed via `uv run ruff check . --statistics`), plus `UP017` (6),
    `UP046` (5), `UP047` (3), `F841` (2), `B007` (1), `F401` (1), `I001` (1), `PLR1714`
    (1), `SIM110` (1). None of these 150 are inside `packages/twinklr/core/` — confirmed
    by cross-referencing the statistics with per-file output.
  - **The honest new-violation diff, recorded here before any fix commit lands** (this
    is the record P0's plan explicitly requires — see "Notes for spec authors" below):
    running `uv run ruff check packages/twinklr/core --config pyproject.toml`
    (forcing ruff to resolve every file in `core/` against the **root's** `[tool.ruff]`
    table instead of core's own nearer, weaker one) produces **237 errors** against
    core alone, versus **143 errors** when `core/` is checked under its own current weak
    config (`uv run ruff check packages/twinklr/core`, no `--config` override). That is
    **94 net-new violations** that unifying the configs will surface in `core/` alone —
    broken down by rule (`--statistics` under the forced root config):
    `UP042` 129, `TC001` (typing-only-first-party-import) 33, `I001` 12, `RUF012`
    (mutable-class-default) 10, `SIM102` 8, `N815` 7, `RUF010` 7, `UP017` 6, `UP046` 5,
    `PIE790` 3, `SIM108` 3, `UP047` 3, `RUF005` 2, `RUF022` 2, `TC006` 2, `N801` 1,
    `PIE810` 1, `PLR1714` 1, `PTH123` 1, `SIM103` 1. (32 of these 237 are `--fix`-able,
    178 more under `--unsafe-fixes`.)
  - Root config's inert families, confirmed present but silently no-op: `ERA`/`T20` are
    selected (root `pyproject.toml:81-82`) but their only rules are then ignored
    (`ERA001` at `:98`, `T201` at `:95`) — per the phase-1 review, "both families are
    inert even where the root config applies." Not this task's job to fix (out of
    scope — noted only so the executor does not mistake this for a bug to chase).
  - `pyrightconfig.json` (root, full content re-read): a third type-checking config,
    `"typeCheckingMode": "basic"`, `include: ["packages"]`, excludes
    `tests/**`,`.dev/**`,`scripts/**`,`utils/**`,`data/**`, `reportMissingImports: "none"`
    — wired to no `Makefile` target, no CI job, and no documentation
    (`context/engineering/conventions.md` documents only mypy as "strict"). Confirmed
    unreferenced anywhere (`grep -rn "pyrightconfig" Makefile .github/ docs/` → 0 hits
    outside the file itself).
- **mypy is unaffected by this task**: mypy reads a *single* configuration file
  discovered from the current working directory (root `pyproject.toml:112-141` when run
  from repo root, which is how `Makefile`'s `type-check`/`validate` targets invoke it —
  `Makefile:97,161`). `packages/twinklr/core/pyproject.toml:84-90`'s `[tool.mypy]` block
  is already dead weight (never read when mypy runs from root), confirmed by the
  phase-1 review §4.10. This task's mypy-side work is limited to deciding
  `pyrightconfig.json`'s fate (delete or align) — do not attempt to "unify" mypy configs,
  there is nothing to unify; there is only a dead block to remove for hygiene.

## Notes for spec authors (from `changes/twinklr-reactivation-review/build/plan/01-phase-0-foundation.md`, copied verbatim)

> T3 must record the expected new-violation count from applying strict rules to core
> BEFORE the fix commit (honest diff).

This spec satisfies that requirement in the "Evidence & background" section above: **94
net-new violations** (237 under unified strict config vs. 143 under today's weak config),
recorded before any commit in this task lands. The executor must not silently
`--fix`/suppress this diff away without the orchestrator/verifier being able to see the
before/after honestly — commit history should show the baseline recorded (this spec, or
an equivalent note in the PR description) before the fix commit, not after.

## Current behavior

- `ruff check .` run from repo root resolves each file against the **nearest ancestor**
  `pyproject.toml` containing `[tool.ruff]`. Files under `packages/twinklr/core/` resolve
  to `packages/twinklr/core/pyproject.toml`'s narrow 7-family ruleset (`E,W,F,I,B,C4,UP`,
  no `TCH`/`SIM`/`PLR`/`PTH`/`ERA`/`T20`/`N`/`PERF`/`RUF`/`TID252`). Every other file
  (`tests/`, `scripts/`, `utils/`, `packages/twinklr/cli/` — which has no `[tool.ruff]`
  of its own) resolves to the root's larger, stricter ruleset.
- This means "lint passes" today says materially less about `core/` — the product
  code — than it appears to, since the 150 currently-failing checks are entirely outside
  `core/` under the strict rules that `core/` never sees.
- `packages/twinklr/core/pyproject.toml` also carries its own `[tool.mypy]` and
  `[tool.pytest.ini_options]` blocks that are dead weight (mypy and pytest, unlike ruff,
  each read a single config file from the invocation directory, so these blocks are never
  consulted when tools run from root as `Makefile` does).
- `pyrightconfig.json` exists, is loadable by any contributor's IDE (VS Code/Pylance),
  and asserts a materially weaker standard (`"basic"`) than the project's documented
  mypy-strict standard, with zero wiring to keep the two aligned.

## Target behavior

- One formatting commit applies `ruff format` to the 13 currently-unformatted files
  (and only those — a mechanical, reviewable diff).
- `packages/twinklr/core` is governed by the **same** `[tool.ruff]` configuration as the
  rest of the repository (the root's), eliminating the weak/strict split entirely. Ruff
  resolves consistently repo-wide after this change — verified with
  `uvx ruff --show-settings` (or in-repo equivalent) showing identical resolved settings
  for a file under `core/` and a file under `tests/`.
- The 94 newly-surfaced violations in `core/` are triaged and fixed (or, for the small
  minority that are not mechanically fixable and represent a deliberate style choice,
  explicitly suppressed with a per-line/per-file `# noqa` and a one-line justification —
  prefer fixing over suppressing; suppression is the exception, not the default) in a
  **separate, clearly-labeled commit** from the formatting commit, so the "honest diff"
  from this spec's evidence section is reviewable against the actual fix.
- `packages/twinklr/core/pyproject.toml`'s dead `[tool.mypy]` and
  `[tool.pytest.ini_options]` blocks are removed (they resolve to nothing today and
  unifying `[tool.ruff]` makes the file's remaining `[tool.ruff]` block also removable —
  see Implementation approach for the exact mechanism).
- `pyrightconfig.json` is either (a) deleted (if the project has no near-term IDE-typing
  use case beyond mypy), or (b) updated to match mypy's strict standard and referenced
  from `context/engineering/conventions.md` so it cannot silently drift again — pick one;
  the plan does not mandate which, but the current unwired, weaker-than-documented state
  must not persist.

## Implementation approach

**1. Format commit (first, isolated).**

```bash
uv run ruff format .
git diff --stat   # confirm exactly the 13 files listed in evidence, no others
```
Commit this alone: `"Format code with ruff (P0-T3)"`. Do not combine with the lint-fix
or config-unification changes — the plan and this spec both require this to be reviewable
independently.

**2. Record the honest diff (before the fix commit — already done in this spec's
Evidence section, but re-confirm on your checkout since the tree may have drifted from
`aa8d325` if T1/T2 landed first):**

```bash
uv run ruff check packages/twinklr/core --statistics                        # today's weak-config count
uv run ruff check packages/twinklr/core --config pyproject.toml --statistics # count under unified strict config
```
Note both numbers in your PR description before proceeding — this is the artifact the
plan's "record the expected new-violation count ... BEFORE the fix commit" requirement
is asking for.

**3. Unify the ruff configuration.**

Delete `[tool.ruff]`, `[tool.ruff.lint]`, and any nested `[tool.ruff.lint.*]` tables from
`packages/twinklr/core/pyproject.toml` entirely, so ruff's hierarchical resolution falls
through to the root `pyproject.toml`'s `[tool.ruff]` table for every file under `core/`
(ruff's documented behavior: absence of a `[tool.ruff]` table in the nearest
`pyproject.toml` causes it to continue searching ancestors). Also delete the dead
`[tool.mypy]` and `[tool.pytest.ini_options]` blocks from the same file (confirmed dead
per Evidence — mypy/pytest never read this file when invoked from root, which is the
only way `Makefile` invokes them). After this edit, `packages/twinklr/core/pyproject.toml`
should retain only `[project]`, `[project.optional-dependencies]`, and `[build-system]`
(the packaging-relevant sections P0-T5 will separately touch — do not let this task's
edits collide with P0-T5's `uv_build` backend adoption; if T5 has already landed when you
do this, re-read its resulting file before editing).

Re-run:
```bash
uv run ruff check . --statistics
```
This should now show the previous 150 (unrelated to core) **plus** the 94 (now surfaced
in `core/`) minus whatever this task's own fix commit resolves — do the triage/fix pass
next before this number is your final state.

**4. Triage and fix the lint baseline (both the pre-existing 150 and the newly-surfaced
94; T3 also owns "triaged `ruff check --fix` commit" per the plan's task table for the
non-core violations, and the core ones become in-scope the moment the config unifies).**

- Start with the 8 (pre-existing) + 32 (newly-surfaced) auto-fixable violations:
  `uv run ruff check . --fix` — review the diff before committing (it should be entirely
  mechanical: unused-import removal, f-string conversion, etc.).
- Triage the remainder by rule family. The dominant rule by a wide margin is `UP042`
  (replace-str-enum, 129 occurrences under the unified config, all currently invisible
  because `core/`'s weak config doesn't select `UP042`... actually re-verify: `UP042` is
  in the `UP` family, which **is** selected by core's own weak config too — re-check
  whether these 129 are already present under the weak config or only surface under the
  strict one before assuming they're "new"; the 143-vs-237 diff in Evidence already
  accounts for this correctly, trust that number over any restated assumption here).
  `UP042` flags `class Foo(str, Enum):` in favor of `class Foo(StrEnum):` (Python 3.11+)
  — this is a real, mechanical, low-risk fix pattern; batch it.
  `TC001`/`TC006` (33+2) are typing-only-import / runtime-cast findings — verify each
  suggested move doesn't break a runtime dependency (e.g. pydantic model resolution)
  before applying `--fix`.
- For any violation that is not safely auto-fixable and does not warrant a code change
  (rare — treat every case as fixable-by-default per the acceptance criteria below), add
  a narrowly-scoped `# noqa: RULE` with a one-line reason, not a blanket file-level
  ignore.
- Split this into as many reviewable commits as make sense by rule family/subsystem;
  the plan does not mandate one commit, only that the format commit and the fix work are
  separable, and that the pre-fix violation count was recorded (step 2).

**5. `pyrightconfig.json` — delete or align.**

Pick one (executor's judgment call unless the orchestrator specifies otherwise):
- **Delete**: `rm pyrightconfig.json`; confirm nothing references it
  (`grep -rn "pyrightconfig" .` should then return zero hits repo-wide).
- **Align**: change `"typeCheckingMode"` to match the project's mypy-strict posture
  (research Pyright's closest equivalent mode — `"strict"` is the analogous setting;
  note this may itself surface a new wave of Pyright-only diagnostics, which is out of
  this task's scope to fix — if choosing this path, pair it with adding a
  `context/engineering/conventions.md` line noting the config exists and its intended
  strictness, so it cannot silently drift again).

## Acceptance criteria

- `uv run ruff format --check .` exits 0.
- `uv run ruff check .` exits 0 (all 150 pre-existing + 94 newly-surfaced violations
  resolved or narrowly, justifiably suppressed).
- `packages/twinklr/core/pyproject.toml` no longer contains `[tool.ruff]`,
  `[tool.mypy]`, or `[tool.pytest.ini_options]` tables.
- `uvx ruff --show-settings <a file under packages/twinklr/core/>` and
  `uvx ruff --show-settings <a file under tests/>` (run out-of-repo per the verifier's
  method in the phase-1 review) resolve to the **same** `[tool.ruff]` source file.
- `pyrightconfig.json` is either absent or aligned + documented (not left in its current
  unwired, weaker-than-mypy state).
- `uv run mypy .` still exits 0 (T1's fix untouched; confirm no regression from this
  task's edits).
- The honest pre-fix violation count (94 new in `core/`) is visible in the PR/commit
  history, not silently absorbed.

## Tests

No new tests — this is a formatting/lint/config-hygiene task with no behavioral surface.
The full test suite (`uv run pytest tests/ -v`, scoped per P0-T2's outcome — do not
regress its pass count) must show no new failures introduced by any `--fix` application,
since some fixes (e.g. `UP042` StrEnum conversions) touch runtime-observable class
identity and could theoretically break `isinstance`/serialization behavior if applied
carelessly. Spot-check any `UP042` conversion against its consuming code (Pydantic model
fields, JSON serialization) before committing.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/ -v   # confirm no new failures vs. P0-T2's baseline
grep -rn "pyrightconfig" . --include="*.md" --include="Makefile" --include="*.yml"  # confirm wiring decision is reflected
```

## Effort & risk

**M** (medium). Main risks: (1) the 94 newly-surfaced `core/` violations may include
non-trivial `UP042`/`TC001` cases where a mechanical fix changes runtime behavior
(StrEnum's `__str__`/serialization differs subtly from `str, Enum` in some Python
versions/usages) — mitigate by running the full test suite after each batch of fixes,
not only at the end; (2) unifying configs is a one-way door for this task but easy to
misorder against P0-T5 (packaging) if both touch `packages/twinklr/core/pyproject.toml`
concurrently — check for T5's changes before editing that file, and rebase rather than
overwrite if there's a conflict; (3) scope creep — do not use this task to fix unrelated
pre-existing code smells beyond what ruff's ruleset flags.

## Descope record (post-execution, 2026-08-13)

Executed against the tree at `e1b3b71` (T1/T2/T5/T6 already landed). Two findings
materially changed this task's actual scope versus the estimate above; both are
recorded here per the plan's "record the expected new-violation count ... BEFORE the
fix commit" requirement, extended to cover the correction below.

**1. The evidence section's 94/237 counts were measured with a stale `.ruff_cache` and
were a significant undercount.** `.ruff_cache` is gitignored and not invalidated
reliably across a `[tool.ruff]` table relocation (core's own table being deleted so its
files fall through to the root table) combined with unrelated file edits from
concurrent tasks. Re-measuring with `ruff check --no-cache` (the only trustworthy mode —
**any lint run in this repo, local or CI, should pass `--no-cache` or start from a
clean `.ruff_cache`, otherwise the reported count is not honest**; flagged separately to
the P0-T4 CI spec since CI's fresh runner sidesteps this but local `make lint` does not):

| | today's (weak) config | unified (strict) config |
|---|---|---|
| `packages/twinklr/core` only | 147 | 1130 |
| repo-wide total | 155 | 1138 |

Net-new from unification: **983**, not 94. Dominant rule: `TC001`
(typing-only-first-party-import), 621 of the 1138.

**2. `TC001` interacts with Pydantic runtime model resolution.** A blind
`ruff check --fix --unsafe-fixes --select TC001` moved imports required by
`pydantic.BaseModel` field resolution into `TYPE_CHECKING` blocks, breaking
`model_rebuild()` for ~270 tests (`PydanticUserError: ... not fully defined`). Fix:
added `runtime-evaluated-base-classes = ["pydantic.BaseModel"]` to
`[tool.ruff.lint.flake8-type-checking]` (root `pyproject.toml`) — this is ruff's
documented mechanism for exactly this class of false positive and dropped the count
from 621 to 522. 522 is still far above a hand-triageable-in-one-pass size (the
per-team-lead threshold was ≤100), and a second bulk-fix attempt on the remainder
independently broke a circular-import-avoidance pattern
(`packages/twinklr/core/sequencer/planning/group_plan.py` ↔
`agents/sequencer/group_planner/holistic.py`, resolved via a deferred
`TYPE_CHECKING` + `# noqa: TC004` import, not TC001) — confirming this rule family
carries real, not just theoretical, runtime risk in this codebase and should not be
force-fixed at volume without per-import review.

**Descoped**: `TC001` added to the root `[tool.ruff.lint.ignore]` list with an inline
justification comment (not silent — see `pyproject.toml`). All other rule families
unified and reached zero violations by direct fix (RUF012 → `ClassVar` annotations,
N801/N814/N815/N817/N818/N803 → renamed where internal-only or `# noqa` with
justification where mirroring an external contract — xLights XML attribute names in
`formats/xlights/layout/models/rgb_effects.py`, setuptools' own `build_py` command
name, numpy/sklearn's `X` matrix convention already exempted for `N806` — and the
SIM/PERF/PTH families fixed mechanically per ruff's suggested rewrite). Final gates:
`ruff format --check .` clean, `ruff check . --no-cache` clean (0 errors, `TC001`
excluded), `mypy .` clean (670 files), `pytest tests/` 4089 passed / 26 skipped / 0
failed.

**Follow-up task recorded**: a proper `TC001` remediation (move each of the 522
first-party typing-only imports into `TYPE_CHECKING`, verifying per-file whether the
import feeds Pydantic field resolution, a circular-import-avoidance shim, or is
genuinely type-only) belongs in the Phase 4 debt wave, not this task.
