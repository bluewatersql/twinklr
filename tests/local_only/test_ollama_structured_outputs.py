"""Explicit-opt-in, one-request Ollama schema-validity smoke test.

This test never installs Ollama or pulls a model. See the P4-T2 task specification
for the operator runbook.
"""

from __future__ import annotations

import os

import pytest

from twinklr.core.agents.providers.factory import create_llm_provider
from twinklr.core.config.models import AppConfig
from twinklr.core.sequencer.planning import MacroPlan


@pytest.mark.local_only
@pytest.mark.asyncio
async def test_ollama_returns_schema_valid_macro_plan() -> None:
    if os.getenv("TWINKLR_RUN_LOCAL_OLLAMA_TESTS") != "1":
        pytest.skip("set TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 to authorize one local Ollama request")

    base_url = os.getenv("TWINKLR_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.getenv("TWINKLR_OLLAMA_MODEL")
    if not model:
        pytest.skip("TWINKLR_OLLAMA_MODEL must name an already-pulled local model")

    provider = create_llm_provider(
        AppConfig(llm_provider="ollama", llm_base_url=base_url, llm_api_key=""),
        session_id="p4-t2-local-smoke",
    )
    response = await provider.generate_json_async(
        messages=[
            {
                "role": "user",
                "content": (
                    "Return one minimal valid Twinklr MacroPlan as JSON. Use one section and "
                    "the simplest valid values permitted by the supplied schema."
                ),
            }
        ],
        model=model,
        response_model=MacroPlan,
        max_tokens=4000,
        timeout_seconds=60,
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )

    assert MacroPlan.model_validate(response.content)
