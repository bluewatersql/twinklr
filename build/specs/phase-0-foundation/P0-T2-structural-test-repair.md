# P0-T2 — Structural test repair

Phase: 0-foundation · Lane: A (config/tooling, serial: T1→T2→T3→T4) · Executor: sonnet ·
Verifier: opus · Depends on: —

## Objective

Bring the unit test suite to a state where `uv run pytest tests/ -v` fails **only** on
tests whose data dependency is genuinely absent from a clean checkout (never on tests
that reference nonexistent tooling), and where a representative subset of
template-dependent tests runs everywhere via a minimal tracked fixture set. Concretely:
delete the 60 tests that reference six `scripts/build/*` tools that do not exist in this
repository; add a `requires_template_data` marker + fixture-presence skip for the 52
tests that fail only because `data/templates/index.json` is absent, and commit a minimal
tracked template fixture set so a representative subset of those 52 exercises real
behavior on every checkout; vendor/pre-fetch the NLTK `averaged_perceptron_tagger_eng`
resource so the 8 NLTK-dependent tests pass offline.

## Evidence & background

- **Findings CC-2 / CC-7** (`changes/twinklr-reactivation-review/reviews/findings.md`):
  CC-2 "Authored-for-nonexistent-entry-points class: ... 60 tests for six nonexistent
  scripts/build tools ..." (REMOVE/rebuild-from-intent → RM-0.2, RM-1.6); CC-7
  "Test-system integrity: ... 112 structural failures from clean checkout ... NLTK
  network dep" (FIX → RM-0.2, RM-1.6).
