# P2P-T10 — Model retarget (D6)

Phase: 2P (Creative Quality, Measured) · Lane: P (platform, parallel) · Executor: sonnet · Verifier: opus · Depends on: P1P-T9

## Objective

Retarget every model call to current models before the December 2026 retirements,
set `reasoning.effort` explicitly for every agent role so the GPT-5.6 default does not
silently change cost and latency, and consolidate the scattered hardcoded model IDs
into the configuration surface that already exists but is largely unwired — including
the call sites outside the agent framework that a retarget grep would miss.

## Evidence & background

Findings: **D6 (Models)**, **M1 (modernization — REQUIRED, hard deadlines)**,
**P1-F15** (config reaches ~2 of ~6 shipped agent invocations), **P3-F2**
(`judge_agent` never wired), **CC-8 / P6-M1** (LLM call sites outside the framework),
**P3-F21** (temperature dropped for "mini" models), plus **P1K-T5**'s relocated call
sites.
Sources: `changes/twinklr-reactivation-review/reviews/modernization.md` M1, M4;
`.../reviews/reactivation-proposal.md` D6; `.../reviews/verification.md` "Phase 3"
cache-fingerprint addendum, "Phase 6".

### M1 quoted — the retarget table and the deadlines

> | Current (code) | Status | Deadline | Target |
> |---|---|---|---|
> | `gpt-5.2` (default, 29 sites) | serving, "previous frontier" | none | **`gpt-5.6-terra`** default; `gpt-5.6-sol` only where evaluation proves quality-critical |
> | `gpt-5-mini` (judge) | deprecated | **2026-12-11** | `gpt-5.6-terra` (official) or `gpt-5.6-luna` (cost-analogue judge, $0.20/$1.20 per 1M) |
> | `gpt-image-1.5` (image client) | deprecated | **2026-12-01** | `gpt-image-2` |
> | `gpt-4.1`, `gpt-4o-mini` | serving, no deadline | — | opportunistic (`terra`/`luna`) |

> Economics (per 1M tokens, standard tier): gpt-5.2 $1.75/$14.00; gpt-5.6-terra
> $2.00/$12.00 (output *cheaper* than incumbent); gpt-5.6-sol $5.00/$30.00 (≈2–3×);
> gpt-5.6-luna $0.20/$1.20. Context expands 400K→1.05M on 5.6.

D6's owner-set targets override M1's default where they differ — the owner's fixed
constraint is "Quality over cost (`gpt-5.6-sol` planning default)":

> **D6 — Models** *(unchanged)*: sol planning / terra judge / gpt-image-2; explicit
> `reasoning.effort`; structured-outputs migration; Dec 2026 retirement deadlines;
> include the out-of-framework call site.

**Targets for this task: `gpt-5.6-sol` for planners / profile / lyrics; `terra` for
judges; `gpt-image-2` for assets.**

### The `reasoning.effort` requirement, quoted

> **Behavioral trap:** GPT-5.6 defaults `reasoning.effort=medium`; gpt-5.2 defaults to
> none. A bare string swap silently adds reasoning-token cost and latency — the
> retarget MUST set `reasoning.effort` explicitly per agent role.

And the plan overview's sequencing constraint, verbatim:

> - Model retarget must set `reasoning.effort` explicitly and include the
>   out-of-framework call site `normalization/llm_review.py` (P2P-T10).

**Both halves are non-negotiable acceptance criteria.**

### The out-of-framework site

P6-M1 (MED-HIGH): `normalization/llm_review.py` "hardcodes gpt-4o-mini on a raw
client — **an LLM call site outside the entire agent framework; any M1 retarget grep
of the agent layer misses it**".

**Re-verified in this tree (2026-08-13): the file is at
`packages/twinklr/core/feature_engineering/normalization/llm_review.py`** (the reviews
cite it as `feature_engineering/normalization/llm_review.py`; the `core/` prefix is
the current path). P3-M-C names the full set of three bypass surfaces:
`normalization/llm_review.py` (`chat.completions.create`),
`core/api/llm/openai/client.py` (`responses.create`, reached by `recipe_builder`), and
`assets/stage.py` (`AsyncOpenAI()` for images).

