# P2P-T11 — Structured outputs (D6)

Phase: 2P (Creative Quality, Measured) · Lane: P (platform, parallel) · Executor: opus · Verifier: opus · Depends on: P2P-T10

## Objective

Move the agent layer from `json_object` mode plus a client-side schema-repair loop to
the Responses API's strict structured outputs, so the server enforces the schema.
The repair loop shrinks to refusal, truncation and content-filter handling, and — the
defect that matters most operationally — JSON-parse failures stop being the one
failure mode that gets zero retries and kills the run.

## Evidence & background

Findings: **M2 (modernization — HIGH_VALUE, sequenced with M1)**, **P3-F25** (no
native structured outputs), **P3-M-G** (unparseable JSON gets zero retries while
schema violations get five), **P3-M-F** (retry amplification ≤9 requests/call),
**P3-M-D** (blind ONESHOT repair — fixed by P2P-T9), **P3-F12** (the 20 dead fields —
deleted by P2P-T1).
Sources: `changes/twinklr-reactivation-review/reviews/modernization.md` M2;
`.../reviews/phases/llm-agents-and-planning.md` §4.6, §7, P3-F25, P3-M-G;
`.../reviews/reactivation-proposal.md` D6.

### M2 quoted

> The Responses API's strict structured outputs (`text.format: {"type":
> "json_schema", "strict":true}`; SDK `client.responses.parse(text_format=
> PydanticModel)`) is the officially recommended replacement for the `json_object`
> mode Twinklr uses. It would replace the client-side schema-repair loop (≤5
> retries/agent) with server-side enforcement, shrinking the retry surface to
> refusal/truncation/content-filter cases.
>
> Real refactor, not a flag flip — strict-mode constraints force model changes: all
> fields required (Optional→`X | null`), `additionalProperties:false` everywhere,
> object root only, no `allOf`; ceilings (5000 properties, 10 nesting levels, 1000
> enum values) must be checked against the choreography schemas. `json_object` mode is
> not deprecated, so this is value-driven, not forced. UNVERIFIED (cheap Stage 4 live
> test): whether `gpt-5.6-*` accepts `json_object` at all — test before retargeting
> without M2.

**P2P-T1 already did the schema-side work**: its acceptance criterion 2 requires every
response model to satisfy every one of these constraints, pinned by
`test_plan_schema_v2_strict_mode_compatible`. If that test is failing when this task
starts, **stop and fix T1's output first** — this task is the migration, not the
redesign.

### The one-call probe, quoted

The open question, carried since Stage 4:

> **Does `gpt-5.6-*` accept `json_object` mode?** M2's open question; the call site is
> `openai.py:298`. Cheap Stage 4 live test; gates whether M1 can ship without M2.

P2P-T10's LOCAL-ONLY smoke test is instructed to answer it. If it has been answered,
use the recorded answer. If not, **this task's first action is the one-call probe** —
before writing migration code — because the answer determines whether the migration is
urgent (json_object rejected on 5.6 → M1 is broken without M2) or merely valuable.

### P3-M-G quoted — the retry-parity defect this task must fix

> `json.JSONDecodeError` is converted to `LLMProviderError` inside the provider
> (`openai.py:333-335`), which `run()` catches at `:154` and returns as an immediate
> failure — bypassing the repair loop entirely. A *schema* violation of the same
> response gets up to 5 repair attempts. The inversion is backwards: **truncated or
> prose-wrapped JSON is the most common `json_object`-mode failure**, and it is the
> one treated as unrecoverable. Because the pipeline is fail-fast, it aborts the whole
> run.

### The invariant strict mode cannot express, quoted

> **The genuinely awkward one**: `PlanSection` enforces "exactly one of `template_id`
> or `segments`" through a validator plus a heuristic check
> (`heuristic_validator.py:219-228`). Strict JSON Schema cannot express that
> constraint, and a top-level union is disallowed. Migration would need either a
> discriminated union under a `kind` field or acceptance that the either/or invariant
> stays a post-validation check — in which case some of M2's promised retry-surface
> reduction does not materialize for this model.

P2P-T1 made this decision and documented it in the model docstring. **Read that
decision; do not re-make it here.** If T1 chose the post-validation route, this task's
"repair loop shrinks" claim is correspondingly weaker for `ChoreographyPlan`, and the
acceptance criteria must reflect the honest smaller reduction rather than asserting a
reduction that did not happen.

### The retry-amplification context (P3-M-F)

> `AsyncOpenAI(...)` is constructed without `max_retries` (`openai.py:67`), so the SDK
> default of 2 retries (3 attempts) applies; `generate_json_async` then wraps its own
> `max_attempts = 3` loop (`:312-320`). The layers compose multiplicatively: **up to 9
> HTTP requests for one logical call**.

This task shrinks the client-side repair surface; it should also make the two retry
layers legible (set `max_retries` explicitly, or document the composition). Do not
leave the multiplication implicit while claiming the retry surface shrank.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- `providers/openai.py` sends `"text": {"format": {"type": "json_object"}}`.
- `async_runner._execute_with_repair_async` loops `max_schema_repair_attempts + 1`
  times, appending formatted Pydantic errors as a new user message each failure.
- Unparseable JSON gets **zero** retries and terminates the run; schema violations get
  up to five.
- Worst case ≈60 logical calls per song (P3-F9), each up to 3 HTTP requests via the
  SDK layer (P3-M-F).
- After P2P-T9, ONESHOT repair attempts at least see their own failing output.

## Target behavior

1. **A one-call `json_object`-on-5.6 probe first**, its result recorded in the
   handoff (and in `memories/` if it settles a standing question). This is one API
   call, and it changes the framing of everything after it.
2. **Strict `json_schema` / `responses.parse` migration.** Agent calls send
   `text.format: {"type": "json_schema", "strict": true}` with the schema derived from
   the Pydantic response model, or use the SDK's `responses.parse(text_format=Model)`.
   Prefer the SDK's typed path where it composes with the existing conversational
   surface; where it does not, send the schema explicitly. Schema derivation stays
   machine-generated from the Pydantic source — ST-1's auto-injection property ("zero
   drift by construction") must survive intact.
3. **Repair loop shrinks to refusal / truncation / content-filter.** Schema violations
   should become impossible server-side; the loop's remaining job is the cases the
   server can legitimately return. Reduce `max_schema_repair_attempts` accordingly and
   document the new ceiling against P3-F9's ≈60.
4. **JSON-parse failures get retry parity.** A `JSONDecodeError` (truncation,
   prose-wrapping) is retried like any other recoverable failure rather than aborting
   the run. Under strict mode this failure should become rare; it must not remain
   fatal when it happens.
5. **Retry layers made legible.** `AsyncOpenAI` gets an explicit `max_retries`, and
   the composition of SDK retries × manual attempts is documented at the call site
   with the resulting worst-case request count.
6. **A fallback path exists and is honest.** If a model or provider rejects strict
   `json_schema`, the client falls back to `json_object` + the repair loop and
   **records that it did**. This also keeps the door open for D12's local provider,
   whose `/v1/responses` "does **not** document JSON-schema structured outputs" —
   schema-constrained decoding there is a `/v1/chat/completions` `response_format`
   path. Do not build the local-provider path here; do build the seam that makes it
   possible without another refactor.

### Non-goals

- Redesigning response models (**P2P-T1**).
- The local provider (**D12 / Phase 4**) — only the seam.
- Judge feedback/threshold work (**P2P-T9**).
- OpenAI SDK 3.x (M4: defer).
- The Anthropic provider's structured-output story. Note in the handoff that
  `AnthropicProvider` is **latent-reachable by configuration** (P3-F23, CLI-gate claim
  rejected) so a config choosing it after this task gets the old path; either gate it
  loudly or document the divergence.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/agents/providers/openai.py` — the `json_object` format line
  (`:298`), `generate_json_async` retry loop (`:312-320`), `JSONDecodeError` →
  `LLMProviderError` conversion (`:333-335`), client construction (`:67`), the
  conversational path (`:435-457`).
