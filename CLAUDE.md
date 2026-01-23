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
                          ├── AgentOrchestrator (multi-agent planning)
                          │     └── AgentRunner → LLMProvider
                          └── RenderingPipeline (DMX rendering)
                                    ↓
                          Output: xLights .xsq file
```

### Core Package Structure (`packages/blinkb0t/core/`)

**Session Layer** (`session.py`)
- `BlinkB0tSession`: Universal coordinator providing lazy-loaded services
- `session.audio`: Audio analysis (tempo, beats, energy, structure)
- `session.sequence`: xLights sequence fingerprinting

**Multi-Agent Orchestration** (`agents/sequencer/moving_heads/`)
- 3-stage iterative pipeline: Planner → Validator → Judge (with refinement loop)
- `AgentOrchestrator`: Main controller running up to N iterations until quality threshold met
- `AgentRunner`: Generic agent execution engine (prompts, LLM calls, validation, schema repair)
- `AgentSpec`: Data-driven agent configuration (prompt pack, response model, LLM settings)
- `HeuristicValidator`: Fast non-LLM validator for initial plan checks
- `FeedbackManager`: Tracks and formats feedback across iterations
- Agent models: `ChoreographyPlan` → `PlanSection` (template_id + preset_id per section)
- Checkpoint support: Saves RAW, EVALUATION, and FINAL plans to `{output_dir}/checkpoints/plans/`

**Audio Analysis** (`domains/audio/`)
- Subdomains: rhythm, harmonic, spectral, energy, structure, timeline
- `AudioAnalyzer`: Main entry point producing `SongFeatures`
- Results cached in `data/audio_cache/` for instant re-runs

**Sequencing** (`sequencer/moving_heads/`)
- `MovingHeadManager`: Domain manager coordinating agent orchestrator + rendering pipeline
- `RenderingPipeline`: Renders agent plans to DMX effects (ChoreographyPlan → FixtureSegments → XSQ)
- Templates: Python-defined choreography units (movement + geometry + dimmer patterns)
- Template registry: Builtin templates loaded from `templates/builtins/` directory
- Libraries define primitives: `MovementType`, `GeometryType`, `DimmerType` enums

**Infrastructure**
- `BeatGrid` (`audio/rhythm/`): Universal timing system (bars/beats → milliseconds)
- `XSQ Parser/Exporter` (`formats/xlights/xsq/`): xLights file I/O
- `CurveGenerator` (`curves/`): DMX value curve generation
- `CheckpointManager` (`utils/checkpoint.py`): Checkpoint read/write for agent plans and audio analysis

### Key Design Patterns

- **Manager Pattern**: Session provides services; domain managers add domain logic
- **AgentSpec Pattern**: Data-driven agent configuration (no agent classes, just specs + runner)
- **Schema Auto-Injection**: Response schemas dynamically injected into prompts to prevent drift
- **Pipeline Composition**: Rendering broken into focused stages
- **Dependency Injection**: Services passed via context objects, never hidden globals
- **Template Composition**: Templates are complete choreography units; LLM selects templates, not components
- **Iterative Refinement**: Multi-agent loop with feedback until quality threshold met

### Agent Architecture Details

**Agent Response Models** (`agents/sequencer/moving_heads/models.py`):
- `ChoreographyPlan`: Complete plan with list of sections + overall_strategy
- `PlanSection`: Single section with template_id, preset_id, bar range, optional modifiers
- `ValidationResponse`: Validator output (valid bool, errors, warnings, summary)
- `JudgeResponse`: Judge evaluation (decision, score, strengths, issues, feedback)

**Agent Prompts** (`agents/sequencer/moving_heads/prompts/`):
- Jinja2 templates: `system.j2`, `user.j2` (optional: `developer.j2`, `examples.jsonl`)
- Schema auto-injected via `{{ response_schema }}` variable
- Context variables: `context`, `plan`, `iteration`, `feedback`, etc.

**LLM Providers** (`agents/providers/`):
- `OpenAIProvider`: Wraps OpenAI client with retry logic and schema repair
- Supports OpenAI Responses API with JSON mode and structured outputs

### Separation of Concerns

- **Templates** define complete choreography (movement + geometry + dimmer patterns)
- **LLM** selects which template + preset to use per section (categorical selection, not generation)
- **Renderer** applies templates to beat grid and compiles to DMX segments
- **Channels** (future): Appearance overlays (shutter, color, gobo) independent of movement

### Agent Workflow

**Iteration Loop** (max 3 iterations by default):
1. **Planning Stage**: Planner agent generates `ChoreographyPlan` (template + preset per section)
2. **Heuristic Validation**: Fast non-LLM checks (template exists, timing valid, coverage complete)
3. **LLM Validation**: Validator agent performs deeper checks (returns `ValidationResponse`)
4. **Judge Stage**: Judge agent evaluates plan quality (returns `JudgeResponse` with score 0-10)
5. **Decision**:
   - Score ≥ 7.0 (APPROVE): Accept plan, proceed to rendering
   - Score 5.0-6.9 (SOFT_FAIL): Add feedback, refine in next iteration
   - Score < 5.0 (HARD_FAIL): Add critical feedback, major revision needed
6. **Refinement** (if not approved): Feedback sent back to planner for next iteration

**Checkpoints Saved**:
- `{project_name}_raw.json`: Latest plan from planner (each iteration)
- `{project_name}_evaluation.json`: Latest judge evaluation (each iteration)
- `{project_name}_final.json`: Final approved plan or best attempt (end of orchestration)

**Rendering** (after orchestration succeeds or reaches max iterations):
1. For each section in plan: Load template by `template_id`, apply `preset_id`
2. Build compile context (beat grid alignment, fixture contexts)
3. Compile template to intermediate representation (IR)
4. Generate DMX curves and fixture segments
5. Export segments to XSQ format

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
- **LLM generating implementation details** (curves, degrees, DMX values) - LLM only selects templates
- **LLM generating component fields** (movement, geometry, dimmer) - these are pre-defined in templates
- **Hardcoded JSON schemas in prompts** - use `{{ response_schema }}` auto-injection
- Templates containing channel specifications
- Mutable default arguments
- Catch-and-ignore errors

## Configuration Files

- `config.json`: Application settings (cache dirs, logging, LLM models)
- `job_config.json`: Job settings (agent config, checkpoint settings, fixture config path)
  - `agent.max_iterations`: Max orchestration iterations (default: 3)
  - `agent.token_budget`: Optional token limit per job
  - `checkpoint`: Whether to save/load checkpoints
- `fixture_config.json`: Moving head definitions and DMX mapping
- `.env`: API keys (OPENAI_API_KEY)

**Agent Configuration** (in code, not file-based):
- Agent specs defined in `agents/sequencer/moving_heads/specs.py`
- Planner: `gpt-5.2`, temp 0.7, conversational mode
- Validator: `gpt-5-mini`, temp 0.2, oneshot mode
- Judge: `gpt-5.2`, temp 0.3, oneshot mode

## Test Structure

Tests mirror source structure in `tests/`:
- `tests/unit/`: Individual components (validators, resolvers, handlers)
  - `tests/unit/agents/`: Agent runner, providers, feedback manager, orchestrator
- `tests/integration/`: Component interactions (template → effects)
- `tests/e2e/`: Full pipeline (audio + config → XSQ output)

Mock external dependencies (OpenAI, file I/O) for unit tests; use real dependencies for integration tests.

## Debugging Agent System

**Inspect Agent Outputs**:
```bash
# View raw plan from planner
cat artifacts/{project_name}/checkpoints/plans/{project_name}_raw.json

# View judge evaluation
cat artifacts/{project_name}/checkpoints/plans/{project_name}_evaluation.json

# View final approved plan
cat artifacts/{project_name}/checkpoints/plans/{project_name}_final.json
```

**Key Logging**:
- Agent orchestrator logs to `blinkb0t.core.agents.sequencer.moving_heads.orchestrator`
- Agent runner logs to `blinkb0t.core.agents.runner`
- LLM provider logs to `blinkb0t.core.agents.providers.openai`
- Rendering pipeline logs to `blinkb0t.core.sequencer.moving_heads.pipeline`

**Common Issues**:
- **Invalid template names**: Check that planner is using template IDs from the registry, not inventing new ones
- **Schema validation failures**: Agent runner will auto-repair up to N attempts (configured in AgentSpec)
- **Missing checkpoints**: Ensure `CheckpointManager` is passed to `OrchestrationConfig`
- **Schema drift**: Prompts use `{{ response_schema }}` auto-injection, never hardcode JSON schemas
