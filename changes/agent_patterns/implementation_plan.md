# Agent Architecture Refactoring - Implementation Plan

**Status:** Ready for Implementation  
**Date:** 2026-01-21  
**Estimated Duration:** 3-4 weeks  
**Success Criteria:** All tasks completed, tests passing, ~200 LOC reduction

## Plan Overview

This implementation plan breaks down the refactoring into **7 phases** with **42 actionable tasks**. Each task has:
- Clear completion criteria
- Test requirements
- Dependencies
- Estimated effort
- Rollback steps

## Task Format

```
### Task X.Y: [Task Name]
**Effort:** [Small/Medium/Large] (~[hours])
**Dependencies:** [Task IDs]
**Files:** [Files to create/modify]

**Objective:** [What to accomplish]

**Steps:**
1. [Actionable step]
2. [Actionable step]

**Completion Criteria:**
- [ ] [Measurable criterion]
- [ ] [Measurable criterion]

**Tests:**
- [ ] [Specific test]

**Rollback:** [How to undo if needed]
```

---

## Phase 1: Provider Abstraction Foundation
**Duration:** 3-4 days  
**Goal:** Abstract LLM provider without breaking existing functionality

### Task 1.1: Create Provider Protocol and Types
**Effort:** Small (~2 hours)  
**Dependencies:** None  
**Files:** 
- Create: `packages/blinkb0t/core/api/llm/provider.py`

**Objective:** Define the core provider protocol and data types that all providers will implement.

**Steps:**
1. Create `packages/blinkb0t/core/api/llm/provider.py`
2. Define `ProviderType` enum with `OPENAI` and `ANTHROPIC` values
3. Define `TokenUsage` dataclass with prompt_tokens, completion_tokens, total_tokens
4. Define `ResponseMetadata` dataclass with response_id, token_usage, model, finish_reason, conversation_id
5. Define `LLMResponse` dataclass with content (Any) and metadata (ResponseMetadata)
6. Define `LLMProviderError` exception class
7. Define `LLMProvider` protocol with methods:
   - `provider_type` property
   - `generate_json(messages, model, temperature, **kwargs)`
   - `generate_json_with_conversation(user_message, conversation_id, model, system_prompt, temperature, **kwargs)`
   - `add_message_to_conversation(conversation_id, role, content)`
   - `get_conversation_history(conversation_id)`
   - `get_token_usage()`
   - `reset_token_tracking()`
8. Add comprehensive docstrings to protocol methods

**Completion Criteria:**
- [ ] All types defined with proper type hints
- [ ] Protocol methods have complete signatures
- [ ] Docstrings explain each method's purpose and parameters
- [ ] File runs without errors (`python -m py_compile`)
- [ ] No imports of non-existent modules

**Tests:**
- [ ] Can import all types: `from blinkb0t.core.api.llm.provider import LLMProvider, TokenUsage, ResponseMetadata, LLMResponse, ProviderType, LLMProviderError`
- [ ] Type checking passes with mypy

**Rollback:** Delete `provider.py` file

---

### Task 1.2: Create Conversation ID Utility
**Effort:** Small (~1 hour)  
**Dependencies:** None  
**Files:**
- Create: `packages/blinkb0t/core/api/llm/utils.py`

**Objective:** Create utility function for generating unique conversation IDs.

**Steps:**
1. Create `packages/blinkb0t/core/api/llm/utils.py`
2. Import `uuid`
3. Define `generate_conversation_id(agent_name: str, iteration: int) -> str`
4. Implementation: `return f"{agent_name}_iter{iteration}_{uuid.uuid4().hex[:8]}"`
5. Add docstring with examples
6. Add validation for empty agent_name or negative iteration

**Completion Criteria:**
- [ ] Function generates IDs in format: `{agent_name}_iter{iteration}_{uuid}`
- [ ] UUID portion is 8 characters
- [ ] Function raises ValueError for invalid inputs
- [ ] Docstring includes 2-3 examples

**Tests:**
- [ ] Test generates correct format: `assert "planner_iter1_" in generate_conversation_id("planner", 1)`
- [ ] Test UUID uniqueness: `assert generate_conversation_id("planner", 1) != generate_conversation_id("planner", 1)`
- [ ] Test validation: `pytest.raises(ValueError, generate_conversation_id, "", 1)`
- [ ] Test negative iteration: `pytest.raises(ValueError, generate_conversation_id, "planner", -1)`

**Rollback:** Delete `utils.py` file

---

### Task 1.3: Create Conversation Dataclass
**Effort:** Small (~1 hour)  
**Dependencies:** None  
**Files:**
- Modify: `packages/blinkb0t/core/api/llm/provider.py`

**Objective:** Add Conversation dataclass for tracking conversation state.

**Steps:**
1. Open `packages/blinkb0t/core/api/llm/provider.py`
2. Import `dataclass`, `field`, `time`
3. Add `Conversation` dataclass with:
   - `id: str`
   - `messages: list[dict[str, str]] = field(default_factory=list)`
   - `created_at: float = field(default_factory=time.time)`
4. Add docstring explaining purpose

**Completion Criteria:**
- [ ] Conversation dataclass defined
- [ ] Default factory for messages list
- [ ] Default factory for timestamp
- [ ] Docstring present

**Tests:**
- [ ] Can create empty conversation: `conv = Conversation(id="test")`
- [ ] Messages default to empty list: `assert conv.messages == []`
- [ ] Timestamp is set: `assert conv.created_at > 0`

**Rollback:** Remove Conversation dataclass from file

---

### Task 1.4: Implement OpenAIProvider Core Structure
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 1.1, Task 1.3  
**Files:**
- Create: `packages/blinkb0t/core/api/llm/openai/provider.py`

**Objective:** Create OpenAIProvider class skeleton with initialization and basic methods.

**Steps:**
1. Create `packages/blinkb0t/core/api/llm/openai/provider.py`
2. Import required types from `..provider`
3. Import existing `OpenAIClient`
4. Define `OpenAIProvider` class
5. Implement `__init__(api_key, retry_config, timeout)`:
   - Initialize `self._client = OpenAIClient(...)`
   - Initialize `self._conversations: dict[str, Conversation] = {}`
6. Implement `provider_type` property returning `ProviderType.OPENAI`
7. Implement `get_token_usage()` by calling `self._client.get_total_token_usage()`
8. Implement `reset_token_tracking()` by calling `self._client.reset_conversation()`
9. Implement `add_message_to_conversation()`:
   - Validate conversation exists
   - Append message to conversation.messages
10. Implement `get_conversation_history()`:
    - Validate conversation exists
    - Return copy of messages
11. Add comprehensive docstrings

**Completion Criteria:**
- [ ] Class initializes without errors
- [ ] All simple methods implemented
- [ ] Type hints on all methods
- [ ] Docstrings on class and all methods
- [ ] Validates conversation_id existence

**Tests:**
- [ ] Can instantiate: `provider = OpenAIProvider(api_key="test")`
- [ ] Provider type correct: `assert provider.provider_type == ProviderType.OPENAI`
- [ ] Token usage returns TokenUsage: `assert isinstance(provider.get_token_usage(), TokenUsage)`
- [ ] Add message raises ValueError for missing conversation: `pytest.raises(ValueError, provider.add_message_to_conversation, "missing", "user", "hi")`

**Rollback:** Delete `openai/provider.py` file

---

### Task 1.5: Implement OpenAIProvider.generate_json
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 1.4  
**Files:**
- Modify: `packages/blinkb0t/core/api/llm/openai/provider.py`

**Objective:** Implement generate_json with retry error handling.

**Steps:**
1. Import OpenAI exceptions: `APIConnectionError, RateLimitError, APIError`
2. Import `logging`, create logger
3. Implement `generate_json()` method:
   - Wrap OpenAI client call in try/except
   - Call `self._client.generate_json(messages, model, temperature, return_metadata=True, **kwargs)`
   - Convert metadata to standardized format
   - Return LLMResponse
4. Add exception handling:
   - Catch `APIConnectionError, RateLimitError`: raise `LLMProviderError`
   - Catch `APIError` with status 500/502/503/529: raise `LLMProviderError`
   - Let other errors propagate
5. Add logging for errors

**Completion Criteria:**
- [ ] Method signature matches protocol
- [ ] Calls OpenAI client correctly
- [ ] Returns LLMResponse with parsed content
- [ ] Converts metadata properly
- [ ] Handles network errors by raising LLMProviderError
- [ ] Handles server errors (529) by raising LLMProviderError
- [ ] Logs errors before raising

**Tests:**
- [ ] Test successful call returns LLMResponse
- [ ] Test network error raises LLMProviderError: `mock client to raise APIConnectionError, verify LLMProviderError raised`
- [ ] Test 529 error raises LLMProviderError: `mock client to raise APIError(status=529), verify LLMProviderError raised`
- [ ] Test 400 error propagates: `mock client to raise APIError(status=400), verify APIError raised (not LLMProviderError)`

**Rollback:** Remove generate_json method, restore previous version

---

### Task 1.6: Implement OpenAIProvider.generate_json_with_conversation
**Effort:** Large (~4 hours)  
**Dependencies:** Task 1.5, Task 1.2  
**Files:**
- Modify: `packages/blinkb0t/core/api/llm/openai/provider.py`

**Objective:** Implement conversation-aware JSON generation with state management.

**Steps:**
1. Import `json`
2. Implement `generate_json_with_conversation()`:
   - Check if `conversation_id` provided and exists in `self._conversations`
   - If exists:
     - Get conversation
     - Append user_message to conversation.messages
   - If not exists:
     - Require conversation_id (raise ValueError if None)
     - Create message list with system_prompt (if provided) and user_message
     - Create new Conversation with id and messages
     - Store in `self._conversations`
   - Call `self._client.generate_json()` with conversation.messages
   - Parse response
   - Append assistant response to conversation.messages (JSON stringified)
   - Build response_metadata with conversation_id
   - Return LLMResponse