- `packages/twinklr/core/agents/async_runner.py` — `run()`'s failure branches
  (`:154`, `:169`, `:188`), `_execute_with_repair_async` (`:335-398`).
- `packages/twinklr/core/agents/schema_utils.py` — schema derivation and
  `get_json_schema_example`'s unused `exclude_fields`.
- `packages/twinklr/core/agents/spec.py` — `max_schema_repair_attempts`.
- `packages/twinklr/core/agents/providers/base.py` — the provider protocol, if the
  strict-schema parameter needs to reach it.
- Response models — read-only; if one fails strict mode, the fix belongs in T1's
  shape, not in a local workaround here.

Sequencing constraints copied verbatim from the plan:

> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.
> - Nothing in this program authorizes pushes/PRs to remotes or paid API calls beyond
>   each spec's stated test budget.

Modernization sequencing, verbatim from `modernization.md`:

> 2. M2 structured-outputs migration (with M1; after the `json_object`-on-5.6 live
>    test).

## Acceptance criteria

1. The `json_object`-on-5.6 probe has been run (or its recorded answer cited), and the
   result is in the handoff.
2. Every agent call on the shipped path uses strict `json_schema` /
   `responses.parse`, with the schema machine-derived from the Pydantic model — no
   hand-authored schema appears anywhere.
