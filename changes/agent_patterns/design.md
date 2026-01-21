# Agent Architecture Refactoring Design

**Status:** Design Phase  
**Date:** 2026-01-20  
**Updated:** 2026-01-21  
**Sprint Goal:** Simplify and enhance agents through patterns, abstraction, and state management

## Executive Summary

This document outlines the design for refactoring the multi-agent orchestration system to:
1. Simplify agents by extending and using defined `agent_patterns`
2. Implement a generic LLM provider abstraction
3. Implement state machine pattern for flow management with enhanced observability
4. Leverage conversations/conversation paradigm within the multi-agent loop
5. Simplify refinement by converting it to follow-up messages instead of a separate agent
6. Implement structured feedback accumulation with token limit management
7. Enhance checkpointing to include complete agent responses for debugging and step-by-step execution

## Current State Analysis

### Architecture Overview

The current system follows a 5-stage pipeline:

```
Orchestrator (532 LOC)
  ↓
StageCoordinator (286 LOC)
  ↓
Individual Agents:
  - PlanGenerator
  - HeuristicValidator (non-agent)
  - ImplementationExpander
  - JudgeCritic
  - RefinementAgent
```

### Current Flow

```
Plan → Validate → Implement → Judge → (Refine if failed) → Repeat
```

### Key Issues Identified

1. **Agent Pattern Underutilization**
   - `agent_patterns.py` exists but agents don't fully leverage `StageExecutor` base class
   - Each agent reimplements similar LLM calling logic
   - Inconsistent error handling and token tracking

2. **Provider Lock-in**
   - Direct dependency on `OpenAIClient` throughout codebase
   - No abstraction for future providers (Claude, etc.)
   - Provider-specific features (conversations) not abstracted
   - Retry logic is provider-specific (e.g., 529 errors) and should stay at provider level

3. **State Management Complexity**
   - Flow control logic scattered across `Orchestrator` and `StageCoordinator`
   - Manual iteration loop management
   - No explicit state machine for transitions
   - Checkpointing logic mixed with orchestration
   - Lack of observability metrics (duration, tokens per state)

4. **Refinement Complexity**
   - `RefinementAgent` is a separate agent that wraps `PlanGenerator` and `ImplementationExpander`
   - Duplicates prompt building logic
   - Doesn't leverage conversation paradigm effectively
   - Adds unnecessary abstraction layer

5. **Conversation Support Incomplete**
   - `OpenAIClient` has `generate_json_with_conversation()` but it's not used
   - Agents don't maintain conversation state
   - Refinement doesn't leverage multi-turn conversations

6. **Feedback Management Missing**
   - No structured feedback accumulation
   - No token limit management for feedback context
   - Feedback not preserved across iterations

## Target Architecture

### High-Level Flow

```
Planner Agent (Conversational)
  ↓
Heuristics Validation (non-agent)
  ├─ Failure → Redirect back to Planner (add context messages via FeedbackManager)
  └─ Success → Continue
  ↓
Implementation Agent (Conversational)
  ↓
Judge Agent (Non-Conversational)
  ├─ Soft Failure → Redirect back to Implementation (add context messages via FeedbackManager)
  ├─ Hard Failure → Redirect back to Planner (add context messages via FeedbackManager)
  └─ Success → Return to client
```

### Key Design Principles

1. **Agent Pattern Consistency**: All agents extend `StageExecutor` or implement `PromptBuilder`/`ResponseParser` protocols
2. **Provider Abstraction**: Generic `LLMProvider` protocol abstracts provider-specific details (including retry logic)
3. **State Machine with Observability**: Explicit FSM manages orchestration flow with duration and token metrics
4. **Conversation-First**: Conversational agents maintain conversation state; refinement uses follow-up messages
5. **Separation of Concerns**: State management, checkpointing, feedback management, and flow control separated from agent logic
6. **Structured Feedback**: FeedbackManager accumulates and formats feedback with FIFO trimming for token limits
7. **Enhanced Result Metadata**: AgentResult includes confidence scores and reasoning traces

## Detailed Design

