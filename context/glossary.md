---
type: context
area: reference
updated: 2026-08-13
---

# Glossary

- **xLights** — open-source lighting control software; Twinklr's output target.
- **`.xsq`** — xLights sequence file format (native Twinklr output).
- **DMX** — digital lighting control protocol; channels/values driven by the renderer,
  never by the LLM.
- **Moving head** — pan/tilt light fixture with dimmer, shutter, color, and gobo channels.
- **Template** — a pre-built, tested choreography unit (geometry + movement + dimmer),
  e.g. fan formation, sweep, chase, pulse. LLMs select templates; they never invent them.
  (Not to be confused with the root `templates/` directory of documentation starters.)
- **Preset** — a named parameterization of a template.
- **BeatGrid** — the beat-aligned timing grid produced by audio rhythm analysis.
- **Categorical planning** — LLM reasons in semantic categories (intensity:
  WHISPER/SOFT/MED/STRONG/PEAK; duration: HIT/BURST/PHRASE/EXTENDED/SECTION) which the
  renderer resolves to precise values.
- **ChoreographyPlan** — the structured Pydantic plan the planner agent produces
  (template + preset per song section).
- **Judge** — the LLM agent scoring plans 0–10; ≥ 7.0 approves.
- **Prompt pack** — a versioned set of Jinja2 templates (system/user/developer) plus
  config that defines one runtime agent's prompting (`packages/twinklr/core/**/prompts/`).
- **FE (feature engineering) pipeline** — incremental corpus analysis of xLights sequence
  packs producing style profiles and recipes; backed by the SQLite **feature store**.
- **Recipe** — a reusable choreography pattern mined from the corpus and promoted for use
  in generation.
- **Viseme** — mouth-shape category mapped from phonemes, used for singing-face effects.
