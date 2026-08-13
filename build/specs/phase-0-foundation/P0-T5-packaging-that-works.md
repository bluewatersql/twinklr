# P0-T5 — Packaging that works

Phase: 0-foundation · Lane: B (packaging, independent) · Executor: sonnet · Verifier:
sonnet · Depends on: —

## Objective

Make `uv build` (or `make build`) produce **non-empty, distributable wheels** for both
`twinklr-core` and `twinklr-cli`, with no tree pollution, by adopting the `uv_build`
backend per package and deleting the broken `find_packages(where="../..")` setup.py
shims. `git status` must be clean after a build.

## Evidence & background

- **Finding P1-F23** (CONFIRMED; `changes/twinklr-reactivation-review/reviews/findings.md`
  CC-2 / SF-7): "packaging nonfunctional (empty wheels + pollution)."
- **Stage 4 runtime baseline** (`reviews/verification.md` §"Stage 4 runtime baseline —
  RESULTS"), quoted verbatim: "**P1-F23 CLOSED — CONFIRMED, worse than suspected**: `uv
  build` exits successfully for both packages but **both wheels are empty** (dist-info
  only, zero Python code; core wheel = 4 files, cli wheel = 5). The setup.py
  `find_packages(where="../..")` shims find nothing from the build sandbox. Packaging is
  nonfunctional end-to-end: `make build` targets wrong directories AND a corrected
  invocation yields undistributable artifacts. Worse, the build **pollutes the source
  tree**: it materialized a full nested copy of the codebase at
  `packages/twinklr/twinklr/` plus three stray `*.egg-info` directories (the setup.py
  `package_dir="../.."` misresolution in action). Only the uv-workspace editable install
  path works. (All artifacts created by this test were deleted; `git status` verified
  clean.)"
- **Root-cause mechanism, re-derived directly against the current tree** (this spec,
  baseline `aa8d325`, not re-executing the build — the empty-wheel/pollution result is
  already CONFIRMED by Stage 4; this spec instead traces *why* by reading the actual
  editable-install artifacts, which is safe/non-mutating):
  - `packages/twinklr/core/setup.py` (full file):
    ```python
    from setuptools import find_packages, setup

    # Find all packages - now physical structure matches import path
    packages = find_packages(where="../..", include=["twinklr.core", "twinklr.core.*"])

    setup(
        packages=packages,
        package_dir={"": "../.."},
    )
    ```
    `packages/twinklr/cli/setup.py` is the identical pattern for `twinklr.cli`. Neither
    `pyproject.toml` declares `[tool.setuptools]` package configuration (core's
    `[build-system]` is bare `setuptools.build_meta`), so these `setup()` kwargs are the
    *only* thing telling setuptools where the code lives.
  - The **physical directory layout does not match the import path**: the package's
    Python source (`agents/`, `api/`, `audio/`, ..., `__init__.py` declaring
    `__version__`) lives directly inside `packages/twinklr/core/` — the same directory
    that holds `pyproject.toml` and `setup.py` — but must import as `twinklr.core.*`,
    not `core.*`. The `twinklr` namespace parent (`packages/twinklr/__init__.py`) lives
    **two directories above** the project root (`packages/twinklr/core/`), i.e. outside
    it entirely. `where="../..", package_dir={"": "../.."}` was written to reach up to
    `packages/` and resolve `twinklr.core` from there.
  - **This works only for editable installs**, and only because setuptools' modern
    editable-install machinery does not build a physically-laid-out wheel at all — it
    generates a custom `MetaPathFinder` with an explicit import-name → filesystem-path
    mapping, bypassing the physical-layout requirement entirely. Confirmed directly by
    reading the installed editable finder:
    `.venv/lib/python3.12/site-packages/__editable___twinklr_core_0_1_0_finder.py`
    contains `MAPPING: dict[str, str] = {'twinklr.core':
    '/…/packages/twinklr/core'}` and `NAMESPACES: dict[str, list[str]] = {'twinklr': []}`
    — i.e., the editable install works by directly mapping the import name to the
    physical path in a generated Python finder, not by relying on `find_packages`
    producing a conventional layout.
  - **A real (non-editable) build cannot use this trick.** `uv build` (or any PEP-517
    build) runs `setup.py`'s `find_packages(where="../..")` inside an **isolated build
    sandbox** whose contents are derived from the project directory
    (`packages/twinklr/core/`) — it does not have access to `../..`
    (`packages/`) as a real filesystem path relative to the sandboxed source tree, so
    `find_packages` returns an empty list, producing dist-info-only wheels. Where the
    `package_dir={"": "../.."}` **does** resolve (e.g. during `sdist` staging outside a
    sandbox), it points **above** the project directory, which is how the build ends up
    materializing a stray nested copy of the whole codebase at
    `packages/twinklr/twinklr/` (`package_dir`'s `../..` resolving against
    `packages/twinklr/core/` lands at `packages/`, and setuptools' file-copy step for
    the discovered — but in-sandbox, empty — package list ends up walking and copying
    from the wrong root instead).
  - `Makefile:181-187` (`build` target, re-read verbatim): `cd packages/core && uv
    build` / `cd packages/cli && uv build` — **both paths are wrong**; the real
    directories are `packages/twinklr/core/` and `packages/twinklr/cli/`.
    `packages/core` and `packages/cli` do not exist at any depth (confirmed:
    `ls packages/core packages/cli` → both absent). This target fails immediately on
    `cd`, before `find_packages` even runs — a second, independent packaging failure
    layered on top of the empty-wheel one.
  - `packages/twinklr/core/pyproject.toml:14` (dependencies list) pins
    `"setuptools>=65.0"` as a **runtime** dependency, commented "Required by librosa for
    pkg_resources" — `pkg_resources` was removed in setuptools 81, so this pin will
    break on a modern resolver (flagged in the phase-1 review §4.9; out of this task's
    core scope but noted since it lives in the same file this task edits — do not "fix"
    it here unless it blocks the `uv_build` migration; if it does, note the interaction
    in your PR).
  - Root `pyproject.toml` is itself a third package (`name = "twinklr"`, version
    `0.2.0`), with `[tool.setuptools] packages = []` (deliberately empty — it is a
    meta-package depending on `twinklr-core`/`twinklr-cli`, confirmed by reading
    `pyproject.toml:1-48` in full) and `[tool.uv.workspace] members = ["packages/twinklr/core", "packages/twinklr/cli"]`.
    This root package is **out of this task's explicit scope** per the plan's task table
    ("Adopt the `uv_build` backend **per package**" — the two workspace members) but its
    own `[build-system]`/`setuptools.build_meta` + empty `packages=[]` combination is
    already functionally inert (it has no code of its own to package) — confirm it is
    not broken by whatever change you make to the two real packages, but do not migrate
    it to `uv_build` unless doing so is required for consistency and is low-risk; if in
    doubt, leave the root package's build-system untouched and note that decision in
    your PR.

## Current behavior

- `uv build` (run correctly, from each package's real directory) exits 0 for both
  `twinklr-core` and `twinklr-cli` but produces **empty wheels** — dist-info only, zero
  Python modules (core wheel: 4 files: `METADATA`, `RECORD`, `WHEEL`, and one more
  dist-info file; cli wheel: 5, similarly dist-info-only).
- The same build additionally **pollutes the source tree**: a full nested copy of the
  codebase materializes at `packages/twinklr/twinklr/`, plus stray `*.egg-info`
  directories, none of which are gitignored artifacts the developer expects.
- `make build` (`Makefile:181-187`) fails immediately — it `cd`s into
  `packages/core`/`packages/cli`, neither of which exists (the real paths are
  `packages/twinklr/core`/`packages/twinklr/cli`).
- Only the `uv` workspace **editable** install path works, and it works via a mechanism
  (setuptools' generated import-mapping finder) that is fundamentally incompatible with
  producing a real, distributable wheel from the same `setup.py` configuration.

## Target behavior

- `uv build` (run from each package directory, or via a corrected `make build`) produces
  wheels that **contain the actual package code** — importing from the built wheel in a
  fresh venv succeeds (`import twinklr.core` / the CLI entry point resolves) — for both
  `twinklr-core` and `twinklr-cli`.
- No tree pollution: `git status` is clean immediately after a build (only `dist/`
  output, which must be gitignored or cleaned, no stray copied source trees or
  `*.egg-info` directories left in tracked locations).
- `make build` targets the correct, real paths and succeeds end to end.
- The `uv` workspace's existing **editable** install behavior (`uv sync`,
  `make install`) continues to work exactly as before — this task must not regress the
  primary development-install path while fixing the secondary (real-build) path.

## Implementation approach

**This is a genuine physical-layout mismatch, not a one-line config change — treat it as
such and budget accordingly (see Effort & risk).**

1. **Consult the official `uv_build` documentation before implementing**
   (`operating_principles`: "Consult official docs before implementing with
   SDKs/frameworks/APIs" — this repo's own convention). Specifically determine, for the
   `uv` version pinned/available in this workspace (`uv --version`; re-check against
   `uv.lock`), whether `[tool.uv.build-backend]` supports mapping a project whose
   `pyproject.toml` lives inside the package's own top-level directory (i.e., project
   root = `packages/twinklr/core/`, which is *also* where `agents/`, `api/`, `audio/`,
   etc. physically live) to an import name of `twinklr.core` (a dotted, two-level name
   whose first segment's directory, `packages/twinklr/`, is **outside** the project
   root) via `module-name`/`module-root`/namespace-package settings — versus requiring a
   conventional `src/<pkg>/...` layout **inside** the project root.

2. **Two candidate implementation paths — choose based on what step 1 finds `uv_build`
   actually supports:**

   - **Path A (config-only, if `uv_build` supports it):** Set
     `build-backend = "uv_build"` in each package's `[build-system]`, and configure
     `[tool.uv.build-backend]` to point at the existing physical location and declare
     the `twinklr.core`/`twinklr.cli` dotted import name plus the `twinklr` namespace
     parent, without moving any files. This is the lower-risk, lower-effort path if the
     backend's namespace/module-root options genuinely support this out-of-project-root
     shape — confirm by actually building and inspecting wheel contents (see
     Verification), not by assuming the config is accepted just because `uv build`
     exits 0 (the current setuptools shim also exits 0 while producing empty wheels —
     exit code alone is not evidence of correctness for this specific defect class).
   - **Path B (physical restructure, if Path A is unsupported):** Move each package's
     source into a conventional layout the backend expects — e.g.
     `packages/twinklr/core/src/twinklr/core/{agents,api,audio,...}` (a `git mv` of
     every existing subpackage/module one level deeper, plus adding the intervening
     `packages/twinklr/core/src/twinklr/__init__.py` namespace file) — and set
     `[tool.uv.build-backend]` to the resulting conventional `src/`-relative
     `module-name = "twinklr.core"`. This changes **no import statements anywhere in
     the codebase** (imports already say `twinklr.core.X` regardless of physical
     location — only the *physical* path changes), but it does require updating every
     tool/config that references the current physical path directly:
     `packages/twinklr/core/pyproject.toml`'s own `[tool.pytest.ini_options]`
     `testpaths` (if retained — see P0-T3, which may have already deleted this block;
     coordinate), any `Makefile`/CI path references (coordinate with P0-T4), and
     confirming the uv workspace's editable-install path still resolves correctly
     post-move (re-run `uv sync` and confirm `import twinklr.core` still works after the
     move, before touching the build-backend).

3. **Delete both setup.py shims** (`packages/twinklr/core/setup.py`,
   `packages/twinklr/cli/setup.py`) once the chosen path's `pyproject.toml`
   configuration fully replaces what they did — do not delete them until the
   replacement is verified working (build a wheel, inspect its contents) to avoid a
   window where neither mechanism works.

4. **Fix `make build`** (`Makefile:181-187`) to `cd` into the real paths
   (`packages/twinklr/core`, `packages/twinklr/cli`) and, if `uv build`'s
   output-directory behavior changes under the new backend, update the echoed
   `dist/` location messages (`Makefile:186-187`) to match reality.

5. **Confirm no tree pollution.** After a build, run `git status`. If any artifact
   lands somewhere unexpected (a repeat of the `packages/twinklr/twinklr/` nested-copy
   pattern, stray `*.egg-info`), that is a regression of this exact defect and must be
   fixed before this task is done — not deferred.

6. **Confirm the editable/dev-install path is unaffected.** `uv sync --extra dev
   --all-packages` (or `make install`) must still work after this task's changes, and
   `import twinklr.core` / `twinklr --help` must still succeed in the resulting
   environment (this is what `make verify-install`, `Makefile:254-262`, already checks —
   run it).

## Acceptance criteria

- `uv build` from `packages/twinklr/core/` produces a wheel containing real Python
  modules (not dist-info-only) — verified by unzipping the wheel and confirming
  `twinklr/core/__init__.py` and a representative subpackage (e.g.
  `twinklr/core/agents/`) are present with real file sizes, not zero-byte stubs.
- `uv build` from `packages/twinklr/cli/` likewise produces a wheel containing
  `twinklr/cli/main.py` and the console-script entry point metadata
  (`project.scripts.twinklr`).
- Installing the built wheel into a **fresh, non-workspace venv** and running
  `python -c "import twinklr.core"` (core) / the `twinklr` console script (cli) succeeds.
- `git status` is clean immediately after running the build (no nested source copies,
  no stray `*.egg-info`, `dist/` itself gitignored or otherwise not left as an untracked
  surprise).
- `make build` succeeds end to end from the repo root without manual path correction.
- `uv sync --extra dev --all-packages` (or `make install`) and `make verify-install`
  still pass after this task's changes — the editable dev-install path is unregressed.
- Both `packages/twinklr/core/setup.py` and `packages/twinklr/cli/setup.py` no longer
  exist.

## Tests

No new pytest tests — this is a packaging-infrastructure task with no Python-level
behavioral surface of its own. Verification is functional (build + inspect + install),
per Verification commands below. If Path B (physical restructure) is chosen, re-run the
**full** test suite afterward (`uv run pytest tests/ -v`) to confirm the physical move
did not break any test's path-relative assumptions (e.g. a test that computes a fixture
path relative to `__file__` inside a moved module) — this is a real risk specific to
Path B and must be checked even though this task does not add new tests.

## Verification commands

```bash
# Build both packages
cd packages/twinklr/core && uv build && cd -
cd packages/twinklr/cli && uv build && cd -

# Inspect wheel contents (adjust wheel filename to what was actually produced)
unzip -l packages/twinklr/core/dist/*.whl | head -30
unzip -l packages/twinklr/cli/dist/*.whl | head -30

# Confirm no tree pollution
git status

# Install the built wheel into a throwaway venv and confirm it actually works
python -m venv /tmp/twinklr-wheel-check
/tmp/twinklr-wheel-check/bin/pip install packages/twinklr/core/dist/*.whl
/tmp/twinklr-wheel-check/bin/python -c "import twinklr.core; print(twinklr.core.__version__)"
rm -rf /tmp/twinklr-wheel-check

# Confirm make build works end to end
make build

# Confirm editable dev-install path is unregressed
uv sync --extra dev --all-packages
make verify-install
uv run pytest tests/ -v   # full-suite regression check, esp. if Path B (physical move) was used

# Cleanup build artifacts before committing
rm -rf packages/twinklr/core/dist packages/twinklr/cli/dist
git status   # confirm clean
```

## Effort & risk

**L** (large, relative to the other Phase 0 tasks). This is not a config toggle — it is
resolving a genuine mismatch between the physical directory layout (project root =
package source root, dotted import name's parent lives outside the project root) and
what any standard PEP-517 backend (`uv_build` included) expects. Main risks: (1) if
Path A's namespace/module-root config turns out to be unsupported for this exact shape,
the fallback (Path B) is a real file-move across hundreds of files under
`packages/twinklr/core/` and `packages/twinklr/cli/` — high surface area for something
to reference the old physical path (test fixtures, `Makefile`, CI, `.gitignore`
patterns, editor configs) even though no Python import statement changes; mitigate with
a full-suite test run and a repo-wide `grep` for the old path prefix
(`packages/twinklr/core/` outside of `packages/twinklr/core/src/`) before considering
the move complete; (2) do not let this task's file moves collide with P0-T3's
`pyproject.toml` edits to the same file (`packages/twinklr/core/pyproject.toml`) — check
for conflicts before merging, since both tasks are independent (Lane B vs Lane A) and
may run concurrently in separate worktrees; (3) verify the editable-install path
(`uv sync`) is re-tested after any change, since that is the path every other developer
and every other Phase 0 task's `uv run` commands depend on — regressing it would be far
more disruptive than the empty-wheel bug this task fixes.