3. Add same error handling as generate_json
4. Add logging for conversation creation and updates

**Completion Criteria:**
- [ ] Creates new conversation if conversation_id not found
- [ ] Reuses existing conversation if conversation_id found
- [ ] Appends user message to conversation
- [ ] Appends assistant response to conversation
- [ ] Returns conversation_id in metadata
- [ ] Same error handling as generate_json
- [ ] Raises ValueError if conversation_id is None for new conversations

**Tests:**
- [ ] Test new conversation creation: `result = provider.generate_json_with_conversation("hi", "conv1", "gpt-4", system_prompt="test")` → conversation created
- [ ] Test conversation reuse: create conversation, call again with same ID → same conversation used, messages appended
- [ ] Test system prompt only used for new conversations: create conversation without system, call again → no system message added
- [ ] Test conversation_id in metadata: `assert result.metadata.conversation_id == "conv1"`
- [ ] Test error handling: same as generate_json tests

**Rollback:** Remove generate_json_with_conversation method

---

### Task 1.7: Create OpenAIProvider Unit Tests
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 1.6  
**Files:**
- Create: `packages/blinkb0t/tests/core/api/llm/openai/test_provider.py`

**Objective:** Comprehensive unit tests for OpenAIProvider using mocks.

**Steps:**
1. Create test file
2. Import pytest, mock, OpenAIProvider, exceptions
3. Create fixture for mock OpenAIClient
4. Write test suite:
   - `test_initialization()`
   - `test_provider_type()`
   - `test_get_token_usage()`
   - `test_reset_token_tracking()`
   - `test_generate_json_success()`
   - `test_generate_json_network_error()`
   - `test_generate_json_server_error_529()`
   - `test_generate_json_client_error_propagates()`
   - `test_generate_json_with_conversation_new()`
   - `test_generate_json_with_conversation_existing()`
   - `test_generate_json_with_conversation_no_id_raises()`
   - `test_add_message_to_conversation_success()`
   - `test_add_message_to_conversation_not_found()`
   - `test_get_conversation_history_success()`
   - `test_get_conversation_history_not_found()`
5. Each test should use mock for OpenAIClient
6. Verify all success and error paths

**Completion Criteria:**
- [ ] All 15+ tests written
- [ ] Tests use proper mocks
- [ ] Tests verify success paths
- [ ] Tests verify error handling
- [ ] Tests verify conversation state management
- [ ] All tests pass: `pytest test_provider.py -v`
- [ ] Coverage >90% for provider.py

**Tests:**
- [ ] Run: `pytest packages/blinkb0t/tests/core/api/llm/openai/test_provider.py -v`
- [ ] All tests pass
- [ ] Coverage: `pytest --cov=packages/blinkb0t/core/api/llm/openai/provider test_provider.py`

**Rollback:** Delete test file

---

### Task 1.8: Update AgentResult with Enhanced Metadata
**Effort:** Small (~1 hour)  
**Dependencies:** None  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`

**Objective:** Add confidence and reasoning fields to AgentResult.

**Steps:**
1. Open `agent_patterns.py`
2. Locate `AgentResult` dataclass
3. Add fields:
   - `confidence: float | None = None`
   - `reasoning: str | None = None`
4. Update docstring to explain new fields
5. Verify TypeVar `T` is still correct

**Completion Criteria:**
- [ ] AgentResult has confidence field (optional float)
- [ ] AgentResult has reasoning field (optional string)
- [ ] Default values are None
- [ ] Docstring updated
- [ ] File compiles without errors

**Tests:**
- [ ] Can create AgentResult without new fields: `result = AgentResult(success=True, data=None, tokens_used=100, metadata={})`
- [ ] Can create with new fields: `result = AgentResult(..., confidence=0.85, reasoning="test")`
- [ ] Fields are optional: `assert result.confidence is None` (when not provided)

**Rollback:** Remove confidence and reasoning fields from AgentResult

---

### Task 1.9: Update StageExecutor to Accept LLMProvider
**Effort:** Small (~1 hour)  
**Dependencies:** Task 1.1, Task 1.8  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`

**Objective:** Change StageExecutor to accept LLMProvider instead of OpenAIClient.

**Steps:**
1. Open `agent_patterns.py`
2. Import `LLMProvider` from `...api.llm.provider`
3. Locate `StageExecutor.__init__` method
4. Change parameter from `openai_client: OpenAIClient` to `llm_provider: LLMProvider`
5. Change instance variable from `self.openai_client` to `self.llm_provider`
6. Update docstring
7. Search for any usage of `self.openai_client` in StageExecutor and update to `self.llm_provider`

**Completion Criteria:**
- [ ] `__init__` accepts `llm_provider: LLMProvider`
- [ ] Instance variable is `self.llm_provider`
- [ ] All references updated
- [ ] Type hints correct
- [ ] Docstring updated
- [ ] File compiles

**Tests:**
- [ ] Can create StageExecutor with mock provider
- [ ] Provider is accessible via `executor.llm_provider`

**Rollback:** Revert parameter name and type back to `openai_client: OpenAIClient`

---

### Task 1.10: Integration Test - Provider with Agents
**Effort:** Small (~2 hours)  
**Dependencies:** Task 1.7, Task 1.9  
**Files:**
- Create: `packages/blinkb0t/tests/core/api/llm/test_provider_integration.py`

**Objective:** Test that OpenAIProvider integrates correctly with existing agent patterns.

**Steps:**
1. Create integration test file
2. Import OpenAIProvider, StageExecutor, mock utilities
3. Create mock for OpenAIClient that returns valid responses
4. Create test StageExecutor instance with OpenAIProvider
5. Write tests:
   - `test_stage_executor_with_provider()`
   - `test_provider_token_tracking()`
   - `test_provider_conversation_with_executor()`
6. Verify provider works end-to-end with patterns

**Completion Criteria:**
- [ ] Tests verify provider integrates with StageExecutor
- [ ] Tests verify token tracking works through provider
- [ ] Tests verify conversation management works
- [ ] All tests pass
- [ ] No import errors

**Tests:**
- [ ] Run: `pytest test_provider_integration.py -v`
- [ ] All tests pass

**Rollback:** Delete integration test file

---

**Phase 1 Checkpoint:**
- [ ] All provider abstractions implemented
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] AgentResult enhanced
- [ ] StageExecutor accepts LLMProvider
- [ ] Code compiles and type checks pass
- [ ] No existing functionality broken

---

## Phase 2: Conversational Agent Patterns
**Duration:** 3-4 days  
**Goal:** Implement conversational and non-conversational executors with conversation support

### Task 2.1: Create ConversationalStageExecutor
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 1.9, Task 1.2  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`

**Objective:** Create base class for conversational agents (Planner, Implementation).

**Steps:**
1. Open `agent_patterns.py`
2. Import `generate_conversation_id` from `...api.llm.utils`
3. Create `ConversationalStageExecutor` class extending `StageExecutor`
4. Add `__init__` that calls `super().__init__()` and initializes:
   - `self.conversation_id: str | None = None`
5. Implement `execute_with_conversation(context, response_model, iteration)`:
   - Generate conversation_id using `generate_conversation_id(self.agent_name, iteration)`
   - Build system_prompt from `self.get_system_prompt()`
   - Build user_prompt from `self.build_user_prompt(context)`
   - Call `self.llm_provider.generate_json_with_conversation(...)`
   - Parse response using `self.parse_response(response.content)`
   - Extract confidence and reasoning from response.content
   - Store `self.conversation_id`
   - Return AgentResult with data, tokens, metadata, confidence, reasoning
6. Implement `add_followup(feedback, response_model)`:
   - Validate `self.conversation_id` exists
   - Call `self.llm_provider.generate_json_with_conversation()` with existing conversation_id
   - Parse and return AgentResult
7. Add comprehensive docstrings

**Completion Criteria:**
- [ ] ConversationalStageExecutor class exists
- [ ] Extends StageExecutor
- [ ] Has conversation_id instance variable
- [ ] execute_with_conversation implemented
- [ ] add_followup implemented
- [ ] Generates unique conversation IDs
- [ ] Extracts confidence and reasoning
- [ ] All type hints correct
- [ ] Docstrings complete

**Tests:**
- [ ] Can instantiate with mock provider
- [ ] execute_with_conversation creates conversation
- [ ] Conversation ID stored after execution
- [ ] add_followup uses existing conversation
- [ ] add_followup raises error if no conversation: `pytest.raises(ValueError, executor.add_followup, "feedback", Model)`
- [ ] Confidence and reasoning extracted if present

**Rollback:** Delete ConversationalStageExecutor class

---

### Task 2.2: Create NonConversationalStageExecutor
**Effort:** Small (~1.5 hours)  
**Dependencies:** Task 1.9  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`

**Objective:** Create base class for non-conversational agents (Judge).

**Steps:**
1. Open `agent_patterns.py`
2. Create `NonConversationalStageExecutor` class extending `StageExecutor`
3. Implement `execute_single_turn(context, response_model)`:
   - Build system_prompt from `self.get_system_prompt()`
   - Build user_prompt from `self.build_user_prompt(context)`
   - Create messages list: `[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]`
   - Call `self.llm_provider.generate_json(messages, model, temperature)`
   - Parse response
   - Extract confidence and reasoning
   - Return AgentResult
4. Add docstrings

**Completion Criteria:**
- [ ] NonConversationalStageExecutor class exists
- [ ] Extends StageExecutor
- [ ] execute_single_turn implemented
- [ ] Uses generate_json (not conversation version)
- [ ] Extracts confidence and reasoning
- [ ] Type hints correct
- [ ] Docstrings complete

**Tests:**
- [ ] Can instantiate with mock provider
- [ ] execute_single_turn calls generate_json
- [ ] Does not create conversations
- [ ] Returns AgentResult with confidence and reasoning

**Rollback:** Delete NonConversationalStageExecutor class

---

