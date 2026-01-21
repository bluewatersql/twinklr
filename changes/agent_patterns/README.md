# Agent Architecture Refactoring

**Status:** Design Phase  
**Date:** 2026-01-20  
**Updated:** 2026-01-21  
**Sprint Goal:** Simplify and enhance agents through patterns, abstraction, state management, and observability

## Overview

This directory contains the design and architecture documentation for refactoring the multi-agent orchestration system. The refactoring aims to:

1. **Simplify agents** by extending and using defined `agent_patterns`
2. **Abstract LLM providers** to support multiple providers (OpenAI, Claude, etc.)
3. **Implement state machine** pattern with comprehensive observability metrics
4. **Leverage conversations** within the multi-agent loop with unique conversation tracking
5. **Simplify refinement** by converting it to follow-up messages instead of a separate agent
6. **Implement structured feedback** with FIFO trimming for token limit management
7. **Enhance checkpointing** to include complete agent responses for debugging and step-by-step execution
8. **Add rich metadata** including confidence scores and reasoning traces to agent results

## Document Structure

### Core Design Documents

- **[design.md](./design_updated.md)** - Main design document with architecture overview, detailed design, implementation plan, and all enhancements
- **[provider_abstraction.md](./provider_abstraction_updated.md)** - LLM provider abstraction specification with retry strategies, conversation ID generation, and provider-specific quirks
- **[state_machine.md](./state_machine_updated.md)** - State machine pattern specification with observability metrics, duration tracking, and bottleneck analysis
- **[migration_guide.md](./migration_guide_updated.md)** - Step-by-step migration guide with example workflows and testing strategies

## Quick Start

### For Architects

Start with **[design.md](./design_updated.md)** for the complete architecture overview, design decisions, and enhancement specifications.

### For Implementers

1. Read **[design.md](./design_updated.md)** for context and understanding of all features
2. Review example workflows in **[migration_guide.md](./migration_guide_updated.md)** to see system behavior
3. Follow **[migration_guide.md](./migration_guide_updated.md)** for step-by-step implementation
4. Reference **[provider_abstraction.md](./provider_abstraction_updated.md)** and **[state_machine.md](./state_machine_updated.md)** for detailed specifications

### For Reviewers

Review **[design.md](./design_updated.md)** for architectural decisions and new features, then check specific specifications and example workflows as needed.

## Key Changes Summary

### Current Architecture

```
Orchestrator (532 LOC)
  ↓
StageCoordinator (286 LOC)
  ↓
Agents:
  - PlanGenerator
  - HeuristicValidator (non-agent)
  - ImplementationExpander
  - JudgeCritic
  - RefinementAgent (separate agent, ~200 LOC)
```

### Target Architecture

```
Orchestrator (with State Machine + Metrics + Feedback)
  ↓
Agents (using patterns):
  - PlannerAgent (Conversational, extends ConversationalStageExecutor)
  - HeuristicValidator (non-agent, unchanged)
  - ImplementationAgent (Conversational, extends ConversationalStageExecutor)
  - JudgeAgent (Non-Conversational, extends NonConversationalStageExecutor)
  - Refinement (follow-up messages, no separate agent)
```

### Key Improvements

1. **Provider Abstraction**: `LLMProvider` protocol replaces direct `OpenAIClient` dependencies
   - Provider-level retry handling (529s, rate limits)
   - Unique conversation ID generation pattern: `{agent_name}_iter{iteration}_{uuid}`
   - Provider-specific quirks documented (OpenAI, Claude)

2. **Agent Patterns**: All agents extend base executors (`ConversationalStageExecutor` or `NonConversationalStageExecutor`)
   - Enhanced `AgentResult` with confidence scores and reasoning traces
   - Conversational agents support follow-up messages

3. **State Machine with Observability**: Explicit state management with comprehensive metrics
   - Duration tracking per state
   - Token consumption tracking per state
   - Bottleneck analysis (slowest states, highest token consumers)
   - Metrics aggregation and reporting
   - Integration with existing token budget system

4. **Structured Feedback Management**: Accumulates feedback across iterations
   - FIFO trimming when approaching token limits
   - Feedback filtering by type (validation, soft failure, hard failure)
   - Feedback preservation in checkpoints

5. **Enhanced Checkpointing**: Complete orchestration state saved
   - State machine with metrics
   - Conversation IDs for resumption
   - **Complete agent responses** (data, metadata, confidence, reasoning)
   - Feedback manager state
   - Supports future step-by-step execution

6. **Simplified Refinement**: Refinement becomes follow-up messages, removing `RefinementAgent` (~200 LOC reduction)

## Example Workflows

The system supports multiple execution paths depending on validation and evaluation results:

### Happy Path
```
PLANNING → VALIDATING → IMPLEMENTING → JUDGING → SUCCEEDED
(First iteration success, ~27s, ~4100 tokens)
```

### Validation Failure
```
PLANNING → VALIDATING (fail) → PLANNING (with feedback) → VALIDATING → ...
(Feedback accumulated, same conversation for planner refinement)
```

### Soft Failure (Refine Implementation)
```
... → JUDGING (68/100) → IMPLEMENTING (refine) → JUDGING (88/100) → SUCCEEDED
(Follow-up message in same conversation)
```

### Hard Failure (Replan)
```
... → JUDGING (52/100) → PLANNING (new conversation) → ... → SUCCEEDED
(New conversation created with feedback)
```

### Budget Exhaustion
```
... → IMPLEMENTING → JUDGING → BUDGET_EXHAUSTED
(Existing budget system integration)
```

See **[migration_guide.md](./migration_guide_updated.md)** for detailed workflow examples with metrics.