### 1. Generic LLM Provider Abstraction

See `provider_abstraction.md` for complete specification.

**Key Points:**
- `LLMProvider` protocol abstracts OpenAI, Claude, etc.
- Provider handles retry logic for network errors (529, rate limits)
- Higher-level failures (bad responses, validation) fail gracefully up the stack
- Unique conversation IDs using pattern: `{agent_name}_iter{iteration}_{uuid}`

```python
# Example conversation ID generation
def generate_conversation_id(agent_name: str, iteration: int) -> str:
    """Generate unique conversation ID."""
    return f"{agent_name}_iter{iteration}_{uuid.uuid4().hex[:8]}"
```

### 2. Enhanced Agent Patterns

#### Updated AgentResult with Confidence and Reasoning

```python
from dataclasses import dataclass
from typing import Generic, TypeVar, Any

T = TypeVar('T')

@dataclass
class AgentResult(Generic[T]):
    """Result from agent execution with enhanced metadata."""
    success: bool
    data: T | None
    tokens_used: int
    metadata: dict[str, Any]
    
    # NEW: Confidence and reasoning
    confidence: float | None = None  # 0.0-1.0 confidence score
    reasoning: str | None = None  # Agent's reasoning trace for debugging
```

#### Conversational Executor

```python
class ConversationalStageExecutor(StageExecutor):
    """Base class for conversational agents (Planner, Implementation)."""
    
    def __init__(
        self,
        job_config: JobConfig,
        llm_provider: LLMProvider,
        agent_name: str
    ):
        super().__init__(job_config, llm_provider, agent_name)
        self.conversation_id: str | None = None
    
    def execute_with_conversation(
        self,
        context: dict[str, Any],
        response_model: type[T],
        iteration: int
    ) -> AgentResult[T]:
        """Execute agent with conversation support."""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(context)
        
        # Generate unique conversation ID
        conversation_id = generate_conversation_id(self.agent_name, iteration)
        
        response = self.llm_provider.generate_json_with_conversation(
            user_message=user_prompt,
            conversation_id=None,  # New conversation
            model=self.agent_config.model,
            system_prompt=system_prompt,
        )
        
        parsed = self.parse_response(response.content)
        
        # Store conversation ID for follow-ups
        self.conversation_id = conversation_id
        
        # Extract confidence and reasoning if present in response
        confidence = response.content.get('confidence')
        reasoning = response.content.get('reasoning')
        
        return AgentResult(
            success=True,
            data=parsed,
            tokens_used=response.metadata.token_usage.total_tokens,
            metadata={"conversation_id": self.conversation_id},
            confidence=confidence,
            reasoning=reasoning
        )
    
    def add_followup(
        self,
        feedback: str,
        response_model: type[T],
    ) -> AgentResult[T]:
        """Add follow-up message to conversation."""
        if not self.conversation_id:
            raise ValueError("No active conversation")
        
        response = self.llm_provider.generate_json_with_conversation(
            user_message=feedback,
            conversation_id=self.conversation_id,
            model=self.agent_config.model,
        )
        
        parsed = self.parse_response(response.content)
        
        confidence = response.content.get('confidence')
        reasoning = response.content.get('reasoning')
        
        return AgentResult(
            success=True,
            data=parsed,
            tokens_used=response.metadata.token_usage.total_tokens,
            confidence=confidence,
            reasoning=reasoning
        )
```

#### Non-Conversational Executor

```python
class NonConversationalStageExecutor(StageExecutor):
    """Base class for non-conversational agents (e.g., Judge)."""
    
    def execute_single_turn(
        self,
        context: dict[str, Any],
        response_model: type[T],
    ) -> AgentResult[T]:
        """Execute single-turn agent call."""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(context)
        
        response = self.llm_provider.generate_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=self.agent_config.model,
        )
        
        parsed = self.parse_response(response.content)
        
        confidence = response.content.get('confidence')
        reasoning = response.content.get('reasoning')
        
        return AgentResult(
            success=True,
            data=parsed,
            tokens_used=response.metadata.token_usage.total_tokens,
            confidence=confidence,
            reasoning=reasoning
        )
```

