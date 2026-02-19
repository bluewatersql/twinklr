# Feature Engineering

This document is the single source of truth for running profiling corpus build + feature engineering.

## Canonical CLI Flow

1. Build unified profile corpus from `data/profiles`.
2. Build feature-engineering artifacts from that corpus.
3. Optionally run the demo report over the feature output.

## 1) Build Unified Profile Corpus

Script:
- `scripts/build_profile_corpus.py`

Example:

```bash
python scripts/build_profile_corpus.py
```

Expected corpus artifacts:
- `sequence_index.jsonl`
- `corpus_manifest.json`
- `quality_report.json`

## 2) Build Feature Engineering Artifacts

Canonical script:
- `scripts/build_feature_engineering.py`

Example:

```bash
python scripts/build_feature_engineering.py
```

Optional audio analysis:

```bash
python scripts/build_feature_engineering.py \
  --skip-audio-analysis
```

Root output artifacts include:
- `content_templates.json`
- `orchestration_templates.json`
- `transition_graph.json`
- `layering_features.parquet|jsonl`
- `color_narrative.parquet|jsonl`
- `quality_report.json`
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
- transition graph summary
- quality gate summary

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
