# LLM Provider Abstraction Specification

**Status:** Design Phase  
**Date:** 2026-01-20  
**Updated:** 2026-01-21  
**Related:** `design.md`

## Overview

This document specifies the generic LLM provider abstraction that will replace direct `OpenAIClient` dependencies throughout the agent system.

## Goals

1. Abstract provider-specific implementation details
2. Support multiple providers (OpenAI, Claude, etc.)
3. Abstract conversation management with unique conversation IDs
4. Provide consistent interface for token tracking
5. Enable provider-specific features via extension points
6. Handle provider-level retries (network errors, 529s) gracefully
7. Document provider-specific quirks and requirements

## Protocol Definition

### Core Types

```python
from typing import Protocol, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

class ProviderType(str, Enum):
    """Supported provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

@dataclass
class TokenUsage:
    """Standardized token usage."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class ResponseMetadata:
    """Standardized response metadata."""
    response_id: str | None = None
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    model: str | None = None
    finish_reason: str | None = None
    conversation_id: str | None = None  # Provider-specific conversation ID

@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: Any  # Parsed JSON or text
    metadata: ResponseMetadata
```

### Conversation ID Generation

```python
def generate_conversation_id(agent_name: str, iteration: int) -> str:
    """Generate unique conversation ID for tracking.
    
    Pattern: {agent_name}_iter{iteration}_{uuid}
    
    Examples:
        - planner_iter1_a3f4b2c1
        - implementation_iter2_7d8e9f0a
    
    Args:
        agent_name: Name of the agent
        iteration: Current iteration number
    
    Returns:
        Unique conversation identifier
    """
    return f"{agent_name}_iter{iteration}_{uuid.uuid4().hex[:8]}"
```

### Core Protocol

```python
class LLMProvider(Protocol):
    """Generic protocol for LLM providers.
    
    Implementations must handle:
    - Provider-level retries (network errors, rate limits, 529s)
    - Conversation state management
    - Token usage tracking
    - JSON response parsing
    """
    
    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        ...
    
    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate JSON response from messages.
        
        Provider handles retries for:
        - Network errors (ConnectionError, TimeoutError)
        - Rate limits (429)
        - Server errors (500, 502, 503, 529)
        
        Higher-level failures (bad responses, validation errors) should
        raise exceptions to be handled by caller.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters
        
        Returns:
            LLMResponse with parsed JSON content and metadata
        
        Raises:
            LLMProviderError: On unrecoverable errors after retries
            ValidationError: On response parsing/validation failures
        """
        ...
    
    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str | None,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate JSON response in conversation context.
        
        Provider manages conversation state and handles retries.
        
        Args:
            user_message: User's message
            conversation_id: Existing conversation ID (None for new conversation)
            model: Model identifier
            system_prompt: System prompt (only used for new conversations)
            temperature: Sampling temperature
            **kwargs: Provider-specific parameters
        
        Returns:
            LLMResponse with parsed JSON content and metadata
            (metadata.conversation_id will contain the conversation ID)
        
        Raises:
            LLMProviderError: On unrecoverable errors
            ValueError: If conversation_id not found
        """
        ...
    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> None:
        """Add message to existing conversation.
        
        Args:
            conversation_id: Conversation identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
        
        Raises:
            ValueError: If conversation not found
        """
        ...
    
    def get_conversation_history(
        self,
        conversation_id: str
    ) -> list[dict[str, str]]:
        """Get conversation history.
        
        Args:
            conversation_id: Conversation identifier
        
        Returns:
            List of message dicts
        
        Raises:
            ValueError: If conversation not found
        """
        ...
    
    def get_token_usage(self) -> TokenUsage:
        """Get cumulative token usage across all calls.
        
        Returns:
            TokenUsage with total tokens used
        """
        ...
    
    def reset_token_tracking(self) -> None:
        """Reset token usage tracking."""
        ...
```

## OpenAI Provider Implementation

### Class Definition

