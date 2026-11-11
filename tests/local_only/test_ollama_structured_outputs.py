"""Explicit-opt-in, one-request Ollama schema-validity smoke test.

This test never installs Ollama or pulls a model. By default it targets the Ollama
cloud model ``glm-5.3:cloud`` through the loopback Ollama daemon, so no local model
weights are involved (owner decision 2026-11-01). See the P4-T2 task specification
and ``changes/twinklr-reactivation-review/runbooks/01-ollama-cloud-smoke.md``.

Ollama Cloud does not enforce ``response_format`` schemas, so the prompt carries the
same generated schema text that ``AsyncAgentRunner`` injects for every real agent call.
"""

from __future__ import annotations

import os

import pytest

from twinklr.core.agents.providers.factory import create_llm_provider
from twinklr.core.agents.schema_utils import get_json_schema_example
from twinklr.core.config.models import AppConfig
from twinklr.core.sequencer.planning import MacroPlan

DEFAULT_OLLAMA_MODEL = "glm-5.3:cloud"


@pytest.mark.local_only
@pytest.mark.asyncio
async def test_ollama_returns_schema_valid_macro_plan() -> None:
    if os.getenv("TWINKLR_RUN_LOCAL_OLLAMA_TESTS") != "1":
        pytest.skip("set TWINKLR_RUN_LOCAL_OLLAMA_TESTS=1 to authorize one Ollama request")

    base_url = os.getenv("TWINKLR_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    model = os.getenv("TWINKLR_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
    timeout_seconds = float(os.getenv("TWINKLR_OLLAMA_TIMEOUT_SECONDS", "300"))
    max_tokens = int(os.getenv("TWINKLR_OLLAMA_MAX_TOKENS", "16000"))

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
                    "the simplest valid values permitted by the supplied schema.\n\n"
                    f"Schema:\n{get_json_schema_example(MacroPlan)}"
                ),
            }
        ],
        model=model,
        response_model=MacroPlan,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        provider_max_attempts=1,
        allow_json_object_fallback=False,
    )

    assert MacroPlan.model_validate(response.content)