### Task 2.3: Create PlannerAgent
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 2.1  
**Files:**
- Create: `packages/blinkb0t/core/agents/moving_heads/planner_agent.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/__init__.py` (update exports)

**Objective:** Refactor PlanGenerator to PlannerAgent using ConversationalStageExecutor.

**Steps:**
1. Copy `packages/blinkb0t/core/agents/moving_heads/plan_generator.py` to `planner_agent.py`
2. Rename class from `PlanGenerator` to `PlannerAgent`
3. Change parent class from `StageExecutor` to `ConversationalStageExecutor`
4. Update `__init__`:
   - Accept `llm_provider: LLMProvider` instead of `openai_client`
   - Pass to super().__init__()
5. Refactor `generate_plan` method:
   - Signature: `generate_plan(context: dict[str, Any], iteration: int) -> AgentResult[AgentPlan]`
   - Implementation: `return self.execute_with_conversation(context, AgentPlan, iteration)`
6. Add new method `refine_plan(feedback: str) -> AgentResult[AgentPlan]`:
   - Implementation: `return self.add_followup(feedback, AgentPlan)`
7. Update prompt templates to include confidence and reasoning in JSON schema:
   ```json
   {
     "segments": [...],
     "confidence": 0.85,
     "reasoning": "explanation"
   }
   ```
8. Update docstrings

**Completion Criteria:**
- [ ] PlannerAgent class exists
- [ ] Extends ConversationalStageExecutor
- [ ] generate_plan method works
- [ ] refine_plan method works
- [ ] Prompts updated for confidence/reasoning
- [ ] Type hints correct
- [ ] Imports updated in __init__.py

**Tests:**
- [ ] Can instantiate PlannerAgent
- [ ] generate_plan creates conversation
- [ ] generate_plan returns AgentResult[AgentPlan]
- [ ] refine_plan reuses conversation
- [ ] Confidence and reasoning present in result

**Rollback:** Delete planner_agent.py, restore exports

---

### Task 2.4: Create ImplementationAgent
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 2.1  
**Files:**
- Create: `packages/blinkb0t/core/agents/moving_heads/implementation_agent.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/__init__.py`

**Objective:** Refactor ImplementationExpander to ImplementationAgent using ConversationalStageExecutor.

**Steps:**
1. Copy `implementation_expander.py` to `implementation_agent.py`
2. Rename class to `ImplementationAgent`
3. Change parent to `ConversationalStageExecutor`
4. Update `__init__` to accept `llm_provider`
5. Refactor `expand_implementation` method:
   - Signature: `expand_implementation(context: dict[str, Any], iteration: int) -> AgentResult[AgentImplementation]`
   - Implementation: `return self.execute_with_conversation(context, AgentImplementation, iteration)`
6. Add `refine_implementation(feedback: str) -> AgentResult[AgentImplementation]`:
   - Implementation: `return self.add_followup(feedback, AgentImplementation)`
7. Update prompts for confidence/reasoning
8. Update docstrings

**Completion Criteria:**
- [ ] ImplementationAgent class exists
- [ ] Extends ConversationalStageExecutor
- [ ] expand_implementation works
- [ ] refine_implementation works
- [ ] Prompts include confidence/reasoning
- [ ] Type hints correct
- [ ] Exports updated

**Tests:**
- [ ] Can instantiate ImplementationAgent
- [ ] expand_implementation creates conversation
- [ ] expand_implementation returns AgentResult[AgentImplementation]
- [ ] refine_implementation reuses conversation
- [ ] Confidence and reasoning in result

**Rollback:** Delete implementation_agent.py, restore exports

---

### Task 2.5: Create JudgeAgent
**Effort:** Medium (~2.5 hours)  
**Dependencies:** Task 2.2  
**Files:**
- Create: `packages/blinkb0t/core/agents/moving_heads/judge_agent.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/__init__.py`

**Objective:** Refactor JudgeCritic to JudgeAgent using NonConversationalStageExecutor.

**Steps:**
1. Copy `judge_critic.py` to `judge_agent.py`
2. Rename class to `JudgeAgent`
3. Change parent to `NonConversationalStageExecutor`
4. Update `__init__` to accept `llm_provider`
5. Refactor `evaluate` method:
   - Signature: `evaluate(context: dict[str, Any]) -> AgentResult[AgentEvaluation]`
   - Implementation: `return self.execute_single_turn(context, AgentEvaluation)`
6. Update prompts for confidence/reasoning
7. Update docstrings

**Completion Criteria:**
- [ ] JudgeAgent class exists
- [ ] Extends NonConversationalStageExecutor
- [ ] evaluate method works
- [ ] Single-turn evaluation (no conversation)
- [ ] Prompts include confidence/reasoning
- [ ] Type hints correct
- [ ] Exports updated

**Tests:**
- [ ] Can instantiate JudgeAgent
- [ ] evaluate calls execute_single_turn
- [ ] Returns AgentResult[AgentEvaluation]
- [ ] No conversation created
- [ ] Confidence and reasoning in result

**Rollback:** Delete judge_agent.py, restore exports

---

### Task 2.6: Unit Tests for New Agents
**Effort:** Large (~4 hours)  
**Dependencies:** Task 2.3, 2.4, 2.5  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_planner_agent.py`
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_implementation_agent.py`
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_judge_agent.py`

**Objective:** Comprehensive unit tests for all refactored agents.

**Steps:**
1. Create test_planner_agent.py:
   - Test initialization
   - Test generate_plan with mock provider
   - Test refine_plan with mock provider
   - Test conversation ID generation
   - Test confidence and reasoning extraction
   - Test error handling
2. Create test_implementation_agent.py:
   - Similar tests for ImplementationAgent
3. Create test_judge_agent.py:
   - Test initialization
   - Test evaluate with mock provider
   - Test single-turn behavior
   - Test confidence and reasoning
4. Use mock LLMProvider in all tests
5. Verify all success and error paths

**Completion Criteria:**
- [ ] 30+ tests written across all agent test files
- [ ] All tests use mock provider
- [ ] Tests verify conversation behavior
- [ ] Tests verify confidence/reasoning extraction
- [ ] All tests pass
- [ ] Coverage >85% for agent files

**Tests:**
- [ ] Run: `pytest packages/blinkb0t/tests/core/agents/moving_heads/test_*_agent.py -v`
- [ ] All tests pass
- [ ] Coverage check

**Rollback:** Delete test files

---

### Task 2.7: Update Orchestrator to Use New Agents
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 2.3, 2.4, 2.5  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Update orchestrator to use new agent classes with provider.

**Steps:**
1. Open `orchestrator.py`
2. Update imports:
   - Import `OpenAIProvider` from `...api.llm.openai.provider`
   - Import `PlannerAgent, ImplementationAgent, JudgeAgent`
3. Update `__init__`:
   - Replace `self.openai_client = OpenAIClient(...)` with `self.llm_provider = OpenAIProvider(...)`
   - Replace `PlanGenerator(...)` with `PlannerAgent(..., self.llm_provider)`
   - Replace `ImplementationExpander(...)` with `ImplementationAgent(..., self.llm_provider)`
   - Replace `JudgeCritic(...)` with `JudgeAgent(..., self.llm_provider)`
4. Update any method calls to use new agent method names
5. Verify token tracking uses `self.llm_provider.get_token_usage()`

**Completion Criteria:**
- [ ] Imports updated
- [ ] llm_provider initialized instead of openai_client
- [ ] All agents initialized with provider
- [ ] Method calls updated
- [ ] Token tracking updated
- [ ] File compiles without errors

**Tests:**
- [ ] Orchestrator can initialize
- [ ] Agents accessible via orchestrator
- [ ] Token tracking works

**Rollback:** Revert to old imports and initialization

---

### Task 2.8: Integration Test - Orchestrator with New Agents
**Effort:** Medium (~2.5 hours)  
**Dependencies:** Task 2.7  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_orchestrator_agents.py`

**Objective:** Test orchestrator integration with refactored agents.

**Steps:**
1. Create integration test file
2. Mock OpenAIProvider responses
3. Write tests:
   - `test_orchestrator_initialization_with_provider()`
   - `test_planner_agent_integration()`
   - `test_implementation_agent_integration()`
   - `test_judge_agent_integration()`
   - `test_conversation_ids_unique()`
   - `test_token_tracking_through_provider()`
4. Verify end-to-end flow with mocks

**Completion Criteria:**
- [ ] Integration tests verify orchestrator works with new agents
- [ ] Tests verify provider integration
- [ ] Tests verify conversation management
- [ ] All tests pass

**Tests:**
- [ ] Run: `pytest test_orchestrator_agents.py -v`
- [ ] All tests pass

**Rollback:** Delete test file

---

**Phase 2 Checkpoint:**
- [ ] ConversationalStageExecutor implemented
- [ ] NonConversationalStageExecutor implemented
- [ ] PlannerAgent created and tested
- [ ] ImplementationAgent created and tested
- [ ] JudgeAgent created and tested
- [ ] Orchestrator updated to use new agents
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Conversation IDs unique and properly formatted

---

## Phase 3: State Machine with Observability
**Duration:** 3-4 days  
**Goal:** Implement state machine with comprehensive metrics tracking

### Task 3.1: Create State Machine Enums and Types
**Effort:** Small (~1.5 hours)  
**Dependencies:** None  
**Files:**
- Create: `packages/blinkb0t/core/agents/moving_heads/state_machine.py`

**Objective:** Define state machine enums and data structures.

**Steps:**
1. Create `state_machine.py`
2. Import `Enum`, `dataclass`, `field`, `time`, `logging`, `Any`
3. Define `OrchestrationState(str, Enum)`:
   - INITIALIZED = "initialized"
   - PLANNING = "planning"
   - VALIDATING = "validating"
   - IMPLEMENTING = "implementing"
   - JUDGING = "judging"
   - SUCCEEDED = "succeeded"
   - FAILED = "failed"
   - BUDGET_EXHAUSTED = "budget_exhausted"
