"""Owner-gated live probes for OpenAI structured-output compatibility.

These tests make paid API calls only when ``TWINKLR_RUN_LIVE_LLM_TESTS=1`` and
``OPENAI_API_KEY`` are both set. The probe makes one HTTP request and the strict
suite makes exactly eight more: provider retries and strict fallback are disabled.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from twinklr.core.agents.audio.lyrics.spec import get_lyrics_spec
from twinklr.core.agents.audio.profile.spec import get_audio_profile_spec
from twinklr.core.agents.providers.openai import OpenAIProvider
from twinklr.core.agents.sequencer.group_planner.holistic import get_holistic_judge_spec
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_holistic_corrector_spec,
)
from twinklr.core.agents.sequencer.group_planner.specs import (
    get_planner_spec as get_group_planner_spec,
)
from twinklr.core.agents.sequencer.macro_planner.specs import (
    get_planner_spec as get_macro_planner_spec,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_judge_spec as get_moving_head_judge_spec,
)
from twinklr.core.agents.sequencer.moving_heads.specs import (
    get_planner_spec as get_moving_head_planner_spec,
)

pytestmark = pytest.mark.local_only


def _require_live_opt_in() -> None:
    if os.getenv("TWINKLR_RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("set TWINKLR_RUN_LIVE_LLM_TESTS=1 to authorize paid LLM calls")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set")


@pytest.mark.asyncio
async def test_json_object_probe_on_gpt_5_6_sol() -> None:
    """One-call answer to the standing json_object compatibility question."""
    _require_live_opt_in()
    provider = OpenAIProvider(timeout=60.0)
    response = await provider.generate_json_async(
        messages=[
            {
                "role": "user",
                "content": 'Return exactly this JSON object: {"ok": true}.',
            }
        ],
        model="gpt-5.6-sol",
        max_tokens=64,
        reasoning_effort="low",
        provider_max_attempts=1,
    )
    assert response.content == {"ok": True}
    assert response.metadata.structured_output_mode == "json_object"


def _live_roles() -> tuple[tuple[str, Any], ...]:
    """Eight distinct shipped roles/response roots; asset revival is Phase 3."""
    return (
        ("audio_profile", get_audio_profile_spec()),
        ("lyrics", get_lyrics_spec()),
        ("group_planner", get_group_planner_spec()),
        ("holistic_corrector", get_holistic_corrector_spec()),
        ("holistic_judge", get_holistic_judge_spec()),
        ("moving_head_planner", get_moving_head_planner_spec()),
        ("moving_head_judge", get_moving_head_judge_spec()),
        ("macro_planner", get_macro_planner_spec()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role_and_spec", _live_roles(), ids=lambda value: value[0])
async def test_live_strict_mode_per_agent(role_and_spec) -> None:
    """One HTTP request per distinct live role; eight paid requests total."""
    _require_live_opt_in()
    role_name, spec = role_and_spec
    model: type[Any] = spec.response_model
    provider = OpenAIProvider(timeout=spec.timeout_seconds)
    instruction = (
        "Return the smallest semantically plausible object accepted by the supplied schema. "
        "Use non-empty placeholder identifiers and concise prose."
    )
    if role_name == "moving_head_judge":
        instruction += " Deliberately omit the required score key from your answer."
    response = await provider.generate_json_async(
        messages=[{"role": "user", "content": instruction}],
        model=spec.model,
        temperature=spec.temperature,
        reasoning_effort="low",
        max_tokens=min(spec.max_tokens, 4_000),
        timeout_seconds=spec.timeout_seconds,
        response_model=model,
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )
    # The moving-head judge arm asks for an invalid omission. Strict server
    # enforcement must override that instruction and retain the required key.
    model.model_validate(response.content)
    if role_name == "moving_head_judge":
        assert "score" in response.content
    assert response.metadata.structured_output_mode == "json_schema"
