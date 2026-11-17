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
| `write_checkpoint` | `true` | Writes the final moving-head plan for `twinklr eval-report`; a physical render adds its record to it ([Evaluation report](#evaluation-report-twinklr-eval-report)); it does not control stage cache reuse | `job.write_checkpoint` |
| `transitions.enabled` | `true` | Enables section transition planning | `job.transitions.enabled` |
| `transitions.default_duration_bars` | `0.5` | Sets the fallback transition length | `job.transitions.default_duration_bars` |
| `timeline_tracks.sections` | `true` | Includes or omits section timing markers | `job.timeline_tracks.sections` |
| `moving_heads.mode` | `"legacy_v1"` | Selects the moving-head renderer. `"physical_v2"` needs schema `"3.1"`, a `physical_profile` on every fixture and a usable `initial_states` entry for each; a job missing any of them is refused when its fixtures load, naming each fixture and what to add, before any analysis or provider request. The planner is offered only templates that carry explicit physical data: none of the builtins does, but a `physical_v2` run also loads the seven physical families in `catalog/templates/moving_heads_physical` (fly-out and fly-in cascades, target orbit, mirror wings, finite snap hold, masked wheel flick and the synthetic zoom pilot, zoom wave; that directory's README gives each one's motion and needs: the cascades, mirror wings and zoom wave need a rig topology, the flick needs a `flick` attribute preset that sets `color`, the zoom wave needs a `zoom` axis on every head's profile, and every family but the cascades needs the profile to declare a shutter state named exactly `open`; the families are authored in 4/4, where their 2-bar cycles hold whole movement periods; in any meter a repeating cycle that would end mid-period, or before an overlay ends, grows to the smallest whole number of bars that holds them (the rule, which applies in 4/4 too and so to `--template-dir` templates, is under the template keys below), so every family plays in 2/4, 3/4, 6/8 and other meters, over more bars per cycle (that README lists them; physical renderer revision 2); under a topology derived from `position_index`, removing the highest-index head can change the other heads' phases, which a declared `topology` avoids), and a run with none is refused before analysis; right after audio analysis, before any planning, every offered template is dry-compiled on the rig over the whole song (with no preset and with each preset it declares), and the dark repositioning between its own cues is planned from `initial_states` under `reposition_fallback`, so a template whose cues cannot be repositioned between is refused, as is one whose pan, tilt or zoom changes faster than the head can follow (it would fall more than one DMX step behind, which on an 8-bit axis at low speed is reached by sub-degree wobble), and a song whose detected beats cannot establish a musical phase (fewer than two, or beats outside the song) is refused, because the renderer never infers tempo. A family is offered through the first of its variants that passes these checks, its base (no preset) and then each preset it declares, in order: that is its effective variant on this rig and song, which a section naming no preset renders, and so does a section naming a preset that was not admitted (with a warning naming why); each failing variant, the base included, is logged and recorded in the trace's `admission_preset_exclusions` (`preset_id` null for the base), and each effective variant other than the base in `admission_effective_presets`. A family none of whose variants passes is left out of the planner's offer instead, every reason logged and recorded in `admission_exclusions`; the run is refused only when no template remains, and a `--template-dir` template that fails, with or without a preset, still refuses it (it is not laddered). The check takes longer in 3/4 than in 4/4 (and in other meters whose grown cycles span more bars), because a longer cycle is checked at more alignments to the bars. The check also logs each offered template's worst-case section-entry dip: how many beats, at the song's shortest beat, a head may stay dark entering one of its sections. Silence or a fade at either end of the song is not refused: the renderer covers only the detected beats plus one beat interval beyond the first and last (or up to the song's edge when that is nearer), holds every fixture dark outside that covered span, drops a cue that would start outside it and cuts one that runs past its end; the trace records the covered span, the longest gap between detected beats and each dropped cue. A long gap between two detected beats mid-song is one long beat and stays lit. A preset id the template does not declare likewise renders the effective variant, with a warning naming why. Each head enters each section on its own: where its first cues can be played as authored after its previous cue (or the initial state) it starts as authored; otherwise it stays dark for whole beats, long enough for any repositioning into it, then cuts in its cues where they would be, never inside a shutter state too short to take effect (a cue wholly inside that window is dropped and recorded). A head missing from the rig therefore changes no other head's output. The trace's `entry_windows` lists each section's window per fixture, and every `dropped_cues` record gives its `reason`. It writes complete 20 ms frames of constant DMX effects over model-relative channels 1-48, plans dark repositioning between cues instead of applying `transitions`, does not apply planner intent, and records its render identity and evidence in the `.xsq.trace.json`. Any refusal writes no file. `twinklr show` renders it too, resting the heads dark where the show's coordination does ([CLI command](#cli-command)); `inject` and `regenerate` inject the physical render's effects, and `regenerate` re-renders the whole song (see Live injection and section regeneration below); `run`, `show`, `inject` and `regenerate` each record the mode and their render in the plan checkpoint, which `eval-report` re-renders ([Evaluation report](#evaluation-report-twinklr-eval-report)); `twinklr display` renders no moving heads and ignores it | `job.moving_heads.mode` |
| `moving_heads.initial_states` | `{}` | Run-supplied time-zero state per fixture id (unwrapped `pan_deg`/`tilt_deg`, `zoom_deg` exactly when the fixture's profile declares a `zoom` axis (left out of dumps when absent), `dimmer`, `discrete_states`, and explicit `settled`/`dark` evidence) for the physical renderer. A fixture without an entry has an unknown initial state. Under `physical_v2` every fixture needs a settled entry its profile accepts, and an entry must name a fixture of the rig; otherwise the job is refused when its fixtures load, and for each fixture without an entry the refusal prints the entry its profile's default bytes give, ready to paste after checking it ([Minimal physical profile](#minimal-physical-profile)). Enters render identity and the render trace, but not the planner's session or cache, so editing it re-renders without re-planning | `job.moving_heads.initial_states` |
| `moving_heads.reposition_fallback` | `"error"` | Applies only to physical (`physical_v2`) output: what the render does with a cue whose dark repositioning cannot be planned. `"error"` refuses the render (before planning when the gate finds it inside a template); `"preserve_aim"` plays the cue at the aim the head holds; `"drop_accent"` keeps the cue dark and plans the next cue from that aim. A fallback applies only to cues of template steps that declare the same `physical_reposition_fallback`, and never covers an unknown initial state, unknown visibility latency, a missing darkness guarantee or a lock; each substituted cue is listed in the trace. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.reposition_fallback` |
| `moving_heads.on_unplayable` | `"dark"` | Applies only to physical (`physical_v2`) output: what the render does with a cue the plan placed where it cannot play honestly, after any `reposition_fallback` the cue and the job both declare. `"dark"` leaves the fixture dark over that cue (it parks there as over any gap) and the render continues: a cue whose dark repositioning still cannot be planned (dropping one can leave the next one too little time, so this repeats until every remaining cue plans), a cue a shutter state too short to take effect lies in (such as a last cue cut to one frame at the song end), a step a fixture cannot play at this section's placement (rate, bounds, pulse or lit-window width) although it plays from bar 1 over the song, and every cue of a section too short for a `ONCE` cycle. Each is listed in the trace's `dropped_cues` with `reason` `"unplayable"`, its `code` and `detail`, the render record carries `unplayable_totals` per code, and the run logs one warning with the counts, which `twinklr run` prints. Never covers an unknown initial state or a lock, and never applies to what is refused before planning: a template that cannot play from bar 1 over the song is still refused, at the gate or at render. `"error"` refuses the render instead. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.on_unplayable` |
| `moving_heads.max_effects` | `1000000` | Applies only to physical (`physical_v2`) output, never to legacy output: the most DMX effects one render may emit after identical adjacent 20 ms frames are merged. More fails the render with `output_budget_exceeded`; frames are never dropped to fit. Must be positive; a non-default value enters render identity. `inject` and `regenerate` have their own, lower bound of 50,000 effects (see Live injection and section regeneration) | `job.moving_heads.max_effects` |
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

A fixture's `config` may also carry an optional `physical_profile` for the opt-in `physical_v2` renderer; in the `base_config` form, `base_config.physical_profile` applies to every fixture and a fixture's `config_overrides.physical_profile` replaces it for that fixture. An invalid profile fails when the fixture file loads, naming the fixture (or `base_config`), the field and the [minimal example](#minimal-physical-profile). The `physical_v2` renderer requires one on every fixture and renders from it alone; the legacy renderer ignores it and refuses a physical channel value rather than exporting nothing. Physical output is written to the fixture's own xLights model, which must be a single-color DMX model with at least `footprint` channels; `twinklr run --layout` checks this before analysis (and records the layout's content hash in the trace), and without a layout the check is skipped with a warning. It declares the fixture explicitly rather than inferring anything from the legacy fields above: `profile_id`, `provenance` (`synthetic`, `manufacturer` or `measured`), the model-relative channel `footprint` (at most 48, the xLights DMX effect's limit) with a default byte for every channel `1..footprint` (an unlisted one is filled, below), continuous `axes` (`pan`/`tilt` in degrees, `dimmer` normalized, and an optional `zoom` beam angle in degrees) with calibrated `physical_min`/`physical_max`, an optional narrower `allowed_min`/`allowed_max` operating window that does not rescale the mapping, coarse/fine offsets, optional `dmx_min`/`dmx_max` for an axis whose calibrated range maps over only part of its DMX word (default `0` and the full word, 255 or 65535 with a fine offset, and left out of dumps at those defaults; a value encodes to `dmx_min` plus its share of the range times `dmx_max - dmx_min`, rounded half up), and inversion, which reflects the word within `dmx_min`..`dmx_max`, `discrete` shutter/color/gobo channels whose named states each select one explicit byte inside a declared, non-overlapping range, and `visibility` (what extinguishes output, and close/open latency). A profile cannot claim darkness it cannot produce: the shutter's `open_state` cannot extinguish, and `dimmer_zero_extinguishes` needs a dimmer axis calibrated from `0` whose operating window admits `0`. Normalized axes lie within `0..1`. Unknown speed, latency and settle times stay `null`; they are never filled in. A profile does not say where a fixture is now; that is `moving_heads.initial_states` in the job config. The retired `capabilities` and `movement_speed` keys stay ignored.

#### Minimal physical profile

A profile states only what cannot be known: which channel carries which function, the calibrated range and inversion of each axis, the byte of each wheel and shutter state, and the timings. Everything else is filled when the fixture file loads, so the profile is exactly the explicit one it stands for (it dumps as that), and the render trace lists, under each `fixtures` entry's `defaulted`, every value that was filled; the key is left out when nothing was. An inference that could be ambiguous is refused, naming what to state. A synthetic 16-channel spot (color 1, shutter 2, dimmer 3, gobo 4, 16-bit pan 11/12 and tilt 13/14, the rest spare), four identical heads sharing one profile in `base_config`:

```json
{
  "group_id": "MOVING_HEADS",
  "base_config": {
    "dmx_mapping": {"pan_channel": 11, "tilt_channel": 13, "dimmer_channel": 3},
    "physical_profile": {
      "profile_id": "example_spot_16ch",
      "provenance": "synthetic",
      "footprint": 16,
      "axes": {
        "pan": {"physical_min": -270.0, "physical_max": 270.0, "allowed_min": -170.0, "allowed_max": 170.0,
                "coarse_offset": 11, "fine_offset": 12,
                "travel_speed_per_s": 150.0, "latency_ms": 20, "settle_ms": 60},
        "tilt": {"physical_min": -30.0, "physical_max": 240.0, "allowed_min": -20.0, "allowed_max": 110.0,
                 "coarse_offset": 13, "fine_offset": 14,
                 "travel_speed_per_s": 150.0, "latency_ms": 20, "settle_ms": 60},
        "dimmer": {"coarse_offset": 3}
      },
      "discrete": {
        "shutter": {"offset": 2, "settle_ms": 0,
                    "states": {"closed": {"value": 0}, "open": {"value": 255}}},
        "color": {"offset": 1, "settle_ms": 150,
                  "states": {"white": {"value": 0}, "red": {"value": 10}, "green": {"value": 20},
                             "blue": {"value": 30}, "amber": {"value": 40}}},
        "gobo": {"offset": 4, "settle_ms": 150,
                 "states": {"open": {"value": 0}, "dots": {"value": 10}, "star": {"value": 20}}}
      },
      "visibility": {"close_latency_ms": 20, "open_latency_ms": 20}
    }
  },
  "fixtures": [
    {"fixture_id": "MH1", "xlights_model_name": "Dmx MH1", "position": {"position_index": 1}},
    {"fixture_id": "MH2", "xlights_model_name": "Dmx MH2", "position": {"position_index": 2}},
    {"fixture_id": "MH3", "xlights_model_name": "Dmx MH3", "position": {"position_index": 3}},
    {"fixture_id": "MH4", "xlights_model_name": "Dmx MH4", "position": {"position_index": 4}}
  ]
}
```

With it the group needs no `topology`. Until the moving-head cutover removes the legacy renderer, a fixture still needs a legacy `dmx_mapping` (`pan_channel`, `tilt_channel` and `dimmer_channel`); the physical renderer never reads it. A fixture's `config_overrides.physical_profile` replaces the shared profile for that fixture.

| Profile value | Left out |
|---|---|
| `profile_id`, `provenance`, `footprint` | Required |
| `axes.<axis>.coarse_offset`, `fine_offset`; `discrete.<channel>.offset` and each state's `value` | Required: which channel and byte carries what |
| `axes.pan`, `tilt`, `zoom`: `physical_min`, `physical_max` | Required: the calibration. `allowed_min`/`allowed_max`, `inverted` and `dmx_min`/`dmx_max` keep their defaults (the calibrated range, not inverted, the full word) |
| `axes.<axis>.unit` | Implied by the axis: `degree` for pan, tilt and zoom, `normalized` for the dimmer. A different unit is refused |
| `axes.dimmer.physical_min`, `physical_max` | `0` and `1` |
| `defaults.<offset>` of pan, tilt or dimmer | The word that encodes `0`, inversion applied: home for pan and tilt, dark for the dimmer. Refused when `0` is outside the axis' allowed window; list them then. A listed coarse byte leaves an unlisted fine byte `0` |
| `defaults.<offset>` of a discrete channel | Its `default_state`'s byte |
| any other `defaults.<offset>`, zoom included | `0`; refused for a zoom whose words do not admit it. A channel the profile does not declare is still sent on every frame: if it is a function channel (pan/tilt speed, a second shutter or strobe, a mode or reset channel), `0` selects whatever its byte 0 means on that fixture. List the resting byte in `defaults` whenever it is not `0`, and state `travel_speed_per_s` as the speed the head moves at with the byte its speed channel carries |
| a state's `range_min`, `range_max` | Its `value` |
| a state's `settle_ms` | Its channel's `settle_ms` (left out of dumps: the states carry it). Without either it stays unknown |
| `discrete.<channel>.default_state` | The state its listed default byte selects (a byte that selects none is refused); with neither, the state that selects byte `0`, refused when none does |
| `discrete.shutter.closed_state`, `open_state` | The shutter state named exactly `closed` / `open`; otherwise none. An explicit `null` is kept. Other wheels' open and closed states are never read and stay as given |
| `visibility.dimmer_zero_extinguishes` | `true` when the dimmer is calibrated from `0` and its allowed window admits `0`, else `false` |
| `visibility.extinguishing_shutter_states` | The shutter's closed state, else none |
| `travel_speed_per_s`, `latency_ms`, `settle_ms`, `close_latency_ms`, `open_latency_ms` | Never defaulted: every timing must be stated. Unknown stays `null`, and a template whose motion or reveal needs it is excluded or refused, naming the term. A guessed time that is too fast would let the renderer reveal a head that is still moving or not yet dark, so motion would be dishonest |

`moving_heads.initial_states` is never defaulted: a fixture without an entry has an unknown initial state and the run is refused before planning, because nothing establishes where a head is when the sequence starts (a previous sequence leaves it wherever it last aimed). The refusal lists every fixture without an entry and prints, as one object ready to paste into `moving_heads.initial_states`, the entry each profile's default bytes give: each axis at the value they encode, each discrete channel in its `default_state`, `settled`, and `dark` exactly when that dimmer level or shutter state extinguishes it. Pasting it asserts that each head really rests there, settled and dark as stated, when the sequence starts.

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

Under `moving_heads.mode` `"physical_v2"`, `show` renders the moving heads on the
physical renderer, with the same prerequisites and checks as `twinklr run`: the rig is
refused when its fixtures load if a fixture lacks a profile or initial state, the
physical family catalog is loaded, and the render preflight gate runs right after
audio analysis, before any planner, with every fixture's model checked against the
`--layout` (always given to `show`). Where the macro plan's coordination rests the
moving heads inside a macro section (the other team's call/response turns, sequenced
or ripple steps on other targets), every head is held dark. Those windows are computed
inside the macro sections only (time outside every macro section is not rested),
and snapped outward to the 20 ms frame grid. On a rig whose heads go dark through the
shutter (no dimmer whose zero extinguishes), each window is lengthened to the closed
state's close latency plus settle, and windows leaving a head lit between them for
less than the open latency plus the lit states' settle are merged; any rig is relit
for at least two frames. The rig's slowest profile sets both. The trace lists the
windows so lengthened and merged as `dark_spans`. A cue running through one keeps
playing its own authored path there, commanded dark through the profile's darkness
(the dimmer at zero when that extinguishes, else the closed shutter), planned before
section entry and repositioning, so the head is where the music puts it when the
window ends and needs no re-entry; through the shutter, a lit remainder of the cue
before or after a window too short for the shutter to open is kept dark too. A
different cue after a window is reached as it would be without the window. Outside
the windows (and those remainders) every lit frame is the one `twinklr run` renders
for the same plan and none of its lit frames is lost. On a shutter-darkened rig, a cue
whose own shutter changes fall closer to a window's edge than its shutter needs can
still be kept dark (`unplayable`), or refuse the render under `on_unplayable`
`"error"`. Dark frames may differ from `twinklr run`'s: a
transaction after a window can start moving as soon as the head is dark, and a
section entry window inside a window can reposition the head there. The macro
palette and focal role are not projected onto the heads, since the physical renderer
applies no planner intensity or colour; the trace's diagnostics say so per section.
`max_effects` counts the moving heads' DMX effects (one per constant frame run) and
`max_xsq_bytes` the whole combined `.xsq`, display effects included; both are checked
before any file is written, the `.xsq` and its `.xsq.trace.json` are published
together, and the trace carries the physical render record (`render`) as `twinklr
run`'s does. Show metrics read the moving heads of a physical trace as onsets: the
frame runs of a cue merge into one, and dark transactions, parks and runs inside a
dark window are left out.

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

A `physical_v2` step may set the beam angle on a fixture's `zoom` axis with
`physical_zoom`; the legacy renderer refuses a step that carries it, and it is left out
of dumps when absent:

| Key | Meaning |
|---|---|
| `physical_zoom.shape` | `hold` keeps `start_deg` through the step; `sine` adds `extent_deg × sin(2π·phase)` at the step's movement phase (its `movement.physical.period_beats`, at the head's pan distribution offset), so a sine needs a periodic movement |
| `physical_zoom.start_deg` | The beam angle, in the degrees of the profile's `zoom` axis |
| `physical_zoom.extent_deg` | Default `0`. The sine's amplitude; a hold takes none and a sine needs one |
| `physical_zoom.if_unsupported` | `error` (default): a fixture whose profile declares no `zoom` axis refuses the step, so the pre-planning dry compile leaves a catalog family that needs one out on that rig. `omit_optional_zoom`: the step plays there without its zoom, and the trace's `omitted_optional` lists each such cue |

On a profile with a `zoom` axis every cue holds a zoom: a step without `physical_zoom`
holds the profile's default byte, as an unauthored channel would. The zoom is a pose
axis like pan and tilt: the dry compile refuses one faster than its
`travel_speed_per_s`, and between cues it is held, never left to its default byte, moves
only in the dark and settles (`latency_ms`, `settle_ms`) before any reveal. Only this
one optical axis exists; focus, iris, prism and gobo rotation do not.

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

A repeating (`JOINER` or `PING_PONG`) `physical_v2` cycle restarts its steps' motion
and pulses at every cycle, so in every meter, 4/4 included, the physical compile grows
a cycle that would cut them: when every loop step starts at the cycle start and spans
the whole cycle, and the cycle's length in beats at the song's meter is not a whole
number of each step's periodic `movement.physical.period_beats` and of each dimmer or
shutter pulse period with a duty cycle below 1, or ends before a `physical_overlays`
entry ends, the cycle and its loop steps grow to the smallest whole number of bars, no
fewer than authored, that holds them all (an overlay still plays once per cycle). A
cycle that already holds them, a `ONCE` cycle and a cycle whose loop steps do not each
span it are left as authored. A cycle that would need more than 8 bars is refused,
naming the bars it would need. So a `--template-dir` template's cycle can grow in 4/4
too, for example a one-bar cycle of a 3-beat period to 3 bars; the pre-planning gate
and the render play the grown cycle alike. Each step instance starts on the 20 ms frame
nearest its musical start; a step's instances that follow one another without a gap,
each starting whole periods after the first (as a step spanning its cycle does), continue
the first one's musical phase rather than restarting at their own frame, so where one
cue ends the next begins at the same pose. A finite movement restarts at every
instance by design.

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
| `physical_overlays.end_beats` | Where it ends, in beats from the start of each cycle; a cycle whose loop steps each span it grows to whole bars that hold it (above), and one whose steps do not is refused if it ends first. Overlays on one wheel may not overlap; overlays on the color and gobo wheels may, each splitting what the other leaves |
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
only the canonical section ID, and, for legacy output, leaves other sections untouched (a
physical job re-renders the whole song; see below). Twinklr tracks its
reserved-layer ownership in the song artifact directory, stops before touching an
unowned collision, and never saves the xLights sequence. Replacement is explicit:
owned effects for the named section are deleted before the new effects are added.

The xLights automation API has no documented authentication. Any local process can drive
the application while the port is enabled. Use a trusted machine, inspect the reserved
layer before saving, and disable the API when finished. Because xLights offers no
transaction and `addEffect` returns no ID, a timeout can be ambiguous; do not save, inspect
reserved layers starting at 99, then run the same command again. Preflight makes that
recovery idempotent, as long as xLights reports each effect back exactly as Twinklr sent
it, which has not been verified against a running xLights.

#### Physical moving heads (`moving_heads.mode = "physical_v2"`)

What differs from the description above for a physical job:

- **What is injected.** `inject` renders the moving heads as `twinklr run` does, with the
  same pre-planning check, but on the rig as reconciled with the live layout (fixtures
  whose models the open layout lacks are left out; one that `moving_heads.initial_states`
  names is refused with the fixture and model named). It writes the same `.xsq` delivery
  to the artifact directory and injects that `.xsq`'s effects: one constant DMX effect per
  merged frame run, on each fixture's own model, all on layer 99, with the same settings
  and frame-aligned times. Only effects are injected: the section and analysis timing
  tracks are not; import the `.xtiming` files if you want them. `inject` and
  `regenerate` plan and render the moving heads on their own, without a show's
  coordination, so they never inject a `twinklr show` render; to use one, import the
  show's `.xsq` instead.
- **Replacement.** Every Twinklr-owned moving-head effect in the sequence is replaced;
  effects identical to what is already there are left in place, so injecting the same
  render twice writes nothing (it still reads every owned effect once). The run's render
  fingerprint is printed. After a complete (not dry-run) injection Twinklr records, in
  `.twinklr-live-plans.json` beside the ownership manifest, the plan now in that sequence
  and digests of the owned effects, the audio, the job config and the live rig.
- **`regenerate <section>` re-renders the whole song.** It re-plans only that section, as
  for legacy output, then renders the moving heads for the **whole song** from the
  recorded plan of the effects already injected, with that section's plan replaced and
  every other section's plan unchanged. A physical render plans each head's dark
  repositioning across section edges, so one section's effects cannot be swapped in on
  their own, and other sections' effects can change near the regenerated one; all of
  Twinklr's moving-head effects are replaced, and only those that changed are deleted and
  added. The re-plan must be one section over the bars the recorded plan gives it.
- **When `regenerate` refuses.** Before any planning request: no plan is recorded for
  the open sequence (no earlier `inject`, or only a dry run); the recorded plan no longer
  describes it (Twinklr's effects in the sequence changed since, for example after a
  partial or interrupted inject, or the audio, the job config or the rig differs; any job
  edit counts, planner settings included); or, in the pre-planning check right after
  audio analysis, a kept section names a template or preset that check did not admit.
  After planning but before anything is written: the re-plan is not one section over the
  bars the recorded plan gives it, or overlaps another section; or another sequence is
  open by the time the effects would be written. In each case run `twinklr inject` first.
  An unreadable `.twinklr-live-plans.json` is named with what to do (delete it, then
  `inject`); an `inject` that cannot record its plan reports the injection complete and
  the plan unrecorded.
- **Interrupted runs.** Before its first write a command records, in the ownership
  manifest, every effect it may place (the ones Twinklr owns that it found in the
  sequence and the ones it is about to add), and any interruption it survives (an
  xLights failure, Ctrl-C, cancellation) records exactly what was confirmed. Even after a
  kill that leaves it no chance to record anything more, run the same command again
  without saving the sequence: it finishes the replacement, and drops recorded effects it
  does not find. A partially injected sequence is not what the recorded plan describes,
  so recover with `inject`, not `regenerate`. One consequence: an effect on layer 99 or
  above that exactly matches (model, layer, times, effect, settings, palette) one Twinklr
  placed or was about to place is treated as Twinklr's and may later be removed.
- **Dry run.** It prints the number of planned writes per model and operation and writes
  every one, as JSON lines, to `live-dry-run.jsonl` in the artifact directory.
- **Volume.** A physical render emits far more effects than legacy output, about
  20,000-30,000 on four heads for a three-minute song. xLights' automation API has no batch
  command, so each effect read, deleted or added is one request, sent one at a time;
  replacing a whole render costs about three requests per effect. A command that would add
  more than 50,000 effects is refused before anything is read; one that would delete more
  than 50,000 owned effects, after reading but before anything is written. At roughly
  6,000-10,000 effects a minute on four heads, expect four heads past about five minutes,
  or eight heads on most songs, to exceed it. Import the `.xsq` from `twinklr run` instead.
  How long xLights takes per request has not been measured, and none of this has been
  tried against a running xLights.

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
- **`checkpoints/plans/final.json`** — the moving-head plan and, for a physical job, its
  render record, which `twinklr eval-report` reads. `twinklr run`, `show` and `inject`
  (and `regenerate`) write this same path for a song, so the last command to run wins.

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

### Evaluation report (`twinklr eval-report`)

```bash
twinklr eval-report \
    --checkpoint <output_dir>/<song_name>/checkpoints/plans/final.json \
    --audio <song audio> --fixture fixture_config.json --out <report dir>
```

The report re-renders the run's moving-head plan and writes `report.json`, `report.md`
and per-channel plots under `plots/`; it writes no sequence file.

For a `physical_v2` job, every command that plans and renders the moving heads
(`twinklr run`, `show`, `inject`, `regenerate`) adds a `render` record to the plan
checkpoint once it has written its `.xsq`: the render fingerprint, the render policy, the beat
grid it rendered against, the pre-planning gate's result, the dark spans a show rested
the heads over (left out when there are none), the trace's input hashes (each fixture's
profile and model name, each template, the beat grid, the dark spans, the renderer and
encoder revisions) and the rendered rig's identity (a hash of the fixture group and of
each of its top-level fields, and whether the rig was reconciled with the live xLights
layout). The report re-renders the plan from that record, over the same dark spans,
with the physical family catalog loaded as `twinklr run` loads it, so each section
renders the variant the run rendered. The audio is analyzed only for the song's BPM and
structure. `--fixture` must be the run's fixture config. The re-render's fingerprint is
compared with the run's: a mismatch is reported as a `RENDER_FINGERPRINT_MISMATCH` error
naming each recorded input that differs (`mismatched_inputs`: a fixture, a field of the
rig, a template, the beat grid, the dark spans, a revision), and printed by the command;
the report then describes the re-render, not the delivered sequence. `inject` and
`regenerate` render on the fixture config as reconciled with the open layout, so where
that layout lacks a group the config names, no fixture config reproduces the
render: the mismatch says so and names the field that differs. A physical checkpoint
without a readable `render` record is refused before any analysis: the command that
planned it stopped before it delivered its moving-head render (an output budget refused
it, for one), or could not write the record (it logs a warning), and re-running that
command writes it; a record written
before the record carried the rig's identity is refused as malformed. So is a plan that
names a template neither built in nor in the physical catalog: `eval-report` has no
template directory option, so a plan using `--template-dir` templates cannot be
re-rendered. A report on a show's checkpoint states its dark spans (how many, and their
total time): the heads keep moving on their authored paths there, commanded dark, so
`lit_range` and `lit_rate` leave those frames out and every other figure counts them.

A physical report reads the encoded frames, so its values are what the sequence
commands. Each section is read over the frames its cues land on (its bounds quantized
to the 20 ms frame grid as cues are). For each section and plotted fixture (the first,
unless the evaluation config names roles or plots them all):

| Channel | Value | Statistics |
|---|---|---|
| `pan`, `tilt`, `zoom` (where the profile has the axis) | Degrees, from each DMX word with inversion undone | min, max, range, mean, std and `energy` (mean rate of change per second) over every frame, so including dark repositioning; `lit_range` and `lit_rate` over lit frames only (emitted intensity above 0), the motion an audience sees |
| `dimmer` | Emitted intensity: the dimmer's normalized value, or 0 where the shutter is in a state the profile declares extinguishing (1 without a dimmer axis) | min, max, range, mean, std, `energy` |

Each section also carries `render_facts`: from the trace, its entry windows (how long
each head stays dark entering it), the reposition transactions of cues starting in it
by status, the cues kept dark with their reason and the render diagnostics that name
it; from the frames, every head's largest step between two consecutive frames in each
channel (`lit_steps`; between two lit frames for pan, tilt and zoom) and, for each head
whose entry is `skipped` (it plays through the boundary instead of entering dark), the
change from its last lit frame before the section to the section's first frame
(`boundary_steps`). Each step carries what the head's configured travel speed allows
over it, plus one DMX word. Flags: `CUES_KEPT_DARK` counts kept-dark cues;
`SECTION_DARK_FOR_ENTRY` names a head whose entry window outlasts the section, which
renders it dark; `LIT_STEP_EXCEEDS_TRAVEL` names a lit step beyond the travel speed
plus one DMX word, decided exactly in DMX words (the renderer should never produce one);
each render diagnostic is a `RENDER_DIAGNOSTIC`. That bound is per frame on commanded
values, so it is necessary, not sufficient: it does not detect sustained overspeed of up
to one word per frame, nor a reveal before the head has finished travelling or settling.

The report's `physical` block holds both fingerprints, the gate's
`admission_exclusions`, `admission_preset_exclusions` and `admission_effective_presets`,
the `unplayable_totals`, and `not_reported`: each legacy metric a physical report leaves
out, and why. Those metrics are `null` in `report.json`: the clamp percentage (the
renderer refuses an out-of-range value instead of clamping it), the limited-range and
static-curve flags (they key on legacy curve types), loop continuity, the curve type,
handler, base position and static DMX, the physics check, template compliance (planner
modifiers are not applied) and section transitions, with their summary counts. What is
true instead: a repeating cycle spans whole periods and its gap-free repeats continue
its phase. A finite move restarts each repeat: dark, through a transaction, when the
restart needs more than one frame's travel; otherwise lit, as one step within the
travel speed (reported as the largest lit step); and a repeat for which neither fits is
kept dark. The renderer plans motion within each profile's travel speed, latency and
settle, and acceleration is modelled by nothing. A head that must reposition into a
section does so dark, in its entry window (entry `cut`) or before the section where its
bound fits there (entry `none`), while a `skipped` head plays through the boundary lit,
within its travel speed. The lit steps above report what the frames do.

A legacy (`legacy_v1`) checkpoint is reported as before: normalized curves sampled from
the segments, with those metrics.

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
