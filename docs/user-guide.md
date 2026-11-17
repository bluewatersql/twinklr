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

Job-specific settings. Loaded by `JobConfig` in `packages/twinklr/core/config/models.py`. Schema version 3.1 is the only one accepted and the default. A job naming `moving_heads.mode` or `transitions` (keys Twinklr no longer has) or `schema_version` `"3.0"` is refused when it loads, naming the key and what to do.

The same registry-backed subset policy applies here.

| JSON field | Default | Observable effect | Ledger path |
|---|---|---|---|
| `schema_version` | `"3.1"` | Declares the job schema; only `"3.1"` is accepted, other values fail validation | `job.schema_version` |
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
| `write_checkpoint` | `true` | Writes the final moving-head plan for `twinklr eval-report`; the render adds its record to it ([Evaluation report](#evaluation-report-twinklr-eval-report)); it does not control stage cache reuse | `job.write_checkpoint` |
| `timeline_tracks.sections` | `true` | Includes or omits section timing markers | `job.timeline_tracks.sections` |
| `moving_heads` | — | The moving-head render policy. The renderer needs a `physical_profile` on every fixture and a usable `initial_states` entry for each; a job missing any of them is refused when its fixtures load, naming each fixture and what to add, before any analysis or provider request. The planner is offered the family catalog and any `--template-dir` templates: every run loads the seven families in `catalog/templates/moving_heads` (fly-out and fly-in cascades, target orbit, mirror wings, finite snap hold, masked wheel flick and the synthetic zoom pilot, zoom wave; that directory's README gives each one's motion and needs: the cascades, mirror wings and zoom wave need a rig topology, the flick needs a `flick` attribute preset that sets `color`, the zoom wave needs a `zoom` axis on every head's profile, and every family but the cascades needs the profile to declare a shutter state named exactly `open`; the families are authored in 4/4, where their 2-bar cycles hold whole movement periods; in any meter a repeating cycle that would end mid-period, or before an overlay ends, grows to the smallest whole number of bars that holds them (the rule, which applies in 4/4 too and so to `--template-dir` templates, is under the template keys below), so every family plays in 2/4, 3/4, 6/8 and other meters, over more bars per cycle (that README lists them; renderer revision 2); under a topology derived from `position_index`, removing the highest-index head can change the other heads' phases, which a declared `topology` avoids), and a run with none is refused right after audio analysis, before any planning; then, still before any planning, every offered template is dry-compiled on the rig over the whole song (with no preset and with each preset it declares), and the dark repositioning between its own cues is planned from `initial_states` under `reposition_fallback`, so a template whose cues cannot be repositioned between is refused, as is one whose pan, tilt or zoom changes faster than the head can follow (it would fall more than one DMX step behind, which on an 8-bit axis at low speed is reached by sub-degree wobble), and a song whose detected beats cannot establish a musical phase (fewer than two, or beats outside the song) is refused, because the renderer never infers tempo. A family is offered through the first of its variants that passes these checks, its base (no preset) and then each preset it declares, in order: that is its effective variant on this rig and song, which a section naming no preset renders, and so does a section naming a preset that was not admitted (with a warning naming why); each failing variant, the base included, is logged and recorded in the trace's `admission_preset_exclusions` (`preset_id` null for the base), and each effective variant other than the base in `admission_effective_presets`. A family none of whose variants passes is left out of the planner's offer instead, every reason logged and recorded in `admission_exclusions`; the run is refused only when no template remains, and a `--template-dir` template that fails, with or without a preset, still refuses it (it is not laddered). The check takes longer in 3/4 than in 4/4 (and in other meters whose grown cycles span more bars), because a longer cycle is checked at more alignments to the bars. The check also logs each offered template's worst-case section-entry dip: how many beats, at the song's shortest beat, a head may stay dark entering one of its sections. Silence or a fade at either end of the song is not refused: the renderer covers only the detected beats plus one beat interval beyond the first and last (or up to the song's edge when that is nearer), holds every fixture dark outside that covered span, drops a cue that would start outside it and cuts one that runs past its end; the trace records the covered span, the longest gap between detected beats and each dropped cue. A long gap between two detected beats mid-song is one long beat and stays lit. A preset id the template does not declare likewise renders the effective variant, with a warning naming why. Each head enters each section on its own: where its first cues can be played as authored after its previous cue (or the initial state) it starts as authored; otherwise it stays dark for whole beats, long enough for any repositioning into it, then cuts in its cues where they would be, never inside a shutter state too short to take effect (a cue wholly inside that window is dropped and recorded). A head missing from the rig therefore changes no other head's output. The trace's `entry_windows` lists each section's window per fixture, and every `dropped_cues` record gives its `reason`. It writes complete 20 ms frames of constant DMX effects over model-relative channels 1-48, plans dark repositioning between cues, renders each section's template, preset and bars, and its colour and gobo on the heads whose wheel states are tagged ([colour and gobo](#how-a-sections-colour-and-gobo-reach-the-lights)) and its intensity on the dimmer ([intensity](#how-a-sections-intensity-reaches-the-lights)), but not yet the rest of the planner's song intent ([known regression](#what-the-pipeline-does)), and records its render identity and evidence in the `.xsq.trace.json`. Any refusal writes no file. `twinklr show` renders it too, resting the heads dark where the show's coordination does ([CLI command](#cli-command)); `inject` and `regenerate` inject the render's effects, and `regenerate` re-renders the whole song (see Live injection and section regeneration below); `run`, `show`, `inject` and `regenerate` each record their render in the plan checkpoint, which `eval-report` re-renders ([Evaluation report](#evaluation-report-twinklr-eval-report)); `twinklr display` renders no moving heads and ignores it | `job.moving_heads` |
| `moving_heads.initial_states` | `{}` | Run-supplied time-zero state per fixture id (unwrapped `pan_deg`/`tilt_deg`, `zoom_deg` exactly when the fixture's profile declares a `zoom` axis (left out of dumps when absent), `dimmer`, `discrete_states`, and explicit `settled`/`dark` evidence) for the moving-head renderer. A fixture without an entry has an unknown initial state. Every fixture needs a settled entry its profile accepts, and an entry must name a fixture of the rig; otherwise the job is refused when its fixtures load, and for each fixture without an entry the refusal prints the entry its profile's default bytes give, ready to paste after checking it ([Minimal physical profile](#minimal-physical-profile)). Enters render identity and the render trace, but not the planner's session or cache, so editing it re-renders without re-planning | `job.moving_heads.initial_states` |
| `moving_heads.reposition_fallback` | `"error"` | What the render does with a cue whose dark repositioning cannot be planned. `"error"` refuses the render (before planning when the gate finds it inside a template); `"preserve_aim"` plays the cue at the aim the head holds; `"drop_accent"` keeps the cue dark and plans the next cue from that aim. A fallback applies only to cues of template steps that declare the same `reposition_fallback`, and never covers an unknown initial state, unknown visibility latency, a missing darkness guarantee or a lock; each substituted cue is listed in the trace. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.reposition_fallback` |
| `moving_heads.on_unplayable` | `"dark"` | What the render does with a cue the plan placed where it cannot play honestly, after any `reposition_fallback` the cue and the job both declare. `"dark"` leaves the fixture dark over that cue (it parks there as over any gap) and the render continues: a cue whose dark repositioning still cannot be planned (dropping one can leave the next one too little time, so this repeats until every remaining cue plans), a cue a shutter state too short to take effect lies in (such as a last cue cut to one frame at the song end), a step a fixture cannot play at this section's placement (rate, bounds, pulse or lit-window width) although it plays from bar 1 over the song, and every cue of a section too short for a `ONCE` cycle. Each is listed in the trace's `dropped_cues` with `reason` `"unplayable"`, its `code` and `detail`, the render record carries `unplayable_totals` per code, and the run logs one warning with the counts, which `twinklr run` prints. Never covers an unknown initial state or a lock, and never applies to what is refused before planning: a template that cannot play from bar 1 over the song is still refused, at the gate or at render. `"error"` refuses the render instead. A non-default value enters render identity, but not the planner's session or cache | `job.moving_heads.on_unplayable` |
| `moving_heads.max_effects` | `1000000` | The most DMX effects one render may emit after identical adjacent 20 ms frames are merged. More fails the render with `output_budget_exceeded`; frames are never dropped to fit. Must be positive; a non-default value enters render identity. `inject` and `regenerate` have their own, lower bound of 50,000 effects (see Live injection and section regeneration) | `job.moving_heads.max_effects` |
| `moving_heads.max_xsq_bytes` | `134217728` (128 MiB) | The largest serialized `.xsq`, in UTF-8 bytes, one render may write. Larger fails the render with `output_budget_exceeded`; frames are never dropped to fit. Must be positive; a non-default value enters render identity | `job.moving_heads.max_xsq_bytes` |

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
  "schema_version": "3.1",
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

Each fixture still needs a `dmx_mapping`, which the renderer does not read: its pan, tilt, dimmer, color, gobo and shutter channel numbers are listed to the moving-head planner. Fields Twinklr no longer reads are refused when the fixture file loads, naming the key, so delete them: `dmx_mapping.shutter_default`, `shutter_map`, `color_map`, `gobo_map`, `pan_fine_channel`, `tilt_fine_channel` and `use_16bit_pan_tilt`; a fixture's `inversions`, `pan_tilt_range`, `orientation` and `limits`; `position.pan_offset_deg` and `tilt_offset_deg`; and the group's `xlights_semantic_groups`.

A fixture's `config` carries a `physical_profile` for the moving-head renderer; in the `base_config` form, `base_config.physical_profile` applies to every fixture and a fixture's `config_overrides.physical_profile` replaces it for that fixture. An invalid profile fails when the fixture file loads, naming the fixture (or `base_config`), the field and the [minimal example](#minimal-physical-profile). The renderer requires one on every fixture and renders from it alone. Its output is written to the fixture's own xLights model, which must be a single-color DMX model with at least `footprint` channels; `twinklr run --layout` checks this before analysis (and records the layout's content hash in the trace), and without a layout the check is skipped with a warning. It declares the fixture explicitly rather than inferring anything from `dmx_mapping`: `profile_id`, `provenance` (`synthetic`, `manufacturer` or `measured`), the model-relative channel `footprint` (at most 48, the xLights DMX effect's limit) with a default byte for every channel `1..footprint` (an unlisted one is filled, below), continuous `axes` (`pan`/`tilt` in degrees, `dimmer` normalized, and an optional `zoom` beam angle in degrees) with calibrated `physical_min`/`physical_max`, an optional narrower `allowed_min`/`allowed_max` operating window that does not rescale the mapping, coarse/fine offsets, optional `dmx_min`/`dmx_max` for an axis whose calibrated range maps over only part of its DMX word (default `0` and the full word, 255 or 65535 with a fine offset, and left out of dumps at those defaults; a value encodes to `dmx_min` plus its share of the range times `dmx_max - dmx_min`, rounded half up), and inversion, which reflects the word within `dmx_min`..`dmx_max`, `discrete` shutter/color/gobo channels whose named states each select one explicit byte inside a declared, non-overlapping range, and `visibility` (what extinguishes output, and close/open latency). A profile cannot claim darkness it cannot produce: the shutter's `open_state` cannot extinguish, and `dimmer_zero_extinguishes` needs a dimmer axis calibrated from `0` whose operating window admits `0`. Normalized axes lie within `0..1`. Unknown speed, latency and settle times stay `null`; they are never filled in. A profile does not say where a fixture is now; that is `moving_heads.initial_states` in the job config. The retired `capabilities` and `movement_speed` keys stay ignored.

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

With it the group needs no `topology`. A fixture still needs a `dmx_mapping` (`pan_channel`, `tilt_channel` and `dimmer_channel`) until that field is removed; the renderer never reads it. A fixture's `config_overrides.physical_profile` replaces the shared profile for that fixture.

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
| a state's `hex`, `pattern`, `strobe` | Never defaulted or guessed: an untagged state is not offered to the planner ([state meaning tags](#state-meaning-tags)) |

#### State meaning tags

A wheel or shutter state may also say what it means, so that the planner's song intent has something to resolve to: a section or event colour, a gobo pattern, a strobe speed. Tags are what make those planner choices available on a rig: the pre-planning check offers the planner only tagged states ([the rig offer](#the-rig-offer)), and a section's colour and gobo play them ([how they reach the lights](#how-a-sections-colour-and-gobo-reach-the-lights)). A strobe event plays a shutter state tagged with its speed where every head's shutter has one ([how events reach the lights](#how-a-sections-events-reach-the-lights)). A tag is rig data: an edit changes the render fingerprint and, under `twinklr show`, the session (as for presets, below). A profile without tags loads, dumps and renders exactly as before, and its heads keep their templates' colours and gobos whatever the planner asks.

| Tag | On | Value |
|---|---|---|
| `hex` | `color` states | The colour the slot shows: `"#RRGGBB"`, or a colour name (`red`, `blue`, `green`, `yellow`, `magenta`, `cyan`, `orange`, `purple`, `amber`, `lime`, `white`, `warm_white`, `cool_white`, `uv`), stored and dumped as that name's `#RRGGBB` |
| `pattern` | `gobo` states | The pattern it projects: `open`, `circles`, `triangles`, `stars`, `diamonds`, `clouds`, `prism`, `shatter`, `dots`, `flame`, `water`, `foliage` or `abstract` |
| `strobe` | `shutter` states | How fast it strobes: `slow`, `medium` or `fast` |
| `offer` | any state | Only `false`: the state honestly has none of these meanings and is never offered |

```json
"color": {"offset": 1, "settle_ms": 150,
          "states": {"white": {"value": 0, "hex": "white"}, "red": {"value": 10, "hex": "#E01010"},
                     "amber": {"value": 40, "hex": "amber"}}},
"gobo": {"offset": 4, "settle_ms": 150,
         "states": {"open": {"value": 0, "pattern": "open"}, "star": {"value": 20, "pattern": "stars"}}},
"shutter": {"offset": 2, "settle_ms": 0,
            "states": {"closed": {"value": 0}, "open": {"value": 255},
                       "strobe_fast": {"range_min": 200, "range_max": 250, "value": 230, "strobe": "fast"}}}
```

A state that honestly has no such meaning (a pulse, a random strobe, a rainbow scroll, a gobo shake) takes `"offer": false` instead: it is never offered and the guidance below stops asking for its tag. `offer` accepts only `false`, cannot sit beside a tag, and is left out of dumps when absent. The shutter's open and closed states need no tag: `open_state`, `closed_state` and `visibility.extinguishing_shutter_states` already say what they do. A shutter whose strobe is one variable slow-to-fast range offers one speed as one state; to offer all three, split the range into three states tagged `slow`, `medium` and `fast`.

Refused when the fixture file loads, naming the fixture, channel and state and what to write: a tag on another channel kind's state, a malformed `hex`, an unknown pattern or speed, two shutter states claiming one strobe speed, a `strobe` tag on the open, closed or an extinguishing state, and a tag beside `offer: false`. Two colour states may share a colour (a wheel can hold two slots of one colour, or an open slot and a white one; a request then resolves to the first by state name), and two gobo states one pattern (a static and a shaking copy; a request takes the shortest name, then the first by name, so `star` before `star_shake`).

A requested colour resolves hue first, in OKLCh, and the match is graded so the planner is offered only what a wheel can show:

| Request | Takes | Fit |
|---|---|---|
| A colour with a hue (OKLCh chroma 0.04 or more) | The tagged slot with a hue whose hue is nearest, then chroma, then lightness, among slots with at least 0.6 of its chroma (a CTO or CTB tint never stands in for a saturated colour). A pale tint (chroma below 0.10) takes the white slot instead when that is nearer it | `exact` within Oklab ΔE 0.02; `close` within ΔE 0.10 and 25° of hue; `approximate` within 75° of hue. For a request at least 0.8 of the slot's luminance, ΔE is measured to the slot at the dimmer level nearest it (a dimmer darkens a slot, never brightens or saturates it), so a slightly darker shade grades as the slot's colour; a darker request is graded on the plain ΔE, since the slot plays at the template's own level (olive is not yellow, maroon not red, grey not white) |
| A colour no slot shows (no qualifying slot within 75° of hue) | The nearest white slot (marked as a fallback), else the nearest hue | `hue_mismatch`: not offered |
| A white or tinted white (`warm_white`, `cool_white`) | The white slot nearest in lightness and tint; on a wheel without one, the nearest slot as a `hue_mismatch` | as above, by ΔE |
| A colour darker than Oklab lightness 0.15 (black) | No match: darkness is the dimmer's | — |

So cyan on a white/red/blue/green wheel shows green (`approximate`), never white; blue on a white/red wheel is a `hue_mismatch`; amber (`#FFA000`, 68°) shows orange where both orange and yellow slots exist; the palette green `#00E676` shows a green slot `close`. A colour name in a `hex` tag or a request is its canonical colour: the deleted renderer's representatives, except `purple`, now a violet (`#A020F0`), and `amber` (`#FFA000`), each moved off a neighbouring preset's hue.

#### The rig offer

Before any planning, the pre-planning check works out what the rig can show of the planner's song intent and shows it to the planner (the prompt's "What This Rig Can Show"), and the planner's cache key hashes it:

- every colour the planner can name, as shown faithfully (every head with a colour wheel shows it `exact` or `close`), approximately (some only `approximate`; the prompt names the wheel colour it plays as), by some heads only (the others keep their template's colour) or not at all;
- for each section, the stop of its macro palette each palette role takes and the wheel colour it lands on, a role the palette has no stop for marked as not in it, and a role landing on the same wheel colour as an earlier one marked so (without a macro plan, the fixed role colours below);
- each gobo pattern and strobe speed, on every head, some or none; whether a hit, and so intensity shaping, is possible (a dimmer axis on every head; the prompt says so where some or no head has one); whether the heads can be commanded dark (`closed`, strobes, `pulse`) and the shortest dark and lit phase their darkness can follow, from which the prompt says how many flashes a beat each strobe plays at the song's median beat and how often the pulse can follow;
- how long a wheel change takes (darkness, turn and settle) in milliseconds and in beats at the song's tempo, and how many of the song's section boundaries it fits half the beat before (the render decides per boundary);
- per admitted template variant, its **dark phases**: the windows of a steady cycle (its second, so a cycle's leading darkness is included), in beats, in which each head is dark (gaps between its cues from visibility envelopes and overlay masks, frames it commands dark); the prompt names the templates with one long enough for a wheel change, and they are there for later accents (lyric-cue events placed on a lit beat, wheel events in a dark one);
- per template, any offered state its overlay masks cannot turn to and back in time (the check compiles each variant holding the slowest offered state, then the next, until it plans); those states are not offered with that template.

A wheel is offered only when it is tagged and **every** one of its states has a `settle_ms` (a turn to a tagged state, and back to the state a template holds, must both be timed in the dark); the tag file names each state without one, ready to paste. So tagging never costs a template its admission. Mixed rigs: a colour or gobo plays on every head that can show it, and a head that cannot, or has no such wheel, keeps its template's look. The offer also widens the section-entry dip the check reports for each template: any state offered for it may be the one a section enters into. That changes the reported dips on a tagged rig (by the slowest offered settle), never which templates are admitted.

A colour or gobo no head can show is repaired before the plan is validated: a section's is cleared to `as_authored`, and a colour or gobo event whose colour or pattern no head shows is dropped; a palette role the section's palette has no stop for (WARM or COOL: a stop with a hue within 90° of 55° or 230°; NEUTRAL: a white) becomes `PALETTE_PRIMARY`. One only some heads show is kept and recorded, naming the heads that keep their own look. Where a head's own wheel change does not fit half the beat before a section whose template has no dark moment long enough in its first half, the colour change is recorded too: where the heads play straight into that section it plays late or not at all. Heads the gate found always enter that template dark after the previous section's template (each pair of admitted variants, from each bar of the predecessor's cycle) are left out: their wheel turns in the entry. Either way the repair is recorded (`plan_repairs`) and shown to the planner on its next revision; it never fails the run. A colour a head shows only approximately is not a repair: the offer says so up front, and the render trace records what played. The deterministic selector's palette-role colours are repaired the same way. A `DRAMATIC` or `INTENSE` intensity on a rig where some or no head has a dimmer axis is kept and recorded as not shaped there, so the planner can give emphasis with events or colour. A wheel shows a colour's hue at the section's brightness, which is the template's and the intensity's; the prompt says so. An event the render will play other than asked is kept and recorded for the planner, with the render's own tests: a strobe slower than asked on some beat of its span (beat by beat) or a pulse slower than every beat, or not at all; a hit on heads without a dimmer, on a beat the part's template is dark on (the published steady-state dark phases: it plays on the lit heads, or moves where every head is dark, and the record names the beat, the direction and the offset), or inside a colour or gobo change's dark lead (it moves); a colour or gobo change shown after its beat on some heads (dark there, or its wheel change into the event's state does not fit half the beat before it), moved because no head shows it within a beat (to which beat), or not played; one closer to the previous change than a wheel change takes. A show's rests are not known when planning, so a hit they make move is reported only by the render's trace.

#### How a section's colour and gobo reach the lights

A section's `color` resolves to one colour: a named colour to its canonical value (the table above); a palette role to a stop of the section's macro palette: `PALETTE_PRIMARY` the first stop, `PALETTE_ACCENT` the second, `PALETTE_WARM` and `PALETTE_COOL` the stop with a hue within 90° of orange (OKLCh 55°) / of cyan-blue (230°) nearest it, `PALETTE_NEUTRAL` the least saturated white. A role the palette has no such stop for is not in that section's palette: the plan repair changes it to `PALETTE_PRIMARY` (and says so), which then plays, or not, as any colour, so where the rig does not show PRIMARY's colour the heads keep their authored colour; a colour from outside the palette is never substituted. `twinklr run` and `twinklr show` resolve it alike, through the macro plan's palettes. Without a macro palette for the section a role takes the fixed colours red, magenta, amber, cyan and white (the renderer before the single-renderer cutover used the same table), and the trace says so. Each head then plays the colour state nearest that colour (the matching above) and the gobo state tagged with the section's `gobo`.

The state replaces the colour and gobo the section's steps and their rig presets hold, for the whole section. A template's own overlay (`masked_wheel_flick`'s flick) keeps its state over its window and then returns to the section's colour, not the template's; a head whose flick colour equals the section's colour therefore shows no flick (nothing to turn to). A held state an overlay mask cannot turn to and back in time plays the template's own colour on that head in that section, recorded, never a refusal. A wheel turns only while the head is dark, settled before it is lit again:

- where a section starts with a dark entry (its heads reposition into it), the turn rides that entry, which may need up to one more beat when the turn is slower than the rest of it;
- where the heads play straight through a boundary lit and the colour or gobo changes there, in order: (a) the last moment of the previous section goes dark for the time the darkness, turn and settle take (the offer's wheel change time, rounded to frames), the head keeping its motion in the dark, and reveals on the section's first frame as before; darkness the previous cue already commands there (a show's rest, a dark phase) counts: the dip rides it, darkening only the lit frames the lead still needs, and adds nothing where the head is dark for the whole lead. The darkness the dip adds may be at most half the beat before the boundary; the trace records it (`added_ms`). (b) Else the head plays the previous colour into the section and turns in the section's first dark window long enough (a template dark phase or overlay mask, a show's rest), from then on in the new colour. (c) Else it keeps the previous colour for the whole section. The trace records (b) and (c) per head with times, and a warning counts them; (c), and (b) whose dark window opens past half the section (`late`, one definition for the trace and the repair), are what the plan repair records for the planner. Where the colour does not change, nothing is added.

An `as_authored` colour and gobo render exactly as before. The trace's `section_looks` lists, per section, what was asked, from where, the heads that play it from the section's start and how faithfully, the heads that turn to it later (`deferred`, with the time), keep the previous state (`kept_previous`), keep the template's (`kept_authored`, or `kept_authored_unplayable` for an overlay that cannot reach it), and each boundary's dark dip (with the darkness it added), deferral or kept state; the render identity hashes the macro palette of each section that resolves a palette role through one (`palettes`), which `eval-report` re-renders through and `twinklr inject` records with the plan, so `regenerate` renders the sections it keeps through the palettes they were injected with.

`twinklr run` (and `inject` and `regenerate`) and `twinklr show` print, before analysis, one `NOTE:` line naming the fixtures whose profiles have untagged states and the file they wrote, `<output_dir>/<song_name>/profile_tags.txt` (removed again once the rig is fully tagged; if it cannot be written, the tags are printed in full instead). The file holds, per profile, each such channel's `states` ready to paste in place of the profile's, with every missing tag either a `<...>` placeholder, which is refused if pasted unfilled, or a suggested value. A value is suggested where the state's name is one colour, pattern or strobe word (`red`, `warm white`, `star`, `strobe_fast`; a colour wheel's `open` suggests white) and not where it is qualified or names two (`dark-blue`, `red_blue`, `strobe_slow_fast`), or, with `--layout` (and always under `show`), where the fixture's xLights model declares a colour-wheel slot inside the state's range. The slot attributes read are `DmxColorWheelColor<i>` at byte `DmxColorWheelDMX<i>`, as the repository's layout profiler names them; those names have not been checked against a layout xLights wrote. A layout slot wins over the name. Suggestions are listed under the snippet for you to confirm; nothing is applied.

#### How a section's intensity reaches the lights

A section's `intensity` plays on the dimmer, locked to the beat grid (`sequencer/moving_heads/intensity.py`, one module holding every value below):

- `as_authored`, `SLOW`, `SMOOTH` and `FAST` play the template exactly as authored (byte for byte; SLOW and FAST equal SMOOTH by the owner's 2026-11-12 ruling).
- `DRAMATIC` and `INTENSE` add a pulse on the beat: `INTENSE` on every beat, `DRAMATIC` every half bar in an even meter of four beats or more (2 beats in 4/4, 3 in 6/8 counted in eighths), otherwise every bar (3 in 3/4, 2 in 2/4). Beats count from the section's first downbeat, and each accent starts on the frame nearest its beat, where the renderer places a template's own beat edges. A head also comes in on an accent where it is revealed after at least half a beat of darkness (a template's dark phase, a show's rest, a long colour dip, an entry window), so no lit window plays flat for want of a beat inside it; a reveal at most a quarter beat before a beat takes that beat's accent instead (one hit, on the beat), and after a shorter darkness the run follows the beat's accents (short flicks keep the beat). No accent starts where less than a quarter beat (and three frames) of the lit run is left, so a run never flashes full on its last frames before going dark. The accent `e` is 1 on its first frame and eases to 0 over one beat, `(1 - p)²` (`p` the share of the beat elapsed), then holds 0 until the next accent: a hit on the beat, not a fade. Each lit run is shaped by its highest authored level `M`, as a gain on the authored level `a`, so the template's own shape (a ramp, its own pulse) keeps its form:
  - **With headroom** (`M` at or below 80% of the dimmer's top): `a × (1 + g × (floor + peak × e))`, `g` scaling the table's gains down just enough that the run's peak reaches the top at most. The light rises and peaks on the beat.
  - **At full** (`M` at the top; every catalog family holds the dimmer full): `a × (1 − depth × (1 − e))`: the authored level on the accent, easing down to `1 − depth` of it before the next. This adds movement, not brightness: on a full family the light averages about 0.80 of the authored level under `DRAMATIC` and 0.74 under `INTENSE`. It is the one case where frames play below the template.
  - **Between** (80% to 100%): the two gains blended in proportion to where `M` lies, so the shaped level has no jump as an authored level nears full.

| Level | Accent every | Floor (headroom) | Peak (headroom) | Between accents (at full) |
|---|---|---|---|---|
| `DRAMATIC` | half bar (4/4) or bar (3/4) | × 1.10 | × 1.50 | × 0.75 |
| `INTENSE` | beat | × 1.15 | × 1.75 | × 0.60 |

These values are a first proposal for the owner to judge on a render, not an accepted look; whether peak sections should be brighter on average than the sections around them is the owner's open question. A frame the template commands dark (a zero dimmer, an extinguishing shutter state) is never touched and no lit frame goes to zero, so the dark frames, the wheels, the aim and every other channel are the template's; the shaping runs once every darkness of the section is placed. Where the dimmer axis declares `travel_speed_per_s`, a pulse whose steepest frame-to-frame step the dimmer cannot follow is scaled down (accent and dip together) until it fits; where it declares `latency_ms`, the accents are commanded that much earlier (at most just under half the section's shortest beat, and never before the section's first frame) so the light lands on the beat; the template's own dimmer edges are not led. A head without a dimmer axis cannot pulse: it plays as authored, and a warning says so per section. The trace's `section_looks` records, per section that sets an intensity (or whose focal role changes it), the intensity asked, the one played, and the shape: period, the gains, the blend band (`full_blend`), which heads got which shape (`headroom_pulse`, `authored_pulse_accent`, `dip_and_return`, `blended`), and the heads scaled for a slow dimmer (`degraded`), led by its latency (`lead_ms`) or without a dimmer (`unavailable`); `eval-report` prints it as a `played` line.

#### How a section's events reach the lights

A section's `events` play on its frames (`sequencer/moving_heads/events.py`, one module holding every value below), each on the frame nearest its beat (a lyric-cue-bound event has already been moved to its cue's beat), per head, inside its section; an event in one part of a section carries into the later parts (a darkness to its end, a colour or gobo as the later parts' held state). Events play after the template, the section's colour and gobo and a show's rests, and before the boundary dips and intensity; hits play last, on the level the section then plays. `bar N beat B` is the B-th detected beat at or after bar N's downbeat (`BeatGrid.beat_index`): beats before bar 1 (a pickup) belong to no bar, and a bar holds the beats detected in it. The renderer, the cue binder, the plan repair and the planner's prompt (which lists each lyric cue's nearest bar and beat) all count this way. An event that cannot be placed (outside its section, past the beat grid, on a beat its bar does not have) is traced as not played with why and warned about; the cue binder moves an event on a beat its bar lacks to the bar's last beat, and records one in a bar past the grid.

| Event | Plays |
|---|---|
| `closed` | dark from the beat until the next `open`, strobe or `pulse`, or the section's end, commanded on the cue's own path (the dimmer at zero where it extinguishes, else the closed shutter) |
| `open` | ends a `closed`, strobe or `pulse`: the template's own light again (one with nothing to end, or a `closed` an `open` on the same beat replaces, is traced as not played) |
| `strobe_slow` / `_medium` / `_fast` | from the beat until the next shutter event or the section's end: the shutter state tagged with that speed where the head has one (the fixture strobes itself, on its lit frames); otherwise an on/off on musical time, dark first, 2 / 4 / 8 flashes a beat, through the dimmer where its zero extinguishes (what the xLights preview shows) else the shutter. Each phase lasts at least what the darkness can follow (a frame; the dimmer's full swing at its `travel_speed_per_s`; through the shutter, the latency plus the state's settle each way): on a beat too short for the rate, it halves until it fits, beat by beat, recorded with how many beats played slower |
| `pulse` | lit for the first half of each beat, dark for the second, until the next shutter event or the section's end (every 2 or 4 beats where the darkness cannot follow one) |
| `hit` | on the level the section plays: with the head lit before the beat, a pre-dip over the quarter beat before it to `contrast` below that level (its last frames held), then the dimmer's top for a few frames and a decay back (**dip and snap**); revealed on the beat (dark before it, as a cascade's windows), the top for a few frames then a duck `contrast` below the level for as many frames, recovering over the decay (**flash and duck**). Never below 10% of the top. A hit on a beat where intensity already accents is one accent. A head counts it played only where at least its held frames differ from the level played without it by its contrast, or by all the room that level leaves above the 10% floor where that is less (frame by frame); otherwise it is traced "no visible change". A hit that lights frames a strobe or `pulse` holds dark is traced on both events |
| `color` / `gobo` | the held colour (pattern) changes at the beat to the event's, resolved as the section's (palette role or named colour to the nearest offered state; pattern to its tagged state), until the next such event or the section's end |

| Hit (by the bound lyric cue's emphasis; unbound: `MED`) | Contrast (share of the top) | Held frames (and frames that must differ) | Decay after it |
|---|---|---|---|
| `LOW` | 0.25 | 2 | a quarter beat |
| `MED` | 0.40 | 3 | half a beat |
| `HIGH` | 0.60 | 4 | three quarters of a beat |

A hit plays on its beat on every head lit there for at least three frames (its frame or one of the two after, where a template's lit window starts a frame late); a head dark there is lit for the hit where its darkness is the dimmer's inside a cue with no wheel moving (a `closed` event, a template's dimmer at zero), easing back to dark; a head dark between its template's cues (it repositions or turns a wheel there) does not play it, recorded. Only where no head can show it on its beat (a section's first beats while the heads reposition, a show's rest, a colour change's dip) does the hit move, on every head, within a bar: a hit bound to a lyric cue to the beat nearest the lyric (the later of equals); another to the later beat the most heads show (the nearest of equals), an earlier one only where no later one serves; recorded with the beat, the direction and the offset, and the lyric cue's line names the beat it played on. A colour or gobo event turns the wheel only while the head is dark: the reveal lands on the beat after a dark lead (the wheel change time) that rides darkness already there or dips at most half the beat before it (`dark_dip`, with the darkness it added); where the head is dark on the beat (a template's dark phase) the transaction pass turns it before the head's next reveal, if the gap still fits; inside a template overlay the event takes over the overlay's state from the beat; else the turn waits for the first dark window after the beat long enough that reveals it within one beat (`deferred`, late); else it does not play on that head, recorded. A head counts as showing the change only where it is lit with it for at least three frames running. The event plays on its beat where some head shows it within one beat; a head dark there shows it from its next reveal, however late (traced `late`), and one never lit again before the section ends does not play it. Where no head would show it within a beat, the event moves, on every head, to the beat within a bar (inside the part, between this wheel's neighbouring events) where the most heads do, a later one first, recorded with the beat, the direction and the offset; else it does not play. A wheel change fits before the beat where its time into the event's own state (its settle) is at most half the beat before it, the darkness already there counted (the prompt names the fastest tempo at which the rig's slowest change fits, and, per template, the beats of its cycle on which an event shows on every head, on some, within a beat, or moves). These values are a first proposal for the owner's W6/W7 view.

The trace's `section_looks` lists every event with what each head played and when (or why not: moved, late, slower, not played), a warning counts what did not play as asked, and `lyric_cues` lists every lyric moment cue the plan references with the event that answered it, the heads, the times and each one's signed offset from the lyric (`offset_ms`: negative before it), or that no event lands on it; `eval-report` prints both. The bound cue's emphasis and time travel with the plan (`PlanEvent.cue_emphasis`, `PlanEvent.cue_ms`, set by the cue binder, never planned).

#### How a section's transitions reach the lights

A section's `transitions` play at its boundaries (`sequencer/moving_heads/transitions.py`, one module holding every value below). Its `ENTRY` shapes the boundary it starts on, its `EXIT` the one it ends on; both name the change at one boundary, so where a section's `EXIT` meets the next section's `ENTRY` the `ENTRY` plays and the `EXIT` is traced (and repaired, `recorded`) as replaced. The song's first `ENTRY` and last `EXIT` play inside the section against the heads at rest: the run's initial pose (`moving_heads.initial_states`), dark. Every value is a first proposal for the owner's W8 view.

**The window.** `length` counts beats of the song's meter from the bar's downbeat (`BEAT` one beat, `HALF_BAR` half the bar's beats, `BAR` to `EIGHT_BARS` that many bars; a pickup shifts nothing, a 3/4 bar is three beats, a variable grid follows its beats). `split` is the share of the window the outgoing look takes; its point, the window's start plus that share, is where the change turns:

| Mode | Window | Plays |
|---|---|---|
| `snap` | at most `length` before the boundary | a cut on the boundary: where the heads must move or turn a wheel for the new look they go dark just before it and are in place, lit, on its frame; where nothing changes, the plain cut (the same bytes as no transition) |
| `crossfade` | `split` of `length` before the boundary, the rest after | the dimmer eases down to the handover level (half the lower of the two looks' levels; a dark look hands over at dark) on the boundary and up to the incoming look's; the aim, zoom and level ease across along the curve |
| `morph` | centred on the boundary | every continuous channel (aim, zoom, level) eases from the outgoing look to the incoming one along the curve, halfway at the split point |
| `sweep` | centred on the boundary | the outgoing look (aim and level) holds to the split point, then the head travels lit to the incoming look along the curve |
| `fade_via_black` | `split` of `length` before the boundary, the rest after | the light fades to dark by the boundary along the curve, the heads change in the dark (as long as the transaction pass needs, from the boundary), then the light fades up over what is left |
| `blackout` | `split` of `length` before the boundary, the rest after | dark over the whole window, the heads changing in the dark; it cuts in at the window's end |

`channels` give a channel its own strategy, overriding the mode's (`zoom` follows `pan`): `smooth` eases it (halfway at the split point), `crossfade` hands the level over (an aim eases as `smooth`), `snap` changes it at the split point, `fade_via_black` the same with the light fading into and out of the change, `sequence` with the change cut by the shutter (closed before it, the dimmer held; a head without a shutter state that extinguishes cuts on the dimmer). A colour or gobo wheel never blends, and nor does the shutter (`smooth` and `crossfade` play as `snap`, traced and recorded); a channel no head has is dropped by repair (`adjusted`), one only some heads have plays on those.

**What needs darkness.** A wheel never turns lit: a colour or gobo state that differs across the boundary turns in a dark cut at the split point, its strategy shaping the cut's edges, and the cut replaces the boundary's dark dip (the section's `boundaries` record says `in_transition`); so does an aim (pan, tilt) under `snap`, `fade_via_black` or `sequence`. The cut lasts what the transaction pass needs for the change (`worst_case_entry_ms`), placed around the split point by `split` (`fade_via_black` from the boundary, `snap` up to it). A lit move faster than the head travels (`travel_speed_per_s`) moves in a dark cut at the split point instead (traced `fallback`); a cut that does not fit the window, or a join the transaction pass cannot play, falls back to no transition on that head (the boundary's own entry, its dip or entry window), traced `not_played` with why.

**Each head's window** stays inside the cues that run unbroken into the boundary on each side (the transaction pass moves a head only between its cues, so a lit blend never reaches across a cascade's dark gap), and, from rest, starts no earlier than the head can be revealed. The boundary's window stays inside the two parts it joins, after the previous boundary's window, ends before the incoming part's first event that commands darkness or a wheel (`closed`, a strobe, `pulse`, `open`, `color`, `gobo`, from its dark lead) and starts after the outgoing part's last such event (the event plays, the transition yields; each clamp traced under `clamped`). A hit inside the window plays on the transition's level. A show's rest darkens the transition as any cue. Intensity leaves the transition alone: it starts at the outgoing look's level as intensity shaped it, and the incoming section's intensity resumes after it on an accent.

**Repair** (`rig_repair._transition_repairs`) shortens a transition longer than the parts it joins hold, by its placement, to the longest length that fits (`adjusted`), drops a strategy for a channel no head has, and records an `EXIT` the next `ENTRY` replaces, a strategy a channel cannot take, and a `crossfade`, `morph` or `sweep` across a colour or gobo change (its dark cut at the split point). The planner's prompt gives each length in milliseconds at the song's median beat and how fast the slowest head crosses its whole pan and tilt range.

The trace's `section_looks[].transitions` lists each transition with its window, split point, any clamp, the `EXIT` it replaced, and per head what it played (`plays`, `dark_ms`, `wheels_turn`, a head's own `window_ms`, `fallback`, `not_played`, `strategies_played_otherwise`, `curve_played`: a curve that neither rises nor falls over its cycle, such as a wave or a hold, plays as `linear`, and one that falls is turned over); `eval-report` prints it.

Under `twinklr show` the moving heads' macro focal role in a section adjusts its intensity at render: `LEAD` plays one step up the intensity ladder (`as_authored`, `SLOW`, `SMOOTH` and `FAST` as `DRAMATIC`; `DRAMATIC` as `INTENSE`; on a template at full level that is the dip-and-return, more movement in the light, not more light), `SUPPORT` plays the planner's choice, `REST` at most the template's level (`DRAMATIC` and `INTENSE` as authored). The heads render as one rig, so a role applies only where every moving-head target holds it; a section that names none for them plays the planner's choice, and one that names different roles, or a role for some targets and none for others, plays the planner's choice with a warning. The planner's prompt under `show` lists each section's role and says so. A role that changes a section's intensity is render identity: the trace and the plan checkpoint record it as `focal_roles`, and `eval-report` re-renders with it (and names `focal roles` when they differ). `twinklr run` has no focal role.

`moving_heads.initial_states` is never defaulted: a fixture without an entry has an unknown initial state and the run is refused before planning, because nothing establishes where a head is when the sequence starts (a previous sequence leaves it wherever it last aimed). The refusal lists every fixture without an entry and prints, as one object ready to paste into `moving_heads.initial_states`, the entry each profile's default bytes give: each axis at the value they encode, each discrete channel in its `default_state`, `settled`, and `dark` exactly when that dimmer level or shutter state extinguishes it. Pasting it asserts that each head really rests there, settled and dark as stated, when the sequence starts.

A fixture group may also declare `presets`, named components that template steps refer to by id (`component_refs`, below) instead of hard-coding angles and profile state names; an empty `presets` is left out of the group's dump:

| Key | Meaning |
|---|---|
| `presets.positions.<id>.fixtures.<fixture_id>` | That fixture's aim, `pan_deg` and `tilt_deg`, in unwrapped fixture-local degrees (never taken modulo 360; the renderer's bounds and travel-rate checks still apply) |
| `presets.positions.<id>.fallback` | Another position preset id, used for every fixture this preset does not list |
| `presets.attributes.<id>.fixtures.<fixture_id>` | That fixture's held `shutter`, `color` and `gobo` states, named as its own `physical_profile` names them, and a normalized `dimmer` level; at least one is set. One preset id can so select a different state name on each profile |
| `presets.attributes.<id>.fallback` | Another attribute preset id, used for every fixture this preset does not list |

A preset naming a fixture outside the group, a state its profile does not declare, a dimmer level on a profile without a dimmer axis, a fallback that is not declared, or a fallback chain that cycles fails when the fixture file loads. A referenced preset that declares nothing for a fixture, along its whole fallback chain, refuses the render (and, for an offered template, the run before planning); a head is never aimed at a center or default. Presets are rig data: an edit changes the render fingerprint. Under `twinklr run` it never changes the planner's session or cache; `twinklr show` includes the whole fixture file in its session, so there an edit plans again.

A fixture group may also declare a `topology`, the canonical full rig that a step's `distribution` (below) spreads phase over; an absent `topology` is left out of the group's dump:

| Key | Meaning |
|---|---|
| `topology.members` | One entry per head of the full rig, including a head this group lacks (a missing or disabled head keeps its place, so the others are never rephased). Every fixture of the group must be listed; fixture ids and ordinals are unique |
| `topology.members.fixture_id` | The head this entry places |
| `topology.members.row` | Its row; rows order first |
| `topology.members.column` | Its column within the row; columns order next |
| `topology.members.ordinal` | A unique number that orders heads sharing a row and column |

Heads are ranked in `(row, column, ordinal, fixture_id)` order over the whole topology, before any head is selected. A group without `topology` gets one derived row when every fixture declares `position.position_index`, ranked by `position_index` itself (index 1 is the first slot), in the rig's left-to-right order: an index the file skips is an empty slot, so a missing head keeps its place whenever the remaining indices show it (a head missing after the highest index cannot be seen; declare a `topology` for that). Two fixtures with the same `position_index` refuse a step with a distribution, naming them. Without either, a step with a distribution refuses the render, and the run before planning, naming the fixture group. The topology is rig data: it changes the render fingerprint. Under `twinklr run` it never changes the planner's session or cache; under `twinklr show` it does, as for presets.

_Source: `packages/twinklr/cli/main.py` (`_resolve_fixture_config_path`),
`packages/twinklr/core/config/fixtures/dmx.py` (`DmxMapping`),
`packages/twinklr/core/config/fixtures/capabilities.py` (`FixtureCapabilities`),
`packages/twinklr/core/config/fixtures/state_tags.py` (`nearest_color_state`, `tag_guidance`),
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
| `--template-dir` | No | — | Load strict JSON moving-head templates from this directory after the family catalog, which loads automatically; naming that catalog directory loads nothing twice |
| `--allow-template-overrides` | No | `false` | Explicitly permit a data template to replace a colliding catalog template ID |
| `--layout` | No | — | Path to your `xlights_rgbeffects.xml`. Before any analysis, every fixture's model must be in the layout, a DMX model (`DisplayAs` starting `Dmx`), single color when it records a `StringType`, and declare a channel count of at least its profile's `footprint` (read from `DmxChannelCount`, which xLights 2026.19 writes on DMX models, else from `parm1` as an unverified fallback; a model declaring neither is refused); otherwise the run is refused, naming fixture, model and item. Without it the check is skipped with a warning |

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

`show` renders the moving heads with the same prerequisites and checks as
`twinklr run`: the rig is
refused when its fixtures load if a fixture lacks a profile or initial state, the
family catalog is loaded, and the render preflight gate runs right after
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
section entry window inside a window can reposition the head there. A section's
palette-role colour resolves through its macro palette, as under `twinklr run`. The
heads' macro focal role adjusts each section's intensity
([intensity](#how-a-sections-intensity-reaches-the-lights)).
`max_effects` counts the moving heads' DMX effects (one per constant frame run) and
`max_xsq_bytes` the whole combined `.xsq`, display effects included; both are checked
before any file is written, the `.xsq` and its `.xsq.trace.json` are published
together, and the trace carries the moving-head render record (`render`) as `twinklr
run`'s does. Show metrics read the moving heads of a trace as onsets: the
frame runs of a cue merge into one, and dark transactions, parks and runs inside a
dark window are left out.

### Data-form moving-head templates

Moving-head templates can be supplied as strict JSON `TemplateDoc` files without
adding a Python module or reinstalling Twinklr. The family catalog always loads first. Duplicate
normalized ID, display-name, and explicit-alias collisions are rejected by default so
filesystem order cannot silently decide which choreography runs. An override can replace
only the exact incumbent template ID and cannot steal an unrelated alias; use
`--allow-template-overrides` only when replacement is deliberate.

A step names its motion in `movement` (`shape`, `mode`, start angles, extents and
`period_beats`, and for relative paths `lissajous_ratio` and `transform`), a dimmer pulse
in `dimmer` (left out for none), a shutter pulse in `shutter` or a held state in
`shutter_state`, held wheel states in `color` and `gobo`, and optionally `zoom`,
`distribution`, `visibility` and `reposition_fallback`; a template's wheel overlays are
its `overlays`. A document that still uses a key from before these names
(`movement.physical`, `dimmer.physical`, an empty `dimmer` object, `physical_shutter`,
`physical_shutter_state`, `physical_color`, `physical_gobo`, `physical_zoom`,
`physical_distribution`, `physical_visibility`, `physical_reposition_fallback` or
`physical_overlays`) is refused when it loads, naming the key and what replaces it (for
an empty `dimmer`, leaving it out).

To validate a template directory:

```bash
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

A template step may name the rig's presets (fixture config, above) instead of
hard-coding them, with `component_refs`; it is left out of dumps when absent:

| Key | Meaning |
|---|---|
| `component_refs.position_id` | A position preset that supplies each start angle the step leaves unset. `movement.start_pan_deg` and `start_tilt_deg` become optional; one set on the step (by the template or a template preset's patch) replaces the reference for that axis only. A step without a position reference must set both |
| `component_refs.attribute_preset_ids` | Attribute presets that supply each fixture's held shutter, color, gobo and dimmer level. The step's own `shutter_state`, `shutter` pulse, `color`, `gobo` or `dimmer` pulse replaces the reference for that channel only; two listed presets that both set a channel of one fixture are refused rather than one silently winning |

References resolve per fixture when the template compiles, both in the pre-planning dry
compile and in the render, and each cue records `component_provenance` in its metadata:
per channel, `step` or the referenced preset, the preset its fallback chain resolved to
and the SHA-256 of the entry used.

A template step may spread phase across the rig's heads (chases, cascades,
mirrored wings) with `distribution`, a list of distributions over the fixture
group's `topology` (fixture config, above). An empty list is left out of dumps:

| Key | Meaning |
|---|---|
| `distribution.domains` | The channels this distribution phases: `pan`, `tilt`, `dimmer` and `shutter` (color and gobo are held states with no phase). Two distributions of one step may not share a domain; a domain none lists keeps the step phase |
| `distribution.block_size` | Default `1`. Consecutive heads (after folding) that share one slot |
| `distribution.group_count` | Default none. Interleaves the blocks into this many slots (block number modulo the count) |
| `distribution.wings` | `1` (default) or `2`. Two wings fold the ordered rig at its center, so heads mirrored about it share a phase, and negate the left wing's pan displacement (an odd center head gets none); a referenced or authored start aim is never mirrored. The sign comes from the distribution that owns `pan` |
| `distribution.spread_cycles` | Default `0`, at least `0`. The phase span from the first slot to the last, both included, in cycles of each kernel's own period; taken at its exact decimal value |
| `distribution.direction` | `forward` (default: slot 0 leads) or `reverse` |

A head's phase in a domain is the step phase minus its offset, so slot 0 leads and later
slots lag; `phase_origin_ms` and a pulse's own `phase_cycles` are unchanged. A lagging
head on a finite `linear` path holds its start pose until its phase reaches zero, and
a head reaches the terminal pose once its phase reaches one; a step that ends sooner
cuts a lagging head wherever its path has reached. A lagging pulse starts its step mid-cycle; as
for any phase shift, the intervals the step start and end cut are exempt from the
one-frame rule, and every other interval is checked at the head's own phase. Each cue
records its head's rank, offsets and pan sign as `phase_distribution` metadata, and the
trace lists them with the rig's canonical order.

A step may move on a path about its base aim (its start angles or its
position reference, never both added) with `movement.shape` `circle`,
`lissajous` (both periodic) or `sweep` (periodic: edge to edge and back each period;
finite: one way, then held). Each extent is that axis's maximum signed displacement of
the unrotated path, so a circle with pan extent 30 and tilt extent 10 is an ellipse ±30°
by ±10°. A circle starts at the aim plus its pan extent, a sweep at the aim minus it
(plus it, when a finite sweep is reversed) and a lissajous at the aim, so the first cue
of a path enters there. A sweep moves along pan, so its tilt extent must be zero unless
`rotation_deg` turns it (and its pan extent zero when turned a quarter turn). The fields
below are left out of dumps when absent:

| Key | Meaning |
|---|---|
| `movement.lissajous_ratio` | `lissajous` only: pan and tilt cycles per period, positive integers, default `[1, 2]` (a figure eight) |
| `movement.transform.rotation_deg` | Default `0`. Turns the path about the aim before each axis is scaled by its own extent, so a 90° turn moves a pan sweep onto tilt at the tilt extent. Turning a circle only shifts where it starts; a lissajous turned off a quarter turn can reach past its extents, by up to √2 times (about 1.24 times for 1:2 at 45°) |
| `movement.transform.reverse` | Default `false`. Runs the path backwards (a circle clockwise instead of counter-clockwise, a finite sweep from the other edge); pulses are unchanged. Refused on a periodic sweep, which it would not change |
| `movement.transform.phase_cycles` | Default `0`. Starts the path this many cycles into its travel, at its exact decimal value; pulses are unchanged |

A transform applies only to these three shapes; `hold`, `sine_pan`, `sine_tilt` and
`linear` keep their meaning. Each axis is evaluated at the head's phase in that axis's
domain, so a distribution meant to shift the whole path lists both `pan` and `tilt`;
a mirrored wing negates the pan component after rotation, reflecting the path. The exact
formulas are in `evaluate_path` (`compile/step.py`). Nothing is normalized
or closed: a path that leaves an axis's range, exceeds its travel speed or moves finer
than the head can follow at any frame is refused by the pre-planning dry compile, like
any other motion.

A step may set the beam angle on a fixture's `zoom` axis with its own
`zoom`; it is left out of dumps when absent:

| Key | Meaning |
|---|---|
| `zoom.shape` | `hold` keeps `start_deg` through the step; `sine` adds `extent_deg × sin(2π·phase)` at the step's movement phase (its `movement.period_beats`, at the head's pan distribution offset), so a sine needs a periodic movement |
| `zoom.start_deg` | The beam angle, in the degrees of the profile's `zoom` axis |
| `zoom.extent_deg` | Default `0`. The sine's amplitude; a hold takes none and a sine needs one |
| `zoom.if_unsupported` | `error` (default): a fixture whose profile declares no `zoom` axis refuses the step, so the pre-planning dry compile leaves a catalog family that needs one out on that rig. `omit_optional_zoom`: the step plays there without its zoom, and the trace's `omitted_optional` lists each such cue |

On a profile with a `zoom` axis every cue holds a zoom: a step without `zoom`
holds the profile's default byte, as an unauthored channel would. The zoom is a pose
axis like pan and tilt: the dry compile refuses one faster than its
`travel_speed_per_s`, and between cues it is held, never left to its default byte, moves
only in the dark and settles (`latency_ms`, `settle_ms`) before any reveal. Only this
one optical axis exists; focus, iris, prism and gobo rotation do not.

A template may set `repeat.mode` to `ONCE`: its one cycle plays at its
nominal tempo and never repeats. Every step must declare finite motion
(`movement.mode` `finite`) that completes within the step (`period_beats`,
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
detected beats is cut without error. The planner sees template IDs and descriptions,
never a repeat mode.

A repeating (`JOINER` or `PING_PONG`) cycle restarts its steps' motion
and pulses at every cycle, so in every meter, 4/4 included, the compile grows
a cycle that would cut them: when every loop step starts at the cycle start and spans
the whole cycle, and the cycle's length in beats at the song's meter is not a whole
number of each step's periodic `movement.period_beats` and of each dimmer or
shutter pulse period with a duty cycle below 1, or ends before an `overlays`
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

A step with a period may light only part of its movement with
`visibility`, and a template may flick a wheel to another state
for part of every cycle with `overlays`. Neither moves a head in the dark
itself: the dark spans they leave between cues are repositioned by the same pass as
every other gap, which darkens the fixture, turns wheels, travels and settles before
the next reveal. Both are left out of dumps when absent:

| Key | Meaning |
|---|---|
| `visibility.visible_phase_start` | Where in each movement period the step lights, as a fraction from `0` (inclusive) up to `visible_phase_end`. Read at the head's own movement phase, its pan/tilt distribution offset included, so a lagging head's window lags with its path. The window is in phase before the path's own `transform`, so a transform changes which arc is lit, not when: `reverse` on a finite sweep lit over `0`-`0.5` lights its travel from the far edge to the aim. A periodic movement lights in every period. A finite movement's phase clamps to `0`-`1` as its motion does, so a window from `0` also lights a lagging head holding its start. A frame is lit when its start lies in the window |
| `visibility.visible_phase_end` | Where the lit window ends, at most `1`. On a finite movement a window ending at `1` includes the terminal pose, so the head stays lit at `level` through any hold after the move (a `ONCE` `HOLD_LAST_POSE` remainder included) and takes no `release_beats`; one ending before `1` leaves the hold dark. A lit window or a dark interval inside a step shorter than one 20 ms frame is refused, never dropped |
| `visibility.attack_beats` | Default `0`. The dimmer rises linearly from 0 over this many beats from the window start |
| `visibility.release_beats` | Default `0`. The dimmer falls linearly to 0 over this many beats before the window end. Attack and release together must fit inside the window |
| `visibility.level` | Default `1`. The lit dimmer level. The envelope replaces the dimmer: the step may not set a `dimmer` or `shutter` pulse, and it replaces a dimmer level an attribute preset supplies. A profile without a dimmer axis needs zero ramps and level `1` |
| `overlays.start_beats` | Where the overlay starts, in beats from the start of each cycle; it may span a step boundary |
| `overlays.end_beats` | Where it ends, in beats from the start of each cycle; a cycle whose loop steps each span it grows to whole bars that hold it (above), and one whose steps do not is refused if it ends first. Overlays on one wheel may not overlap; overlays on the color and gobo wheels may, each splitting what the other leaves |
| `overlays.mask_beats` | The dark time after the start and before the end while the wheel turns and settles. A mask too short for the wheel fails the render like any reposition that does not fit, and a step's declared `reposition_fallback` applies |
| `overlays.channel` | `color` or `gobo` |
| `overlays.state` | The state to show, named as each fixture's profile names it; never a byte |
| `overlays.attribute_preset_id` | Instead of `state`: a rig attribute preset whose entry for each fixture (along its fallback chain) names that fixture's state on `channel` |
| `overlays.release` | `resume_base`, the only value: after the end the head shows whichever step is in force then, so a step change during the overlay is what resumes |

An overlay applies in every cycle the section plays as authored, including the head of a
cycle a `TRUNCATE` remainder plays, but not over a `HOLD_LAST_POSE` remainder, which
holds the cycle's closing step from a new start where no authored cycle plays it. A cue
that already holds the overlay's state (its own, or the profile's default where it sets
none) is left whole, without masks, and records the channel under `overlay_unchanged` in
its metadata. An overlay that falls wholly inside an envelope's dark part changes
nothing, since there is no cue there to split.

The lit shutter is the step's own static `shutter_state` (or a referenced
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
and writes DMX effects to reserved layers starting at 99. Differences between the live
layout and the fixture config are printed; Twinklr never guesses channel mappings for
unknown models.

```bash
uv run twinklr inject --audio song.mp3 --config job_config.json --dry-run
uv run twinklr inject --audio song.mp3 --config job_config.json
uv run twinklr regenerate chorus_2 --audio song.mp3 --config job_config.json
```

The dry run prints the exact `deleteEffect`/`addEffect` requests and writes nothing.
`regenerate` reuses cached audio/profile/lyrics/macro analysis, forces a fresh plan for
only the canonical section ID, and re-renders the whole song (see below). Twinklr tracks
its reserved-layer ownership in the song artifact directory, stops before touching an
unowned collision, and never saves the xLights sequence.

The xLights automation API has no documented authentication. Any local process can drive
the application while the port is enabled. Use a trusted machine, inspect the reserved
layer before saving, and disable the API when finished. Because xLights offers no
transaction and `addEffect` returns no ID, a timeout can be ambiguous; do not save, inspect
reserved layers starting at 99, then run the same command again. Preflight makes that
recovery idempotent, as long as xLights reports each effect back exactly as Twinklr sent
it, which has not been verified against a running xLights.

#### What is injected, replaced and refused

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
- **`regenerate <section>` re-renders the whole song.** It re-plans only that section,
  then renders the moving heads for the **whole song** from the
  recorded plan of the effects already injected, with that section's plan replaced and
  every other section's plan unchanged. The render plans each head's dark
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
  The rig's digest covers the fields this Twinklr version records for a rig, so after an
  upgrade that changes them `regenerate` refuses every sequence injected before it, until
  `twinklr inject` runs again for that sequence.
  An unreadable `.twinklr-live-plans.json` is named with what to do (delete it, then
  `inject`); an `inject` that cannot record its plan reports the injection complete and
  the plan unrecorded. A plan recorded before the planner contract of 2026-11-17 is
  refused by name: run `twinklr inject` to re-plan the song.
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
- **Volume.** A render emits many effects, about 20,000-30,000 on four heads for a three-minute song. xLights' automation API has no batch
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
2. **Render preflight** (`render_preflight`) — the moving-head gate described under `moving_heads` above: refuses a rig or song the renderer cannot render and fixes the templates the planner is offered, before any planner runs.
3. **Audio Profiling** (`profile`) — LLM generates musical interpretation and creative guidance from the analysis.
4. **Lyrics Analysis** (`lyrics`) — conditional stage; runs only if lyrics are detected. Produces narrative and thematic context.
5. **Macro Planning** (`macro`) — LLM generates a high-level choreography strategy across all display groups.
6. **Moving Head Planning** (`moving_heads`) — multi-agent loop (planner -> deterministic heuristics -> judge) generates a `ChoreographyPlan`: per song section, one to three templates (each with a preset or none) over its bars, and the section's song intent (intensity, colour from the song's palette or a named colour, gobo, timed accents such as strobes, hits and colour or gobo changes tied to the lyrics' moment cues, motif variation, movement density, and entry and exit transitions). The planner is asked to answer the song in every section (intensity from the energy target, a colour from the section's palette, an accent on every high- and medium-emphasis lyric cue and on drops and hits) and to give a reason wherever it keeps the template's own intensity, colour or gobo (`as_authored`); the judge marks a plan down for unanswered lyric cues, flat intensity and an ignored palette. A single item the song cannot hold is repaired rather than refused, keeping as much of it as the song allows (an event outside its section moves into it, a cue's accent nearest the next section's downbeat lands on its own section's last beat; an unknown lyric cue is dropped): the repair is recorded in the trace (`plan_repairs`, and in the `eval-report`) and shown to the planner on its next revision. A valid plan that leaves a high-emphasis lyric cue without an event goes back to the planner before judging, at most once per run and only while a planning round remains; otherwise it is judged as it is. A plan that is structurally wrong (a song section left unplanned, a section whose bars are not the song structure's, a template not offered, a section beyond the song, a placeholder reason or overall strategy) goes back to the planner. In the sequence's section timing marks a section of one part is named by its section id (`chorus_1`), a part the planner labelled by `<section id>|<label>` (`chorus_1|drop`, also for a single labelled part), and an unlabelled part of several by `<section id>|A`, `|B`, `|C`.
7. **Rendering** (`render`) — compiles the plan's templates against each fixture's profile into complete 20 ms frames, plans dark repositioning between cues, then writes the delivery: a fresh `.xsq`, one `.xtiming` per timing track, and an `.xmap`.

**Known regression: the moving-head render does not yet carry all of the song.** The
renderer applies the templates, presets and bars each section names, each section's
colour and gobo on the heads whose wheel states are tagged
([how](#how-a-sections-colour-and-gobo-reach-the-lights)), its intensity on the
dimmer, which under `twinklr show` the heads' macro focal role adjusts
([how](#how-a-sections-intensity-reaches-the-lights)), and its timed events and the
lyric moment cues they land on ([how](#how-a-sections-events-reach-the-lights)), and its
entry and exit transitions ([how](#how-a-sections-transitions-reach-the-lights)). It does
not yet render the rest of the planner's song intent (motif variation, density,
modifiers), which no renderer has rendered; the trace's diagnostics name, per section,
the intent fields it set that are not rendered. Rendering them is planned work
([song-intent rendering](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)).

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
- **`profile_tags.txt`** — paste-ready meaning tags for the rig's untagged wheel and
  shutter states, written by `run`, `inject`, `regenerate` and `show` only while there are any
  ([state meaning tags](#state-meaning-tags)).
- Stage artifacts and intermediate results (audio analysis data, profiles, plans)
- **`checkpoints/plans/final.json`** — the moving-head plan and its render record, which `twinklr eval-report` reads. `twinklr run`, `show` and `inject`
  (and `regenerate`) write this same path for a song, so the last command to run wins.

### Using the Output

You **import** these into your own sequence rather than opening Twinklr's file as your show.

1. Open your sequence in **xLights**.
2. Import the effects from the generated `.xsq` as a donor sequence, using the shipped
   `.xmap` to pre-fill the model mapping. Your layout must already contain models the
   mapping can point at — Twinklr names them from your fixture config's
   `xlights_model_name` values.
3. The imported effects are constant DMX effects, one per run of identical 20 ms frames,
   each writing every channel of the head's profile footprint.
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
and per-channel plots under `plots/`; it writes no sequence file. Each section states the
planner's song intent as planned (`song_intent`), what its colour and gobo played on
the heads (`played`) and the fields it set that the renderer does not render yet; the
render block lists the plan's repairs (`plan_repairs`).

Every command that plans and renders the moving heads
(`twinklr run`, `show`, `inject`, `regenerate`) adds a `render` record to the plan
checkpoint once it has written its `.xsq`: the render fingerprint, the render policy, the beat
grid it rendered against, the pre-planning gate's result, the dark spans a show rested
the heads over (left out when there are none), the trace's input hashes (each fixture's
profile and model name, each template, the beat grid, the dark spans, the renderer and
encoder revisions) and the rendered rig's identity (a hash of the fixture group and of
each of its top-level fields, and whether the rig was reconciled with the live xLights
layout). The report re-renders the plan from that record, over the same dark spans,
with the family catalog loaded as `twinklr run` loads it, so each section
renders the variant the run rendered. The audio is analyzed only for the song's BPM and
structure. `--fixture` must be the run's fixture config. The re-render's fingerprint is
compared with the run's: a mismatch is reported as a `RENDER_FINGERPRINT_MISMATCH` error
naming each recorded input that differs (`mismatched_inputs`: a fixture, a field of the
rig, a template, the beat grid, the dark spans, a revision), and printed by the command;
the report then describes the re-render, not the delivered sequence. `inject` and
`regenerate` render on the fixture config as reconciled with the open layout, so where
that layout lacks a group the config names, no fixture config reproduces the
render: the mismatch says so and names the field that differs. A checkpoint
without a readable `render` record is refused before any analysis: the command that
planned it stopped before it delivered its moving-head render (an output budget refused
it, for one), or could not write the record (it logs a warning), and re-running that
command writes it; a record written before the record carried the rig's identity, or one whose
policy names `mode` (written by an earlier Twinklr version), is refused as malformed. A
checkpoint whose plan was written before the planner contract of 2026-11-17 is refused
by name; re-run the command that planned it. So is a
plan that names a template not in the family catalog: `eval-report` has no
template directory option, so a plan using `--template-dir` templates cannot be
re-rendered. A report on a show's checkpoint states its dark spans (how many, and their
total time): the heads keep moving on their authored paths there, commanded dark, so
`lit_range` and `lit_rate` leave those frames out and every other figure counts them.

A report reads the encoded frames, so its values are what the sequence
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

The report's `render` block holds both fingerprints, the gate's
`admission_exclusions`, `admission_preset_exclusions` and `admission_effective_presets`,
and the `unplayable_totals`. The report holds no curve metrics: no clamp percentage
(the renderer refuses an out-of-range value instead of clamping it), no limited-range or
static-curve flags, loop continuity, curve type, handler, base position, static DMX,
physics check, template compliance or section transitions, and no summary counts for
them. What holds instead: a repeating cycle spans whole periods and its gap-free repeats
continue its phase. A finite move restarts each repeat: dark, through a transaction, when the
restart needs more than one frame's travel; otherwise lit, as one step within the
travel speed (reported as the largest lit step); and a repeat for which neither fits is
kept dark. The renderer plans motion within each profile's travel speed, latency and
settle, and acceleration is modelled by nothing. A head that must reposition into a
section does so dark, in its entry window (entry `cut`) or before the section where its
bound fits there (entry `none`), while a `skipped` head plays through the boundary lit,
within its travel speed. The lit steps above report what the frames do.

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
- **Render stage**: a moving-head render the renderer refuses (`Moving-head render refused: ...`, naming the reason) or one over an output budget (`output_budget_exceeded`)

Agent responses are cached when `agent.agent_cache.enabled` is true (the default).
Re-running after fixing a failure can reuse compatible cached responses. The separate
`write_checkpoint` field controls only the final moving-head plan written for
`twinklr eval-report`; it does not enable or disable stage caching.

A cached result is reused only for the same inputs as this Twinklr version models them.
The session hashes the app and job configs (and, for `twinklr show`, the fixture group),
and the moving-head planner stage also hashes the descriptions of the templates it is
offered. After an upgrade that changes any of those, the first `run` or `show` of each
song plans again, which makes paid provider requests.

### Resetting caches

```bash
make clean-cache    # Clear audio cache, step cache, and logs
make reset          # Also clears feature store, profiles, and FE output
```

_Source: `Makefile` targets `clean-cache`, `reset`_