4. Define `StateTransition` dataclass:
   - `from_state: OrchestrationState`
   - `to_state: OrchestrationState`
   - `timestamp: float`
   - `context: dict[str, Any]`
   - `reason: str | None = None`
   - `duration_seconds: float = 0.0`
   - `tokens_consumed: int = 0`
5. Define `StateMetrics` dataclass:
   - `state: OrchestrationState`
   - `visit_count: int = 0`
   - `total_duration_seconds: float = 0.0`
   - `total_tokens: int = 0`
   - `avg_duration_seconds: float = 0.0`
   - `avg_tokens: float = 0.0`
   - `min_duration_seconds: float = float('inf')`
   - `max_duration_seconds: float = 0.0`
6. Define `InvalidTransitionError(Exception)` class
7. Add docstrings

**Completion Criteria:**
- [ ] OrchestrationState enum with all 8 states
- [ ] StateTransition dataclass with metrics fields
- [ ] StateMetrics dataclass complete
- [ ] InvalidTransitionError defined
- [ ] All docstrings present
- [ ] File compiles

**Tests:**
- [ ] Can create enum values: `state = OrchestrationState.PLANNING`
- [ ] Can create StateTransition: `t = StateTransition(from_state=..., to_state=..., timestamp=time.time(), context={})`
- [ ] Can create StateMetrics: `m = StateMetrics(state=OrchestrationState.PLANNING)`

**Rollback:** Delete state_machine.py

---

### Task 3.2: Implement State Machine Core Logic
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 3.1  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/state_machine.py`

**Objective:** Implement OrchestrationStateMachine with transition logic.

**Steps:**
1. Create `OrchestrationStateMachine` class
2. Define `VALID_TRANSITIONS` class variable as dict mapping states to valid next states
3. Define `TERMINAL_STATES` as set containing SUCCEEDED, FAILED, BUDGET_EXHAUSTED
4. Implement `__init__`:
   - `self.current_state = OrchestrationState.INITIALIZED`
   - `self.history: list[StateTransition] = []`
   - `self.iteration_count = 0`
   - `self.max_iterations = 3`
5. Implement `can_transition_to(state)`:
   - Check if state in VALID_TRANSITIONS[current_state]
6. Implement `is_terminal()`:
   - Check if current_state in TERMINAL_STATES
7. Implement `transition(to_state, context, reason, duration_seconds, tokens_consumed)`:
   - Validate transition using can_transition_to
   - Raise InvalidTransitionError if invalid
   - Check if already terminal (log warning, return False)
   - Create StateTransition object
   - Append to history
   - Update current_state
   - Increment iteration_count if leaving PLANNING
   - Log transition with metrics
   - Return True
8. Implement `reset()`:
   - Reset to INITIALIZED
   - Clear history
   - Reset iteration_count
9. Implement `exceeded_max_iterations()`:
   - Return iteration_count >= max_iterations
10. Add docstrings

**Completion Criteria:**
- [ ] OrchestrationStateMachine class exists
- [ ] VALID_TRANSITIONS complete for all states
- [ ] TERMINAL_STATES correct
- [ ] transition() validates and records transitions
- [ ] transition() tracks metrics
- [ ] transition() increments iterations correctly
- [ ] can_transition_to() works
- [ ] is_terminal() works
- [ ] reset() works
- [ ] Raises InvalidTransitionError for invalid transitions

**Tests:**
- [ ] Test valid transition: `sm.transition(PLANNING)` from INITIALIZED succeeds
- [ ] Test invalid transition: `sm.transition(SUCCEEDED)` from INITIALIZED raises InvalidTransitionError
- [ ] Test terminal state prevents transitions
- [ ] Test iteration counting: transitions from PLANNING increment count
- [ ] Test metrics recording: transition with duration/tokens recorded
- [ ] Test reset: all state cleared

**Rollback:** Remove OrchestrationStateMachine class

---

### Task 3.3: Implement State Machine Observability Methods
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 3.2  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/state_machine.py`

**Objective:** Add metrics aggregation and analysis methods.

**Steps:**
1. Implement `get_state_metrics(state: OrchestrationState) -> StateMetrics`:
   - Filter history for transitions FROM this state
   - Calculate visit_count, total_duration, total_tokens
   - Calculate averages, min, max
   - Return StateMetrics object
2. Implement `get_all_state_metrics() -> dict[OrchestrationState, StateMetrics]`:
   - Loop through all non-terminal states
   - Call get_state_metrics for each
   - Return dict
3. Implement `get_total_metrics() -> dict[str, Any]`:
   - Sum all duration_seconds from history
   - Sum all tokens_consumed from history
   - Count transitions
   - Count state visits
   - Return dict with totals and current_state
4. Implement `get_transition_metrics() -> dict[str, Any]`:
   - Count occurrences of each transition type (from → to)
   - Find most common transition
   - Return dict with counts and most_common
5. Implement `get_bottleneck_analysis() -> dict[str, Any]`:
   - Get all state metrics
   - Find slowest state (max avg_duration)
   - Find highest token state (max avg_tokens)
   - Calculate per-iteration averages
   - Return dict with analysis
6. Implement `format_metrics_report() -> str`:
   - Build human-readable report string
   - Include total metrics
   - Include state visit counts
   - Include bottleneck analysis
   - Include transition patterns
   - Return formatted string
7. Implement `get_transition_history() -> list[StateTransition]`:
   - Return copy of history
8. Add docstrings to all methods

**Completion Criteria:**
- [ ] All 7 methods implemented
- [ ] get_state_metrics calculates correct aggregations
- [ ] get_bottleneck_analysis identifies slowest/highest token states
- [ ] format_metrics_report produces readable output
- [ ] All calculations correct (averages, min, max)
- [ ] Type hints correct
- [ ] Docstrings complete

**Tests:**
- [ ] Test get_state_metrics: create transitions, verify counts and averages
- [ ] Test get_bottleneck_analysis: verify slowest state identified
- [ ] Test format_metrics_report: verify output is string
- [ ] Test with no transitions: verify handles empty history
- [ ] Test metrics accuracy: known transitions produce expected aggregations

**Rollback:** Remove observability methods

---

### Task 3.4: Create State Machine Unit Tests
**Effort:** Large (~4 hours)  
**Dependencies:** Task 3.3  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_state_machine.py`

**Objective:** Comprehensive tests for state machine including observability.

**Steps:**
1. Create test file
2. Import pytest, OrchestrationStateMachine, states, exceptions
3. Create fixtures for initialized state machine
4. Write test suite (20+ tests):
   - Test initialization
   - Test valid transitions (all combinations)
   - Test invalid transitions raise errors
   - Test terminal states
   - Test iteration counting
   - Test metrics recording
   - Test get_state_metrics
   - Test get_all_state_metrics
   - Test get_total_metrics
   - Test get_transition_metrics
   - Test get_bottleneck_analysis
   - Test format_metrics_report
   - Test reset
   - Test exceeded_max_iterations
   - Test transition history
5. Test edge cases (empty history, single transition, etc.)

**Completion Criteria:**
- [ ] 25+ tests written
- [ ] All state transitions tested
- [ ] All metrics methods tested
- [ ] Edge cases covered
- [ ] All tests pass
- [ ] Coverage >90% for state_machine.py

**Tests:**
- [ ] Run: `pytest test_state_machine.py -v`
- [ ] All tests pass
- [ ] Coverage check

**Rollback:** Delete test file

---

### Task 3.5: Integrate State Machine into Orchestrator (Basic)
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 3.3, Task 2.7  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Add state machine to orchestrator without changing flow yet.

**Steps:**
1. Open orchestrator.py
2. Import `OrchestrationStateMachine, OrchestrationState, InvalidTransitionError`
3. In `__init__`:
   - Add `self.state_machine = OrchestrationStateMachine()`
   - Set `self.state_machine.max_iterations = job_config.agent.max_iterations`
4. Add `self.agent_responses: dict[str, AgentResult] = {}` for tracking
5. Do NOT change the main loop yet (keep existing iteration logic)
6. Add helper method `_track_state_metrics(start_time, tokens_before) -> tuple[float, int]`:
   - Calculate duration: `time.time() - start_time`
   - Calculate tokens: `self.llm_provider.get_token_usage().total_tokens - tokens_before`
   - Return tuple
7. Add docstrings

**Completion Criteria:**
- [ ] State machine initialized in orchestrator
- [ ] max_iterations set from config
- [ ] agent_responses dict added
- [ ] Helper method for metrics tracking added
- [ ] Existing flow unchanged
- [ ] File compiles

**Tests:**
- [ ] Orchestrator initializes with state machine
- [ ] State machine has correct max_iterations
- [ ] agent_responses dict exists

**Rollback:** Remove state machine initialization and related code

---

### Task 3.6: Replace Iteration Loop with State Machine
**Effort:** Large (~5 hours)  
**Dependencies:** Task 3.5  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Replace manual iteration loop with state machine driven flow.

**Steps:**
1. Open orchestrator.py main `run()` method
2. Replace `while iteration < max_iterations:` with:
   ```python
   # Transition to planning
   self.state_machine.transition(OrchestrationState.PLANNING)
   
   while not self.state_machine.is_terminal():
       state = self.state_machine.current_state
       start_time = time.time()
       tokens_before = self.llm_provider.get_token_usage().total_tokens
       
       # Execute state-specific logic...
   ```
3. Implement state-specific blocks:
   - `if state == OrchestrationState.PLANNING:`
   - `elif state == OrchestrationState.VALIDATING:`
   - `elif state == OrchestrationState.IMPLEMENTING:`
   - `elif state == OrchestrationState.JUDGING:`
4. Each block:
   - Execute appropriate agent/validator
   - Calculate metrics using helper
   - Store result in `self.agent_responses`
   - Call `self.state_machine.transition()` with next state, metrics, reason
5. Add budget check:
   - After each stage, check existing budget system
   - If exhausted: `self.state_machine.transition(BUDGET_EXHAUSTED, reason="...")`
6. Add max iterations check:
   - If exceeded: transition to FAILED
7. Handle validation failures: transition back to PLANNING
8. Handle judge failures: transition to IMPLEMENTING (soft) or PLANNING (hard)
9. Log metrics report at end: `logger.info(self.state_machine.format_metrics_report())`
10. Update `_build_result()` to use `self.state_machine.current_state`

**Completion Criteria:**
- [ ] Iteration loop replaced with state machine
- [ ] All state transitions implemented
- [ ] Metrics tracked and passed to transitions
- [ ] Agent responses stored
- [ ] Budget integration works
- [ ] Max iterations check works
- [ ] Validation/judge failure paths correct
- [ ] Metrics report logged
- [ ] File compiles and runs

**Tests:**
- [ ] Test happy path: PLANNING → VALIDATING → IMPLEMENTING → JUDGING → SUCCEEDED
- [ ] Test validation failure: loops back to PLANNING
- [ ] Test judge soft failure: loops to IMPLEMENTING
- [ ] Test judge hard failure: loops to PLANNING
- [ ] Test budget exhaustion: transitions to BUDGET_EXHAUSTED
- [ ] Test max iterations: transitions to FAILED
- [ ] Test metrics recording: verify non-zero durations and tokens

**Rollback:** Revert to old iteration loop

---

### Task 3.7: Update Checkpointing for State Machine
**Effort:** Medium (~2.5 hours)  
**Dependencies:** Task 3.6  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/checkpoint_manager.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Save and restore state machine with metrics in checkpoints.

**Steps:**
1. Open checkpoint_manager.py
2. Update `save_orchestration_state()` signature:
   - Add `state_machine: OrchestrationStateMachine` parameter
   - Add `agent_responses: dict[str, AgentResult]` parameter
3. Serialize state machine:
   - current_state (value)
   - iteration_count
   - history (list of dicts with all transition fields)
4. Serialize agent_responses:
   - For each response: success, data (model_dump), tokens_used, metadata, confidence, reasoning
5. Write to checkpoint
6. Implement `load_orchestration_state()`:
   - Read checkpoint
   - Reconstruct state machine
   - Restore history with metrics
   - Restore agent_responses
   - Return dict with all data
7. Update orchestrator to use new checkpoint methods:
   - Call save_orchestration_state with state_machine and agent_responses
   - On resume, load and restore state

**Completion Criteria:**
- [ ] Checkpoint saves state machine with metrics
- [ ] Checkpoint saves agent responses
- [ ] Load reconstructs state machine correctly
- [ ] History preserved with all fields
- [ ] Agent responses restored
- [ ] Orchestrator uses new methods

**Tests:**
- [ ] Test save and load state machine
- [ ] Test metrics preserved across save/load
- [ ] Test agent responses preserved
- [ ] Test resume from checkpoint continues correctly

**Rollback:** Revert checkpoint changes

---

### Task 3.8: Integration Test - State Machine Flow
**Effort:** Large (~4 hours)  
**Dependencies:** Task 3.7  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_state_machine_integration.py`

