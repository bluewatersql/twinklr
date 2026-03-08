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
# Option 1: Environment variable
export OPENAI_API_KEY='your-key-here'

# Option 2: .env file
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

The CLI checks for `OPENAI_API_KEY` at startup and exits with an error if it is not set.

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

Verifies that `uv` is installed, Python is available, and `.env` exists with `OPENAI_API_KEY`.

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
| `agent.success_threshold` | `70` | Config field (0-100 scale); the CLI currently hard-codes `min_pass_score=7.0` (0-10 scale) as the operative gate |
| `agent.token_budget` | `75000` | Total token budget |
| `agent.plan_agent.model` | `"gpt-5.2"` | Planner LLM model |
| `agent.judge_agent.model` | `"gpt-5-mini"` | Judge LLM model |
| `planner_features.enable_shutter` | `true` | Plan shutter/strobe |
| `planner_features.enable_color` | `true` | Plan color changes |
| `planner_features.enable_gobo` | `true` | Plan gobo selection |
| `channel_defaults.shutter` | `"open"` | Default shutter state |
| `channel_defaults.color` | `"white"` | Default color |
| `channel_defaults.gobo` | `"open"` | Default gobo |
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

_Source: `packages/twinklr/cli/main.py:50-59` (`_resolve_fixture_config_path`)_

---

## Running the Pipeline

### CLI Command

```bash
uv run twinklr run \
  --audio path/to/song.mp3 \
  --xsq path/to/template.xsq \
  --config path/to/job_config.json \
  --out artifacts \
  --app-config config.json
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `--audio` | Yes | — | Path to audio file (MP3 or WAV) |
| `--xsq` | Yes | — | Path to input `.xsq` template (existing xLights sequence to merge into) |
| `--config` | Yes | — | Path to job config JSON |
| `--out` | No | `.` | Output directory |
| `--app-config` | No | `config.json` | Path to app config JSON |

_Source: `packages/twinklr/cli/main.py:331-354` (`build_arg_parser`)_

### What the Pipeline Does

The `twinklr run` command executes the moving heads pipeline with these stages:

1. **Audio Analysis** (`audio`) — analyzes the audio file for tempo, beat grid, energy dynamics, section boundaries, and harmonic content.
2. **Audio Profiling** (`profile`) — LLM generates musical interpretation and creative guidance from the analysis.
3. **Lyrics Analysis** (`lyrics`) — conditional stage; runs only if lyrics are detected. Produces narrative and thematic context.
4. **Macro Planning** (`macro`) — LLM generates a high-level choreography strategy across all display groups.
5. **Moving Head Planning** (`moving_heads`) — multi-agent loop (planner -> validator -> judge) generates a `ChoreographyPlan` with template selections and parameters per section.
6. **Rendering** (`render`) — compiles the plan into DMX values, curve data, and fixture segments, then writes the output `.xsq` file.

_Source: `packages/twinklr/core/pipeline/definitions/moving_heads.py` and `common.py`_

### Display Graph

The CLI currently uses a hardcoded display layout with three groups:

| Group | Element Kind | Fixtures | Pixel Fraction | Position |
|---|---|---|---|---|
| `MOVING_HEADS` | Moving Head | 4 | 30% | Center, full height, yard |
| `OUTLINE` | String | 10 | 50% | Full width, high, house |
| `MEGA_TREE` | Tree | 1 | 20% | Center, full height, yard |

_Source: `packages/twinklr/cli/main.py:62-135` (`build_display_graph`)_

A layout parser to auto-populate this from xLights layout files is planned but not yet implemented.

---

## Understanding Outputs

### Output Directory Structure

Artifacts are written to `<output_dir>/<song_name>/`:

- **`<song_name>_twinklr_mh.xsq`** — the generated xLights sequence file for moving heads
- Stage artifacts and intermediate results (audio analysis data, profiles, plans)

### Using the XSQ Output

1. Open **xLights**
2. Import or open the generated `.xsq` file
3. The sequence contains value curves for each moving head fixture across all DMX channels (pan, tilt, dimmer, shutter, color, gobo)
4. Timeline timing tracks (beats, sections) are included if configured in `job_config.json` (`timeline_tracks`)
5. You can refine the sequence manually in xLights if desired

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

Set the environment variable or add it to your `.env` file. The CLI checks for this at startup.

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