## Implementation Timeline

- **Week 1**: Provider abstraction + Enhanced agent patterns (confidence, reasoning)
- **Week 2**: State machine with observability + Feedback management + Enhanced checkpointing
- **Week 3**: Refinement simplification + Testing + Workflow validation
- **Week 4**: Cleanup, documentation, finalization

## New Features Detail

### 1. Observability Metrics

State machine tracks comprehensive metrics:

```python
# Per-state metrics
metrics = state_machine.get_state_metrics(OrchestrationState.PLANNING)
# Returns: visit_count, total_duration, total_tokens, avg_duration, avg_tokens

# Bottleneck analysis
bottlenecks = state_machine.get_bottleneck_analysis()
# Returns: slowest_state, highest_token_state, per-iteration averages

# Formatted report
report = state_machine.format_metrics_report()
# Human-readable summary of all metrics
```

### 2. Structured Feedback Management

Feedback accumulates with intelligent trimming:

```python
feedback_manager.add_feedback(
    feedback_type=FeedbackType.VALIDATION_FAILURE,
    content="Plan duration too short...",
    iteration=1
)

# Get feedback with FIFO trimming
feedback = feedback_manager.get_feedback_for_prompt(
    max_tokens=2000,
    feedback_types=[FeedbackType.VALIDATION_FAILURE]
)
# Most recent feedback preserved when over limit
```

### 3. Enhanced Agent Metadata

All agent results include rich metadata:

```python
result = planner.generate_plan(context, iteration=1)
# result.confidence = 0.85  # Model's confidence score
# result.reasoning = "Generated balanced plan..."  # Model's reasoning
```

### 4. Conversation ID Pattern

Unique, pattern-based conversation IDs prevent reuse:

```python
conversation_id = generate_conversation_id("planner", iteration=1)
# Result: "planner_iter1_a3f4b2c1"
# Format: {agent_name}_iter{iteration}_{uuid}
```

### 5. Provider-Level Error Handling

Retry logic at provider level, graceful failures up stack:

```python
# Provider retries (network, 529s, rate limits)
response = provider.generate_json(...)  # Retries internally

# Application failures (validation, bad responses)
# Raise exceptions, let orchestrator handle
```

### 6. Complete Checkpoint State

Checkpoints include everything for debugging and resumption:

```python
checkpoint_manager.save_orchestration_state(
    state_machine=state_machine,  # With metrics
    planner_conversation_id="planner_iter1_a3f4b2c1",
    implementation_conversation_id="implementation_iter1_7b2c3d4e",
    agent_responses={
        "plan": AgentResult(...),  # Complete response
        "validation": ValidationResult(...),
        "implementation": AgentResult(...),
        "evaluation": AgentResult(...)
    },
    feedback_manager=feedback_manager  # With accumulated feedback
)
```

## Success Criteria

1. ✅ All agents extend appropriate base executors
2. ✅ `LLMProvider` abstraction supports OpenAI (Claude-ready)
3. ✅ State machine manages all flow with comprehensive metrics
4. ✅ Feedback accumulates with FIFO trimming working correctly
5. ✅ Checkpoints include complete agent responses
6. ✅ AgentResult includes confidence and reasoning
7. ✅ Refinement works via follow-up messages (no separate agent)
8. ✅ Code reduction: ~200-300 LOC
9. ✅ All tests passing
10. ✅ Token usage accurate and trackable per state
11. ✅ Observability metrics useful for optimization
12. ✅ All example workflows passing

## Testing Focus Areas

### Unit Tests
- Provider abstraction and retry logic
- State machine transitions and metrics calculation
- Feedback manager FIFO trimming
- Conversation ID generation uniqueness
- AgentResult metadata extraction

### Integration Tests
- Agent interactions with conversations
- State machine flow with metrics
- Feedback accumulation and injection
- Checkpoint serialization/restoration
- All example workflows

### End-to-End Tests
- Happy path (first iteration success)
- Validation failure with retry
- Soft failure with implementation refinement
- Hard failure with replanning
- Budget exhaustion
- Multiple feedback accumulation

## Related Documents

- Current orchestrator: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`
- Current agent patterns: `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`
- State machine consideration: `changes/futures/agent_state_machine.md`
- OpenAI client: `packages/blinkb0t/core/api/llm/openai/client.py`

## Benefits Summary

### Code Quality
- **Simplified**: Remove `RefinementAgent` (~200 LOC)
- **Consistent**: All agents follow same patterns
- **Maintainable**: Clear separation of concerns
- **Testable**: Easy to mock and test components

### Observability
- **Metrics**: Duration and tokens per state
- **Bottlenecks**: Identify optimization opportunities
- **Debugging**: Complete agent responses in checkpoints
- **Tracing**: Confidence and reasoning for analysis

### Flexibility
- **Provider Agnostic**: Easy to add Claude, other providers
- **Conversation Support**: Multi-turn interactions for refinement
- **Feedback Management**: Structured accumulation with smart trimming
- **Step Execution**: Future support via checkpointed responses

### Reliability
- **Error Handling**: Provider-level retries, graceful failures
- **State Management**: Explicit FSM prevents invalid transitions
- **Budget Control**: Integration with existing token budget system
- **Checkpointing**: Complete state preservation for recovery

## Questions?

For questions or clarifications, refer to:
- **Architecture decisions**: `design_updated.md`
- **Provider details**: `provider_abstraction_updated.md`
- **State machine details**: `state_machine_updated.md`
- **Implementation steps**: `migration_guide_updated.md`
- **Example workflows**: See workflows section in `migration_guide_updated.md`