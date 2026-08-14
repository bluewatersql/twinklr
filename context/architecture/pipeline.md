---
type: context
area: architecture
updated: 2026-08-14
---

# Pipeline Architecture

Four stages; 1 and 4 are fully deterministic, 2 and 3 use LLMs:

```
Audio File (.mp3)
     │
     ▼
1. Audio Analysis (deterministic)      tempo, beats, energy, sections, lyrics, phonemes
2. Audio Profiling (LLM)               musical interpretation, creative guidance, mood arc
3. Multi-Agent Planning (LLM)          planner → validator → judge iterative refinement
4. Rendering & Compilation (det.)      templates → curves → DMX values → fixture segments
     │
     ▼
Delivery: fresh .xsq + .xtiming tracks + .xmap mapping hint
```

## Subsystem map (`packages/twinklr/core/`)

| Subsystem | Path | Role |
|---|---|---|
| Audio analysis | `audio/` | rhythm, energy, structure, harmonic, lyrics, phonemes |
| Agents | `agents/` | orchestration: audio/lyrics profiling, sequencer planners, judge, providers |
| Sequencer | `sequencer/` | moving-heads template compiler & DMX export; display effects; template registry |
| Curves | `curves/` | native + custom curve generation |
| Pipeline | `pipeline/` | declarative stage framework; fail-fast policy, stage caching |
| Feature engineering | `feature_engineering/`, `feature_store/` | corpus mining → profiles, recipes (SQLite store) |
| Formats | `formats/xlights/` | `.xsq`/`.xtiming`/`.xmap` writers; the `.xsq` reader is analysis-only (P1P-T11) |
| Config | `config/` | Pydantic app/job/fixture config models |
| API clients | `api/` | HTTP (sync+async), OpenAI LLM client, AcoustID/MusicBrainz |
| Caching | `caching/` | FSCache (async), sync variants, null cache |

The CLI package (`packages/twinklr/cli/`) wires the end-to-end `twinklr run` workflow.

## Execution semantics

- **Fail-fast**: non-judge stage failures abort the run; no partial render output.
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
