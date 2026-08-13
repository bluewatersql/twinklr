# P4-T2 — Local provider option (D12)

Phase: 4-compounding · Lane: provider (touches `agents/providers/`, `config/models.py`,
provider factory/config loading) · Executor: sonnet · Verifier: opus · Depends on:
P2P-T11 (structured-outputs migration, per `build/plan/07-phase-4-compounding.md` task
table — D12's own text: "after M2's structured-outputs migration")

## Objective

Add an Ollama provider option, reached through the OpenAI SDK's documented `base_url`
override, with a structured-output path that works around Ollama's
`/v1/responses` gap by routing through `/v1/chat/completions` `response_format`. Ship
an offline smoke test proving at least one local model produces schema-valid output
against Twinklr's own choreography schemas — not a public benchmark ranking.

## Evidence & background

**D12** (reactivation-proposal.md:239–249): "Feasible with one caveat: the OpenAI SDK
officially supports `base_url` override (constructor or `OPENAI_BASE_URL`), and
Ollama (very active) exposes an OpenAI-compatible surface — but its `/v1/responses`
does **not** document JSON-schema structured outputs; schema-constrained decoding is
supported via `/v1/chat/completions` `response_format` (and native `/api/chat
format`). **Recommendation**: after M2's structured-outputs migration, add a provider
config with a chat-completions structured-output fallback path; targets for 32 GB
machines: `qwen3.5:27b`, `granite4.1:30b`, or `nemotron-3.5-lightning` (30B MoE) —
benchmark against OUR schemas before trusting any ranking (public rankings are
unverified). Priority: after the cloud path is proven; it's an option, not a
dependency."

**M4 program entry** (`07-phase-4-compounding.md` exit criteria): "local-provider
option available" is a phase-exit criterion, not optional polish.

**Existing provider architecture (context for the executor — re-verify against
current tree, not re-derived here):** `agents/providers/openai.py` constructs
`AsyncOpenAI(api_key=..., timeout=..., base_url=...)` (P1-F12 evidence,
`foundation-and-orchestration.md:1023-1038`, baseline line `agents/providers/openai.py:67`)
— `base_url` is ALREADY a constructor parameter in the live code, meaning the SDK-level
hook this task needs already exists; this task adds the provider **config** surface
and the **response_format fallback** logic, not the SDK plumbing itself.

**P3-F23 (verification.md:188-191, CLI provider-selection precedent):** "The CLI only
checks `OPENAI_API_KEY` is non-empty, never selects provider — an anthropic
config.json runs end-to-end." This confirms the provider-selection surface in the CLI
is currently a non-gate (any `base_url`/model config reaches the client unchecked) —
useful precedent for how loosely provider config is currently validated, but also a
known latent-bug area (Anthropic's `[-4:]` windowing produces assistant-first message
lists the API rejects on turn 3, per the same citation) that this task must NOT
inherit uncritically for the Ollama path — validate the new provider's message
windowing independently rather than assuming existing multi-provider code is safe.

**Structured outputs dependency (M2, modernization.md:48–61):** this task depends on
P2P-T11 having landed the Responses API strict structured-outputs migration
(`text.format: {"type":"json_schema","strict":true}` / SDK
`client.responses.parse(text_format=PydanticModel)`). Ollama's gap is specifically
that its `/v1/responses` endpoint doesn't document this — so the fallback path for
the Ollama provider must use `/v1/chat/completions` `response_format` instead of the
now-standard `/v1/responses` path the cloud provider uses post-M2. This is a
**per-provider branch**, not a reversion of M2 for all providers.

## Current behavior

- The only live LLM provider path is OpenAI via `AsyncOpenAI` (and, per P3-F23, an
  under-validated Anthropic path). No Ollama or generic-`base_url` local-model config
  surface exists.
- Post-M2 (P2P-T11), structured output requests go through the Responses API's
  `text.format` strict JSON-schema path uniformly.

## Target behavior

- A new provider config option (naming/shape to match the existing
  `AgentConfig`/`ProviderConfig`-style structure the executor finds in
  `config/models.py` — re-verify current shape before adding fields) lets the user
  point Twinklr at a local Ollama instance: `base_url` (e.g.
  `http://localhost:11434/v1`), model name (`qwen3.5:27b` / `granite4.1:30b` /
  `nemotron-3.5-lightning` or user-supplied), and no API key requirement (Ollama
  accepts a dummy/empty key).
- When the active provider is Ollama (or any provider flagged as lacking
  `/v1/responses` structured-output support), the agent call path routes structured
  requests through `/v1/chat/completions` with `response_format` set to the JSON
  schema, rather than through the Responses API `text.format` path used for OpenAI
  post-M2. This must be a clean branch on provider capability, not a global
  regression of the M2 path for OpenAI.
- Schema-repair/retry behavior (the existing ONESHOT retry loop, per CC-4/P3-M-D
  context) still applies on the chat-completions path — the fallback is a
  request-shape change, not a removal of error handling.
- An offline smoke test (LOCAL-ONLY, see below) exercises at least one of the three
  target models against Twinklr's actual choreography schema (e.g., the moving-heads
  plan schema) and confirms schema-valid output round-trips through Pydantic
  validation.