**P1K-T5 moves `normalization/llm_review.py` and `recipe_builder/generation.py` onto
the provider framework.** If P1K-T5 has merged, those call sites are inside the
framework and this task retargets them there. If it has not, this task must still
cover them where they are — the constraint says *include the site*, not *wait for the
lane*. Check and state which situation applies in the handoff.

### The configuration surface (the actual work)

> Remediation should also move model IDs from 29 hardcoded sites into configuration
> (they are already configurable via `AgentConfig.model` defaults — consolidate; note
> phase-1/3 finding: most of that config surface is currently unwired).

**Re-verified in this tree: 50 matches for the five model IDs across `packages/` and
`scripts/` `.py` files** (including docstrings, comments and pricing tables), with the
functional defaults at: `config/models.py:22` (`AgentConfig.model = "gpt-5.2"`),
`config/models.py:109` (`judge_agent` default `gpt-5-mini`), `agents/spec.py:46`
(`AgentSpec.model` default `gpt-5.2`), the five spec factories
(`audio/{lyrics,profile}/spec.py`, `sequencer/{macro_planner,moving_heads,group_planner}/specs.py`,
`group_planner/holistic.py`), `agents/assets/{image_client,prompt_enricher}.py`, and
`core/api/llm/openai/client.py`.

The unwired-config evidence:
- **P1-F15**: "config reaches ~2 of ~6 shipped agent invocations (`temperature` etc.
  unwired even for plan_agent; MH planner model is a Python default)."
- **P3-F2**: `AgentOrchestrationConfig.judge_agent` — "zero readers anywhere". The
  macro judge therefore runs at frontier price by wiring bug, not decision.

**So the task is wiring, not renaming.** A retarget that changes 50 string literals
and leaves the config unwired has done the easy half and left the deceptive half.

### Cache safety, quoted (this gate is already cleared)

> **Cache-interaction (verified)**: model IDs ARE in every LLM stage's cache key, so
> the retarget cannot serve stale cached plans — gate cleared. But prompt-pack content
> is in NO key; once cross-run cache reuse is fixed (P1-F4), any prompt edit silently
> serves stale plans — land prompt-content hashing in the same change as the
> session-ID fix (see verification.md cache-fingerprint addendum).

The prompt-hashing half is P1P-T9, this task's dependency. So: **cache-safe**, and the
dependency is what makes it so.

### The temperature interaction

P3-F21: `openai.py:302-303` drops `temperature` for any model whose name contains
"mini". Retargeting `gpt-5-mini` → `gpt-5.6-luna`/`terra` **silently re-enables**
temperature for `mh_judge` (0.3), the section judge (0.3) and the asset enricher
(0.6) — "changing behavior in a way the retarget would not predict". Handle it
explicitly: either remove the substring hack and gate on a real capability flag, or
keep the drop and document it. Do not let it change behavior by accident.

Line numbers are hints from baseline `aa8d325`; re-verify before editing.

## Current behavior

- Model IDs are Python defaults scattered across spec factories, orchestrator
  signatures, config defaults and two out-of-framework clients.
- `AgentConfig.judge_agent` and most of `AgentOrchestrationConfig`'s per-agent config
  are inert; the macro judge runs `gpt-5.2` because `get_judge_spec()` is called with
  no arguments.
- No call sets `reasoning.effort`.
- Temperature is silently dropped for any model whose id contains "mini".
- `gpt-5-mini` (retires 2026-12-11) and `gpt-image-1.5` (retires 2026-12-01) are in
  the shipped path.

## Target behavior

1. **Every model id comes from configuration**, with one documented default per agent
   role. No shipped code path selects a model from a Python literal. Comments,
   docstrings and pricing tables that name a model are updated or deleted so a future
   retarget grep finds only live sites.
