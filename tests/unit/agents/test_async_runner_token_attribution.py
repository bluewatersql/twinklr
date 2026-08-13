"""Per-stage token attribution must be exact under concurrency (P1-F27/P3-F24).

The runner used to snapshot the provider's *cumulative* counter before and after
its await and subtract. ``profile`` and ``lyrics`` declare the same input, so
they occupy one wave and run concurrently against the single shared provider —
each stage's delta therefore absorbed the other's tokens. These tests pin the
per-call figures the provider already reports on ``LLMResponse``.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

from pydantic import BaseModel
import pytest

from twinklr.core.agents.async_runner import AsyncAgentRunner
from twinklr.core.agents.providers.base import (
    LLMResponse,
    ProviderType,
    ResponseMetadata,
    TokenUsage,
)
from twinklr.core.agents.spec import AgentSpec

FIXTURES_PATH = Path(__file__).parent.parent.parent / "fixtures" / "prompts"


class SampleResponse(BaseModel):
    """Response model the fake provider satisfies."""

    result: str
    count: int


class FakeSharedProvider:
    """One provider shared by every concurrent runner, as a session provides.

    Tracks a cumulative counter exactly like the real providers do, and reports
    each call's own usage on the response. ``gate`` forces the two callers to
    overlap, so a snapshot-and-subtract implementation cannot be correct.
    """

    provider_type = ProviderType.OPENAI

    def __init__(self, gate: asyncio.Barrier | None = None) -> None:
        self._cumulative = TokenUsage()
        self._lock = asyncio.Lock()
        self._gate = gate
        self.calls: list[str] = []
        self.usage_by_agent: dict[str, list[TokenUsage]] = {}

    def _next_usage(self, agent: str) -> TokenUsage:
        """Distinct, easily-summed figures per agent."""
        magnitude = {"profile": 100, "lyrics": 7}[agent]
        return TokenUsage(
            prompt_tokens=magnitude,
            completion_tokens=magnitude * 2,
            total_tokens=magnitude * 3,
        )

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        agent = model  # tests pass the agent name as the model for routing
        self.calls.append(agent)

        if self._gate is not None:
            # Both callers are now inside the await; a cumulative-counter delta
            # taken around this point necessarily includes the other's tokens.
            await self._gate.wait()

        usage = self._next_usage(agent)
        async with self._lock:
            self._cumulative = TokenUsage(
                prompt_tokens=self._cumulative.prompt_tokens + usage.prompt_tokens,
                completion_tokens=self._cumulative.completion_tokens + usage.completion_tokens,
                total_tokens=self._cumulative.total_tokens + usage.total_tokens,
            )
        self.usage_by_agent.setdefault(agent, []).append(usage)

        return LLMResponse(
            content={"result": "ok", "count": 1},
            metadata=ResponseMetadata(token_usage=usage, model=model),
        )

    def get_token_usage(self) -> TokenUsage:
        return self._cumulative


class FakeRepairingProvider:
    """Returns invalid content until the configured attempt succeeds."""

    provider_type = ProviderType.OPENAI

    def __init__(self, failures: int, usage_per_call: TokenUsage) -> None:
        self._failures = failures
        self._usage = usage_per_call
        self._cumulative = TokenUsage()
        self.call_count = 0

    async def generate_json_async(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.call_count += 1
        self._cumulative = TokenUsage(
            prompt_tokens=self._cumulative.prompt_tokens + self._usage.prompt_tokens,
            completion_tokens=self._cumulative.completion_tokens + self._usage.completion_tokens,
            total_tokens=self._cumulative.total_tokens + self._usage.total_tokens,
        )

        content = (
            {"result": "ok", "count": 1}
            if self.call_count > self._failures
            else {"wrong_field": True}
        )
        return LLMResponse(
            content=content,
            metadata=ResponseMetadata(token_usage=self._usage, model=model),
        )

    def get_token_usage(self) -> TokenUsage:
        return self._cumulative


def _spec(agent: str, *, repair_attempts: int = 2) -> AgentSpec:
    return AgentSpec(
        name=agent,
        prompt_pack="test_pack",
        response_model=SampleResponse,
        model=agent,
        max_schema_repair_attempts=repair_attempts,
    )


def _variables() -> dict[str, Any]:
    return {"agent_name": "test", "iteration": 1, "context": {}, "feedback": None}


async def test_concurrent_stages_report_own_tokens() -> None:
    """Two stages in one wave must each report only their own calls."""
    gate = asyncio.Barrier(2)
    provider = FakeSharedProvider(gate=gate)

    profile_runner = AsyncAgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)
    lyrics_runner = AsyncAgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    profile_result, lyrics_result = await asyncio.gather(
        profile_runner.run(spec=_spec("profile"), variables=_variables()),
        lyrics_runner.run(spec=_spec("lyrics"), variables=_variables()),
    )

    assert profile_result.success and lyrics_result.success
    assert profile_result.tokens_used == 300
    assert lyrics_result.tokens_used == 21
    assert profile_result.prompt_tokens == 100
    assert lyrics_result.completion_tokens == 14

    # The stage figures must add up to the run's real cost, no double counting.
    assert (
        profile_result.tokens_used + lyrics_result.tokens_used
        == provider.get_token_usage().total_tokens
    )


async def test_repair_attempts_tokens_are_summed() -> None:
    """A call that repairs twice reports all three requests' tokens."""
    per_call = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    provider = FakeRepairingProvider(failures=2, usage_per_call=per_call)
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    result = await runner.run(spec=_spec("profile"), variables=_variables())

    assert result.success is True
    assert provider.call_count == 3
    assert result.tokens_used == 45
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 15


async def test_exhausted_repairs_still_report_tokens_spent() -> None:
    """Failure is not free: the tokens already spent must be reported."""
    per_call = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    provider = FakeRepairingProvider(failures=99, usage_per_call=per_call)
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    result = await runner.run(spec=_spec("profile", repair_attempts=1), variables=_variables())

    assert result.success is False
    assert provider.call_count == 2
    assert result.tokens_used == 30


async def test_completion_log_receives_per_call_usage() -> None:
    """The logged figures come from the response, not a counter diff."""
    logged: dict[str, Any] = {}

    class RecordingLogger:
        async def start_call_async(self, **kwargs: Any) -> str:
            return "call-1"

        async def complete_call_async(self, **kwargs: Any) -> None:
            logged.update(kwargs)

    provider = FakeSharedProvider()
    runner = AsyncAgentRunner(
        provider=provider,
        prompt_base_path=FIXTURES_PATH,
        llm_logger=RecordingLogger(),  # type: ignore[arg-type]
    )

    await runner.run(spec=_spec("lyrics"), variables=_variables())

    assert logged["tokens_used"] == 21
    assert logged["prompt_tokens"] == 7
    assert logged["completion_tokens"] == 14


def test_runner_has_no_delta_arithmetic() -> None:
    """Guard against the snapshot-and-subtract pattern returning."""
    runner_source = inspect.getsource(inspect.getmodule(AsyncAgentRunner))

    assert "get_token_usage()" not in runner_source


@pytest.mark.parametrize("stage", ["profile", "lyrics"])
async def test_single_stage_is_unaffected(stage: str) -> None:
    """The sequential case keeps working."""
    provider = FakeSharedProvider()
    runner = AsyncAgentRunner(provider=provider, prompt_base_path=FIXTURES_PATH)

    result = await runner.run(spec=_spec(stage), variables=_variables())

    expected = provider.usage_by_agent[stage][0]
    assert result.tokens_used == expected.total_tokens