**Objective:** Test complete state machine integration with orchestrator.

**Steps:**
1. Create integration test file
2. Mock all agents and provider
3. Write tests for each workflow:
   - Happy path (success on first iteration)
   - Validation failure path
   - Soft failure path
   - Hard failure path
   - Budget exhaustion path
   - Max iterations path
4. Verify state transitions match expected
5. Verify metrics recorded correctly
6. Verify checkpointing works
7. Verify final state correct

**Completion Criteria:**
- [ ] 6+ workflow tests written
- [ ] All expected state transitions verified
- [ ] Metrics verified
- [ ] Checkpointing verified
- [ ] All tests pass

**Tests:**
- [ ] Run: `pytest test_state_machine_integration.py -v`
- [ ] All tests pass

**Rollback:** Delete test file

---

**Phase 3 Checkpoint:**
- [ ] State machine fully implemented with observability
- [ ] Orchestrator uses state machine for flow control
- [ ] Metrics tracked per state
- [ ] Bottleneck analysis working
- [ ] Checkpointing includes state machine
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Metrics report logs useful information

---

## Phase 4: Feedback Management
**Duration:** 2-3 days  
**Goal:** Implement structured feedback accumulation with FIFO trimming

### Task 4.1: Create Feedback Types and Entry
**Effort:** Small (~1.5 hours)  
**Dependencies:** None  
**Files:**
- Create: `packages/blinkb0t/core/agents/moving_heads/feedback_manager.py`

**Objective:** Define feedback data structures.

**Steps:**
1. Create feedback_manager.py
2. Import `dataclass`, `field`, `Enum`, `time`, `Any`, `tiktoken`
3. Define `FeedbackType(str, Enum)`:
   - VALIDATION_FAILURE = "validation_failure"
   - JUDGE_SOFT_FAILURE = "judge_soft_failure"
   - JUDGE_HARD_FAILURE = "judge_hard_failure"
4. Define `FeedbackEntry` dataclass:
   - `type: FeedbackType`
   - `content: str`
   - `iteration: int`
   - `timestamp: float`
   - `priority: int = 0`
   - `metadata: dict[str, Any] = field(default_factory=dict)`
5. Add docstrings

**Completion Criteria:**
- [ ] FeedbackType enum with 3 types
- [ ] FeedbackEntry dataclass complete
- [ ] All fields have correct types
- [ ] Docstrings present
- [ ] File compiles

**Tests:**
- [ ] Can create FeedbackType: `ft = FeedbackType.VALIDATION_FAILURE`
- [ ] Can create FeedbackEntry: `entry = FeedbackEntry(type=..., content="...", iteration=1, timestamp=time.time())`

**Rollback:** Delete feedback_manager.py

---

### Task 4.2: Implement FeedbackManager Core
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 4.1  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/feedback_manager.py`

**Objective:** Implement feedback accumulation and management.

**Steps:**
1. Create `FeedbackManager` class
2. Implement `__init__(max_feedback_tokens: int, model: str)`:
   - Store max_feedback_tokens
   - Initialize `self.feedback_history: list[FeedbackEntry] = []`
   - Initialize `self.encoding = tiktoken.encoding_for_model(model)`
3. Implement `add_feedback(feedback_type, content, iteration, priority, metadata)`:
   - Create FeedbackEntry
   - Append to feedback_history
   - Log addition
4. Implement `clear()`:
   - Clear feedback_history
5. Implement `get_feedback_summary() -> dict[str, Any]`:
   - Count total entries
   - Count by type
   - Count iterations with feedback
   - Return dict
6. Implement `_format_feedback_entry(entry: FeedbackEntry) -> str`:
   - Format as markdown section:
     ```
     ### Iteration {iteration} - {type}
     {content}
     ```
   - Return formatted string
7. Add docstrings

**Completion Criteria:**
- [ ] FeedbackManager class exists
- [ ] __init__ stores config and initializes encoding
- [ ] add_feedback appends entries
- [ ] clear works
- [ ] get_feedback_summary returns correct counts
- [ ] _format_feedback_entry produces correct format
- [ ] Docstrings complete

**Tests:**
- [ ] Can instantiate FeedbackManager
- [ ] add_feedback appends to history
- [ ] get_feedback_summary returns correct counts
- [ ] _format_feedback_entry produces expected format
- [ ] clear empties history

**Rollback:** Remove FeedbackManager class

---

### Task 4.3: Implement FIFO Trimming Logic
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 4.2  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/feedback_manager.py`

**Objective:** Implement get_feedback_for_prompt with FIFO trimming.

**Steps:**
1. Implement `_trim_to_token_limit(sections: list[str], max_tokens: int) -> str`:
   - Add header: "## Previous Feedback\n\n"
   - Calculate header tokens
   - Calculate available tokens
   - Iterate through sections (newest first):
     - Calculate section tokens
     - If total + section > available: break
     - Add section to included list
     - Update total
   - Reverse included list (to show oldest-to-newest)
   - Join with "\n\n"
   - Return formatted string
2. Implement `get_feedback_for_prompt(max_tokens, feedback_types) -> str`:
   - Use max_tokens or default
   - Filter feedback_history by types if specified
   - Return empty string if no feedback
   - Build sections list (reversed for newest-first)
   - Call _trim_to_token_limit
   - Return result
3. Add docstrings explaining FIFO approach

**Completion Criteria:**
- [ ] _trim_to_token_limit implemented
- [ ] FIFO approach: keeps newest feedback when trimming
- [ ] get_feedback_for_prompt filters by type correctly
- [ ] Token counting accurate using tiktoken
- [ ] Returns empty string for no feedback
- [ ] Docstrings explain FIFO logic

**Tests:**
- [ ] Test no feedback: returns empty string
- [ ] Test single feedback: returns formatted feedback
- [ ] Test multiple feedback under limit: returns all
- [ ] Test multiple feedback over limit: returns newest that fit
- [ ] Test type filtering: only returns specified types
- [ ] Test token counting: verify trimming at correct boundary

**Rollback:** Remove get_feedback_for_prompt and _trim_to_token_limit methods

---

