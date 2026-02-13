---
title: "Building an AI Choreographer for Christmas Light Shows"
description: "An 8-part blog series on building Twinklr — an LLM-powered choreography engine that turns music into coordinated moving head light shows for xLights."
tags: [ai, llm, python, christmas-lights, xlights, choreography, moving-heads, series-index]
---

![Twinklr](../assets/twinklr_logo_light.png)

# Building an AI Choreographer for Christmas Light Shows

An 8-part series covering the design, architecture, and hard-won lessons from building **Twinklr** — an AI system that listens to a Christmas song and produces a fully choreographed moving head light show for xLights. No manual keyframing. No DMX by hand. Just music in, synchronized lights out.

The series follows the full pipeline: from raw audio analysis through LLM-based planning to deterministic rendering, covering the architecture decisions, failure modes, and design pivots along the way.

---

## Series Contents

| Part | Title | Summary |
|:----:|-------|---------|
| 0 | [An LLM xLights Choreographer?](overview.md) | The problem space, why naive LLM approaches fail, and the architecture that makes it work — LLM plans intent, deterministic code implements it. |
| 1 | [Hearing the Music — Audio Analysis & Feature Extraction](audio_analysis.md) | Deterministic audio analysis: BeatGrid timing, seven feature domains, multi-scale energy, genre-aware section detection, and a 5-stage lyrics fallback pipeline. |
| 2 | [Making Sense of Sound — LLM-Based Audio & Lyric Profiling](audio_profiling.md) | Compressing ~100KB of features to ~10KB for the LLM. Context shaping, anti-generic prompting, and why audio and lyrics need separate agents. |
| 3 | [The Choreographer — Multi-Agent Planning System](multi_agent_planning.md) | The planner-judge loop: data-driven agent specs, heuristic validation before LLM evaluation, conversational refinement, and structured feedback. |
| 4 | [The Categorical Pivot](categorical_planning.md) | The most consequential design change — replacing numeric outputs with categorical vocabularies (`IntensityLevel`, `EffectDuration`, `PlanningTimeRef`) to eliminate 38% of judge failures. |
| 5 | [Prompt Engineering — Schema Injection, Taxonomy, and Anti-Patterns](prompt_engineering.md) | Prompt packs, Jinja2 templates, auto-injected Pydantic schemas, taxonomy injection, and the schema repair loop. Plus what didn't work. |
| 6 | [From Plan to Pixels — Rendering & Compilation](rendering_compilation.md) | Template anatomy, the compilation pipeline, phase offsets for chase effects, custom curve generation, per-channel transitions, and xLights export. |
| 7 | [Lessons Learned & What's Next](lessons_learned.md) | Retrospective: what worked, what surprised us, what we'd change, and the roadmap ahead. |

---

## Key Themes

- **Creative vs. Deterministic boundary** — The LLM handles creative judgment (which template, what intensity, how long); deterministic code handles implementation (curves, angles, DMX values).
- **Categorical over numeric** — LLMs excel at categorical selection and fail at spatial math and numeric precision. Design your interfaces accordingly.
- **Multi-agent iteration** — A planner-judge loop with structured feedback converges faster than single-shot generation.
- **Schema as contract** — Auto-injecting Pydantic schemas into prompts eliminates schema drift and silent failures.

---

[Back to Docs Home](../index.md)
