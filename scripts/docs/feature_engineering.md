# Feature Engineering

This document is the single source of truth for running profiling corpus build + feature engineering.

## 0) Unified Pipeline (Recommended)

The unified build pipeline runs the complete workflow in a single command:
discover vendor packages → profile → feature-engineer → report.

Script:
- `scripts/build/build_pipeline.py`

### Quick Start

```bash
# Full run with defaults (zero arguments required)
python scripts/build/build_pipeline.py
```

### Common Options

```bash
# Force full reprocessing (delete store, reprofile, re-run FE)
python scripts/build/build_pipeline.py --force

# Skip profiling (use existing profiles only)
python scripts/build/build_pipeline.py --skip-profiling

# Skip audio analysis (faster)
python scripts/build/build_pipeline.py --skip-audio
```

### How It Works

1. **Discover**: Finds `*.zip` and `*.xsqz` packages under `data/vendor_packages`
2. **Profile**: Runs `SequencePackProfiler` on each package (skips if profile already exists)
3. **Feature Engineer**: Builds unified corpus, then runs `FeatureEngineeringPipeline` with store-driven incremental processing
4. **Report**: Prints summary of processed sequences

State is tracked in a SQLite feature store (`data/features/twinklr.db` by default). Running the pipeline twice skips all work. Adding a new vendor package processes only that package.

### Default Paths

| Setting | Default |
|---------|---------|
| Vendor packages | `data/vendor_packages` |
| Profile output | `data/profiles` |
| FE output | `data/features/feature_engineering` |
| Feature store | `data/features/twinklr.db` |

## Canonical CLI Flow

**Recommended**: Use `scripts/build/build_pipeline.py` (Section 0) for the full workflow.

The steps below describe the individual scripts for advanced use cases:
1. Build unified profile corpus from `data/profiles`.
2. Build feature-engineering artifacts from that corpus.
3. Optionally run the demo report over the feature output.

## 1) Build Unified Profile Corpus

> **Note**: For end-to-end workflows, prefer `scripts/build/build_pipeline.py` which handles corpus building internally. Use this script only for standalone corpus builds.

Script:
- `scripts/build/build_profile_corpus.py`

Example:

```bash
python scripts/build/build_profile_corpus.py
```

Expected corpus artifacts:
- `sequence_index.jsonl`
- `corpus_manifest.json`
- `quality_report.json`

## 2) Build Feature Engineering Artifacts

> **Note**: For end-to-end workflows, prefer `scripts/build/build_pipeline.py` which handles profiling and corpus building before FE. Use this script when starting from an existing corpus.

Canonical script:
- `scripts/build/build_feature_engineering.py`

Example:

```bash
python scripts/build/build_feature_engineering.py
```

Optional audio analysis:

```bash
python scripts/build/build_feature_engineering.py \
  --skip-audio-analysis
```

Default quality gates for unknown coverage are intentionally strict:
- `--quality-max-unknown-effect-family-ratio 0.02`
- `--quality-max-unknown-motion-ratio 0.02`
- `--quality-max-single-unknown-effect-type-ratio 0.01`

Root output artifacts include:
- `content_templates.json`
- `orchestration_templates.json`
- `transition_graph.json`
- `layering_features.parquet|jsonl`
- `color_narrative.parquet|jsonl`
- `quality_report.json`
- `unknown_diagnostics.json`
- `template_retrieval_index.json`
- `template_diagnostics.json`
- `motif_catalog.json`
- `cluster_candidates.json`
- `cluster_review_queue.jsonl`
- `taxonomy_model_bundle.json`
- `taxonomy_eval_report.json`
- `retrieval_ann_index.json`
- `retrieval_eval_report.json`
- `planner_adapter_payloads/sequencer_adapter_payloads.jsonl`
- `planner_adapter_acceptance.json`
- `feature_store_manifest.json`

Per sequence output includes:
- `audio_discovery.json`
- `feature_bundle.json`
- `aligned_events.parquet|jsonl`
- `effect_phrases.parquet|jsonl`
- `phrase_taxonomy.parquet|jsonl`
- `target_roles.parquet|jsonl`

## 3) Run Demo Reporting

Script:
- `scripts/demo_feature_engineering.py`

Build + report:

```bash
python scripts/demo_feature_engineering.py \
  --corpus-dir data/profiles/corpus/v0_effectdb_structured_1 \
  --output-dir data/features/demo_feature_engineering
```

Report only (no build):

```bash
python scripts/demo_feature_engineering.py \
  --skip-build \
  --output-dir data/features/demo_feature_engineering
```

Demo report output:
- `feature_engineering_demo.md`

The demo surfaces:
- per-sequence coverage with `sequence_name` (song)
- duplicate-sequence warning by `sequence_sha256`
- taxonomy/role distributions
- top content/orchestration templates
- template retrieval baseline ranking
- template diagnostics (low support/high concentration/high variance/over-generic flags)
- transition graph summary
- quality gate summary

## 4) Query Template Retrieval

Script:
- `scripts/query_template_retrieval.py`

Example:

```bash
python scripts/query_template_retrieval.py \
  --feature-dir data/features/feature_engineering \
  --template-kind orchestration \
  --role lead \
  --top-n 15
```

Filter by effect family and flow:

```bash
python scripts/query_template_retrieval.py \
  --feature-dir data/features/feature_engineering \
  --effect-family bars \
  --min-transition-flow 0.2 \
  --top-n 20
```

## Directory Conventions

Profiles source:
- `data/profiles/<profile_dir>`

Unified corpus:
- `data/profiles/corpus/<schema_or_run_name>`

Feature outputs:
- `data/features/<run_name>`

## Notes

- `_v0_check` and `*_smoke` directories are development/test artifacts and are not canonical run paths.
- If multiple entries share the same `sequence_sha256`, feature distributions can look duplicated across package IDs.