### Task 4.4: Create FeedbackManager Unit Tests
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 4.3  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_feedback_manager.py`

**Objective:** Comprehensive tests for feedback manager.

**Steps:**
1. Create test file
2. Import pytest, FeedbackManager, FeedbackType, FeedbackEntry
3. Create fixtures for feedback manager
4. Write test suite (15+ tests):
   - Test initialization
   - Test add_feedback
   - Test get_feedback_summary
   - Test get_feedback_for_prompt with no feedback
   - Test get_feedback_for_prompt with single feedback
   - Test get_feedback_for_prompt with multiple under limit
   - Test get_feedback_for_prompt with FIFO trimming
   - Test feedback type filtering
   - Test _format_feedback_entry
   - Test clear
   - Test token counting accuracy
   - Test edge cases (empty content, very long content)
5. Mock tiktoken if needed for deterministic tests

**Completion Criteria:**
- [ ] 15+ tests written
- [ ] All methods tested
- [ ] FIFO trimming verified
- [ ] Type filtering verified
- [ ] Token counting verified
- [ ] All tests pass
- [ ] Coverage >90% for feedback_manager.py

**Tests:**
- [ ] Run: `pytest test_feedback_manager.py -v`
- [ ] All tests pass
- [ ] Coverage check

**Rollback:** Delete test file

---

### Task 4.5: Integrate FeedbackManager into Orchestrator
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 4.3, Task 3.6  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Add feedback manager to orchestrator and use it.

**Steps:**
1. Open orchestrator.py
2. Import `FeedbackManager, FeedbackType`
3. In `__init__`:
   - Add `self.feedback_manager = FeedbackManager(max_feedback_tokens=2000, model=job_config.agent.model)`
4. Update VALIDATING block:
   - On validation failure: `self.feedback_manager.add_feedback(FeedbackType.VALIDATION_FAILURE, failure_message, iteration)`
5. Update JUDGING block:
   - On soft failure: `self.feedback_manager.add_feedback(FeedbackType.JUDGE_SOFT_FAILURE, feedback, iteration)`
   - On hard failure: `self.feedback_manager.add_feedback(FeedbackType.JUDGE_HARD_FAILURE, feedback, iteration)`
6. Update `_execute_planning()` method:
   - Get feedback: `feedback = self.feedback_manager.get_feedback_for_prompt(feedback_types=[VALIDATION_FAILURE, JUDGE_HARD_FAILURE])`
   - Build context with feedback
   - Pass to planner
7. Update `_execute_implementation()` method:
   - Get feedback: `feedback = self.feedback_manager.get_feedback_for_prompt(feedback_types=[JUDGE_SOFT_FAILURE])`
   - Build context with feedback
   - Pass to implementation agent
8. Create helper methods:
   - `_build_planning_feedback(evaluation, failure_analysis) -> str`
   - `_build_implementation_feedback(evaluation, failure_analysis) -> str`
9. Log feedback summary at end

**Completion Criteria:**
- [ ] FeedbackManager initialized
- [ ] Feedback added on all failure types
- [ ] Feedback retrieved and filtered correctly
- [ ] Feedback injected into agent contexts
- [ ] Helper methods build useful feedback
- [ ] Feedback summary logged

**Tests:**
- [ ] Orchestrator initializes with feedback manager
- [ ] Validation failure adds feedback
- [ ] Judge failures add feedback
- [ ] Planning gets correct feedback types
- [ ] Implementation gets correct feedback types

**Rollback:** Remove feedback manager integration

---

### Task 4.6: Update Checkpointing for Feedback
**Effort:** Small (~2 hours)  
**Dependencies:** Task 4.5, Task 3.7  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/checkpoint_manager.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Save and restore feedback manager state in checkpoints.

**Steps:**
1. Update `save_orchestration_state()`:
   - Add `feedback_manager: FeedbackManager` parameter
   - Serialize feedback_history: type, content, iteration, timestamp, priority, metadata for each entry
   - Add to checkpoint data
2. Update `load_orchestration_state()`:
   - Reconstruct FeedbackManager
   - Recreate FeedbackEntry objects from checkpoint
   - Restore to feedback_manager.feedback_history
   - Return in result dict
3. Update orchestrator checkpoint calls:
   - Pass feedback_manager to save
   - Restore feedback_manager on load

**Completion Criteria:**
- [ ] Checkpoint saves feedback history
- [ ] Load reconstructs feedback manager
- [ ] All feedback entries preserved
- [ ] Orchestrator uses updated methods

**Tests:**
- [ ] Test save and load feedback manager
- [ ] Test feedback entries preserved
- [ ] Test resume continues with accumulated feedback

**Rollback:** Revert checkpoint changes

---

### Task 4.7: Integration Test - Feedback Flows
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 4.6  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_feedback_integration.py`

**Objective:** Test feedback management in orchestration workflows.

**Steps:**
1. Create integration test file
2. Mock agents and provider
3. Write tests:
   - Test feedback accumulation across iterations
   - Test feedback filtering by type
   - Test FIFO trimming in real scenarios
   - Test feedback injection into agents
   - Test feedback in checkpoints
   - Test multiple feedback types
4. Verify feedback appears in agent contexts
5. Verify trimming works correctly

**Completion Criteria:**
- [ ] 6+ integration tests written
- [ ] Feedback accumulation verified
- [ ] Filtering verified
- [ ] Trimming verified
- [ ] Injection verified
- [ ] All tests pass

**Tests:**
- [ ] Run: `pytest test_feedback_integration.py -v`
- [ ] All tests pass

**Rollback:** Delete test file

---

**Phase 4 Checkpoint:**
- [ ] FeedbackManager fully implemented
- [ ] FIFO trimming working correctly
- [ ] Integrated into orchestrator
- [ ] Feedback added on failures
- [ ] Feedback injected into agents
- [ ] Checkpointing includes feedback
- [ ] All tests pass
- [ ] Token limits respected

---

## Phase 5: Refinement Simplification
**Duration:** 2-3 days  
**Goal:** Remove RefinementAgent, use follow-up messages

### Task 5.1: Update Planning Stage for Refinement
**Effort:** Medium (~2 hours)  
**Dependencies:** Task 4.5, Task 2.3  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Make planning stage handle both initial and refinement via follow-ups.

**Steps:**
1. Open orchestrator.py
2. Update `_execute_planning()` method:
   - Check if `self.planner.conversation_id` exists
   - If exists (refinement):
     - Get feedback for planning
     - Call `self.planner.refine_plan(feedback)`
   - If not exists (initial):
     - Get feedback (may be empty for first iteration)
     - Build context with feedback
     - Call `self.planner.generate_plan(context, iteration)`
3. Ensure feedback includes validation and hard failures
4. Log whether initial or refinement

**Completion Criteria:**
- [ ] Planning stage checks for existing conversation
- [ ] Initial planning calls generate_plan
- [ ] Refinement calls refine_plan
- [ ] Feedback injected in both cases
- [ ] Logging distinguishes initial vs refinement

**Tests:**
- [ ] Test initial planning: no conversation, calls generate_plan
- [ ] Test refinement: has conversation, calls refine_plan
- [ ] Test feedback injection in both cases

**Rollback:** Revert _execute_planning method

---

### Task 5.2: Update Implementation Stage for Refinement
**Effort:** Medium (~2 hours)  
**Dependencies:** Task 4.5, Task 2.4  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Make implementation stage handle both initial and refinement via follow-ups.

**Steps:**
1. Update `_execute_implementation()` method:
   - Check if `self.implementation.conversation_id` exists
   - If exists (refinement):
     - Get feedback for implementation
     - Call `self.implementation.refine_implementation(feedback)`
   - If not exists (initial):
     - Get feedback (should be empty initially)
     - Build context with feedback
     - Call `self.implementation.expand_implementation(context, iteration)`
2. Ensure feedback includes only soft failures
3. Log whether initial or refinement

**Completion Criteria:**
- [ ] Implementation stage checks for existing conversation
- [ ] Initial calls expand_implementation
- [ ] Refinement calls refine_implementation
- [ ] Feedback filtered to soft failures only
- [ ] Logging distinguishes initial vs refinement

**Tests:**
- [ ] Test initial implementation: no conversation, calls expand_implementation
- [ ] Test refinement: has conversation, calls refine_implementation
- [ ] Test feedback filtering

**Rollback:** Revert _execute_implementation method

---

### Task 5.3: Update Judge Failure Handling
**Effort:** Small (~1.5 hours)  
**Dependencies:** Task 5.1, Task 5.2  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Ensure judge failures transition correctly for refinement.

**Steps:**
1. Update JUDGING state block:
   - On soft failure:
     - Analyze failure
     - Build implementation feedback
     - Add to feedback_manager
     - Transition to IMPLEMENTING (not new state)
     - Do NOT increment iteration
   - On hard failure:
     - Analyze failure
     - Build planning feedback
     - Add to feedback_manager
     - Transition to PLANNING
     - Create NEW conversation for planner (clear conversation_id)
     - Iteration will increment on next PLANNING transition
2. Ensure soft failure reuses implementation conversation
3. Ensure hard failure creates new planner conversation

**Completion Criteria:**
- [ ] Soft failure transitions to IMPLEMENTING
- [ ] Soft failure reuses conversation
- [ ] Hard failure transitions to PLANNING
- [ ] Hard failure creates new planner conversation
- [ ] Iteration counting correct
- [ ] Feedback added for both types

**Tests:**
- [ ] Test soft failure: transitions to IMPLEMENTING, same conversation
- [ ] Test hard failure: transitions to PLANNING, new conversation
- [ ] Test iteration count: soft doesn't increment, hard does

**Rollback:** Revert JUDGING block changes

---

### Task 5.4: Remove RefinementAgent
**Effort:** Small (~1 hour)  
**Dependencies:** Task 5.3  
**Files:**
- Delete: `packages/blinkb0t/core/agents/moving_heads/refinement_agent.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/__init__.py`
- Modify: `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`

**Objective:** Delete RefinementAgent and remove all references.

**Steps:**
1. Search orchestrator for any remaining references to RefinementAgent
2. Remove any RefinementAgent imports
3. Remove any RefinementAgent initialization
4. Delete `refinement_agent.py` file
5. Update `__init__.py` to remove RefinementAgent export
6. Verify no other files reference RefinementAgent

**Completion Criteria:**
- [ ] refinement_agent.py deleted
- [ ] No imports of RefinementAgent
- [ ] No RefinementAgent initialization
- [ ] No references in orchestrator
- [ ] __init__.py updated
- [ ] All code compiles

**Tests:**
- [ ] Search codebase: `grep -r "RefinementAgent"` returns no results (except maybe tests)
- [ ] Orchestrator compiles
- [ ] No import errors

