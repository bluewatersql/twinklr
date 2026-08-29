---
type: note
area: quality
created: 2026-08-29
updated: 2026-08-29
change: post-refactor-validation
phase: 0
---

# Phase 0 — Current-state functional inventory

_Deliverable for [plan.md](../plan.md) Phase 0. Read-only code review of the post-refactor
engine, synthesized from six parallel subsystem explorations (pipeline/CLI, provider,
emission, audio, feature-engineering, test-topology) plus direct inspection of an
`artifacts/` baseline. Every claim is file:line-cited to the subagent findings; spot-check
before relying on any single line number._

## Method

Six focused `explore` subagents each inventoried one subsystem and classified components as
**WORKING** (real deterministic code), **STUBBED** (real code, but only proven via mocked
LLM/provider — no live proof), or **PARTIAL** (incomplete / opt-in / deferred / needs an
external live process or owner data). Findings below are the merged result.

## TL;DR verdict

- The **deterministic spine is solid**: pipeline executor, the P3-T6 unified emission core,
  MH + display `.xsq` generation, trace-v2 sidecars, and golden render pins are all
  WORKING and CI-covered.
- The **entire creative path is LLM-gated and unproven live post-refactor.** A real
  `audio → plan → render → .xsq` show requires 3–4 live LLM stages for MH-only, more for
  display/show. None have a successful live run on record; CI replaces every one with a
  fixture/mock.
- **Two concrete code-level risks would break a naive live run** (details below): a
  model-capability-policy gap for `gpt-5.6-terra`/`luna`, and the Ollama loopback
  validator. Both are addressable before spending live calls.
- The `artifacts/` baselines expose **directly measurable parity metrics** (effect counts,
  value-curve channels, sections, segments, scores) — Phase 1 is well-grounded.

---

## 1. Runnable surface — CLI → pipeline map

Console entry `twinklr = twinklr.cli.main:main` (`packages/twinklr/cli/pyproject.toml:12`),
dispatch `cli/main.py:681`. Three pipeline definitions: `moving_heads`, `display`,
`combined_show`.

| Command | Pipeline | Classification | Note |
|---|---|---|---|
| `twinklr run` | `moving_heads` (`definitions/moving_heads.py:23`) | STUBBED | MH DAG renders offline; planning proven only with mocks |
| `twinklr inject` / `regenerate` | `moving_heads` + live xLights (`main.py:468`) | PARTIAL | LLM-stubbed planning + live xLights automation |
| `twinklr display` | `display` (`definitions/display.py:45`) | STUBBED | E2E fixtures profile/macro/groups/holistic |
| `twinklr show` | `combined_show` (`definitions/show.py:23`) | STUBBED | Shared prefix + MH + display → one `.xsq` |
| `twinklr curate-catalog` | recipe-builder (separate) | PARTIAL | `--dry-run` deterministic; live gen needs `OPENAI_API_KEY` |
| `twinklr catalog-coverage` | none | WORKING | pure layout/catalog math |
| `twinklr review-staged-recipes` | none (HITL) | WORKING | interactive admit/reject |
| `twinklr template-export` / `template-validate` | none | WORKING | registry ↔ JSON |
| `twinklr show-eval` | none (offline metrics) | WORKING | explicitly provider-free |
| `twinklr eval-report` / `--fseqcmp` | none | WORKING | checkpoint re-render / FSEQ byte compare |

Full detail: pipeline/CLI exploration `de754909`.

## 2. Per-stage classification (the DAG)

Shared prefix `definitions/common.py:18`. **Live-LLM stages are the validation risk.**

| Stage | File:line | Live LLM? | Class |
|---|---|---|---|
| `audio` | `agents/audio/stages/analysis.py:19` | No (optional demucs/whisperx) | WORKING |
| `profile` | `agents/audio/profile/stage.py:20` | **Yes** | STUBBED |
| `lyrics` (if `has_lyrics`) | `agents/audio/lyrics/stage.py:25` | **Yes** | STUBBED |
| `macro` | `agents/sequencer/macro_planner/stage.py:20` | **Yes** | STUBBED |
| `moving_heads` | `agents/sequencer/moving_heads/stage.py:25` | **Yes** | STUBBED |
| `render` | `.../moving_heads/rendering_stage.py:24` | No | WORKING |
| `groups` | `.../group_planner/stage.py:41` | **Yes** (FAN_OUT) | STUBBED |
| `aggregate` | `.../group_planner/stage.py:657` | No | WORKING |
| `holistic` | `.../holistic_stage.py:32` | **Yes** | STUBBED |
| `holistic_corrector` | `.../corrector_stage.py:34` | **Yes** (when ≠ APPROVE) | STUBBED |
| `asset_creation` | `agents/assets/stage.py:44` | **Yes** (LLM + image API) | PARTIAL (off by default) |
| `asset_resolution` | `pipeline/display_stages.py:36` | No | WORKING |
| `display_render` | `pipeline/display_stages.py:126` | No | WORKING |
| `show_render` | `pipeline/show_stages.py:25` | No | WORKING |

