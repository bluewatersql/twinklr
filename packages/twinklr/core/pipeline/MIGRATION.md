# Migration Guide: Refactoring to Pipeline Framework

This guide shows how to refactor `demo_sequencer_pipeline.py` to use the new pipeline framework.

## Current State (Manual Orchestration)

```python
# Stage 1: Audio Analysis
bundle = await analyzer.analyze(audio_path)

# Stage 2: Phase 1 Agents (parallel with asyncio.gather)
audio_task = run_audio_profile(...)
lyrics_task = run_lyrics_async(...)
audio_profile, lyric_context = await asyncio.gather(audio_task, lyrics_task)

# Stage 3: MacroPlanner
result = await orchestrator.run(planning_context)

# Stage 4: GroupPlanner (sequential loop)
for group in display_groups:
    group_plan = await orchestrator.run_single_group(...)
    group_plans.append(group_plan)
```

**Problems:**
- Manual dependency tracking
- Explicit parallelism with `asyncio.gather`
- No retry logic
- No standardized error handling
- Hard to add new stages
- Group planner runs sequentially (should be parallel)

## Target State (Pipeline Framework)

```python
# Define pipeline once
pipeline = create_sequencer_pipeline(display_groups)

# Execute
executor = PipelineExecutor()
result = await executor.execute(pipeline, audio_path, context)

# Access outputs
macro_plan = result.outputs["macro"]
group_plans = result.outputs["groups"]
```

**Benefits:**
- Automatic dependency resolution
- Automatic parallelism detection
- Built-in retry logic
- Standardized error handling
- Easy to add stages
- Group planner runs in parallel (fan-out)

## Step-by-Step Migration

### Step 1: Create Stage Wrappers

Wrap each logical unit of work as a stage. See `packages/twinklr/core/pipeline/stages.py` for complete examples.

**Before:**
```python
# Inline audio analysis
analyzer = AudioAnalyzer(app_config, job_config)
bundle = await analyzer.analyze(audio_path)
```

**After:**
```python
# Wrapped as stage
class AudioAnalysisStage:
    @property
    def name(self) -> str:
        return "audio_analysis"
    
    async def execute(self, input: str, context: PipelineContext) -> StageResult[SongBundle]:
        analyzer = AudioAnalyzer(context.app_config, context.job_config)
        bundle = await analyzer.analyze(input)
        
        # Store state for conditional stages
        context.set_state("has_lyrics", bundle.lyrics is not None)
        
        return StageResult.success(bundle, stage_name=self.name)
```

### Step 2: Define Pipeline

Create a function that returns `PipelineDefinition`:

```python
def create_sequencer_pipeline(display_groups: list[dict]) -> PipelineDefinition:
    return PipelineDefinition(
        name="twinklr_sequencer",
        stages=[
            # Stage 1: Audio
            StageDefinition("audio", AudioAnalysisStage()),
            
            # Stage 2: Profile + Lyrics (parallel)
            StageDefinition("profile", AudioProfileStage(), inputs=["audio"]),
            StageDefinition(
                "lyrics",
                LyricsStage(),
                pattern=ExecutionPattern.CONDITIONAL,
                inputs=["audio"],
                condition=lambda ctx: ctx.get_state("has_lyrics"),
            ),
            
            # Stage 3: Macro Planning
            StageDefinition(
                "macro",
                MacroPlannerStage(display_groups),
                inputs=["profile", "lyrics"],
            ),
            
            # Stage 4: Group Planning (fan-out)
            StageDefinition(
                "group_contexts",
                GroupPlanningContextBuilder(display_groups),
                inputs=["macro", "profile", "lyrics"],
            ),
            StageDefinition(
                "groups",
                GroupPlannerStage(),
                pattern=ExecutionPattern.FAN_OUT,
                inputs=["group_contexts"],
            ),
        ],
    )
```

### Step 3: Replace Manual Execution

**Before:**
```python
# Manual execution with explicit error handling
try:
    bundle = await analyzer.analyze(audio_path)
except Exception as e:
    print(f"Failed: {e}")
    return

try:
    audio_profile = await run_audio_profile(...)
except Exception as e:
    print(f"Failed: {e}")
    return

# ... etc
```

**After:**
```python
# Declarative execution
pipeline = create_sequencer_pipeline(display_groups)
executor = PipelineExecutor()
result = await executor.execute(pipeline, audio_path, context)

if result.success:
    print("Pipeline completed!")
else:
    print(f"Failed stages: {result.failed_stages}")
```

### Step 4: Create Pipeline Context

**Before:**
```python
# Dependencies passed to each function
provider = OpenAIProvider(api_key=api_key)
llm_logger = create_llm_logger(...)

# Pass to each call
profile = await run_audio_profile(
    bundle, provider, llm_logger, model, temperature
)
```