```python
from openai import OpenAIError, APIError, RateLimitError, APIConnectionError
import logging

logger = logging.getLogger(__name__)

class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass

@dataclass
class Conversation:
    """Conversation state."""
    id: str
    messages: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

class OpenAIProvider:
    """OpenAI provider implementation with retry logic."""
    
    def __init__(
        self,
        api_key: str | None = None,
        retry_config: RetryConfig | None = None,
        timeout: float = 120.0,
    ):
        """Initialize OpenAI provider.
        
        Provider handles retries for network errors and server errors.
        
        Args:
            api_key: OpenAI API key (uses env var if not provided)
            retry_config: Retry configuration for provider-level retries
            timeout: Request timeout
        """
        self._client = OpenAIClient(
            api_key=api_key,
            retry_config=retry_config,
            timeout=timeout
        )
        self._conversations: dict[str, Conversation] = {}
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI
    
    def generate_json(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate JSON using OpenAI client with retry handling."""
        try:
            # Call OpenAI client (handles retries internally)
            response_data, metadata = self._client.generate_json(
                messages=messages,
                model=model,
                temperature=temperature,
                return_metadata=True,
                **kwargs
            )
            
            # Convert to standardized format
            return LLMResponse(
                content=response_data,
                metadata=self._convert_metadata(metadata)
            )
            
        except (APIConnectionError, RateLimitError) as e:
            # Network/rate limit errors after retries exhausted
            logger.error(f"OpenAI provider error after retries: {e}")
            raise LLMProviderError(f"Provider error: {e}") from e
        
        except APIError as e:
            if e.status_code in (500, 502, 503, 529):
                # Server errors after retries exhausted
                logger.error(f"OpenAI server error after retries: {e}")
                raise LLMProviderError(f"Server error: {e}") from e
            else:
                # Other API errors (4xx) - don't retry, fail up stack
                raise
    
    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str | None,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate JSON with conversation support and retry handling."""
        try:
            # Get or create conversation
            if conversation_id and conversation_id in self._conversations:
                conversation = self._conversations[conversation_id]
                # Add user message
                conversation.messages.append({
                    "role": "user",
                    "content": user_message
                })
            else:
                # Create new conversation
                if not conversation_id:
                    raise ValueError("conversation_id required for new conversations")
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": user_message})
                
                conversation = Conversation(
                    id=conversation_id,
                    messages=messages
                )
                self._conversations[conversation_id] = conversation
            
            # Call OpenAI (handles retries)
            response_data, metadata = self._client.generate_json(
                messages=conversation.messages,
                model=model,
                temperature=temperature,
                return_metadata=True,
                **kwargs
            )
            
            # Add assistant response to conversation
            conversation.messages.append({
                "role": "assistant",
                "content": json.dumps(response_data)
            })
            
            # Convert metadata
            response_metadata = self._convert_metadata(metadata)
            response_metadata.conversation_id = conversation_id
            
            return LLMResponse(
                content=response_data,
                metadata=response_metadata
            )
            
        except (APIConnectionError, RateLimitError, APIError) as e:
            # Handle same as generate_json
            if isinstance(e, APIError) and e.status_code in (500, 502, 503, 529):
                raise LLMProviderError(f"Server error: {e}") from e
            elif isinstance(e, (APIConnectionError, RateLimitError)):
                raise LLMProviderError(f"Provider error: {e}") from e
            else:
                raise
    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> None:
        """Add message to conversation."""
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        self._conversations[conversation_id].messages.append({
            "role": role,
            "content": content
        })
    
    def get_conversation_history(
        self,
        conversation_id: str
    ) -> list[dict[str, str]]:
        """Get conversation history."""
        if conversation_id not in self._conversations:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        return self._conversations[conversation_id].messages.copy()
    
    def get_token_usage(self) -> TokenUsage:
        """Get cumulative token usage."""
        usage = self._client.get_total_token_usage()
        return TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens
        )
    
    def reset_token_tracking(self) -> None:
        """Reset token tracking."""
        self._client.reset_conversation()
    
    def _convert_metadata(self, metadata: ResponseMetadata) -> ResponseMetadata:
        """Convert OpenAI metadata to standardized format."""
        return metadata
```

## Provider-Specific Quirks

### OpenAI Quirks

#### Message Alternation
OpenAI requires messages to alternate between user and assistant (with optional system at start):

```python
# ✓ Valid
messages = [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there"},
    {"role": "user", "content": "How are you?"}
]

# ✗ Invalid - consecutive user messages
messages = [
    {"role": "user", "content": "Hello"},
    {"role": "user", "content": "Are you there?"}  # ERROR
]
```

