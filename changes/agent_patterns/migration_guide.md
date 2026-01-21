# Migration Guide: Agent Architecture Refactoring

**Status:** Design Phase  
**Date:** 2026-01-20  
**Updated:** 2026-01-21  
**Related:** `design.md`, `provider_abstraction.md`, `state_machine.md`

## Overview

This guide provides step-by-step instructions for migrating from the current agent architecture to the new simplified, pattern-based architecture with enhanced observability and feedback management.

## Example Workflows

Before diving into migration steps, here are example workflows showing how the system behaves in different scenarios:

### Workflow 1: Happy Path (First Iteration Success)

```
INITIALIZED
  ↓ (0.0s, 0 tokens)
PLANNING
  ├─ PlannerAgent creates conversation: planner_iter1_a3f4b2c1
  ├─ Generate plan (8.5s, 1200 tokens)
  ├─ Confidence: 0.85
  └─ Reasoning: "Generated balanced plan with clear energy progression"
  ↓ (8.5s, 1200 tokens)
VALIDATING
  ├─ HeuristicValidator checks plan
  ├─ All heuristics pass
  └─ (1.2s, 0 tokens - non-LLM)
  ↓
IMPLEMENTING
  ├─ ImplementationAgent creates conversation: implementation_iter1_7b2c3d4e
  ├─ Expand to detailed implementation (12.3s, 2100 tokens)
  ├─ Confidence: 0.80
  └─ Reasoning: "Expanded all segments with timing and positioning"
  ↓ (12.3s, 2100 tokens)
JUDGING
  ├─ JudgeAgent evaluates (single-turn, 5.2s, 800 tokens)
  ├─ Overall Score: 92/100
  ├─ pass_threshold: True
  └─ Confidence: 0.90
  ↓ (5.2s, 800 tokens)
SUCCEEDED

Final Metrics:
- Total Duration: 27.2s
- Total Tokens: 4,100
- Iterations: 1
```

### Workflow 2: Validation Failure Path (Retry with Feedback)

```
INITIALIZED
  ↓
PLANNING (Iteration 1)
  ├─ PlannerAgent creates conversation: planner_iter1_a3f4b2c1
  ├─ Generate plan (7.8s, 1100 tokens)
  └─ Plan has 3 short segments for 4-minute song
  ↓ (7.8s, 1100 tokens)
VALIDATING
  ├─ HeuristicValidator checks plan
  ├─ FAIL: Total duration 180s < minimum 220s
  ├─ FeedbackManager adds:
  │   Type: VALIDATION_FAILURE
  │   Content: "Plan duration too short. Need 220-250s..."
  └─ (1.0s, 0 tokens)
  ↓
PLANNING (Iteration 2, with feedback)
  ├─ PlannerAgent refine_plan() via follow-up message
  ├─ Same conversation: planner_iter1_a3f4b2c1
  ├─ Feedback injected into user message
  ├─ Generate refined plan (6.5s, 900 tokens)
  └─ Plan now has 5 segments, 240s duration
  ↓ (6.5s, 900 tokens)
VALIDATING
  ├─ HeuristicValidator checks plan
  ├─ All heuristics pass
  └─ (1.1s, 0 tokens)
  ↓
IMPLEMENTING
  ├─ ImplementationAgent creates conversation: implementation_iter2_8c3d4e5f
  ├─ [continues to success...]
  
Final Metrics:
- Total Duration: 35.4s
- Total Tokens: 5,300
- Iterations: 2
- Most Common Transition: VALIDATING → PLANNING (1x)
```

### Workflow 3: Soft Failure Path (Refine Implementation)