- **Stage 4 runtime baseline** (`reviews/verification.md` §"Stage 4 runtime baseline —
  RESULTS"): `uv run pytest tests/ -v` → exit 1, **120 failed, 4040 passed, 15 skipped**
  in 2m42s. Classification (all 120 accounted for):
  - **60** — tests for nonexistent `scripts/build/*` tools (`generate_effect_templates`,
    `upgrade_template_layers`, `backfill_template_metadata`, `align_templates`,
    `audit_template_structure`, `build_coverage_gap`): `FileNotFoundError` on the script
    path. BASELINE, never-passing on this tree.
  - **52** — missing gitignored `data/templates/index.json` (display composition 50,
    `recipe_builder/test_pipeline` 1, `agents/test_taxonomy_utils` 1). BASELINE
    structural defect: the unit suite depends on corpus-generated local data that no
    clean checkout can have.
  - **8** — NLTK resource not downloaded (`averaged_perceptron_tagger_eng` LookupError
    in g2p/phoneme tests). ENVIRONMENTAL (one-time network download) — but "unit tests
    require a live NLTK download" is itself a finding (offline-hostile test dep).
- **Re-verified directly against the current tree** (this spec, baseline `aa8d325`):
  running the full suite reproduces exactly **120 failed, 4040 passed, 15 skipped** with
  an identical breakdown. The full failure classification, confirmed by running
  `uv run pytest tests/ -q` and inspecting each failure's traceback:

  **The 6 nonexistent-`scripts/build/*`-tool test files (60 tests, exact per-file counts
  confirmed via `grep -c '^def test_\|^    def test_'` and pytest collection):**

  | Test file | Test count | Script it imports (does not exist) |
  |---|---|---|
  | `tests/unit/scripts/test_generate_effect_templates.py` | 15 | `scripts/build/generate_effect_templates.py` |
  | `tests/unit/scripts/test_upgrade_template_layers.py` | 12 | `scripts/build/upgrade_template_layers.py` |
  | `tests/unit/scripts/test_align_templates.py` | 10 | `scripts/build/align_templates.py` |
  | `tests/unit/scripts/test_backfill_template_metadata.py` | 10 | `scripts/build/backfill_template_metadata.py` |
  | `tests/unit/scripts/test_audit_template_structure.py` | 8 | `scripts/build/audit_template_structure.py` |
  | `tests/unit/scripts/test_coverage_gap.py` | 5 | `scripts/build/build_coverage_gap.py` |

  Total: 15+12+10+10+8+5 = **60**. Each file loads its target script via
  `importlib.util.spec_from_file_location(...)` / `spec.loader.exec_module(module)`
  against a hardcoded path under `scripts/build/` (confirmed by reading
  `test_generate_effect_templates.py:8,37-42`); `scripts/build/` does not exist anywhere
  in the current tree (`ls scripts/` confirms — only `analysis/`, `demo_*.py`,
  `validation/`, `docs/`, and a handful of standalone `.py` files exist, no `build/`
  subdirectory) and every one of these tests fails with
  `FileNotFoundError: [Errno 2] No such file or directory:
  '/…/scripts/build/<name>.py'` at collection/setup time — confirmed by direct run of
  `test_generate_effect_templates.py`.

  **The 52 `data/templates/index.json`-dependent tests (exact file-level breakdown,
  reproduced by running the full suite and grouping failures by file):**

  | Test file | Failures |
  |---|---|
  | `tests/unit/sequencer/display/composition/test_engine.py` | 27 |
  | `tests/unit/sequencer/display/composition/test_sequenced.py` | 11 |
  | `tests/unit/pipeline/test_display_stages.py` | 9 |
  | `tests/unit/sequencer/display/test_renderer_overlay.py` | 3 |
  | `tests/unit/recipe_builder/test_pipeline.py` | 1 |
  | `tests/unit/agents/test_taxonomy_utils.py` | 1 |

  Total: 27+11+9+3+1+1 = **52**, matching Stage 4's "display composition 50 [=27+11+9+3],
  recipe_builder/test_pipeline 1, agents/test_taxonomy_utils 1" exactly. Confirmed root
  cause by running `test_engine.py::TestCompositionEngine::test_basic_composition`
  directly: `FileNotFoundError: [Errno 2] No such file or directory:
  '/…/data/templates/index.json'` raised from a `Path.read_text()` call; `data/templates`
  does not exist in this checkout (`ls data/templates` → no such file or directory — the
  directory is gitignored per `AGENTS.md` "Repository hygiene": `data/`, `artifacts/` are
  generated/local and never committed).

  **The 8 NLTK-dependent tests:**

  | Test file | Failures |
  |---|---|
  | `tests/unit/audio/phonemes/test_g2p_service.py` | 4 |
  | `tests/unit/audio/phonemes/test_bundle.py` | 4 |

  Confirmed by direct run: `LookupError` from `nltk/data.py:579` —
  `Attempted to load taggers/averaged_perceptron_tagger_eng`, with the standard NLTK
  "Resource not found... `nltk.download('averaged_perceptron_tagger_eng')`" message,
  searched across `~/nltk_data`, `.venv/lib/nltk_data`, etc. and not found in any of
  them.

- **60 + 52 + 8 = 120**, the full and only classification of every current pytest
  failure — confirmed exhaustively, no residual unclassified failures.
- **Known-test-failures memory is stale**: `reviews/verification.md` notes
  "The known-test-failures memory is REFUTED in both directions
  (`memories/learnings/known-test-failures.md`): all four listed tests PASS at baseline
  ..., while 120 other tests fail. The memory must be replaced at closeout with this
  verified record." This spec's completion is the trigger to update that memory file
  (`memories/learnings/known-test-failures.md`) — see Definition of Done in `AGENTS.md`.

## Notes for spec authors (from `build/plan/01-phase-0-foundation.md`, copied verbatim)

> T2's tracked-fixture decision is design-bearing: pick the smallest recipe/template set
> that lets `test_engine.py`-class tests assert real behavior (coordinate with P1K-T4's
> seed catalog — same data, one home).

This is a real, live constraint on this task: the minimal tracked template fixture set
you commit here becomes the seed for Phase 1K's catalog-in-git work (`P1K-T4`, described
in `build/plan/03-phase-1k-knowledge-edges.md`). Do not invent a throwaway fixture format
disconnected from that later task — read `03-phase-1k-knowledge-edges.md`'s P1K-T4 row
before choosing the fixture's shape and location, so the two tasks share one fixture
set rather than each authoring its own. If P1K-T4 has not yet landed a home for the
seed catalog when you execute this task, place the fixture at
`data/templates/` (gitignored path, but the point of this task is to add committed
override files there — see Implementation approach) using the exact schema
`display composition`'s `test_engine.py`/`test_sequenced.py` and
`test_display_stages.py`/`test_renderer_overlay.py` expect (reverse-engineer the schema
by reading what `data/templates/index.json` is expected to contain from the failing
tests' fixtures/mocks, not by inventing a new one), and leave a comment/README noting
this is the P1K-T4 coordination point so the later task's author finds it.

## Current behavior

- `uv run pytest tests/ -v` fails with exit 1: 120 failed, 4040 passed, 15 skipped.
- 60 of those failures are `FileNotFoundError`s from tests written against a
  `scripts/build/` directory that has never existed in the tree reachable from this
  checkout (per `AGENTS.md`'s hygiene rules, `scripts/build/` is not in `.gitignore`
  either — it is simply absent; whether it was ever committed and later deleted is not
  something this task needs to resolve, since the remediation is deletion either way).
- 52 failures are `FileNotFoundError`/parse failures against `data/templates/index.json`,
  which is legitimately absent from any clean checkout because `data/` is gitignored
  generated/local state (`AGENTS.md` "Repository hygiene").
- 8 failures are `LookupError`s from an NLTK POS-tagger resource that is not vendored
  and requires a network download on first use.
- `tests/unit/scripts/` currently contains 6 files (60 tests) entirely dedicated to the
  nonexistent-script class; `tests/unit/scripts/validation/` (not affected by this task)
  contains other, passing tests.

## Target behavior

- `uv run pytest tests/ -v` from a **clean checkout with no network access and no
  vendor/manual data staging** exits 0, or fails only on tests explicitly marked/skipped
  for a documented, unavoidable reason (e.g., genuinely optional live-API tests already
  marked `LOCAL-ONLY`/`integration` elsewhere in the tree — out of this task's scope).
- The 60 nonexistent-script tests no longer exist (the six files under
  `tests/unit/scripts/` that reference `scripts/build/*` are deleted). If any of those
  six scripts represent product intent worth keeping, that is a **separate**,
  later decision (P0's plan explicitly scopes this as REMOVE, not rebuild — see CC-2's
  disposition "REMOVE/rebuild-from-intent → RM-0.2, RM-1.6"; this task performs the
  REMOVE half only).
- The 52 `data/templates`-dependent tests carry a `requires_template_data` pytest marker
  and skip cleanly (not fail) when the fixture data is absent, **and** a minimal tracked
  fixture set is committed so that a representative subset of these tests (not
  necessarily all 52 — see Implementation approach) runs and asserts real behavior on
  every checkout, clean or not.
- The NLTK `averaged_perceptron_tagger_eng` resource is either vendored into the repo (or
  fetched deterministically at `make install`/`uv sync` time from a pinned, checksummed
  source) so the 8 dependent tests pass without requiring a live, un-pinned
  `nltk.download()` call during test collection or execution.

**Non-goals**: this task does not restore or rebuild any of the six
`scripts/build/*` tools; does not change `data/templates/index.json`'s runtime consumer
code (only test fixture behavior); does not touch the NLTK-consuming production code
paths (`audio/phonemes/*`), only the test-time resource availability.

## Implementation approach

**1. Delete the 60 nonexistent-script tests.**

Delete these six files entirely:
```
tests/unit/scripts/test_generate_effect_templates.py
tests/unit/scripts/test_upgrade_template_layers.py
tests/unit/scripts/test_align_templates.py
tests/unit/scripts/test_backfill_template_metadata.py
tests/unit/scripts/test_audit_template_structure.py
tests/unit/scripts/test_coverage_gap.py
```
Confirm before deleting that `tests/unit/scripts/validation/` and any other files in
`tests/unit/scripts/` are untouched (they test `scripts/validation/*`, which does exist
and is out of scope). Re-run `uv run pytest tests/unit/scripts/ --collect-only -q`
before and after to confirm the six files are gone and nothing else in that directory
regressed.

**2. Add a `requires_template_data` marker for the 52 template-dependent tests.**

- Register the marker in `pyproject.toml`'s `[tool.pytest.ini_options]` `markers` list
  (alongside the existing `integration`/`slow` markers at
  `pyproject.toml:154-157` — re-verify the exact line range before editing) with a
  one-line description, e.g. `"requires_template_data: test needs data/templates/index.json (skips if absent, always-present subset covered by tracked fixtures)"`.
- Add a `conftest.py`-level `pytest_collection_modifyitems` or per-test
  `@pytest.mark.skipif` guard (prefer a `conftest.py` fixture-presence check, consistent
  with how `tests/integration/profiling/test_profiler_integration.py` already
  `pytest.skip()`s when vendor fixtures are absent — reuse that pattern rather than
  inventing a new one) so that tests carrying `requires_template_data` skip with a clear
  reason (`"data/templates/index.json not present; run <the FE/recipe pipeline or
  commit fixtures> first"`) instead of failing, whenever the underlying data is
  genuinely absent for a specific test's exact fixture requirement.
- Apply the marker to the specific tests in the six files listed above (27 in
  `test_engine.py`, 11 in `test_sequenced.py`, 9 in `test_display_stages.py`, 3 in
  `test_renderer_overlay.py`, 1 in `test_pipeline.py`, 1 in `test_taxonomy_utils.py`) —
  do not mark tests in these files that do not currently fail (mark only the specific
  52 test functions/methods that fail today; re-verify the exact set by running each
  file and matching against the failure list above, since a file may contain both
  template-dependent and template-independent tests).

**3. Commit a minimal tracked template fixture set.**

- Read `build/plan/03-phase-1k-knowledge-edges.md`'s P1K-T4 task row first (see "Notes
  for spec authors" above) to avoid diverging from the seed-catalog shape Phase 1K will
  build on.
- Reverse-engineer the expected `data/templates/index.json` schema (and whatever
  companion template files it indexes) from what the 52 failing tests actually load —
  read the fixture/setup code in `test_engine.py`, `test_sequenced.py`,
  `test_display_stages.py`, `test_renderer_overlay.py`, `test_pipeline.py`, and
  `test_taxonomy_utils.py` to determine the minimal `index.json` + template file shape
  that satisfies their setup without editing the tests' assertions.
- Choose the **smallest** fixture set that lets `test_engine.py`-class tests assert real
  behavior (per the plan's explicit design-bearing note above) — this does not have to
  be a full recreation of a production `data/templates/` tree; a handful of
  representative templates covering the code paths these specific tests exercise is the
  target.
- Commit this fixture set at a path that does not collide with the gitignored
  `data/templates/` runtime directory — either (a) commit fixture files under
  `tests/fixtures/templates/` (or an equivalent `tests/`-scoped fixture directory
  consistent with existing conventions — check `tests/unit/conftest.py` and sibling
  `conftest.py` files for the repo's existing fixture-directory convention before
  choosing) and have the relevant tests' fixtures point there instead of the hardcoded
  `data/templates/index.json` path, **or** (b) if reusing the exact
  `data/templates/index.json` path is unavoidable because production code (not just
  tests) hardcodes that path, add a narrow, explicit `.gitignore` exception
  (`!data/templates/index.json` plus whatever companion files) so this specific fixture
  set is tracked while the rest of `data/` remains ignored. Prefer (a); only use (b) if
  the coupling to the exact runtime path cannot be avoided without changing production
  code (which is out of this task's scope).
- After committing the fixture set, re-run the 52 previously-failing tests. Tests that
  now pass against the tracked fixture should have their `requires_template_data` marker
  removed (they no longer need it) or converted to a marker that always resolves true
  against the tracked fixture (your choice — the acceptance criterion is that they run
  and pass on every checkout, not that the marker itself survives). Tests that still
  need a fuller, non-minimal dataset (if any) keep the marker and its skip behavior.

**4. Vendor/pre-fetch the NLTK resource.**

- Determine the smallest viable mechanism: either (a) vendor the
  `averaged_perceptron_tagger_eng` resource file(s) directly into the repository (check
  its size first — NLTK POS-tagger pickles are typically small, a few MB; if it exceeds
  a size that would bloat the repo unreasonably, prefer (b)), or (b) add a pinned,
  checksummed download step to `make install`/`make sync` (e.g., a `python -c
  "import nltk; nltk.download('averaged_perceptron_tagger_eng')"` step with a version/
  checksum pin if NLTK's download mechanism supports one, or a direct pinned URL fetch)
  that runs once at setup time rather than lazily during test collection.
- Whichever mechanism is chosen, `tests/unit/audio/phonemes/test_g2p_service.py` and
  `tests/unit/audio/phonemes/test_bundle.py` must pass with **no network access at test
  time** (the setup/vendoring step may use network; the test run itself may not).
- Document the mechanism in whatever onboarding doc covers `make install` (coordinate
  with P0-T6, which also touches onboarding truth — do not duplicate; if P0-T6 has
  already landed when you do this, add one line there rather than a new doc).

## Acceptance criteria

- `tests/unit/scripts/test_generate_effect_templates.py`,
  `test_upgrade_template_layers.py`, `test_align_templates.py`,
  `test_backfill_template_metadata.py`, `test_audit_template_structure.py`, and
  `test_coverage_gap.py` no longer exist in the repository.
- `pyproject.toml` registers a `requires_template_data` marker with a description.
- A tracked template fixture set exists in git (not gitignored) at a documented path,
  and at least the tests in `test_engine.py`/`test_sequenced.py` that the fixture set
  targets pass against it without skipping, on a clean checkout, with no
  corpus-generation step run first.
- `tests/unit/audio/phonemes/test_g2p_service.py` and `test_bundle.py` pass with network
  access disabled at test-run time (verified per Verification commands below).
- `uv run pytest tests/ -v` from a clean checkout: zero failures classified as
  `FileNotFoundError` against `scripts/build/*` (because those tests are deleted); zero
  failures classified as `FileNotFoundError`/`LookupError` against
  `data/templates/index.json` or the NLTK resource (either passing against tracked
  fixtures/vendored resource, or cleanly skipped with `requires_template_data` and a
  clear reason — not a hard failure).
- `git status` clean after the fixture-commit step (no stray untracked generated files
  left behind by whatever process was used to derive the fixtures).

## Tests

- No new test *behavior* is invented — this task's job is to make existing tests either
  run for real (against tracked fixtures) or skip cleanly, not to write new assertions.
- Exception: if the marker/skip machinery itself needs a smoke test (e.g., a test
  confirming that `requires_template_data`-marked tests skip cleanly when the fixture
  directory is absent, for defense against future regressions), add one minimal test for
  the marker mechanism itself under `tests/unit/` (e.g.
  `tests/unit/test_pytest_markers.py` or alongside the `conftest.py` change) — TDD:
  write this test first if you add it, confirming it fails before the marker/skip logic
  exists and passes after.

## Verification commands

```bash
# Full suite, clean-checkout simulation (no data/templates present, no manual staging)
uv run pytest tests/ -v

# Confirm the six deleted files are gone and nothing else in tests/unit/scripts/ broke
ls tests/unit/scripts/
uv run pytest tests/unit/scripts/ -v

# Confirm the tracked fixture subset runs and passes
uv run pytest tests/unit/sequencer/display/composition/test_engine.py tests/unit/sequencer/display/composition/test_sequenced.py -v -m requires_template_data

# Confirm NLTK-dependent tests pass with no network (adjust to this machine's offline-simulation method, e.g. a firewall rule or NLTK_DATA env pointed only at the vendored/pre-fetched path)
NLTK_DATA=<vendored-or-prefetched-path> uv run pytest tests/unit/audio/phonemes/test_g2p_service.py tests/unit/audio/phonemes/test_bundle.py -v

git status   # confirm no stray generated files
```

## Effort & risk

**M** (medium). Main risks: (1) the minimal fixture set for `data/templates/index.json`
may require deeper reverse-engineering of the FE/recipe-builder artifact schema than a
first read suggests — mitigate by reading the P1K-T4 plan section first, and by treating
"a representative subset passes" (not "all 52 pass without skip") as the acceptance bar,
per the plan's own framing; (2) NLTK resource vendoring size/licensing — mitigate by
checking the resource's size and NLTK's own license/redistribution terms before choosing
vendor-in-repo vs. pinned-fetch-at-install; (3) coordination collision with P1K-T4 if
both tasks run in parallel worktrees and each invents an incompatible fixture shape —
mitigate by checking `changes/`/`build/specs/phase-1k-knowledge-edges/` for a P1K-T4 spec
before finalizing the fixture schema, and flagging the orchestrator if one doesn't yet
exist to sequence instead of guess.

## Orchestrator reconciliation note (2026-08-13)

The template-data home is **`catalog/templates/`** (tracked), per P1K-T3 — not a
separate `tests/fixtures/templates/` copy. This task's fixture work becomes: (a) a
pytest fixture that loads the tracked catalog from `catalog/templates/` when present,
(b) the `requires_template_data` marker/skip for tests needing corpus-scale data
beyond the seed catalog, and (c) at most a tiny `tests/fixtures/templates-extra/`
for pathological test-only recipes (malformed/edge cases that don't belong in the
real catalog). One data home; tests consume it, never fork it. If this task executes
before P1K-T3, create `catalog/templates/` with the minimal seed subset and P1K-T3
extends it.
