---
type: context
area: architecture
updated: 2026-11-17
---

# Multi-Agent Planning

_Updated from the integrated Phase 2P implementation and re-verified during P4-T6. The
former separate semantic-validation role is not part of the shipped system;
deterministic heuristics plus the LLM judge form the live validation loop._

The choreography planner is an iterative refinement loop over structured Pydantic models:

1. **Planner** generates a typed plan. A moving-head section has 1-3 parts (template and
   preset over its bars) and categorical song intent: intensity, colour (a role in the
   song's palette, whose colours the prompt shows, or a named colour), gobo, timed events
   (open/closed, strobes, pulse, hit, colour, gobo) bound optionally to lyric MomentCues,
   motif and variation, density, and ENTRY/EXIT transitions. The planner is asked to
   answer the song in every section and to give a reason for any field it leaves to the
   template; the judge penalises unanswered lyric cues, flat intensity and an ignored
   palette, and a valid plan leaving a high-emphasis cue unanswered is sent back to the
   planner before judging, at most once per run and only while a planning round remains.
   The
   schema is within Claude's measured limits (11 unions, 60 nodes; pinned in
   `tests/unit/agents/test_structured_outputs.py`).
2. **Normalisation and heuristic validation**: on the moving-head path, single items the
   song cannot hold are repaired, recorded in the plan's `repairs` (and the render
   trace) and fed back on the next iteration, never refusing the plan; structural
   errors fail validation (fast, free). On the display path five deterministic
   auto-repair passes fix common LLM mistakes before scoring.
3. **Judge** scores 0–10 and decides: approve (≥ 7.0 by default), soft-fail (revise),
   or hard-fail (redo). `JudgeVerdict` validation reconciles verdict status to score.
   Structured feedback loops back to the planner. Up to 3 iterations by default.

**Known regression.** The moving-head renderer applies only the selected templates,
presets and their bars. It does not yet render the plan's song intent; the renderer
deleted in the single-renderer cutover rendered intensity, section colour, shutter and
gobo events (cue-bound ones included) and entry transitions. The owner has ruled that
all of it is rendered on the single path and that nothing leaves the planner contract
without the owner's word ([song-intent rendering](../../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md),
[decision](../../memories/decisions/mh-single-renderer.md)). The dated history of that
channel is in
[llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
The planner is offered only the templates the pre-planning gate admitted for the rig and
song. The implemented three-arm harness will test the standing default against a
deterministic selector (choosing among the admitted families) and a macro-ablated LLM
arm, but the owner experiment and D1 verdict are still pending; implementation fixtures
are not decision evidence.

## Design principles

- **LLM plans intent; renderer implements precision** — the foundational decision; see
  [memories/decisions/llm-plans-intent-renderer-implements-precision.md](../../memories/decisions/llm-plans-intent-renderer-implements-precision.md).
- **Categorical over numeric** — intensity is WHISPER/SOFT/MED/STRONG/PEAK for the
  display planner and SLOW/SMOOTH/FAST/DRAMATIC/INTENSE for the moving-head planner;
  duration is HIT/BURST/PHRASE/EXTENDED/SECTION. The display renderer resolves categories to precise
  values; the moving-head renderer does not yet render planner intensity (the known
  regression above).
- **Templates as complete units** — each moving-head template states its steps' motion,
  pulses, wheel states and phase spread as data, checked on the rig before it is offered.
  The LLM selects templates and expresses typed categorical intent; it never invents
  fixture math or direct DMX values.
- **Data-only template loading** — moving-head templates are JSON `TemplateDoc` files in
  one validating registry. The seven-family catalog (`catalog/templates/moving_heads/`)
  loads first and `--template-dir` documents second; normalized ID/name/alias collisions
  fail unless an explicit override targets the exact incumbent ID. Moving-head templates
  and display recipes share the tracked `catalog/templates/` data home but not a schema:
  one catalog for the moving-head and display renderers is the recorded convergence
  direction, not current behavior.
- **Schema auto-injection and enforcement** — Pydantic response models generate both the
  JSON schemas embedded in prompts and provider requests. OpenAI uses the Responses API
  strict `json_schema` path; opt-in loopback Ollama uses Chat Completions with JSON-schema
  `response_format`. A general provider transform converts Pydantic discriminated-union `oneOf`
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
  sequencer planners, shared judge/iteration controller, provider adapters)
- OpenAI is the verified cloud strict-output path. Ollama means Ollama cloud
  (`glm-5.3:cloud`) through the loopback daemon, routed via `/v1/chat/completions`; a
  full `twinklr run` with every role on that model passed on 2026-11-12
  ([evidence](../../changes/twinklr-reactivation-review/evidence/2026-11-12-p4-t2-ollama-cloud-pipeline/README.md)).
  Ollama Cloud does not enforce `response_format`, so the schema travels in the prompt. Claude
  (`llm_provider: anthropic`, default `claude-opus-5-5`) uses `output_config.format`
  structured outputs. Claude refuses to compile the larger planner schemas ("compiled
  grammar is too large"), so the adapter sends those requests with the schema carried only
  by the prompt, decided before sending, and validates them client-side. The moving-head
  planner's schema is within the measured limits and is sent as an enforced format; its
  schema compiled and was enforced live on 2026-11-17 (W2 evidence record). The first Claude live run passed on 2026-11-12
  ([evaluation](../../evaluations/2026-11-12-claude-baseline-live-run/README.md)).
- Runtime prompt packs: `packages/twinklr/core/**/prompts/` (Jinja2 — application source,
  distinct from the root `prompts/` agent-workflow library)
- Deep reference: [docs/audio_profile/index.md](../../docs/audio_profile/index.md) series
- Moving-head data loader: `packages/twinklr/core/sequencer/moving_heads/templates/`
