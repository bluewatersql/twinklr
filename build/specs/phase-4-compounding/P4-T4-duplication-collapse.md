# P4-T4 — Duplication collapse

Phase: 4-compounding · Lane: duplication (touches `api/llm/openai/client.py`,
`agents/providers/openai.py`, `api/http/retry.py`, `pipeline/definition.py`,
`pipeline/executor.py`, `config/loader.py`, `core/utils/logging.py`,
`config/models.py`, `enhancement_factory.py`, `core/audio/advanced/tension.py`,
`core/audio/energy/multiscale.py`, `core/audio/energy/builds_drops.py`) · Executor:
sonnet · Verifier: opus · Depends on: P2P merged (per
`build/plan/07-phase-4-compounding.md` task table)

## Objective

Collapse five independently-verified duplication classes (CC-6) into single
implementations: one retry policy replacing four independently-configured retry
layers (with the OpenAI SDK's own default retries explicitly disabled), one
`configure_logging` (wired or `AppConfig.logging` deleted), conversation-store
eviction, httpx client lifecycle (`aclose()` on teardown), and the triplicated
`HAS_SCIPY` fallback pattern centralized into one helper.

## Evidence & background

**CC-6** (`findings.md:40`): "Duplication debt: 2 OpenAI clients/4 retry stacks, 2
`configure_logging`, 3 type-check configs (core linted WEAK — empirically
confirmed), 2 fresh emitters (stamp+grid conflict; MH unquantized), 2 XSQ writers
(dedup asymmetry; harvest+seed), triplicated fallbacks, v1/v2 straddles." This task
covers the retry/client, logging, conversation-store, httpx-lifecycle, and
scipy-fallback sub-items per the plan's task-table scope: "One OpenAI client + one
retry policy (SDK `max_retries` explicit — kills the ≤9-requests amplification); one
`configure_logging` (wire or delete `AppConfig.logging`); conversation-store
eviction; httpx client lifecycle (`aclose`); scipy/penalty triplication collapse."

**Note on scope**: the 3-type-check-configs and 2-fresh-emitters/2-XSQ-writers
sub-items of CC-6 are display/MH render-path concerns already addressed (or slated
for) Phase 3's convergence work and are NOT part of this task's file list — do not
expand scope to touch `pyrightconfig.json` or the fresh-emitter/XSQ-writer code
here; those are P4-F17/P5-F15-family concerns tracked separately.

### Retry collapse (P1-F12, `foundation-and-orchestration.md:1023-1038`)

> "Four independently-configured retry layers stack multiplicatively over a paid
> API... (1) `api/http/retry.py:8-75` — `RetryPolicy`, 3 attempts, jittered backoff,
> `Retry-After`, idempotent-only. (2) `api/llm/openai/client.py:90-102` +
> `_retry_with_backoff:229-267` — per-error-type counts. (3)
> `agents/providers/openai.py:310-318,377-397` — a third, type-based inline loop on
> the async path. (4) `pipeline/definition.py:36-52` + `executor.py:321-370` —
> stage-level. Beneath all of them, the OpenAI SDK's own client retries by default
> and is **never disabled**: `OpenAI(api_key=..., timeout=...)`
> (`api/llm/openai/client.py:140`) and `AsyncOpenAI(api_key=..., timeout=...,
> base_url=...)` (`agents/providers/openai.py:67`) pass no `max_retries`. Attempts
> therefore multiply rather than add, with no shared budget or deadline. Timeouts
> disagree too: `300.0` (`providers/openai.py:56`), `120.0`
> (`llm/openai/client.py:128`), and a config field `AgentConfig.timeout_seconds=60`
> (`config/models.py:30`) that nothing reads. *Fix:* set `max_retries=0` on the SDK
> clients, keep exactly one application-level policy, and give it a wall-clock
> deadline."

**Confirms the ≤9-requests amplification concretely** (P3-M-F,
`llm-agents-and-planning.md:1444-1450`): "`AsyncOpenAI(...)` is constructed without
`max_retries` (`openai.py:67`), so the SDK default of 2 retries (3 attempts)
applies; `generate_json_async` then wraps its own `max_attempts = 3` loop
(`:312-320`). The layers compose multiplicatively: **up to 9 HTTP requests for one
logical call**, with the manual backoff (`0.5 * 2**attempt`) unaware of the SDK's."

**Related but explicitly OUT OF SCOPE for this task's retry work** (do not fix here,
just don't make it worse): P3-M-G (`llm-agents-and-planning.md:1452-1459`) — the
repair-loop asymmetry where `json.JSONDecodeError` gets zero retries while schema
violations get five — is a control-flow bug, not a duplication issue; it belongs to
whichever task owns CC-3/P3 remedies, not this one. If collapsing the retry layers
touches the same code path, do not silently fix or silently worsen P3-M-G's
behavior — leave its current (buggy) behavior bit-for-bit unless a future task
targets it explicitly.

**Recommended target from the review's own duplication table**
(`foundation-and-orchestration.md:771`): "Custom `RetryPolicy` + three other retry
stacks → One policy object; `stamina` or `tenacity` if a library is wanted; **and
explicitly setting `max_retries=0` on the OpenAI SDK clients**. The redundancy, not
the quality, is the problem."

### Logging collapse (P1-F25, `foundation-and-orchestration.md:533-536,1224`)

> "Two `configure_logging`. `config/loader.py:144-157` (AppConfig-driven, honours
> level/format/third-party-logger suppression) [is dead — nothing calls it in
> production]. `core/utils/logging.py::configure_logging` [is] used by the CLI
> (`cli/main.py:44,297`) [with] a hardcoded `level='INFO'`, so `AppConfig.logging`
> (`models.py:428`) is dead on the shipped path. The former has no importer other
> than the `core.config` re-export (`config/__init__.py:21,44`)."

