# agent_patterns v3

This is a clean-slate redesign of `agent_patterns` with one guiding principle:

> **Agents are configuration, not classes.**  
> The only thing that typically differentiates one agent from another is the prompt pack + output schema.

## What this module contains

- `AgentSpec[T]`: data-only configuration for an agent
- `AgentRunner`: a single execution engine for *all* agents
- `PromptPackLoader`: loads prompt packs from disk
- `PromptRenderer`: renders templates (Jinja2 StrictUndefined by default)
- `AgentState`: holds conversation IDs so conversational agents can refine without re-sending history
- `AgentResult[T]`: a strict, typed result envelope with usage + metadata
- Optional `AgentRegistry`: map agent names → specs

## What this module intentionally does NOT contain

- Orchestration / state machine logic
- Checkpoint persistence
- Feedback management policies
- Provider-specific retry logic
- Heavy budgeting logic

Those belong in their own modules/layers and plug into `AgentRunner` through small interfaces.

---

## Prompt packs

A prompt pack is a directory under a base folder (e.g. `prompts/`):

```
prompts/
  planner/
    system.j2            # required
    developer.j2         # optional
    user.j2              # optional (template for the user message)
    examples.jsonl       # optional (few-shot messages)
```

### `system.j2` (required)
Your system prompt template.

### `developer.j2` (optional)
“Contracts”, formatting requirements, JSON-only constraints, tool policies, etc.

### `user.j2` (optional)
If provided, it becomes the **user message** (after rendering).  
If omitted, the runner sends a JSON blob like:

```json
{"context": <context>, "feedback": "...optional..."}
```

### `examples.jsonl` (optional)
Each line must be JSON: `{"role": "...", "content": "..."}`.  
These messages are inserted between developer and user messages.

---

## Template rendering: Jinja2 strict by default

`PromptRenderer` tries to use Jinja2 with `StrictUndefined`:

- missing variables raise immediately (fail-fast)
- no silent empty strings

If Jinja2 is not available, it falls back to a **strict `$var` renderer**:
- `$name` substitutes variables
- `$$` escapes to `$`
- missing variables raise `KeyError`

### Standard variables available to all prompts

Every run provides:

- `agent_name`
- `iteration` (may be None)
- `feedback` (may be None)
- `context` (the shaped context object)

You can provide more variables via:
- `AgentSpec.default_vars`
- `AgentRunner.run(..., extra_vars={...})`

---

## Canonical call signature

You run any agent through **one** runner call:

```python
result, state = runner.run(
    spec=planner_spec,
    context=my_context,
    state=state,           # optional; returned updated
    iteration=0,           # recommended for conversational agents
    feedback=None,         # optional
    budget=None,           # optional override
    extra_vars={"now": "..."}  # optional
)
```

You never implement an “agent class”.

---

## Conversation support

Conversation is just a mode flag on `AgentSpec`:

- `AgentMode.SINGLE_TURN`
- `AgentMode.CONVERSATION`

### How it works

- `AgentState` stores a `conversation_id` per agent name.
- For conversational agents:
  - First call starts a conversation using the system prompt.
  - Follow-ups use the stored `conversation_id`.

### Resetting a conversation
To force a fresh conversation:

```python
state.clear_conversation("planner")
```

---

## Schema validation + schema repair

- The runner validates the provider response using your `response_model` (Pydantic).
- If validation fails, it performs a small **schema repair loop**:
  - builds a deterministic “repair” user message with:
    - the validation errors
    - the invalid prior response (truncated)
    - “Return ONLY valid JSON”
  - retries up to `schema_repair_attempts` (default 1)

Provider-level retries (429/5xx/529/network) should be handled inside the provider.

---

## Budgeting & context shaping

The runner calls an injected `ContextShaper`:

```python
shaped = shaper.shape(agent=spec, context=context, budget=budget or spec.budget)
```

`ShapedContext` contains:
- `data`: the shaped context used for prompts
- `stats`: token estimates / reduction pct / notes

The runner records shaping stats under `AgentResult.metadata["shaping"]`.

Default is `IdentityContextShaper` (no changes).

---

## AgentResult: stable output envelope

`AgentResult[T]` includes:

- `success`, `data`, `error` (with strict invariants)
- `usage` (prompt/completion/total)
- `duration_seconds`
- `conversation_id`
- `confidence`/`reasoning` (if present in provider content)
- `metadata` (stable keys for downstream checkpointing/metrics)

---

## Minimal example

```python
from pydantic import BaseModel
from agent_patterns_v3 import (
    AgentRunner, AgentSpec, AgentMode, PromptPackLoader, PromptPackRef,
    AgentState, AgentRegistry
)

class Plan(BaseModel):
    steps: list[str]

provider = ...  # implements LLMProvider
loader = PromptPackLoader("prompts")
runner = AgentRunner(provider=provider, prompt_loader=loader)

planner = AgentSpec(
    name="planner",
    prompt_pack=PromptPackRef("planner"),
    response_model=Plan,
    mode=AgentMode.CONVERSATION,
    model="gpt-5",
    schema_repair_attempts=2,
)

state = AgentState()
result, state = runner.run(spec=planner, context={"goal": "do the thing"}, state=state, iteration=0)

if result.success:
    print(result.data.steps)
else:
    print("ERROR:", result.error)
```

---

## Adding a new agent

1. Create a new prompt pack folder under `prompts/<agent_name>/`
2. Add `system.j2` (required)
3. Optionally add `developer.j2`, `user.j2`, `examples.jsonl`
4. Create a Pydantic model for the output schema
5. Register a new `AgentSpec` pointing at the prompt pack and schema

No new executor classes. No boilerplate.
