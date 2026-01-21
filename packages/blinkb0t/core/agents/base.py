"""
agent_patterns_v3.py

V3 philosophy: Agents are *configuration*, not classes.

- One AgentRunner executes any agent given an AgentSpec.
- The only thing that typically varies across agents is the prompt pack + output schema.
- Conversation vs single-turn is a mode flag, not a separate executor implementation.
- Prompt rendering is Jinja2 (StrictUndefined) by default, with a strict format fallback.

This module intentionally stays thin:
- No orchestration/state-machine logic (that's a different layer)
- No provider-specific logic (use an injected LLMProvider)
- No heavy budgeting logic (use an injected ContextShaper)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)

import jinja2
from pydantic import BaseModel, ValidationError, field_validator, model_validator

# -----------------------------
# Public types
# -----------------------------

T = TypeVar("T", bound=BaseModel)


class AgentMode(str, Enum):
    """How the agent is executed."""

    SINGLE_TURN = "single_turn"
    CONVERSATION = "conversation"


@dataclass(frozen=True)
class Usage:
    """Token usage for a single provider call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ResponseMetadata:
    """Provider response metadata.

    This is intentionally provider-agnostic; providers may populate only a subset.
    """

    response_id: str | None = None
    model: str | None = None
    finish_reason: str | None = None
    usage: Usage = Usage()
    conversation_id: str | None = None
    provider: str | None = None  # e.g. "openai", "anthropic"


@dataclass(frozen=True)
class LLMResponse:
    """Standardized provider response wrapper."""

    content: Any
    metadata: ResponseMetadata


@runtime_checkable
class LLMProvider(Protocol):
    """Provider abstraction for calling an LLM.

    Providers should:
      - implement retries for network/rate/server errors
      - parse JSON when asked (return content as dict/list/etc.)
      - return per-call usage in metadata (if available)
    """

    def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...

    def generate_json_with_conversation(
        self,
        *,
        user_message: str,
        conversation_id: str | None,
        model: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...


@dataclass(frozen=True)
class Budget:
    """Optional, lightweight budget hints.

    The shaper decides how to interpret these values.
    """

    max_input_tokens: int | None = None
    target_input_tokens: int | None = None


@dataclass(frozen=True)
class ShapingStats:
    token_estimate: int | None = None
    reduction_pct: float | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ShapedContext:
    data: Any
    stats: ShapingStats = ShapingStats()


@runtime_checkable
class ContextShaper(Protocol):
    """Shapes context to fit a budget and/or stage constraints."""

    def shape(
        self,
        *,
        agent: AgentSpec[Any],
        context: Any,
        budget: Budget | None,
    ) -> ShapedContext: ...


class IdentityContextShaper:
    """Default shaper: returns context unchanged."""

    def shape(self, *, agent: AgentSpec[Any], context: Any, budget: Budget | None) -> ShapedContext:
        return ShapedContext(data=context, stats=ShapingStats(notes="identity"))


@dataclass(frozen=True)
class PromptPackRef:
    """Reference to a prompt pack directory (e.g., prompts/planner/...)."""

    name: str


@dataclass(frozen=True)
class RenderedPrompts:
    """Rendered prompt components + hashes for reproducibility."""

    system: str
    developer: str | None
    user_template: str | None  # If present, used to render the user message
    examples: list[dict[str, str]]
    hashes: dict[str, str]  # keys: system/developer/user_template/examples/combined


@dataclass
class AgentState:
    """Mutable state passed between calls.

    Stores conversation IDs per agent name, so conversational agents can refine
    via follow-ups without re-sending full history.
    """

    conversations: dict[str, str] = dataclasses.field(default_factory=dict)

    def get_conversation_id(self, agent_name: str) -> str | None:
        return self.conversations.get(agent_name)

    def set_conversation_id(self, agent_name: str, conversation_id: str) -> None:
        self.conversations[agent_name] = conversation_id

    def clear_conversation(self, agent_name: str) -> None:
        self.conversations.pop(agent_name, None)


@dataclass
class AgentSpec(Generic[T]):
    """Agent configuration (data-only).

    Adding a new agent should not require new Python classes—just a new AgentSpec
    pointing at a prompt pack and an output schema.
    """

    name: str
    prompt_pack: PromptPackRef
    response_model: type[T]
    mode: AgentMode = AgentMode.SINGLE_TURN

    # Model + sampling config
    model: str = "gpt-5"
    temperature: float | None = None
    provider_kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)

    # Reliability knobs
    schema_repair_attempts: int = 1
    repair_max_chars: int = 6000  # truncation for including invalid output in repair prompt

    # Budget hints (optional)
    budget: Budget | None = None

    # Optional static variables available to prompt rendering (in addition to run-time vars)
    default_vars: dict[str, Any] = dataclasses.field(default_factory=dict)


