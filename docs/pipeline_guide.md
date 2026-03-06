# Twinklr Pipeline Guide

## Overview

Twinklr's Feature Engineering (FE) system analyses a corpus of xLights
sequence packs to discover reusable choreography patterns, build
style profiles, and produce adapter payloads that the AI sequencer
consumes at generation time.

The pipeline is **store-driven and incremental**: a SQLite feature store
tracks every profiled sequence and its FE processing status. Running
the pipeline twice in a row skips all work. Adding one new vendor
package profiles and feature-engineers only that package.

This guide covers:

1. [Quick start — unified pipeline](#1-quick-start--unified-pipeline)
2. [What the FE pipeline does](#2-what-the-fe-pipeline-does)
3. [Running the pipeline](#3-running-the-pipeline)
4. [Feature Store (SQLite)](#4-feature-store-sqlite)
5. [Recipe pipeline](#5-recipe-pipeline)
6. [Template & taxonomy flow](#6-template--taxonomy-flow)
7. [Unified Pipeline architecture](#7-unified-pipeline-architecture)
8. [Running the sequencer pipeline](#8-running-the-sequencer-pipeline)
9. [Configuration reference](#9-configuration-reference)
10. [Resetting & clean runs](#10-resetting--clean-runs)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Quick Start — Unified Pipeline

The recommended way to run the full workflow is a single command:

```bash
# Full run with defaults (zero arguments required)
uv run python scripts/build/build_pipeline.py
```

This discovers vendor packages, profiles them, runs feature engineering,
and prints a summary. State is persisted in a SQLite feature store so
subsequent runs skip already-processed sequences.

```bash
# Second run — skips everything (no changes detected)
uv run python scripts/build/build_pipeline.py

# Add a new package, third run — processes only the new one
cp new_package.zip data/vendor_sequences/
uv run python scripts/build/build_pipeline.py

# Force full reprocessing from scratch
uv run python scripts/build/build_pipeline.py --force
```

### Pipeline Steps

| Step | What Happens |
|------|-------------|
| **Discover** | Finds `*.zip` and `*.xsqz` packages under `data/vendor_sequences` |
| **Profile** | Runs `SequencePackProfiler` on each package; SHA-based skip logic avoids re-profiling unchanged archives. Registers each profile in the feature store |
| **Feature Engineer** | Builds a unified corpus, then runs `FeatureEngineeringPipeline` with store-driven incremental processing. Profiles with `fe_status=complete` are loaded from cache; only `pending` profiles are processed |
| **Report** | Prints summary of processed sequences, output paths, and store location |

### Default Paths

| Setting | Default |
|---------|---------|
| Vendor packages | `data/vendor_sequences` |
| Profile output | `data/profiles` |
| FE output | `data/features/feature_engineering` |
| Feature store DB | `data/features/twinklr.db` |

### CLI Reference

```
usage: build_pipeline.py [-h]
    [--feature-store-db PATH]
    [--feature-store-backend {sqlite,null}]
    [--vendor-dir PATH]
    [--profiles-dir PATH]
    [--output-dir PATH]
    [--force]
    [--skip-profiling]
    [--skip-audio]
    [--quality-max-unknown-effect-family-ratio FLOAT]
    [--quality-max-unknown-motion-ratio FLOAT]
    [--quality-max-single-unknown-effect-type-ratio FLOAT]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--feature-store-db` | SQLite feature store path | `data/features/twinklr.db` |
| `--feature-store-backend` | Feature store backend | `sqlite` |
| `--vendor-dir` | Root dir for `*.zip`/`*.xsqz` packages | `data/vendor_sequences` |
| `--profiles-dir` | Output dir for profiling artifacts | `data/profiles` |
| `--output-dir` | Output root for FE artifacts | `data/features/feature_engineering` |
| `--force` | Delete store DB and re-profile/re-run FE from scratch | `False` |
| `--skip-profiling` | Skip profiling; use existing profile artifacts only | `False` |
| `--skip-audio` | Skip audio analysis in the FE pipeline | `False` |
| `--quality-max-unknown-effect-family-ratio` | Max unknown effect-family ratio | `0.02` |
| `--quality-max-unknown-motion-ratio` | Max unknown motion-class ratio | `0.02` |
| `--quality-max-single-unknown-effect-type-ratio` | Max ratio for any one unknown effect type | `0.01` |

---

## 2. What the FE Pipeline Does

The FE pipeline reads pre-profiled sequence packs and executes two
levels of analysis:

### Per-Profile Stages

Each sequence pack is processed independently:

| Stage | What It Produces | Flag |
|---|---|---|
| **Audio Discovery** | Locates the audio file for the sequence | (always on) |
| **Temporal Alignment** | Aligns effect events to beats/bars | `enable_alignment` |
| **Phrase Encoding** | Groups events into `EffectPhrase` objects | `enable_phrase_encoding` |
| **Taxonomy Classification** | Classifies phrases (effect_family, motion_class, etc.) | `enable_taxonomy` |
| **Target Role Assignment** | Assigns semantic roles to display targets | `enable_target_roles` |
| **Stack Detection** | Detects layered effect stacks | `enable_stack_detection` |

### Corpus-Aggregate Stages

After all profiles are processed, corpus-wide analysis runs:

| Stage | What It Produces | Flag |
|---|---|---|
| **Template Mining** | Discovers reusable `MinedTemplate` patterns | `enable_template_mining` |
| **Transition Modeling** | Models how templates transition between each other | `enable_transition_modeling` |
| **Motif Mining** | Finds recurring multi-template motifs | `enable_v2_motif_mining` |
| **Clustering** | Groups similar templates (DBSCAN on embeddings) | `enable_v2_clustering` |
| **Learned Taxonomy V2** | Trains and evaluates an improved taxonomy model | `enable_v2_learned_taxonomy` |
| **ANN Retrieval** | Builds a sqlite-vec approximate nearest-neighbour index | `enable_v2_ann_retrieval` |
| **Layering Features** | Extracts multi-layer density and depth patterns | `enable_layering_features` |
| **Color Narrative** | Discovers colour usage patterns across sections | `enable_color_narrative` |
| **Color Arc** | Builds palette library and section-to-palette assignments | `enable_color_arc` |
| **Propensity** | Computes effect-family usage affinities | `enable_propensity` |
| **Style Fingerprint** | Creates a creator style profile (timing, colour, layering) | `enable_style_fingerprint` |
| **Quality Gates** | Validates coverage, confidence, and unknown-type ratios | `enable_quality_gates` |
| **Recipe Promotion** | Promotes high-quality mined templates into `EffectRecipe` objects | `enable_recipe_promotion` |
| **Adapter Contracts** | Builds payload files consumed by the sequencer agent | `enable_v2_adapter_contracts` |

### Output Artifacts

After a corpus run, the output directory contains:

```
data/features/feature_engineering/
├── feature_store_manifest.json   # Inventory of all produced artifacts
├── effect_phrases.json           # Per-profile phrase data
├── phrase_taxonomy.json          # Taxonomy classifications
├── target_roles.json             # Target role assignments
├── template_catalog.json         # Mined templates
├── transition_graph.json         # Template transition model
├── motif_catalog.json            # Multi-template motifs
├── cluster_catalog.json          # Template clusters
├── retrieval_index.json          # ANN search index
├── layering_features.json        # Layering depth/density
├── color_narrative.json          # Colour usage patterns (section-level dominant colour/contrast)
├── color_palette_library.json    # Corpus-discovered palette clusters (per-song)
├── color_arc.json                # Palette library + section assignments
├── propensity_index.json         # Effect-family affinities
├── style_fingerprint.json        # Creator style profile
├── vocabulary_extensions.json    # Compound motion/energy terms mined from corpus
├── quality_report.json           # Quality gate results
├── recipe_catalog.json           # Promoted recipes
└── adapter_payloads/             # Sequencer adapter files
    ├── macro_adapter.json
    └── group_adapter.json
```

---

## 3. Running the Pipeline

### Prerequisites

- Python 3.12+
- `uv` package manager
- Project dependencies installed: `uv sync`

### Unified Pipeline (Recommended)

See [Section 1](#1-quick-start--unified-pipeline) for the single-command
workflow. This is the recommended approach for all use cases.

### Individual Scripts (Advanced)

For advanced use cases, you can run the individual steps separately:

#### Profiling Only

```bash
# Profile all vendor packages
uv run python scripts/demo_profiling.py

# Profile a specific package
uv run python scripts/demo_profiling.py \
  --input data/vendor_sequences/example1.zip \
  --output-dir data/profiles/example1

# With feature store persistence
uv run python scripts/demo_profiling.py \
  --feature-store-db data/features/twinklr.db
```

The profiler uses SHA-based skip logic: if the zip's SHA-256 matches an
existing profile in the store (and the profile directory exists on disk),
profiling is skipped and the cached profile is returned.

#### Corpus Build Only

> **Note**: The unified pipeline handles corpus building internally.
> Use this script only for standalone corpus builds.

```bash
uv run python scripts/build/build_profile_corpus.py
```

#### Feature Engineering Only

> **Note**: The unified pipeline handles profiling and corpus building
> before FE. Use this script when starting from an existing corpus.

```bash
uv run python scripts/build/build_feature_engineering.py

# Skip audio analysis (faster)
uv run python scripts/build/build_feature_engineering.py \
  --skip-audio-analysis
```

#### FE Demo Report

```bash
uv run python scripts/demo_feature_engineering.py \
  --corpus-dir data/profiles/corpus/v0_effectdb_structured_1 \
  --output-dir data/features/demo_feature_engineering
```

### Python API

#### Store-Driven Incremental Run (Recommended)

```python
from pathlib import Path
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)
from twinklr.core.feature_store.models import FeatureStoreConfig

options = FeatureEngineeringPipelineOptions(
    feature_store_config=FeatureStoreConfig(
        backend="sqlite",
        db_path=Path("output/feature_store.db"),
    ),
)

pipeline = FeatureEngineeringPipeline(options=options)

# run() queries the store for pending profiles, processes them,
# and loads cached bundles for already-complete profiles.
# Manages its own store lifecycle (initialize/close).
bundles = pipeline.run(Path("output/features"))

print(f"Processed {len(bundles)} sequences")
```

#### Force Reprocessing

```python
# Reset all profiles to pending and reprocess everything
bundles = pipeline.run(Path("output/features"), force=True)
```

#### Legacy Corpus-Based Run

```python
# run_corpus() reads sequence_index.jsonl and processes profiles
# listed there. Manages its own store lifecycle.
bundles = pipeline.run_corpus(
    corpus_dir=Path("data/profiles/corpus/v0_effectdb_structured_1"),
    output_root=Path("output/corpus"),
)
```

#### Single Profile

```python
# run_profile() processes one profile directory.
# Caller must manage store lifecycle externally.
bundle = pipeline.run_profile(
    profile_dir=Path("data/profiles/my_pack"),
    output_dir=Path("output/single"),
)
```

---

## 4. Feature Store (SQLite)

The feature store provides persistent, queryable storage for pipeline
state and FE artifacts. It tracks profiled sequences, their processing
status, and all derived features.

### Backends

| Backend | Use Case | Config |
|---|---|---|
| `null` | Default — no persistence beyond JSON files | No config needed |
| `sqlite` | Persistent, queryable store for development and production | `FeatureStoreConfig(backend="sqlite", db_path=...)` |

### Schema

The SQLite store auto-bootstraps its schema on first `initialize()`.
Tables include:

| Table | Purpose |
|-------|---------|
| `profiles` | Tracks profiled sequences and FE processing status |
| `phrases` | Effect phrase records |
| `taxonomy` | Phrase taxonomy classifications |
| `templates` | Mined template patterns |
| `stacks` | Effect stack records |
| `transitions` | Template transition graph edges |
| `recipes` | Promoted effect recipes |
| `propensity` | Effect-family usage affinities |
| `corpus_metadata` | Corpus-level metadata blobs |
| `reference_data` | Versioned reference datasets |

Schema definitions live in `packages/twinklr/core/feature_store/schemas/`.

### Profile Tracking

The `profiles` table is the backbone of incremental processing:

```
profiles
├── profile_id          TEXT PRIMARY KEY  -- {package_id}/{sequence_file_id}
├── package_id          TEXT NOT NULL
├── sequence_file_id    TEXT NOT NULL
├── profile_path        TEXT NOT NULL     -- filesystem path to profile JSON
├── zip_sha256          TEXT              -- SHA-256 of source archive
├── sequence_sha256     TEXT              -- SHA-256 of sequence content
├── song                TEXT
├── artist              TEXT
├── duration_ms         INTEGER
├── effect_total_events INTEGER
├── fe_status           TEXT NOT NULL DEFAULT 'pending'  -- pending|complete|error
├── fe_error            TEXT
├── profiled_at         TEXT NOT NULL
└── fe_completed_at     TEXT
```

**Status flow**: `pending` → `complete` (on success) or `error` (on failure).

The profiler registers profiles on successful profiling. The FE pipeline
queries for `pending` profiles to process and marks them `complete` or
`error` after processing. On `--force`, all profiles are reset to
`pending`.

### Querying the Store

```python
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig

config = FeatureStoreConfig(backend="sqlite", db_path=Path("output/feature_store.db"))
store = create_feature_store(config)
store.initialize()

try:
    # Query profiles by FE status
    pending = store.query_profiles(fe_status="pending")
    complete = store.query_profiles(fe_status="complete")

    # Find a profile by sequence SHA
    profile = store.query_profile_by_sha("abc123...")

    # Query phrases by target
    phrases = store.query_phrases_by_target(
        package_id="my_pack",
        sequence_file_id="my_sequence",
        target_name="Megatree",
    )

    # Query templates
    templates = store.query_templates()

    # Get corpus statistics (includes profile_count)
    stats = store.get_corpus_stats()
    print(f"Profiles: {stats.profile_count}")
    print(f"Phrases: {stats.phrase_count}, Templates: {stats.template_count}")
finally:
    store.close()
```

### Lifecycle

The store follows a strict lifecycle:

1. `initialize()` — Opens the database, bootstraps schema if needed
2. `upsert_*()` — Called by the pipeline during processing
3. `query_*()` / `mark_*()` — Read/update data
4. `close()` — Always called, even on exceptions (finally block)

Entry points (`run()` and `run_corpus()`) manage their own lifecycle
internally. Only `run_profile()` requires the caller to manage it.

---

## 5. Recipe Pipeline

The recipe pipeline converts mined templates into renderable recipes:

```
MinedTemplate → PromotionPipeline → RecipeCatalog → RecipeRenderer
```

### Promotion

```python
from twinklr.core.feature_engineering.promotion import PromotionPipeline

result = PromotionPipeline().run(
    candidates=mined_templates,
    min_support=5,          # Minimum observation count
    min_stability=0.3,      # Minimum cross-pack stability
    clusters=cluster_list,  # Optional: dedup within clusters
)

for recipe in result.promoted_recipes:
    print(f"  {recipe.recipe_id}: {recipe.name}")
```

### Catalog Assembly

```python
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog

catalog = RecipeCatalog.merge(
    builtins=builtin_recipes,
    promoted=result.promoted_recipes,
)

# Query by lane
base_recipes = catalog.list_by_lane(LaneKind.BASE)
rhythm_recipes = catalog.list_by_lane(LaneKind.RHYTHM)
```

### Rendering

```python
from twinklr.core.sequencer.display.recipe_renderer import RecipeRenderer, RenderEnvironment

env = RenderEnvironment(
    energy=0.8,
    density=0.6,
    palette_colors={"primary": "#FF0000", "accent": "#00FF00"},
)

result = RecipeRenderer().render(recipe, env)
for layer in result.layers:
    print(f"  Layer {layer.layer_name}: {layer.effect_type} → {layer.resolved_color}")
```

### Style-Weighted Retrieval

```python
from twinklr.core.feature_engineering.style_transfer import StyleWeightedRetrieval

retrieval = StyleWeightedRetrieval()
scored = retrieval.rank(catalog, style_fingerprint)

for entry in scored[:5]:
    print(f"  {entry.recipe.recipe_id}: score={entry.score:.3f}")
```

---

## 6. Template & Taxonomy Flow

This section describes how templates and taxonomy data are injected into
the planner's LLM prompts at generation time, and how FE-discovered
taxonomy relates to the planner's vocabulary.

### Template Sources

Two template sources merge at planner time:

| Source | Location | Loaded By |
|--------|----------|-----------|
| **Built-in templates** | `data/templates/index.json` + `builtins/*.json` | `TemplateStore.from_directory()` |
| **FE-mined recipes** | `data/features/feature_engineering/recipe_catalog.json` | `load_fe_artifacts()` → `RecipeCatalog.from_store()` |

Built-in templates are hand-authored `EffectRecipe` definitions. FE-mined
templates are discovered by `TemplateMiner` from corpus phrases, then
promoted into recipes via `PromotionPipeline` (see [Section 5](#5-recipe-pipeline)).
Promoted recipes are one of several FE outputs that feed into the planner — see
[FE Artifact Planner Consumption](#what-fe-artifacts-feed-the-planner) below.

### Taxonomy Injection

Taxonomy enums are defined as Python enums in
`packages/twinklr/core/sequencer/vocabulary/` (`LaneKind`,
`CoordinationMode`, `IntensityLevel`, etc.).

`inject_taxonomy()` in `agents/taxonomy_utils.py` is called by
`AsyncAgentRunner.run()` before every LLM call. It adds
`variables["taxonomy"]` containing all enum value lists to the Jinja2
template context. The planner's `developer.j2` prompt renders these
as constrained value sets.

**Important:** `taxonomy_utils.py` reads only from Python enums and
theming registries. It does not load anything from FE output files.

### What FE Artifacts Feed the Planner

All `FEArtifactBundle` fields are loaded once per pipeline run by
`load_fe_artifacts()` and injected into every section's planning context
via `GroupPlannerStage._extract_fe_fields()`. The table below shows the
current consumption status of each artifact:

| FE Artifact | Produced By | Planner Usage |
|-------------|-------------|---------------|
| `recipe_catalog.json` | `PromotionPipeline` | **Yes** — merged into `RecipeCatalog`; rendered in `developer.j2` |
| `color_arc.json` | `ColorArcBuilder` | **Yes** — section assignment injected as `color_arc`; nearest `arc_keyframe` injected as `arc_keyframe` |
| `color_palette_library.json` | `ColorArcBuilder` | **Yes** — consumed by `ColorArcExtractor` to select corpus-derived palettes |
| `color_narrative.json` | `ColorNarrativeBuilder` | **Yes** — section-matched row injected as `color_narrative_row` |
| `propensity_index.json` | `PropensityMiner` | **Yes** — injected as `propensity_hints` (song-level) |
| `style_fingerprint.json` | `StyleFingerprintBuilder` | **Yes** — all sub-fields injected as `style_constraints` (timing, transition, layering, recipes, colour tendencies) |
| `vocabulary_extensions.json` | `VocabularyExpander` | **Yes** — compound motion/energy terms injected into taxonomy dict for `developer.j2` |
| `transition_graph.json` | `TransitionModeler` | Loaded into `FEArtifactBundle`; available but not yet forwarded to prompt |
| `taxonomy_model_bundle.json` | `LearnedTaxonomyTrainer` | FE-internal use only |
| `effect_metadata.json` | `EffectMetadataProfileBuilder` | Written to disk; not loaded by planner |
| `phrase_taxonomy.json` | Per-profile taxonomy stage | FE-internal use only |

The planner's base taxonomy (enum value lists rendered in `developer.j2`)
is controlled by Python enums in `sequencer/vocabulary/` and is enriched
at runtime with corpus-derived compound terms when `vocabulary_extensions`
is present. `taxonomy_utils.py` reads only from Python enums; the compound
term injection happens in `context_shaping.py`.

### Context Shaping

`GroupPlannerStage` builds a `SectionPlanningContext` for each song section
via `_build_section_context()`:

1. **Template filtering** — `filter_templates_by_intent()` filters by
   energy, motion density, and motif IDs
2. **Simplification** — Templates are reduced to
   `{template_id, name, compatible_lanes, affinity_tags, tags}`
3. **Recipe shaping** — Recipes are rendered as
   `{recipe_id, name, composition, layers, model_affinities}`
4. **FE context** — `_extract_fe_fields(section_id)` extracts six fields
   from `FEArtifactBundle` into the section context:
   - `color_arc` — section colour assignment (palette, spatial mapping, shift timing, contrast target)
   - `arc_keyframe` — nearest arc keyframe to this section's song position (temperature, saturation, contrast)
   - `color_narrative_row` — section-matched narrative row (dominant colour class, contrast shift, hue movement)
   - `propensity_hints` — full `PropensityIndex` dump (song-level effect-family affinities)
   - `style_constraints` — all `StyleFingerprint` sub-fields (timing, transition, layering, recipe preferences, colour tendencies)
   - `vocabulary_extensions` — `VocabularyExtensions` object held as a live Pydantic model for `shape_planner_context()` to consume

`shape_planner_context()` then transforms the `SectionPlanningContext` into
a flat prompt variables dict: it enriches the base taxonomy dict with
compound motion/energy terms when `vocabulary_extensions` is present, and
passes `color_arc`, `propensity_hints`, and `style_constraints` through
directly. `color_narrative_row` and `arc_keyframe` are also available on
the context and rendered by `user.j2`.

### Prompt Injection Points

| Prompt | What's Injected |
|--------|-----------------|
| `user.j2` | Template catalog entries by lane (BASE, RHYTHM, ACCENT); Feature Engineering Context block: color arc (palette, spatial mapping, shift timing), propensity hints (top affinities), style constraints (timing, transition, layering, recipe preferences, colour tendencies), color narrative (dominant class, contrast shift, hue movement), arc position (temperature, saturation, contrast) |
| `developer.j2` | Taxonomy enum values; optional compound motion/energy term vocabulary (corpus-derived, when `vocabulary_extensions` present); recipe catalog with composition and layer details |

### Key Files

| Purpose | File |
|---------|------|
| Built-in template loading | `sequencer/templates/group/store.py` |
| Template catalog build | `sequencer/templates/group/catalog.py` |
| FE artifact loading | `feature_engineering/loader.py` |
| FE artifact bundle | `feature_engineering/loader.py` → `FEArtifactBundle` |
| Recipe catalog merge | `sequencer/templates/group/recipe_catalog.py` |
| Template mining | `feature_engineering/templates/miner.py` |
| Taxonomy injection | `agents/taxonomy_utils.py` |
| Context shaping | `agents/sequencer/group_planner/context_shaping.py` |
| Section context build | `agents/sequencer/group_planner/stage.py` |

---

## 7. Unified Pipeline Architecture

Both the sequencer and FE pipelines use a declarative DAG execution model
built on three core types:

### Core Types

| Type | Role |
|---|---|
| `PipelineDefinition` | Declares stages, their dependencies, and execution patterns |
| `StageDefinition` | Configures a single stage (ID, implementation, inputs, pattern) |
| `PipelineExecutor` | Resolves dependencies, builds execution waves, runs stages |
| `PipelineContext` | Shared state, metrics, and dependency injection across stages |
| `PipelineResult` | Immutable result with all stage outputs and timing metadata |
| `StageResult[T]` | Per-stage result (success/failure/skipped with typed output) |

### Execution Patterns

| Pattern | Behaviour |
|---|---|
| `SEQUENTIAL` | Execute once with single input (default) |
| `PARALLEL` | Execute alongside other stages sharing the same dependencies |
| `FAN_OUT` | Execute N times in parallel (one per input item) |
| `CONDITIONAL` | Execute only if `condition(context)` returns `True` |

### How It Works

1. **Validation** — `PipelineDefinition.validate_pipeline()` checks for
   cycles, missing dependencies, and duplicate IDs.

2. **Topological Sort** — The executor sorts stages into waves. Stages
   with no pending dependencies execute in parallel.

3. **Wave Execution** — Each wave runs via `asyncio.gather()`. Results
   are stored in context and fed as inputs to downstream stages.

4. **State Sharing** — Stages communicate via `PipelineContext.state`
   (e.g. `context.set_state("has_lyrics", True)`).

5. **Fail-Fast** — If a critical stage fails, the pipeline stops
   immediately. Non-critical stages (like lyrics) can fail without
   halting the pipeline.

### DAG Diagram — Moving Heads Pipeline

```
audio ──┬──► profile ──┬──► macro ──► moving_heads ──► render
        │              │
        └──► lyrics ───┘
             (conditional)
```

### Building a Pipeline

```python
from twinklr.core.pipeline import PipelineDefinition, StageDefinition, ExecutionPattern

pipeline = PipelineDefinition(
    name="my_pipeline",
    description="Custom pipeline",
    fail_fast=True,
    stages=[
        StageDefinition(id="audio", stage=AudioAnalysisStage()),
        StageDefinition(
            id="profile",
            stage=AudioProfileStage(),
            inputs=["audio"],
        ),
        StageDefinition(
            id="lyrics",
            stage=LyricsStage(),
            inputs=["audio"],
            pattern=ExecutionPattern.CONDITIONAL,
            condition=lambda ctx: ctx.get_state("has_lyrics", False),
        ),
        StageDefinition(
            id="macro",
            stage=MacroPlannerStage(display_groups=groups),
            inputs=["profile", "lyrics"],
        ),
    ],
)

errors = pipeline.validate_pipeline()
assert not errors, f"Validation failed: {errors}"
```

### Executing a Pipeline

```python
import asyncio
from twinklr.core.pipeline.executor import PipelineExecutor
from twinklr.core.pipeline.context import PipelineContext
from twinklr.core.session import TwinklrSession

session = TwinklrSession(app_config="config.json", job_config="job_config.json")
context = PipelineContext(session=session, output_dir=Path("output/"))

result = asyncio.run(
    PipelineExecutor().execute(pipeline, str(audio_path), context)
)

if result.success:
    plan = result.get_output("macro")
    print(f"Generated {len(plan)} macro sections")
else:
    print(f"Failed stages: {result.failed_stages}")
```

---

## 8. Running the Sequencer Pipeline

### CLI — Moving Heads

```bash
export OPENAI_API_KEY="sk-..."

uv run twinklr run \
  --audio path/to/song.mp3 \
  --xsq path/to/template.xsq \
  --config path/to/job_config.json \
  --app-config path/to/config.json \
  --out output/
```

### CLI Options

| Flag | Description | Default |
|---|---|---|
| `--audio` | Path to audio file (MP3/WAV) | (required) |
| `--xsq` | Path to xLights template `.xsq` file | (required) |
| `--config` | Path to job configuration JSON | (required) |
| `--app-config` | Path to app configuration JSON | `config.json` |
| `--out` | Output directory | `output/` |

### What Happens

1. **Audio Analysis** — Extracts tempo, beats, bars, energy, structure,
   harmonic content, and optionally lyrics.

2. **Audio Profile** — LLM generates musical analysis and creative
   guidance from the audio features.

3. **Lyrics** (conditional) — If lyrics are detected, the LLM analyses
   narrative themes and emotional arc.

4. **Macro Planning** — LLM creates a high-level choreography strategy:
   energy levels, density, and style per song section.

5. **Moving Head Planning** — The 5-stage agent loop (Plan → Validate →
   Judge → Iterate) generates a `ChoreographyPlan`:
   - **Plan**: LLM picks templates, presets, and timing per section
   - **Validate**: Heuristic checks (bar ranges, no overlaps, coverage)
   - **Judge**: LLM scores the plan (0-10) and provides feedback
   - **Iterate**: If score < threshold, planner revises with feedback

6. **Render** — Compiles the plan into DMX channel data and writes the
   `.xsq` output file.

### Demo Scripts

```bash
# Moving heads pipeline demo
uv run python scripts/demo_moving_heads_pipeline.py

# Sequencer pipeline demo
uv run python scripts/demo_sequencer_pipeline.py

# Recipe pipeline demo (phases 1, 2a, 2b, 2c, or all)
uv run python scripts/demo_recipe_pipeline.py --phase all
```

---

## 9. Configuration Reference

### App Config (`config.json`)

```json
{
  "llm_api_key": "$OPENAI_API_KEY",
  "llm_provider": "openai",
  "output_dir": "output",
  "cache_dir": ".cache",
  "audio_processing": {
    "hop_length": 512,
    "frame_length": 2048,
    "cache_enabled": true
  },
  "planning": {
    "max_beats": 1000,
    "max_sections": 20
  }
}
```

### Job Config (`job_config.json`)

```json
{
  "schema_version": "2.0",
  "fixture_config_path": "data/fixtures/my_fixtures.json",
  "agent": {
    "max_iterations": 3,
    "success_threshold": 7.0,
    "plan_agent": { "model": "gpt-4o", "temperature": 0.7 },
    "judge_agent": { "model": "gpt-4o", "temperature": 0.3 }
  },
  "pose_config": { "poses": {} },
  "planner_features": {
    "enable_shutter": true,
    "enable_color": true,
    "enable_gobo": false
  },
  "transitions": {
    "enabled": true,
    "default_duration_bars": 1,
    "default_mode": "crossfade"
  }
}
```

### FE Pipeline Options

All FE pipeline options are passed via `FeatureEngineeringPipelineOptions`.
Key options:

| Option | Type | Default | Description |
|---|---|---|---|
| `extracted_search_roots` | `tuple[Path, ...]` | `(Path("data/vendor_sequences"),)` | Where to find extracted audio |
| `feature_store_config` | `FeatureStoreConfig \| None` | `None` | Feature store config (null or sqlite) |
| `fail_fast` | `bool` | `True` | Stop on first profile error in `run()` |
| `enable_alignment` | `bool` | `True` | Temporal alignment stage |
| `enable_phrase_encoding` | `bool` | `True` | Phrase encoding stage |
| `enable_taxonomy` | `bool` | `True` | Taxonomy classification |
| `enable_target_roles` | `bool` | `True` | Target role assignment |
| `enable_stack_detection` | `bool` | `True` | Effect stack detection |
| `enable_template_mining` | `bool` | `True` | Template mining |
| `enable_color_arc` | `bool` | `True` | Colour arc extraction |
| `enable_propensity` | `bool` | `True` | Propensity mining |
| `enable_style_fingerprint` | `bool` | `True` | Style fingerprint |
| `enable_recipe_promotion` | `bool` | `True` | Recipe promotion |
| `enable_quality_gates` | `bool` | `True` | Quality gate validation |
| `enable_v2_motif_mining` | `bool` | `True` | Motif mining |
| `enable_v2_clustering` | `bool` | `True` | Template clustering |
| `enable_v2_learned_taxonomy` | `bool` | `True` | Learned taxonomy V2 |
| `enable_v2_ann_retrieval` | `bool` | `True` | ANN retrieval index |
| `enable_v2_adapter_contracts` | `bool` | `True` | Adapter contract generation |
| `recipe_promotion_min_support` | `int` | `5` | Min observations for promotion |
| `recipe_promotion_min_stability` | `float` | `0.3` | Min cross-pack stability |
| `quality_max_unknown_effect_family_ratio` | `float` | `0.02` | Max unknown effect-family ratio |
| `quality_max_unknown_motion_ratio` | `float` | `0.02` | Max unknown motion-class ratio |
| `quality_max_single_unknown_effect_type_ratio` | `float` | `0.01` | Max ratio for any one unknown effect type |

---

## 10. Resetting & Clean Runs

### What `--force` Does

The `--force` flag on `build_pipeline.py`:
1. Deletes the SQLite feature store DB (`data/features/twinklr.db`)
2. Re-profiles all vendor packages (ignores SHA-based skip logic)

It does **not** delete existing profile directories or FE output
artifacts. Old per-sequence directories remain on disk.

### Full Clean Reset

To completely reset all pipeline state and artifacts:

```bash
# 1. Clear application caches (audio analysis, step cache)
make clean-cache

# 2. Remove the feature store DB
rm -f data/features/twinklr.db

# 3. Remove all profiling output (forces re-profiling)
rm -rf data/profiles/*

# 4. Remove all FE output artifacts
rm -rf data/features/feature_engineering/*

# 5. Run the unified pipeline from scratch
uv run python scripts/build/build_pipeline.py --force
```

### Partial Resets

**Keep profiles, redo FE only:**

```bash
rm -f data/features/twinklr.db
rm -rf data/features/feature_engineering/*
uv run python scripts/build/build_pipeline.py --force --skip-profiling
```

**Reprocess FE via Python API (no disk cleanup):**

```python
pipeline = FeatureEngineeringPipeline(options=options)
bundles = pipeline.run(Path("output/features"), force=True)
```

This calls `reset_all_fe_status()` on the store, setting all profiles
back to `pending` without deleting any files.

### Makefile Targets

| Target | What It Cleans |
|--------|---------------|
| `make clean` | Python caches, build artifacts, test/coverage artifacts, editor temp files |
| `make clean-cache` | `data/audio_cache/*`, `.cache/*` |
| `make clean-all` | Both of the above |

None of these targets touch the feature store, profiles, or FE output.

### Data Directories

| Path | Contents | Safe to Delete? |
|------|----------|----------------|
| `data/vendor_sequences/` | Input vendor packages | No — source data |
| `data/profiles/` | Per-package profile artifacts + corpus | Yes — rebuilt by profiler |
| `data/profiles/corpus/` | Unified corpus (sequence index) | Yes — rebuilt from profiles |
| `data/features/twinklr.db` | SQLite feature store | Yes — rebuilt on next run |
| `data/features/feature_engineering/` | FE output artifacts | Yes — rebuilt by FE pipeline |
| `data/audio_cache/` | Cached audio analysis results | Yes — rebuilt on demand |
| `.cache/` | Step result cache | Yes — rebuilt on demand |

---

## 11. Troubleshooting

### Unified Pipeline

**Problem: "No vendor packages found"**
- Ensure `*.zip` or `*.xsqz` files exist under the `--vendor-dir` directory
  (default: `data/vendor_sequences`).

**Problem: Pipeline skips a package you expect it to process**
- The profiler uses SHA-based skip logic. If the zip SHA-256 matches a
  profile already in the store and the profile directory exists, it skips.
- Use `--force` to delete the store and reprofile everything.

**Problem: FE skips a sequence you expect it to process**
- Check the profile's `fe_status` in the store. Profiles marked `complete`
  are loaded from cache, not reprocessed.
- Use `--force` to reset all profiles to `pending`.

**Problem: "ERROR: No sequences in corpus"**
- The corpus `sequence_index.jsonl` is empty or missing. Ensure profiling
  ran successfully and profiles exist under `--profiles-dir`.

### FE Pipeline

**Problem: "No audio file found for profile"**
- The audio discovery service searches `extracted_search_roots` and
  `music_repo_roots` for a file matching the sequence's `media_file`.
- Ensure the audio file exists in one of these directories.
- Set `audio_required=False` (default) to skip profiles without audio.

**Problem: Empty phrases or taxonomy**
- Check that `enriched_effect_events.json` exists in the profile and
  contains at least one event.
- Verify that `enable_alignment` and `enable_phrase_encoding` are `True`.

**Problem: Feature store errors**
- Ensure the `db_path` directory exists (the store creates the file but
  not parent directories).
- Check schema version: the store auto-bootstraps on first run.

**Problem: Profile stuck in `error` status**
- Query `store.query_profiles(fe_status="error")` to find errored profiles.
- Check the `fe_error` field for the error message.
- Fix the underlying issue, then run with `--force` to reprocess.

### Unified DAG Pipeline

**Problem: "Pipeline validation failed: cycle detected"**
- Check `StageDefinition.inputs` for circular references.
- Use `pipeline.validate_pipeline()` to get specific error messages.

**Problem: Conditional stage not running**
- Verify the condition function reads the correct state key.
- Check that a preceding stage sets the state flag (e.g.
  `context.set_state("has_lyrics", True)` in the audio stage).

**Problem: Stage timeout**
- Increase `timeout_ms` on the `StageDefinition`.
- For LLM stages, check `AgentConfig.timeout_seconds` in the job config.

### Sequencer Pipeline

**Problem: "OPENAI_API_KEY not set"**
- Export the key: `export OPENAI_API_KEY="sk-..."`
- Or set it in your `config.json` under `llm_api_key`.

**Problem: Low judge scores (< 7.0)**
- Increase `max_iterations` in job config to give the planner more attempts.
- Lower `success_threshold` if the default 7.0 is too strict for your use case.
- Check the LLM logs for judge feedback to understand scoring rationale.

**Problem: Missing templates in plan**
- Verify the template JSON files exist in `data/templates/`.
- Call `load_builtin_templates()` before checking available template IDs.
- Ensure the template ID is in the `available_templates` list passed to
  `build_moving_heads_pipeline()`.

---

## Testing

### Running the Full Test Suite

```bash
make validate    # Runs ruff + mypy + pytest with coverage
```

### Running Specific Test Suites

```bash
# Feature store profiles tests
uv run pytest tests/unit/feature_store/test_profiles.py -v

# Profiler store integration tests
uv run pytest tests/unit/profiling/test_profiler_store.py -v

# FE incremental pipeline tests
uv run pytest tests/unit/feature_engineering/test_pipeline_incremental.py -v

# FE + unified pipeline E2E test
uv run pytest tests/integration/test_fe_unified_pipeline_e2e.py -v

# FE Phase 1 integration tests
uv run pytest tests/integration/feature_engineering/ -v

# Recipe pipeline E2E
uv run pytest tests/integration/test_recipe_end_to_end.py -v

# Feature store unit tests
uv run pytest tests/unit/feature_engineering/test_pipeline_with_store.py -v

# Pipeline executor unit tests
uv run pytest tests/unit/pipeline/ -v
```

### Test Structure

```
tests/
├── conftest.py                          # Shared fixtures
├── unit/
│   ├── feature_engineering/
│   │   ├── test_pipeline.py             # Core pipeline unit tests
│   │   ├── test_pipeline_with_store.py  # Feature store integration
│   │   └── test_pipeline_incremental.py # Store-driven incremental tests
│   ├── feature_store/
│   │   └── test_profiles.py             # Profile table + protocol tests
│   ├── profiling/
│   │   └── test_profiler_store.py       # Profiler SHA skip + registration
│   └── pipeline/                        # Pipeline executor tests
└── integration/
    ├── test_fe_unified_pipeline_e2e.py  # Full E2E
    ├── test_recipe_end_to_end.py        # Recipe lifecycle E2E
    └── feature_engineering/
        └── test_fe_phase1_pipeline.py   # Phase 1 artifact tests
```

---

## Directory Conventions

| Path | Contents |
|------|----------|
| `data/profiles/<profile_dir>` | Per-package profile artifacts |
| `data/profiles/corpus/<schema>` | Unified corpus |
| `data/features/<run_name>` | Feature outputs |
| `data/features/twinklr.db` | Feature store |
| `data/templates/` | Built-in template definitions |
| `data/vendor_sequences/` | Source vendor packages |

## Notes

- `_v0_check` and `*_smoke` directories are development/test artifacts and are not canonical run paths.
- If multiple entries share the same `sequence_sha256`, feature distributions can look duplicated across package IDs.
- The `run_corpus()` method is a legacy entry point that reads `sequence_index.jsonl`. Prefer `run()` for new workflows.
- `scripts/build/build_profile_corpus.py` and `twinklr.core.profiling.unify` are deprecated in favour of the unified pipeline.