### 3. State Machine Pattern with Observability

See `state_machine.md` for complete specification.

**Key Enhancements:**
- State transitions track duration and tokens consumed
- Metrics collection for observability
- Integration with existing token budget system

```python
from dataclasses import dataclass
from enum import Enum
import time

@dataclass
class StateTransition:
    """Record of state transition with metrics."""
    from_state: OrchestrationState
    to_state: OrchestrationState
    timestamp: float
    context: dict[str, Any]
    reason: str | None = None
    
    # NEW: Observability metrics
    duration_seconds: float = 0.0
    tokens_consumed: int = 0

class OrchestrationStateMachine:
    """State machine with observability."""
    
    def transition(
        self,
        to_state: OrchestrationState,
        context: dict[str, Any] | None = None,
        reason: str | None = None,
        duration_seconds: float = 0.0,
        tokens_consumed: int = 0
    ) -> bool:
        """Transition with metrics."""
        # Validation logic...
        
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=time.time(),
            context=context or {},
            reason=reason,
            duration_seconds=duration_seconds,
            tokens_consumed=tokens_consumed
        )
        
        self.history.append(transition)
        self.current_state = to_state
        
        return True
    
    def get_state_metrics(self, state: OrchestrationState) -> dict[str, Any]:
        """Get aggregated metrics for a state."""
        state_transitions = [
            t for t in self.history
            if t.from_state == state
        ]
        
        if not state_transitions:
            return {
                "visit_count": 0,
                "total_duration": 0.0,
                "total_tokens": 0,
                "avg_duration": 0.0,
                "avg_tokens": 0
            }
        
        return {
            "visit_count": len(state_transitions),
            "total_duration": sum(t.duration_seconds for t in state_transitions),
            "total_tokens": sum(t.tokens_consumed for t in state_transitions),
            "avg_duration": sum(t.duration_seconds for t in state_transitions) / len(state_transitions),
            "avg_tokens": sum(t.tokens_consumed for t in state_transitions) // len(state_transitions)
        }
```

### 4. Feedback Management Architecture

**Design Philosophy:**
- Structured feedback accumulation across iterations
- FIFO trimming when approaching token limits
- Separate feedback contexts for planner vs. implementation

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import tiktoken

class FeedbackType(str, Enum):
    """Types of feedback."""
    VALIDATION_FAILURE = "validation_failure"
    JUDGE_SOFT_FAILURE = "judge_soft_failure"
    JUDGE_HARD_FAILURE = "judge_hard_failure"

@dataclass
class FeedbackEntry:
    """Single feedback entry."""
    type: FeedbackType
    content: str
    iteration: int
    timestamp: float
    priority: int = 0  # Higher = more important (reserved for future use)
    metadata: dict[str, Any] = field(default_factory=dict)

