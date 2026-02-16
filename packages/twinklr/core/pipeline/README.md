# Pipeline Framework

Declarative pipeline orchestration for Twinklr with automatic dependency resolution, parallel execution, and error handling.

## Overview

The pipeline framework provides a clean abstraction for building complex multi-stage workflows. It handles:

- **Automatic dependency resolution** - Topological sorting of stages based on dependencies
- **Parallel execution** - Stages with same dependencies run concurrently
- **Fan-out pattern** - Execute a stage N times in parallel (e.g., per display group)
- **Conditional execution** - Skip stages based on runtime conditions
- **Retry logic** - Configurable exponential backoff retry
- **Error handling** - Fail-fast execution (no partial render outputs)
- **State management** - Shared context across stages
- **Metrics tracking** - Built-in observability

## Architecture

### Core Components

```
PipelineDefinition
  ├── StageDefinition[]     # Declarative stage config
  └── validate()            # Validate dependencies, detect cycles

PipelineExecutor
  ├── execute()             # Main entry point
  ├── _build_execution_plan()  # Topological sort
  └── _execute_wave()       # Parallel wave execution

PipelineContext
  ├── provider: LLMProvider
  ├── config: Config
  ├── state: dict           # Mutable shared state
  └── metrics: dict         # Metrics tracking

PipelineStage (Protocol)
  └── execute(input, context) -> StageResult
```

### Execution Flow

```
1. Validate pipeline definition (dependencies, cycles)
2. Build execution plan (topological sort into waves)
3. For each wave:
   a. Execute all stages in wave concurrently
   b. Collect outputs
   c. Fail immediately on any stage failure (no partial continuation)
4. Return PipelineResult with all outputs
```

## Failure Strategy

- **Fail-fast is the default and required pipeline behavior** for render/export workflows.
- **No partial rendering**: when any non-judge stage fails, the pipeline aborts and does not emit partial sequence output.
- **Only exception**: judge/critic `soft_fail` used inside iterative planning loops when token budget or iteration ceilings are reached.
- **Restartability is cache-backed**: successful stages are cached, and reruns reuse those cached artifacts after the error condition is resolved.
- **Cache writes are success-only**: failed stage outputs are never committed as resumable artifacts.

## Usage

### Basic Sequential Pipeline

```python
from twinklr.core.pipeline import (
    PipelineDefinition,
    PipelineExecutor,
    PipelineContext,
    StageDefinition,
)

# Define stages
pipeline = PipelineDefinition(
    name="my_pipeline",
    stages=[
        StageDefinition("audio", AudioAnalysisStage()),
        StageDefinition("profile", AudioProfileStage(), inputs=["audio"]),
    ],
)

# Execute
executor = PipelineExecutor()
result = await executor.execute(pipeline, audio_path, context)

if result.success:
    profile = result.outputs["profile"]
```

### Parallel Stages

Stages with same dependencies automatically run in parallel:

```python
PipelineDefinition(
    name="parallel",
    stages=[
        StageDefinition("audio", AudioAnalysisStage()),
        # These two run in parallel (both depend only on "audio")
        StageDefinition("profile", AudioProfileStage(), inputs=["audio"]),
        StageDefinition("lyrics", LyricsStage(), inputs=["audio"]),
        # This waits for both profile and lyrics
        StageDefinition("macro", MacroPlannerStage(), inputs=["profile", "lyrics"]),
    ],
)
```

### Fan-Out Pattern

Execute a stage N times in parallel:

```python
StageDefinition(
    id="groups",
    stage=GroupPlannerStage(),
    pattern=ExecutionPattern.FAN_OUT,
    inputs=["group_contexts"],  # Must be list
    retry_config=RetryConfig(max_attempts=2),
)
```

Input to fan-out stage must be a list. The stage executes once per item, and returns a list of outputs.

### Conditional Execution

Skip stages based on runtime conditions:

```python
StageDefinition(
    id="lyrics",
    stage=LyricsStage(),
    pattern=ExecutionPattern.CONDITIONAL,
    inputs=["audio"],
    condition=lambda ctx: ctx.get_state("has_lyrics", False),
    critical=False,  # Non-critical: pipeline continues if skipped
)
```

### Retry Configuration

```python
from twinklr.core.pipeline.definition import RetryConfig

StageDefinition(
    id="macro",
    stage=MacroPlannerStage(),
    retry_config=RetryConfig(
        max_attempts=3,
        initial_delay_ms=1000,
        backoff_multiplier=2.0,
        max_delay_ms=60000,
        retryable_errors=["timeout", "rate_limit"],  # Only retry these
    ),
)
```

