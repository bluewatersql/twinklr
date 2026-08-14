# P1K-T5 — Out-of-framework LLM calls into the framework

Phase: 1K · Lane: FW · Executor: sonnet · Verifier: sonnet · Depends on: —

## Objective

Move the two LLM call sites in this phase's scope —
`feature_engineering/normalization/llm_review.py::LLMReviewPass` and
`recipe_builder/generation.py::generate_with_llm` — off raw/ad-hoc OpenAI
clients and onto Twinklr's `agents/providers` framework
(`LLMProvider` protocol, dispatched via `create_llm_provider`), so both get
config-driven model selection instead of hardcoded model strings, and both
become visible to any future model-ID retarget sweep scoped to `agents/`. Also
seed the unseeded `random.shuffle` in `recipe_builder/generation.py`'s exemplar
selection so repeated runs over identical input produce reproducible example
choices.

## Evidence & background

**P6-M1 (MED-HIGH, ADDED at verification)**:
`feature_engineering/normalization/llm_review.py:32` hardcodes a call to
`gpt-4o-mini` on a raw client, entirely outside `agents/providers/*` — "the one
place in this phase's scope where an LLM call site would be invisible to a
modernization sweep scoped to the agent layer." Full text:
`changes/twinklr-reactivation-review/reviews/phases/corpus-intelligence.md`
("P6-M1" and "normalization/ contains a hardcoded LLM call site entirely
outside the agent framework"). This finding is also the concrete evidence that
overturned the phase's original subsystem-wide "deterministic" headline
(REJECTED at verification) — recipe_builder generation is LLM-driven by
default (count #2) and this is count #1.

**Sequencing constraint, copied verbatim from `changes/twinklr-reactivation-review/build/plan/00-overview.md`**
(applies to this task and must be respected by whoever executes P2P-T10
later): *"Model retarget must set `reasoning.effort` explicitly and include
the out-of-framework call site `normalization/llm_review.py` (P2P-T10)."*
**This task (P1K-T5) does the plumbing only** — it moves both call sites onto
the provider framework so that a *later* task (P2P-T10, Phase 2P, out of this
task's scope) can find and retarget them with an explicit `reasoning.effort`
and updated model IDs. **Do not set `reasoning.effort` or change either call
site's target model identity in this task** beyond making the model a
config-driven value instead of a hardcoded literal (see Target behavior).

**Call site 1 — `feature_engineering/normalization/llm_review.py`**
(`llm_review.py:24-34,71-78`, baseline `aa8d325`):

```python
class LLMReviewPass:
    def __init__(self, llm_client: Any, model: str = "gpt-4o-mini") -> None:
        self._client = llm_client
        self._model = model

    def _review_single(self, cluster: AliasClusterGroup) -> AliasReviewResult:
        ...
        response = self._client.client.chat.completions.create(
            model=self._model,
            messages=[...],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
```

Note the double unwrap: `self._client.client.chat.completions.create(...)` —
`llm_client` here is an `OpenAIClient` wrapper (from
`twinklr.core.api.llm.openai.client`), and `.client` reaches through to the
raw OpenAI SDK object underneath it, then calls the SDK's
`chat.completions.create` directly. This is two layers below where the
`agents/providers` framework's `LLMProvider.generate_json()` already sits.

**Sole caller** (confirmed by repo-wide grep — `LLMReviewPass` has exactly one
non-test call site): `scripts/analysis/normalize_unknown_effects.py:135-141`:

```python
from twinklr.core.api.llm.openai.client import OpenAIClient
from twinklr.core.feature_engineering.normalization.llm_review import LLMReviewPass
...
reviewer = LLMReviewPass(llm_client=llm_client)
```

where `llm_client` is constructed as a raw `OpenAIClient` earlier in the same
script. This confirms `LLMReviewPass` is *not* wired into
`corpus_artifacts.py`'s main pipeline at all today — it is exercised only by
this standalone offline analysis script, consistent with the corpus-
intelligence review's framing of `normalization/` as one of the still-unread,
lower-priority residual-gap modules; this task's scope is limited to the LLM
plumbing, it does not wire `LLMReviewPass` into the main pipeline (that is a
separate, unscoped change).

**Call site 2 — `recipe_builder/generation.py::generate_with_llm`**
(`generation.py:343-420`, baseline `aa8d325`):

```python
def generate_with_llm(
    opportunities, analysis, catalog_recipes, llm_client: Any,
    model: str = "gpt-4.1", temperature: float = 0.9,
) -> list[RecipeCandidate]:
    ...
    raw = llm_client.generate_json(messages=messages, model=model, temperature=temperature)
```

`llm_client` here is constructed via
`twinklr.core.api.llm.openai.client.create_client(api_key=...)`
(`scripts/demo_recipe_builder.py:191`) — the **raw** `OpenAIClient`, not
`agents.providers.openai.OpenAIProvider`. Confirmed:
`OpenAIProvider._sync_client = OpenAIClient(...)` internally
(`agents/providers/openai.py:69`) — i.e. `OpenAIProvider` already wraps this
exact client to provide the standardized `LLMProvider.generate_json()`
surface, retries, and token accounting, but `generation.py` never goes through
that wrapper or through `agents/providers/factory.py::create_llm_provider()`
— it bypasses the framework's dispatch layer entirely, configuring its model
via a bare function default (`model: str = "gpt-4.1"`) instead of
`AppConfig`/`AgentConfig`.

Also in this file: `_select_diverse_examples()` (`generation.py:263-311`) calls
`random.shuffle(candidates)` (`:277`) with the global, unseeded RNG —
determinism-breaking count #3 named in the P6 review's REJECTED-headline
evidence ("unseeded `random.shuffle` in exemplar selection ... repeated runs
over identical input can produce different candidate orderings/selections").

**The framework these move onto**:

- `agents/providers/base.py::LLMProvider` (Protocol) — `generate_json(messages,
  model, temperature=None, **kwargs) -> LLMResponse`, where
  `LLMResponse.content: Any  # Parsed JSON dict` (`base.py:37-42,64-92`) — the
  response is already a parsed dict, no manual `json.loads(...)` needed by
  callers.
- `agents/providers/factory.py::create_llm_provider(app_config: AppConfig,
  session_id: str) -> LLMProvider` — the single existing dispatch point
  (openai/anthropic today) every other framework-compliant call site in the
  repo uses (`factory.py:10-41`).
- `config/models.py::AgentConfig` (`models.py:19-30`) — the existing
  per-agent LLM config shape already used elsewhere (e.g.
  `AgentConfig(model="gpt-5-mini", temperature=1.0)` at `models.py:109`):
  `model: str`, `temperature: float`, `max_tokens: int`,
  `timeout_seconds: int`. Reuse this shape for both call sites' config —
  do not invent a new config pattern.
- `config/models.py::AppConfig` (`models.py:419-440`) already carries
  `llm_provider`, `llm_api_key`, `llm_base_url` — the fields
  `create_llm_provider()` consumes.

## Current behavior

`LLMReviewPass` and `generate_with_llm` each accept a bare `llm_client: Any`
and a hardcoded default model string (`"gpt-4o-mini"`, `"gpt-4.1"`
respectively), calling either the raw OpenAI SDK object directly
(`llm_review.py`) or a raw `OpenAIClient.generate_json()` (`generation.py`).
Neither goes through `agents/providers/factory.py::create_llm_provider()`.
`_select_diverse_examples()`'s example ordering is non-reproducible across
runs.

## Target behavior

1. **`LLMReviewPass`**: constructor changes from
   `__init__(self, llm_client: Any, model: str = "gpt-4o-mini")` to
   `__init__(self, provider: LLMProvider, config: AgentConfig)`.
   `_review_single()` calls
   `self._provider.generate_json(messages=[...], model=self._config.model, temperature=self._config.temperature)`
   and reads the parsed dict directly from `response.content` (drop the manual
   `response.choices[0].message.content` unwrap and `json.loads(...)` — the
   provider already returns parsed JSON). Drop the explicit
   `response_format={"type": "json_object"}` kwarg unless
   `OpenAIProvider.generate_json()`'s implementation requires it be passed
   through `**kwargs` — check `agents/providers/openai.py`'s `generate_json`
   body before removing; if it does not force JSON mode itself, pass it
   through via `**kwargs`.
2. **`generate_with_llm`**: signature changes from
   `(..., llm_client: Any, model: str = "gpt-4.1", temperature: float = 0.9)`
   to `(..., provider: LLMProvider, config: AgentConfig)`. The call becomes
   `provider.generate_json(messages=messages, model=config.model, temperature=config.temperature)`,
   reading `response.content` as the already-parsed dict passed to
   `_parse_llm_response()` (the current code already treats
   `llm_client.generate_json(...)`'s return value as a raw dict via
   `_parse_llm_response(raw)` — confirm `OpenAIClient.generate_json()`'s
   return shape matches `LLMResponse.content`'s shape exactly; if
   `OpenAIClient.generate_json()` already returns a parsed dict today, this is
   a call-shape change only, not a parsing-logic change).
3. **Config surface** — add `AgentConfig`-typed fields in place of the bare
   model/temperature defaults:
   - `recipe_builder/pipeline.py::PipelineConfig` currently has
     `llm_client: Any | None = None`, `llm_model: str = "gpt-4.1"`,
     `llm_temperature: float = 0.9` (`pipeline.py:60-62`). Replace these three
     fields with `llm_provider: LLMProvider | None = None` and
     `generation_agent: AgentConfig = field(default_factory=AgentConfig)`.
     Update `run_pipeline()`'s call into `generate_candidates()` accordingly
     (`pipeline.py:236`).
   - `feature_engineering/config.py` gains a new field for `LLMReviewPass`'s
     configuration, e.g. `normalization_review_agent: AgentConfig | None =
     None` on whichever options dataclass is appropriate for
     `scripts/analysis/normalize_unknown_effects.py` to source it from (this
     script is standalone and not part of `FeatureEngineeringPipelineOptions`'s
     main flow — adding the field to `config.py` keeps the config pattern
     consistent even though the only current caller is the standalone script;
     do not wire `LLMReviewPass` into the main pipeline as part of this task).
4. **Callers updated**: `scripts/demo_recipe_builder.py:191` (`create_client(api_key=...)`)
   → `create_llm_provider(app_config, session_id)`, passed as
   `PipelineConfig.llm_provider`; `scripts/analysis/normalize_unknown_effects.py:135-141`
   similarly updated to construct a provider via `create_llm_provider(...)`
   and an `AgentConfig` instead of a raw `OpenAIClient`.
5. **Seed the exemplar shuffle**: `_select_diverse_examples()`'s
   `random.shuffle(candidates)` becomes
   `random.Random(seed).shuffle(candidates)`, where `seed` is derived
   deterministically and stably from the opportunity being generated for —
   e.g. `int(hashlib.sha1(opportunity.opportunity_id.encode()).hexdigest()[:8], 16)`
   — so the same opportunity over the same catalog always selects the same
   example set, while different opportunities still see different shuffles.
   Do not use a single global fixed seed for every opportunity (that would
   make every opportunity's example selection identical, defeating the
   diversity intent) — the seed must vary per-opportunity but be
   deterministic given the opportunity.

**Non-goals**: no change to either prompt's content/wording; no change to
`_parse_llm_response()`'s validation/fixup logic in either file; no setting of
`reasoning.effort` (P2P-T10's job, later); no model-ID change beyond
"config-driven instead of hardcoded" (the actual target model values are
whatever `AgentConfig`'s defaults or the caller's config say today — do not
retarget to a new model as part of this task); no wiring of `LLMReviewPass`
into `corpus_artifacts.py`'s main pipeline (its only caller remains the
standalone analysis script, now updated to use the framework).

## Implementation approach

Files:

- `packages/twinklr/core/feature_engineering/normalization/llm_review.py` —
  constructor + `_review_single()` rewrite as above.
- `packages/twinklr/core/feature_engineering/config.py` — new
  `AgentConfig`-typed field for the normalization review pass.
- `packages/twinklr/core/recipe_builder/generation.py` —
  `generate_with_llm()` signature + body rewrite; `_select_diverse_examples()`
  seeded-shuffle change; `generate_candidates()`'s dispatch logic
  (`generation.py:616-657`) updated to pass `provider`/`config` instead of
  `llm_client`/`model`/`temperature`.
- `packages/twinklr/core/recipe_builder/pipeline.py` — `PipelineConfig` field
  changes (`llm_client`/`llm_model`/`llm_temperature` →
  `llm_provider`/`generation_agent`); update `run_pipeline()`'s call site
  (`pipeline.py:236`) and the manifest's `input_paths` dict
  (`pipeline.py:380`, currently logs `config.llm_model` — update to
  `config.generation_agent.model`).
- `scripts/demo_recipe_builder.py` — provider construction via
  `create_llm_provider`.
- `scripts/analysis/normalize_unknown_effects.py` — provider construction via
  `create_llm_provider`; `LLMReviewPass` call-site update.

Sequencing constraint (copied verbatim, applies to whoever later executes
P2P-T10, not to this task's own scope): *"Model retarget must set
`reasoning.effort` explicitly and include the out-of-framework call site
`normalization/llm_review.py` (P2P-T10)."* This task's job is to make that
later step possible by removing the "out-of-framework" part of that
description — leave a short code comment or docstring note on
`LLMReviewPass.__init__` pointing future readers at this constraint if useful,
but do not implement the retarget itself here.

## Acceptance criteria

- Neither `llm_review.py` nor `generation.py` imports or references
  `twinklr.core.api.llm.openai.client` directly anymore (both go through
  `LLMProvider`/`agents/providers`).
- Both files' model selection comes from an `AgentConfig` value, not a bare
  string default baked into a function/constructor signature.
- `PipelineConfig.llm_model`/`llm_temperature`/`llm_client: Any` are removed,
  replaced by `llm_provider: LLMProvider | None` +
  `generation_agent: AgentConfig`.
- `_select_diverse_examples()`'s shuffle is seeded deterministically per
  opportunity; two calls with the same opportunity + catalog produce identical
  selected-example ordering; two different opportunities over the same
  catalog can (not must, but demonstrably can) produce different orderings.
- `scripts/demo_recipe_builder.py` and
  `scripts/analysis/normalize_unknown_effects.py` both construct their LLM
  access via `create_llm_provider(app_config, session_id)`.
- No `reasoning.effort` value is introduced by this task; no model ID
  literal changes value (only becomes config-sourced).
- `mypy`/`ruff` clean on all touched files.

## Tests

- `tests/unit/feature_engineering/normalization/test_llm_review.py`: update
  the existing test double from a raw-client mock to an `LLMProvider`-protocol
  fake (a stub implementing `generate_json()` returning a pre-built
  `LLMResponse`); assert `_review_single()` reads `response.content` directly
  with no `json.loads` step in the test's mock path.
- `tests/unit/recipe_builder/test_generation.py`: same fake-provider pattern
  for `generate_with_llm()`; add
  `test_select_diverse_examples_is_deterministic` — call
  `_select_diverse_examples()` twice with the same opportunity/catalog, assert
  identical output ordering; call it with two different opportunities, assert
  the two calls are not required to (but may) differ — do not assert
  inequality strictly if it could flake on a small candidate pool, assert
  reproducibility instead as the primary claim.
- `tests/unit/recipe_builder/test_pipeline.py`: update any `PipelineConfig`
  construction in existing tests to the new `llm_provider`/`generation_agent`
  fields.

## Verification commands

```bash
uv run pytest tests/unit/feature_engineering/normalization/test_llm_review.py -q
uv run pytest tests/unit/recipe_builder/test_generation.py tests/unit/recipe_builder/test_pipeline.py -q
uv run ruff check packages/twinklr/core/feature_engineering/normalization packages/twinklr/core/recipe_builder
uv run mypy packages/twinklr/core/feature_engineering/normalization packages/twinklr/core/recipe_builder
grep -rn "api.llm.openai.client" packages/twinklr/core/feature_engineering/normalization/llm_review.py packages/twinklr/core/recipe_builder/generation.py || echo "clean"
```

No LOCAL-ONLY / paid-API steps — this task's test budget is fake-provider unit
tests only; no live LLM calls are required or authorized to verify it.

## Effort & risk

**M.** Mechanical signature/plumbing change at two call sites plus one
config-shape change threaded through their callers; the main risk is
under-verifying that `LLMResponse.content`'s shape (already-parsed dict)
actually matches what each file's downstream parsing code expects —
mitigated by checking `OpenAIProvider.generate_json()`'s and
`OpenAIClient.generate_json()`'s actual return shapes before assuming
parity, and by the fake-provider unit tests exercising the real parse path.
Secondary, low risk: accidentally changing prompt content or validation
behavior while touching these files — out of scope, keep diffs to the
plumbing described above.
