# Review Manifest

_Living disposition table for all first-party areas. Baseline `aa8d325`. Updated
2026-08-13 (end of Stage 1). Statuses: NOT_STARTED | IN_PROGRESS | REVIEWED | VERIFIED |
BLOCKED | N/A. "Reviewer" = discovery worker (Stage 1) / assigned phase (Stage 3).
Evidence = worker report location (this change's session transcripts, synthesized into
discovery.md §-references)._

| Area | First-party paths/components | Reviewer | Status | Evidence | Findings (candidate) | Verification | Notes |
|---|---|---|---|---|---|---|---|
| Workspace packaging | root/core/cli `pyproject.toml`, `uv.lock`, namespace init | worker-1 → phase 1 | REVIEWED | discovery §1, critic A7 | version declared in 5 places, 2 values; cli `>=3.10` inconsistency; dup ruff/mypy config; unused sqlite-vec extra | pending Stage 7 | |
| Build automation | `Makefile` (30 targets) | worker-1 → phase 7 | REVIEWED | discovery §5 | 4 broken target groups (build, test-unit/integration, coverage); validate mutates source | pending | |
| CI / release | `.github/workflows/` | worker-1 → phase 7 | REVIEWED | discovery §1 | no quality-gate CI at all; docs-only workflow | pending | |
| Repo hygiene / boundaries | `.gitignore`, `pyrightconfig.json`, `docs/_config.yml` | worker-1 → phase 7 | REVIEWED | discovery §1 | third unwired type-check config | pending | well-organized overall |
| CLI | `packages/twinklr/cli/` | worker-2 → phase 7 | REVIEWED | discovery §2 | hardcoded display graph; OPENAI-only gate; no display/cache/config subcommands | pending | single console script |
| Pipeline framework | `core/pipeline/{definition,executor,execution,context,result,stage}.py` | worker-2 → phase 1 | REVIEWED | discovery §3 | checkpoint config dead; `critical` field legacy; restartability defeated by random session_id | pending | DAG/waves/FAN_OUT solid |
| Pipeline definitions | `core/pipeline/definitions/`, `display_stages.py`, `stages.py` | worker-2 → phase 1 | REVIEWED | discovery §2, §5 | `stages.py` dead (confirmed); display pipeline unreachable from CLI | pending | |
| Configuration | `core/config/` | worker-2 → phase 1 | REVIEWED | discovery §3, §5 | AppConfig.logging dead; token_budget no-op (confirmed); inconsistent extra= strictness; silent default fallback for missing config.json; `.env` never loaded | pending | SecretStr hygiene good |
| Caching | `core/caching/` | worker-2 → phase 1 | REVIEWED | discovery §3 | atomic commit good; session-scoped keys defeat CLI reuse | pending | |
| API clients (LLM) | `core/api/llm/`, `core/agents/providers/` | workers 2+4 → phase 3 | REVIEWED | discovery §5 | two OpenAI clients, divergent retry/timeout; Anthropic unreachable + relaxed typing; no native structured outputs | pending | |
| API clients (audio) | `core/api/{http,audio}/` | worker-3 (shallow) → phase 1 | NOT_STARTED | discovery §7 | retry/rate-limit behavior unverified | pending | deferred (critic A6: was mislabeled IN_PROGRESS) |
| Audio: deterministic DSP | `core/audio/{rhythm,energy,spectral,harmonic,structure,timeline,advanced,utils}` | worker-3 → phase 2 | REVIEWED | discovery §3, §5 | dead duplicates (tempo-changes fn, 3 detector methods); dead `context_weights`; untyped features dict at core boundary | pending | DSP itself deterministic, no seeds |
| Audio: metadata/lyrics/phonemes | `core/audio/{metadata,lyrics,phonemes}/` | worker-3 → phase 2 | REVIEWED | discovery §3, §5 | diarization orphaned; unreachable ImportError guard; nondeterministic stages inside "deterministic" layer; LyricsBundle version inconsistency | pending | degradation design consistent |
| Audio: validation & orphans | `core/audio/{validation,genre,context,sections.py,models}` | worker-3 (+follow-up) → phase 2 | REVIEWED | discovery §5 | 2 of 6 validator checks broken (schema drift); GenreClassifier + context/ orphaned; `Section` model dead (confirmed) | pending | `generate_section_ids` confirmed live |
| Agents: runner & prompts | `core/agents/{async_runner,spec,prompts/}` | worker-4 → phase 3 | REVIEWED | discovery §3 | schema/taxonomy auto-injection airtight (strength); pack.yaml unenforced/inconsistent; token-delta race (confirmed) | pending | |
| Agents: iteration/judging | `core/agents/shared/judge/`, `state_machine.py` | worker-4 → phase 3 | REVIEWED | discovery §3, §5 | docs claim removed LLM-validator role; OrchestrationStateMachine dead (confirmed); loop value unproven (H4) | pending | verdict enforcement is a strength |
| Agents: planners | `core/agents/sequencer/{macro_planner,group_planner,moving_heads}/`, `audio/{profile,lyrics}` | worker-4 → phase 3 | REVIEWED | discovery §3 | 5 auto-repair passes (strength); ultra-short-section bypass; inconsistent prompt_base_path conventions | pending | |
| Agents: assets | `core/agents/assets/` (11 modules) | — → phase 3 | NOT_STARTED | discovery §6, critic A6/E3 | unread; contains paid image-generation client (`image_client.py:180`, gpt-image-1.5) | pending | explicitly owned by phase 3; phase 5 must not assume |
| Sequencer: moving heads | `core/sequencer/moving_heads/` | worker-5 → phase 4 | REVIEWED | discovery §3, §5 | 38 code-defined templates (authoring = Python); TODO production-hardening in movement handler; transition cycle detection stubbed | pending | |
| Sequencer: display | `core/sequencer/display/` | worker-5 → phase 5 | REVIEWED | discovery §2, §5 | unreachable from CLI; TRIM overlap policy; trace sidecar (strength) | pending | |
| Templates & theming | `core/sequencer/{templates,theming}/` | worker-5 → phase 5 | REVIEWED | discovery §3, §5 | recipe data gitignored (repo carries no display templates); DisplayGraph→ChoreographyGraph migration unfinished | pending | |
| Timing & vocabulary | `core/sequencer/{timing,vocabulary}/` | worker-5 → phase 4 (phase 3 consumer-review) | REVIEWED | discovery §3 | BeatGrid sole-timing-authority (strength); vocabulary = planner/renderer contract | pending | seam owner per critic C3 |
| Curves | `core/curves/` | worker-5 → phase 4 | REVIEWED | discovery §5 | simplify_rdp dead (confirmed); dual legacy/categorical APIs; triangle-phase TODO | pending | bounds double-enforced |
| xLights formats | `core/formats/xlights/` | worker-5 (+follow-up) → phase 5 | REVIEWED | discovery §3, §5, critic B3 | **confirmed defect: template content loss on shipped path**; no version-compat logic; conflicting default versions; zero round-trip tests; parser/exporter untested | pending | DisplayElements preservation partial mitigation |
| Feature engineering | `core/feature_engineering/` | worker-6 → phase 6 | REVIEWED | discovery §2, §3 | consumed only by unreachable display path; transitions v1/v2 straddle; "ANN" is brute force | pending | 94 test files |
| Feature store | `core/feature_store/` | worker-6 → phase 6 | REVIEWED | discovery §3 | no migration path; per-call commits; no cross-process handling; NullFeatureStore default | pending | |
| Recipe builder / profiling | `core/recipe_builder/`, `core/profiling/` | worker-6 → phase 6 | REVIEWED | discovery §2 | offline-by-design (documented); last real code commit touched this (2026-04-01) | pending | |
| Reporting / evaluation | `core/reporting/` | worker-6 → phase 6 | REVIEWED | discovery §5 | standalone quality tool (strength); no stored eval results in repo; 1 TODO | pending | |
| Resolvers | `core/resolvers/` | — → phase 4 | NOT_STARTED | worker-7 §1 | zero test coverage | pending | 242 lines; must be read in phase 4 |
| Sequencer: planning/models/rendering | `core/sequencer/{planning,models,rendering}/` | — → phases 3/5/4 | NOT_STARTED | critic A2/A3 | `rendering/categorical_resolver.py` has zero test coverage (second untested package) | pending | planning→phase 3 (planner contract), models→phase 5, rendering→phase 4 |
| Agents: analytics/context/logging | `core/agents/{analytics,context,logging}/` | — → phase 3 | NOT_STARTED | critic A3 | not individually surveyed | pending | covered in spirit by parent row; listed explicitly per critic |
| Setup shims | `packages/twinklr/{core,cli}/setup.py` | — → phase 1 | NOT_STARTED | critic A4 | setuptools `find_packages` shims inside a uv workspace — vestigial or conflicting with build backend | pending | |
| Licensing | `LICENSE` (absent), pyproject `license` fields (absent) | — → phase 7 + Stage 2 | REVIEWED | critic A5/E2 | no license anywhere; material for product-strategy verdict | pending | |
| io / logging / parsers / utils (core) | `core/{io,logging,parsers,utils}/` | — → phase 1 | NOT_STARTED | — | two configure_logging implementations flagged | pending | shallow coverage in Stage 1 |
| Session | `core/session.py` | worker-2 → phase 1 | REVIEWED | discovery §3 | single shared provider instance (race contributor); lazy init pattern | pending | |
| Tests & fixtures | `tests/` (404 test files, 500 total), `conftest.py` | worker-7 → phase 7 | REVIEWED | discovery §5, critic A1 | no centralized LLM fake (74 files ad-hoc mock); no round-trip/golden tests; `.xsq` parser/exporter untested; 4 reported failures unverified | pending Stage 4 run | |
| Scripts & utils | `scripts/` (32 files, 30 py), `utils/video_demo.py` | workers 1+5 → phase 7 | REVIEWED | discovery §2, critic A7 | mostly unreferenced by automation; validation tool post-hoc only | pending | |
| Docs site | `docs/` | worker-7 → phase 7 | REVIEWED | discovery §4 | multi-agent + FE narratives drift from code; paths spot-check clean | pending | |
| Knowledge trees | `AGENTS.md`, `context/`, `memories/`, `prompts/`, `templates/` | orchestrator | REVIEWED | discovery §4 | 2 context docs carry stale architecture claims; known-failures memory stale-flagged | pending | this review updates at closeout |

## Coverage assertions (revised at gate per critic A)

- Every top-level directory of `packages/twinklr/core/` appears above, including the
  subpackages the critic flagged as previously implicit (`sequencer/{planning,models,rendering}`,
  `agents/{analytics,context,logging,assets}`, setup shims, licensing). All NOT_STARTED
  rows carry an explicit phase assignment — they are deferred, not forgotten.
- Two packages have zero test coverage: `core/resolvers/` and
  `core/sequencer/rendering/`; `core/formats/xlights/` is effectively untested (one
  direct test file, none for parser/exporter).
- Generated/vendored/third-party: none tracked in repo (`data/`, `artifacts/`
  gitignored and absent) — nothing to sample. Doc illustration assets (`docs/assets/`)
  are content, N/A for code review.
- No area is BLOCKED at discovery level. Runtime-dependent evidence (test run, xLights
  acceptance, display-pipeline execution) is deferred to Stage 4 and may introduce
  BLOCKED rows there (recipe/FE data absence — see discovery §6).