class AgentResult(BaseModel, Generic[T]):
    """Standard result envelope for any agent call."""

    success: bool
    data: T | None = None
    error: str | None = None

    # Optional LLM self-reported fields (if present in content)
    confidence: float | None = None
    reasoning: str | None = None

    # Observability
    usage: Usage = Usage()
    duration_seconds: float = 0.0
    conversation_id: str | None = None

    # Stable metadata keys for downstream checkpointing/metrics
    metadata: dict[str, Any] = {}

    @model_validator(mode="after")
    def _validate_invariants(self) -> AgentResult[T]:
        if self.success:
            if self.error is not None:
                raise ValueError("AgentResult invariant violated: success=True requires error=None")
        else:
            if self.error is None:
                raise ValueError(
                    "AgentResult invariant violated: success=False requires error!=None"
                )
        return self

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


# -----------------------------
# Prompt packs + rendering
# -----------------------------


class PromptPackLoader:
    """Loads prompt packs from a base directory.

    Expected layout per pack:
      <base>/<pack>/
        system.j2            (required)
        developer.j2         (optional)
        user.j2              (optional)  - template to render the user message
        examples.jsonl       (optional)  - each line: {"role": "...", "content": "..."}
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self._cache: dict[tuple[str, str], str] = {}  # (pack, filename) -> text
        self._cache_examples: dict[str, list[dict[str, str]]] = {}

    def _read_text(self, pack: str, filename: str) -> str:
        key = (pack, filename)
        if key in self._cache:
            return self._cache[key]
        path = self.base_dir / pack / filename
        text = path.read_text(encoding="utf-8")
        self._cache[key] = text
        return text

    def _read_optional(self, pack: str, filename: str) -> str | None:
        path = self.base_dir / pack / filename
        if not path.exists():
            return None
        return self._read_text(pack, filename)

    def _read_examples(self, pack: str) -> list[dict[str, str]]:
        if pack in self._cache_examples:
            return self._cache_examples[pack]
        path = self.base_dir / pack / "examples.jsonl"
        if not path.exists():
            self._cache_examples[pack] = []
            return []
        examples: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                role = obj.get("role")
                content = obj.get("content")
                if not isinstance(role, str) or not isinstance(content, str):
                    raise ValueError(
                        f"Invalid examples.jsonl line (must contain role/content strings): {obj}"
                    )
                examples.append({"role": role, "content": content})
        self._cache_examples[pack] = examples
        return examples

    def load(self, ref: PromptPackRef) -> dict[str, Any]:
        pack = ref.name
        system = self._read_text(pack, "system.j2")
        developer = self._read_optional(pack, "developer.j2")
        user_tmpl = self._read_optional(pack, "user.j2")
        examples = self._read_examples(pack)
        return {
            "system": system,
            "developer": developer,
            "user_template": user_tmpl,
            "examples": examples,
        }


class PromptRenderer:
    """Renders prompt templates.

    Uses Jinja2 StrictUndefined when available; otherwise uses a strict $var renderer.
    """

    def __init__(self) -> None:
        self._jinja = jinja2

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _render_jinja(self, template_text: str, variables: Mapping[str, Any]) -> str:
        assert self._jinja is not None
        jinja2 = self._jinja
        env = jinja2.Environment(
            undefined=jinja2.StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True
        )
        tmpl = env.from_string(template_text)
        return tmpl.render(**dict(variables))

    def _render_strict_dollar(self, template_text: str, variables: Mapping[str, Any]) -> str:
        # A minimal strict renderer for "$var" placeholders.
        # - "$$" escapes to "$"
        # - Missing keys raise KeyError
        out: list[str] = []
        i = 0
        n = len(template_text)
        while i < n:
            ch = template_text[i]
            if ch != "$":
                out.append(ch)
                i += 1
                continue
            # "$$" -> "$"
            if i + 1 < n and template_text[i + 1] == "$":
                out.append("$")
                i += 2
                continue
            # "$name"
            j = i + 1
            while j < n and (template_text[j].isalnum() or template_text[j] == "_"):
                j += 1
            key = template_text[i + 1 : j]
            if not key:
                raise ValueError("Invalid '$' in template: expected $var or $$")
            if key not in variables:
                raise KeyError(f"Missing template variable: {key}")
            out.append(str(variables[key]))
            i = j
        return "".join(out)

    def render(self, template_text: str, variables: Mapping[str, Any]) -> str:
        if self._jinja is not None:
            return self._render_jinja(template_text, variables)
        return self._render_strict_dollar(template_text, variables)

    def render_pack(
        self, loaded_pack: dict[str, Any], variables: Mapping[str, Any]
    ) -> RenderedPrompts:
        system_src: str = loaded_pack["system"]
        developer_src: str | None = loaded_pack.get("developer")
        user_src: str | None = loaded_pack.get("user_template")
        examples: list[dict[str, str]] = loaded_pack.get("examples") or []

        system = self.render(system_src, variables)
        developer = self.render(developer_src, variables) if developer_src else None
        user_template = self.render(user_src, variables) if user_src else None

        # Hashes (rendered + combined)
        hashes: dict[str, str] = {
            "system": self._sha(system),
            "developer": self._sha(developer) if developer else "",
            "user_template": self._sha(user_template) if user_template else "",
            "examples": self._sha(json.dumps(examples, sort_keys=True)),
        }
        combined = "\n\n".join(
            [system, developer or "", user_template or "", json.dumps(examples, sort_keys=True)]
        )
        hashes["combined"] = self._sha(combined)

        return RenderedPrompts(
            system=system,
            developer=developer,
            user_template=user_template,
            examples=examples,
            hashes=hashes,
        )


# -----------------------------
# Agent runner (single engine)
# -----------------------------


def generate_conversation_id(agent_name: str, iteration: int) -> str:
    """Generate a unique conversation ID for tracking.
    Pattern: {agent_name}_iter{iteration}_{uuid}
    """
    return f"{agent_name}_iter{iteration}_{uuid.uuid4().hex}"


class AgentRunner:
    """Single execution engine for all agents."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        prompt_loader: PromptPackLoader,
        prompt_renderer: PromptRenderer | None = None,
        context_shaper: ContextShaper | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._loader = prompt_loader
        self._renderer = prompt_renderer or PromptRenderer()
        self._shaper = context_shaper or IdentityContextShaper()
        self._clock = clock

    def run(
        self,
        *,
        spec: AgentSpec[T],
        context: Any,
        state: AgentState | None = None,
        iteration: int | None = None,
        feedback: str | None = None,
        budget: Budget | None = None,
        extra_vars: dict[str, Any] | None = None,
    ) -> tuple[AgentResult[T], AgentState]:
        """Run an agent described by spec.

        Returns (AgentResult, updated_state). State is always returned (created if None).
        """
        state = state or AgentState()
        t0 = self._clock()

        # 1) Shape context (budget-aware)
        shaped = self._shaper.shape(agent=spec, context=context, budget=budget or spec.budget)

        # 2) Render prompt pack with strict vars
        variables: dict[str, Any] = {}
        variables.update(spec.default_vars or {})
        variables.update(extra_vars or {})
        # Standard variables available to all prompts
        variables.setdefault("agent_name", spec.name)
        variables.setdefault("iteration", iteration)
        variables.setdefault("feedback", feedback)
        variables.setdefault("context", shaped.data)

        loaded_pack = self._loader.load(spec.prompt_pack)
        rendered = self._renderer.render_pack(loaded_pack, variables)

        # 3) Build the "user message" (via user template if provided, else JSON dump context)
        user_message = self._build_user_message(rendered, shaped.data, feedback)

        # 4) Execute with schema repair loop
        conversation_id = (
            state.get_conversation_id(spec.name) if spec.mode == AgentMode.CONVERSATION else None
        )
        result = self._execute_with_repair(
            spec=spec,
            rendered=rendered,
            user_message=user_message,
            conversation_id=conversation_id,
            state=state,
            iteration=iteration,
            shaping=shaped,
        )

        # 5) Finalize timing
        duration = max(0.0, self._clock() - t0)
        result.duration_seconds = duration  # type: ignore[attr-defined]

        return result, state

    def _build_user_message(
        self, rendered: RenderedPrompts, context: Any, feedback: str | None
    ) -> str:
        if rendered.user_template:
            # If the pack includes a user template, it is already rendered and should contain context/feedback.
            return rendered.user_template
        payload = {"context": context}
        if feedback:
            payload["feedback"] = feedback
        # Compact but readable; avoids huge whitespace expansion
        return json.dumps(payload, ensure_ascii=False)

    def _messages_single_turn(
        self, rendered: RenderedPrompts, user_message: str
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": rendered.system}]
        if rendered.developer:
            messages.append({"role": "developer", "content": rendered.developer})
        if rendered.examples:
            messages.extend(rendered.examples)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _invoke_provider(
        self,
        *,
        spec: AgentSpec[T],
        rendered: RenderedPrompts,
        user_message: str,
        conversation_id: str | None,
        state: AgentState,
        iteration: int | None,
    ) -> LLMResponse:
        """Invoke the provider in the appropriate mode, updating state for conversations."""
        if spec.mode == AgentMode.CONVERSATION:
            if iteration is None:
                # Force iteration to be explicit for consistent conversation id patterns.
                iteration = 0
            if conversation_id is None:
                # Start new conversation
                requested_id = generate_conversation_id(spec.name, iteration)
                resp = self._provider.generate_json_with_conversation(
                    user_message=user_message,
                    conversation_id=None,  # provider creates new
                    model=spec.model,
                    system_prompt=rendered.system,
                    temperature=spec.temperature,
                    **spec.provider_kwargs,
                )
                # prefer provider-returned conversation_id; fallback to requested_id if missing
                conv = resp.metadata.conversation_id or requested_id
                state.set_conversation_id(spec.name, conv)
                # Ensure metadata has conversation id populated for downstream
                if resp.metadata.conversation_id is None:
                    resp = LLMResponse(
                        content=resp.content,
                        metadata=dataclasses.replace(resp.metadata, conversation_id=conv),
                    )
                return resp

            # Follow-up in existing conversation
            resp = self._provider.generate_json_with_conversation(
                user_message=user_message,
                conversation_id=conversation_id,
                model=spec.model,
                system_prompt=None,
                temperature=spec.temperature,
                **spec.provider_kwargs,
            )
            # keep state in sync in case provider returns a different id
            if resp.metadata.conversation_id and resp.metadata.conversation_id != conversation_id:
                state.set_conversation_id(spec.name, resp.metadata.conversation_id)
            return resp

        # Single-turn
        msgs = self._messages_single_turn(rendered, user_message)
        return self._provider.generate_json(
            messages=msgs,
            model=spec.model,
            temperature=spec.temperature,
            **spec.provider_kwargs,
        )

    def _execute_with_repair(
        self,
        *,
        spec: AgentSpec[T],
        rendered: RenderedPrompts,
        user_message: str,
        conversation_id: str | None,
        state: AgentState,
        iteration: int | None,
        shaping: ShapedContext,
    ) -> AgentResult[T]:
        attempts = max(0, int(spec.schema_repair_attempts))
        last_error: str | None = None
        last_resp: LLMResponse | None = None

        current_user_message = user_message
        current_conversation_id = conversation_id

        for attempt in range(attempts + 1):
            resp = self._invoke_provider(
                spec=spec,
                rendered=rendered,
                user_message=current_user_message,
                conversation_id=current_conversation_id,
                state=state,
                iteration=iteration,
            )
            last_resp = resp
            current_conversation_id = resp.metadata.conversation_id or current_conversation_id

            parsed, confidence, reasoning, err = self._parse_validate_extract(
                spec.response_model, resp.content
            )
            if err is None and parsed is not None:
                return self._success_result(
                    data=parsed,
                    confidence=confidence,
                    reasoning=reasoning,
                    resp=resp,
                    spec=spec,
                    rendered=rendered,
                    shaping=shaping,
                    attempt=attempt,
                )

            last_error = err or "Unknown validation error"
            if attempt >= attempts:
                break

            # Build next repair message
            current_user_message = self._build_repair_message(
                schema_name=spec.response_model.__name__,
                validation_error=last_error,
                invalid_content=resp.content,
                max_chars=spec.repair_max_chars,
            )
            # In single-turn mode, we keep the same system/developer/examples and only replace the user message.
            # In conversation mode, this becomes a follow-up user message.

        # Failure result
        return self._failure_result(
            error=last_error or "Unknown error",
            resp=last_resp,
            spec=spec,
            rendered=rendered,
            shaping=shaping,
            attempt=attempts,
        )

    def _parse_validate_extract(
        self,
        model: type[T],
        content: Any,
    ) -> tuple[T | None, float | None, str | None, str | None]:
        """Validate provider content into the response model and optionally extract confidence/reasoning."""
        try:
            parsed = model.model_validate(content)
        except ValidationError as ve:
            return None, None, None, self._format_validation_error(ve)
        except Exception as e:
            return None, None, None, f"Failed to parse/validate response: {e}"

        # Optional extraction if present in raw dict
        confidence = None
        reasoning = None
        if isinstance(content, dict):
            if isinstance(content.get("confidence"), (int, float)):
                confidence = float(content["confidence"])
            if isinstance(content.get("reasoning"), str):
                reasoning = content["reasoning"]
        return parsed, confidence, reasoning, None

    @staticmethod
    def _format_validation_error(err: ValidationError) -> str:
        # Compact, readable summary
        lines: list[str] = []
        for e in err.errors():
            loc = ".".join(str(x) for x in e.get("loc", []))
            msg = e.get("msg", "")
            typ = e.get("type", "")
            lines.append(f"- {loc}: {msg} ({typ})")
        return "Schema validation failed:\n" + "\n".join(lines)

    @staticmethod
    def _truncate(obj: Any, max_chars: int) -> str:
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        if len(s) <= max_chars:
            return s
        return s[: max_chars - 30] + "...<truncated>..."

    def _build_repair_message(
        self,
        *,
        schema_name: str,
        validation_error: str,
        invalid_content: Any,
        max_chars: int,
    ) -> str:
        bad = self._truncate(invalid_content, max_chars=max_chars)
        # This is intentionally terse and deterministic.
        return (
            f"The previous response did not match the required schema `{schema_name}`.\n\n"
            f"Validation errors:\n{validation_error}\n\n"
            f"Previous (invalid) response:\n{bad}\n\n"
            "Return ONLY a single valid JSON object that matches the schema exactly. No markdown, no commentary."
        )

    def _success_result(
        self,
        *,
        data: T,
        confidence: float | None,
        reasoning: str | None,
        resp: LLMResponse,
        spec: AgentSpec[T],
        rendered: RenderedPrompts,
        shaping: ShapedContext,
        attempt: int,
    ) -> AgentResult[T]:
        meta = self._build_metadata(
            spec=spec, resp=resp, rendered=rendered, shaping=shaping, attempt=attempt
        )
        return AgentResult[T](
            success=True,
            data=data,
            error=None,
            confidence=confidence,
            reasoning=reasoning,
            usage=resp.metadata.usage,
            conversation_id=resp.metadata.conversation_id,
            metadata=meta,
        )

    def _failure_result(
        self,
        *,
        error: str,
        resp: LLMResponse | None,
        spec: AgentSpec[T],
        rendered: RenderedPrompts,
        shaping: ShapedContext,
        attempt: int,
    ) -> AgentResult[T]:
        usage = resp.metadata.usage if resp else Usage()
        conversation_id = resp.metadata.conversation_id if resp else None
        meta = self._build_metadata(
            spec=spec, resp=resp, rendered=rendered, shaping=shaping, attempt=attempt
        )
        return AgentResult[T](
            success=False,
            data=None,
            error=error,
            usage=usage,
            conversation_id=conversation_id,
            metadata=meta,
        )

    def _build_metadata(
        self,
        *,
        spec: AgentSpec[Any],
        resp: LLMResponse | None,
        rendered: RenderedPrompts,
        shaping: ShapedContext,
        attempt: int,
    ) -> dict[str, Any]:
        md: dict[str, Any] = {
            "agent_name": spec.name,
            "mode": spec.mode.value,
            "model": spec.model,
            "temperature": spec.temperature,
            "schema_repair_attempt": attempt,
            "prompt_hashes": rendered.hashes,
            "shaping": dataclasses.asdict(shaping.stats),
        }
        if resp:
            md.update(
                {
                    "provider": resp.metadata.provider,
                    "response_id": resp.metadata.response_id,
                    "finish_reason": resp.metadata.finish_reason,
                    "conversation_id": resp.metadata.conversation_id,
                }
            )
        return md


# -----------------------------
# Convenience: Agent registry (optional)
# -----------------------------


class AgentRegistry:
    """A small registry so callers can refer to agents by name."""

    def __init__(self) -> None:
        self._specs: dict[str, AgentSpec[Any]] = {}

    def register(self, spec: AgentSpec[Any]) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Agent '{spec.name}' already registered")
        self._specs[spec.name] = spec

    def get(self, name: str) -> AgentSpec[Any]:
        if name not in self._specs:
            raise KeyError(f"Unknown agent: {name}")
        return self._specs[name]

    def names(self) -> list[str]:
        return sorted(self._specs.keys())
