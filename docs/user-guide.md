---
title: "User Guide"
description: "Installation, configuration, and usage instructions for Twinklr."
---

# User Guide

Step-by-step instructions for installing, configuring, and running Twinklr to generate xLights sequences from audio files.

---

## Prerequisites

- **Python 3.13** (required; 3.14 is not supported — see `pyproject.toml` `requires-python`)
- **[uv](https://github.com/astral-sh/uv)** — Astral's fast Python package manager
- **Provider access** — an OpenAI API key for the default cloud path, or a separately
  installed loopback Ollama server for the opt-in local adapter
- **xLights** — to view and use the generated `.xsq` sequence files

Optional:
- **Genius API token** — for online lyrics lookup (`GENIUS_ACCESS_TOKEN`)
- **AcoustID API key** — for audio fingerprinting (`ACOUSTID_API_KEY`)
- **HuggingFace token** — for WhisperX model downloads (`HF_TOKEN`)

---

## Installation

### Standard Install

```bash
# Clone the repository
git clone https://github.com/bluewatersql/twinklr.git
cd twinklr

# Install all packages with dev dependencies
make install
```

This runs `uv sync --extra dev --extra anthropic --all-packages`, installing both workspace packages (`twinklr-core` and `twinklr-cli`), development tools (pytest, ruff, mypy), and the optional Claude provider SDK that the test suite imports.

_Source: `Makefile` target `install`_

### Full Install (with ML)

For WhisperX lyrics transcription and other ML features:

```bash
make install-dev
```

This adds the `ml` extra group (~2GB+ for PyTorch and WhisperX). WhisperX models download automatically on first use (~150MB for the `base` model).

Package installation does not establish working WhisperX transcription on the current
default FFmpeg 9; runtime audio execution remains owner-deferred. See the active
[P4-T1 task contract](../changes/twinklr-reactivation-review/build/specs/phase-4-compounding/P4-T1-ml-chain-python-bump.md).

_Source: `Makefile` target `install-dev`_

### Optional Stem Separation

To enable cached Demucs 4.1.0 source separation on supported systems:

```bash
uv sync --package twinklr-core --extra stems
```

The stage remains off until `audio_processing.enhancements.stems.enabled` is set.
Apple Silicon follows Demucs's automatic MPS selection and retries once on CPU if an
MPS kernel fails. Intel macOS is explicitly unsupported by this extra because Demucs
4.1.0 conflicts with Twinklr's NumPy 2 requirement there; analysis remains available
with a result-visible full-mix fallback. The default install does not include Demucs,
PyTorch, or model downloads.

### Verify Installation

```bash
make verify-install
```

Checks that both packages are importable and the CLI responds to `--help`.

---

## Environment Setup

### Provider credentials

The default OpenAI provider requires an API key for LLM agent calls:

```bash
export OPENAI_API_KEY='your-key-here'
```

The CLI validates credentials after loading `config.json`. The opt-in local Ollama
provider does not require `OPENAI_API_KEY`; remote OpenAI and Anthropic providers still
fail before pipeline execution when their configured key is empty.
`.env.example` lists the variables Twinklr reads, but nothing in the codebase loads a
`.env` file automatically — export the variable in your shell (or set it in your shell
profile) rather than relying on a `.env` file.

_Source: `packages/twinklr/cli/main.py` (`build_run_pipeline`) and
`packages/twinklr/core/agents/providers/factory.py` (`validate_llm_provider_config`)_

### Optional: Additional API Keys

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required when `llm_provider` is `"openai"` |
| `ANTHROPIC_API_KEY` | Required when `llm_provider` is `"anthropic"` (must start with `sk-ant-`) |
| `GENIUS_ACCESS_TOKEN` | Genius lyrics lookup (set `enable_lyrics_lookup: true` in config) |
| `ACOUSTID_API_KEY` | AcoustID audio fingerprinting (set `enable_acoustid: true` in config) |
| `HF_TOKEN` | HuggingFace token for WhisperX model downloads |

### Environment Check

```bash
make env-check
```

Verifies that `uv` and Python are available. Its API-key check applies to the default
OpenAI setup; Ollama configuration is validated when the CLI loads `config.json`.

---

## Configuration Files

Twinklr uses three JSON configuration files. None are committed to the repo — create them from the defaults documented below.

### `config.json` (App Config)

Application-level settings shared across all jobs. Loaded by `AppConfig` in `packages/twinklr/core/config/models.py`.

The table is a deliberately curated user-facing subset, not a second schema. Its
**Ledger path** column is checked against P4-T5's exhaustive config-effect registry:
every listed path must remain declared and backed by an effect or invariant test, and a
removed path cannot remain here. Nested expert fields remain discoverable from the
Pydantic models; the registry accounts for all of them.

| JSON field | Default | Observable effect | Ledger path |
|---|---|---|---|
| `project_root` | current directory | Base for relative cache and artifact paths; `TWINKLR_PROJECT_ROOT` is the fallback | `app.project_root` |
| `cache_dir` | `"data/audio_cache"` | Changes the audio-analysis cache location | `app.cache_dir` |
| `llm_provider` | `"openai"` | Selects the provider adapter | `app.llm_provider` |
| `llm_base_url` | `"https://api.openai.com/v1"` | Changes the provider endpoint after provider-specific URL validation | `app.llm_base_url` |
| `audio_processing.hop_length` | `512` | Changes analysis frame spacing | `app.audio_processing.hop_length` |
| `audio_processing.frame_length` | `2048` | Changes analysis window length | `app.audio_processing.frame_length` |
| `audio_processing.enhancements.stems.enabled` | `false` | Opts into cached Demucs source separation | `app.audio_processing.enhancements.stems.enabled` |
| `audio_processing.enhancements.stems.model_name` | `"htdemucs"` | Selects the Demucs model and changes cache identity | `app.audio_processing.enhancements.stems.model_name` |
| `audio_processing.enhancements.stems.vocal_presence_threshold` | `0.05` | Changes the separated-vocal gate for WhisperX | `app.audio_processing.enhancements.stems.vocal_presence_threshold` |
| `audio_processing.rhythm_source` | `"dsp"` | Selects the beat/downbeat producer | `app.audio_processing.rhythm_source` |
| `audio_processing.structure_source` | `"dsp"` | Selects the musical-section producer | `app.audio_processing.structure_source` |
| `logging.level` | `"INFO"` | Changes CLI log filtering | `app.logging.level` |
| `logging.format` | timestamped text | Changes the installed CLI log formatter | `app.logging.format` |

The `llm_api_key` field is populated from the `OPENAI_API_KEY` environment variable
automatically, or from `ANTHROPIC_API_KEY` when `llm_provider` is `"anthropic"`. Ollama supplies the SDK's required-but-ignored local placeholder
internally, so no key belongs in local configuration.

Minimal example:

```json
{
  "llm_provider": "openai"
}
```

For a running local Ollama server, use a loopback OpenAI-compatible endpoint:

```json
{
  "llm_provider": "ollama",
  "llm_base_url": "http://127.0.0.1:11434/v1"
}
```

Model selection remains in the role settings in `job_config.json`; there is no inert
app-level model override. The recommended Ollama model (and the smoke-test default) is the Ollama
**cloud** model `glm-5.3:cloud`: the loopback daemon forwards `:cloud` requests to Ollama's hosted
service, so no local model weights are downloaded or run (sign in once with
`ollama signin`). Set each role you intend to run, for example:

```json
{
  "agent": {
    "plan_agent": {"model": "glm-5.3:cloud"},
    "judge_agent": {"model": "glm-5.3:cloud"},
    "profile_agent": {"model": "glm-5.3:cloud"},
    "lyrics_agent": {"model": "glm-5.3:cloud"},
    "refinement_agent": {"model": "glm-5.3:cloud"}
  }
}
```

Ollama structured requests use `/v1/chat/completions` with a JSON-schema
`response_format`; OpenAI requests continue to use `/v1/responses`. Ollama mode is
opt-in and limited to loopback URLs. Image/vision stages are not supported by this
adapter.

For Claude, set `"llm_provider": "anthropic"`, export `ANTHROPIC_API_KEY`, and set every
role's `model` in `job_config.json` to a `claude-*` id (for example `claude-opus-5-5`).
Each role's `reasoning_effort` becomes Claude's `effort`, and `temperature` is ignored
because current Claude models reject sampling parameters. Image/vision stages are not
supported by this adapter.

#### Explicit local schema smoke

The repository includes a `local_only` test against Twinklr's real `MacroPlan` schema.
It does not install Ollama or pull a model. With the Ollama daemon running and signed in,
authorize exactly one request with:

```bash
TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 \
uv run pytest tests/local_only/test_ollama_structured_outputs.py -q --no-cov
```

The model defaults to `glm-5.3:cloud` and the base URL to `http://127.0.0.1:11434/v1`;
override them with `TWINKLR_OLLAMA_MODEL` and `TWINKLR_OLLAMA_BASE_URL`. The request
timeout (`TWINKLR_OLLAMA_TIMEOUT_SECONDS`, default 300) and output budget
(`TWINKLR_OLLAMA_MAX_TOKENS`, default 16000) leave room for thinking models. The smoke
disables SDK retries, provider transport retries beyond the single request, schema
repair, and JSON-object fallback. Passing it proves schema validity for that specific
model; it is not a choreography-quality benchmark. Step-by-step:
[Ollama cloud smoke runbook](../changes/twinklr-reactivation-review/runbooks/01-ollama-cloud-smoke.md).

### `job_config.json` (Job Config)

Job-specific settings. Loaded by `JobConfig` in `packages/twinklr/core/config/models.py`. Schema version 3.0 is the default; 3.1 is also accepted.

The same registry-backed subset policy applies here.

| JSON field | Default | Observable effect | Ledger path |
|---|---|---|---|
| `schema_version` | `"3.0"` | Declares the job schema; `"3.0"` and `"3.1"` are accepted, other values fail validation. `"3.1"` is required to select `moving_heads.mode` `"physical_v2"` | `job.schema_version` |
| `fixture_config_path` | `"fixture_config.json"` | Selects the fixture definition loaded for planning/rendering | `job.fixture_config_path` |
| `agent.max_iterations` | `3` | Sets planner/judge cycles; `0` plans once, runs heuristics, and skips the judge | `job.agent.max_iterations` |
| `agent.success_threshold` | `70` | Sets the accepted judge score on the single 0-100 configured scale | `job.agent.success_threshold` |
| `agent.plan_agent.model` | `"gpt-5.6-sol"` | Selects the macro, moving-head, and group planner model | `job.agent.plan_agent.model` |
| `agent.plan_agent.reasoning_effort` | `"high"` | Sets planner reasoning effort and cache identity | `job.agent.plan_agent.reasoning_effort` |
| `agent.judge_agent.model` | `"gpt-5.6-terra"` | Selects the macro, moving-head, group, and holistic judge model | `job.agent.judge_agent.model` |
| `agent.judge_agent.reasoning_effort` | `"low"` | Sets judge reasoning effort and cache identity | `job.agent.judge_agent.reasoning_effort` |
| `agent.profile_agent` | `gpt-5.6-sol`, medium reasoning | Controls audio-profile request settings | `job.agent.profile_agent` |
| `agent.lyrics_agent` | `gpt-5.6-sol`, medium reasoning | Controls lyrics-context request settings | `job.agent.lyrics_agent` |
| `agent.refinement_agent` | `gpt-5.6-sol`, medium reasoning | Controls holistic-correction request settings | `job.agent.refinement_agent` |
| `agent.asset_enricher_agent` | `gpt-5.6-terra`, low reasoning | Controls image-prompt enrichment; does not enable generation | `job.agent.asset_enricher_agent` |
| `agent.image_model` | `"gpt-image-2"` | Selects the Images API model when assets are enabled | `job.agent.image_model` |
| `agent.llm_logging.enabled` | `true` | Enables or disables per-call LLM logs | `job.agent.llm_logging.enabled` |
| `agent.agent_cache.enabled` | `true` | Enables or disables agent-result cache reuse | `job.agent.agent_cache.enabled` |
| `assets.enabled` | `false` | Opts display/show into generated Pictures assets | `job.assets.enabled` |
| `assets.dry_run` | `false` | Reports capped asset work without enrichment or image calls | `job.assets.dry_run` |
| `assets.max_image_requests_per_run` | `1` | Fixed one-request policy; alternative values fail validation | `job.assets.max_image_requests_per_run` |
| `assets.estimated_image_usd_per_request` | `0.20` | Fixed conservative reservation used by the pre-call policy | `job.assets.estimated_image_usd_per_request` |
| `assets.image_quality` | `"low"` | Fixed supported image quality; alternatives fail validation | `job.assets.image_quality` |
| `assets.asset_base_path` | `null` | Changes the generated-asset/catalog root | `job.assets.asset_base_path` |
| `write_checkpoint` | `true` | Writes the final moving-head plan for `twinklr eval-report`; it does not control stage cache reuse | `job.write_checkpoint` |
| `transitions.enabled` | `true` | Enables section transition planning | `job.transitions.enabled` |
| `transitions.default_duration_bars` | `0.5` | Sets the fallback transition length | `job.transitions.default_duration_bars` |
| `timeline_tracks.sections` | `true` | Includes or omits section timing markers | `job.timeline_tracks.sections` |
| `moving_heads.mode` | `"legacy_v1"` | Selects the moving-head renderer. `"physical_v2"` needs schema `"3.1"`, a `physical_profile` on every fixture and a usable `initial_states` entry for each; a job missing any of them is refused when its fixtures load, naming each fixture and item, before any analysis or provider request. The planner is offered only templates that carry explicit physical data: none of the builtins does, but a `physical_v2` run also loads the six physical families in `catalog/templates/moving_heads_physical` (fly-out and fly-in cascades, target orbit, mirror wings, finite snap hold and masked wheel flick; that directory's README gives each one's motion and needs: the cascades and mirror wings need a rig topology, the flick needs a `flick` attribute preset that sets `color`, and every family but the cascades needs the profile to declare a shutter state named exactly `open`; the families are authored for 4/4, and in 3/4 or 6/8 the orbit and the wings are left out because their cycles would end mid-path; under a topology derived from `position_index`, removing the highest-index head can change the other heads' phases, which a declared `topology` avoids), and a run with none is refused before analysis; right after audio analysis, before any planning, every offered template is dry-compiled on the rig over the whole song (with no preset and with each preset it declares), and the dark repositioning between its own cues is planned from `initial_states` under `reposition_fallback`, so a template whose cues cannot be repositioned between is refused, as is one whose pan or tilt changes faster than the head can follow (it would fall more than one DMX step behind, which on an 8-bit axis at low speed is reached by sub-degree wobble), and a song whose detected beats cannot establish a musical phase (fewer than two, or beats outside the song) is refused, because the renderer never infers tempo. A family that fails these checks on the rig is left out of the planner's offer instead, with the reason logged and recorded in the trace's `admission_exclusions`; the run is refused only when no template remains, and a `--template-dir` template that fails still refuses it. The check also logs each offered template's worst-case section-entry dip: how many beats, at the song's shortest beat, a head may stay dark entering one of its sections. Silence or a fade at either end of the song is not refused: the renderer covers only the detected beats plus one beat interval beyond the first and last (or up to the song's edge when that is nearer), holds every fixture dark outside that covered span, drops a cue that would start outside it and cuts one that runs past its end; the trace records the covered span, the longest gap between detected beats and each dropped cue. A long gap between two detected beats mid-song is one long beat and stays lit. A preset id the template does not declare applies no preset. Each head enters each section on its own: where its first cues can be played as authored after its previous cue (or the initial state) it starts as authored; otherwise it stays dark for whole beats, long enough for any repositioning into it, then cuts in its cues where they would be, never inside a shutter state too short to take effect (a cue wholly inside that window is dropped and recorded). A head missing from the rig therefore changes no other head's output. The trace's `entry_windows` lists each section's window per fixture, and every `dropped_cues` record gives its `reason`. It writes complete 20 ms frames of constant DMX effects over model-relative channels 1-48, plans dark repositioning between cues instead of applying `transitions`, does not apply planner intent, and records its render identity and evidence in the `.xsq.trace.json`. Any refusal writes no file. `twinklr show`, `inject` and `regenerate` render legacy output only and refuse it; the checkpoint records the mode, and `eval-report` refuses a physical checkpoint before analysis; `twinklr display` renders no moving heads and ignores it | `job.moving_heads.mode` |
| `moving_heads.initial_states` | `{}` | Run-supplied time-zero state per fixture id (unwrapped `pan_deg`/`tilt_deg`, `dimmer`, `discrete_states`, and explicit `settled`/`dark` evidence) for the physical renderer. A fixture without an entry has an unknown initial state. Under `physical_v2` every fixture needs a settled entry its profile accepts, and an entry must name a fixture of the rig; otherwise the job is refused when its fixtures load. Enters render identity and the render trace, but not the planner's session or cache, so editing it re-renders without re-planning | `job.moving_heads.initial_states` |
| `moving_heads.reposition_fallback` | `"error"` | Applies only to physical (`physical_v2`) output: what the render does with a cue whose dark repositioning cannot be planned. `"error"` refuses the render (before planning when the gate finds it inside a template); `"preserve_aim"` plays the cue at the aim the head holds; `"drop_accent"` keeps the cue dark and plans the next cue from that aim. A fallback applies only to cues of template steps that declare the same `physical_reposition_fallback`, and never covers an unknown initial state, unknown visibility latency, a missing darkness guarantee or a lock; each substituted cue is listed in the trace. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.reposition_fallback` |
| `moving_heads.on_unplayable` | `"dark"` | Applies only to physical (`physical_v2`) output: what the render does with a cue the plan placed where it cannot play honestly, after any `reposition_fallback` the cue and the job both declare. `"dark"` leaves the fixture dark over that cue (it parks there as over any gap) and the render continues: a cue whose dark repositioning still cannot be planned (dropping one can leave the next one too little time, so this repeats until every remaining cue plans), a cue a shutter state too short to take effect lies in (such as a last cue cut to one frame at the song end), a step a fixture cannot play at this section's placement (rate, bounds, pulse or lit-window width) although it plays from bar 1 over the song, and every cue of a section too short for a `ONCE` cycle. Each is listed in the trace's `dropped_cues` with `reason` `"unplayable"`, its `code` and `detail`, the render record carries `unplayable_totals` per code, and the run logs one warning with the counts, which `twinklr run` prints. Never covers an unknown initial state or a lock, and never applies to what is refused before planning: a template that cannot play from bar 1 over the song is still refused, at the gate or at render. `"error"` refuses the render instead. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.on_unplayable` |
| `moving_heads.max_effects` | `1000000` | Applies only to physical (`physical_v2`) output, never to legacy output: the most DMX effects one render may emit after identical adjacent 20 ms frames are merged. More fails the render with `output_budget_exceeded`; frames are never dropped to fit. Must be positive; a non-default value enters render identity | `job.moving_heads.max_effects` |
| `moving_heads.max_xsq_bytes` | `134217728` (128 MiB) | Applies only to physical (`physical_v2`) output, never to legacy output: the largest serialized `.xsq`, in UTF-8 bytes, one render may write. Larger fails the render with `output_budget_exceeded`; frames are never dropped to fit. Must be positive; a non-default value enters render identity | `job.moving_heads.max_xsq_bytes` |

The planner schema may describe up to four narrative assets (`maxItems=4`), but the
enabled live path authorizes only one image-provider request and reports the rest as
skipped. When the provider returns complete and internally consistent modality token
usage, Twinklr records actual image cost using the dated `gpt-image-2` rate card. Missing
or inconsistent usage leaves actual cost unavailable and retains the full `$0.20`
reservation; a reported cost above the estimate is surfaced explicitly.
Cache replay validates every stored asset as a non-empty PNG with the expected
dimensions before any enrichment or provider work. A corrupt or mismatched cached file
fails loudly and is never rebilled automatically. Replay summaries report cached work
for that run while preserving the catalog entry's original `created` provenance.

Minimal example:

```json
{
  "schema_version": "3.0",
  "fixture_config_path": "fixture_config.json",
  "agent": {
    "max_iterations": 3,
    "plan_agent": { "model": "gpt-5.6-sol", "reasoning_effort": "high" },
    "judge_agent": { "model": "gpt-5.6-terra", "reasoning_effort": "low" }
  }
}
```

Every OpenAI LLM role sends its configured `reasoning_effort` explicitly;
providers without that capability filter the option. Set all of
`model`, `temperature`, and `reasoning_effort` together on the role you are
changing; cache identity includes the model and reasoning level, so a retarget
gets a fresh result rather than reusing an incompatible plan. Asset generation
remains disabled by default; changing `agent.image_model` alone does not turn it on.
To inspect a run without any image or enrichment calls, set
`"assets": {"enabled": true, "dry_run": true}`. A live opt-in uses
`"assets": {"enabled": true}` and requires the OpenAI provider. Generated files and
the atomically updated `asset_catalog.json` land under the configured assets root;
catalog paths remain relative so moving that root preserves cache hits. Exactly one
provider request is authorized per run and ambiguous failures are never retried. The
`$0.20` value is a conservative estimate/reservation, not a guaranteed hard spend cap;
trustworthy complete usage populates actual cost, while missing or inconsistent usage
retains the reservation and leaves actual cost unavailable.

Iterative judging is retained by default. On cycle two and later, each judge sees its
own prior verdict summaries, feedback, and issues from the current run. That history is
run-local and is not shared across judge roles. Changing `success_threshold` or
`max_iterations` changes prompt/cache identity for the affected planning stage.

### `fixture_config.json` (Fixture Config)

Defines the physical moving head fixtures — names, DMX channels, and positions. The path is specified in `job_config.json` as `fixture_config_path`, resolved relative to the job config directory.

Each fixture's `dmx_mapping` also declares the value the render exports for that channel when the choreography never writes to it: `shutter_default` (0-255, defaults to `255` — open), and `color_map`/`gobo_map`'s `"open"` entry for color and gobo. A channel the mapping does not declare at all (e.g. `shutter_channel: null`) is omitted from the exported settings string rather than defaulted.

A fixture's `config` may also carry an optional `physical_profile` for the opt-in `physical_v2` renderer; in the `base_config` form, `base_config.physical_profile` applies to every fixture and a fixture's `config_overrides.physical_profile` replaces it for that fixture. An invalid profile fails when the fixture file loads, naming the fixture. The `physical_v2` renderer requires one on every fixture and renders from it alone; the legacy renderer ignores it and refuses a physical channel value rather than exporting nothing. Physical output is written to the fixture's own xLights model, which must be a single-color DMX model with at least `footprint` channels; `twinklr run --layout` checks this before analysis (and records the layout's content hash in the trace), and without a layout the check is skipped with a warning. It declares the fixture explicitly rather than inferring anything from the legacy fields above: `profile_id`, `provenance` (`synthetic`, `manufacturer` or `measured`), the model-relative channel `footprint` (at most 48, the xLights DMX effect's limit) with a default byte for every channel `1..footprint`, continuous `axes` (`pan`/`tilt` in degrees, `dimmer` normalized) with calibrated `physical_min`/`physical_max`, an optional narrower `allowed_min`/`allowed_max` operating window that does not rescale the mapping, coarse/fine offsets and inversion, `discrete` shutter/color/gobo channels whose named states each select one explicit byte inside a declared, non-overlapping range, and `visibility` (what extinguishes output, and close/open latency). A profile cannot claim darkness it cannot produce: the shutter's `open_state` cannot extinguish, and `dimmer_zero_extinguishes` needs a dimmer axis calibrated from `0` whose operating window admits `0`. Normalized axes lie within `0..1`. Unknown speed, latency and settle times stay `null`; they are never filled in. A profile does not say where a fixture is now; that is `moving_heads.initial_states` in the job config. The retired `capabilities` and `movement_speed` keys stay ignored.

A fixture group may also declare `presets`, named components that `physical_v2` template steps refer to by id (`component_refs`, below) instead of hard-coding angles and profile state names; the legacy renderer ignores them, and an empty `presets` is left out of the group's dump:

| Key | Meaning |
|---|---|
| `presets.positions.<id>.fixtures.<fixture_id>` | That fixture's aim, `pan_deg` and `tilt_deg`, in unwrapped fixture-local degrees (never taken modulo 360; the renderer's bounds and travel-rate checks still apply) |
| `presets.positions.<id>.fallback` | Another position preset id, used for every fixture this preset does not list |
| `presets.attributes.<id>.fixtures.<fixture_id>` | That fixture's held `shutter`, `color` and `gobo` states, named as its own `physical_profile` names them, and a normalized `dimmer` level; at least one is set. One preset id can so select a different state name on each profile |
| `presets.attributes.<id>.fallback` | Another attribute preset id, used for every fixture this preset does not list |

