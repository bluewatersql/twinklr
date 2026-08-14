# P1K-T4 — recipe_builder session hardening

Phase: 1K · Lane: CAT · Executor: sonnet · Verifier: sonnet · Depends on: P1K-T3

## Objective

Turn `recipe_builder`'s curation workflow from a standalone demo script into a
first-class `twinklr` CLI command that operates against the git-tracked
`catalog/templates/` home established in P1K-T3, verify the staged→promote
gate works end-to-end against that new home, and fix two named, low-risk
code-quality defects the corpus-intelligence review flagged in this same file
scope: a silent parquet-read-error swallow and an unvalidated default
corpus-root path.

## Evidence & background

**No CLI/Makefile entry point today** (corpus-intelligence review,
"recipe_builder is a coherent, safety-conscious design" section): "its
principal defect is not design quality but total disconnection: no
CLI/Makefile entry (only `scripts/demo_recipe_builder.py`, a full standalone
argparse wrapper, confirmed zero references from `cli/main.py` or
`pipeline/definitions/`)". `scripts/demo_recipe_builder.py` is ~300+ lines of
its own `argparse` setup, entirely separate from `packages/twinklr/cli/main.py`.

**Existing CLI extension point** — `packages/twinklr/cli/main.py::build_arg_parser()`
(`main.py:331-353`) uses a single `argparse` subparsers pattern:

```python
sub = p.add_subparsers(dest="cmd", required=True)
run = sub.add_parser("run", help="Run the full pipeline")
run.add_argument("--audio", required=True, ...)
...
```