Two choices per the plan: wire `AppConfig.logging` into the CLI's call to
`core/utils/logging.py::configure_logging` (making the config-driven level/format
actually take effect), or delete `config/loader.py`'s dead `configure_logging` +
`AppConfig.logging` entirely and correct any docs claiming it's live (cross-reference
P7-M2/CC-1, which already lists `logging.level` as a dead-config member documented
as live in `docs/user-guide.md:121` — **whichever choice this task makes must be
reflected in that doc correction too, coordinate with P4-T6** if T6 hasn't landed
yet, or leave a note for it if it has).

### Conversation-store eviction (P3-M-H, `llm-agents-and-planning.md:1461-1465`)

> "`self._conversations: dict[str, Conversation]` (`openai.py:77`) is written at
> `:154` and `:435` and grep-verified never deleted, popped, or cleared —
> `reset_token_tracking` (`:208-212`) resets counters only. Every conversational
> agent's full history persists for the provider's lifetime. Bounded per process
> today; a leak in any long-lived or batch usage."

### httpx client lifecycle (P2-M10, `deterministic-audio-analysis.md:686`, and
`foundation-and-orchestration.md:433-436,484`)

> "`enhancement_factory.py` constructs two `AsyncApiClient`/`httpx.AsyncClient`
> connection pools per `AudioAnalyzer` and never calls `aclose()` on either,
> anywhere in `core/audio/`, `core/pipeline/`, or `cli/` — both are also
> constructed with placeholder `base_url`s, offering no real safety net from that
> field." Evidence: `enhancement_factory.py:61-62,115-116`;
> `api/http/client.py:454,468-476` ("`aclose`/context-manager support exists but is
> unused"); repo-wide grep for `aclose()` in the relevant packages returns zero
> hits.

### Scipy/penalty triplication (P2-F21 + P2-F23, `deterministic-audio-analysis.md:672,674`)

> P2-F21: "`HAS_SCIPY` fallback pattern is independently defined/duplicated in 3
> files within this phase's scope" — `advanced/tension.py:15-17,109`;
> `energy/multiscale.py:19-21,45`; `energy/builds_drops.py:14-19,78`. Disposition:
> "SIMPLIFY (centralize in `utils.py`, which currently has no `HAS_SCIPY`
> definition at all)."
>
> P2-F23: "Near-verbatim quality-penalty logic (coverage/overlap/OOB/gap penalties,
> clamping) is triplicated across `lyrics/pipeline.py`'s `_finalize_bundle` (from
> line 301, `overlap_penalty` at 352-353), `_try_whisperx_align` (from line 401,
> `overlap_penalty` at 456-457), and `_try_whisperx_transcribe` (from line 499,
> `overlap_penalty` at 543-544)." Disposition: "SIMPLIFY (extract shared helper)."