3. A response that would previously have failed Pydantic validation is now prevented
   server-side, demonstrated end-to-end for at least one agent in the LOCAL-ONLY run.
4. `max_schema_repair_attempts` is reduced, and the new worst-case logical-call and
   HTTP-request ceilings are stated explicitly against P3-F9's ≈60 and P3-M-F's ≤9.
5. A `JSONDecodeError` is retried rather than aborting the run — asserted with a fake
   provider that returns truncated JSON once and valid output on retry.
6. `AsyncOpenAI` is constructed with an explicit `max_retries`, and the composition is
   documented at the call site.
7. The `json_object` fallback exists, is exercised by a test, and records that it was
   taken.
8. If P2P-T1 chose the post-validation route for `PlanSection`'s either/or invariant,
   the handoff states plainly which validation remains client-side rather than
   claiming a reduction that did not occur.
9. `make validate` check-only forms pass; the golden render suite is unaffected (this
   task changes how plans are obtained, not what they render).

## Tests

1. `test_agent_calls_use_strict_json_schema` — fake provider asserts the request
   carries `strict: true` and the derived schema.
2. `test_schema_is_machine_derived` — the sent schema equals
   `Model.model_json_schema()` (post-T1 shape); pins ST-1.
3. `test_json_decode_error_is_retried` — criterion 5's guard, the P3-M-G fix.
4. `test_repair_loop_handles_refusal_and_truncation` — the surviving cases.
5. `test_fallback_to_json_object_is_recorded` — a provider rejecting strict mode
   falls back and flags it.
6. `test_worst_case_request_count` — bounded fake counting HTTP-level attempts;
   documents the P3-M-F composition numerically.
7. **LOCAL-ONLY** `test_live_strict_mode_per_agent` — one real call per agent role
   under strict mode, asserting a valid parse and, for one agent, that a previously
   schema-violating prompt now cannot violate. Budget: **≤ 8 calls, ≤ $1.50**.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/agents -q
