"""Async agent runner - async-native execution engine for agents."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import Any

from pydantic import ValidationError

from twinklr.core.agents.logging import LLMCallLogger, NullLLMCallLogger
from twinklr.core.agents.prompts import PromptPackLoader
from twinklr.core.agents.providers.base import (
    LLMProvider,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.providers.conversation import generate_conversation_id
from twinklr.core.agents.providers.errors import (
    LLMProviderError,
    RecoverableLLMProviderError,
)
from twinklr.core.agents.result import AgentResult
from twinklr.core.agents.schema_utils import get_json_schema_example
from twinklr.core.agents.spec import AgentMode, AgentSpec
from twinklr.core.agents.state import AgentState
from twinklr.core.agents.taxonomy_utils import inject_taxonomy

logger = logging.getLogger(__name__)

MAX_ONESHOT_REPAIR_RESPONSE_CHARS = 6_000


def sum_token_usage(usages: list[TokenUsage]) -> TokenUsage:
    """Add up the per-call usage figures reported by the provider.

    Args:
        usages: One entry per provider call (including repair attempts)

    Returns:
        Combined usage
    """
    return TokenUsage(
        prompt_tokens=sum(u.prompt_tokens for u in usages),
        reasoning_tokens=sum(u.reasoning_tokens for u in usages),
        completion_tokens=sum(u.completion_tokens for u in usages),
        total_tokens=sum(u.total_tokens for u in usages),
    )


class RunError(Exception):
    """Raised when agent execution fails."""


class AsyncAgentRunner:
    """Async-native agent execution engine.

    This is the primary implementation. All operations are async.

    Responsibilities:
    - Load and render prompts
    - Call LLM provider (async)
    - Validate responses
    - Handle schema repair loop (async)
    - Log LLM calls (async)
    - Return standardized results

    Example:
        runner = AsyncAgentRunner(provider, prompts_path, llm_logger)
        result = await runner.run(spec, variables, state)
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_base_path: str | Path,
        llm_logger: LLMCallLogger | None = None,
    ):
        """Initialize async agent runner.

        Args:
            provider: LLM provider (must support async methods)
            prompt_base_path: Base directory for prompt packs
            llm_logger: Optional LLM call logger (uses NullLLMCallLogger if not provided)
        """
        self.provider = provider
        self.prompt_loader = PromptPackLoader(base_path=prompt_base_path)
        self.llm_logger: LLMCallLogger = llm_logger or NullLLMCallLogger()

        logger.debug(f"AsyncAgentRunner initialized with {provider.provider_type.value} provider")

    async def run(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        state: AgentState | None = None,
        *,
        input_image_urls: list[str] | None = None,
    ) -> AgentResult:
        """Execute agent with spec and variables (async).

        Args:
            spec: Agent specification
            variables: Variables for prompt rendering
            state: Optional state (required for conversational agents)
            input_image_urls: Optional data URLs attached to an ONESHOT OpenAI user turn

        Returns:
            AgentResult with execution outcome
        """
        start_time = time.time()

        # Per-call usage reported by the provider, one entry per request
        # (including repair attempts). The provider's cumulative counter cannot
        # be used here: stages in the same wave share one provider and run
        # concurrently, so a snapshot delta captures other stages' calls too.
        call_usages: list[TokenUsage] = []

        try:
            # Merge default variables
            merged_vars = {**spec.default_variables, **variables}

            # Auto-inject response schema to avoid drift between prompts and models
            if spec.response_model and hasattr(spec.response_model, "model_json_schema"):
                merged_vars["response_schema"] = get_json_schema_example(spec.response_model)

            # Auto-inject taxonomy enum values to avoid drift between prompts and enums
            merged_vars = inject_taxonomy(merged_vars)

            # Load and render prompts (sync, but fast)
            prompts = self.prompt_loader.load_and_render(spec.prompt_pack, merged_vars)

            # Build messages
            messages = self._build_messages(prompts, spec)
            delivered_examples_count = len(prompts.get("examples") or [])

            # Start logging (async)
            call_id = await self._safe_log_start(
                spec=spec,
                variables=merged_vars,
                prompts=prompts,
                state=state,
                delivered_examples_count=delivered_examples_count,
            )

            # Execute with schema repair loop (async)
            (
                response_data,
                repair_attempts,
                response_metadata,
            ) = await self._execute_with_repair_async(
                spec, messages, state, call_usages, input_image_urls
            )

            # Calculate duration and tokens
            duration = time.time() - start_time
            usage = sum_token_usage(call_usages)

            # Track state if provided
            if state:
                state.attempt_count += 1

            # Complete logging (async)
            await self._safe_log_complete(
                call_id=call_id,
                raw_response=response_data,
                validated_response=response_data,
                validation_errors=[],
                usage=usage,
                duration=duration,
                success=True,
                repair_attempts=repair_attempts,
            )

            # Build result
            metadata: dict[str, Any] = {
                "schema_repair_attempts": repair_attempts,
                "model": response_metadata.model or spec.model,
                **self._usage_metadata(call_usages),
            }
            if response_metadata.response_id is not None:
                metadata["response_id"] = response_metadata.response_id
            if response_metadata.finish_reason is not None:
                metadata["finish_reason"] = response_metadata.finish_reason
            if response_metadata.structured_output_mode is not None:
                metadata["structured_output_mode"] = response_metadata.structured_output_mode
            if response_metadata.structured_output_fallback_reason is not None:
                metadata["structured_output_fallback_reason"] = (
                    response_metadata.structured_output_fallback_reason
                )
            if response_metadata.response_schema_hash is not None:
                metadata["response_schema_hash"] = response_metadata.response_schema_hash
            if state and state.conversation_id:
                metadata["conversation_id"] = state.conversation_id

            return AgentResult(
                success=True,
                data=response_data,
                duration_seconds=duration,
                tokens_used=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                conversation_id=state.conversation_id if state else None,
                metadata=metadata,
            )

        except LLMProviderError as e:
            duration = time.time() - start_time
            usage = sum_token_usage(call_usages)

            logger.error(f"Provider error in {spec.name}: {e}")

            return AgentResult(
                success=False,
                data=None,
                error_message=f"Provider error: {e}",
                duration_seconds=duration,
                tokens_used=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                metadata=self._usage_metadata(call_usages),
            )

        except RunError as e:
            duration = time.time() - start_time
            usage = sum_token_usage(call_usages)

            logger.error(f"Run error in {spec.name}: {e}")

            repair_attempts = spec.max_schema_repair_attempts
            metadata = {
                "schema_repair_attempts": repair_attempts,
                **self._usage_metadata(call_usages),
            }

            return AgentResult(
                success=False,
                data=None,
                error_message=str(e),
                duration_seconds=duration,
                tokens_used=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                metadata=metadata,
            )

        except Exception as e:
            duration = time.time() - start_time
            usage = sum_token_usage(call_usages)

            logger.error(f"Unexpected error in {spec.name}: {e}")

            return AgentResult(
                success=False,
                data=None,
                error_message=f"Execution error: {e}",
                duration_seconds=duration,
                tokens_used=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                metadata=self._usage_metadata(call_usages),
            )

    @staticmethod
    def _usage_metadata(call_usages: list[TokenUsage]) -> dict[str, Any]:
        """Serialize each logical response usage for experiment-grade costing."""
        return {
            "logical_request_count": len(call_usages),
            "call_usages": [
                {
                    "prompt_tokens": usage.prompt_tokens,
                    "reasoning_tokens": usage.reasoning_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                }
                for usage in call_usages
            ],
        }

    def _build_messages(self, prompts: dict[str, Any], spec: AgentSpec) -> list[dict[str, str]]:
        """Build message list for LLM provider.

        Args:
            prompts: Rendered prompts (system, developer, user, examples)
            spec: Agent specification

        Returns:
            List of message dicts
        """
        messages = []

        if "developer" in prompts:
            messages.append({"role": "developer", "content": prompts["developer"]})

        if "system" in prompts:
            messages.append({"role": "system", "content": prompts["system"]})

        if "examples" in prompts:
            messages.extend(prompts["examples"])

        if "user" in prompts:
            messages.append({"role": "user", "content": prompts["user"]})

        return messages

    def _build_logging_context(
        self,
        variables: dict[str, Any],
        prompts: dict[str, Any],
        spec: AgentSpec,
        delivered_examples_count: int,
    ) -> dict[str, Any]:
        """Build a compact, useful context summary for LLM call logging.

        Many agents pass flat variables (not nested under ``context``), so logging only
        ``variables['context']`` produces misleading "No context provided" summaries.
        This method extracts stable identifiers and payload-size indicators without
        dumping large prompt inputs.
        """
        summary: dict[str, Any] = {
            "agent": spec.name,
            "mode": spec.mode.value,
        }

        for key in (
            "run_id",
            "section_id",
            "section_name",
            "plan_set_id",
            "iteration",
            "energy_target",
            "motion_density",
            "choreography_style",
        ):
            if key in variables and variables[key] is not None:
                summary[key] = variables[key]

        # Prompt payload size indicators (chars)
        summary["prompt_sizes"] = {
            "system_chars": len(prompts.get("system") or ""),
            "developer_chars": len(prompts.get("developer") or ""),
            "user_chars": len(prompts.get("user") or ""),
            "examples_count": len(prompts.get("examples") or []),
            "delivered_examples_count": delivered_examples_count,
        }

        # Common context counts used for optimization/debugging
        if isinstance(variables.get("display_graph"), dict):
            dg = variables["display_graph"]
            groups = dg.get("groups")
            if isinstance(groups, list):
                summary["display_groups"] = len(groups)
            gbr = dg.get("groups_by_role")
            if isinstance(gbr, dict):
                summary["display_roles"] = len(gbr)

        if isinstance(variables.get("template_catalog"), dict):
            entries = variables["template_catalog"].get("entries")
            if isinstance(entries, list):
                summary["templates"] = len(entries)
        if isinstance(variables.get("template_catalog_full"), dict):
            entries = variables["template_catalog_full"].get("entries")
            if isinstance(entries, list):
                summary["templates_full"] = len(entries)

        if isinstance(variables.get("motif_ids"), list):
            summary["motifs"] = len(variables["motif_ids"])
        if isinstance(variables.get("lead_targets"), list):
            summary["lead_targets"] = len(variables["lead_targets"])
        if isinstance(variables.get("support_targets"), list):
            summary["support_targets"] = len(variables["support_targets"])
        # Plan payload size for judge calls
        if "plan" in variables:
            try:
                import json

                summary["plan_json_chars"] = len(json.dumps(variables["plan"], default=str))
            except Exception:
                summary["plan_json_chars"] = -1
        if "group_plan_set" in variables:
            try:
                import json

                summary["group_plan_set_json_chars"] = len(
                    json.dumps(variables["group_plan_set"], default=str)
                )
            except Exception:
                summary["group_plan_set_json_chars"] = -1

        return summary

    async def _execute_with_repair_async(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
        call_usages: list[TokenUsage],
        input_image_urls: list[str] | None,
    ) -> tuple[Any, int, ResponseMetadata]:
        """Execute agent with schema repair loop (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM
            state: Optional state (for conversation tracking)
            call_usages: Sink the usage of each provider call is appended to,
                so the caller sees every request's tokens — including those of
                repair attempts and of an attempt that then raised.

        Returns:
            Tuple of (validated_data, repair_attempts, final response metadata)

        Raises:
            RunError: If schema validation exhausted attempts
            LLMProviderError: If provider fails
        """
        repair_attempts = 0

        for attempt in range(spec.max_schema_repair_attempts + 1):
            # Call provider (async, oneshot or conversational)
            try:
                if spec.mode == AgentMode.CONVERSATIONAL:
                    if input_image_urls:
                        raise RunError("Image inputs require an ONESHOT agent specification")
                    response = await self._call_conversational_async(spec, messages, state)
                else:
                    response = await self._call_oneshot_async(spec, messages, input_image_urls)
            except RecoverableLLMProviderError as error:
                call_usages.append(error.token_usage)
                repair_attempts += 1
                if attempt >= spec.max_schema_repair_attempts:
                    raise RunError(
                        f"Recoverable structured response failure exhausted retries "
                        f"({error.reason}): {error}"
                    ) from error
                logger.warning(
                    "Agent %s retrying recoverable structured response failure (%s)",
                    spec.name,
                    error.reason,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous structured response could not be consumed "
                            f"({error.reason}). Return one complete response matching "
                            "the schema in the system prompt."
                        ),
                    }
                )
                continue

            call_usages.append(response.metadata.token_usage)

            # Skip validation if response_model is dict
            if spec.response_model is dict:
                return response.content, 0, response.metadata

            # Try to validate response
            try:
                validated = spec.response_model(**response.content)
                if spec.response_adapter is not None:
                    validated = spec.response_adapter(validated)
                logger.debug(f"Agent {spec.name} succeeded (repair attempts: {repair_attempts})")
                return validated, repair_attempts, response.metadata

            except ValidationError as e:
                repair_attempts += 1

                # Format validation error
                error_details = self._format_validation_error(e)

                # Log the failed response for debugging (first attempt only)
                if attempt == 0:
                    try:
                        raw_json = json.dumps(response.content, indent=2)
                    except Exception:
                        raw_json = str(response.content)

                    logger.warning(
                        f"Agent {spec.name} FIRST schema validation failure:\n"
                        f"===== VALIDATION ERROR =====\n"
                        f"{error_details}\n"
                        f"===== RAW RESPONSE =====\n"
                        f"{raw_json}"
                    )
                else:
                    logger.warning(
                        f"Agent {spec.name} schema validation failed "
                        f"(attempt {attempt + 1}/{spec.max_schema_repair_attempts + 1})"
                    )

                if attempt >= spec.max_schema_repair_attempts:
                    logger.error(
                        f"Agent {spec.name} exhausted schema repair attempts "
                        f"({spec.max_schema_repair_attempts})"
                    )
                    raise RunError(
                        f"Schema validation failed after {repair_attempts} attempts: {e}"
                    ) from e

                # A conversational provider retains its assistant turn. ONESHOT has no
                # such store, so include one bounded excerpt or the repair would be a
                # blind resample based only on validation errors.
                failed_response_context = ""
                if spec.mode == AgentMode.ONESHOT:
                    try:
                        failed_response = json.dumps(
                            response.content,
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        )
                    except (TypeError, ValueError):
                        failed_response = str(response.content)
                    was_truncated = len(failed_response) > MAX_ONESHOT_REPAIR_RESPONSE_CHARS
                    failed_response = failed_response[:MAX_ONESHOT_REPAIR_RESPONSE_CHARS]
                    bound_note = (
                        f" (truncated to {MAX_ONESHOT_REPAIR_RESPONSE_CHARS} characters)"
                        if was_truncated
                        else ""
                    )
                    failed_response_context = (
                        f"Your previous response{bound_note} was:\n"
                        f"```json\n{failed_response}\n```\n\n"
                    )

                # The schema remains in the system prompt; do not echo it here.
                repair_message = (
                    f"{failed_response_context}"
                    f"Schema validation failed. Fix these errors:\n{error_details}\n\n"
                    f"The expected schema is in the system prompt. "
                    f"Return a corrected JSON response."
                )

                messages.append({"role": "user", "content": repair_message})

        raise RunError("Schema repair loop exited unexpectedly")

    async def _call_oneshot_async(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        input_image_urls: list[str] | None = None,
    ) -> Any:
        """Call provider in oneshot mode (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM

        Returns:
            LLM response
        """
        return await self.provider.generate_json_async(
            messages=messages,
            model=spec.model,
            temperature=spec.temperature,
            **self._provider_request_kwargs(spec, input_image_urls),
        )

    async def _call_conversational_async(
        self,
        spec: AgentSpec,
        messages: list[dict[str, str]],
        state: AgentState | None,
    ) -> Any:
        """Call provider in conversational mode (async).

        Args:
            spec: Agent specification
            messages: Messages for LLM
            state: Agent state (for conversation tracking)

        Returns:
            LLM response
        """
        if not state:
            raise RunError(f"Conversational agent {spec.name} requires state but none provided")

        # Create or reuse conversation
        is_new_conversation = not state.conversation_id
        if is_new_conversation:
            state.conversation_id = generate_conversation_id(spec.name, state.attempt_count)
            logger.debug(f"Created conversation: {state.conversation_id}")
        assert state.conversation_id is not None

        # Build system prompt (only for first message)
        system_prompt = None
        if is_new_conversation:
            system_parts = []
            if any(m["role"] == "developer" for m in messages):
                system_parts.append(
                    next(m["content"] for m in messages if m["role"] == "developer")
                )
            if any(m["role"] == "system" for m in messages):
                system_parts.append(next(m["content"] for m in messages if m["role"] == "system"))
            system_prompt = "\n\n".join(system_parts) if system_parts else None

        # Get user message (last message should be user)
        user_messages = [m for m in messages if m["role"] == "user"]
        if not user_messages:
            raise RunError(f"No user message found in prompts for {spec.name}")

        user_message = user_messages[-1]["content"]

        # The provider's conversational surface accepts one user message rather than a
        # message list. Preserve the authored roles by folding the concrete few-shot
        # transcript into the first system prompt. It then remains in provider-managed
        # conversation history for refinements without extra seeding calls or tokens.
        if is_new_conversation:
            final_user_index = max(
                index for index, message in enumerate(messages) if message["role"] == "user"
            )
            examples = [
                message
                for index, message in enumerate(messages)
                if index < final_user_index and message["role"] in {"user", "assistant"}
            ]
            if examples:
                transcript = "\n".join(json.dumps(message, sort_keys=True) for message in examples)
                example_block = (
                    "## Few-shot examples (role-labelled transcript)\n"
                    f"{transcript}\n"
                    "## End few-shot examples"
                )
                system_prompt = (
                    f"{system_prompt}\n\n{example_block}" if system_prompt else example_block
                )

        return await self.provider.generate_json_with_conversation_async(
            user_message=user_message,
            conversation_id=state.conversation_id,
            model=spec.model,
            system_prompt=system_prompt,
            temperature=spec.temperature,
            **self._provider_request_kwargs(spec),
        )

    def _provider_request_kwargs(
        self, spec: AgentSpec, input_image_urls: list[str] | None = None
    ) -> dict[str, Any]:
        """Build portable request options and gate provider-specific features."""
        kwargs: dict[str, Any] = {
            "max_tokens": spec.max_tokens,
            "timeout_seconds": spec.timeout_seconds,
        }
        if spec.response_model is not dict:
            kwargs["response_model"] = spec.response_model
        if self.provider.provider_type == ProviderType.OPENAI:
            kwargs["reasoning_effort"] = spec.reasoning_effort
            kwargs["provider_max_attempts"] = spec.provider_max_attempts
            kwargs["allow_json_object_fallback"] = spec.allow_json_object_fallback
            if input_image_urls:
                kwargs["input_image_urls"] = input_image_urls
        elif input_image_urls:
            raise RunError("Configured provider does not support vision image inputs")
        return kwargs

    def _format_validation_error(self, error: ValidationError) -> str:
        """Format validation error for repair message.

        Args:
            error: Pydantic validation error

        Returns:
            Formatted error string
        """
        error_lines = []
        for err in error.errors():
            loc = ".".join(str(loc_part) for loc_part in err["loc"])
            msg = err["msg"]
            error_lines.append(f"- {loc}: {msg}")

        return "\n".join(error_lines)

    async def _safe_log_start(
        self,
        spec: AgentSpec,
        variables: dict[str, Any],
        prompts: dict[str, Any],
        state: AgentState | None,
        delivered_examples_count: int,
    ) -> str:
        """Safely log call start (async).

        Never raises - logs errors and returns empty string on failure.
        """
        try:
            return await self.llm_logger.start_call_async(
                agent_name=spec.name,
                agent_mode=spec.mode.value,
                iteration=variables.get("iteration"),
                model=spec.model,
                temperature=spec.temperature,
                prompts=prompts,
                context=self._build_logging_context(
                    variables, prompts, spec, delivered_examples_count
                ),
                conversation_id=state.conversation_id if state else None,
                run_id=variables.get("run_id"),
                provider=self.provider.provider_type.value,
            )
        except Exception as e:
            logger.warning(f"Failed to log call start: {e}")
            return ""

    async def _safe_log_complete(
        self,
        call_id: str,
        raw_response: Any,
        validated_response: Any,
        validation_errors: list[str],
        usage: TokenUsage,
        duration: float,
        success: bool,
        repair_attempts: int,
    ) -> None:
        """Safely log call completion (async).

        Never raises - logs errors silently.

        Args:
            call_id: Call identifier from start_call_async
            raw_response: Raw LLM response
            validated_response: Validated response (after Pydantic parsing)
            validation_errors: List of validation error messages
            usage: Tokens this agent's own requests consumed, summed across
                repair attempts
            duration: Call duration in seconds
            success: Whether the call succeeded
            repair_attempts: Number of schema repair attempts
        """
        try:
            await self.llm_logger.complete_call_async(
                call_id=call_id,
                raw_response=raw_response,
                validated_response=validated_response,
                validation_errors=validation_errors,
                tokens_used=usage.total_tokens,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_seconds=duration,
                success=success,
                repair_attempts=repair_attempts,
            )
        except Exception as e:
            logger.warning(f"Failed to log call completion: {e}")
