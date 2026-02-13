<p align="center">
  <img src="docs/assets/twinklr_logo.png" alt="Twinklr" width="400">
</p>

<h3 align="center">AI-Powered Choreography Engine for Christmas Light Shows</h3>

<p align="center">
  Transform music into coordinated light shows using audio analysis, template composition, and multi-agent LLM orchestration.
  <br />
  Outputs sequences for <a href="https://xlights.org">xLights</a>, the open-source lighting control standard.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/packaging-uv-blueviolet?logo=astral&logoColor=white" alt="uv">
  <img src="https://img.shields.io/badge/linting-ruff-orange" alt="Ruff">
  <img src="https://img.shields.io/badge/types-mypy-blue" alt="mypy">
  <img src="https://img.shields.io/badge/models-pydantic_v2-e92063" alt="Pydantic V2">
</p>

---

## What is Twinklr?

Twinklr is a choreography engine that takes an audio file and automatically generates synchronized moving head sequences for Christmas light displays. Instead of spending dozens of hours manually programming pan angles, tilt curves, and dimmer patterns in xLights, Twinklr does it in minutes.

The core insight: **LLMs plan creative intent; deterministic code handles precision.** The AI decides *what* should happen ("fan formation with building intensity during the chorus"), and the rendering engine handles *how* ("pan fixture 3 to 127.5 degrees over 2,400 milliseconds with a sine-eased curve"). This separation is what makes the system reliable.

## How It Works

```
Audio File (.mp3)
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  1. Audio Analysis (deterministic)                      │
│     Tempo, beats, energy, sections, lyrics, phonemes    │
├─────────────────────────────────────────────────────────┤
│  2. Audio Profiling (LLM)                               │
│     Musical interpretation, creative guidance, mood arc  │
├─────────────────────────────────────────────────────────┤
│  3. Multi-Agent Planning (LLM)                          │
│     Planner → Validator → Judge (iterative refinement)  │
├─────────────────────────────────────────────────────────┤
│  4. Rendering & Compilation (deterministic)             │
│     Templates → curves → DMX values → fixture segments  │
└─────────────────────────────────────────────────────────┘
     │
     ▼
 xLights Sequence (.xsq)
```

**Stages 1 and 4 are entirely deterministic** — signal processing, curve math, and file format compliance. **Stages 2 and 3 use LLMs** for musical interpretation and choreography planning. The LLM never touches DMX values directly.

## Features

- **Full Audio Analysis** — tempo, beat grid, energy dynamics, section detection, harmonic content, lyrics with multi-source fallback (embedded tags, LRCLib, Genius, WhisperX)
- **Multi-Agent Orchestration** — iterative planner/validator/judge loop with structured feedback and automatic refinement
- **Categorical Planning** — LLM reasons in semantic terms (WHISPER/SOFT/MED/STRONG/PEAK intensity, HIT/BURST/PHRASE/EXTENDED/SECTION duration) while the renderer maps to precise DMX values
- **Template Library** — pre-built choreography units (fan formations, sweeps, chases, pulses) with presets and phase offsets for fixture-to-fixture coordination
- **Schema Auto-Injection** — Pydantic models generate the JSON schemas shown to the LLM, eliminating prompt/schema drift
- **Two-Tier Validation** — fast heuristic checks before expensive LLM evaluation
- **xLights Export** — native `.xsq` output with custom value curves, DMX mapping, and fixture grouping

## Quick Start

### Prerequisites