## 3. Minimal live-call set for a real show

MH-only `twinklr run`:

```
audio (local MIR) → profile (LLM) → [lyrics (LLM)?] → macro (LLM) → moving_heads (LLM) → render (deterministic .xsq)
```

= **4 LLM stages** (3 if instrumental). `display` adds `groups` + `holistic` (+ corrector /
assets when enabled); `show` needs `moving_heads` too before `show_render`.

---

## 4. Provider / transport layer  ⚠ contains two live-run blockers

Full detail: provider exploration `eaa986ed`. Legacy `api/llm/` is **gone** (P4-T4 collapsed
into `agents/providers/`). Retry ownership is provider-only (SDK retries disabled,
`openai.py:55`; `RetryPolicy` max 3, 4xx non-retryable).

**Both P3-T4 failure classes are fixed in code:**
- `$ref`-beside-sibling-keys → stripped in `schema_utils.py:166`, validated `:251`; MacroPlan
  regression `tests/unit/sequencer/planning/test_macro_contract.py:461`.
- unsupported `temperature` → `capabilities.py:19` omits it **for `gpt-5.6-sol` only**.
  Invalid-schema 400s fail loud, not soft-fallback (`openai.py:620`).

### ⚠ FINDING A — capability-policy gap (Phase 3 blocker candidate)

`capabilities.py:18` only knows `gpt-5.6-sol` (temp off), `gpt-4.1`/`gpt-4o` (temp on).
**Everything else defaults to "send temperature."** Shipped role defaults
`gpt-5.6-terra` (judge / asset enricher, `config/models.py:122,146`) and `gpt-5.6-luna`
(vision judge, `config/models.py:202`) are **not** listed. The MH macro path uses `sol`
(safe), but the full orchestrator also calls the **judge (`terra`)** — if `terra`/`luna`
reject `temperature` like `sol`, a live show repeats P3-T4 attempt-2's HTTP 400.
**Action:** before Phase 3, add `terra`/`luna` to the capability map (or set
`temperature=None` in their role configs) and lock with a unit test. This is a small,
offline, TDD-able fix and belongs in Phase 2/early Phase 3.

### ⚠ FINDING B — Ollama cloud path (reconciles owner note with code)

Owner note (2026-08-29): use an Ollama **cloud-hosted** model to expedite. The code's
`AppConfig.validate_local_provider_endpoint` (`config/models.py:545`) rejects non-loopback
Ollama base URLs, and there is no cloud API-key path — so pointing directly at
`https://ollama.com` is blocked (`test_ollama.py:124`).
**However**, Ollama's cloud models (`kimi-k3:cloud`, `deepseek-v4-pro:cloud`,
`glm-5.2:cloud` per the handoff's `ollama list`) are served **through the local ollama
daemon** at `127.0.0.1:11434`, which proxies to Ollama cloud. So the expedited path is:
run the local daemon, set `TWINKLR_OLLAMA_MODEL=<name>:cloud` with the default loopback
`TWINKLR_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1` — this satisfies the loopback validator
**and** uses a cloud-hosted model, no multi-GB download, no code change. Confirm the daemon
is signed in to Ollama cloud. (If instead a direct remote endpoint is ever required, that
needs a product change: relax the validator + add auth.)

Env gates for the smoke: `TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1`, `TWINKLR_OLLAMA_MODEL`,
optional `TWINKLR_OLLAMA_BASE_URL` (`tests/local_only/test_ollama_structured_outputs.py:21`).

---

## 5. Emission / `.xsq` — where MH "technical detail" lives

Full detail: emission exploration `0d0c05a9`. P3-T6 unified seam is WORKING: MH
(`XsqAdapter`) and display (`XSQWriter`) both queue into `EmissionSession`
(`emission.py:94`), which owns EffectDB/palette registries, 20 ms grid quantization,
file/live layer translation, and trace-v2 rows. Then `XSQExporter.export`
(`exporter.py:38`) writes XML and `write_xsq_trace_sidecar` (`trace.py:62`) writes
`{xsq}.trace.json` (schema `twinklr-xsq-trace.v2`).