A preset naming a fixture outside the group, a state its profile does not declare, a dimmer level on a profile without a dimmer axis, a fallback that is not declared, or a fallback chain that cycles fails when the fixture file loads. A referenced preset that declares nothing for a fixture, along its whole fallback chain, refuses the render (and, for an offered template, the run before planning); a head is never aimed at a center or default. Presets are rig data: an edit changes the render fingerprint, never the planner's session or cache.

A fixture group may also declare a `topology`, the canonical full rig that a `physical_v2` step's `physical_distribution` (below) spreads phase over; the legacy renderer ignores it, and an absent `topology` is left out of the group's dump:

| Key | Meaning |
|---|---|
| `topology.members` | One entry per head of the full rig, including a head this group lacks (a missing or disabled head keeps its place, so the others are never rephased). Every fixture of the group must be listed; fixture ids and ordinals are unique |
| `topology.members.fixture_id` | The head this entry places |
| `topology.members.row` | Its row; rows order first |
| `topology.members.column` | Its column within the row; columns order next |
| `topology.members.ordinal` | A unique number that orders heads sharing a row and column |

Heads are ranked in `(row, column, ordinal, fixture_id)` order over the whole topology, before any head is selected. A group without `topology` gets one derived row when every fixture declares `position.position_index`, ranked by `position_index` itself (index 1 is the first slot), in the rig's left-to-right order: an index the file skips is an empty slot, so a missing head keeps its place whenever the remaining indices show it (a head missing after the highest index cannot be seen; declare a `topology` for that). Two fixtures with the same `position_index` refuse a step with a distribution, naming them. Without either, a step with a distribution refuses the render, and the run before planning, naming the fixture group. The topology is rig data: it changes the render fingerprint, never the planner's session or cache.

