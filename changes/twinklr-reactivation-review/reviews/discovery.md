# Discovery — Repository Reconstruction

_Stage 1 synthesis. Baseline `aa8d325bca6e83d9be0853e5842759bc7bcb8d1e` (main, clean).
Produced 2026-08-13 from seven parallel read-only surveys (workers 1–7) plus targeted
follow-ups, then corrected under independent critic challenge (see plan.md gate
record). Claims cite worker/critic findings; absence claims ("no X exists") and
intent-attributions are inference from exhaustive search, not direct observation —
where load-bearing they were independently re-verified by a non-author (critic spot
checks, §4–5). No commands that mutate state were run; no source was modified._

## 1. Repository and package topology

uv workspace, three members (root `pyproject.toml` [tool.uv.workspace]):

- **twinklr** (root, v0.2.0) — aggregator; builds no code (`packages = []`). Python
  `>=3.12,<3.13`.
- **twinklr-core** (`packages/twinklr/core/`, pyproject v0.1.0 but `__init__.py`
  `__version__="0.2.0"`) — all product logic (~20 subsystem packages). Heavy deps:
  librosa/numpy/scipy/numba core; optional extras `ml` (whisperx + torch==2.4.0 pinned,
  ~2 GB), `fe` (sqlite-vec — declared but unused, see §6), `anthropic`, `normalization`
  (sentence-transformers), `dev`.