**Key insight for parity:** MH richness is **not** effect-type variety (effect is always
`"DMX"`). It lives in the **EffectDB DMX settings strings** — sliders + value curves
(`DmxSettingsBuilder.build_settings_string:43`) — and in BASE/TRANSITION layers, template
variety, grouping, and section coverage. Coordination *modes* are **not serialized** into
the `.xsq`/trace (only their timing windows), so mode variety must be read from the plan
artifact, not the `.xsq`.

One orphan: `EffectDBRegistry` (`effectdb_registry.py:12`) has no production callers
(PARTIAL/dead). One stale comment: `writer.py:109` still says "unification remains P3-T6"
though both writers already share the seam.

## 6. Audio pipeline

Full detail: audio exploration `bfd95017`. A real **audio → SongBundle** runs today with
default deps (librosa DSP: rhythm, energy, structure, harmonic, spectral, tension). Defaults
on: embedded metadata, embedded lyrics, phonemes (if timed words). Defaults off / deferred:
WhisperX (`enable_whisperx=False` + TorchCodec runtime deferred under FFmpeg 9 — no in-code
`torchcodec` import, deferral is policy/docs), Demucs stems (opt-in, graceful full-mix
fallback), AcoustID/MusicBrainz, online lyrics, `beat_this`/`allinone` MIR.
`AudioProfile`/`Lyrics` **agents** always need a live LLM. `make test-audio` exercises the
analyzer only, not the profile LLM. Real songs live in `data/music/` (~60 tracks);
content/model-aware cache in `data/audio_cache`.

## 7. Feature-engineering / catalog

Full detail: FE exploration `d3ccd908`. **Choreography planning works end-to-end from the
tracked seed catalog alone** — FE propensity/style is optional enrichment
(`display_wiring.py:82` continues if `fe_bundle is None`; planner hooks degrade gracefully
`group_planner/stage.py:314`). Production loads `catalog/templates/` (tracked); `data/templates/`
is a gitignored overlay. **Seed size: 6 display recipes + 3 MH JSON docs; MH runtime uses
~37 Python builtins.** All P2K-T2 owner-run tooling is WORKING but its empirical exits need a
private corpus that is absent (NEEDS-owner-data). Caveat: the seed is *thin* vs a former
~37-recipe display catalog, so creative richness is structurally limited without mined data
— relevant when judging a new run's sophistication.

## 8. Test topology — what green `make validate` proves

Full detail: test exploration `ad55b42a`. Layers: `tests/unit/` ~470 files/~4,429 tests;
`tests/integration/` 22 files/~120 (LLM/audio stubbed in the "E2E" ones); `tests/golden/`
14 files + 78 `*.settings.txt` + 2 `.xsq` (real render, no LLM); `tests/local_only/` 4 files
(runtime-skipped without env). CI runs `pytest -m "not local_only" --no-cov`
(`.github/workflows/ci.yml:47`); **no `fail_under` coverage gate exists in repo config.**

**`make validate` proves:** format/lint/types clean; big unit+integration suite; **offline
render goldens** (DMX settings + `.xsq` round-trip + combined-show golden); stubbed pipeline
wiring.

**It does NOT prove:** live LLM structured-output compatibility, live xLights import, real
audio/MIR, an LLM-planned end-to-end show, or any regression vs `artifacts/`.

**All four "E2E/integration" files confirmed stubbed:** `test_combined_show_pipeline.py:219`
and `test_display_pipeline_e2e.py:131` replace profile/macro/groups/etc. with `_FixtureStage`
and `patch(...AudioAnalyzer...)`; `test_fe_unified_pipeline_e2e.py:754` uses a mock session;
`test_recipe_end_to_end.py` is pure deterministic FE (no LLM at all).

**Fixed in this phase (P0-5):** `make test-unit`/`test-integration` pointed at four
non-existent top-level files (`tests/test_value_curves.py`, `test_phase1_integration.py`,
`test_e2e_value_curves.py`, `test_phase4_sequencer.py`); retargeted to `tests/unit/` and
`tests/integration/`.

---

## 9. Baseline `artifacts/` inventory + concrete parity metrics

Pre-refactoring generated shows (gitignored, Feb–Mar 2026):

| Dir | Type | Key files |
|---|---|---|
| `11_need_a_favor` | MH | `…_twinklr_mh.xsq` (732 KB), `pipeline_metadata.json`, `choreography_plan.json`, `macro_sections.json`, `audio_profile.json` |
| `titanium…` | MH | `…_twinklr_mh.xsq` (453 KB) + same JSON set |
| `02_rudolph…` | Display | `…_display.xsq` + `.trace.json`, `group_plan_set.json`, `holistic_evaluation.json` |
| `need_a_favor`, `org`, `shared` | mixed/support | — |