**Handling:** Provider should validate or merge consecutive same-role messages.

#### System Message Placement
System messages should be first in the conversation:

```python
# ✓ Preferred
messages = [
    {"role": "system", "content": "..."},  # First
    {"role": "user", "content": "..."}
]

# ⚠ Works but not recommended
messages = [
    {"role": "user", "content": "..."},
    {"role": "system", "content": "..."}  # Later
]
```

#### JSON Mode
OpenAI's JSON mode requires explicit format specification:

```python
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    response_format={"type": "json_object"}  # Required for JSON mode
)
```

**Note:** Provider handles this automatically in `generate_json()`.

#### Token Limits by Model
- GPT-4: 8,192 tokens (legacy), 128k tokens (turbo)
- GPT-3.5: 4,096 tokens (legacy), 16k tokens (turbo)

**Handling:** Provider should track token usage and warn when approaching limits.

### Claude (Anthropic) Quirks

#### Message Format
Claude uses a different structure:

```python
# Anthropic format
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello"}
    ],
    system="You are helpful."  # Separate parameter
)
```

**Key Differences:**
- System prompt is separate parameter, not in messages
- Requires explicit `max_tokens` parameter
- Different model naming convention

#### Tool Use
Claude has native tool/function calling:

```python
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    tools=[
        {
            "name": "get_weather",
            "description": "Get weather for location",
            "input_schema": {...}
        }
    ],
    messages=[{"role": "user", "content": "What's the weather?"}]
)
```

#### Thinking Tokens
Claude may include internal reasoning (thinking) tokens:

```python
response.content = [
    {"type": "thinking", "thinking": "Let me analyze..."},
    {"type": "text", "text": "The answer is..."}
]
```

**Handling:** Provider should filter or expose thinking separately.

## Future Provider: Claude Implementation Sketch

```python
class ClaudeProvider:
    """Claude (Anthropic) provider implementation."""
    
    def __init__(self, api_key: str | None = None):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._conversations: dict[str, Conversation] = {}
    
    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC
    
    def generate_json_with_conversation(
        self,
        user_message: str,
        conversation_id: str | None,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Generate JSON using Claude's API."""
        # Get or create conversation
        if conversation_id and conversation_id in self._conversations:
            conversation = self._conversations[conversation_id]
            conversation.messages.append({
                "role": "user",
                "content": user_message
            })
        else:
            if not conversation_id:
                raise ValueError("conversation_id required")
            
            conversation = Conversation(
                id=conversation_id,
                messages=[{"role": "user", "content": user_message}]
            )
            self._conversations[conversation_id] = conversation
        
        # Call Claude API
        response = self._client.messages.create(
            model=model,
            max_tokens=4096,  # Claude requires this
            system=system_prompt,  # Separate from messages
            messages=conversation.messages,
            temperature=temperature,
            **kwargs
        )
        
        # Parse response (handle thinking tokens)
        content_blocks = [
            block for block in response.content
            if block.type == "text"  # Filter out thinking
        ]
        response_text = content_blocks[0].text if content_blocks else ""
        
        # Parse JSON
        response_data = json.loads(response_text)
        
        # Add to conversation
        conversation.messages.append({
            "role": "assistant",
            "content": response_text
        })
        
        # Build metadata
        metadata = ResponseMetadata(
            response_id=response.id,
            token_usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens
            ),
            model=response.model,
            finish_reason=response.stop_reason,
            conversation_id=conversation_id
        )
        
        return LLMResponse(
            content=response_data,
            metadata=metadata
        )
```

## Usage Examples

### Basic Usage

```python
# Initialize provider
provider = OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))

# Single-turn call
response = provider.generate_json(
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Generate a plan."}
    ],
    model="gpt-4",
    temperature=0.7
)

plan = response.content  # Parsed JSON
tokens = response.metadata.token_usage.total_tokens
```

### Conversational Usage

