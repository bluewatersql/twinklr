---
type: context
area: reference
updated: 2026-11-17
---

# Glossary

- **xLights** — open-source lighting control software; Twinklr's output target.
- **`.xsq`** — xLights sequence file format. Twinklr writes one containing only its own
  effects and models; it reads one only to profile a corpus, never to build output.
- **`.xtiming`** — a standalone xLights timing track. Imports into any sequence with no
  model mapping, which makes it Twinklr's mapping-free deliverable.
- **`.xmap`** — mapping hints for xLights' effect import, naming the models a donor
  sequence emitted so the mapping is pre-filled rather than entered row by row.
- **DMX** — digital lighting control protocol; channels/values driven by the renderer,
  never by the LLM.
- **Moving head** — pan/tilt light fixture with dimmer, shutter, color, and gobo channels.
- **Physical profile** — a fixture's `physical_profile`: which DMX offset carries which
  axis or wheel, each axis' calibrated range, each wheel state's byte, and the head's
  timings. The moving-head renderer reads only this, never `dmx_mapping`.
- **Template** — a moving-head choreography unit, a JSON `TemplateDoc` whose steps state
  motion, dimmer or shutter pulse, wheel states and phase spread across the heads. The
  catalog's seven **families** live in `catalog/templates/moving_heads/`. LLMs select
  templates; they never invent them. (Not to be confused with the root `templates/`
  directory of documentation starters, or the display's recipe templates.)
- **Preset** — a named variant of a template that patches some of its steps (the
  catalog's are `narrow` and `slow`).
- **Gate** (`render_preflight`) — the pre-planning check that dry-compiles every offered
  template and preset on the rig over the song and admits each family through its first
  passing variant, its **effective variant**.
- **BeatGrid** — the beat-aligned timing grid produced by audio rhythm analysis.
- **Categorical planning** — LLM reasons in semantic categories (intensity:
  WHISPER/SOFT/MED/STRONG/PEAK; duration: HIT/BURST/PHRASE/EXTENDED/SECTION) which
  deterministic code resolves to precise values. The moving-head renderer does not yet
  render planner intensity: a known regression being fixed
  ([plan](../changes/2026_11_12_mh_true_up/plan/song-intent-rendering.md)).
- **ChoreographyPlan** — the structured Pydantic plan the planner agent produces
  (template + preset per song section).
- **Judge** — the LLM agent scoring plans 0–10; the bar comes from
  `agent.success_threshold` (configured 0–100, converted once to the planners' 0–10).
- **Prompt pack** — a versioned set of Jinja2 templates (system/user/developer) plus
  config that defines one runtime agent's prompting (`packages/twinklr/core/**/prompts/`).
- **FE (feature engineering) pipeline** — incremental corpus analysis of xLights sequence
  packs producing style profiles and recipes; backed by the SQLite **feature store**.
- **Recipe** — a reusable choreography pattern mined from the corpus and promoted for use
  in generation.
- **Viseme** — mouth-shape category mapped from phonemes, used for singing-face effects.