- **Python 3.12+**
- **[uv](https://github.com/astral-sh/uv)** (package manager)
- **OpenAI API key** (for agent orchestration)

### Installation

```bash
# Clone the repository
git clone https://github.com/bluewatersql/twinklr.git
cd twinklr

# Install dependencies
make install

# Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

For full audio features including WhisperX transcription:

```bash
make install-dev   # Includes ML dependencies (~2GB+)
```

### Usage

```bash
uv run twinklr run \
  --audio path/to/song.mp3 \
  --xsq path/to/template.xsq \
  --config job_config.json \
  --out artifacts
```

This runs the full pipeline: audio analysis, LLM profiling, multi-agent planning, and rendering. The output is an xLights `.xsq` sequence file ready to import.

## Project Structure

```
twinklr/
├── packages/twinklr/
│   ├── core/                    # Core library (twinklr-core)
│   │   ├── agents/              # Multi-agent orchestration
│   │   │   ├── audio/           # Audio & lyrics profiling agents
│   │   │   ├── sequencer/       # Planner, group planner agents
│   │   │   ├── providers/       # LLM provider adapters (OpenAI)
│   │   │   ├── shared/          # Judge, iteration controller
│   │   │   └── logging/         # LLM call logging
│   │   ├── audio/               # Audio analysis pipeline
│   │   │   ├── rhythm/          # Tempo, beats, BeatGrid
│   │   │   ├── energy/          # RMS, builds, drops
│   │   │   ├── structure/       # Section detection
│   │   │   ├── harmonic/        # Key, chords, chroma
│   │   │   └── phonemes/        # G2P, viseme mapping
│   │   ├── sequencer/           # Rendering & compilation
│   │   │   ├── moving_heads/    # Template compiler, DMX export
│   │   │   ├── display/         # Display effects & composition
│   │   │   └── templates/       # Template registry & builtins
│   │   ├── config/              # App & job config models
│   │   ├── curves/              # Curve generation (native + custom)
│   │   └── pipeline/            # Declarative pipeline framework
│   └── cli/                     # CLI entry point (twinklr-cli)
├── tests/                       # Unit, integration, e2e tests
├── blog/                        # Technical blog series
├── Makefile                     # Development commands
└── pyproject.toml               # Workspace configuration
```

## Architecture

### Key Design Decisions

| Principle | What It Means |
|---|---|
| **LLM plans intent, renderer implements precision** | The LLM selects templates and categorical parameters; deterministic code computes DMX values, curves, and timing |
| **Categorical over numeric** | Intensity is WHISPER/SOFT/MED/STRONG/PEAK, not a float. Duration is HIT/BURST/PHRASE, not milliseconds. The renderer resolves categories to precise values |
| **Templates as complete units** | Each template defines geometry + movement + dimmer as a tested, self-contained choreography unit. The LLM selects templates, never invents new ones |
| **Schema auto-injection** | Pydantic response models generate the JSON schemas shown in prompts, so model changes automatically propagate — no manual sync |
| **Two-tier validation** | Heuristic checks (template exists? timing valid?) run before the LLM judge, saving tokens on structurally invalid plans |
| **Data-driven agents** | No agent class hierarchies. One runner + `AgentSpec` data objects (prompt pack, response model, LLM settings) |

### Multi-Agent Planning Loop

The choreography planner uses an iterative refinement loop:

1. **Planner** generates a `ChoreographyPlan` (template + preset per song section)
2. **Heuristic Validator** checks structural validity (fast, free)
3. **LLM Validator** checks semantic quality (template appropriateness, coordination)
4. **Judge** scores the plan (0-10) and decides: approve, soft-fail (refine), or hard-fail (redo)
5. Structured feedback loops back to the planner for the next iteration

Plans that score 7.0+ are approved. The loop runs up to 3 iterations by default.

## Development

```bash
# Run all quality checks (recommended before committing)
make validate          # format + lint-fix + type-check + test

# Individual checks
make lint              # Ruff linting
make format            # Ruff formatting
make type-check        # mypy
make test              # pytest (all tests)
make test-cov          # pytest with coverage report

# Test audio pipeline on a file
make test-audio FILE=path/to/song.mp3

# Environment check
make env-check         # Verify uv, Python, .env setup
```

### Quality Gates

All commits must pass:
- Ruff linting (0 issues)
- mypy type checking (0 errors on new code)
- pytest (0 failures, coverage >= 65%)

## Configuration

| File | Purpose |
|---|---|
| `.env` | API keys (`OPENAI_API_KEY` required, plus optional keys for AcoustID, Genius, HuggingFace) |
| `config.json` | App settings — cache directories, audio processing options, logging |
| `job_config.json` | Job settings — agent config (iterations, model, token budget), fixture config path, checkpoints |
| `fixture_config.json` | Moving head definitions — fixture names, DMX channels, physical positions |

Copy `.env.example` to `.env` to get started. Config files are gitignored; create them from the documented schemas.

## Tech Stack

- **Python 3.12+** with strict type hints
- **[uv](https://github.com/astral-sh/uv)** for package management (workspace with core + cli packages)
- **[Pydantic V2](https://docs.pydantic.dev/)** for all data validation (LLM outputs, configs, models)
- **[OpenAI API](https://platform.openai.com/)** for agent orchestration (Responses API with structured outputs)
- **[librosa](https://librosa.org/)** for audio analysis and feature extraction
- **[Jinja2](https://jinja.palletsprojects.com/)** for prompt templating
- **[Rich](https://rich.readthedocs.io/)** for CLI output
- **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting
- **[mypy](https://mypy-lang.org/)** for static type checking