```
INITIALIZED
  ↓
PLANNING (Iteration 1)
  ├─ Generate plan (8.2s, 1150 tokens)
  ↓
VALIDATING
  ├─ Pass (1.0s, 0 tokens)
  ↓
IMPLEMENTING
  ├─ ImplementationAgent creates conversation: implementation_iter1_7b2c3d4e
  ├─ Expand implementation (11.5s, 2000 tokens)
  ↓
JUDGING
  ├─ JudgeAgent evaluates (5.0s, 750 tokens)
  ├─ Overall Score: 68/100
  ├─ pass_threshold: False
  ├─ Issues:
  │   - Energy matching: 65/100 (needs improvement)
  │   - Timing precision: 82/100 (acceptable)
  │   - Spatial utilization: 60/100 (needs improvement)
  ├─ FailureAnalysis: fix_strategy="refine_implementation" (soft failure)
  ├─ FeedbackManager adds:
  │   Type: JUDGE_SOFT_FAILURE
  │   Content: "Implementation scored 68/100. Main issues:\n
  │              - Energy matching (65): Improve build-ups...\n
  │              - Spatial utilization (60): Diversify positions..."
  └─ (5.0s, 750 tokens)
  ↓
IMPLEMENTING (same iteration, refinement)
  ├─ ImplementationAgent refine_implementation() via follow-up
  ├─ Same conversation: implementation_iter1_7b2c3d4e
  ├─ Feedback injected into user message
  ├─ Refine based on feedback (9.8s, 1500 tokens)
  └─ Improved energy builds and spatial variety
  ↓ (9.8s, 1500 tokens)
JUDGING
  ├─ JudgeAgent evaluates (4.8s, 720 tokens)
  ├─ Overall Score: 88/100
  ├─ pass_threshold: True
  └─ All criteria improved
  ↓ (4.8s, 720 tokens)
SUCCEEDED

Final Metrics:
- Total Duration: 45.1s
- Total Tokens: 6,870
- Iterations: 1 (refinement doesn't increment)
- Slowest State: IMPLEMENTING (avg: 10.65s)
- Highest Tokens: IMPLEMENTING (avg: 1750)
```

### Workflow 4: Hard Failure Path (Replan)

```
INITIALIZED
  ↓
PLANNING (Iteration 1)
  ├─ Generate plan (8.0s, 1200 tokens)
  ├─ Plan: Aggressive strobing throughout
  ↓
VALIDATING
  ├─ Pass (1.0s, 0 tokens)
  ↓
IMPLEMENTING
  ├─ Expand implementation (12.0s, 2100 tokens)
  ↓
JUDGING
  ├─ Evaluate (5.2s, 800 tokens)
  ├─ Overall Score: 52/100
  ├─ pass_threshold: False
  ├─ Issues:
  │   - Structural coherence: 48/100 (plan fundamentally flawed)
  │   - Energy matching: 55/100
  │   - Movement diversity: 58/100
  ├─ FailureAnalysis: fix_strategy="replan" (hard failure)
  ├─ FeedbackManager adds:
  │   Type: JUDGE_HARD_FAILURE
  │   Content: "Plan scored 52/100. Critical structural issues:\n
  │              - Strobing overused (no contrast/dynamics)\n
  │              - Missing emotional arc\n
  │              - Need complete rethink of approach"
  └─ (5.2s, 800 tokens)
  ↓
PLANNING (Iteration 2, with feedback)
  ├─ PlannerAgent creates NEW conversation: planner_iter2_c4d5e6f7
  ├─ Feedback from JUDGE_HARD_FAILURE injected
  ├─ Generate new plan (8.5s, 1300 tokens)
  └─ Plan: Balanced approach with build-ups and releases
  ↓ (8.5s, 1300 tokens)
VALIDATING
  ├─ Pass (1.1s, 0 tokens)
  ↓
IMPLEMENTING
  ├─ ImplementationAgent creates NEW conversation: implementation_iter2_d5e6f7g8
  ├─ Expand implementation (11.8s, 2050 tokens)
  ↓
JUDGING
  ├─ Evaluate (5.0s, 780 tokens)
  ├─ Overall Score: 87/100
  ├─ pass_threshold: True
  ↓ (5.0s, 780 tokens)
SUCCEEDED

Final Metrics:
- Total Duration: 53.1s
- Total Tokens: 8,330
- Iterations: 2
- State Visits: PLANNING(2), VALIDATING(2), IMPLEMENTING(2), JUDGING(2)
```

### Workflow 5: Budget Exhaustion

```
INITIALIZED
  ↓
PLANNING (Iteration 1)
  ├─ Generate plan (8.0s, 1200 tokens)
  ├─ Budget: 1200/5000 used
  ↓
VALIDATING → PLANNING (Iteration 2)
  ├─ Refine plan (7.5s, 1100 tokens)
  ├─ Budget: 2300/5000 used
  ↓
VALIDATING → IMPLEMENTING
  ├─ Expand implementation (12.0s, 2100 tokens)
  ├─ Budget: 4400/5000 used
  ↓
JUDGING
  ├─ Evaluate (5.0s, 750 tokens)
  ├─ Score: 72/100 (soft failure)
  ├─ Budget: 5150/5000 used ⚠ EXHAUSTED
  ↓
BUDGET_EXHAUSTED

Result:
- Final State: BUDGET_EXHAUSTED
- Reason: Token budget exceeded during judging
- Last successful state: JUDGING (incomplete)
- Recommendation: Increase budget or simplify prompts
```

