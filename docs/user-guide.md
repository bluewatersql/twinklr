---
title: "User Guide"
description: "Installation, configuration, and usage instructions for Twinklr."
---

# User Guide

Step-by-step instructions for installing, configuring, and running Twinklr to generate xLights sequences from audio files.

---

## Prerequisites

- **Python 3.12+** (required; 3.13+ is not yet supported — see `pyproject.toml` `requires-python`)
- **[uv](https://github.com/astral-sh/uv)** — Astral's fast Python package manager
- **OpenAI API key** — required for LLM-based choreography planning
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

This runs `uv sync --extra dev --all-packages`, installing both workspace packages (`twinklr-core` and `twinklr-cli`) and development tools (pytest, ruff, mypy).

_Source: `Makefile` target `install`_

### Full Install (with ML)

For WhisperX lyrics transcription and other ML features:

```bash
make install-dev
```

This adds the `ml` extra group (~2GB+ for PyTorch and WhisperX). WhisperX models download automatically on first use (~150MB for the `base` model).

_Source: `Makefile` target `install-dev`_

### Verify Installation

```bash
make verify-install
```

Checks that both packages are importable and the CLI responds to `--help`.

---

## Environment Setup

### Required: OpenAI API Key

The pipeline requires an OpenAI API key for LLM agent calls:

```bash
export OPENAI_API_KEY='your-key-here'
```

The CLI checks for `OPENAI_API_KEY` at startup and exits with an error if it is not set.
`.env.example` lists the variables Twinklr reads, but nothing in the codebase loads a
`.env` file automatically — export the variable in your shell (or set it in your shell
profile) rather than relying on a `.env` file.

_Source: `packages/twinklr/cli/main.py:158-163`_

### Optional: Additional API Keys

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | **Required.** LLM provider API key |
| `GENIUS_ACCESS_TOKEN` | Genius lyrics lookup (set `enable_lyrics_lookup: true` in config) |
| `ACOUSTID_API_KEY` | AcoustID audio fingerprinting (set `enable_acoustid: true` in config) |
| `HF_TOKEN` | HuggingFace token for WhisperX model downloads |

### Environment Check

```bash
make env-check
```

Verifies that `uv` is installed, Python is available, and `OPENAI_API_KEY` is set in the current shell environment.

---

## Configuration Files

Twinklr uses three JSON configuration files. None are committed to the repo — create them from the defaults documented below.

### `config.json` (App Config)

Application-level settings shared across all jobs. Loaded by `AppConfig` in `packages/twinklr/core/config/models.py`.

Key fields and defaults:

| Field | Default | Description |
|---|---|---|
| `output_dir` | `"artifacts"` | Base output directory |
| `cache_dir` | `"data/audio_cache"` | Audio analysis cache |
| `llm_provider` | `"openai"` | LLM provider name |
| `llm_base_url` | `"https://api.openai.com/v1"` | LLM API base URL |
| `audio_processing.hop_length` | `512` | Librosa hop length |
| `audio_processing.frame_length` | `2048` | Librosa frame length |
| `logging.level` | `"INFO"` | Log level |

The `llm_api_key` field is populated from the `OPENAI_API_KEY` environment variable automatically.

Minimal example:

```json
{
  "output_dir": "artifacts",
  "llm_provider": "openai"
}
```

### `job_config.json` (Job Config)

Job-specific settings. Loaded by `JobConfig` in `packages/twinklr/core/config/models.py`. Schema version 3.0.

Key fields and defaults:

| Field | Default | Description |
|---|---|---|
| `schema_version` | `"3.0"` | Config schema version |
| `fixture_config_path` | `"fixture_config.json"` | Path to fixture definitions (relative to job config dir) |
| `agent.max_iterations` | `3` | Max planner/judge iterations |
| `agent.success_threshold` | `70` | Minimum judge score to accept a plan, on a 0-100 scale (validated; values outside the range are rejected). This is the only place the threshold is set — the planners take it converted to their own 0-10 scale. Note it does not yet stop a run: the judge score is recorded, not enforced. |
| `agent.token_budget` | `75000` | Total token budget |
| `agent.plan_agent.model` | `"gpt-5.2"` | Planner LLM model |
| `agent.judge_agent.model` | `"gpt-5-mini"` | Judge LLM model |
| `planner_features.enable_shutter` | `true` | Plan shutter/strobe |
| `planner_features.enable_color` | `true` | Plan color changes |
| `planner_features.enable_gobo` | `true` | Plan gobo selection |
| `transitions.enabled` | `true` | Enable section transitions |
| `transitions.default_duration_bars` | `0.5` | Transition length in bars |
| `checkpoint` | `true` | Enable stage result caching |

Minimal example:

```json
{
  "schema_version": "3.0",
  "fixture_config_path": "fixture_config.json",
  "agent": {
    "max_iterations": 3,
    "plan_agent": { "model": "gpt-5.2" }
  }
}
```

### `fixture_config.json` (Fixture Config)

Defines the physical moving head fixtures — names, DMX channels, and positions. The path is specified in `job_config.json` as `fixture_config_path`, resolved relative to the job config directory.

Each fixture's `dmx_mapping` also declares the value the render exports for that channel when the choreography never writes to it: `shutter_default` (0-255, defaults to `255` — open), and `color_map`/`gobo_map`'s `"open"` entry for color and gobo. A channel the mapping does not declare at all (e.g. `shutter_channel: null`) is omitted from the exported settings string rather than defaulted.

_Source: `packages/twinklr/cli/main.py:50-59` (`_resolve_fixture_config_path`), `packages/twinklr/core/config/fixtures/dmx.py` (`DmxMapping`)_

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

### What the Pipeline Does

The `twinklr run` command executes the moving heads pipeline with these stages:

1. **Audio Analysis** (`audio`) — analyzes the audio file for tempo, beat grid, energy dynamics, section boundaries, and harmonic content.
2. **Audio Profiling** (`profile`) — LLM generates musical interpretation and creative guidance from the analysis.
3. **Lyrics Analysis** (`lyrics`) — conditional stage; runs only if lyrics are detected. Produces narrative and thematic context.
4. **Macro Planning** (`macro`) — LLM generates a high-level choreography strategy across all display groups.
5. **Moving Head Planning** (`moving_heads`) — multi-agent loop (planner -> validator -> judge) generates a `ChoreographyPlan` with template selections and parameters per section.
6. **Rendering** (`render`) — compiles the plan into DMX values, curve data, and fixture segments, then writes the delivery: a fresh `.xsq`, one `.xtiming` per timing track, and an `.xmap`.

_Source: `packages/twinklr/core/pipeline/definitions/moving_heads.py` and `common.py`_

### Display Graph

The display graph describes what the planner may address. It is built from your fixture
config and contains one group — `MOVING_HEADS`, at the fixture count your config declares.

It used to be a hardcoded three-group yard (moving heads, outline, mega tree) with literal
fixture counts, which described the author's own display to the planner of every run. The
outline and mega-tree groups were addressable in the prompt but nothing rendered them: the
display pipeline is deferred, so naming them only told the planner about hardware the run
would never light. When that pipeline becomes reachable, its groups join the graph from
configuration.

_Source: `packages/twinklr/cli/main.py` (`build_display_graph`)_

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

### `OPENAI_API_KEY environment variable not set`

Export the environment variable: `export OPENAI_API_KEY='your-key-here'`. The CLI checks for this at startup.

### `Config file not found`

Config files (`config.json`, `job_config.json`, `fixture_config.json`) are not included in the repo. Create them with the documented defaults above. The `fixture_config_path` in `job_config.json` is resolved relative to the job config file's directory.

### `uv is not installed`

Install uv from [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv). All `make` targets check for uv before proceeding.

### Pipeline fails at a specific stage

The pipeline uses a fail-fast policy. Check the console output for the failed stage name and error message. Common causes:
- **Audio stage**: unsupported audio format or corrupt file
- **Agent stages**: LLM API errors, token budget exceeded, or timeout
- **Render stage**: invalid fixture config or missing template XSQ file

Successful stages are cached when `checkpoint: true` in job config. Re-running after fixing the error will reuse cached results for completed stages.

### Resetting caches

```bash
make clean-cache    # Clear audio cache, step cache, and logs
make reset          # Also clears feature store, profiles, and FE output
```

_Source: `Makefile` targets `clean-cache`, `reset`_