**Rollback:** Restore refinement_agent.py and references

---

### Task 5.5: Update Existing Tests for Refinement Changes
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 5.4  
**Files:**
- Modify: Various test files that reference RefinementAgent or refinement logic

**Objective:** Update tests to work with new refinement approach.

**Steps:**
1. Search for tests referencing RefinementAgent
2. Update or delete these tests
3. Update orchestrator tests to verify:
   - Soft failure refinement via follow-up
   - Hard failure replanning with new conversation
   - Conversation reuse for soft failures
   - New conversation for hard failures
4. Update any integration tests affected by changes
5. Ensure all test suites pass

**Completion Criteria:**
- [ ] All RefinementAgent tests removed or updated
- [ ] Orchestrator tests cover new refinement logic
- [ ] Integration tests updated
- [ ] All test suites pass
- [ ] No broken tests

**Tests:**
- [ ] Run full test suite: `pytest packages/blinkb0t/tests/ -v`
- [ ] All tests pass

**Rollback:** Revert test changes

---

### Task 5.6: Integration Test - Refinement Workflows
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 5.5  
**Files:**
- Create: `packages/blinkb0t/tests/core/agents/moving_heads/test_refinement_workflows.py`

**Objective:** Test complete refinement workflows end-to-end.

**Steps:**
1. Create test file
2. Mock agents and provider
3. Write workflow tests:
   - Test soft failure refinement (implementation)
   - Test hard failure refinement (planning)
   - Test multiple soft failures in a row
   - Test mixed soft and hard failures
   - Test conversation continuity for soft
   - Test new conversation for hard
4. Verify conversation IDs correctly managed
5. Verify feedback correctly filtered
6. Verify iteration counting correct

**Completion Criteria:**
- [ ] 6+ workflow tests written
- [ ] Soft failure refinement verified
- [ ] Hard failure refinement verified
- [ ] Conversation management verified
- [ ] All tests pass

**Tests:**
- [ ] Run: `pytest test_refinement_workflows.py -v`
- [ ] All tests pass

**Rollback:** Delete test file

---

**Phase 5 Checkpoint:**
- [ ] Refinement works via follow-up messages
- [ ] RefinementAgent deleted (~200 LOC removed)
- [ ] Soft failures refine implementation
- [ ] Hard failures replan with new conversation
- [ ] Conversation management correct
- [ ] All tests pass
- [ ] Code reduction achieved

---

## Phase 6: Documentation and Examples
**Duration:** 1-2 days  
**Goal:** Update documentation, add examples, verify all workflows

### Task 6.1: Update Agent Docstrings
**Effort:** Small (~2 hours)  
**Dependencies:** Task 2.6  
**Files:**
- Modify: All agent files (planner_agent.py, implementation_agent.py, judge_agent.py)

**Objective:** Ensure all agents have comprehensive docstrings.

**Steps:**
1. Open each agent file
2. Update class docstrings:
   - Explain purpose
   - Explain conversation behavior
   - Note confidence and reasoning
3. Update method docstrings:
   - Explain parameters
   - Explain return values
   - Provide usage examples
4. Add module-level docstrings

**Completion Criteria:**
- [ ] All agent classes have docstrings
- [ ] All public methods have docstrings
- [ ] Examples included where helpful
- [ ] Module-level docstrings present

**Tests:**
- [ ] Docstrings render correctly: `python -m pydoc blinkb0t.core.agents.moving_heads.planner_agent`
- [ ] No missing docstring warnings

**Rollback:** Revert docstring changes

---

### Task 6.2: Create Usage Examples
**Effort:** Medium (~3 hours)  
**Dependencies:** All previous tasks  
**Files:**
- Create: `packages/blinkb0t/examples/agent_refactoring/`
  - `basic_provider_usage.py`
  - `conversational_agent_usage.py`
  - `state_machine_usage.py`
  - `feedback_management_usage.py`
  - `complete_workflow.py`

**Objective:** Provide working examples for all major features.

**Steps:**
1. Create examples directory
2. Write `basic_provider_usage.py`:
   - Show OpenAIProvider initialization
   - Show simple generate_json call
   - Show conversation usage
3. Write `conversational_agent_usage.py`:
   - Show PlannerAgent usage
   - Show initial plan and refinement
   - Show conversation ID management
4. Write `state_machine_usage.py`:
   - Show state machine setup
   - Show transitions
   - Show metrics retrieval
5. Write `feedback_management_usage.py`:
   - Show FeedbackManager setup
   - Show adding feedback
   - Show FIFO trimming
6. Write `complete_workflow.py`:
   - End-to-end example with all components
   - Show happy path
   - Show failure and refinement
7. Add README.md in examples directory

**Completion Criteria:**
- [ ] All 5 example files created
- [ ] Each example runs without errors
- [ ] Examples demonstrate key features
- [ ] README explains examples
- [ ] Code is well-commented

**Tests:**
- [ ] Run each example: `python basic_provider_usage.py`
- [ ] All examples execute successfully

**Rollback:** Delete examples directory

---

### Task 6.3: Update Main README
**Effort:** Small (~1.5 hours)  
**Dependencies:** Task 6.2  
**Files:**
- Modify: `packages/blinkb0t/core/agents/moving_heads/README.md`

**Objective:** Update README with new architecture information.

**Steps:**
1. Open README.md
2. Update architecture section:
   - Show new agent hierarchy
   - Explain provider abstraction
   - Explain state machine
   - Explain feedback management
3. Add "New Features" section:
   - Conversational agents
   - Observability metrics
   - Structured feedback
   - Enhanced checkpointing
4. Add "Migration Notes" section:
   - What changed
   - What was removed (RefinementAgent)
   - Breaking changes
5. Add links to examples
6. Update any diagrams

**Completion Criteria:**
- [ ] README updated with new architecture
- [ ] New features documented
- [ ] Migration notes present
- [ ] Examples linked
- [ ] Clear and well-formatted

**Tests:**
- [ ] README renders correctly in markdown viewer
- [ ] Links work

**Rollback:** Revert README changes

---

### Task 6.4: Create Migration Guide for Users
**Effort:** Small (~2 hours)  
**Dependencies:** Task 6.3  
**Files:**
- Create: `packages/blinkb0t/docs/MIGRATION_GUIDE.md`

**Objective:** Provide guide for users migrating to new architecture.

**Steps:**
1. Create MIGRATION_GUIDE.md
2. Document breaking changes:
   - PlanGenerator → PlannerAgent
   - ImplementationExpander → ImplementationAgent
   - JudgeCritic → JudgeAgent
   - RefinementAgent removed
   - OpenAIClient → LLMProvider
3. Provide code examples:
   - Before: old code
   - After: new code
4. Document new features:
   - Conversation IDs
   - Confidence and reasoning
   - Feedback management
   - Metrics
5. Provide troubleshooting section

**Completion Criteria:**
- [ ] Migration guide complete
- [ ] Breaking changes documented
- [ ] Examples provided
- [ ] Troubleshooting section present

**Tests:**
- [ ] Guide is clear and understandable
- [ ] Examples are correct

**Rollback:** Delete migration guide

---

**Phase 6 Checkpoint:**
- [ ] All docstrings updated
- [ ] Usage examples created and working
- [ ] README updated
- [ ] Migration guide created
- [ ] Documentation comprehensive

---

## Phase 7: Final Testing and Cleanup
**Duration:** 2-3 days  
**Goal:** Comprehensive testing, cleanup, and release preparation

### Task 7.1: Run Full Test Suite
**Effort:** Small (~1 hour)  
**Dependencies:** All previous tasks  
**Files:** N/A (running tests)

**Objective:** Verify all tests pass.

**Steps:**
1. Run complete test suite: `pytest packages/blinkb0t/tests/ -v`
2. Verify no failures
3. Check test coverage: `pytest --cov=packages/blinkb0t/core/agents/moving_heads --cov=packages/blinkb0t/core/api/llm`
4. Verify coverage >85% for refactored code
5. Run type checking: `mypy packages/blinkb0t/core/agents/moving_heads`
6. Verify no type errors
7. Fix any issues found

**Completion Criteria:**
- [ ] All tests pass (100%)
- [ ] Coverage >85% for refactored modules
- [ ] No type check errors
- [ ] No linting errors

**Tests:**
- [ ] `pytest packages/blinkb0t/tests/ -v` → all pass
- [ ] Coverage report generated
- [ ] `mypy` passes

**Rollback:** N/A (identify issues)

---

### Task 7.2: Performance Testing
**Effort:** Medium (~3 hours)  
**Dependencies:** Task 7.1  
**Files:**
- Create: `packages/blinkb0t/tests/performance/test_agent_refactoring_performance.py`

**Objective:** Verify no performance regression from refactoring.

**Steps:**
1. Create performance test file
2. Create baseline performance test with old code (if available)
3. Create performance test with new code
4. Test scenarios:
   - Single iteration execution time
   - Token usage accuracy
   - Memory usage
   - State machine overhead
   - Feedback manager overhead
5. Compare results
6. Verify overhead <5%
7. Document performance characteristics

**Completion Criteria:**
- [ ] Performance tests written
- [ ] Baseline comparison done
- [ ] Overhead <5% (or acceptable)
- [ ] Token usage accurate
- [ ] Memory usage acceptable
- [ ] Results documented

**Tests:**
- [ ] Run performance tests
- [ ] Review results
- [ ] Verify acceptable performance

**Rollback:** N/A (identify issues)

---

### Task 7.3: End-to-End Integration Tests
**Effort:** Large (~4 hours)  
**Dependencies:** Task 7.1  
**Files:**
- Create: `packages/blinkb0t/tests/integration/test_complete_workflows.py`

**Objective:** Test all example workflows end-to-end.