**Measured baseline metrics for `11_need_a_favor` (the parity yardstick):** from the `.xsq` —
932 placed effects, 622 value-curve DMX channels, `sequenceTiming 20 ms`, version **2025.13**;
from `pipeline_metadata.json` — 4 fixtures, 37 templates available, **13 sections**, **262
render segments**, macro score **8.3** (31,326 tokens, 1 iter), MH score **7.7** (44,089
tokens, 2 iters).

This confirms the Phase 1 sophistication metrics (§P1-2a) are directly extractable from the
`.xsq` + `pipeline_metadata.json`, and gives concrete numbers a new run must be "on par"
with. **Known intended divergence:** current code stamps `.xsq` version **2026.15**
(`fresh.py`), vs 2025.13 in the baseline — exclude the version stamp from parity.

---

## 10. Findings that adjust the plan

1. **Add a Phase-2/early-3 capability-policy fix** for `gpt-5.6-terra`/`luna` (Finding A).
   Without it, a live `display`/`show` run risks the same HTTP 400 that killed P3-T4.
2. **Ollama cloud is feasible with no code change** via the local daemon + `:cloud` model
   tag (Finding B); resolves plan open-question 5 mechanically.
3. **Parity harness should read `pipeline_metadata.json` + parsed `.xsq`**, not intermediate
   plan JSON — matches the owner's "final-output parity" bar and is already populated with
   scores/segments/sections.
4. **Seed catalog is thin (6 display recipes)** — a fresh run's display richness is bounded
   by catalog size, not just the engine; weight MH `.xsq` DMX/value-curve/segment metrics
   most heavily for parity, and note display-recipe breadth as a separate owner-data lever.
5. **No coverage gate exists** despite conventions citing ≥65%; consider adding `fail_under`
   as an optional hardening item (out of scope unless owner wants it).
6. **Makefile targets fixed** (done); **two stale in-code comments** noted (`writer.py:109`,
   display "deferred" note `main.py:139`) — cosmetic, deferred.

## 11. Open questions — status after Phase 0

- Q1 live model + budget — **still owner-input needed.** Recommend macro/plan on `gpt-5.6-sol`
  (temp-safe); resolve Finding A before enabling judge/vision roles live. Need a USD cap.
- Q2 baseline songs — **recommend `11_need_a_favor` (MH) + `02_rudolph…` (display)**; confirm
  their source audio is still in `data/music/` (need_a_favor mp3 referenced; rudolph TBD).
- Q3 intended-divergence sign-off — owner; version stamp is the first known example.
- Q4 tracked baseline location/size — a few hundred KB; **recommend committing the chosen
  `.xsq` + `pipeline_metadata.json` under `tests/regression/baselines/`.**
- Q5 Ollama — **resolved** (Finding B).
- Q6 branch/worktree — recommend a branch off `main` (currently synced at `54948c0`).

## 12. Phase 0 exit

Inventory complete and evidence-backed. Phase 1–4 task lists in [plan.md](../plan.md) hold,
with the three additions above (capability fix, metadata-based parity harness, seed-catalog
caveat). Fresh `make validate` evidence appended below once the run completes.

### Fresh gate evidence (attempted 2026-08-29)

`make validate` was **not runnable in this session's environment**, for two reasons — both
environmental, neither a code defect:

1. **Dirty-tree guard (by design).** `make validate` (`Makefile:156`) refuses to run against
   uncommitted changes because it mutates the tree (format/lint-fix). This Phase 0 work left
   the tree dirty (3 new docs + the Makefile target retarget), and committing is not
   authorized without owner go-ahead.
2. **Offline sandbox.** The CI-equivalent non-mutating checks (`uv run --no-sync ruff
   check`, `ruff format --check`, `pytest -m "not local_only"`) could not run: `uv run`
   requires a network resync (pypi unreachable — `Connection refused`), and the local
   `.venv` is bare (python 3.13.13 only; no `pytest`/`ruff`/`mypy`, `twinklr` not
   importable). Tooling lives in uv's managed environment which needs network to populate.

**Scope-of-change safety:** the Phase 0 diff is documentation (`spec.md`, `plan.md`, this
note) plus a one-line-per-target Makefile fix (`test-unit`/`test-integration` → `tests/unit/`
/ `tests/integration/`). No Python source, config, or test file changed, so the last accepted
gate result stands: **main `03b75e9` — 5,637 passed / 39 skipped, 89% coverage, Ruff clean,
mypy clean across 721 files** (`context/current-state.md`); closeout `54948c0` is docs-only.

**Action for the next session (networked env):** commit these docs, then run `make validate`
from a clean tree to capture a fresh full-gate result before Phase 1 begins.