- **twinklr-cli** (`packages/twinklr/cli/`, v0.1.0, `requires-python>=3.10` —
  inconsistent with the workspace's 3.12 pin) — one console script: `twinklr`.

Namespace packaging via `pkgutil.extend_path`. Version declared in three places with two
values (0.2.0 / 0.1.0 / 0.2.0) and no sync mechanism. Ruff/mypy configured twice (root
richly, core minimally) with untested resolution ambiguity; `pyrightconfig.json` is a
third, unwired type-checking config.

Knowledge trees (`context/`, `changes/`, `memories/`, `prompts/`, `docs/`) are tracked;
`data/`, `artifacts/`, local configs, `.env`, and agent state are gitignored. `docs/` is
a Jekyll GitHub Pages site — the only CI workflow in the repository builds it.
**No CI executes tests, lint, type-check, or `make validate` — all quality gates are
local-manual only** (worker-1).

## 2. Entry points and execution paths

**One production entry point**: `twinklr run` (`cli/main.py`) → `build_moving_heads_pipeline`
→ `PipelineExecutor` (async DAG, waves, FAN_OUT semaphore) →
`audio → profile + lyrics → macro → moving_heads → render` → `.xsq`.

Requires `OPENAI_API_KEY` env var (hard-coded check; Anthropic provider exists but is
unreachable from the CLI). The display choreography graph is **hardcoded** in
`cli/main.py:62-135` (3 groups; comment admits layout parsing is future work).

**Second, complete-but-unreachable pipeline**: `build_display_pipeline`
(`pipeline/definitions/display.py`) — common → GroupPlanner FAN_OUT per section →
aggregate → holistic judge → holistic corrector → display render, with asset
creation/resolution stages gated behind `enable_assets: bool = False`
(`display.py:56` — the default pipeline shape excludes them). Callers: one demo script
(`scripts/demo_sequencer_pipeline.py:555`) and unit tests only (workers 2, 6; verified
by critic). This is the only path that consumes feature-engineering
artifacts (`fe_bundle` → `SectionPlanningContext` → planner prompt), and only when a
locally built `feature_store_manifest.json` exists.

**Consequence (load-bearing for Stage 2):** of the three claimed product scopes
(`context/product/overview.md`: moving heads, display sequencer, feature engineering),
only moving-heads is connected end-to-end. Display sequencing and the entire corpus
subsystem are built, tested in isolation, and disconnected from the shipped entry point.
The docs' "virtuous loop" narrative (`docs/feature_engineering/07`) describes wiring
that exists only for the unreachable pipeline (worker-6).

Other executable surfaces: `scripts/` (8 demo scripts, analysis, an offline
`.xsq` validation tool under `scripts/validation/`), `make test-audio*` (the only
Makefile targets that call a script), `eval-report` (post-hoc render-quality evaluation,
`reporting/evaluation/`), `recipe_builder/` (offline human-in-the-loop recipe curation).

## 3. Dependency and data-flow map (as implemented)

```
audio file → AudioAnalyzer (librosa DSP, deterministic core)
           + metadata (embedded tags → fpcalc/AcoustID → MusicBrainz, all optional/degrading)
           + lyrics (embedded → LRCLib → Genius → WhisperX align → transcribe; first hit wins)
           + phonemes/visemes (g2p_en, deterministic)
           → SongBundle (schema v3.0; features dict is UNTYPED legacy v2.3 shape)
→ AudioProfile agent (LLM, oneshot) + Lyrics agent (LLM, oneshot)
→ MacroPlanner (LLM, iterative: planner → heuristic validation+repair → judge, ≤3 iter)
→ MovingHeadPlanner (same loop, judge = gpt-5-mini)
→ RenderingPipeline: template registry (38 Python-code builtins) → compile
  (chase order, phase offsets, curves in [0,1]) → DMX conversion (clamped [0,255])
  → XsqAdapter (group-first effects) → XSequence → XSQExporter → .xsq
```

Cross-cutting mechanics established by evidence:

- **LLM boundary**: all agents run through one `AsyncAgentRunner` + `AgentSpec`;
  prompts are Jinja2 packs (SandboxedEnvironment, StrictUndefined); **response schemas
  and ~25 categorical-vocabulary enums are auto-injected from Pydantic/source enums —
  zero hand-authored schema duplicates found** (worker-4). OpenAI Responses API in
  plain `json_object` mode (not native structured outputs); conformance enforced by a
  client-side schema-repair loop (≤5 retries). Judge `status` is force-reconciled to
  score thresholds by a Pydantic validator — the LLM cannot emit inconsistent verdicts.
- **Iteration loop**: the documented "LLM validator" role no longer exists — the live
  loop is planner → heuristic validation with **five deterministic auto-repair passes**
  (fuzzy ID matching, bounds snapping, conflict dropping, spacing sanitization) → judge.
  `context/architecture/multi-agent-planning.md` still documents the removed role.
- **Caching**: content-addressed FSCache with atomic two-file commit; keys include
  `session_id` — and the CLI generates a **random UUID per invocation** (OBSERVED:
  `cli/main.py:229` → `session.py:69`), so cross-run restartability (a documented
  execution property) is defeated at the only production entry point. Nuance (critic
  B4): the deterministic-ID capability is deliberate and documented
  (`session.py:59-60`, "Pass a deterministic ID for cache reuse across runs") — the
  CLI simply never uses it. Defect shape: small integration fix, not architecture.
- **Pipeline semantics**: fail-fast is real (executor aborts on first failed stage);
  `JobConfig.checkpoint`/`PipelineContext.checkpoint_dir` are declared but never read.
- **Feature store**: SQLite, DDL-as-data, `INSERT OR REPLACE` per-call commits, WAL,
  version-string gate with **no migration path**; app-level `threading.Lock`
  serialization; no cross-process handling. All embedding/similarity math is brute-force
  NumPy; sqlite-vec is declared as an extra but never imported (worker-6).
- **xLights I/O**: ms-internal / seconds-at-boundary; parser is allow-list with
  `extra="ignore"` everywhere and the exporter regenerates XML from the model, so
  **unmodeled xLights fields do not survive parse→export**; no version-compat logic
  (two pipelines stamp different hardcoded default versions); output validation exists
  only as a separate post-hoc script (workers 5).

## 4. Claimed positions vs observed reality (inputs to Stage 2)

| Claim (source) | Classification | Observed status |
|---|---|---|
| Product = moving heads + display + FE feeding generation (`context/product/overview.md`) | INHERITED_DESIGN_CHOICE | Only moving-heads path is connected; display + FE are unreachable from CLI |
| "LLM plans intent; renderer implements precision" (`memories/decisions/…`) | INHERITED_DESIGN_CHOICE (candidate strength) | Faithfully implemented: categorical enums, template-bounded action space, renderer-owned numerics; schema auto-injection verified airtight |
| Planner → heuristic validator → **LLM validator** → judge (`context/architecture/multi-agent-planning.md`; also `context/current-state.md:23`) | Stale documentation (two context docs) | LLM validator removed in code; docs not updated |
| Fail-fast + cache restartability (`context/architecture/pipeline.md`) | Half-true | Fail-fast: yes. Restartability: defeated by per-run random session_id at the CLI |
| Native `.xsq` round-trip fidelity (product goal) | **CONFIRMED DEFECT** (critic B3) | The CLI's mandatory input is a template `.xsq` (`cli/main.py:140` → `xsq_export.py:53-56` parses it); parser models use `extra="ignore"` at nine sites and the exporter regenerates XML from scratch (`exporter.py:78-149`) — **unmodeled template content is silently dropped on the only shipped path**, with zero round-trip tests and no version handling |
| Python 3.12-only (`memories/constraints/python-3.12-only.md`) | HARD_EXTERNAL-ish (ML dep chain) | Confirmed in packaging; cli package contradicts with `>=3.10` |
| Four known test failures (`memories/learnings/known-test-failures.md`) | UNVALIDATED_ASSUMPTION (self-flagged) | 6 months stale, provenance-suspect; must re-verify in Stage 4 |
| Token budget configurable per job (`JobConfig.agent.token_budget`) | Built but never fed (critic B2) | Confirmed no-op, but not dead code: the mechanism is fully built and correctly wired orchestrator→`IterationConfig`→live enforcement (`controller.py:452-453`); no stage ever passes the JobConfig value in, and `TokenBudgetManager` is never instantiated. Remediation = feed the input, not delete |

## 5. History signals requiring deeper review

**Confirmed dead in production** (definition + grep of all importers/constructors):
`pipeline/stages.py` (legacy reference stages; carries the dangling
`changes/archive/group_planner_v3_failed/` comment — archive confirmed absent, already
documented in `context/current-state.md`); `agents/state_machine.py::OrchestrationStateMachine`
(exercised only by its own unit tests); `agents/token_budget_manager.py::TokenBudgetManager`;
`audio/lyrics/diarization*.py`; `audio/genre/classifier.py`; `audio/context/{hints,unified_map}.py`
(also read a pre-refactor features schema); `curves/simplification.py::simplify_rdp`;
`structure/models.py::Section` (validators never run — production sections are plain dicts);
`rhythm/beats.py::detect_tempo_changes` (dead duplicate of `rhythm/tempo.py`);
three verbatim-duplicate methods in `structure/sections.py::SongSectionDetector`;
`SectioningPreset.context_weights` (validated, never read).

**Confirmed broken**: `make build`, `make test-unit`, `make test-integration`,
`make coverage*` (stale pre-restructure paths / missing script); two of six checks in
`audio/validation/validator.py` — schema drift means the key-confidence check emits a
spurious "Low key detection confidence: 0.00" warning on **every** production run and
the downbeat check silently never fires; the whole validation result is then logged at
DEBUG and discarded (`analyzer.py:696-698`), so none of the module's checks has
user-visible effect (critic B5); token budget end-to-end.

**Confirmed production defect — `.xsq` template content loss** (promoted from
hypothesis by critic B3): the only shipped path requires a template `.xsq`, parses it
with `extra="ignore"` models, and regenerates the output XML from scratch — any
xLights content Twinklr does not model is silently dropped from the user's own
template. No test guards this.

**Confirmed bug pattern**: per-call token-usage deltas are computed by snapshotting a
shared provider counter across `await` boundaries while FAN_OUT runs up to 4 concurrent
sections against one provider instance — per-stage token accounting is unreliable under
concurrency (workers 4+2, confirmed at `async_runner.py` + `executor.py` + `session.py`).

**In-progress migrations still straddling**: `DisplayGraph` → `ChoreographyGraph`
(both exported, labeled legacy in code); `transitions.py` vs `transitions_v2/`;
`effect_function_v1.json` vs `v2.json`; `EffectPlacement` "migration compatibility"
dataclass permanent on the hot path; dual legacy/categorical curve-registry APIs;
dual TimeRef support in group-planner timing.

**Duplication debt**: two OpenAI clients with independent retry/timeout policies inside
one provider; two `configure_logging` implementations (CLI uses the hardcoded one —
`AppConfig.logging` is dead); duplicated fixture-config path resolution; duplicated
conversation-windowing logic across both providers; thrice-duplicated `HAS_SCIPY`
fallback pattern.

**Positive signals worth preserving** (candidate KEEP findings): schema/taxonomy
auto-injection design; categorical vocabulary contract; judge score/status enforcement;
deterministic auto-repair before LLM feedback; template registry deep-copy defaults;
atomic cache commit; `defusedxml`/`SecretStr`/sandboxed-Jinja hygiene; a 404-test-file
tree broadly mirroring the package layout; low TODO density (4 repo-wide); the
standalone `eval-report` quality-evidence tool. **Coverage caveat (critic A1/A2,
replaces an earlier incorrect claim)**: directory parity overstates health —
`core/formats/xlights/` (the entire output boundary: parser, exporter, models) has
exactly one direct test file (`test_timeline.py`); the `.xsq` parser and exporter have
no dedicated tests; and `core/sequencer/rendering/` (`categorical_resolver.py`) is a
second zero-coverage package alongside `core/resolvers/`.

## 6. Environment and runtime blockers (for Stage 4)

- Host Python is 3.14.6; project requires 3.12 (`uv.lock` pins `==3.12.*`). uv should
  provision the interpreter, but this is unverified — classify ENVIRONMENTAL if it bites.
- Any live pipeline run needs `OPENAI_API_KEY` (out of scope in local-safe mode);
  `.env` is never loaded programmatically — shell-side only.
- `ml` extras are a ~2 GB install; WhisperX/torch pins are 2024-era.
- `fe` extra declares sqlite-vec, which nothing imports — install-surface noise.
- `make validate` mutates source (format + lint-fix); safe-worktree protocol required.
- Display-pipeline and FE runtime checks additionally require locally generated
  `data/templates/` + `data/features/` content that is not in the repository —
  representative execution may be impossible without fabricating corpus data (flag as
  BLOCKED evidence class if so).
- **Model-ID resolution** (critic E1): `gpt-5.2` is hardcoded at 29 sites, plus
  `gpt-5-mini`, `gpt-4.1`, `gpt-4o-mini`, `gpt-image-1.5` (defaults at
  `config/models.py:22,109`). After ~5 months dormant, whether these IDs still resolve
  against the Responses API gates every Stage 4 runtime claim — verify before Stage 4.
- **Image-generation spend** (critic E3): `agents/assets/image_client.py:180` calls
  `images.generate()` (`gpt-image-1.5` default). Any display-path run with
  `enable_assets=True` incurs image-generation cost — inside the "no paid calls without
  authorization" boundary.
- **Secondary credentials** (critic E4): `.env.example` also declares
  `GENIUS_ACCESS_TOKEN`, `ACOUSTID_API_KEY`, `HF_TOKEN`; whether degradation paths
  degrade cleanly without them is unverified and shapes what "representative execution"
  can mean offline.

## 7. Major unknowns

1. Current test-suite status (pass/fail counts, the four reported failures) — Stage 4.
2. Whether generated `.xsq` files are accepted by real xLights (no e2e evidence in
   repo). Concrete testable form (critic E5): the two conflicting hardcoded version
   stamps — `"2024.01"` (`pipeline/display_stages.py:243`) vs `"2024.10"`
   (`moving_heads/xsq_export.py:67`).
3. Whether the display pipeline works end-to-end at all (never CLI-wired; demo-only).
4. How many `EffectRecipe`s exist in practice and their quality (data is gitignored).
5. Ruff/mypy config resolution between root and core (affects what "passing gates" means).
6. Actual runtime cost/latency/token profile of a full moving-heads run (no telemetry
   in repo) — a product-viability question, not just an ops metric (critic D2).
7. Why development velocity collapsed: against `packages/`, 67 commits in 2026-02 → 9
   in 2026-03 → 1 in 2026-04 → 0 since (critic-refined; no repo evidence of cause; no
   unmerged branches).
8. **Licensing/IP posture** (critic E2): no `LICENSE` file and no `license` field in
   any `pyproject.toml`, for software that reads/writes a third-party application's
   format atop a GPL-adjacent audio stack (librosa ISC, but ffmpeg/codec chain varies).
9. Whether the hardcoded model IDs still resolve (see §6) — pre-Stage-4 gate.

## 8. Early hypotheses — UNCONFIRMED, to be tested in Stages 2–7

_Revised per critic D3: H3 was promoted to a confirmed defect (§5) and is no longer a
hypothesis; H5 (a predicted final classification) was cut — it would anchor downstream
reviewers on a verdict they are meant to derive; H2 is restated as an open question._

- H1: The product's defensible core is the moving-heads path plus the audio-analysis
  layer; display + corpus subsystems are accumulated experiments that never reached the
  product boundary (supported by §2 wiring evidence; needs Stage 2 value analysis).
- Q2 (open question, replaces former H2): **Is the LLM load-bearing at all?** The
  action space is fully bounded by categorical enums and a fixed template registry,
  with the renderer owning every numeric (§3). Would a rules/heuristics engine over the
  same vocabulary — driven by the deterministic audio features — produce comparable
  choreography at zero token cost, latency, and nondeterminism? Conversely, what
  observable quality does the LLM add? This is the central system-approach question
  for Stage 2; neither direction is presumed.
- Q3 (residual of promoted H3): given template-content loss is confirmed, the open
  boundary question is what the product's round-trip contract *should* be — full
  fidelity (requires a preserving parser/writer design) vs. generate-fresh-only
  (requires documenting the limitation and validating version stamps against real
  xLights).
- H4: The judge/iteration loop's value is unproven in-repo (no evaluation artifacts
  comparing 1-shot vs iterated output); its cost/complexity may not be justified
  (needs Stage 5/6 analysis; eval-report tooling exists but no stored results).