### Workflow 6: Multiple Feedback Accumulation

```
INITIALIZED
  ↓
PLANNING (Iteration 1)
  ├─ Generate plan (8.0s, 1200 tokens)
  ↓
VALIDATING
  ├─ FAIL: Duration too short
  ├─ FeedbackManager: Add VALIDATION_FAILURE #1
  ↓
PLANNING (Iteration 2)
  ├─ Feedback: Previous 1 entry (VALIDATION_FAILURE)
  ├─ Refine plan (7.0s, 1000 tokens)
  ↓
VALIDATING
  ├─ FAIL: Not enough contrast
  ├─ FeedbackManager: Add VALIDATION_FAILURE #2
  ↓
PLANNING (Iteration 3)
  ├─ Feedback: Previous 2 entries (both VALIDATION_FAILURE)
  ├─ FeedbackManager formats with FIFO trimming if needed
  ├─ Refine plan (7.2s, 1050 tokens)
  ↓
VALIDATING → IMPLEMENTING → JUDGING
  ├─ Score: 70/100 (soft failure)
  ├─ FeedbackManager: Add JUDGE_SOFT_FAILURE #3
  ↓
IMPLEMENTING (refinement)
  ├─ Feedback: Only JUDGE_SOFT_FAILURE (filtered by type)
  ├─ Refine implementation (9.5s, 1400 tokens)
  ↓
JUDGING → SUCCEEDED

Feedback Summary:
- Total Entries: 3
- By Type:
  - VALIDATION_FAILURE: 2
  - JUDGE_SOFT_FAILURE: 1
- Iterations with Feedback: 3
```

## Migration Phases

### Phase 1: Provider Abstraction (Week 1)

**Goal**: Abstract LLM provider without breaking existing functionality.

#### Step 1.1: Create Provider Protocol

1. Create `packages/blinkb0t/core/api/llm/provider.py`:
   - Define `LLMProvider` protocol
   - Define `TokenUsage`, `ResponseMetadata`, `LLMResponse` dataclasses
   - Define `ProviderType` enum
   - Add `LLMProviderError` exception

2. Create `packages/blinkb0t/core/api/llm/utils.py`:
   - Implement `generate_conversation_id()` function

3. Create `packages/blinkb0t/core/api/llm/openai/provider.py`:
   - Implement `OpenAIProvider` class
   - Wrap existing `OpenAIClient` functionality
   - Implement conversation management
   - Add provider-level retry handling for 529s, rate limits

#### Step 1.2: Update Agent Patterns

1. Update `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`:
   - Update `AgentResult` to include `confidence` and `reasoning`
   - Change `StageExecutor.__init__` to accept `LLMProvider` instead of `OpenAIClient`
   - Update `execute_llm_call` to use provider interface

#### Step 1.3: Update Agents (Gradual)

1. Update `PlanGenerator` → `PlannerAgent`:
   ```python
   # Before
   def __init__(self, job_config: JobConfig, openai_client: OpenAIClient):
       self.openai_client = openai_client
   
   # After
   def __init__(self, job_config: JobConfig, llm_provider: LLMProvider):
       self.llm_provider = llm_provider
   ```

2. Update `ImplementationExpander` → `ImplementationAgent` similarly
3. Update `JudgeCritic` → `JudgeAgent` similarly

#### Step 1.4: Update Orchestrator

1. Update `AgentOrchestrator.__init__`:
   ```python
   # Before
   self.openai_client = OpenAIClient(api_key=api_key)
   plan_generator = PlanGenerator(job_config, self.openai_client)
   
   # After
   self.llm_provider = OpenAIProvider(api_key=api_key)
   planner = PlannerAgent(job_config, self.llm_provider)
   ```

#### Step 1.5: Testing

- Run existing tests (should pass)
- Add tests for `OpenAIProvider`
- Verify token tracking works correctly
- Test retry behavior for 529 errors

**Checkpoint**: All tests passing, provider abstraction complete.

---

### Phase 2: Enhanced Agent Patterns (Week 1-2)

**Goal**: Refactor agents to use conversational and non-conversational executors with enhanced metadata.

#### Step 2.1: Update AgentResult