**Non-goals:** benchmarking or ranking the three candidate models against each other
for creative quality — D12 explicitly says "benchmark against OUR schemas before
trusting any ranking," meaning schema-validity, not choreography quality, is this
task's bar. Do not wire Ollama as a default provider — it remains opt-in
configuration. Do not implement `/api/chat` native format support (D12 mentions it as
an alternative but the recommendation is `/v1/chat/completions` `response_format`).

## Implementation approach

- Files to touch: `config/models.py` (provider config schema), wherever
  `agents/providers/openai.py`'s sibling providers live or would live (check for an
  existing `agents/providers/` package structure — Anthropic's provider, if present
  per P3-F23, is the pattern to follow for adding a new provider rather than
  reinventing provider dispatch), the structured-output call path introduced by
  P2P-T11 (add the capability branch there, not a parallel code path).
- Design decision already made (do not relitigate): the fallback triggers on a
  provider-capability flag (e.g., `supports_responses_structured_output: bool` or
  equivalent), not on string-matching the provider name — this keeps the branch
  correct if Ollama later adds `/v1/responses` support, and keeps other
  `base_url`-override providers (any future OpenAI-compatible local server) covered
  by the same flag rather than requiring per-provider special-casing.
- Sequencing constraint: this task cannot land before P2P-T11's structured-outputs
  migration exists in the tree — the chat-completions fallback needs the same JSON
  schema object the Responses API path uses; if P2P-T11 produced a schema-generation
  helper, reuse it rather than duplicating schema derivation logic for the fallback
  path.
- Re-verify all line/file citations above against the current tree before editing —
  they are baseline-`aa8d325` hints per the plan's verification-currency note.

## Acceptance criteria

- New provider config accepts `base_url` + model name for an Ollama-compatible
  endpoint; no API key is required when the provider is local.
- A structured-output request against the local-provider branch is issued via
  `/v1/chat/completions` `response_format`, verified by an integration test using a
  mocked/fake HTTP transport (not a live Ollama call) that asserts the request body
  shape.
- The OpenAI/cloud path's post-M2 behavior (Responses API `text.format`) is
  unchanged — a regression test confirms the cloud path still issues
  `client.responses.parse`/equivalent, not `/v1/chat/completions`.
- The LOCAL-ONLY offline smoke test (see Tests) is documented with exact setup
  instructions (which Ollama models to pull, how to point config at localhost) and
  is excluded from CI.

## Tests

- **Unit**: provider-capability branch selects `/v1/chat/completions` for a
  local/Ollama-flagged provider and the Responses API path for OpenAI — assert on
  the constructed request object/call arguments via a fake transport, not by
  contacting a real endpoint.
- **Unit**: provider config validation accepts a `base_url` + model config without
  requiring `OPENAI_API_KEY` to be set when the provider is local.
- **LOCAL-ONLY, marked and excluded from CI**: an offline smoke test that requires a
  running local Ollama instance with one of `qwen3.5:27b` / `granite4.1:30b` /
  `nemotron-3.5-lightning` pulled. It issues one structured-output request against a
  real (not mocked) choreography schema (pick the smallest wired schema available —
  re-verify which plan schema is cheapest to round-trip) and asserts the response
  parses into the corresponding Pydantic model without a repair retry. This is the
  "offline-December smoke test" the plan table calls for — it validates the
  offline-capability claim, not model quality.

## Verification commands

```bash
uv run pytest tests/unit/agents/providers/ -v   # path is a hint; confirm actual location
uv run pytest tests/unit/config/ -v -k provider
uv run mypy .
uv run ruff check .
```

LOCAL-ONLY (not run by the verifier in CI; run manually with Ollama installed and a
target model pulled, e.g. `ollama pull qwen3.5:27b`):
```bash
TWINKLR_PROVIDER=ollama TWINKLR_OLLAMA_BASE_URL=http://localhost:11434/v1 \
  uv run pytest tests/integration/ -v -k ollama_smoke  # exact marker/path per executor's test placement
```

## Effort & risk

**S/M.** Main risk: Ollama's structured-output support is a moving target (D12 flags
this as researched-but-not-verified against Twinklr's actual schemas) — a schema that
validates cleanly against OpenAI's strict-mode constraints (all fields required,
`additionalProperties:false`, no `allOf`, object root only) may still fail against a
local model's weaker instruction-following even with `response_format` set correctly.
Mitigation: the LOCAL-ONLY smoke test is the acceptance gate for this specific risk —
if it fails, the task's exit is "documented gap + fallback path exists," not "silently
ship a broken local mode." Do not claim local-provider support works end-to-end
without having actually run the smoke test at least once.
