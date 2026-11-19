---
type: context
area: architecture
updated: 2026-11-17
---

# Pipeline Architecture

Four stages; 1 and 4 are fully deterministic, 2 and 3 use LLMs:

```
Audio File (.mp3)
     │
     ▼
1. Audio Analysis (deterministic)      tempo, beats, energy, sections, lyrics, phonemes
2. Audio Profiling (LLM)               musical interpretation, creative guidance, mood arc
3. Multi-Agent Planning (LLM)          one macro → MH + display planning branches
4. Rendering & Compilation (det.)      shared BeatGrid → coordinated effects → one XSequence
     │
     ▼
Delivery: fresh .xsq + .xtiming tracks + .xmap mapping hint
```

## Subsystem map (`packages/twinklr/core/`)

| Subsystem | Path | Role |
|---|---|---|
| Audio analysis | `audio/` | rhythm, energy, structure, harmonic, lyrics, phonemes |
| Agents | `agents/` | orchestration: audio/lyrics profiling, sequencer planners, judge, providers |
| Sequencer | `sequencer/` | moving-head template registry, compiler, frame encoder and DMX export; display effects |
| Curves | `curves/` | native + custom curve generation |
| Pipeline | `pipeline/` | declarative stage framework; fail-fast policy, stage caching |
| Feature engineering | `feature_engineering/`, `feature_store/` | corpus mining → profiles, recipes (SQLite store) |
| Formats | `formats/xlights/` | `.xsq`/`.xtiming`/`.xmap` writers; the `.xsq` reader is analysis-only (P1P-T11) |
| Config | `config/` | Pydantic app/job/fixture config models |
| API clients | `api/` | HTTP (sync+async), OpenAI LLM client, AcoustID/MusicBrainz |
| Caching | `caching/` | FSCache (async), sync variants, null cache |

The CLI package (`packages/twinklr/cli/`) exposes branch-only `twinklr run` / `twinklr
display` workflows and the additive `twinklr show` convergence workflow. The combined
pipeline executes the common audio/profile/lyrics/macro prefix once, then joins the MH
and display branches at one in-memory render barrier. The binding ownership, focal,
palette, call/response, and catalog policy is recorded in the
[coordinated-show decision](../../memories/decisions/coordinated-show-contract.md).
For sequenced and ripple looks, the render advances through the macro's assigned
lead and support teams on detected beats. A zone or split takes one step as a
team, and short sections share beats between teams when needed. Ripple overlaps
the first half of each new step with its predecessor. The house foundation and
the other groups retain their planned coverage and focal-role brightness.

## Execution semantics

- **Fail-fast**: non-judge stage failures abort the run; no partial render output.
- **Pre-planning gate**: every moving-head pipeline (`run`, `show`, `inject`,
  `regenerate`) runs `render_preflight` right after `audio`, before any planner. It
  refuses a rig or song the renderer cannot render and fixes the templates the planner
  is offered, so a refusal costs no LLM request.
- **Restartability**: successful-stage results are cached and reused on rerun.
- **Store-driven FE**: the feature-engineering pipeline is incremental — already-processed
  sequences are skipped ([Pipeline Guide](../../docs/pipeline_guide.md)).
- **One timing/structure source**: audio configuration selects independent rhythm and
  structure producers, whose normalized `beats_s`, `bars_s`, and section output feed
  every downstream consumer through the unchanged `BeatGrid`. `dsp` is the default;
  model-backed selections are explicit optional dependencies and fail loudly when
  their local runtime/weights are unavailable.

## Deep reference

- [docs/developer-guide.md](../../docs/developer-guide.md) — repository structure and workflows
- [docs/pipeline_guide.md](../../docs/pipeline_guide.md) — FE pipeline, feature store, recipes
- [docs/feature_engineering/index.md](../../docs/feature_engineering/index.md) — narrative series
