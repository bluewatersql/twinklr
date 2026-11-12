"""Probe which registered response schemas Claude's structured outputs compile."""

import time

import anthropic

from tests.unit.agents.test_structured_outputs import _registered_specs
from twinklr.core.agents.providers.anthropic import claude_json_schema

client = anthropic.Anthropic(max_retries=0)
print("utc_start", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
for spec in _registered_specs():
    started = time.time()
    try:
        message = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the smallest valid object."}],
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": claude_json_schema(spec.response_model),
                },
            },
        )
        u = message.usage
        print(
            f"{spec.name:24} ACCEPTED stop={message.stop_reason} in={u.input_tokens} out={u.output_tokens} {time.time() - started:.1f}s"
        )
    except anthropic.APIStatusError as error:
        print(
            f"{spec.name:24} REJECTED {error.status_code} {error.body} {time.time() - started:.1f}s"
        )
print("utc_end", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