1. Update `agent_patterns.py`:
   - Add `confidence: float | None` field
   - Add `reasoning: str | None` field

#### Step 2.2: Create Conversational Executors

1. Update `agent_patterns.py`:
   - Add `ConversationalStageExecutor` class
   - Add `NonConversationalStageExecutor` class
   - Implement conversation management methods
   - Use `generate_conversation_id()` for unique IDs

#### Step 2.3: Refactor Planner Agent

1. Rename `PlanGenerator` → `PlannerAgent`
2. Extend `ConversationalStageExecutor`:
   ```python
   class PlannerAgent(ConversationalStageExecutor):
       def generate_plan(self, context, iteration) -> AgentResult[AgentPlan]:
           return self.execute_with_conversation(context, AgentPlan, iteration)
       
       def refine_plan(self, feedback) -> AgentResult[AgentPlan]:
           return self.add_followup(feedback, AgentPlan)
   ```

3. Update prompts to request confidence and reasoning in JSON response

#### Step 2.4: Refactor Implementation Agent

1. Rename `ImplementationExpander` → `ImplementationAgent`
2. Extend `ConversationalStageExecutor`
3. Add `refine_implementation()` method
4. Update prompts for confidence and reasoning

#### Step 2.5: Refactor Judge Agent

1. Rename `JudgeCritic` → `JudgeAgent`
2. Extend `NonConversationalStageExecutor`
3. Keep single-turn evaluation logic
4. Add confidence and reasoning to evaluation

#### Step 2.6: Update Imports

1. Update all imports:
   ```python
   # Before
   from blinkb0t.core.agents.moving_heads.plan_generator import PlanGenerator
   
   # After
   from blinkb0t.core.agents.moving_heads.planner_agent import PlannerAgent
   ```

#### Step 2.7: Testing

- Update tests to use new class names
- Test conversational methods
- Test confidence and reasoning extraction
- Verify backward compatibility

**Checkpoint**: All agents refactored, enhanced metadata working, tests passing.

---

### Phase 3: State Machine with Observability (Week 2)

**Goal**: Implement state machine with comprehensive metrics tracking.

#### Step 3.1: Create State Machine

1. Create `packages/blinkb0t/core/agents/moving_heads/state_machine.py`:
   - Implement `OrchestrationStateMachine` class
   - Define state transitions
   - Add transition validation
   - Add metrics tracking (duration, tokens)
   - Implement observability methods:
     - `get_state_metrics()`
     - `get_all_state_metrics()`
     - `get_total_metrics()`
     - `get_bottleneck_analysis()`
     - `format_metrics_report()`

#### Step 3.2: Integrate into Orchestrator

1. Add state machine to `AgentOrchestrator`:
   ```python
   def __init__(self, job_config: JobConfig):
       self.state_machine = OrchestrationStateMachine()
       self.state_machine.max_iterations = job_config.agent.max_iterations
   ```

2. Replace iteration loop with state machine:
   ```python
   while not self.state_machine.is_terminal():
       state = self.state_machine.current_state
       
       # Track metrics
       start_time = time.time()
       tokens_before = self.llm_provider.get_token_usage().total_tokens
       
       if state == OrchestrationState.PLANNING:
           result = self._execute_planning()
           duration = time.time() - start_time
           tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
           
           self.state_machine.transition(
               next_state,
               duration_seconds=duration,
               tokens_consumed=tokens
           )
   ```

3. Log metrics report at end:
   ```python
   logger.info("\n" + self.state_machine.format_metrics_report())
   ```

#### Step 3.3: Integrate with Existing Budget System

1. Check budget using existing system:
   ```python
   if self.token_budget_manager.is_exhausted():
       self.state_machine.transition(
           OrchestrationState.BUDGET_EXHAUSTED,
           reason="Token budget exhausted"
       )
   ```

#### Step 3.4: Add Checkpointing

1. Update `CheckpointManager`:
   - Update `save_orchestration_state()` to include metrics
   - Update `load_orchestration_state()` to restore metrics

2. Update `Orchestrator`:
   - Save state machine in checkpoints
   - Restore state machine on resume

#### Step 3.5: Testing

- Test state transitions
- Test invalid transitions (should raise errors)
- Test metrics calculation
- Test bottleneck analysis
- Test checkpointing/restoration with metrics
- Test iteration limits

**Checkpoint**: State machine integrated, metrics working, flow control simplified.

---

### Phase 4: Feedback Management (Week 2)

**Goal**: Implement structured feedback accumulation with FIFO trimming.