### Context State Management

Share state between stages:

```python
class AudioAnalysisStage:
    async def execute(self, input, context):
        bundle = await analyze(input)
        
        # Store state for downstream stages
        context.set_state("has_lyrics", bundle.lyrics is not None)
        context.add_metric("duration_ms", bundle.timing.duration_ms)
        
        return StageResult.success(bundle)

class LyricsStage:
    async def execute(self, input, context):
        # Access state from upstream stage
        if not context.get_state("has_lyrics"):
            return StageResult.failure("No lyrics available")
        # ...
```

## Creating Custom Stages

Stages implement the `PipelineStage` protocol:

```python
from twinklr.core.pipeline import PipelineStage, StageResult, PipelineContext

class MyCustomStage:
    @property
    def name(self) -> str:
        return "my_stage"
    
    async def execute(
        self,
        input: MyInputType,
        context: PipelineContext,
    ) -> StageResult[MyOutputType]:
        try:
            # Access dependencies
            provider = context.provider
            config = context.job_config
            
            # Do work
            result = await my_logic(input, provider)
            
            # Track metrics
            context.add_metric("my_metric", 123)
            
            # Return success
            return StageResult.success(result, stage_name=self.name)
            
        except Exception as e:
            logger.exception("Stage failed", exc_info=e)
            return StageResult.failure(str(e), stage_name=self.name)
```

## Complete Example

See `packages/twinklr/core/pipeline/example_usage.py` for a complete working example that demonstrates:

- Sequential stages (audio analysis)
- Parallel stages (profile + lyrics)
- Conditional stages (lyrics only if available)
- Fan-out pattern (group planning)
- Retry configuration
- Context state management
- Metrics tracking

## Testing

The framework includes comprehensive tests in `tests/unit/pipeline/`:

- Pipeline definition validation
- Sequential execution
- Parallel execution
- Fan-out pattern
- Conditional stages
- Retry logic
- Error handling
- Context management

Run tests:

```bash
uv run pytest tests/unit/pipeline/ -v
```

## Design Principles

1. **Declarative over Imperative** - Define what to run, not how
2. **Explicit Dependencies** - No hidden state, all deps declared
3. **Type Safety** - Full mypy support with Protocol pattern
4. **Immutable Results** - StageResult is frozen Pydantic model
5. **Protocol Pattern** - No inheritance required, structural typing
6. **Dependency Injection** - All services via PipelineContext
7. **Error Recovery** - Errors captured in results, not exceptions
8. **Observable** - Built-in logging, metrics, and tracing

## Comparison to Frameworks

### vs. LangGraph

| Feature | Pipeline Framework | LangGraph |
|---------|-------------------|-----------|
| Complexity | ~500 LOC | ~5000+ LOC |
| Learning Curve | Minimal | Steep |
| Graph Visualization | No | Yes |
| Conditional Routing | Yes (conditions) | Yes (advanced) |
| Human-in-loop | No | Yes |
| Checkpointing | Manual | Built-in |
| Best For | Linear pipelines | Complex graphs |

### vs. Airflow/Prefect

| Feature | Pipeline Framework | Airflow/Prefect |
|---------|-------------------|-----------------|
| Deployment | In-process | Distributed |
| Scheduling | No | Yes |
| UI | No | Yes |
| Scale | Single machine | Multi-node |
| Best For | Local workflows | Production ETL |

## When to Use

✅ **Good fit:**
- 5-20 stage pipelines
- Clear stage dependencies
- Mostly linear with some parallelism
- Need automatic dependency resolution
- Want simple, understandable code

❌ **Not a good fit:**
- Complex branching logic (>10 conditional paths)
- Human-in-the-loop workflows
- Need graph visualization for stakeholders
- Multi-hour workflows needing checkpointing
- Distributed execution across machines

## Future Enhancements

Potential additions (not currently implemented):

- **Visualization** - Generate Mermaid/Graphviz diagrams from definition
- **Profiling** - Per-stage timing and resource usage
- **Streaming** - Output streaming for long-running stages
- **Checkpointing** - Save/resume from checkpoints
- **Rate Limiting** - Global rate limiter for LLM calls
- **DAG Validation UI** - Web-based pipeline editor

## Examples in Codebase

1. **Sequencer Pipeline** (`example_usage.py`)
   - Complete audio → planning → rendering pipeline
   - Demonstrates all patterns

2. **Stage Implementations** (`stages.py`)
   - Wrapping existing orchestrators as stages
   - Real-world integration examples

3. **Tests** (`tests/unit/pipeline/`)
   - Unit tests for all functionality
   - Reference for usage patterns
