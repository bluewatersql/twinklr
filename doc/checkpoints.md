# Checkpoint System

The checkpoint system saves intermediate and final results during orchestration runs, enabling inspection of the multi-agent planning process.

## Checkpoint Types

### Core Checkpoints (Overwritten Each Iteration)
- **RAW**: Latest raw plan from planner agent (pre-validation)
- **EVALUATION**: Latest judge evaluation and decision
- **FINAL**: Final approved plan or best attempt (saved only at completion)

### Auxiliary Checkpoints
- **SEQUENCE**: Compiled DMX sequence data
- **AUDIO**: Audio analysis features

## Iteration-Specific Checkpoints (New)

Starting with the agent rewrite, all iterations are preserved for debugging and analysis.

### Naming Convention

```
{project_name}_{run_id}_iter{NN}_{checkpoint_type}.json
```

**Example:**
```
need_a_favor_a3f9b2c1_iter01_raw.json
need_a_favor_a3f9b2c1_iter01_evaluation.json
need_a_favor_a3f9b2c1_iter02_raw.json
need_a_favor_a3f9b2c1_iter02_evaluation.json
```

### Components

- **project_name**: From job config (e.g., "need_a_favor")
- **run_id**: Unique 8-character hex ID generated per orchestration run
- **iter{NN}**: Zero-padded iteration number (01, 02, 03, ...)
- **checkpoint_type**: `raw` or `evaluation`

## File Structure

```
artifacts/
└── {project_name}/
    └── checkpoints/
        ├── {project_name}_audio.json              # Audio features
        ├── {project_name}_sequence.json           # DMX sequence
        └── plans/
            ├── {project_name}_raw.json                        # Latest raw plan
            ├── {project_name}_evaluation.json                 # Latest evaluation
            ├── {project_name}_final.json                      # Final approved plan
            ├── {project_name}_{run_id}_iter01_raw.json        # Iteration 1 raw plan
            ├── {project_name}_{run_id}_iter01_evaluation.json # Iteration 1 evaluation
            ├── {project_name}_{run_id}_iter02_raw.json        # Iteration 2 raw plan
            ├── {project_name}_{run_id}_iter02_evaluation.json # Iteration 2 evaluation
            └── ...
```

## Checkpoint Contents

### Raw Plan (`raw`)
```json
{
  "run_id": "a3f9b2c1",
  "iteration": 1,
  "checkpoint_type": "raw",
  "plan": {
    "sections": [...],
    "song_structure": {...}
  }
}
```

### Evaluation (`evaluation`)
```json
{
  "run_id": "a3f9b2c1",
  "iteration": 1,
  "checkpoint_type": "evaluation",
  "evaluation": {
    "decision": "SOFT_FAIL",
    "score": 6,
    "reasoning": "...",
    "feedback": "..."
  },
  "plan_sections": 5,
  "score": 6,
  "decision": "SOFT_FAIL"
}
```

### Final Plan (`final`)
```json
{
  "status": "SUCCESS",
  "plan": {...},
  "evaluation": {...},
  "iterations": 3,
  "total_tokens": 15420,
  "duration_seconds": 12.5
}
```

## Usage

### Automatic Checkpointing

Checkpoints are saved automatically when `checkpoint: true` in job config:

```json
{
  "checkpoint": true,
  "output_dir": "artifacts/my_song"
}
```

### Reviewing Iterations

All iterations are preserved, allowing post-run analysis:

```bash
# List all raw plans for a run
ls artifacts/my_song/checkpoints/plans/*_iter*_raw.json

# List all evaluations for a run
ls artifacts/my_song/checkpoints/plans/*_iter*_evaluation.json

# View specific iteration
cat artifacts/my_song/checkpoints/plans/my_song_a3f9b2c1_iter02_evaluation.json
```

### Programmatic Access

```python
from twinklr.core.utils.checkpoint import CheckpointManager, CheckpointType

# Create manager
manager = CheckpointManager(job_config=job_config)

# Start run (generates unique ID)
run_id = manager.start_run()

# Save iteration checkpoint
manager.write_iteration_checkpoint(
    CheckpointType.RAW,
    {"plan": plan.model_dump()},
    iteration=1
)

# Save overwriting checkpoint
manager.write_checkpoint(
    CheckpointType.FINAL,
    {"status": "SUCCESS", "plan": plan.model_dump()}
)
```

## Benefits

1. **Full Audit Trail**: Every plan and evaluation is preserved
2. **Debugging**: Compare iterations to understand refinement process
3. **Analysis**: Study how the judge guides the planner over iterations
4. **Reproducibility**: Run ID links all artifacts from a single run
5. **Backward Compatible**: Existing FINAL/RAW/EVALUATION checkpoints still work

## Best Practices

- **Keep run_id in logs**: Include run ID in orchestration logs for traceability
- **Archive old runs**: Periodically clean up old iteration checkpoints
- **Use for debugging**: When a run fails, review all iterations to understand why
- **Compare scores**: Track score progression across iterations to tune thresholds
