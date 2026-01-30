# Phase 0: Async-First Agent Infrastructure Migration Guide

This document describes the Phase 0 migration to async-first agent infrastructure with comprehensive LLM observability.

## Overview

Phase 0 transforms the agent framework to be **async-first** while maintaining **100% backward compatibility** with existing synchronous code. The key additions are:

1. **AsyncAgentRunner** - Primary async implementation for agent execution
2. **LLM Call Logging** - Comprehensive logging of all LLM interactions
3. **Async LLM Provider** - Extended provider protocol with async methods
4. **Sync Wrappers** - Existing `AgentRunner` now wraps `AsyncAgentRunner`

## Breaking Changes

**None.** Phase 0 maintains full backward compatibility:

- `AgentRunner.run()` continues to work synchronously
- All existing tests pass without modification
- Existing orchestrator code works unchanged

## New Features

### 1. Async Agent Execution

For async contexts (FastAPI, asyncio applications), use `AsyncAgentRunner` directly:

```python
from twinklr.core.agents import AsyncAgentRunner

# Async execution
runner = AsyncAgentRunner(
    provider=provider,
    prompt_base_path=Path("prompts"),
    llm_logger=logger,  # Optional
)

result = await runner.run(spec=spec, variables=variables, state=state)
```

### 2. LLM Call Logging

All LLM interactions can now be logged for debugging and observability:

```python
from twinklr.core.agents.logging import create_llm_logger

# Create logger with factory
logger = create_llm_logger(
    enabled=True,
    output_dir=Path("artifacts/llm_logs"),
    run_id="run_20260128_123456",
    log_level="standard",  # minimal, standard, full
    format="yaml",         # yaml, json
    sanitize=True,         # Remove sensitive data
)

# Pass to runner
runner = AsyncAgentRunner(provider=provider, llm_logger=logger)

# Or use sync wrapper
runner = AgentRunner(provider=provider, llm_logger=logger)
```

### 3. Configuration

Add `llm_logging` to your `job_config.json`:

```json
{
  "agent": {
    "llm_logging": {
      "enabled": true,
      "log_level": "standard",
      "format": "yaml",
      "sanitize": true
    }
  }
}
```

### 4. Environment Variables

Override logging settings via environment:

| Variable | Values | Description |
|----------|--------|-------------|
| `TWINKLR_DISABLE_LLM_LOGGING` | `1`, `true` | Disable logging entirely |
| `TWINKLR_LLM_LOG_LEVEL` | `minimal`, `standard`, `full` | Override log detail level |
| `TWINKLR_LLM_LOG_FORMAT` | `yaml`, `json` | Override output format |

## Migration Steps

### For Existing Code (No Changes Required)

Existing synchronous code continues to work:

```python
# This still works exactly as before
from twinklr.core.agents import AgentRunner

runner = AgentRunner(provider=provider, prompt_base_path=path)
result = runner.run(spec=spec, variables=variables)
```

### To Add LLM Logging

1. Create a logger:
```python
from twinklr.core.agents.logging import create_llm_logger

logger = create_llm_logger(
    output_dir=Path("artifacts"),
    run_id="my_run",
)
```

2. Pass to runner:
```python
runner = AgentRunner(
    provider=provider,
    prompt_base_path=path,
    llm_logger=logger,  # Add this
)
```

3. Logs are written to `{output_dir}/{run_id}/llm_calls/`

### To Use Async Execution

For async applications:

```python
import asyncio
from twinklr.core.agents import AsyncAgentRunner

async def run_agents():
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=path)

    # Run multiple agents in parallel
    results = await asyncio.gather(
        runner.run(spec=spec1, variables=vars1),
        runner.run(spec=spec2, variables=vars2),
        runner.run(spec=spec3, variables=vars3),
    )
    return results
```

## Architecture

### Before Phase 0

```
AgentRunner (sync)
    └── LLMProvider.generate_json() (sync)
```

### After Phase 0

```
AsyncAgentRunner (async, primary)
    └── LLMProvider.generate_json_async() (async)
    └── LLMCallLogger (async file I/O)

AgentRunner (sync, wrapper)
    └── AsyncAgentRunner (via asyncio.run())
```

## Log Output Structure

Logs are organized by run:

```
artifacts/
└── {run_id}/
    └── llm_calls/
        ├── call_001_planner.yaml
        ├── call_002_judge.yaml
        └── summary.yaml
```

### Log Levels

| Level | Contents |
|-------|----------|
| `minimal` | Token counts, latency, model, success/failure |
| `standard` | + Prompts, responses (default) |
| `full` | + Full context, raw API payloads |

## Testing

Run async tests:

```bash
uv run pytest tests/unit/agents/test_async_runner.py -v
```

Run all agent tests:

```bash
uv run pytest tests/unit/agents/ -v
```

## Troubleshooting

### "Event loop is already running"

If you see this error, you're calling sync `AgentRunner.run()` from within an async context. Use `AsyncAgentRunner` directly instead:

```python
# Instead of:
runner = AgentRunner(provider=provider)
result = runner.run(spec=spec, variables=variables)  # Error in async context

# Use:
runner = AsyncAgentRunner(provider=provider)
result = await runner.run(spec=spec, variables=variables)
```

### Logs not appearing

1. Check `llm_logging.enabled` is `true` in config
2. Check environment variable `TWINKLR_DISABLE_LLM_LOGGING` is not set
3. Verify output directory is writable
4. Call `logger.flush()` or `await logger.flush_async()` to force write

### Performance considerations

- Use `enabled: false` in production if logging overhead is a concern
- Use `log_level: minimal` for production monitoring
- Use `log_level: full` only during debugging