**Steps:**
1. Create integration test file
2. Set up real (or realistic mock) environment
3. Test all 6 example workflows:
   - Happy path
   - Validation failure
   - Soft failure
   - Hard failure
   - Budget exhaustion
   - Multiple feedback accumulation
4. Verify state transitions match expected
5. Verify metrics recorded correctly
6. Verify agent responses correct
7. Verify checkpointing works
8. Verify feedback accumulates correctly
9. Use actual audio files and configurations

**Completion Criteria:**
- [ ] 6 workflow integration tests written
- [ ] All workflows tested end-to-end
- [ ] Tests use realistic scenarios
- [ ] All assertions pass
- [ ] Tests run in <5 minutes total

**Tests:**
- [ ] Run: `pytest test_complete_workflows.py -v -s`
- [ ] All workflows pass
- [ ] Review logged metrics for sanity

**Rollback:** N/A (identify issues)

---

### Task 7.4: Code Cleanup
**Effort:** Medium (~2.5 hours)  
**Dependencies:** Task 7.3  
**Files:** Various

**Objective:** Clean up any remaining old code, TODOs, and unused imports.

**Steps:**
1. Search for old agent references:
   - `grep -r "PlanGenerator"` (should be none except tests/docs)
   - `grep -r "ImplementationExpander"`
   - `grep -r "JudgeCritic"`
   - `grep -r "RefinementAgent"`
   - `grep -r "OpenAIClient"` (should only be in provider implementation)
2. Search for TODO comments: `grep -r "TODO"`
3. Resolve or document all TODOs
4. Remove unused imports:
   - Use tool like `autoflake` or manual review
5. Remove commented-out code
6. Verify consistent code style:
   - Run `black` formatter
   - Run `isort` for imports
7. Update any stale comments

**Completion Criteria:**
- [ ] No references to old agent names (except docs)
- [ ] All TODOs resolved or documented
- [ ] No unused imports
- [ ] No commented-out code
- [ ] Code formatted consistently
- [ ] Comments up to date

**Tests:**
- [ ] Run: `black packages/blinkb0t/core/agents/moving_heads/`
- [ ] Run: `isort packages/blinkb0t/core/agents/moving_heads/`
- [ ] Verify code compiles after cleanup

**Rollback:** Git revert cleanup commits

---

### Task 7.5: Verify Success Metrics
**Effort:** Small (~1 hour)  
**Dependencies:** Task 7.4  
**Files:** N/A

**Objective:** Verify all success criteria met.

**Steps:**
1. Review success criteria from plan:
   - [ ] All agents extend appropriate base executors
   - [ ] LLMProvider abstraction supports OpenAI (Claude-ready)
   - [ ] State machine manages all flow with metrics
   - [ ] Feedback accumulates with FIFO trimming
   - [ ] Checkpoints include complete agent responses
   - [ ] AgentResult includes confidence and reasoning
   - [ ] Refinement works via follow-up messages
   - [ ] Code reduction: ~200-300 LOC
   - [ ] All tests passing
   - [ ] Token usage accurate
   - [ ] Observability metrics useful
2. Count LOC reduction:
   - Count lines in deleted RefinementAgent
   - Verify ~200-300 LOC reduction
3. Verify all tests pass
4. Verify all documentation updated
5. Create checklist verification document

**Completion Criteria:**
- [ ] All 11 success criteria verified
- [ ] LOC reduction documented
- [ ] Verification document created
- [ ] Any gaps documented

**Tests:**
- [ ] Run: `cloc` tool on old vs new codebase
- [ ] Final test run: `pytest packages/blinkb0t/tests/ -v`

**Rollback:** N/A (documentation)

---

### Task 7.6: Create Release Notes
**Effort:** Small (~2 hours)  
**Dependencies:** Task 7.5  
**Files:**
- Create: `packages/blinkb0t/RELEASE_NOTES.md`

**Objective:** Document release with all changes.

**Steps:**
1. Create RELEASE_NOTES.md
2. Document version number
3. List major changes:
   - Provider abstraction
   - Conversational agents
   - State machine with observability
   - Feedback management
   - Refinement simplification
   - Enhanced checkpointing
4. List breaking changes
5. List new features
6. List bug fixes (if any)
7. List deprecations
8. Add upgrade instructions
9. Add known issues (if any)

**Completion Criteria:**
- [ ] Release notes complete
- [ ] All major changes documented
- [ ] Breaking changes highlighted
- [ ] Upgrade instructions clear

**Tests:**
- [ ] Review release notes for accuracy
- [ ] Verify all changes documented

**Rollback:** N/A (documentation)

---

### Task 7.7: Final Review and Sign-off
**Effort:** Small (~1 hour)  
**Dependencies:** Task 7.6  
**Files:** N/A

**Objective:** Final review before considering implementation complete.

**Steps:**
1. Review all implemented features
2. Review all tests
3. Review all documentation
4. Run final test suite
5. Run final type check
6. Review with team (if applicable)
7. Get sign-off from stakeholders
8. Create final checklist
9. Mark implementation as COMPLETE

**Completion Criteria:**
- [ ] All features implemented
- [ ] All tests passing
- [ ] All documentation complete
- [ ] Team reviewed (if applicable)
- [ ] Sign-off received
- [ ] Implementation marked COMPLETE

**Tests:**
- [ ] Final test run: all pass
- [ ] Final review: no blockers

**Rollback:** N/A

---

**Phase 7 Checkpoint:**
- [ ] All tests passing
- [ ] Performance acceptable
- [ ] Code cleaned up
- [ ] Success metrics verified
- [ ] Release notes created
- [ ] Final review complete
- [ ] Implementation COMPLETE

---

## Summary Statistics

**Total Phases:** 7  
**Total Tasks:** 42  
**Total Estimated Effort:** ~135-150 hours (3-4 weeks for one developer)

**Task Breakdown:**
- Small tasks (1-2 hours): 17 tasks
- Medium tasks (2-4 hours): 18 tasks
- Large tasks (4-5 hours): 7 tasks

**Success Metrics Achievement:**
1. ✅ Provider abstraction (Phase 1)
2. ✅ Conversational patterns (Phase 2)
3. ✅ State machine with observability (Phase 3)
4. ✅ Feedback management (Phase 4)
5. ✅ Enhanced checkpointing (Phase 3-4)
6. ✅ Refinement simplification (Phase 5)
7. ✅ ~200 LOC reduction (Phase 5)
8. ✅ Confidence and reasoning (Phase 2)
9. ✅ Unique conversation IDs (Phase 1)
10. ✅ All tests passing (Phase 7)
11. ✅ Documentation complete (Phase 6-7)

**Risk Mitigation:**
- Each task has clear rollback steps
- Phases can be completed independently
- Tests at every level (unit, integration, e2e)
- Frequent checkpoints
- Documentation throughout

## Execution Guidelines

### For AI Agent Execution

When executing this plan:

1. **Work Sequentially**: Complete tasks in order within each phase
2. **Verify Completion**: Check all completion criteria before moving on
3. **Run Tests**: Run tests after each task
4. **Commit Often**: Commit after each task completion
5. **Update Tracking**: Mark tasks complete in this document
6. **Handle Failures**: Use rollback steps if task fails
7. **Ask for Help**: Flag blockers immediately
8. **Document Issues**: Keep notes on any unexpected issues

### Success Indicators

- [ ] Each task's completion criteria met
- [ ] Each task's tests pass
- [ ] Phase checkpoints verified
- [ ] No broken tests at any point
- [ ] Code compiles at all times
- [ ] Documentation stays current

### Failure Handling

If a task fails:
1. Review error messages
2. Check completion criteria
3. Use rollback steps
4. Document the issue
5. Request assistance if needed
6. Retry or revise approach

---

## Appendix: Quick Reference

### Key Files Created
- `packages/blinkb0t/core/api/llm/provider.py`
- `packages/blinkb0t/core/api/llm/utils.py`
- `packages/blinkb0t/core/api/llm/openai/provider.py`
- `packages/blinkb0t/core/agents/moving_heads/state_machine.py`
- `packages/blinkb0t/core/agents/moving_heads/feedback_manager.py`
- `packages/blinkb0t/core/agents/moving_heads/planner_agent.py`
- `packages/blinkb0t/core/agents/moving_heads/implementation_agent.py`
- `packages/blinkb0t/core/agents/moving_heads/judge_agent.py`

### Key Files Modified
- `packages/blinkb0t/core/agents/moving_heads/agent_patterns.py`
- `packages/blinkb0t/core/agents/moving_heads/orchestrator.py`
- `packages/blinkb0t/core/agents/moving_heads/checkpoint_manager.py`

### Key Files Deleted
- `packages/blinkb0t/core/agents/moving_heads/plan_generator.py` (replaced)
- `packages/blinkb0t/core/agents/moving_heads/implementation_expander.py` (replaced)
- `packages/blinkb0t/core/agents/moving_heads/judge_critic.py` (replaced)
- `packages/blinkb0t/core/agents/moving_heads/refinement_agent.py` (removed)

### Test Commands
```bash
# Run all tests
pytest packages/blinkb0t/tests/ -v

# Run specific module tests
pytest packages/blinkb0t/tests/core/api/llm/ -v
pytest packages/blinkb0t/tests/core/agents/moving_heads/ -v

# Run with coverage
pytest --cov=packages/blinkb0t/core/agents/moving_heads --cov=packages/blinkb0t/core/api/llm -v

# Type checking
mypy packages/blinkb0t/core/agents/moving_heads
mypy packages/blinkb0t/core/api/llm

# Code formatting
black packages/blinkb0t/core/agents/moving_heads/
isort packages/blinkb0t/core/agents/moving_heads/
```

### Verification Commands
```bash
# Check for old references
grep -r "PlanGenerator" packages/blinkb0t/core/
grep -r "RefinementAgent" packages/blinkb0t/core/

# Count LOC
cloc packages/blinkb0t/core/agents/moving_heads/

# Run examples
python packages/blinkb0t/examples/agent_refactoring/complete_workflow.py
```