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
  timings. The moving-head renderer reads only this, never `dmx_mapping`. A wheel or
  shutter state may carry a **meaning tag** (`hex`, `pattern`, `strobe`): what it shows,
  for the planner's colour, gobo and strobe choices, or `offer: false` when it has
  none; never defaulted. Tagged states with a known settle make up the **rig offer**
  (what the planner is told the rig can show); a section's colour and gobo, and its
  colour, gobo and strobe events, play them.
- **Rig offer** — what the pre-planning gate tells the planner a rig can show of its
  song intent: each colour (faithfully, approximately, on some heads, not at all), each
  section's palette roles on the wheel, gobos, strobe speeds, hit, whether the heads can
  go dark and how fast they can flash (what each strobe and the pulse play at the
  song's tempo), wheel change time, and per template its dark phases and the states its
  overlay masks cannot reach
  (`TemplateAdmission.offer`, `sequencer/moving_heads/song_intent.py`).
- **Template** — a moving-head choreography unit, a JSON `TemplateDoc` whose steps state
  motion, dimmer or shutter pulse, wheel states and phase spread across the heads. The
  catalog's seven **families** live in `catalog/templates/moving_heads/`. LLMs select
  templates; they never invent them. (Not to be confused with the root `templates/`
  directory of documentation starters, or the display's recipe templates.)
- **Preset** — a named variant of a template that patches some of its steps (the
  catalog's ladder variants are `narrow` and `slow`; its variation variants `wide`,
  `fast` and their reach+rate combinations are offered but never a fallback).
- **Gate** (`render_preflight`) — the pre-planning check that dry-compiles every offered
  template and preset on the rig over the song and admits each family through its first
  passing variant, its **effective variant**.
- **BeatGrid** — the beat-aligned timing grid produced by audio rhythm analysis.
- **Categorical planning** — LLM reasons in semantic categories (display intensity:
  WHISPER/SOFT/MED/STRONG/PEAK; moving-head intensity: SLOW/SMOOTH/FAST/DRAMATIC/INTENSE;
  duration: HIT/BURST/PHRASE/EXTENDED/SECTION) which
  deterministic code resolves to precise values. The moving-head renderer plays DRAMATIC
  and INTENSE as a beat-locked dimmer pulse and the other levels as authored
  ([user guide](../docs/user-guide.md#how-a-sections-intensity-reaches-the-lights)).
- **ChoreographyPlan** — the structured Pydantic plan the moving-head planner produces:
  per song section, 1-3 parts (template + preset over bars) and the section's **song
  intent** (intensity, colour, gobo, timed events tied to lyric moment cues, motif
  variation, density, entry/exit transitions; an intensity, colour or gobo of
  `as_authored` keeps the template's own look and needs a reason), and per part its
  modifiers. Everything but density renders; density is a known regression being fixed.
- **Plan repair** — deterministic normalisation that drops or adjusts one planned item
  the song cannot hold (an unknown cue is dropped; an event outside its section is moved
  into it) instead of refusing the plan, keeping as much of it as the song allows; recorded in the plan's `repairs`, the trace's `plan_repairs` and the
  next refinement prompt.
- **Judge** — the LLM agent scoring plans 0–10; the bar comes from
  `agent.success_threshold` (configured 0–100, converted once to the planners' 0–10).
- **Prompt pack** — a versioned set of Jinja2 templates (system/user/developer) plus
  config that defines one runtime agent's prompting (`packages/twinklr/core/**/prompts/`).
- **FE (feature engineering) pipeline** — incremental corpus analysis of xLights sequence
  packs producing style profiles and recipes; backed by the SQLite **feature store**.
- **Recipe** — a reusable choreography pattern mined from the corpus and promoted for use
  in generation.
- **Viseme** — mouth-shape category mapped from phonemes, used for singing-face effects.