2. **Targets applied**: `gpt-5.6-sol` for the two planners, the audio-profile agent
   and the lyrics agent; `gpt-5.6-terra` for the judges; `gpt-image-2` for the image
   client (ahead of the 2026-12-01 retirement). Opportunistic `terra`/`luna` for the
   `gpt-4.1`/`gpt-4o-mini` sites, including the out-of-framework one.
3. **`reasoning.effort` is set explicitly for every agent role** and is part of the
   config surface. Choose per role and document the reasoning:
   planners/profile/lyrics get a deliberate value (quality axis); judges get a
   deliberate value (they evaluate, they do not create). The requirement is that no
   call relies on the provider's default.
4. **`AgentOrchestrationConfig` is genuinely wired**: `judge_agent` gets a reader
   (P3-F2), and the per-agent config that P1-F15 shows reaching ~2 of ~6 invocations
   reaches all of them — or the unreachable members are deleted. Half-wired config is
   the worst outcome ("some fields work, some silently do not, and one actively
   fails — the worst configuration failure mode, because it defeats the user's
   ability to reason about the file at all").
5. **`docs/user-guide.md` matches reality** for every knob touched (P7-M2 records the
   guide as unreliable as a class; this task must not add to it).
6. **The temperature/"mini" interaction is resolved explicitly** and its resolution is
   tested.
7. **No new out-of-framework call sites.** If P1K-T5 has not merged, retarget the
   existing ones in place and note them for T5's relocation.

### Non-goals

- Structured outputs migration (**P2P-T11**, which depends on this task).
- OpenAI SDK 3.x (M4: "zero soak time: pin latest 2.x for reactivation; adopt 3.x as
  a separate later item").
- Enabling the assets pipeline. `gpt-image-2` retargeting is a string/config change;
  **`enable_assets=True` remains gated behind P3-F28b's cost controls**, which are
  Phase 3 work (D13). Retarget the client without flipping the flag.
- Per-call token accounting (P1P-T9).
- Prompt content changes.

## Implementation approach

Files/symbols (re-verify first):

- `packages/twinklr/core/config/models.py` — `AgentConfig.model` (`:22`),
  `AgentOrchestrationConfig.judge_agent` (`:109`) and siblings; add the
  `reasoning.effort` surface.
- `packages/twinklr/core/agents/spec.py` — `AgentSpec.model` default (`:46`); add
  reasoning-effort to the spec if that is where it belongs.
- Spec factories: `agents/audio/lyrics/spec.py`, `agents/audio/profile/spec.py`,
  `agents/sequencer/macro_planner/specs.py`,
  `agents/sequencer/moving_heads/specs.py`,
  `agents/sequencer/group_planner/specs.py`, `group_planner/holistic.py`.
- Orchestrators with `model: str = "gpt-5.2"` parameters (`audio/*/orchestrator.py`).
- `packages/twinklr/core/agents/providers/openai.py` — where `reasoning.effort` is
  sent; also the "mini" temperature hack.
- `packages/twinklr/core/agents/assets/image_client.py`, `prompt_enricher.py`.
- `packages/twinklr/core/api/llm/openai/client.py`.
- `packages/twinklr/core/feature_engineering/normalization/llm_review.py` — **the
  out-of-framework site named in the sequencing constraint**.
- `packages/twinklr/core/agents/token_budget_manager.py` — carries a gpt-5.2 pricing
  docstring; note it is dead code (P3-F33) slated for removal, so update or leave with
  a comment, but do not let it be the reason a grep finds a stale id.
- `docs/user-guide.md`.

Sequencing constraints copied verbatim from the plan:

> - Model retarget must set `reasoning.effort` explicitly and include the
>   out-of-framework call site `normalization/llm_review.py` (P2P-T10).
> - Deterministic session-ID + cache-root anchoring + prompt-content hashing land
>   **together** (P1P-T9).
> - **Verification currency**: evidence in specs is from baseline `aa8d325`.
>   Executors must re-verify cited line numbers before editing.

## Acceptance criteria

1. `grep -rn 'gpt-5\.2\|gpt-5-mini\|gpt-4o-mini\|gpt-image-1\.5' packages/ scripts/`
   returns only entries that are provably not model selections (or nothing). Every
   remaining match is justified in the handoff.
2. Every agent role's model comes from configuration; changing the config changes the
   model actually sent, asserted against a fake provider that records the request.
3. **Every request carries an explicit `reasoning.effort`.** A test asserts no agent
   role relies on the provider default. This is the constraint most likely to be
   skipped, so it gets its own test.
4. The out-of-framework `normalization/llm_review.py` call site is retargeted (or
   relocated per P1K-T5) and is covered by the same config surface; its model is no
   longer a Python literal.
5. `judge_agent` has a reader, and the macro judge's model comes from config rather
   than `get_judge_spec()`'s Python default. Any per-agent config member that still
   cannot reach a call is deleted, not left inert.
6. The temperature/"mini" behavior after retarget is deliberate and tested (either the
   substring hack is gone and temperature is sent, or it is retained on an explicit
   capability check and documented).
7. `docs/user-guide.md` describes the post-task behavior of every knob touched.
8. The image client targets `gpt-image-2`; `enable_assets` remains `False`.
9. Cache behavior: a model change produces a clean cache miss (already true — assert
   it so it stays true).
10. `make validate` check-only forms pass.

## Tests

1. `test_every_agent_role_sends_explicit_reasoning_effort` — parametrized over the
   agent specs; fake provider records the request payload. Criterion 3's guard.
2. `test_model_id_comes_from_config` — parametrized per role; config change → request
   change.
3. `test_no_hardcoded_model_literals` — repo-level grep test over `packages/` with an
   explicit allowlist of justified matches; makes the next retarget cheap.
4. `test_judge_agent_config_is_read` — the P3-F2 guard.
5. `test_temperature_behavior_after_retarget` — pins whichever resolution was chosen.
6. `test_cache_key_includes_model` — a model change is a miss.
7. `test_out_of_framework_site_uses_config` — covers `llm_review.py` wherever it lives
   at merge time.
8. **LOCAL-ONLY** `test_live_smoke_one_call_per_role` — one real call per agent role
   against the new models, asserting a parseable response. Budget: **≤ 6 calls,
   ≤ $1.00**. This is also where M2's open question gets answered if T11 has not run
   yet: whether `gpt-5.6-*` accepts `json_object` mode at all (call site
   `providers/openai.py`, the `"text": {"format": {"type": "json_object"}}` line).
   Record the answer — P2P-T11 depends on it.

## Verification commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/agents -q
uv run pytest -k "model or reasoning or retarget" -q
grep -rn 'gpt-5\.2\|gpt-5-mini\|gpt-4o-mini\|gpt-image-1\.5' packages/ scripts/
```

LOCAL-ONLY (`OPENAI_API_KEY` set):

```bash
uv run pytest -m local_only -k "live_smoke" -q     # budget: ≤6 calls, ≤$1.00
```

Paid-API budget for this task: **≤ $2.00 total**.

## Effort & risk

**M.** Mechanically bounded but wide: ~50 textual sites and a config surface that is
mostly unwired, so the real work is making configuration reach the call. Main risk:
declaring victory after the string swap, leaving `reasoning.effort` unset — which
silently adds reasoning-token cost and latency to every call and would show up in
P2P-T13's cost figures as an unattributable jump ("reasoning tokens are inside
`output_tokens` but never separated"). Mitigation: criterion 3 has its own
parametrized test. Second risk: the "mini" temperature hack changing three agents'
sampling behavior invisibly — mitigated by making it an explicit decision with a test.
Third risk: touching the assets client tempts flipping `enable_assets`; it stays off,
gated behind P3-F28b.

## Backlog addition (P1P-T9 verification, 2026-08-13)
Reasoning tokens are unseparated inside output token counts; when setting explicit
reasoning.effort here, split reasoning vs completion tokens in TokenUsage so cost
instrumentation stays honest on 5.6-class models.