**After:**
```python
# Dependencies in context (once)
context = PipelineContext(
    provider=provider,
    app_config=app_config,
    job_config=job_config,
    llm_logger=llm_logger,
    output_dir=output_dir,
)

# Stages access from context
async def execute(self, input, context):
    profile = await run_audio_profile(
        input,
        context.provider,
        context.llm_logger,
        context.job_config.agent.plan_agent.model,
    )
```

### Step 5: Handle Group Planning Fan-Out

**Before:**
```python
# Sequential loop
group_plans = []
for group in display_groups:
    ctx = GroupPlanningContext(
        audio_profile=audio_profile,
        macro_plan=macro_plan,
        group_id=group["role_key"],
        # ...
    )
    result = await orchestrator.run_single_group(ctx)
    group_plans.append(result.plan)
```

**After:**
```python
# Builder stage creates list of contexts
class GroupPlanningContextBuilder:
    async def execute(self, input, context):
        contexts = [
            GroupPlanningContext(
                audio_profile=input["profile"],
                macro_plan=input["macro"],
                group_id=group["role_key"],
                # ...
            )
            for group in self.display_groups
        ]
        return StageResult.success(contexts)

# Fan-out stage executes in parallel
StageDefinition(
    "groups",
    GroupPlannerStage(),
    pattern=ExecutionPattern.FAN_OUT,
    inputs=["group_contexts"],  # List from builder
)
```

### Step 6: Access Results

**Before:**
```python
# Results stored in local variables
audio_bundle = ...  # from stage 1
audio_profile = ... # from stage 2
macro_plan = ...    # from stage 3
group_plans = ...   # from stage 4
```

**After:**
```python
# Results in pipeline result
result = await executor.execute(pipeline, audio_path, context)

audio_bundle = result.outputs["audio"]
audio_profile = result.outputs["profile"]
macro_plan = result.outputs["macro"]
group_plans = result.outputs["groups"]  # List of GroupPlan
```

## Full Refactored Script

See `packages/twinklr/core/pipeline/example_usage.py` for a complete working example.

Key differences:
- ~100 lines vs ~480 lines in original
- Declarative pipeline definition
- Automatic parallelism
- Built-in error handling
- Easier to extend

## Testing Your Migration

1. **Validate pipeline:**
   ```python
   errors = pipeline.validate()
   if errors:
       print(f"Validation errors: {errors}")
   ```

2. **Run both versions side-by-side:**
   - Keep old script as `demo_sequencer_pipeline_old.py`
   - Create new version with pipeline framework
   - Compare outputs to ensure equivalence

3. **Check parallelism:**
   - Add timing logs to stages
   - Verify profile + lyrics run concurrently
   - Verify group planners run concurrently

4. **Verify error handling:**
   - Inject failures into stages
   - Check fail-fast behavior
   - Check retry logic

## Common Pitfalls

### 1. Fan-out input must be a list

**Wrong:**
```python
# Builder returns single dict
return StageResult.success({"contexts": contexts})
```

**Correct:**
```python
# Builder returns list directly
return StageResult.success(contexts)  # contexts is list
```

### 2. Multiple inputs require dict

**Wrong:**
```python
# Stage expects tuple
def execute(self, input: tuple, context):
    profile, lyrics = input  # Won't work
```

**Correct:**
```python
# Stage expects dict
def execute(self, input: dict, context):
    profile = input["profile"]
    lyrics = input.get("lyrics")  # May be None
```

### 3. Conditional stages need state

**Wrong:**
```python
# Condition checks input directly
condition=lambda ctx: ctx.get_state("lyrics") is not None
```

**Correct:**
```python
# Upstream stage stores state
class AudioAnalysisStage:
    async def execute(self, input, context):
        # ...
        context.set_state("has_lyrics", bundle.lyrics is not None)
        return StageResult.success(bundle)

# Condition checks state
condition=lambda ctx: ctx.get_state("has_lyrics", False)
```

### 4. Don't raise exceptions in stages

**Wrong:**
```python
async def execute(self, input, context):
    if not valid:
        raise ValueError("Invalid input")
```

**Correct:**
```python
async def execute(self, input, context):
    if not valid:
        return StageResult.failure("Invalid input", stage_name=self.name)
```

## Gradual Migration

You don't have to migrate everything at once:

1. **Phase 1**: Migrate audio analysis stage
2. **Phase 2**: Add profile + lyrics with parallel execution
3. **Phase 3**: Add macro planner
4. **Phase 4**: Add group planner with fan-out
5. **Phase 5**: Add future stages (assets, rendering, export)

Each phase can be tested independently.

## Next Steps

1. Review `example_usage.py` for complete working example
2. Review `stages.py` for stage implementation patterns
3. Run tests: `uv run pytest tests/unit/pipeline/ -v`
4. Start migration with audio analysis stage
5. Add stages incrementally
6. Compare outputs with original script

## Questions?

Common questions addressed in `README.md`:
- How do I add retry logic?
- How do I skip stages conditionally?
- How do I share state between stages?
- How do I track metrics?
- When should I use fan-out vs parallel?
