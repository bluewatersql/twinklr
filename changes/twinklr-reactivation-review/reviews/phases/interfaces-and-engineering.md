---
type: change
status: active
area: engineering
updated: 2026-08-13
---

# Phase 7 — Interfaces & Engineering

_Stage 3 phase review. Baseline `aa8d325`. Author: general-purpose (sonnet)
"phase7-author". Read-only against application code; this file is the only write
target. Verifier: "phase7-verifier" (critic-type, opus), Stage 7. A separate Stage 4
run executes the real test suite; where this review needed runtime truth (pytest/mypy/
ruff pass status), it is explicitly deferred to that run rather than executed here.
**Verified 2026-08-13 (opus critic, non-author) — see §10 and
`reviews/verification.md` "Phase 7" for the full verdict table: 3 ACCEPTED, 11
REVISED, 1 downgraded to INFO, 4 verifier-added findings adopted (P7-M1–M4). This
revision applies all required corrections; original author text is preserved where
the verifier accepted it._

## 1. Scope & exclusions

**In scope**: `packages/twinklr/cli/` (all files, `main.py` read in full — 363 lines);
`Makefile` (39 targets [corrected at verification; `grep -cE '^[a-zA-Z_-]+:' Makefile`
— 30 was an undercount], read in full); `.github/workflows/` (1 file); `scripts/` (32
files: 30 Python + 2 Markdown); `utils/video_demo.py`; `tests/` architecture (conftest
hierarchy, fixture strategy, mocking pattern, marker discipline, unit/integration
split quality — not individual test correctness, which is Stage 4's domain); `docs/`
site structure and drift risk (spot-checked against source, not exhaustively);
knowledge-tree governance docs (`AGENTS.md`, `context/`, `memories/`, `prompts/` —
assessed as engineering artifacts: internal consistency and followability, not
re-litigating Stage 1's content-accuracy findings); licensing absence;
`pyrightconfig.json`.

**Excluded** (owned by other phases, referenced not re-derived): workspace packaging
and version drift specifics (phase 1); pipeline framework/config/caching internals
(phase 1); LLM provider/agent internals (phase 3); `.xsq` parser/exporter defect
mechanics (phase 5); feature-engineering/corpus pipeline internals (phase 6, though
its **documentation** in `docs/pipeline_guide.md` is in scope here since docs
accuracy is an engineering-artifact question). No pytest/mypy/ruff/`make validate`
execution was performed by this author — all runtime-status claims below are marked
DEFERRED TO STAGE 4 or are static-evidence-only (file/path existence, grep, `git log`),
which required no execution.

## 2. Purpose, entry points, contracts, state, invariants, dependencies, consumers

**Purpose**: the human/CI-facing surface of Twinklr — the one shipped command
(`twinklr run`), the automation that is supposed to keep the codebase releasable
(`Makefile`, CI), the exploratory/offline tooling around the two pipelines
(`scripts/`), the test harness proving correctness, and the documentation and
knowledge-governance layer describing all of it.

**Entry points**: `twinklr run` (`cli/main.py:357-363` → `build_arg_parser` → single
`run` subparser); `make <target>` (39 targets, `Makefile`); GitHub Actions triggers
on push-to-`main` (Jekyll build/deploy only — `.github/workflows/jekyll-gh-pages.yml`);
`scripts/*.py` invoked ad hoc via `uv run python scripts/...`; `pytest` via
`testpaths = ["tests"]` (`pyproject.toml:149`).

**Contracts**: the CLI's contract with the pipeline layer is a `PipelineContext` +
`build_moving_heads_pipeline(...)` call (`main.py:206-218`) — CLI owns argument
parsing, config loading, session construction, and (see §4) a hardcoded display
topology; it does not own pipeline semantics. `Makefile`'s contract with the toolchain
is "target name documents an operation, body is the ground truth" — several targets
violate this by pointing at paths/files that no longer exist (§4). `scripts/`'s
contract is informal: no package `__init__.py`-level API, each script is a standalone
CLI with its own `argparse`.

**State**: none owned by this layer beyond what it constructs per-invocation (CLI
builds a fresh `TwinklrSession` and `PipelineContext` each run — see phase 1 for
session/cache internals). `tests/` state is fixture-scoped, no shared DB/filesystem
state observed at the conftest level.

**Invariants (as documented/implied)**: `OPENAI_API_KEY` must be set before `run`
executes (`main.py:158-166`); `make validate` must pass before any completion claim
(`AGENTS.md` "Development quality gates"); `testpaths` confines pytest collection to
`tests/` (`pyproject.toml:149`) — this invariant silently excludes `scripts/validation/
test_*.py` from ever running under pytest (§4, P7-F10).

**Dependencies**: CLI depends on `core.config`, `core.pipeline`, `core.sequencer.*`,
`core.session`, `core.utils.{formatting,logging}` (import list, `main.py:17-44`).
`Makefile` depends on `uv`, `ruff`, `mypy`, `pytest`, and (for two targets) a script
that does not exist (§4). CI depends only on GitHub's Jekyll action chain — no
dependency on `uv`, Python, or the test toolchain at all.

**Consumers**: end users invoke the CLI; developers invoke `Makefile` targets;
`scripts/` are consumed by developers manually (none are invoked by CI, and only
`test_audio_pipeline.py` is invoked by `Makefile`); `docs/` is consumed by GitHub
Pages visitors and (per its own citations) intended as the deep reference beneath
`context/`.

## 3. Representative execution paths inspected

1. **New-developer clone-to-run path**, traced statically end-to-end against
   `docs/user-guide.md` and `docs/developer-guide.md`: clone → `make install` (target
   exists, calls real `uv sync` — no defect) → `make verify-install` (exists, real
   commands) → set `OPENAI_API_KEY` → `twinklr run --audio ... --xsq ... --config
   ...`. **This path breaks at the credential step for a user who follows the guide's
   own "Option 2"** (§4, P7-F1) and **breaks entirely for a user attempting the
   corpus/FE quick start**, whose first documented command does not exist in the
   repository (§4, P7-F2).
2. **`make build` / `make test-unit` / `make test-integration` / `make coverage`**:
   traced by resolving every path each target references against the actual tree.
   All four fail on path/file resolution before any tool runs (§4, P7-F3–F5) —
   confirmed via `ls`/`find`, no execution needed.
3. **`make validate`**: traced step-by-step (`ruff format .` → `ruff check . --fix` →
   `mypy .` → `pytest tests/ -v`). All four referenced commands and paths are real.
   No defect in the target itself; the concern is architectural reuse in CI (§4,
   P7-F6).
4. **CLI `run` path**: traced `main()` → `run_pipeline` → `run_pipeline_async` →
   `build_display_graph()` → `build_moving_heads_pipeline(...)` → `PipelineExecutor.
   execute(...)`. Confirms the CLI never references `build_display_pipeline` — the
   second, fully-built pipeline (discovery §2) is unreachable from this file, and the
   display topology is authored as Python literals inside the presentation layer
   (`main.py:62-135`).
5. **Test discovery path**: traced `pyproject.toml` `[tool.pytest.ini_options]`
   against `tests/` and `scripts/validation/`. `testpaths = ["tests"]` means the two
   `test_*.py`-named files under `scripts/validation/` are never collected — confirmed
   they are `argparse` CLI harnesses, not pytest suites, by reading their headers.
6. **Marker-based test selection path**: traced `pytest.ini_options.markers`
   (`integration`, `slow`) against actual usage. **Corrected at verification**:
   `tests/integration/` contains 16 test files (not 25 as originally counted), 14 of
   which carry no `integration` marker; the 11 repo-wide marker hits land in only 2
   files, and `pytest -m integration` selects just those 2 files today — a starker
   gap than originally stated (enumerated in §4, P7-F7).

## 4. Implementation assessment

### CLI (`packages/twinklr/cli/main.py`, full file read)

- Single subcommand (`run`), five flags (`--audio`, `--xsq`, `--out`, `--app-config`,
  `--config`). Clean, readable, well-ordered console output via `rich`. The
  happy-path narration (config load → templates → display graph → pipeline validate →
  execute → results) is good UX for a CLI that is meant to be watched interactively.
- `build_display_graph()` (`main.py:62-135`) constructs a 3-group `ChoreographyGraph`
  (`MOVING_HEADS`, `OUTLINE`, `MEGA_TREE`) with hardcoded fixture counts, pixel
  fractions, and spatial zones. The docstring self-admits: "The layout parser will
  eventually auto-populate this; for now values are hardcoded as sensible defaults."
  This is domain/config construction embedded in the presentation-layer entry point —
  a layering violation independent of whether a layout parser should exist (that
  product question is Stage 2's; the layering placement is an engineering defect
  either way).
- **Added at verification (P7-M1, merged into this finding)**: the hardcoding runs
  deeper than the display graph. `main.py:208` passes a literal `fixture_count=4`
  into `build_moving_heads_pipeline(...)`, which flows into the planner prompt path
  (`stage.py:145` → `orchestrator.py:75`) — while the user's *actual* fixture config
  is resolved three lines later (`main.py:214-217`, `_resolve_fixture_config_path`)
  and never reconciled against the literal. On the only shipped path, any rig that
  does not have exactly 4 fixtures gets a planner that is told a false count.
  `min_pass_score=7.0` (`main.py:211`) is the same pattern: a second hardcoded
  operative value that silently overrides `job_config.agent.success_threshold`
  (documented in `docs/user-guide.md` as the config field for this, on a 0–100
  scale, while the CLI's literal is on a 0–10 scale — see P7-M2). Net effect: **the
  shipped CLI is correct only for the author's own display and fixture rig**, not a
  general-purpose entry point despite taking `--config`/`--app-config` as if it were.
- API-key gating (`main.py:158-166`) is a plain `os.getenv` check with a helpful error
  message that itself only advertises the `export` form, not `.env` — inconsistent
  with `docs/user-guide.md`, which advertises both (§ P7-F1).
- Error handling is coarse but adequate for a single-command tool: config-load
  failures, missing files, and pipeline validation errors each get a distinct
  message and non-zero exit code.
- No `--version` flag despite three separate version declarations existing elsewhere
  in the workspace (phase 1's finding; noted here only because the CLI is the natural
  place a user would look for one and doesn't find it).

### Build automation (`Makefile`, full file read)

- 39 targets (corrected at verification via `grep -cE '^[a-zA-Z_-]+:' Makefile`; this
  author originally undercounted at 30), well-organized into commented sections,
  consistent color-coded output convention, good `help` target using
  self-documenting `##` comments.
- **P7-M4 (added at verification)**: `.PHONY` (`Makefile:1`) lists 20 names but only
  19 of them correspond to real targets (`run-demo` is declared phony despite no such
  target existing anywhere in the file — a stale entry, likely predating a rename).
  That leaves 20 of the file's 39 real targets (including `test-unit`,
  `test-integration`, `clean-all`, `clean-venv`, `env-check`, `lock`, and others)
  undeclared. No naming collision with a real file/directory was found today, so
  this is inert in practice, but the declaration is incomplete and stale rather than
  deliberately scoped, and any future same-named path in the repo root would cause
  the corresponding target to silently no-op.
- `build` (target, not reviewed section) references `cd packages/core && uv build` and
  `cd packages/cli && uv build` — **confirmed absent**: the actual paths are
  `packages/twinklr/core/` and `packages/twinklr/cli/`. `packages/core` and
  `packages/cli` do not exist at any depth (`ls` confirms). This target fails
  immediately on `cd`.
- `test-unit` references `tests/test_value_curves.py tests/test_phase1_integration.py`;
  `test-integration` references `tests/test_e2e_value_curves.py tests/
  test_phase4_sequencer.py`. Of these four filenames, only one (`test_value_curves.py`)
  exists anywhere in the repository, and at a different path
  (`tests/unit/sequencer/display/composition/test_value_curves.py` — not
  `tests/test_value_curves.py`). **Corrected at verification**: this author's
  original causal story — "reference a flat layout that predates the current
  structure and were never updated when the suite was reorganized" — is disproved.
  The verifier checked full history (148 commits) and found the other three
  filenames (`test_phase1_integration.py`, `test_e2e_value_curves.py`,
  `test_phase4_sequencer.py`) **never existed at any path, at any point in the
  repository's history**. These targets were not broken by a later reorganization —
  they were authored referencing entry points that never worked, a day one defect
  rather than drift. This is a distinct remediation class (author-time error, not
  refactor debt) and is flagged to Stage 5/8 as such.
- `coverage` / `coverage-detailed` call `uv run python scripts/show_coverage_by_
  component.py`. **Corrected at verification**: this author's original claim that
  the script "does not exist anywhere in the repository... and no git history under
  that name either" is wrong. The script existed and was deleted on 2026-01-30
  (commit `c67bbdd`, "Refactor feedback management and improve documentation" — a
  cleanup commit whose message does not mention the deletion). It is restorable
  verbatim via `git show c67bbdd^:scripts/show_coverage_by_component.py`. The defect
  (both targets currently broken) stands; the severity is lower than originally
  assessed because remediation is a `git show`/`git restore` away, not a rewrite
  from scratch, and it downgrades from a "never built" pattern to ordinary deletion
  debt.
- `validate` (and its aliases `check-all`/`pre-commit`) is **not** broken — every
  command it runs (`ruff format .`, `ruff check . --fix`, `mypy .`, `pytest tests/
  -v`) resolves to a real path/command. The concern here is architectural, not a bug:
  it mutates the working tree (format + lint `--fix`) with no `git diff --exit-code`
  or equivalent guard on `validate` itself, then reports success based on the
  *post-mutation* state. **Corrected at verification**: this author originally
  claimed the whole pattern was unsafe for CI reuse and rated it HIGH; the guard
  pattern this finding calls for **already exists in the Makefile**, just not wired
  to `validate` — `lint-fix-unsafe-apply` (`Makefile:79-87`) implements exactly a
  `git diff --quiet && git diff --cached --quiet || { echo Error: uncommitted
  changes...; exit 1; }` checkpoint before mutating. Because that idiom is already a
  known, used pattern in this codebase, the gap is narrower and cheaper to close
  than "add CI-safety architecture from scratch" implied: `make lint` (`ruff check .`,
  no `--fix`), `make type-check` (`mypy .`), and `make test` (`pytest tests/ -v`)
  are each already non-mutating, CI-safe targets on their own today — a CI workflow
  could call all three directly right now with no Makefile changes. The one missing
  piece for a fully check-only CI variant of `validate` is formatting: `ruff format .`
  (mutating) has no check-only sibling (`ruff format --check .`) anywhere in the
  file. Severity revised down accordingly: this is a small, additive gap (one new
  target/CI step), not an architecture-level defect requiring new guard
  infrastructure.
- `clean` / `clean-cache` / `reset` / `clean-all` are careful, well-scoped, and
  correctly guarded (only ever remove generated artifacts, gitignored caches, or
  `.venv`) — no destructive-by-accident patterns found.
- `env-check` checks that `.env` *exists* and *contains the string* `OPENAI_API_KEY`
  (`grep -q "OPENAI_API_KEY" .env`) — it does not (and cannot, given nothing loads
  `.env`) verify the key is actually visible to a running process, and prints a
  green "✓ OPENAI_API_KEY is set" regardless. **Corrected at verification**: this is
  the actual locus of P7-F1's deception, not the CLI. The CLI's own failure mode
  (`main.py:158-166`) is loud and actionable — it prints "ERROR: OPENAI_API_KEY
  environment variable not set" plus the exact `export` remedy — so a developer who
  runs the CLI directly is not misled for long. It is specifically `make env-check`
  that tells a developer their setup is correct ("✓") when it is not, because it
  greps file contents instead of checking the process environment. Severity revised
  down from HIGH to MEDIUM; disposition narrowed from "load `.env` in the CLI" to
  "either fix `env-check` to test the actual environment (e.g. `env | grep
  OPENAI_API_KEY` after sourcing, or an explicit `uv run python -c` check) or delete
  the `.env` option from `docs/user-guide.md` entirely, whichever the remediation
  roadmap prefers" (see P7-F1 in §10).

### CI (`.github/workflows/`)

- Exactly one workflow, `jekyll-gh-pages.yml`, triggered on push to `main` and manual
  dispatch. It builds and deploys the `docs/` Jekyll site. **No workflow runs `ruff`,
  `mypy`, `pytest`, or any variant of `make validate`/`check-all`.** Every quality
  gate in this repository is local-manual only, with no enforcement at merge time.

### `scripts/` (32 files: 30 `.py`, 2 `.md`) — triage

| Category | Files | Assessment |
|---|---|---|
| **Promoted/real tool** | `scripts/validation/validate_artifacts.py`, `validate_agent_artifacts.py` | Genuinely unified entrypoints (README states "Legacy MH-only wrappers … were removed. Use `validate_artifacts.py` directly" — a real consolidation, not just a claim). Well-documented (`scripts/validation/README.md`), pipeline-aware (`--pipeline {auto,display,mh}`). **Not wired into `Makefile` or CI at all** — the only automated hook to any validation script is `test-audio*` (below). Candidate to promote further: add a `make validate-artifacts` target or a CI smoke job. |
| **Wired, working** | `scripts/test_audio_pipeline.py` | The one script actually invoked by `Makefile` (3 targets: `test-audio`, `test-audio-whisperx`, `test-audio-all`). Named with the `test_` prefix but is a manual CLI harness, not a pytest file (outside `testpaths`) — same naming ambiguity as the two files below, tolerated here only because it happens to be the one script someone remembered to wire up. |
| **Misleadingly named, uncollected** | `scripts/validation/test_prompt_validation.py`, `test_schema_validation.py` | Both are `argparse`-driven CLI harnesses with real, useful purposes (template rendering + taxonomy validation; cached-response schema validation) but are named exactly like pytest test files while living outside `testpaths = ["tests"]` — pytest never collects them. A developer grepping for "prompt validation tests" would reasonably expect `pytest` to run these; it silently does not. |
| **Demo/exploration, load-bearing** | `scripts/demo_sequencer_pipeline.py` | Per discovery §2, this is the **only caller anywhere** of `build_display_pipeline` — i.e., the sole runbook for the second, CLI-unreachable pipeline. Despite being load-bearing, it is referenced from `docs/pipeline_guide.md` only in passing (line 765) and has no dedicated "how to run the display pipeline" section pointing a new developer at it as the canonical way to exercise that code path. |
| **Demo/exploration, corpus-tooling** | `demo_asset_pipeline.py`, `demo_display_renderer.py`, `demo_eval_report.py`, `demo_feature_engineering.py`, `demo_moving_heads_pipeline.py`, `demo_profiling.py`, `demo_recipe_builder.py`, `demo_recipe_pipeline.py` | All last touched between 2026-01-31 and 2026-04-01, contemporaneous with the broader development slowdown (discovery §7.7). Several are referenced from `docs/pipeline_guide.md`; none from `Makefile`/CI. Legitimate reference material for the corpus-intelligence subsystem (phase 6), currently undiscoverable except by reading `docs/pipeline_guide.md` or browsing the directory — no `scripts/README.md` exists. |
| **Analysis (offline, data-dependent)** | `scripts/analysis/cross_lane_profile_analysis.py`, `normalize_unknown_effects.py`, `validate_rules_against_profiles.py` | One-off diagnostic tools for validator-rule-vs-corpus checks. Legitimately un-runnable in this repository state since they require `data/features/...` corpus artifacts that are gitignored and absent (consistent with discovery §6). Not dead code — orphaned by data absence, not by disuse. |
| **Template/corpus tooling** | `enrich_builtin_templates.py`, `evaluate_recipe_dictionary.py`, `query_template_retrieval.py`, `cleanup_display_templates.py`, `validate_fe_output.py` | Same data-dependency caveat. `query_template_retrieval.py` has zero references anywhere outside itself — most likely genuinely dead/exploratory. |
| **Orphaned, unrelated to product** | `utils/video_demo.py` | Lives outside `scripts/` entirely (inconsistent placement). Calls `client.videos.generate`/`retrieve` (OpenAI video generation) — an experimental prototype with **zero references anywhere** in application code, tests, docs, or `Makefile` (confirmed by repo-wide grep; the only hit is this review's own manifest). Unrelated to lighting choreography. Strong candidate for removal or, if intentionally kept as a spike, relocation + a one-line docstring explaining why it's there. |
| **Docs-only** | `scripts/docs/feature_engineering.md`, `scripts/validation/README.md` | Fine as-is; the asymmetry (one subdirectory documented, the rest not) is the finding, not these files themselves. |

**Cross-cutting scripts finding**: no top-level `scripts/README.md` indexes any of
this. `scripts/validation/README.md` covers 11 of the 30 Python files; the remaining
19 have no discoverability aid beyond in-file docstrings and scattered `docs/`
mentions.

### Tests architecture (`tests/`, 404 `test_*.py` files / 488 `.py` files total —
corrected at verification, this author originally undercounted the latter as "~460";
root `conftest.py` read in full)

- Directory split (`tests/unit/` — 25 subpackage-mirroring directories, `tests/
  integration/` — 14 sub-areas) is real and broadly mirrors `packages/twinklr/core/`
  layout, consistent with discovery's "404-file tree broadly mirroring the package
  layout" strength claim.
- Root `conftest.py` (159 lines) provides only domain fixtures (`BeatGrid`,
  `FixtureInstance`, template loading, JSON fixture loader) — **zero LLM/agent/
  provider fixtures**. Five additional `conftest.py` files exist under specific
  subpackages (`agents/sequencer/{group_planner,macro_planner}`, `audio`, `curves`,
  `recipe_builder`), none of which centralize LLM mocking either.
- Ad-hoc LLM mocking pattern (inherited finding, confirmed and characterized here):
  spot-checked `tests/unit/agents/providers/test_openai.py` and `tests/unit/agents/
  test_async_runner.py`. Each file hand-constructs `MagicMock()`/`AsyncMock()` around
  `OpenAIClient`/`AsyncOpenAI`, manually building `TokenUsage`, `LLMResponse`,
  `ResponseMetadata` objects and `usage.prompt_tokens`/`completion_tokens` mock
  attributes from scratch. `grep -rl "MagicMock\|AsyncMock"` across `tests/` returns
  57 files (confirmed clean at verification — count and pattern both held). This is
  not wrong per file, but it means the *shape* of a provider response is redefined
  ~57 times with no single source of truth — a real schema change to
  `LLMResponse`/`TokenUsage`/`ResponseMetadata` requires auditing every file
  individually, and any one of them drifting from the real shape produces a green
  test that asserts nothing meaningful about production behavior. **Revised at
  verification**: the harm above is inferred from the pattern, not demonstrated by
  an observed drift incident in this repo — severity down from MEDIUM-HIGH to
  MEDIUM on that basis. Sequencing note: since Stage 2 has since ruled on which
  subsystems are DEFER/ABANDON candidates, extracting a centralized fake should
  happen *after* that instrument-then-decide triage, not before — building shared
  test infrastructure for code paths Stage 2 may recommend deleting would be wasted
  effort.
- Marker discipline: `pyproject.toml:154-157` defines only `integration` and `slow`.
  `slow` has negligible use. `integration` is applied inconsistently: **corrected at
  verification** — `tests/integration/` holds 16 test files, not 25 as this author
  originally counted, and the gap is starker than originally stated: 14 of the 16
  carry no `@pytest.mark.integration` decorator, the 11 repo-wide marker hits land
  in only 2 files, and `pytest -m integration` selects just those same 2 files.
  Directory placement, not the marker, is effectively the entire selection
  mechanism today (enumerated by direct `grep -L`: `test_transitions_multi_layer.py`,
  `test_categorical_params_e2e.py`, `test_handler_categorical_params.py`,
  `test_fe_unified_pipeline_e2e.py`, `test_recipe_end_to_end.py`, `agents/
  test_learning_integration.py`, `audio/test_lyrics_analyzer_integration.py`, `api/
  test_llm_client.py`, `feature_engineering/test_fe_phase1_pipeline.py`, `agents/
  audio/lyrics/{test_context_shaping,test_runner}.py`, `agents/audio/profile/
  {test_context_shaping,test_runner}.py`, `agents/sequencer/group_planner/
  test_orchestrator_integration.py`). `pytest -m "not integration"` would still
  collect and run all 14 of these. The directory path, not the marker, is the only
  reliable selector today.
- `addopts` in `pyproject.toml:152` always runs with coverage collection
  (`--cov=twinklr.core --cov-report=...`) on every invocation of bare `pytest` —
  reasonable for local dev, adds constant overhead to every CI job that would run
  `pytest` directly without a lighter-weight variant for fast feedback loops.

### Docs site (`docs/`, structure + targeted spot-checks)

- Jekyll site (`primer` remote theme via `_config.yml`), five top-level pages plus
  two deep-dive series (`audio_profile/`, `feature_engineering/`). Reasonably
  organized; the one CI workflow in the repo exists solely to build/deploy this site.
- `docs/pipeline_guide.md` §1 "Quick Start — Unified Pipeline" — explicitly labeled
  "the recommended way to run the full workflow" — instructs `uv run python
  scripts/build/build_pipeline.py` as its very first command, repeated 9 times
  throughout the guide (`build_pipeline.py` ×5, `build_profile_corpus.py` ×2,
  `build_feature_engineering.py` ×2). **Corrected at verification**: this author's
  original claim that "`scripts/build/` has never existed in this repository's git
  history" is true for only 6 of the 10 references, not all of them. The verifier
  traced history and found `scripts/build/` was real and was deleted on 2026-02-24
  (commit `82aaf38`, "Refactor template handling and context shaping in choreography
  pipeline" — again a cleanup commit that does not call out the deletion in its
  message). 4 of the 10 references are ordinary stale-documentation-after-deletion;
  the other 6 (concentrated in the newer "Unified Pipeline" framing) reference a
  `build_pipeline.py` entrypoint name that does not match anything the deleted
  directory ever contained either, so those 6 remain "never existed as documented."
  **Remedy redirected at verification**: because the corpus/FE pipeline this guide
  describes is itself a Stage-2 ABANDON-candidate subsystem (unreachable from the
  CLI, last touched 2026-04-01 — discovery §2, §7.7), the fix is not to rewrite the
  guide toward a currently-correct entrypoint (which would invest further in a
  subsystem Stage 2 may recommend cutting); it is to mark the guide as describing
  that ABANDON-candidate subsystem's last-known state, pending Stage 2/8's decision
  on whether to restore, replace, or retire it. Severity (HIGH) is unchanged — the
  guide is still actively misleading today — but the disposition changed from FIX
  to "correct in place + flag as describing at-risk subsystem," not "make the
  quick-start work again."
- `docs/user-guide.md:73-77` presents two equally-weighted setup options: `export
  OPENAI_API_KEY=...` (works) and `cp .env.example .env` + edit (does not work,
  because nothing in the codebase loads `.env` — confirmed by `grep -rn
  "load_dotenv\|dotenv"` returning zero hits anywhere in `packages/` or any
  `pyproject.toml`). **Corrected at verification** (severity HIGH→MEDIUM; full detail
  under the `env-check` bullet above): the CLI's own failure at this point is loud
  and gives the exact remedy (`main.py:159-164`), so a developer working directly
  against the CLI recovers quickly. The genuinely deceptive step is `make env-check`
  (docs line 99), which prints "✓ OPENAI_API_KEY is set" after grepping only the
  file's contents — that is where a developer following "Option 2" gets a false
  green signal before hitting the CLI's real error with no explanation of why a
  variable they "set" isn't recognized. Preferred remedy per verification: fix
  `env-check` to test the actual process environment, or delete the `.env` option
  from the docs — over adding `python-dotenv` loading to the CLI, which this author
  originally favored (either remains a valid choice for Stage 8, this is not a hard
  ranking).
- **P7-M2 (added at verification, HIGH, CONFIRMED)** — dead-config-class
  verification: `docs/user-guide.md` documents several config fields as live
  behavior that the code silently ignores. Enumerated with line cites:
  `agent.token_budget` (`:146` — no-op, matches the inherited "token budget
  end-to-end" finding); `agent.judge_agent.model` (`:148` — never wired, the CLI's
  judge always uses whatever the pipeline definition hardcodes, not this field);
  `channel_defaults.{shutter,color,gobo}` (`:152-154` — zero readers found);
  `checkpoint` (`:157`, elaborated at `:296` — zero readers, `PipelineContext.
  checkpoint_dir` is declared but never read per discovery §3, and the doc's claim
  "Re-running after fixing the error will reuse cached results for completed
  stages" (`:296`) is a **false resume promise**); `logging.level` (`:121` — the CLI
  bypasses `AppConfig.logging` entirely and hardcodes its own `configure_logging`
  call, per the inherited "two `configure_logging` implementations" finding); and
  the shutter/color/gobo curve claims at `:245` (disproved — see phase 4/5 for the
  rendering-side detail). **Every one of these fails silently — no error, no
  warning, just documented behavior that doesn't happen.** This elevates from "one
  or two isolated dead-config findings" (which several phases had already noted
  individually) to a confirmed *class*: `docs/user-guide.md`'s configuration
  reference is not a reliable description of runtime behavior, and a reader has no
  way to tell which of its documented fields are live from the doc alone.
- **P7-M3 (added at verification, MEDIUM, CONFIRMED)**: `docs/developer-guide.md:348`
  ("Key Scripts" table) has 2 of its 5 rows pointing at nonexistent files —
  `build_pipeline.py` ("in `scripts/build/`", the deleted directory above) and
  `show_coverage_by_component.py` (deleted 2026-01-30 per P7-F5) — a 40% error rate
  in the one table meant to orient a new developer around `scripts/`.
- Other spot-checks (developer-guide.md directory tree) were broadly accurate aside
  from the table above; the two docs (`pipeline_guide.md`, `developer-guide.md`)
  share overlapping drift, consistent with a single historical rename/restructure
  that was never fully propagated to either.

### Knowledge trees as engineering artifacts (`AGENTS.md`, `context/`, `memories/`,
`prompts/`)

- `AGENTS.md` (125 lines) is internally consistent on a full read: it states a clear
  router role, an explicit source-of-truth hierarchy, a memory protocol with
  concrete steps, a change-management protocol, and a "definition of done" that
  cross-references `make validate` — which (per above) is itself sound as a local
  command. No self-contradiction found. The one soft tension: "Definition of done"
  requires `make validate` to pass with "fresh output as evidence," but nothing in
  `AGENTS.md`/`CLAUDE.md` flags that three other `make` target groups (`build`,
  `test-unit`/`test-integration`, `coverage*`) are broken — a new contributor
  reading only the governance docs would have no warning before hitting them.
- `context/INDEX.md`, `prompts/INDEX.md`, `changes/ACTIVE.md`, `memories/INDEX.md`
  all exist and are wired as described. The "load only relevant context" protocol
  in `AGENTS.md` step 3 is followable — each `context/` doc is short and scoped.
- `context/current-state.md` itself carries one of the "2 stale context-doc claims"
  (owned by discovery/phase-3 territory for content, noted here only as a governance
  observation): it states "planner → heuristic validator → **LLM validator** →
  judge loop" in its "Implemented" bullet list — the same removed-role claim
  `multi-agent-planning.md` carries. Because `current-state.md` is explicitly the
  step-1 "Start here" document in `context/INDEX.md`, this is the most-read stale
  claim in the entire knowledge tree, not a peripheral one.
- `pyrightconfig.json` sets `"typeCheckingMode": "basic"` and is not referenced by
  any `Makefile` target, CI job, or documentation (`context/engineering/
  conventions.md` documents only `mypy` as "strict"). It is a live, loadable config
  (any contributor using Pyright/Pylance in VS Code gets it automatically) asserting
  a weaker standard than the project's documented one, with no wiring to keep it
  aligned or flag drift.

### Licensing

- No `LICENSE` file at any path; no `license` field in any of the three
  `pyproject.toml` files (root, `core`, `cli`) — confirmed by direct read. Material
  for Stage 2's product-strategy verdict (discovery §7.8) as much as an engineering
  gap: the project reads/writes a third-party application's proprietary-ish format
  and sits atop a mixed-license audio stack with no declared terms of its own.

## 5. Tests & validation assessment

Test *architecture* (not runtime pass/fail, which is Stage 4's job):

- Structural split (unit/integration by directory) is real and mostly sound.
- Marker-based fast/slow or unit/integration selection is not reliable today (§4).
- No centralized LLM-provider fake exists; the cost is duplicated response-shape
  assumptions across ~57 files rather than a single fixture module, and no assurance
  that all 57 stay in sync with the real provider contract as it evolves.
- No round-trip/golden-file test category exists anywhere in `tests/` (repo-wide —
  this is a test-architecture gap this phase can assess generally; its most visible
  consequence, the `.xsq` template-content-loss defect, is phase 5's to own in
  detail).
- `scripts/validation/` tooling (schema/prompt/artifact validators) is a *second*,
  parallel validation surface that never runs under `pytest`/CI and exists purely as
  manual developer tooling — a reasonable design given it validates against
  data-dependent artifacts (`artifacts/`, gitignored), but it means "the tests pass"
  and "the validators pass" are two independently-triggered claims with no single
  command unifying them.
- Coverage tooling itself is broken (`coverage`/`coverage-detailed` targets, §4) —
  the one piece of automation that would make "which packages are undertested"
  visible at a glance does not run, which plausibly contributed to `resolvers/` and
  `sequencer/rendering/` reaching zero coverage unnoticed (phase 4's packages, noted
  here as a process observation).

## 6. Critical assessment (PROVISIONAL where noted)

- The interfaces/engineering layer as a whole reads as **built by someone who cared
  about developer ergonomics** (colored Makefile output, rich CLI narration,
  well-organized docs site, a genuinely consolidated validation-script package) **but
  the automation that would keep any of it honest over time was never finished**: no
  CI enforcement, two Makefile target families that silently rotted after a
  restructure, and a documentation guide whose entire "recommended" path was never
  real to begin with. This pattern — good artifacts, no verification loop — matches
  the project-wide narrative in discovery §5 (dead duplicates, unfinished migrations)
  more than it suggests neglect; the code online was reorganized (flat `tests/` →
  `tests/unit/`+`tests/integration/`, template consolidation in `scripts/build/`
  presumably becoming the current `scripts/*` demo files) and the glue (Makefile,
  docs) wasn't updated in lockstep.
- **No longer PROVISIONAL** (resolved at/after verification): this author originally
  held P7-F9 (CLI exposes only moving-heads; the display pipeline has zero CLI
  surface) as PROVISIONAL pending Stage 2's product-thesis verdict. **Stage 2 has
  since ruled DEFER on the display pipeline** — under that decision, a CLI that does
  not expose it is not a defect, it is the correct current shape. P7-F9 is
  downgraded to INFO accordingly (§10). What survives as a real, non-provisional
  defect is P7-F8/P7-M1 together: the hardcoded display graph *and* the hardcoded
  `fixture_count=4`/`min_pass_score=7.0` mean the CLI's one supported pipeline is
  correct only for the author's own display and fixture rig, not a general-purpose
  entry point — that critique holds regardless of the display pipeline's fate.
- The `make validate` mutate-then-test pattern is the correct local-dev ergonomic
  choice and should **not** be changed; the gap is narrower than this author
  originally assessed (§4 P7-F6 correction) — `lint`/`type-check`/`test` are already
  CI-safe individually, and the only missing piece is a `ruff format --check .`
  target/step.
- Scripts triage supports a clear minimal action: wire `validate_artifacts.py`/
  `validate_agent_artifacts.py` into either `Makefile` or a light CI smoke job (they
  are the most production-grade tools in `scripts/` and are currently invoked by
  nothing but a human remembering the README exists); write a `scripts/README.md`
  index; delete or relocate `utils/video_demo.py`; complete the `.PHONY` list and
  drop the stale `run-demo` entry (P7-M4).
- **Elevated by verification**: `docs/user-guide.md`'s configuration reference is
  not just missing a couple of stale claims (this author's original framing) — P7-M2
  establishes it as a *class* of silent no-ops (token budget, judge model,
  channel defaults, checkpoint/resume, logging level, curve claims), all
  undetectable from the doc itself. Any remediation of `docs/user-guide.md` should
  audit the full config-reference table against live readers, not patch the
  individually-known items.

## 7. Comparison with credible simpler/modern alternatives

- **CI**: GitHub Actions is already in use for the Jekyll workflow, so no new
  platform adoption is needed — a second workflow (`ci.yml`) triggered on
  pull_request/push, using `astral-sh/setup-uv` (official action) to provision the
  toolchain, is the natural, lowest-friction addition. No case for a heavier
  alternative (e.g., a separate CI vendor) given the project's small size and
  existing GitHub-native tooling.
- **Test mocking**: rather than adopting a new dependency (e.g., `respx` for HTTP-
  level interception of the OpenAI SDK), the pragmatic fix given the project's
  otherwise-lean dependency discipline (modernization.md notes deliberate avoidance
  of unused extras like `sqlite-vec`) is an in-repo fake: a `tests/support/
  llm_fake.py` module exposing a `FakeOpenAIProvider`/`scriptable_response()` fixture
  that constructs `LLMResponse`/`TokenUsage`/`ResponseMetadata` once, correctly, and
  is imported everywhere instead of re-built. This mirrors the pattern the codebase
  already uses well elsewhere (schema/taxonomy auto-injection, discovery §3) —
  single source of truth, not a new tool.
- **CLI framework**: `argparse` is adequate for the current one-subcommand surface;
  no case to introduce `Typer`/`Click` unless/until a `display` subcommand or
  cache/config introspection commands are added (Stage 2-dependent), at which point
  `Typer`'s subcommand ergonomics would reduce boilerplate meaningfully.
- **Coverage visibility**: rather than rewriting the missing `show_coverage_by_
  component.py` from scratch, `pytest-cov`'s existing `--cov-report=json` output
  (already produced by `test-cov`, `pyproject.toml:152`) could feed a much smaller
  script that reads `coverage.json` and groups by top-level `core/` subpackage —
  less to maintain than reconstructing whatever the original script did.

## 8. Relevant doc/context claims

| Claim | Source | Status |
|---|---|---|
| "The recommended way to run the full workflow is a single command: `scripts/build/build_pipeline.py`" | `docs/pipeline_guide.md:31-36` | **Half-false at verification**: true for 6 of 10 `scripts/build/` refs (never matched anything the directory contained); the other 4 are ordinary stale-after-deletion (`scripts/build/` was real, deleted 2026-02-24, `82aaf38`) (P7-F2) |
| "Option 2: .env file ... Edit .env and set OPENAI_API_KEY" as a working setup path | `docs/user-guide.md:75-77` | **Misleading, MEDIUM at verification** — `.env` is never loaded programmatically, but the sharper deception is `make env-check` reporting "✓" from a file grep rather than the process environment (P7-F1) |
| Full config reference table (`token_budget`, `judge_agent.model`, `channel_defaults.*`, `checkpoint`, `logging.level`, curve claims) | `docs/user-guide.md:121,146,148,152-154,157,245,296` | **Confirmed dead-config class at verification (P7-M2)** — every cited field fails silently; the table is not a reliable behavior description |
| "make validate — format + lint-fix + type-check + test — run before completion claims" | `AGENTS.md`, `context/engineering/conventions.md` | Accurate description of what the target does; CI-reuse gap is narrower than originally assessed — `lint`/`type-check`/`test` are already CI-safe individually, only `format --check` is missing (P7-F6) |
| Directory tree / scripts table | `docs/developer-guide.md:57,340-348` | Directory tree accurate; scripts table has 2 of 5 rows pointing at nonexistent files (P7-M3) |
| "planner → heuristic validator → LLM validator → judge loop" | `context/current-state.md` "Implemented" list | Stale (LLM validator role removed) — same claim as `multi-agent-planning.md`, already cited in discovery §4; downgraded to INFO at verification as a duplicate, not a new finding (P7-F16) |
| mypy strict typing standard | `context/engineering/conventions.md` | Contradicted by unused `pyrightconfig.json` asserting `"basic"` mode with no wiring to reconcile the two (confirmed clean at verification) |

## 9. Architecture worth preserving

- `scripts/validation/validate_artifacts.py` + `validate_agent_artifacts.py`: a real,
  documented consolidation of what used to be scattered per-pipeline wrappers — the
  README explicitly records the wrapper removal. This is the pattern the rest of
  `scripts/` should follow, not an outlier to fix.
- `Makefile`'s `clean`/`clean-cache`/`reset` family: correctly scoped, no
  destructive-by-accident risk, good separation between "dev caches" and "app
  runtime state."
- `AGENTS.md`'s router-not-encyclopedia design and explicit source-of-truth
  hierarchy: internally consistent, genuinely followable, and (per this review's own
  experience using it in §1 to scope the work) functions as intended.
- Directory-mirrored `tests/unit/`/`tests/integration/` structure: a real, useful
  organizing signal even where the marker layer built on top of it is inconsistent.
- `docs/` site structure and Jekyll wiring: functional, low-maintenance, no
  observed structural problems (only content-accuracy ones, above).

## 10. Candidate findings

_Verified 2026-08-13 (opus critic, non-author) — see `reviews/verification.md` "Phase
7". Severity column reflects the post-verification value; where verification
changed severity, the prior value and reason are noted inline. Verdict column is the
verifier's determination._

| ID | Title | Severity | Confidence | Evidence | Relationship | Disposition | Verifier verdict |
|---|---|---|---|---|---|---|---|
| P7-F1 | `docs/user-guide.md` "Option 2: .env file" documents a non-functional setup path | MEDIUM (was HIGH) | CONFIRMED | `docs/user-guide.md:73-77`; `grep -rn "load_dotenv\|dotenv"` → 0 hits in `packages/`, all `pyproject.toml`; CLI failure (`main.py:159-164`) is loud with remedy printed — the deceptive step is `make env-check` (`Makefile:320-343`) reporting "✓" from a file-content grep, not the process environment | New (elaborates inherited ".env never loaded" into a concrete DX break on the documented quick-start path) | FIX `env-check` to test the real environment, or delete the `.env` option from the docs — prefer over adding `python-dotenv` to the CLI | REVISED |
| P7-F2 | `docs/pipeline_guide.md`'s "recommended" Quick Start references `scripts/build/` | HIGH (unchanged) | CONFIRMED | `docs/pipeline_guide.md:31-36,884,894` (10 refs total, corrected from 9); `scripts/build/` was real, deleted 2026-02-24 (`82aaf38`) — true "never existed" only for 6/10 refs, the other 4 are stale-after-deletion | New | Remedy redirected: mark the guide as describing an ABANDON-candidate subsystem (corpus/FE, per Stage 2) pending its retire/restore decision — not a rewrite toward a currently-working entrypoint | REVISED |
| P7-F3 | `make build` targets nonexistent package paths (`packages/core`, `packages/cli`) | MEDIUM | CONFIRMED | `Makefile` `build` target; `ls packages/core packages/cli` → both absent; real paths `packages/twinklr/{core,cli}/`; also covers `make info` (same wrong paths) and the `.PHONY` gap (P7-M4) | Confirms/details inherited "4 broken Makefile target groups" | FIX | ACCEPTED (scope widened to include `make info` + P7-M4) |
| P7-F4 | `make test-unit`/`make test-integration` reference test files that don't exist | MEDIUM-HIGH | CONFIRMED | `Makefile` targets reference `tests/test_value_curves.py`, `tests/test_phase1_integration.py`, `tests/test_e2e_value_curves.py`, `tests/test_phase4_sequencer.py`; verifier checked full history (148 commits) — 3 of the 4 **never existed at any path, at any point** | Confirms/details inherited finding; causal story corrected — not drift from a later reorg, authored broken from day one (distinct remediation class, flagged to Stage 5/8) | FIX (repoint to `pytest tests/unit -v` / `pytest tests/integration -v`) | REVISED (causal correction) |
| P7-F5 | `make coverage`/`make coverage-detailed` call a script that does not exist | LOW-MEDIUM (was assessed as "never existed") | CONFIRMED | `Makefile` targets call `scripts/show_coverage_by_component.py`; the script **existed and was deleted 2026-01-30** (`c67bbdd`), restorable via `git show c67bbdd^:scripts/show_coverage_by_component.py` | Confirms/details inherited finding; ordinary deletion debt, not "never built" | FIX via restore, or REMOVE the targets | REVISED |
| P7-F6 | `make validate`'s mutate-then-test design is unsafe to reuse verbatim as a CI gate | MEDIUM (was HIGH) | CONFIRMED | `Makefile` `validate`: `ruff format .` → `ruff check . --fix` → `mypy .` → `pytest`; the git-clean checkpoint guard this finding calls for already exists in the file (`lint-fix-unsafe-apply`, `Makefile:79-87`), just not wired to `validate`; `make lint`/`type-check`/`test` are already non-mutating and CI-safe today | New; directly shapes the minimal-CI proposal (§7, §6) | FIX — the only missing piece is a `ruff format --check .` step; add it, keep `make validate` unchanged for local use | REVISED (severity + scope narrowed) |
| P7-F7 | `integration` pytest marker is under-applied relative to the `tests/integration/` directory | MEDIUM | CONFIRMED | `tests/integration/` has **16** files (corrected from 25), 14 unmarked; the 11 repo-wide `pytest.mark.integration` hits land in only **2** files; `pytest -m integration` selects just those 2 | New | FIX (apply marker repo-wide, e.g. via conftest path-based auto-marking, or drop marker-based selection in favor of directory-based) | REVISED (counts strengthened the finding) |
| P7-F8 | CLI hardcodes the physical display graph inside the presentation-layer entry point | MEDIUM-HIGH (was MEDIUM) | CONFIRMED | `packages/twinklr/cli/main.py:62-135` (`build_display_graph`); merged with P7-M1 (`fixture_count=4` at `:208`, `min_pass_score=7.0` at `:211`, both hardcoded past the point where the user's real fixture config is resolved at `:214-217`) | Confirms/details inherited "hardcoded display graph in CLI"; strengthened by P7-M1 into a single narrative: the shipped CLI is correct only for the author's own rig | FIX/MODERNIZE (move to config or a domain module regardless of Stage 2's product verdict) | REVISED (merged with P7-M1, severity raised) |
| P7-F9 | CLI exposes only the moving-heads pipeline; the display pipeline has zero CLI surface | INFO (was MEDIUM) | CONFIRMED | `packages/twinklr/cli/main.py:331-354` (`build_arg_parser`, single `run` subparser); cf. discovery §2 | New (engineering framing of a fact discovery established) | Not a defect under Stage 2's ruling (DEFER on the display pipeline) — no action | REVISED → downgraded to INFO (Stage 2 resolved the provisional dependency) |
| P7-F10 | `scripts/validation/test_prompt_validation.py`/`test_schema_validation.py` are pytest-named CLI harnesses pytest never collects | LOW | CONFIRMED | file headers (argparse `main()`, not pytest); `pyproject.toml:149` `testpaths = ["tests"]` excludes `scripts/` entirely | New | FIX (rename, e.g. `check_prompts.py`/`check_schemas.py`) | ACCEPTED (narrower harm than stated, disposition holds) |
| P7-F11 | `scripts/` has no top-level index/README; most non-`validation/` scripts are undiscoverable except by directory browse | LOW | CONFIRMED | `ls scripts/README.md` → absent; `scripts/validation/README.md` covers only 11 of 30 `.py` files | New | FIX (add `scripts/README.md`) | ACCEPTED |
| P7-F12 | `utils/video_demo.py` is a fully orphaned, product-unrelated prototype | LOW (was LOW-MEDIUM) | CONFIRMED | repo-wide `grep -rln "video_demo"` → only this review's own manifest references it; calls OpenAI video-generation API, inconsistent top-level `utils/` placement vs `scripts/` | New | REMOVE (or relocate + document if intentionally a kept spike) | REVISED — orphan confirmed, but no reachable harm found (nothing imports or invokes it), so severity down |
| P7-F13 | `pyrightconfig.json` asserts a weaker, unwired type-checking standard (`"basic"`) than the documented mypy-strict standard | LOW | CONFIRMED | `pyrightconfig.json` `typeCheckingMode: "basic"`; not referenced by any `Makefile` target or CI job; scope also narrower than a first read suggests — excludes `tests/`, `scripts/`, `utils/`, and sets `reportMissingImports: "none"` | Confirms/details inherited "third unwired type-check config" | FIX (wire to matching strictness or remove) | ACCEPTED (also narrower in scope than originally described) |
| P7-F14 | No `LICENSE` file; no `license` field in any of the three `pyproject.toml` files | MEDIUM | CONFIRMED | repo-wide `find -iname "LICENSE*"` → 0 matches; `grep -n license` on all 3 `pyproject.toml` → 0 matches | Confirms inherited finding (discovery §7.8) | **Duplicate of discovery §7.8 / Stage 2 — hand to Stage 8 for remediation, do not double-count as a phase-7-original finding** | ACCEPTED |
| P7-F15 | No centralized LLM-provider test fake; response-shape assumptions duplicated across ~57 files | MEDIUM (was MEDIUM-HIGH) | CONFIRMED | `grep -rl "MagicMock\|AsyncMock" tests/` → 57 files (confirmed clean); root `conftest.py` (159 lines) has zero agent/LLM fixtures | Confirms/details inherited "no centralized LLM fake (74-file ad-hoc mock)" pattern (this author's 57-file grep and the inherited 74-file count support the same finding via different mock idioms) | FIX (extract `tests/support/llm_fake.py`) — but **sequence after Stage 2's instrument-then-decide triage**, not before, since building shared test infra for code slated for deletion would be wasted effort | REVISED — harm inferred not demonstrated; sequencing condition added |
| P7-F16 | `current-state.md`'s "Implemented" list carries the same stale "LLM validator" claim as `multi-agent-planning.md` | INFO (was LOW) | CONFIRMED | `context/current-state.md` "Multi-agent choreography planning" bullet; `context/INDEX.md` lists it first under "Start here" | **Duplicate — already cited in discovery §4; not a new phase-7 finding, hand to discovery's remediation tracking** | FIX (same correction as the sibling doc, at both locations) — via discovery's tracking, not a separate phase-7 action item | REVISED → downgraded to INFO (duplicate) |
| P7-M1 | `cli/main.py:208` hardcodes `fixture_count=4` into the planner prompt path while resolving the real fixture config 3 lines later; `min_pass_score=7.0` (`:211`) similarly overrides the config field | MEDIUM-HIGH | CONFIRMED | `main.py:208,211,214-217`; flows to `stage.py:145` → `orchestrator.py:75` | Merged into P7-F8's narrative (§4, §10) | FIX (thread `fixture_count` from the resolved fixture config; read `success_threshold` from `job_config.agent` instead of the literal) | Verifier-added (adopted) |
| P7-M2 | `docs/user-guide.md`'s config reference documents a *class* of fields that fail silently: `token_budget` (:146), `judge_agent.model` (:148), `channel_defaults.{shutter,color,gobo}` (:152-154), `checkpoint`/false resume promise (:157,:296), `logging.level` (:121), shutter/color/gobo curve claims (:245) | HIGH | CONFIRMED | line cites above; each cross-checked against inherited/phase findings (token budget no-op, `AppConfig.logging` dead, `checkpoint_dir` never read) | Elevates several previously-individual dead-config findings (phases 1/7) into a confirmed class | FIX — audit the full config table against live readers as one pass, not per-field patches | Verifier-added (adopted) |
| P7-M3 | `docs/developer-guide.md:348` "Key Scripts" table has 2 of 5 rows pointing at nonexistent files (`build_pipeline.py`, `show_coverage_by_component.py`) | MEDIUM | CONFIRMED | `docs/developer-guide.md:338-348` | Same drift family as P7-F2/P7-F5 | FIX | Verifier-added (adopted) |
| P7-M4 | `.PHONY` (`Makefile:1`) covers 20 of the file's 39 targets, and one of those 20 (`run-demo`) is a stale entry with no matching target at all | LOW | CONFIRMED | `Makefile:1` vs. full target enumeration | Fold into P7-F3 | FIX (complete the list; drop `run-demo`) | Verifier-added (adopted) |

**Strengths logged as findings** (INFO severity, not defects; all confirmed clean at
verification): `scripts/validation/` consolidation pattern (§9); `AGENTS.md`
governance-doc consistency (§9); `Makefile` clean/reset target safety (§9); `tests/`
directory-mirrored structure (§9); CLI structural description, 57-file mock count,
LICENSE absence, pyright config, single Jekyll workflow, and the scripts triage table
were all independently confirmed accurate by the verifier without revision.

## 11. Unresolved questions & cross-phase dependencies

- **Stage 4 dependency**: whether `ruff check .`, `ruff format --check .`, `mypy .`,
  and `pytest tests/ -v` currently pass is unknown to this author by design — Stage 4
  owns that runtime truth. This phase's CI/quality-gate proposal (§7, P7-F6) is
  written to be correct regardless of current pass/fail status.
- **Phase 1 dependency**: the dual root/core ruff+mypy configuration (workspace
  packaging row, manifest.md) affects what "the type-check job passes" even means
  for a future CI pipeline — should be resolved before or alongside adding a
  `type-check` CI job, not after.
- **Phase 5 dependency**: the general "no round-trip/golden test category exists"
  architecture gap (§5) has its most concrete instance in the `.xsq` template-loss
  defect, which is phase 5's to detail; this phase only asserts the category is
  missing repo-wide.
- **Phase 4 dependency**: `resolvers/` and `sequencer/rendering/` zero coverage is
  phase 4's finding to own; this phase notes only the process contributor (broken
  coverage-visibility tooling, P7-F5).
- **Resolved (was Stage 2 dependency, PROVISIONAL)**: P7-F9's disposition depended on
  Stage 2's product-thesis verdict for the display pipeline. Stage 2 has since ruled
  **DEFER** — under that ruling, the CLI's current single-`run` shape is not a
  defect, and P7-F9 is downgraded to INFO (§10). No further action pending on this
  item; if Stage 2's DEFER is later revisited, P7-F9 should be reopened.
- **Partially resolved at verification**: this author's original open question
  ("does `scripts/build/`'s complete absence from git history reflect an
  uncommitted rename, a never-built plan, or squashed history?") had a wrong
  premise — `scripts/build/` was real and was deleted 2026-02-24 (`82aaf38`, P7-F2
  correction). The narrower open question that remains: 6 of the 10
  `docs/pipeline_guide.md` references name an entrypoint (`build_pipeline.py`) that
  does not match anything the deleted directory is known to have contained — whether
  that reflects a planned-but-never-merged consolidation script or a documentation
  aspiration that outran the implementation is still unresolved and not
  answerable from repository evidence alone.

## 12. Phase verification status

**VERIFIED** (2026-08-13, opus critic, non-author — "phase7-verifier"). Verdict: 3
ACCEPTED, 11 REVISED, 1 downgraded to INFO (P7-F9, resolved by Stage 2's DEFER
ruling), 4 verifier-added findings adopted (P7-M1–M4). All required corrections
from `reviews/verification.md` "Phase 7" applied above. P7-F14 (no LICENSE) and
P7-F16 (stale `current-state.md` claim) are confirmed duplicates of discovery §7.8
and discovery §4 respectively — retained here for phase-7 evidence completeness but
handed to Stage 8/discovery's own remediation tracking, not to be double-counted as
separate phase-7-original action items in cross-phase synthesis (Stage 5) or the
remediation roadmap (Stage 8).