#### Step 4.1: Create Feedback Manager

1. Create `packages/blinkb0t/core/agents/moving_heads/feedback_manager.py`:
   - Implement `FeedbackType` enum
   - Implement `FeedbackEntry` dataclass
   - Implement `FeedbackManager` class
   - Add FIFO trimming logic in `get_feedback_for_prompt()`
   - Add feedback summary methods

#### Step 4.2: Integrate with Orchestrator

1. Add feedback manager to `AgentOrchestrator`:
   ```python
   def __init__(self, job_config: JobConfig):
       self.feedback_manager = FeedbackManager(
           max_feedback_tokens=2000,
           model=job_config.agent.model
       )
   ```

2. Add feedback on failures:
   ```python
   # Validation failure
   self.feedback_manager.add_feedback(
       feedback_type=FeedbackType.VALIDATION_FAILURE,
       content=validation_result.failure_message,
       iteration=self.state_machine.iteration_count
   )
   
   # Judgesoftfailure
   self.feedback_manager.add_feedback(
       feedback_type=FeedbackType.JUDGE_SOFT_FAILURE,
       content=self._build_implementation_feedback(...),
       iteration=self.state_machine.iteration_count
   )
   ```

3. Inject feedback into prompts:
   ```python
   def _execute_planning(self):
       feedback = self.feedback_manager.get_feedback_for_prompt(
           feedback_types=[
               FeedbackType.VALIDATION_FAILURE,
               FeedbackType.JUDGE_HARD_FAILURE
           ]
       )
       context = self._build_planning_context(feedback)
       ...
   ```

#### Step 4.3: Add to Checkpointing

1. Update `CheckpointManager.save_orchestration_state()`:
   - Add `feedback_manager` parameter
   - Serialize feedback history

2. Update restoration to rebuild `FeedbackManager`

#### Step 4.4: Testing

- Test feedback accumulation
- Test FIFO trimming
- Test feedback filtering by type
- Test feedback in checkpoints
- Test token limit enforcement

**Checkpoint**: Feedback management working, structured accumulation verified.

---

### Phase 5: Enhanced Checkpointing (Week 2-3)

**Goal**: Include complete agent responses in checkpoints for debugging and step execution.

#### Step 5.1: Update Checkpoint Structure

1. Update `CheckpointManager.save_orchestration_state()`:
   - Add `agent_responses: dict[str, AgentResult]` parameter
   - Serialize complete agent responses including:
     - success
     - data (model_dump())
     - tokens_used
     - metadata
     - confidence
     - reasoning

2. Update orchestrator to track responses:
   ```python
   def __init__(self, ...):
       self.agent_responses: dict[str, AgentResult] = {}
   
   def _execute_planning(self):
       result = self.planner.generate_plan(...)
       self.agent_responses["plan"] = result
       return result
   ```

#### Step 5.2: Update Restoration

1. Load agent responses from checkpoint
2. Verify data integrity
3. Support step-by-step execution (future enhancement)

#### Step 5.3: Testing

- Test checkpoint serialization
- Test restoration
- Verify all response fields preserved
- Test with complex agent responses

**Checkpoint**: Enhanced checkpointing complete, debugging support enabled.

---

### Phase 6: Refinement Simplification (Week 3)

**Goal**: Remove `RefinementAgent`, implement refinement as follow-up messages.

#### Step 6.1: Update Orchestrator Logic

1. Remove `RefinementAgent` initialization

2. Replace refinement stage with follow-up messages:
   ```python
   # Judge soft failure
   if failure_analysis.fix_strategy == "refine_implementation":
       feedback = self._build_implementation_feedback(...)
       self.feedback_manager.add_feedback(
           FeedbackType.JUDGE_SOFT_FAILURE,
           feedback,
           iteration
       )
       
       # Transition back to IMPLEMENTING (not REFINEMENT)
       self.state_machine.transition(
           OrchestrationState.IMPLEMENTING,
           reason="Soft failure - refining implementation"
       )
   ```

3. In `_execute_implementation()`:
   ```python
   if self.implementation.conversation_id:
       # Refinement via follow-up
       feedback = self.feedback_manager.get_feedback_for_prompt(
           feedback_types=[FeedbackType.JUDGE_SOFT_FAILURE]
       )
       return self.implementation.refine_implementation(feedback)
   else:
       # Initial implementation
       return self.implementation.expand_implementation(...)
   ```

#### Step 6.2: Update State Machine

