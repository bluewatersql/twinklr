---
type: context
area: architecture
updated: 2026-08-14
---

# Multi-Agent Planning

_Corrected 2026-08-13 from source evidence (reactivation review): the separate "LLM
validator" role documented earlier was removed from code
(`agents/state_machine.py:18` records the removal); the live loop is below._

The choreography planner is an iterative refinement loop over structured Pydantic models:

1. **Planner** generates a plan (template + preset per song section).
2. **Heuristic validation** checks structural validity (fast, free); on the display
   path five deterministic auto-repair passes fix common LLM mistakes before scoring.
3. **Judge** scores 0–10 and decides: approve (≥ 7.0, enforced by a model validator
   that reconciles status to score), soft-fail (revise), or hard-fail (redo).
   Structured feedback loops back to the planner. Up to 3 iterations by default.

> **Reality note (verified 2026-08-13):** on the shipped moving-heads path the
> renderer consumes only `template_id` + `preset_id` from all of this — see the
> reality-check in
> [memories/decisions/llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).

## Design principles

- **LLM plans intent; renderer implements precision** — the foundational decision; see
  [memories/decisions/llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
- **Categorical over numeric** — intensity is WHISPER/SOFT/MED/STRONG/PEAK; duration is
  HIT/BURST/PHRASE/EXTENDED/SECTION. The renderer resolves categories to DMX values.
- **Templates as complete units** — geometry + movement + dimmer as tested, self-contained
  choreography units. The LLM selects templates; it never invents them.
- **Data-first template loading** — moving-head `TemplateDoc` JSON and Python factories
  share one validating registry. Python builtins load first; configured data loads second,
  and normalized ID/name/alias collisions fail unless an explicit override targets the
  exact incumbent ID. The two forms coexist for progressive migration. Moving-head
  templates and display recipes now share the
  tracked `catalog/templates/` data home but not yet a schema: one catalog with two
  renderers is the recorded convergence direction, not current behavior.
- **Schema auto-injection** — Pydantic response models generate the JSON schemas embedded
  in prompts, eliminating prompt/schema drift.
- **Two-tier validation** — heuristics run before the LLM judge to save tokens on
  structurally invalid plans.
- **Data-driven agents** — no agent class hierarchies: one runner + `AgentSpec` data
  objects (prompt pack, response model, LLM settings).

## Where things live

- Agent orchestration: `packages/twinklr/core/agents/` (audio/lyrics profiling,
  sequencer planners, shared judge/iteration controller, OpenAI provider adapter)
- Runtime prompt packs: `packages/twinklr/core/**/prompts/` (Jinja2 — application source,
  distinct from the root `prompts/` agent-workflow library)
- Deep reference: [docs/audio_profile/index.md](../../docs/audio_profile/index.md) series
- Moving-head data loader: `packages/twinklr/core/sequencer/moving_heads/templates/`