uv run pytest -k "structured or schema or repair or retry" -q
uv run pytest -k golden -q
```

LOCAL-ONLY (`OPENAI_API_KEY` set):

```bash
uv run pytest -m local_only -k "strict_mode or json_object_probe" -q   # ≤8 calls, ≤$1.50
```

Paid-API budget for this task: **≤ $2.00 total**, including the probe.

## Effort & risk

**M–L.** Main risk: a response model that passes T1's structural test but is rejected
by the live API for a constraint the test did not encode (strict mode has sharp edges
around `$ref` shapes, defaults, and enum handling that a local JSON-Schema walk can
miss). Mitigation: the LOCAL-ONLY per-role live test is an acceptance criterion, not a
nicety, and any rejection is fixed in T1's model shape rather than by a local schema
patch — otherwise the machine-derived property (ST-1) quietly dies. Second risk:
claiming a retry-surface reduction that the `PlanSection` invariant prevents —
mitigated by criterion 8 requiring the honest statement. Third risk: the fallback path
becoming the silent default if strict mode errors intermittently — mitigated by making
the fallback record itself (CC-3's silent-degradation lesson).

## Implementation handoff — 2026-08-14 (pending independent verification)

### Implemented contract

- `AsyncAgentRunner` passes the exact Pydantic response root through the provider
  framework. `OpenAIProvider` sends `text.format={type: json_schema, name, schema,
  strict: true}` where `schema` is machine-derived from `model_json_schema()` and then
  normalized by one general supported-subset transform: Pydantic discriminated-union
  `oneOf` becomes equivalent nested `anyOf`, and discriminator metadata is removed.
  No response model has a hand-patched schema.
- The normalized schema is rejected locally if it contains `oneOf`, `discriminator`,
  or an officially unsupported composition keyword, if any object is not closed and
  all-required, or if it exceeds 5,000 properties, 10 object/array levels, or 1,000
  enum values. `CorrectionResponse` is exactly depth 10. Its display-domain behavior
  is unchanged: override names and typed values use equal-length parallel strict arrays
  which the adapter zips back into the renderer's parameter mapping.
- The final response metadata records `structured_output_mode`, an optional fallback
  reason, and the SHA-256 response-schema identity. The same schema identity is part of
  `spec_prompt_hash`, so a schema-only contract edit invalidates agent-stage caches.
- The SDK retry layer is explicit and disabled (`max_retries=0`). The provider owns one
  three-attempt transient loop. Each registered role retains one logical response retry:
  the normal ceiling is therefore 2 logical calls × 3 HTTP attempts = **6 HTTP
  requests** per agent invocation, down from the previous worst case of 6 logical calls
  × 9 composed HTTP attempts = 54. A capability-only strict rejection can add one 400
  response before each `json_object` fallback, making the compatibility-path ceiling 8.
  Against P3-F9's approximate 60 base agent invocations, the explicit normal ceiling is
  120 logical calls / 360 HTTP attempts; the fallback-only ceiling is 480 HTTP attempts
  and is observable rather than silent.
- Recoverable JSON decoding, refusal, truncation, content filtering, and empty-response
  outcomes get the same one-retry treatment. Usage is extracted and recorded before
  any of those classifications, and the recoverable exception carries that attempt's
  exact usage into the runner's integrated per-stage total. Schema-invalid output is
  prevented by the server, except for Pydantic post-model invariants that JSON Schema
  cannot express.
- Strict-capability rejection falls back only for an explicit 400 capability phrase,
  logs a warning, and records `json_object_fallback`. Invalid-schema/request 400s,
  including messages that also mention `response_format` or `json_schema`, fail loudly
  without fallback.
- `AnthropicProvider` is latent-reachable by configuration but has no equivalent strict
  contract. Registered `AgentSpec` calls now reject it loudly; legacy/direct calls keep
  their prior behavior.

### Resolution of the P2P-T1 display-root deferral

P2P-T1 deliberately limited its strict-root assertion to five roots and deferred
`SectionCoordinationPlan` / `CorrectionResult` here. Requiring the runtime display
models directly would expose framework-populated timing/asset fields and an arbitrary
`param_overrides` object that strict mode cannot represent. This task therefore adds
strict `SectionCoordinationResponse` / `CorrectionResponse` DTO roots and explicit
`AgentSpec.response_adapter` functions. The DTOs:

- exclude `schema_version`, `start_ms`, `end_ms`, narrative `section_ids`, and
  `resolved_asset_ids`; adapters populate them after server validation;
- encode parameter overrides as equal-length `param_override_keys` and typed
  `param_overrides` arrays and adapt them back to the renderer's dictionary;
- make all LLM-owned keys required, including nullable/list-valued keys.

All nine unique registered response roots (including the asset enricher, though asset
revival remains Phase 3) pass a local strict-schema walker. This deliberately resolves
the earlier §4/non-goal tension without redesigning the renderer-facing domain models.

### Honest remaining client-side validation

P2P-T1 retained `PlanSection`'s `template_id` XOR `segments` invariant as a Pydantic
post-model validator. Strict JSON Schema cannot enforce it, so `ChoreographyPlan` can
still consume the single logical retry after a server-schema-valid response violates
that XOR. The migration does not claim that this repair surface disappeared.

### Owner-gated live evidence still pending

No paid API call was made during implementation. The standing
`json_object`-on-gpt-5.6 question is therefore **still unanswered**, and no memory entry
was created. The committed LOCAL-ONLY harness skips unless both the API key and explicit
opt-in are present. Run these separately so the call counts remain visible:

```bash
TWINKLR_RUN_LIVE_LLM_TESTS=1 uv run pytest \
  tests/local_only/test_openai_structured_outputs.py \
  -m local_only -k json_object_probe -q

TWINKLR_RUN_LIVE_LLM_TESTS=1 uv run pytest \
  tests/local_only/test_openai_structured_outputs.py \
  -m local_only -k live_strict_mode_per_agent -q
```

The first command makes exactly one HTTP request. The second makes exactly eight HTTP
requests (one per currently shipped distinct role/root; the Phase-3 asset role is
excluded), uses low reasoning and caps each output at 4,000 tokens for the task's
≤$1.50 suite budget. Provider transport attempts are set to one and strict fallback is
disabled in this bounded harness, so a rejection fails the role rather than silently
spending a ninth strict-suite request. The `moving_head_judge` arm explicitly asks the
model to omit required `score`, then asserts that strict server enforcement retained the
key and returns a Pydantic-valid result. Record the probe answer here and promote it to
`memories/` only after the owner runs it.