class FeedbackManager:
    """Manages structured feedback accumulation with token limits."""
    
    def __init__(self, max_feedback_tokens: int = 2000, model: str = "gpt-4"):
        """Initialize feedback manager.
        
        Args:
            max_feedback_tokens: Maximum tokens for feedback context
            model: Model name for tokenization
        """
        self.max_feedback_tokens = max_feedback_tokens
        self.feedback_history: list[FeedbackEntry] = []
        self.encoding = tiktoken.encoding_for_model(model)
    
    def add_feedback(
        self,
        feedback_type: FeedbackType,
        content: str,
        iteration: int,
        priority: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Add feedback entry.
        
        Args:
            feedback_type: Type of feedback
            content: Feedback content
            iteration: Current iteration number
            priority: Priority (higher = more important, reserved for future)
            metadata: Optional metadata
        """
        entry = FeedbackEntry(
            type=feedback_type,
            content=content,
            iteration=iteration,
            timestamp=time.time(),
            priority=priority,
            metadata=metadata or {}
        )
        self.feedback_history.append(entry)
    
    def get_feedback_for_prompt(
        self,
        max_tokens: int | None = None,
        feedback_types: list[FeedbackType] | None = None
    ) -> str:
        """Get formatted feedback respecting token limits.
        
        Uses FIFO trimming: keeps most recent feedback when over limit.
        
        Args:
            max_tokens: Override default max tokens
            feedback_types: Filter by feedback types (None = all types)
        
        Returns:
            Formatted feedback string
        """
        max_tokens = max_tokens or self.max_feedback_tokens
        
        # Filter by type if specified
        relevant_feedback = self.feedback_history
        if feedback_types:
            relevant_feedback = [
                f for f in relevant_feedback
                if f.type in feedback_types
            ]
        
        if not relevant_feedback:
            return ""
        
        # Build feedback sections (most recent first for FIFO trimming)
        sections = []
        for entry in reversed(relevant_feedback):
            section = self._format_feedback_entry(entry)
            sections.append(section)
        
        # Trim using FIFO approach (keep most recent)
        formatted = self._trim_to_token_limit(sections, max_tokens)
        
        return formatted
    
    def _format_feedback_entry(self, entry: FeedbackEntry) -> str:
        """Format single feedback entry."""
        return f"""
### Iteration {entry.iteration} - {entry.type.value}
{entry.content}
""".strip()
    
    def _trim_to_token_limit(
        self,
        sections: list[str],
        max_tokens: int
    ) -> str:
        """Trim sections to fit within token limit using FIFO.
        
        Args:
            sections: Feedback sections (newest first)
            max_tokens: Token limit
        
        Returns:
            Formatted feedback within token limit
        """
        header = "## Previous Feedback\n\n"
        header_tokens = len(self.encoding.encode(header))
        
        available_tokens = max_tokens - header_tokens
        
        # Add sections from newest to oldest until we hit limit
        included_sections = []
        total_tokens = 0
        
        for section in sections:
            section_tokens = len(self.encoding.encode(section))
            
            if total_tokens + section_tokens > available_tokens:
                # Would exceed limit, stop here
                break
            
            included_sections.append(section)
            total_tokens += section_tokens
        
        if not included_sections:
            return ""
        
        # Reverse to show oldest-to-newest (but we kept newest when trimming)
        included_sections.reverse()
        
        return header + "\n\n".join(included_sections)
    
    def clear(self) -> None:
        """Clear all feedback."""
        self.feedback_history.clear()
    
    def get_feedback_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        by_type = {}
        for entry in self.feedback_history:
            by_type.setdefault(entry.type.value, 0)
            by_type[entry.type.value] += 1
        
        return {
            "total_entries": len(self.feedback_history),
            "by_type": by_type,
            "iterations_with_feedback": len(set(e.iteration for e in self.feedback_history))
        }
```

### 5. Checkpointing Integration

Complete orchestration state is checkpointed, including:
- State machine state and history with metrics
- Conversation IDs for resumption
- **Complete agent responses** for debugging, troubleshooting, and future step-by-step execution
- Feedback manager state

```python
class CheckpointManager:
    def save_orchestration_state(
        self,
        state_machine: OrchestrationStateMachine,
        planner_conversation_id: str | None,
        implementation_conversation_id: str | None,
        agent_responses: dict[str, AgentResult],
        feedback_manager: FeedbackManager
    ) -> None:
        """Save complete orchestration state.
        
        Args:
            state_machine: Current state machine
            planner_conversation_id: Planner's conversation ID
            implementation_conversation_id: Implementation's conversation ID
            agent_responses: Complete agent responses for each stage
                Keys: "plan", "validation", "implementation", "evaluation"
            feedback_manager: Feedback manager with accumulated feedback
        """
        checkpoint_data = {
            "state_machine": {
                "current_state": state_machine.current_state.value,
                "iteration_count": state_machine.iteration_count,
                "history": [
                    {
                        "from_state": t.from_state.value,
                        "to_state": t.to_state.value,
                        "timestamp": t.timestamp,
                        "reason": t.reason,
                        "duration_seconds": t.duration_seconds,
                        "tokens_consumed": t.tokens_consumed
                    }
                    for t in state_machine.history
                ]
            },
            "conversations": {
                "planner": planner_conversation_id,
                "implementation": implementation_conversation_id
            },
            "agent_responses": {
                stage: {
                    "success": response.success,
                    "data": response.data.model_dump() if response.data else None,
                    "tokens_used": response.tokens_used,
                    "metadata": response.metadata,
                    "confidence": response.confidence,
                    "reasoning": response.reasoning
                }
                for stage, response in agent_responses.items()
                if response is not None
            },
            "feedback": {
                "history": [
                    {
                        "type": entry.type.value,
                        "content": entry.content,
                        "iteration": entry.iteration,
                        "timestamp": entry.timestamp,
                        "priority": entry.priority,
                        "metadata": entry.metadata
                    }
                    for entry in feedback_manager.feedback_history
                ]
            }
        }
        self.write_checkpoint(CheckpointType.ORCHESTRATION_STATE, checkpoint_data)
    
    def load_orchestration_state(self) -> dict[str, Any] | None:
        """Load orchestration state from checkpoint.
        
        Returns:
            Dict containing:
                - state_machine: State machine data
                - conversations: Conversation IDs
                - agent_responses: Complete agent response history
                - feedback: Feedback manager data
        """
        return self.read_checkpoint(CheckpointType.ORCHESTRATION_STATE)
```

### 6. Refactored Agents

#### PlannerAgent (Conversational)

```python
class PlannerAgent(ConversationalStageExecutor):
    """Conversational planner agent."""
    
    def generate_plan(
        self,
        context: dict[str, Any],
        iteration: int
    ) -> AgentResult[AgentPlan]:
        """Generate initial plan."""
        return self.execute_with_conversation(
            context=context,
            response_model=AgentPlan,
            iteration=iteration
        )
    
    def refine_plan(
        self,
        feedback: str
    ) -> AgentResult[AgentPlan]:
        """Refine plan based on feedback (follow-up message)."""
        return self.add_followup(
            feedback=feedback,
            response_model=AgentPlan
        )
```

#### ImplementationAgent (Conversational)

```python
class ImplementationAgent(ConversationalStageExecutor):
    """Conversational implementation agent."""
    
    def expand_implementation(
        self,
        context: dict[str, Any],
        iteration: int
    ) -> AgentResult[AgentImplementation]:
        """Expand plan to implementation."""
        return self.execute_with_conversation(
            context=context,
            response_model=AgentImplementation,
            iteration=iteration
        )
    
    def refine_implementation(
        self,
        feedback: str
    ) -> AgentResult[AgentImplementation]:
        """Refine implementation based on feedback (follow-up message)."""
        return self.add_followup(
            feedback=feedback,
            response_model=AgentImplementation
        )
```

#### JudgeAgent (Non-Conversational)

```python
class JudgeAgent(NonConversationalStageExecutor):
    """Non-conversational judge agent."""
    
    def evaluate(
        self,
        context: dict[str, Any]
    ) -> AgentResult[AgentEvaluation]:
        """Evaluate plan and implementation."""
        return self.execute_single_turn(
            context=context,
            response_model=AgentEvaluation
        )
```

### 7. Updated Orchestrator Integration

```python
class AgentOrchestrator:
    """Orchestrator with state machine and feedback management."""
    
    def __init__(self, job_config: JobConfig):
        # Initialize provider
        self.llm_provider = OpenAIProvider(api_key=job_config.openai_api_key)
        
        # Initialize state machine
        self.state_machine = OrchestrationStateMachine()
        self.state_machine.max_iterations = job_config.agent.max_iterations
        
        # Initialize feedback manager
        self.feedback_manager = FeedbackManager(
            max_feedback_tokens=2000,
            model=job_config.agent.model
        )
        
        # Initialize agents
        self.planner = PlannerAgent(job_config, self.llm_provider, "planner")
        self.validator = HeuristicValidator(job_config)
        self.implementation = ImplementationAgent(job_config, self.llm_provider, "implementation")
        self.judge = JudgeAgent(job_config, self.llm_provider, "judge")
        
        # Track agent responses for checkpointing
        self.agent_responses: dict[str, AgentResult] = {}
    
    def run(self, audio_path: str) -> OrchestratorResult:
        """Run orchestration with state machine."""
        self.state_machine.transition(OrchestrationState.PLANNING)
        
        while not self.state_machine.is_terminal():
            state = self.state_machine.current_state
            start_time = time.time()
            tokens_before = self.llm_provider.get_token_usage().total_tokens
            
            if state == OrchestrationState.PLANNING:
                result = self._execute_planning()
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                if result.success:
                    self.agent_responses["plan"] = result
                    self.state_machine.transition(
                        OrchestrationState.VALIDATING,
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    self.state_machine.transition(
                        OrchestrationState.FAILED,
                        reason="Planning failed",
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
            
            elif state == OrchestrationState.VALIDATING:
                validation_result = self._execute_validation()
                duration = time.time() - start_time
                
                if validation_result.passed:
                    self.agent_responses["validation"] = validation_result
                    self.state_machine.transition(
                        OrchestrationState.IMPLEMENTING,
                        duration_seconds=duration,
                        tokens_consumed=0  # Validation is non-LLM
                    )
                else:
                    # Add validation feedback
                    self.feedback_manager.add_feedback(
                        feedback_type=FeedbackType.VALIDATION_FAILURE,
                        content=validation_result.failure_message,
                        iteration=self.state_machine.iteration_count
                    )
                    
                    self.state_machine.transition(
                        OrchestrationState.PLANNING,
                        reason="Validation failed",
                        duration_seconds=duration,
                        tokens_consumed=0
                    )
            
            elif state == OrchestrationState.IMPLEMENTING:
                result = self._execute_implementation()
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                if result.success:
                    self.agent_responses["implementation"] = result
                    self.state_machine.transition(
                        OrchestrationState.JUDGING,
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    self.state_machine.transition(
                        OrchestrationState.FAILED,
                        reason="Implementation failed",
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
            
            elif state == OrchestrationState.JUDGING:
                result = self._execute_judging()
                duration = time.time() - start_time
                tokens = self.llm_provider.get_token_usage().total_tokens - tokens_before
                
                self.agent_responses["evaluation"] = result
                
                if result.data.pass_threshold:
                    self.state_machine.transition(
                        OrchestrationState.SUCCEEDED,
                        duration_seconds=duration,
                        tokens_consumed=tokens
                    )
                else:
                    failure_analysis = self._analyze_failure(result.data)
                    
                    if failure_analysis.fix_strategy == "refine_implementation":
                        # Soft failure - add feedback for implementation
                        feedback = self._build_implementation_feedback(
                            result.data,
                            failure_analysis
                        )
                        self.feedback_manager.add_feedback(
                            feedback_type=FeedbackType.JUDGE_SOFT_FAILURE,
                            content=feedback,
                            iteration=self.state_machine.iteration_count
                        )
                        
                        self.state_machine.transition(
                            OrchestrationState.IMPLEMENTING,
                            reason="Soft failure - refining implementation",
                            duration_seconds=duration,
                            tokens_consumed=tokens
                        )
                    else:
                        # Hard failure - add feedback for planner
                        feedback = self._build_planning_feedback(
                            result.data,
                            failure_analysis
                        )
                        self.feedback_manager.add_feedback(
                            feedback_type=FeedbackType.JUDGE_HARD_FAILURE,
                            content=feedback,
                            iteration=self.state_machine.iteration_count
                        )
                        
                        self.state_machine.transition(
                            OrchestrationState.PLANNING,
                            reason="Hard failure - replanning",
                            duration_seconds=duration,
                            tokens_consumed=tokens
                        )
            
            # Check budget (existing implementation)
            if self._is_budget_exhausted():
                self.state_machine.transition(
                    OrchestrationState.BUDGET_EXHAUSTED,
                    reason="Token budget exhausted"
                )
            
            # Save checkpoint after each state
            self._save_checkpoint()
        
        return self._build_result()
    
    def _execute_planning(self) -> AgentResult[AgentPlan]:
        """Execute planning stage with feedback."""
        # Get accumulated feedback
        feedback = self.feedback_manager.get_feedback_for_prompt(
            feedback_types=[
                FeedbackType.VALIDATION_FAILURE,
                FeedbackType.JUDGE_HARD_FAILURE
            ]
        )
        
        context = self._build_planning_context(feedback)
        
        if self.planner.conversation_id:
            # Refinement via follow-up
            return self.planner.refine_plan(feedback)
        else:
            # Initial plan
            return self.planner.generate_plan(
                context,
                iteration=self.state_machine.iteration_count
            )
    
    def _execute_implementation(self) -> AgentResult[AgentImplementation]:
        """Execute implementation stage with feedback."""
        # Get accumulated feedback
        feedback = self.feedback_manager.get_feedback_for_prompt(
            feedback_types=[FeedbackType.JUDGE_SOFT_FAILURE]
        )
        
        context = self._build_implementation_context(feedback)
        
        if self.implementation.conversation_id:
            # Refinement via follow-up
            return self.implementation.refine_implementation(feedback)
        else:
            # Initial implementation
            return self.implementation.expand_implementation(
                context,
                iteration=self.state_machine.iteration_count
            )
    
    def _save_checkpoint(self) -> None:
        """Save orchestration checkpoint."""
        self.checkpoint_manager.save_orchestration_state(
            state_machine=self.state_machine,
            planner_conversation_id=self.planner.conversation_id,
            implementation_conversation_id=self.implementation.conversation_id,
            agent_responses=self.agent_responses,
            feedback_manager=self.feedback_manager
        )
```

## Implementation Plan

### Phase 1: Provider Abstraction (Week 1)
- Create `LLMProvider` protocol
- Implement `OpenAIProvider` with conversation support
- Update agent patterns to accept `LLMProvider`
- Add conversation ID generation utility

### Phase 2: Enhanced Agent Patterns (Week 1-2)
- Add confidence and reasoning to `AgentResult`
- Implement `ConversationalStageExecutor` and `NonConversationalStageExecutor`
- Refactor agents: `PlannerAgent`, `ImplementationAgent`, `JudgeAgent`

### Phase 3: State Machine with Observability (Week 2)
- Implement `OrchestrationStateMachine` with metrics tracking
- Add state transition validation
- Integrate with existing token budget system
- Add metrics aggregation methods

### Phase 4: Feedback Management (Week 2)
- Implement `FeedbackManager` with structured feedback
- Add FIFO trimming logic
- Integrate with agents for feedback accumulation

### Phase 5: Checkpointing Enhancement (Week 2-3)
- Update `CheckpointManager` to serialize agent responses
- Add feedback manager state to checkpoints
- Test checkpoint restoration

### Phase 6: Refinement Removal (Week 3)
- Remove `RefinementAgent`
- Update orchestrator to use follow-up messages
- Test refinement workflows

### Phase 7: Testing & Cleanup (Week 3-4)
- Comprehensive testing (unit, integration, e2e)
- Performance validation
- Documentation updates

## Success Criteria

1. ✅ All agents extend appropriate base executors
2. ✅ `LLMProvider` abstraction supports OpenAI (Claude-ready)
3. ✅ State machine manages all flow with metrics
4. ✅ Feedback accumulates with FIFO trimming
5. ✅ Checkpoints include complete agent responses
6. ✅ AgentResult includes confidence and reasoning
7. ✅ Refinement works via follow-up messages
8. ✅ Code reduction: ~200-300 LOC
9. ✅ All tests passing
10. ✅ Token usage accurate
11. ✅ Observability metrics available

## Benefits Summary

- **Simplified Architecture**: Remove `RefinementAgent` (~200 LOC)
- **Provider Flexibility**: Easy to add Claude, other providers
- **Better Observability**: Duration and token metrics per state
- **Structured Feedback**: Accumulation with intelligent trimming
- **Enhanced Debugging**: Complete agent responses in checkpoints
- **Future-Ready**: Step-by-step execution support via checkpoints
- **Better Error Handling**: Provider-level retries, graceful stack failures
- **Metadata Richness**: Confidence and reasoning in results