# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BlinkB0t (Twinklr) is an AI-powered choreography engine for xLights that transforms music into DMX moving head sequences using audio analysis, template composition, and multi-agent LLM orchestration.

## Commands
- Always run ruff/mypy/pytest via uv run
- When running code that requires secrets run via uv run --env-file .env -- <cmd>
- Never cat or printenv secrets; treat .env as sensitive

```bash
# Install dependencies
make install                    # First-time setup (requires uv)
uv sync --extra dev --all-packages  # Alternative install

# Quality checks (run before commits)
make validate                   # Format, lint-fix, type-check, test
make check-all                  # lint, format, type-check, test-cov

# Individual checks
uv run ruff check .             # Lint
uv run ruff format .            # Format
uv run mypy .                   # Type check

# Testing
uv run pytest tests/ -v                    # All tests
uv run pytest tests/unit/ -v               # Unit tests only
uv run pytest tests/integration/ -v        # Integration tests
uv run pytest -v -k "test_template"        # Pattern match
uv run pytest tests/unit/test_foo.py::test_specific -v  # Single test

# Run the pipeline
uv run blinkb0t run --audio <mp3> --xsq <xsq> --config job_config.json --out artifacts
```

## Architecture

### System Flow

```
CLI → BlinkB0tSession → MovingHeadManager
                          ├── AgentOrchestrator (5-stage AI planning)
                          └── MovingHeadSequencer (DMX rendering)
                                    ↓
                          Output: xLights .xsq file
```

### Core Package Structure (`packages/blinkb0t/core/`)

**Session Layer** (`session.py`)
- `BlinkB0tSession`: Universal coordinator providing lazy-loaded services
- `session.audio`: Audio analysis (tempo, beats, energy, structure)
- `session.sequence`: xLights sequence fingerprinting

**Multi-Agent Orchestration** (`agents/moving_heads/`)
- 5-stage pipeline: Plan → Validate → Implement → Judge → Refine
- `AgentOrchestrator`: Main controller running iterations until quality threshold met
- `StageCoordinator`: Executes individual stages with error handling
- `ContextShaper`: Builds token-efficient context for LLM prompts
- `TokenBudgetManager`: Tracks/limits token spending across stages

**Audio Analysis** (`domains/audio/`)
- Subdomains: rhythm, harmonic, spectral, energy, structure, timeline
- `AudioAnalyzer`: Main entry point producing `SongFeatures`
- Results cached in `data/audio_cache/` for instant re-runs

**Sequencing** (`domains/sequencing/`)
- `MovingHeadManager`: Domain manager coordinating planner + sequencer
- `MovingHeadSequencer`: Renders agent plans to DMX effects
- `RenderingPipeline`: Timeline → Segments → Curves → XSQ export
- Templates in `data/v2/templates/` (JSON validated against Python schemas)
- Libraries define primitives: movements, geometry transforms, dimmer patterns

**Infrastructure** (`domains/sequencing/infrastructure/`)
- `BeatGrid`: Universal timing system (bars/beats → milliseconds)
- `XSQ Parser/Exporter`: xLights file I/O
- `CurveGenerator`: DMX value curve generation

### Key Design Patterns

- **Manager Pattern**: Session provides services; domain managers add domain logic
- **Protocol-Based Design**: Agents share common interfaces (PromptBuilder, ResponseParser)
- **Pipeline Composition**: Rendering broken into focused stages
- **Dependency Injection**: Services passed via context objects, never hidden globals
- **Template Composition**: Multi-step templates compose curated primitives (LLM never generates raw DMX)

### Separation of Concerns

- **Templates** define movement choreography (pan/tilt trajectories)
- **Channels** define appearance (dimmer, shutter, color, gobo)
- These are independent - movement and appearance are composed, not coupled

## Development Standards

- **Python 3.12+** with type hints on all functions (mypy strict mode)
- **Ruff** for linting/formatting (100 char line length)
- **TDD**: Write tests before implementation
- **Pydantic V2** for all data validation
- **Google-style docstrings** on public symbols
- **Test coverage**: Maintain 65%+ (strive for 80%)

### Anti-Patterns to Avoid

- God objects (keep <500 lines, <10 public methods)
- Hidden dependencies (use dependency injection)
- LLM generating implementation details (curves, degrees, DMX values)
- Templates containing channel specifications
- Mutable default arguments
- Catch-and-ignore errors

## Configuration Files

- `config.json`: Application settings (cache dirs, logging, LLM models)
- `job_config.json`: Job settings (iterations, thresholds, fixture config path)
- `fixture_config.json`: Moving head definitions and DMX mapping
- `.env`: API keys (OPENAI_API_KEY)

## Test Structure

Tests mirror source structure in `tests/`:
- `tests/unit/`: Individual components (validators, resolvers, handlers)
- `tests/integration/`: Component interactions (template → effects)
- `tests/e2e/`: Full pipeline (audio + config → XSQ output)

Mock external dependencies (OpenAI, file I/O) for unit tests; use real dependencies for integration tests.
