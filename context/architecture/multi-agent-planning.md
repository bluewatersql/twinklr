---
type: context
area: architecture
updated: 2026-08-13
---

# Multi-Agent Planning

The choreography planner is an iterative refinement loop over structured Pydantic models:

1. **Planner** generates a `ChoreographyPlan` (template + preset per song section).
2. **Heuristic validator** checks structural validity (fast, free — template exists,
   timing valid).
3. **LLM validator** checks semantic quality (template appropriateness, coordination).
4. **Judge** scores 0–10 and decides: approve (≥ 7.0), soft-fail (revise), or hard-fail
   (redo). Structured feedback loops back to the planner. Up to 3 iterations by default.

## Design principles

- **LLM plans intent; renderer implements precision** — the foundational decision; see
  [memories/decisions/llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
- **Categorical over numeric** — intensity is WHISPER/SOFT/MED/STRONG/PEAK; duration is
  HIT/BURST/PHRASE/EXTENDED/SECTION. The renderer resolves categories to DMX values.
- **Templates as complete units** — geometry + movement + dimmer as tested, self-contained
  choreography units. The LLM selects templates; it never invents them.
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