```python
from blinkb0t.core.agents.moving_heads.utils import generate_conversation_id

# Start conversation with unique ID
conversation_id = generate_conversation_id("planner", iteration=1)
# Result: "planner_iter1_a3f4b2c1"

response1 = provider.generate_json_with_conversation(
    user_message="Generate a plan for a 4-minute song.",
    conversation_id=conversation_id,
    model="gpt-4",
    system_prompt="You are a lighting choreography planner."
)

plan = response1.content

# Add follow-up (same conversation)
response2 = provider.generate_json_with_conversation(
    user_message="The plan scored 65/100. Improve the energy matching.",
    conversation_id=conversation_id,  # Same ID
    model="gpt-4"
)

refined_plan = response2.content
```

### Agent Integration

```python
class PlannerAgent(ConversationalStageExecutor):
    def __init__(self, job_config: JobConfig, llm_provider: LLMProvider):
        super().__init__(job_config, llm_provider, "planner")
    
    def generate_plan(
        self,
        context: dict[str, Any],
        iteration: int
    ) -> AgentResult[AgentPlan]:
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(context)
        
        # Generate unique conversation ID
        conversation_id = generate_conversation_id(self.agent_name, iteration)
        
        response = self.llm_provider.generate_json_with_conversation(
            user_message=user_prompt,
            conversation_id=conversation_id,
            model=self.agent_config.model,
            system_prompt=system_prompt,
        )
        
        plan = AgentPlan.model_validate(response.content)
        
        # Store for follow-ups
        self.conversation_id = conversation_id
        
        return AgentResult(
            success=True,
            data=plan,
            tokens_used=response.metadata.token_usage.total_tokens,
            metadata={"conversation_id": conversation_id}
        )
```

## Error Handling Strategy

### Provider-Level Errors (Retry at Provider)
- Network errors (ConnectionError, TimeoutError)
- Rate limits (429)
- Server errors (500, 502, 503, 529)

**Handling:** Provider retries with exponential backoff, then raises `LLMProviderError`

### Application-Level Errors (Fail Gracefully Up Stack)
- Invalid JSON response
- Schema validation errors
- Business logic failures (low confidence, bad plan)

**Handling:** Raise specific exceptions, let orchestrator handle retry logic

```python
# In provider
try:
    response = api_call()
except RateLimitError:
    # Retry with backoff
    retry_with_backoff()

# In agent
try:
    result = provider.generate_json(...)
except LLMProviderError as e:
    # Provider exhausted retries, fail gracefully
    logger.error(f"Provider error: {e}")
    return AgentResult(success=False, error=str(e))
except ValidationError as e:
    # Bad response format, don't retry
    logger.error(f"Validation error: {e}")
    return AgentResult(success=False, error=str(e))
```

## Testing Strategy

### Provider Mock

```python
class MockLLMProvider:
    """Mock provider for testing."""
    
    def __init__(self):
        self._conversations: dict[str, list[dict[str, str]]] = {}
        self._token_usage = TokenUsage()
        self._responses: dict[str, Any] = {}
    
    def set_response(self, key: str, response: Any) -> None:
        """Set mock response for testing."""
        self._responses[key] = response
    
    def generate_json(self, messages, model, **kwargs) -> LLMResponse:
        """Return mock response."""
        return LLMResponse(
            content=self._responses.get("default", {"mock": "response"}),
            metadata=ResponseMetadata(
                token_usage=TokenUsage(total_tokens=100)
            )
        )
```

### Unit Tests

```python
def test_planner_agent_with_mock_provider():
    provider = MockLLMProvider()
    provider.set_response("plan", {
        "segments": [...],
        "confidence": 0.85,
        "reasoning": "Generated based on..."
    })
    
    agent = PlannerAgent(job_config, provider)
    result = agent.generate_plan(context, iteration=1)
    
    assert result.success
    assert result.data is not None
    assert result.confidence == 0.85
    assert "Generated based on" in result.reasoning
```

## Benefits

1. **Provider Agnostic**: Agents don't know about OpenAI-specific details
2. **Easy Testing**: Mock providers for unit tests
3. **Future Proof**: Easy to add Claude, Anthropic, etc.
4. **Consistent Interface**: Same API across all providers
5. **Conversation Abstraction**: Conversation management abstracted from agents
6. **Graceful Error Handling**: Provider retries vs. application failures clearly separated
7. **Unique Conversation Tracking**: Pattern-based IDs prevent conversation reuse
8. **Quirk Documentation**: Provider-specific behaviors documented for implementers