## Current behavior

Five independent request paths through the OpenAI SDK each apply their own retry
policy with no shared budget, and the SDK's own default retrying is never disabled —
one logical LLM call can issue up to 9 HTTP requests. Two `configure_logging`
functions exist; the config-driven one is dead, the CLI-used one ignores
`AppConfig.logging` entirely. The OpenAI provider's conversation dict grows
unbounded for the life of the process. `enhancement_factory.py` leaks two HTTP
connection pools per `AudioAnalyzer` construction. `HAS_SCIPY` is defined three
times; the lyrics-pipeline penalty-scoring logic is copy-pasted three times.

## Target behavior

- Exactly one retry policy governs LLM calls; `OpenAI(...)` and `AsyncOpenAI(...)`
  are both constructed with `max_retries=0` so the SDK never retries underneath the
  application policy. The pipeline/stage-level retry layer
  (`pipeline/definition.py`/`executor.py`) and the provider-level inline loop
  (`agents/providers/openai.py`) collapse into one policy object with a single
  configured attempt count and a wall-clock deadline; `api/http/retry.py`'s
  `RetryPolicy` is either that one surviving policy or is explicitly retired in
  favor of it — pick one, don't keep both under different names.
- One `configure_logging` remains, wired so `AppConfig.logging`'s level/format
  settings actually take effect on the shipped CLI path — OR `AppConfig.logging`
  and the dead `config/loader.py::configure_logging` are deleted together with a
  doc correction. State which choice was made in the task's handoff/PR description.
- `AsyncAgentRunner`'s (or wherever `self._conversations` lives) conversation store
  has an eviction mechanism — bounded size, TTL, or explicit `reset()`/cleanup
  called at a sensible lifecycle point (e.g., end of a run). Exact mechanism is an
  implementation choice; "never evicted, ever" must no longer be true.
- `enhancement_factory.py`'s two `AsyncApiClient`/`httpx.AsyncClient` instances are
  closed via `aclose()` on `AudioAnalyzer` teardown (context-manager `__aexit__`, an
  explicit `close()` method callers are expected to invoke, or equivalent) — pick
  whichever pattern matches how `AudioAnalyzer` is already used elsewhere in the
  codebase; do not invent a new lifecycle convention if one already exists nearby.
- `HAS_SCIPY` is defined once in `utils.py` (which "currently has no `HAS_SCIPY`
  definition at all," per P2-F21) and imported by the three sites that currently
  redefine it.
- The penalty-scoring logic (coverage/overlap/OOB/gap penalties, clamping) in
  `lyrics/pipeline.py` is extracted into one shared helper called from all three of
  `_finalize_bundle`, `_try_whisperx_align`, `_try_whisperx_transcribe`.

**Non-goals:** fixing P3-M-G's retry-asymmetry bug (unparseable JSON vs. schema
violations) — collapse the layers without changing that behavior. Fixing P3-M-I
(Anthropic windowing) — unrelated bug, different finding. Touching the 3
type-check-config or 2-fresh-emitter/2-XSQ-writer CC-6 sub-items — out of this
task's file list.

## Implementation approach

- Retry collapse: start from `api/http/retry.py`'s `RetryPolicy` as the survivor (it
  already has jittered backoff, `Retry-After` handling, idempotent-methods-only
  logic per `foundation-and-orchestration.md:405-406`) or replace all four with
  `stamina`/`tenacity` per the review's own suggestion — either is acceptable;
  document the choice. Set `max_retries=0` explicitly on both `OpenAI(...)`
  (`api/llm/openai/client.py:140`) and `AsyncOpenAI(...)`
  (`agents/providers/openai.py:67`) constructors. Reconcile the three disagreeing
  timeouts (`300.0` at `providers/openai.py:56`, `120.0` at
  `llm/openai/client.py:128`, unwired `AgentConfig.timeout_seconds=60` at
  `config/models.py:30`) into one — either wire `timeout_seconds` through and use it
  everywhere, or pick one hardcoded value and delete the other two plus the unwired
  config field (coordinate with CC-1/P4-T5 if `timeout_seconds` is in that task's
  dead-config sweep).