_Source: `packages/twinklr/cli/main.py` (`_resolve_fixture_config_path`),
`packages/twinklr/core/config/fixtures/dmx.py` (`DmxMapping`),
`packages/twinklr/core/config/fixtures/capabilities.py` (`FixtureCapabilities`),
`packages/twinklr/core/config/fixtures/presets.py` (`RigPresetLibrary`) and
`packages/twinklr/core/sequencer/models/moving_heads/topology.py` (`FixtureTopology`)_

---

## Running the Pipeline

### CLI Command

```bash
uv run twinklr run \
  --audio path/to/song.mp3 \
  --config path/to/job_config.json \
  --out artifacts \
  --app-config config.json
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--audio` | Yes | — | Path to audio file (MP3 or WAV) |
| `--config` | Yes | — | Path to job config JSON |
| `--out` | No | `.` | Output directory |
| `--app-config` | No | `config.json` | Path to app config JSON |
| `--template-dir` | No | — | Load strict JSON moving-head templates from this directory after Python builtins and, for a `physical_v2` job, after the physical family catalog, which loads automatically; naming that catalog directory loads nothing twice |
| `--allow-template-overrides` | No | `false` | Explicitly permit a data template to replace a colliding Python builtin ID |
| `--layout` | No | — | Path to your `xlights_rgbeffects.xml`. Used only by `moving_heads.mode` `"physical_v2"`: before any analysis, every fixture's model must be in the layout, a DMX model (`DisplayAs` starting `Dmx`), single color when it records a `StringType`, and declare a channel count of at least its profile's `footprint` (read from `DmxChannelCount`, which xLights 2026.19 writes on DMX models, else from `parm1` as an unverified fallback; a model declaring neither is refused); otherwise the run is refused, naming fixture, model and item. Without it the check is skipped with a warning. A `legacy_v1` run ignores it entirely |