This is the one existing example to extend from (per P6-F3's evidence: "the
`twinklr` console script is argparse-only with exactly one subcommand (`run`,
`cli/main.py:331-353`) and no dispatch pattern to extend from except that one
example").

**Existing staged-only safety design, unchanged by this task**
(`recipe_builder/pipeline.py:113-118`, printed banner: *"NOTE: All outputs are
staged only — not merged into the live library."*). The sole write path into
the live catalog is `recipe_builder/promotion.py::promote_staged_recipes()`,
requiring a deliberate second invocation
(`scripts/demo_recipe_builder.py:132-137,276`, `--promote`/`--promote-from`
flags) — `promote_staged_recipes` already skips recipes whose `recipe_id`
already appears in `index.json` (`promotion.py:82-83`, `existing_ids` set),
i.e. it is already idempotent-safe on re-run; this task verifies that
end-to-end against the new `catalog/templates/` home, it does not change the
promotion logic.

**Two named code-quality defects in this scope** (both from the
corpus-intelligence review's "Minor code-quality signals" section):

1. `feature_engineering/corpus_artifacts.py`'s `load_profile_artifacts._read_models`
   (around line 696-704, baseline `aa8d325`, re-verify before editing):

   ```python
   def _read_models(stem: str, model_cls: type[_BM]) -> tuple[Any, ...] | None:
       for ext in (".parquet", ".jsonl"):
           p = output_dir / f"{stem}{ext}"
           if not p.exists():
               continue
           if ext == ".parquet":
               try:
                   import pyarrow.parquet as pq
                   table = pq.read_table(p)
                   return tuple(model_cls.model_validate(row) for row in table.to_pylist())
               except (ImportError, Exception):
                   continue
           else:
               ...
   ```

   Verified defect: `ImportError` is already a subclass of `Exception`, so the
   tuple is redundant, and the broad `except (ImportError, Exception): continue`
   silently swallows *any* parquet-read failure (a genuinely corrupted or
   schema-incompatible `.parquet` file, not just "pyarrow not installed") and
   falls through to the `.jsonl` sibling without logging — masking real
   corruption/format errors rather than surfacing them.

2. `feature_engineering/config.py:93-94`:

   ```python
   extracted_search_roots: tuple[Path, ...] = (Path("data/vendor_packages"),)
   music_repo_roots: tuple[Path, ...] = (Path("data/music"),)
   ```

   Verified defect: hardcoded default corpus-root paths on a frozen dataclass
   with no early existence/validation check — a caller who doesn't override
   these on a machine where the paths don't exist gets silent wrong-path
   behavior (an empty corpus, zero phrases mined) rather than a fail-fast
   error naming the missing path.

Full text: `changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
("Minor code-quality signals worth recording" section).

## Current behavior

`scripts/demo_recipe_builder.py` is the only way to run the recipe_builder
pipeline; it is invisible to `twinklr <cmd>` and to any test asserting CLI
surface completeness. `corpus_artifacts.py`'s parquet reader silently falls
back to JSONL (or returns `None`) on any parquet exception, indistinguishable
in logs from "pyarrow not installed" vs. "the parquet file is corrupt."
`feature_engineering/config.py`'s default corpus roots produce silent
zero-phrase output when absent, with no log line naming which path was
missing.

## Target behavior

1. **New `twinklr` CLI subcommand** wrapping `recipe_builder.pipeline.run_pipeline`
   and `recipe_builder.promotion.promote_staged_recipes`, added to
   `packages/twinklr/cli/main.py::build_arg_parser()` alongside the existing
   `run` subparser (naming is the executor's call — `curate-catalog` or
   `recipe-builder` are both reasonable; pick one and be consistent across the
   subcommand name, its help text, and any log lines). It must support at
   minimum: running the 5-phase pipeline (analysis→generation→enrichment→
   validation→admission) against a `--templates-dir` defaulting to
   `catalog/templates/` (P1K-T3's home, not `data/templates/`), and a
   `--promote` flag/second-subcommand mirroring
   `scripts/demo_recipe_builder.py`'s existing `--promote`/`--promote-from`
   behavior. `scripts/demo_recipe_builder.py` may remain as a thin deprecated
   shim calling into the same underlying functions, or be deleted — document
   whichever choice is made in the handoff; either is acceptable, but do not
   leave two divergent implementations of the same orchestration logic.
2. `corpus_artifacts.py::_read_models` (or its P1K-T1-renamed equivalent —
   re-verify the current name/line before editing) splits its exception
   handling:
   ```python
   except ImportError:
       continue  # pyarrow not installed; jsonl sibling is the legitimate fallback
   except Exception as exc:
       logger.warning("Parquet read failed for %s (%s): %s — falling back to jsonl", p, stem, exc)
       continue
   ```
   Both branches still fall through to the `.jsonl` check (behavior
   unchanged); only the observability changes — genuine corruption is now
   logged, not silent.
3. `feature_engineering/config.py`'s corpus-root defaults gain a visibility
   check at the point they are first consulted (not a hard failure — a fresh
   checkout legitimately has no corpus yet, and this is a local single-user
   tool, not a service with strict startup validation): when
   `extracted_search_roots`/`music_repo_roots` entries do not exist on disk at
   pipeline start, log a `logger.warning` naming the specific missing path(s)
   before proceeding (with zero-phrase output, unchanged from today). Do not
   raise; do not change the default path values themselves.
4. **End-to-end verification** of the staged→promote gate against the new
   home: run the full pipeline with `dry_run=True` (deterministic fallback
   generation only — no paid LLM calls) against a tmp copy of
   `catalog/templates/`'s shape, confirm staged outputs land under
   `run_dir/staged_recipes/` and are **not** visible in the tmp catalog's
   `index.json` until `promote_staged_recipes()` is explicitly called;
   confirm a second identical promote call is a no-op for already-promoted
   `recipe_id`s (exercising the existing `existing_ids` skip logic, not new
   code).

**Non-goals**: no change to the 5-phase pipeline's internal analysis/
generation/enrichment/validation/admission logic beyond the two named defects;
no change to `admission.py`'s classification rules (that mypy-only defect,
P6-M3, is a one-variable rename tracked separately — do not conflate it with
this task's scope unless the orchestrator has explicitly folded it in here);
no change to T2's active-learning wiring (separate task); no change to
`promote_staged_recipes()`'s idempotency logic — it is verified, not modified.

## Implementation approach

Files:

- `packages/twinklr/cli/main.py` — new subparser + dispatch branch in
  `build_arg_parser()` and wherever `main()`/the cmd-dispatch `if/elif` chain
  lives; wire to `recipe_builder.pipeline.run_pipeline` /
  `recipe_builder.promotion.promote_staged_recipes`.
- `packages/twinklr/core/feature_engineering/corpus_artifacts.py` —
  `_read_models` exception-handling split.
- `packages/twinklr/core/feature_engineering/config.py` — corpus-root
  existence-check + warning log, placed at the point the roots are first
  consulted (likely in the discovery/mining entry point that reads
  `extracted_search_roots`, not in the frozen dataclass itself, since the
  dataclass has no side-effecting `__post_init__` convention elsewhere in this
  module — check for one before adding).
- `scripts/demo_recipe_builder.py` — reduced to a thin shim or removed,
  per the executor's documented choice.

Sequencing: depends on P1K-T3 (the `catalog/templates/` home must exist and be
the default `templates_dir` before this task's CLI command and end-to-end test
can target it correctly).

## Acceptance criteria

- `twinklr <new-subcommand> --help` runs and documents the pipeline's phases
  and `--promote` behavior.
- Running the new subcommand with `--dry-run` against a tmp catalog directory
  produces the same `run_manifest.json`/staged-output shape
  `scripts/demo_recipe_builder.py` produces today (no regression in artifact
  content, only in entry point).
- `--templates-dir` defaults to `catalog/templates/`, not `data/templates/`.
- `_read_models` logs a `warning` on genuine parquet-read exceptions and stays
  silent (or logs at `debug`) on `ImportError` alone; both cases still fall
  through to the `.jsonl` sibling unchanged.
- A missing `extracted_search_roots`/`music_repo_roots` path produces a
  `warning` log naming the path, with output behavior otherwise unchanged
  (still zero phrases, not a raised exception).
- A staged-then-promoted recipe appears in the target catalog's `index.json`
  only after the explicit promote step, never after the analysis/generation/
  validation/admission phases alone; a second promote call for the same
  `recipe_id` is a documented no-op (asserted, not just assumed).

## Tests

- `tests/unit/cli/test_main.py` (or new `tests/unit/cli/test_recipe_builder_cmd.py`):
  argument-parsing test for the new subcommand (`build_arg_parser()` accepts
  the expected flags) and a smoke-run test invoking it end-to-end against a
  tmp `catalog/templates/`-shaped fixture with `dry_run=True`.
- `tests/unit/feature_engineering/test_corpus_artifacts.py`: add
  `test_read_models_logs_warning_on_parquet_corruption` (write a malformed
  `.parquet`-named file — or monkeypatch `pq.read_table` to raise a non-Import
  exception — assert a `warning` log call and that the function still falls
  through to `.jsonl`) and
  `test_read_models_silent_on_missing_pyarrow` (monkeypatch the import to
  raise `ImportError`, assert no `warning` log).
- `tests/unit/feature_engineering/test_config.py`: add
  `test_missing_corpus_root_logs_warning`.
- `tests/unit/recipe_builder/test_pipeline.py` or new integration test: full
  dry-run pipeline → stage → promote → re-promote (no-op) sequence against a
  tmp catalog directory, asserting `index.json`'s entry count only increases
  once.

## Verification commands

```bash
uv run python -m twinklr.cli.main <new-subcommand> --help
uv run pytest tests/unit/cli/ -q
uv run pytest tests/unit/feature_engineering/test_corpus_artifacts.py tests/unit/feature_engineering/test_config.py -q
uv run pytest tests/unit/recipe_builder/ -q
uv run ruff check packages/twinklr/cli packages/twinklr/core/feature_engineering packages/twinklr/core/recipe_builder
uv run mypy packages/twinklr/cli packages/twinklr/core/feature_engineering packages/twinklr/core/recipe_builder
```

No LOCAL-ONLY / paid-API steps — the required test budget is dry-run/
deterministic-fallback only; no live LLM calls are needed to verify this
task's acceptance criteria.

## Effort & risk

**M.** Mechanical CLI wrapping plus two small, well-isolated bug fixes. Main
risk: the new subcommand silently diverging from `scripts/demo_recipe_builder.py`'s
existing behavior (different default paths, dropped flags) — mitigated by the
smoke-run test comparing output shape, and by keeping the demo script as a
thin shim over the same functions if full removal feels risky to the
executor. Low risk on the two code-quality fixes — both are logging-only
changes with no behavior change to the success path.