- Logging collapse: trace both `configure_logging` call graphs first
  (`config/loader.py:144-157`'s only importer per the finding is the
  `core.config` re-export at `config/__init__.py:21,44` — confirm this is still
  true before deciding wire-vs-delete).
- Conversation-store eviction and httpx lifecycle: both are additive fixes (add a
  cleanup path) rather than restructuring existing call sites — low risk, keep the
  diffs focused.
- Scipy/penalty triplication: mechanical extraction, no behavior change intended —
  the target behavior for penalty scoring must be bit-identical to today across all
  three call sites (this is a duplication fix, not a scoring-formula change).

## Acceptance criteria

- `git grep -n "max_retries"` shows `OpenAI(...)` and `AsyncOpenAI(...)` both pass
  `max_retries=0` explicitly.
- Exactly one retry-policy implementation remains in the codebase (or a named
  external library replaces all four); `pipeline/definition.py`/`executor.py`'s
  stage-level retry and `agents/providers/openai.py`'s inline loop no longer exist
  as separate mechanisms.
- A test issuing a request that fails validation 3 times (schema-repair path)
  results in a bounded, single-digit total HTTP request count — not up to 9. Assert
  the exact count the collapsed policy produces.
- Exactly one `configure_logging` function exists in the codebase; `AppConfig.logging`
  is either observably wired (a test proves changing `AppConfig.logging.level`
  changes emitted log output) or is deleted along with its dead sibling.
- A test proves the OpenAI provider's conversation store does not grow unboundedly
  across N simulated runs — either bounded size or explicit clear/evict is
  exercised.
- A test proves `enhancement_factory.py`'s HTTP clients are closed after
  `AudioAnalyzer` teardown (assert `aclose()` was called, or that the underlying
  transport reports closed).
- `HAS_SCIPY` has exactly one definition site (`utils.py`); the three former
  redefinition sites import it instead.
- `lyrics/pipeline.py`'s three penalty-scoring call sites all invoke the same
  extracted helper; a test with a fixed input asserts identical penalty output from
  all three call paths (regression-pins the "no behavior change" requirement).

## Tests

TDD where behavior is definable in advance:
- Failing-first test for the request-count bound (currently ≤9, target: assert the
  new bound explicitly) before touching the retry code.
- Failing-first test for conversation-store growth-then-eviction before adding the
  eviction mechanism.
- Failing-first test for `aclose()` being called on teardown before wiring the
  lifecycle.
- Regression test pinning identical penalty-score output across the three
  `lyrics/pipeline.py` call sites, run BEFORE the extraction (captures current
  behavior) and again AFTER (must match) — this is the safety net against
  accidentally changing scoring behavior while deduplicating.

## Verification commands

```bash
uv run pytest tests/unit/api/ tests/unit/agents/providers/ -v
uv run pytest tests/unit/audio/ -v -k "scipy or penalty or HAS_SCIPY"
uv run pytest tests/ -v
uv run mypy .
uv run ruff check .
git grep -n "max_retries" packages/twinklr/core/api/llm/openai/client.py packages/twinklr/core/agents/providers/openai.py
git grep -n "def configure_logging"
```

## Effort & risk

**M.** Main risk: the retry collapse touches the only production LLM call path —
getting the new single policy's attempt count/backoff wrong could either
under-retry (increasing spurious failures on transient errors) or reintroduce the
multiplicative amplification under a different name. Mitigation: the request-count
regression test is the acceptance gate, and P3-M-G's existing (buggy) behavior must
be preserved bit-for-bit so this task's diff is reviewable in isolation from that
separate fix.
