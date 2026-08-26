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

This runs `uv sync --extra dev --all-packages`, installing both workspace packages (`twinklr-core` and `twinklr-cli`) and development tools (pytest, ruff, mypy).

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

_Source: `packages/twinklr/cli/main.py:158-163`_

### Optional: Additional API Keys

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required when `llm_provider` is `"openai"` |
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
automatically. Ollama supplies the SDK's required-but-ignored local placeholder
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
app-level model override. Set each role you intend to run, for example:

```json
{
  "agent": {
    "plan_agent": {"model": "qwen3.5:27b"},
    "judge_agent": {"model": "qwen3.5:27b"},
    "profile_agent": {"model": "qwen3.5:27b"},
    "lyrics_agent": {"model": "qwen3.5:27b"},
    "refinement_agent": {"model": "qwen3.5:27b"}
  }
}
```

Local structured requests use `/v1/chat/completions` with a JSON-schema
`response_format`; OpenAI cloud requests continue to use `/v1/responses`. Local mode is
opt-in and limited to loopback URLs. Image/vision stages are not supported by this local
adapter.

#### Explicit local schema smoke

The repository includes a `local_only` test against Twinklr's real `MacroPlan` schema.
It does not install Ollama or pull a model. After you separately install Ollama, start it,
and pull a model of your choice, authorize exactly one local request with:

```bash
TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 \
TWINKLR_OLLAMA_MODEL=qwen3.5:27b \
TWINKLR_OLLAMA_BASE_URL=http://127.0.0.1:11434/v1 \
uv run pytest tests/local_only/test_ollama_structured_outputs.py -q --no-cov
```

The smoke disables SDK retries, provider transport retries beyond the single request,
schema repair, and JSON-object fallback. Passing it proves schema validity for that
specific installed model; it is not a choreography-quality benchmark.

### `job_config.json` (Job Config)

Job-specific settings. Loaded by `JobConfig` in `packages/twinklr/core/config/models.py`. Schema version 3.0.

The same registry-backed subset policy applies here.

| JSON field | Default | Observable effect | Ledger path |
|---|---|---|---|
| `schema_version` | `"3.0"` | Fixed schema identity; other values fail validation | `job.schema_version` |
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
| `--template-dir` | No | — | Load strict JSON moving-head templates from this directory after Python builtins |
| `--allow-template-overrides` | No | `false` | Explicitly permit a data template to replace a colliding Python builtin ID |

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
5. **Moving Head Planning** (`moving_heads`) — multi-agent loop (planner -> validator -> judge) generates a `ChoreographyPlan` with template selections and parameters per section.
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
