---
type: change
status: active
area: engineering
created: 2026-11-11
updated: 2026-11-11
---

# P4-T2 Ollama cloud schema smoke — 2026-11-11

> Raw `*.log` files named here sit beside this README in the owner's checkout but are
> gitignored by the repository's no-logs rule. The tables in this README reproduce their
> results.

Run per [runbook 01](../../runbooks/01-ollama-cloud-smoke.md). Authority:
[P4-T2 spec](../../build/specs/phase-4-compounding/P4-T2-local-provider-option.md),
*Owner amendment — 2026-11-01*.

| Field | Value |
|---|---|
| Date (UTC) | 2026-11-11T19:48:44Z – 20:02:54Z |
| Ollama | `ollama version is 0.34.2` (daemon at `http://127.0.0.1:11434`) |
| Model | `glm-5.3:cloud` (`glm_dsa_moe`, FP8; capabilities completion/thinking/tools) |
| Git SHA | `88b855ff34ac8fa89d322c064bec7ce401495cef` |
| Requests | 3 in total (attempt 1 here, plus two corrected attempts below), each with `provider_max_attempts=1` and `allow_json_object_fallback=False` |
| Result | Attempt 1 **FAILED** with `json_decode` (`pytest.log`). Attempt 3 parsed but failed one semantic rule; see *Corrected attempts* |

## Scope

Ollama cloud, not a local model. The request went to the loopback daemon, which proxies
`:cloud` models to ollama.com. A pass would have proven the Ollama provider and
strict-schema path, not offline operation.

## Attempt 1 failure classification

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
grammar-constrained decoding (upstream issue ollama/ollama#12362).

## Corrected attempts (cloud only)

Twinklr never uses local models. Ollama means Ollama cloud. The corrections below stay
within that rule.

| # | Git SHA | Change | Result |
|---|---|---|---|
| 1 | `88b855f` | none: bare prompt, schema sent only as `response_format` | Prose: the model never saw a schema (`pytest.log`) |
| 2 | `d860f68` | Smoke prompt now carries the MacroPlan schema, exactly as `AsyncAgentRunner` injects `response_schema` for every real agent call | A correctly shaped MacroPlan, but wrapped in a ```` ```json ```` fence, so `json.loads` failed (log: `pytest-attempt2.log`) |
| 3 | `83068d6` | `OllamaProvider` unwraps a fence that spans the whole response. Prose still fails parsing. | JSON parsed and matched the schema shape, then failed one cross-field model rule: `MacroSection.theme.scope must be ThemeScope.SECTION` (log: `pytest-attempt3.log`) |

There were three requests in total, each with `provider_max_attempts=1` and no fallback.
I stopped spending at attempt 3: tuning the smoke prompt until it passes would be
rerunning to get a pass.

## What this shows

- **Transport and model access work.** Loopback daemon → `glm-5.3:cloud` is fine.
- **Schema enforcement on cloud comes from the prompt, not from decoding.** Twinklr's
  runner already puts the schema in the prompt, and with it the model produces
  schema-shaped JSON.
- **Two real cloud-path defects were found and fixed:**
  - The smoke left the schema out of the prompt (fixed in the test).
  - The provider rejected fenced JSON (fixed in `OllamaProvider`; this would have
    broken every real Ollama cloud call).
- **What is still open is a semantic rule, not a schema failure.** The real macro planner
  has `max_schema_repair_attempts=1`, which sends exactly this validation error back to
  the model. This single-call smoke has no repair step.

## Owner decision needed (cloud only)

1. **Accept attempt 3 as the Phase 4 Ollama cloud evidence.** It shows the provider path,
   prompt-carried schema and parsing all work. The semantic rule is left to the runner's
   repair loop.
2. **Authorize one more cloud request through the runner-level path**
   (`AsyncAgentRunner` + macro planner spec, with its one repair attempt). That would
   exercise the full real-call path, but the smoke needs reworking to supply the planner's
   inputs.
