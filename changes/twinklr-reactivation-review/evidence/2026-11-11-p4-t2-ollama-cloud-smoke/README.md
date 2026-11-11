---
type: change
status: active
area: engineering
created: 2026-11-11
updated: 2026-11-11
---

# P4-T2 Ollama cloud schema smoke — 2026-11-11

Run per [runbook 01](../../runbooks/01-ollama-cloud-smoke.md). Authority:
[P4-T2 spec](../../build/specs/phase-4-compounding/P4-T2-local-provider-option.md),
*Owner amendment — 2026-11-01*.

| Field | Value |
|---|---|
| Date (UTC) | 2026-11-11T19:48:44Z – 19:48:54Z |
| Ollama | `ollama version is 0.34.2` (daemon at `http://127.0.0.1:11434`) |
| Model | `glm-5.3:cloud` (`glm_dsa_moe`, FP8; capabilities completion/thinking/tools) |
| Git SHA | `88b855ff34ac8fa89d322c064bec7ce401495cef` |
| Requests | exactly 1 (`provider_max_attempts=1`, `allow_json_object_fallback=False`) |
| Result | **FAILED** — `RecoverableLLMProviderError: json_decode` ([pytest.log](pytest.log)) |

## Scope

Ollama cloud, not a local model. The request went to the loopback daemon, which proxies
`:cloud` models to ollama.com. A pass would have proven the Ollama provider and
strict-schema path, not offline operation.

## Failure classification

**Schema not enforced (provider capability gap). Not transport, timeout or truncation.**

The response came back in about 8 s with prose and no JSON:

> I don't see a schema in our conversation — no Twinklr MacroPlan schema has been supplied
> to me, so I can't know whi… ot invent field names and present them as "valid," since that
> could give you something that silently fails validation.

The provider sent the strict schema as a Chat Completions
`response_format: {type: json_schema, strict: true}`
(`OllamaProvider`, `supports_responses_structured_output=False`). The model answered as if
it had received only the user message. This matches Ollama's own documentation: **Ollama's
Cloud does not currently support structured outputs**
(<https://docs.ollama.com/capabilities/structured-outputs>). Pydantic AI also documents
that Ollama cloud accepts `response_format` `json_schema` without error but applies no
grammar-constrained decoding (upstream issue ollama/ollama#12362). Local Ollama
(v0.5.0+) enforces the schema by constrained decoding.

## Consequence for the 2026-11-01 amendment

Under the cloud-only amendment, the P4-T2 exit as written cannot pass. That exit is a
schema-valid `MacroPlan` through the strict path with no repair or fallback. Any rerun
against a `:cloud` model is unconstrained generation, so more attempts are not the fix.
No second attempt was made.

## Owner decision needed

1. **Revert to a local model for this smoke only.** This proves the strict path the
   provider was built for, using constrained decoding. It needs a local model pull.
2. **Keep cloud and re-scope the exit** to "schema-in-prompt plus post-validation". That
   needs a provider change, its own review, and a new single authorized attempt. It would
   not prove strict decoding.
3. **Accept this record as the Phase 4 Ollama finding** and close the exit as "cloud
   schema enforcement unsupported", with no further spend.