Twinklr takes **no input sequence**. It used to require `--xsq` and rewrite the sequence you
gave it, which cost you your jukebox state, your per-element display state, anything in the
file Twinklr does not model, and flattened multi-layer lyric timing tracks — on every run.
Twinklr now emits its own files for you to import into your show (see
[Understanding Outputs](#understanding-outputs)). If you have a script that passes `--xsq`,
delete the flag: it is rejected rather than ignored, so a stale invocation fails loudly
instead of quietly building something other than what you asked for.

Your rig comes from the fixture config that `job_config.json` points at
(`fixture_config_path`). That file decides how many moving heads the planner is told about
— an 8-head rig is planned as 8 heads — and which xLights models the effects are written
to.

_Source: `packages/twinklr/cli/main.py` (`build_arg_parser`, `build_run_pipeline`)_

For the RGB/pixel display pipeline, provide the xLights layout file as well:

```bash
uv run twinklr display \
  --audio path/to/song.mp3 \
  --layout path/to/xlights_rgbeffects.xml \
  --config path/to/job_config.json \
  --out artifacts \
  --app-config config.json
```

The display command derives its targets and xLights mappings from the layout, loads the
tracked starter recipe catalog, and writes a display `.xsq` plus its render-trace sidecar.
Use `--fe-output-dir DIR` to apply persisted feature-engineering context. Add
`--style NAME` only with that directory to select a named grouped fingerprint.
The display command may omit `--app-config`; Twinklr then uses application defaults.
If you supply the flag, its file must exist and validate.

To plan and render moving heads and the RGB/pixel display from one macro arc, use the
additive combined command:

```bash
uv run twinklr show \
  --audio path/to/song.mp3 \
  --layout path/to/xlights_rgbeffects.xml \
  --fixture-config path/to/fixture_config.json \
  --config path/to/job_config.json \
  --out artifacts
```

`twinklr show` runs analysis, profile, lyrics, and macro planning once, then plans the
two backends in parallel and writes their effects into one sequence. The fixture
config's `xlights_group` must name one dedicated layout group whose active direct model
members exactly match every fixture's `xlights_model_name`. Missing, inactive, extra,
nested, or multiply-owned members fail before provider work. The existing
`twinklr run` and `twinklr display` commands remain the branch-only iteration paths.
Like `display`, `show` accepts `--fe-output-dir DIR` and an optional `--style NAME`.
Its effective recipe catalog layers tracked recipes, optional local extensions, then
FE-promoted recipes; an absent/empty catalog or planner/renderer ID mismatch fails
before provider work.

### Data-form moving-head templates

Moving-head templates can be supplied as strict JSON `TemplateDoc` files without
adding a Python module or reinstalling Twinklr. Builtins always load first. Duplicate
normalized ID, display-name, and explicit-alias collisions are rejected by default so
filesystem order cannot silently decide which choreography runs. An override can replace
only the exact incumbent template ID and cannot steal an unrelated alias; use
`--allow-template-overrides` only when replacement is deliberate.

To export the Python library as editable JSON or validate a template directory:

```bash
uv run twinklr template-export --out /tmp/mh-templates
uv run twinklr template-validate --template-dir /tmp/mh-templates
```

Then opt a run into that directory:

```bash
uv run twinklr run \
  --audio path/to/song.mp3 \
  --config path/to/job_config.json \
  --template-dir /tmp/mh-templates \
  --allow-template-overrides
```

A `physical_v2` template step may name the rig's presets (fixture config, above) instead
of hard-coding them, with `component_refs`; the legacy renderer refuses a step that
carries it, and it is left out of dumps when absent:

| Key | Meaning |
|---|---|
| `component_refs.position_id` | A position preset that supplies each start angle the step leaves unset. `movement.physical.start_pan_deg` and `start_tilt_deg` become optional; one set on the step (by the template or a template preset's patch) replaces the reference for that axis only. A step without a position reference must set both |
| `component_refs.attribute_preset_ids` | Attribute presets that supply each fixture's held shutter, color, gobo and dimmer level. The step's own `physical_shutter_state`, `physical_shutter` pulse, `physical_color`, `physical_gobo` or `dimmer.physical` replaces the reference for that channel only; two listed presets that both set a channel of one fixture are refused rather than one silently winning |

References resolve per fixture when the template compiles, both in the pre-planning dry
compile and in the render, and each cue records `component_provenance` in its metadata:
per channel, `step` or the referenced preset, the preset its fallback chain resolved to
and the SHA-256 of the entry used.

A `physical_v2` template step may spread phase across the rig's heads (chases, cascades,
mirrored wings) with `physical_distribution`, a list of distributions over the fixture
group's `topology` (fixture config, above). The legacy renderer refuses a step that
carries one, and an empty list is left out of dumps:

| Key | Meaning |
|---|---|
| `physical_distribution.domains` | The channels this distribution phases: `pan`, `tilt`, `dimmer` and `shutter` (color and gobo are held states with no phase). Two distributions of one step may not share a domain; a domain none lists keeps the step phase |
| `physical_distribution.block_size` | Default `1`. Consecutive heads (after folding) that share one slot |
| `physical_distribution.group_count` | Default none. Interleaves the blocks into this many slots (block number modulo the count) |
| `physical_distribution.wings` | `1` (default) or `2`. Two wings fold the ordered rig at its center, so heads mirrored about it share a phase, and negate the left wing's pan displacement (an odd center head gets none); a referenced or authored start aim is never mirrored. The sign comes from the distribution that owns `pan` |
| `physical_distribution.spread_cycles` | Default `0`, at least `0`. The phase span from the first slot to the last, both included, in cycles of each kernel's own period; taken at its exact decimal value |
| `physical_distribution.direction` | `forward` (default: slot 0 leads) or `reverse` |

A head's phase in a domain is the step phase minus its offset, so slot 0 leads and later
slots lag; `phase_origin_ms` and a pulse's own `phase_cycles` are unchanged. A lagging
head on a finite `linear` path holds its start pose until its phase reaches zero, and
a head reaches the terminal pose once its phase reaches one; a step that ends sooner
cuts a lagging head wherever its path has reached. A lagging pulse starts its step mid-cycle; as
for any phase shift, the intervals the step start and end cut are exempt from the
one-frame rule, and every other interval is checked at the head's own phase. Each cue
records its head's rank, offsets and pan sign as `phase_distribution` metadata, and the
trace lists them with the rig's canonical order.

A `physical_v2` step may move on a path about its base aim (its start angles or its
position reference, never both added) with `movement.physical.shape` `circle`,
`lissajous` (both periodic) or `sweep` (periodic: edge to edge and back each period;
finite: one way, then held). Each extent is that axis's maximum signed displacement of
the unrotated path, so a circle with pan extent 30 and tilt extent 10 is an ellipse ±30°
by ±10°. A circle starts at the aim plus its pan extent, a sweep at the aim minus it
(plus it, when a finite sweep is reversed) and a lissajous at the aim, so the first cue
of a path enters there. A sweep moves along pan, so its tilt extent must be zero unless
`rotation_deg` turns it (and its pan extent zero when turned a quarter turn). The legacy
renderer refuses these shapes, and the fields below are left out of dumps when absent:

| Key | Meaning |
|---|---|
| `movement.physical.lissajous_ratio` | `lissajous` only: pan and tilt cycles per period, positive integers, default `[1, 2]` (a figure eight) |
| `movement.physical.transform.rotation_deg` | Default `0`. Turns the path about the aim before each axis is scaled by its own extent, so a 90° turn moves a pan sweep onto tilt at the tilt extent. Turning a circle only shifts where it starts; a lissajous turned off a quarter turn can reach past its extents, by up to √2 times (about 1.24 times for 1:2 at 45°) |
| `movement.physical.transform.reverse` | Default `false`. Runs the path backwards (a circle clockwise instead of counter-clockwise, a finite sweep from the other edge); pulses are unchanged. Refused on a periodic sweep, which it would not change |
| `movement.physical.transform.phase_cycles` | Default `0`. Starts the path this many cycles into its travel, at its exact decimal value; pulses are unchanged |

A transform applies only to these three shapes; `hold`, `sine_pan`, `sine_tilt` and
`linear` keep their meaning. Each axis is evaluated at the head's phase in that axis's
domain, so a distribution meant to shift the whole path lists both `pan` and `tilt`;
a mirrored wing negates the pan component after rotation, reflecting the path. The exact
formulas are in `evaluate_physical_path` (`compile/physical.py`). Nothing is normalized
or closed: a path that leaves an axis's range, exceeds its travel speed or moves finer
than the head can follow at any frame is refused by the pre-planning dry compile, like
any other motion.

A `physical_v2` template may set `repeat.mode` to `ONCE`: its one cycle plays at its
nominal tempo and never repeats. Every step must declare finite motion
(`movement.physical.mode` `finite`) that completes within the step (`period_beats`,
less the share a positive `transform.phase_cycles` skips, or more for a negative one), and no
dimmer or shutter pulse with a duty cycle below 1, so a head reaches its terminal pose
by the end of the cycle. With `remainder_policy` `HOLD_LAST_POSE`, the cues that close
the cycle run on to the section end as one cue each: a head holds its terminal pose and
states there (lit when the step is), and a head lagging by its phase distribution
completes its move first. With `TRUNCATE`, nothing follows the cycle: a lagging head
that has not finished is cut where it is, and every head is held dark until its next
cue. `FADE_OUT` is refused. The pre-planning dry compile checks a `ONCE` template at
every bar a section could start on, since its single cycle meets that bar's tempo.
A section shorter than the cycle fails the render, after planning, because the gate
cannot know the planner's section lengths; a cycle cut by the end of the song or of the
detected beats is cut without error. The legacy renderer refuses `ONCE`; the planner
sees template IDs and descriptions, never a repeat mode.

A `physical_v2` step with a period may light only part of its movement with
`physical_visibility`, and a `physical_v2` template may flick a wheel to another state
for part of every cycle with `physical_overlays`. Neither moves a head in the dark
itself: the dark spans they leave between cues are repositioned by the same pass as
every other gap, which darkens the fixture, turns wheels, travels and settles before
the next reveal. The legacy renderer refuses both, and both are left out of dumps when
absent:

| Key | Meaning |
|---|---|
| `physical_visibility.visible_phase_start` | Where in each movement period the step lights, as a fraction from `0` (inclusive) up to `visible_phase_end`. Read at the head's own movement phase, its pan/tilt distribution offset included, so a lagging head's window lags with its path. The window is in phase before the path's own `transform`, so a transform changes which arc is lit, not when: `reverse` on a finite sweep lit over `0`-`0.5` lights its travel from the far edge to the aim. A periodic movement lights in every period. A finite movement's phase clamps to `0`-`1` as its motion does, so a window from `0` also lights a lagging head holding its start. A frame is lit when its start lies in the window |
| `physical_visibility.visible_phase_end` | Where the lit window ends, at most `1`. On a finite movement a window ending at `1` includes the terminal pose, so the head stays lit at `level` through any hold after the move (a `ONCE` `HOLD_LAST_POSE` remainder included) and takes no `release_beats`; one ending before `1` leaves the hold dark. A lit window or a dark interval inside a step shorter than one 20 ms frame is refused, never dropped |
| `physical_visibility.attack_beats` | Default `0`. The dimmer rises linearly from 0 over this many beats from the window start |
| `physical_visibility.release_beats` | Default `0`. The dimmer falls linearly to 0 over this many beats before the window end. Attack and release together must fit inside the window |
| `physical_visibility.level` | Default `1`. The lit dimmer level. The envelope replaces the dimmer: the step may not set `dimmer.physical` or a `physical_shutter` pulse, and it replaces a dimmer level an attribute preset supplies. A profile without a dimmer axis needs zero ramps and level `1` |
| `physical_overlays.start_beats` | Where the overlay starts, in beats from the start of each cycle; it may span a step boundary |
| `physical_overlays.end_beats` | Where it ends, within the cycle. Overlays on one wheel may not overlap; overlays on the color and gobo wheels may, each splitting what the other leaves |
| `physical_overlays.mask_beats` | The dark time after the start and before the end while the wheel turns and settles. A mask too short for the wheel fails the render like any reposition that does not fit, and a step's declared `physical_reposition_fallback` applies |
| `physical_overlays.channel` | `color` or `gobo` |
| `physical_overlays.state` | The state to show, named as each fixture's profile names it; never a byte |
| `physical_overlays.attribute_preset_id` | Instead of `state`: a rig attribute preset whose entry for each fixture (along its fallback chain) names that fixture's state on `channel` |
| `physical_overlays.release` | `resume_base`, the only value: after the end the head shows whichever step is in force then, so a step change during the overlay is what resumes |

An overlay applies in every cycle the section plays as authored, including the head of a
cycle a `TRUNCATE` remainder plays, but not over a `HOLD_LAST_POSE` remainder, which
holds the cycle's closing step from a new start where no authored cycle plays it. A cue
that already holds the overlay's state (its own, or the profile's default where it sets
none) is left whole, without masks, and records the channel under `overlay_unchanged` in
its metadata. An overlay that falls wholly inside an envelope's dark part changes
nothing, since there is no cue there to split.

The lit shutter is the step's own static `physical_shutter_state` (or a referenced
preset's), else the profile's `discrete.open_state`; a step with neither is refused.
Between overlay masks the head plays its steps' own cues with the wheel replaced, so a
change the steps themselves make inside the flick on another wheel is still refused,
and an overlay over a `PING_PONG` template is refused because every other cycle mirrors
its steps. Envelopes and overlays are applied in the compile both the pre-planning dry
compile and the render use, so the gate checks the same cues the render plays.

### Deterministic FSEQ comparison (CI-safe)

After xLights has rendered two `.fseq` files, compare them without launching xLights or
a graphical session:

```bash
uv run twinklr --fseqcmp baseline.fseq candidate.fseq
```

The command succeeds only when the files are byte-identical. On a mismatch it reports
the first changed byte, file sizes, and SHA-256 hashes, then exits non-zero. This is the
deterministic CI-tier check; it does not judge visual quality.

### Preview video export (LOCAL-ONLY)

Twinklr's xLights automation client can load a generated `.xsq`, render it, export the
House Preview video, and close the sequence. It requires a **windowed** xLights 2026.15
instance with its HTTP automation API enabled; headless xLights can render FSEQ but not
video previews. No preview export runs in CI.

The automation endpoint is unauthenticated by xLights. While it is enabled, any local
process can drive the application. Use it only on a trusted local machine, keep unsaved
work out of the target instance, and disable the endpoint when finished. The client never
enables, launches, quits, or exposes xLights on its own.

To run the smoke test after starting xLights and enabling its API:

```bash
TWINKLR_XLIGHTS_PREVIEW_SEQUENCE=/absolute/path/to/generated.xsq \\
  uv run pytest -m local_only -k preview -q
```

The test asserts that the returned video exists and is non-empty. This machine has not
yet performed that empirical check; it is an owner-local step.

### Live injection and section regeneration (LOCAL-ONLY)

With a sequence already open in windowed xLights, the live workflow reads the actual
model/group names, plans only against configured moving heads that really exist there,
and writes DMX effects to reserved layers starting at 99. Relative exporter layers are
preserved (for example, regular effects use 99 and transitions use 100), so effects that
the deterministic renderer separated are never flattened into overlaps. Differences
between the live layout and the
fixture config are printed; Twinklr never guesses channel mappings for unknown models.

```bash
uv run twinklr inject --audio song.mp3 --config job_config.json --dry-run
uv run twinklr inject --audio song.mp3 --config job_config.json
uv run twinklr regenerate chorus_2 --audio song.mp3 --config job_config.json
```

The dry run prints the exact `deleteEffect`/`addEffect` requests and writes nothing.
`regenerate` reuses cached audio/profile/lyrics/macro analysis, forces a fresh plan for
only the canonical section ID, and leaves other sections untouched. Twinklr tracks its
reserved-layer ownership in the song artifact directory, stops before touching an
unowned collision, and never saves the xLights sequence. Replacement is explicit:
owned effects for the named section are deleted before the new effects are added.

The xLights automation API has no documented authentication. Any local process can drive
the application while the port is enabled. Use a trusted machine, inspect the reserved
layer before saving, and disable the API when finished. Because xLights offers no
transaction and `addEffect` returns no ID, a timeout can be ambiguous; do not save, inspect
reserved layers starting at 99, then run the same command again. Preflight makes that
recovery idempotent.

### What the Pipeline Does

The `twinklr run` command executes the moving heads pipeline with these stages:

1. **Audio Analysis** (`audio`) — analyzes the audio file for tempo, beat grid, energy dynamics, section boundaries, and harmonic content.
2. **Audio Profiling** (`profile`) — LLM generates musical interpretation and creative guidance from the analysis.
3. **Lyrics Analysis** (`lyrics`) — conditional stage; runs only if lyrics are detected. Produces narrative and thematic context.
4. **Macro Planning** (`macro`) — LLM generates a high-level choreography strategy across all display groups.
5. **Moving Head Planning** (`moving_heads`) — multi-agent loop (planner -> deterministic heuristics -> judge) generates a `ChoreographyPlan` with template selections and parameters per section.
6. **Rendering** (`render`) — compiles the plan into DMX values, curve data, and fixture segments, then writes the delivery: a fresh `.xsq`, one `.xtiming` per timing track, and an `.xmap`.

_Source: `packages/twinklr/core/pipeline/definitions/moving_heads.py` and `common.py`_

### Display Graph

The graph describes what each planner may address. `twinklr run` builds the moving-head
group from your fixture config at the declared fixture count. `twinklr display` builds
RGB/pixel targets from your `xlights_rgbeffects.xml`: explicit model groups are preserved,
and active models not assigned to a group become individual targets. The adapter derives
model mappings, pixel fractions, and approximate display positions from the layout.

The old hardcoded three-group yard described the author's display and is retired from the
shipped path.

_Source: `packages/twinklr/cli/main.py` and
`packages/twinklr/core/formats/xlights/layout/choreography.py`_

---

## Understanding Outputs

### Output Directory Structure

Artifacts are written to `<output_dir>/<song_name>/`:

- **`<song_name>_twinklr_mh.xsq`** — a self-contained xLights sequence carrying Twinklr's
  effects. It names only Twinklr's own models and the audio file it was choreographed
  against; it is a donor sequence to import from, not a show file to open as your show.
- **`<song_name>_twinklr_mh.<track>.xtiming`** — one file per timing track Twinklr built
  from the audio (`audiosections`, `beats`, `bars`, and `lyrics`/`phonemes` when available).
- **`<song_name>_twinklr_mh.xmap`** — mapping hints naming every model the `.xsq` emitted,
  proposed against a layout model of the same name.
- **`<song_name>_twinklr_display.xsq`** — the RGB/pixel donor sequence emitted by
  `twinklr display`.
- **`<song_name>_twinklr_display.xsq.trace.json`** — deterministic placement-level
  display render trace used by validation tooling.
- Stage artifacts and intermediate results (audio analysis data, profiles, plans)

### Using the Output

You **import** these into your own sequence rather than opening Twinklr's file as your show.

1. Open your sequence in **xLights**.
2. Import the effects from the generated `.xsq` as a donor sequence, using the shipped
   `.xmap` to pre-fill the model mapping. Your layout must already contain models the
   mapping can point at — Twinklr names them from your fixture config's
   `xlights_model_name` values.
3. The imported effects contain value curves for each moving head across all mapped DMX
   channels (pan, tilt, dimmer, shutter, color, gobo).
4. Import the `.xtiming` files to get Twinklr's timing tracks. These need **no mapping at
   all** — they import standalone into any sequence, so they are useful even if you take
   none of the effects.
5. Refine anything you kept, in xLights, as usual.

Whether a bare `.xsq` imports without an accompanying `xlights_rgbeffects.xml` is being
verified empirically; the `.xtiming` path has no such question.

---

## Testing Audio Analysis

To test just the audio analysis pipeline on a file (without running the full LLM pipeline):

```bash
make test-audio FILE=path/to/song.mp3
```

For WhisperX transcription testing:

```bash
make test-audio-whisperx FILE=path/to/song.mp3
```

For full audio pipeline with all enhancements enabled:

```bash
make test-audio-all FILE=path/to/song.mp3
```

_Source: `Makefile` targets `test-audio`, `test-audio-whisperx`, `test-audio-all`_

---

## Troubleshooting

### OpenAI provider requires an API key

For the default cloud provider, export `OPENAI_API_KEY='your-key-here'` or set
`llm_api_key` in `config.json`. A local Ollama configuration needs neither.

### `Config file not found`

Config files (`config.json`, `job_config.json`, `fixture_config.json`) are not included in the repo. Create them with the documented defaults above. The `fixture_config_path` in `job_config.json` is resolved relative to the job config file's directory.

### `uv is not installed`

Install uv from [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv). All `make` targets check for uv before proceeding.

### Pipeline fails at a specific stage

The pipeline uses a fail-fast policy. Check the console output for the failed stage name and error message. Common causes:
- **Audio stage**: unsupported audio format or corrupt file
- **Agent stages**: provider refusal/error, configured output limit, or timeout
- **Render stage**: invalid fixture config or missing template XSQ file

Agent responses are cached when `agent.agent_cache.enabled` is true (the default).
Re-running after fixing a failure can reuse compatible cached responses. The separate
`write_checkpoint` field controls only the final moving-head plan written for
`twinklr eval-report`; it does not enable or disable stage caching.

### Resetting caches

```bash
make clean-cache    # Clear audio cache, step cache, and logs
make reset          # Also clears feature store, profiles, and FE output
```

_Source: `Makefile` targets `clean-cache`, `reset`_
