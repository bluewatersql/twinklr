---
type: context
area: architecture
updated: 2026-08-14
---

# Multi-Agent Planning

_Updated 2026-08-14 from the integrated Phase 2P implementation. The separate "LLM
validator" role documented before the reactivation review remains removed; deterministic
heuristics plus the LLM judge form the live validation loop._

The choreography planner is an iterative refinement loop over structured Pydantic models:

1. **Planner** generates a typed schema-v2 plan. A section selects a template/preset and
   can carry categorical intensity, color, shutter, gobo, segmentation, and lyric
   MomentCue intent.
2. **Heuristic validation** checks structural validity (fast, free); on the display
   path five deterministic auto-repair passes fix common LLM mistakes before scoring.
3. **Judge** scores 0–10 and decides: approve (≥ 7.0, enforced by a model validator
   that reconciles status to score), soft-fail (revise), or hard-fail (redo).
   Structured feedback loops back to the planner. Up to 3 iterations by default.

The moving-head renderer now resolves schema-v2 intensity, color, shutter, gobo, and
MomentCue intent deterministically. The earlier `template_id` + `preset_id`-only
bottleneck is preserved as a dated baseline and resolution record in
[llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
The implemented three-arm harness will test the standing default against a deterministic
selector and a macro-ablated LLM arm, but the owner experiment and D1 verdict are still
pending; implementation fixtures are not decision evidence.

## Design principles

- **LLM plans intent; renderer implements precision** — the foundational decision; see
  [memories/decisions/llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
- **Categorical over numeric** — intensity is WHISPER/SOFT/MED/STRONG/PEAK; duration is
  HIT/BURST/PHRASE/EXTENDED/SECTION. The renderer resolves categories to DMX values.
- **Templates as complete units** — geometry + movement + dimmer as tested, self-contained
  choreography units. The LLM selects templates and expresses typed categorical intent;
  it never invents fixture math or direct DMX values.
- **Data-first template loading** — moving-head `TemplateDoc` JSON and Python factories
  share one validating registry. Python builtins load first; configured data loads second,
  and normalized ID/name/alias collisions fail unless an explicit override targets the
  exact incumbent ID. The two forms coexist for progressive migration. Moving-head
  templates and display recipes now share the
  tracked `catalog/templates/` data home but not yet a schema: one catalog with two
  renderers is the recorded convergence direction, not current behavior.
- **Schema auto-injection and enforcement** — Pydantic response models generate both the
  JSON schemas embedded in prompts and the OpenAI Responses API strict `json_schema`
  request. A general provider transform converts Pydantic discriminated-union `oneOf`
  to supported nested `anyOf` and removes discriminator metadata; Pydantic still
  enforces the branch semantics after generation. Unsupported schema keywords and the
  provider's 5,000-property/10-level/1,000-enum ceilings fail locally before a request.
  The exact normalized response-schema hash is part of agent-stage cache identity.
  Explicit model-capability rejection can take an observable `json_object` fallback;
  invalid-schema/request errors fail loudly. Malformed JSON, refusal, truncation,
  content filtering, and empty responses get one bounded logical retry, with each
  failed response's tokens retained in exact per-stage attribution.
- **Two-tier validation** — heuristics run before the LLM judge to save tokens on
  structurally invalid plans.
- **Data-driven agents** — no agent class hierarchies: one runner + `AgentSpec` data
  objects (prompt pack, response model, LLM settings).

## Where things live

- Agent orchestration: `packages/twinklr/core/agents/` (audio/lyrics profiling,
  sequencer planners, shared judge/iteration controller, OpenAI provider adapter)
- OpenAI is the required provider for registered strict-output agent roles. Anthropic is
  still configurable for legacy/direct calls but is rejected loudly for those roles
  until it has an equivalent schema-enforcement implementation.
- Runtime prompt packs: `packages/twinklr/core/**/prompts/` (Jinja2 — application source,
  distinct from the root `prompts/` agent-workflow library)
- Deep reference: [docs/audio_profile/index.md](../../docs/audio_profile/index.md) series
- Moving-head data loader: `packages/twinklr/core/sequencer/moving_heads/templates/`