1. Verify no `REFINEMENT` state exists
2. Ensure transitions support refinement pattern:
   - JUDGING → IMPLEMENTING (soft failure)
   - JUDGING → PLANNING (hard failure)

#### Step 6.3: Remove Refinement Agent

1. Delete `packages/blinkb0t/core/agents/moving_heads/refinement_agent.py`
2. Remove from `StageCoordinator`
3. Update imports

#### Step 6.4: Testing

- Test refinement as follow-up messages
- Test both soft and hard failure paths
- Verify conversation continuity
- End-to-end test full pipeline
- Verify iteration count doesn't increment for soft failures

**Checkpoint**: Refinement simplified, `RefinementAgent` removed (~200 LOC reduction).

---

### Phase 7: Cleanup & Finalization (Week 3-4)

**Goal**: Remove old code, update documentation, finalize migration.

#### Step 7.1: Remove Old Code

1. Remove unused methods from `StageCoordinator`
2. Remove old iteration loop logic
3. Clean up imports
4. Remove dead code

#### Step 7.2: Update Documentation

1. Update docstrings
2. Update README with new architecture
3. Update architecture docs
4. Document observability features
5. Document feedback management

#### Step 7.3: Final Testing

1. Run full test suite
2. Integration tests for all workflows (see examples above)
3. End-to-end tests
4. Performance testing
5. Load testing

#### Step 7.4: Code Review

1. Review all changes
2. Verify code quality
3. Check for any remaining TODOs
4. Verify metrics accuracy

**Checkpoint**: Migration complete, all tests passing, documentation updated.

## Rollback Plan

If issues arise during migration:

1. **Phase 1-2**: Keep old `OpenAIClient` code, new code is additive
2. **Phase 3**: Feature flag state machine (fallback to old loop)
3. **Phase 4**: Feature flag feedback manager (fallback to inline feedback)
4. **Phase 5**: Feature flag enhanced checkpoints (use basic checkpoints)
5. **Phase 6**: Keep `RefinementAgent` until new approach proven

## Testing Strategy

### Unit Tests

- Test each component independently
- Mock dependencies
- Test error cases
- Test metrics calculations
- Test feedback trimming

### Integration Tests

- Test agent interactions
- Test state machine transitions
- Test conversation flow
- Test feedback accumulation
- Test all workflows (see examples above)

### End-to-End Tests

- Test full pipeline
- Test refinement scenarios
- Test error recovery
- Test budget exhaustion
- Test checkpoint restoration

## Performance Considerations

- Monitor token usage (should be similar or better due to feedback trimming)
- Monitor execution time (should be similar, metrics tracking adds <1% overhead)
- Monitor conversation overhead (minimal, ~10-20 tokens per follow-up)
- Monitor feedback trimming effectiveness (verify FIFO maintains recent context)

## Success Metrics

1. ✅ Code reduction: ~200-300 LOC removed
2. ✅ All tests passing
3. ✅ No performance regression (<5% overhead acceptable for metrics)
4. ✅ Token usage accurate
5. ✅ Checkpointing works with all enhancements
6. ✅ Conversations working correctly
7. ✅ Feedback accumulation and trimming working
8. ✅ Observability metrics available and useful
9. ✅ Confidence and reasoning captured
10. ✅ All example workflows passing

## Common Issues & Solutions

### Issue: Provider abstraction breaks existing code

**Solution**: Keep `OpenAIClient` wrapper, gradually migrate

### Issue: State machine too complex

**Solution**: Start simple, add features incrementally, use feature flags

### Issue: Conversations not working

**Solution**: Feature flag, fallback to single-turn

### Issue: Refinement feedback not effective

**Solution**: Iterate on feedback prompt builder, verify feedback is being injected

### Issue: Metrics overhead too high

**Solution**: Make metrics optional, use sampling for high-frequency operations

### Issue: Feedback trimming too aggressive

**Solution**: Adjust `max_feedback_tokens`, verify FIFO preserves critical context

### Issue: Conversation ID collisions

**Solution**: Verify `generate_conversation_id()` includes UUID for uniqueness

## Next Steps After Migration

1. Add Claude provider support
2. Add more sophisticated conversation management
3. Add state machine visualization dashboard
4. Add more observability/metrics (latency percentiles, success rates)
5. Implement step-by-step execution using checkpointed agent responses
6. Add feedback quality metrics (how often feedback leads to success)
7. Add A/B testing framework for prompt variations