- Stage 2 must additionally seed the product questions discovery under-weighted
  (critic D2): who the user is; whether "replaces dozens of hours of manual xLights
  programming" is evidenced or assumed; competitive alternatives (xLights' own
  generation tooling, sequence marketplaces); and per-song generation cost as a
  viability parameter.

## 9. Phase decomposition — revised at the gate (critic C2/C3)

The original six-phase plan put ~240 modules, two parallel render implementations, and
the entire `.xsq` I/O boundary in one phase. Revised to seven phases; reviewer AND
separate verifier ownership per phase is now recorded in `plan.md` (critic C1):

1. `foundation-and-orchestration` — pipeline framework/definitions, config, caching,
   session, api/http+audio clients, core io/logging/parsers/utils, packaging.
2. `deterministic-audio-analysis` — core/audio (all subpackages).
3. `llm-agents-and-planning` — agents runner/prompts/providers, iteration/judging,
   planners, **agents/assets (explicitly owned here; phase 5 must not assume it)**,
   sequencer/planning models (planner-facing contract).
4. `moving-heads-rendering` — sequencer/moving_heads, curves, resolvers,
   sequencer/rendering (categorical_resolver), timing, vocabulary.
5. `display-rendering-and-xlights-io` — sequencer/display, templates/group, theming,
   sequencer/models, formats/xlights (parser/exporter/layout).
6. `corpus-intelligence` — feature_engineering, feature_store, recipe_builder,
   profiling, reporting/evaluation.
7. `interfaces-and-engineering` — CLI, Makefile/CI, scripts/utils, test architecture,
   docs site, knowledge trees.

Cross-phase seam ownership (critic C3): the FAN_OUT token-accounting race is owned by
phase 1 (executor/session side) with phase 3 consulted (async_runner side); the
`vocabulary` contract is owned by phase 4 with phase 3 as consumer-reviewer;
`agents/assets` is owned by phase 3 as stated above.
