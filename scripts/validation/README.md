# Validation Scripts (Unified)

This directory contains the unified validation entrypoints for both sequencer pipelines:

- `validate_artifacts.py` — validates generated plan/evaluation/XSQ artifacts for:
  - `mh` (moving heads)
  - `display` (group-plan + holistic + xLights XSQ)
- `validate_agent_artifacts.py` — validates agent schemas and prompt artifacts

Legacy MH-only wrappers (`plan.py`, `xsq.py`) were removed. Use `validate_artifacts.py` directly.

## Quick Start

### Display pipeline

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline display --mode all 11_need_a_favor
```

### Moving-head pipeline

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline mh --mode all need_a_favor
```

### Auto-detect pipeline

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline auto --mode all 11_need_a_favor
```

## What Gets Validated

## `validate_artifacts.py`

### Modes

- `--mode plan`
  - Validates plan/evaluation JSON artifacts
- `--mode xsq`
  - Validates rendered xLights `.xsq`
- `--mode all`
  - Runs both `plan` and `xsq`

### Pipelines

- `--pipeline display`
  - Uses display-specific plan/evaluation checks and display XSQ checks
- `--pipeline mh`
  - Uses in-process extracted MH plan/XSQ validators (deep parity path)
- `--pipeline auto`
  - Attempts JSON-shape detection, then XSQ filename heuristics

## Artifact Discovery (default paths)

Given `sequence_name`, the validator looks under `artifacts/<sequence_name>/`.

### Display

- `group_plan_set.json`
- `holistic_evaluation.json`
- `<sequence_name>_display.xsq`
- optional sidecar: `<sequence_name>_display.xsq.trace.json`

### MH

- `plan_raw_<sequence_name>.json`
- `plan_<sequence_name>.json` (or `final_<sequence_name>.json` fallback)
- `evaluation_<sequence_name>.json`
- `<sequence_name>_twinklr_mh.xsq`

You can override any path with explicit CLI flags.

## CLI Reference (`validate_artifacts.py`)

### Common flags

- `--mode {plan,xsq,all}`
- `--pipeline {auto,display,mh}`
- `--plan-path <path>`
- `--evaluation-path <path>`
- `--xsq-path <path>`
- `--quality-only` (skip deeper plan-vs-XSQ checks)

### MH-only flags

- `--raw-plan-path <path>`
- `--fixture-config-path <path>`
- `--output-json <path>` (MH XSQ issue export)

### Display-only flags

- `--display-target-map <path>`
  - JSON map of semantic target IDs -> xLights element aliases
  - reduces false positives in target matching
- `--display-xsq-trace-path <path>`
  - optional explicit display XSQ trace sidecar
  - defaults to `<xsq>.trace.json`

## Output Interpretation

The validator prints a per-mode summary.

- `❌` = critical issue (causes non-zero exit)
- `⚠️` = warning (non-fatal; investigate)
- `PASS` = no issues found for that mode

Exit code behavior:

- `0` = no critical issues across selected modes
- `1` = one or more critical issues found

Warnings do not fail the command unless they correspond to logic that emits a critical (`❌`) issue.

## Display Validation Details

### Plan validation (display)

Validates structure and common semantic issues in:

- section list presence and shape
- duplicate `section_id`
- section overlap timing
- duplicate lane entries per section
- placement required fields (`placement_id`, `template_id`, `target`, `start`, `duration`)
- placement `start`/`duration` type-shape checks
- duplicate `placement_id` across the plan set
- placement target mismatch vs coordination targets

### Holistic evaluation validation (display)

Validates:

- score ranges
- `recommendations` list shape
- `score_breakdown` numeric values (0..10)
- `cross_section_issues` field shapes
- `severity` values (`NIT|WARN|ERROR`)
- `targeted_actions` list contents

### Cross-validation (display plan + evaluation)

Checks references from holistic feedback back to plan artifacts:

- unknown section references in `affected_sections`
- unknown `section ...` references in `targeted_actions`
- unknown `placement_id ...` references in `targeted_actions`

### XSQ validation (display)

Baseline checks:

- invalid effect timing windows
- invalid effect `ref` vs `EffectDB`
- overlaps within the same element/layer
- sections with no overlapping XSQ effects

Semantic checks:

- section-level target coverage (`group_plan_set` targets vs rendered XSQ elements)
- optional placement-level coverage when sidecar trace is present

## Display XSQ Trace Sidecar (placement-level validation)

To enable placement-level display XSQ validation, generate a sidecar next to the `.xsq`:

- `<xsq>.trace.json`

Current display demos write this automatically:

- `scripts/demo_display_renderer.py`
- `scripts/demo_sequencer_pipeline.py`

### What the sidecar enables

The validator can detect:

- plan placements with no rendered trace coverage
- trace entries referencing unknown `placement_id`
- section/lane/template mismatches between trace and plan
- target/element mismatch vs planned placement target (with alias map support)

### Alias map example (`--display-target-map`)

```json
{
  "CANDY_STRIPES": ["Candy Canes"],
  "MEGA_TREE": ["Mega Tree"]
}
```

This map is used for both section-level target coverage and placement-level sidecar checks.

## MH Validation Details

MH validation is now unified but still deep (in-process):

- plan validation:
  - raw plan structure/timing/channels
  - implementation plan structure/timing/template refs
  - beat alignment
  - evaluation schema/scoring
  - raw↔implementation cross-validation
- XSQ validation:
  - DMX parsing and quality checks
  - duplicates/overlaps/gaps/missing refs
  - DMX data presence thresholds
  - value curve checks
  - section coverage and channel usage vs plan/fixture config

## Agent Artifact Validator (`validate_agent_artifacts.py`)

Unified wrapper for validating agent-facing artifacts:

- `--schemas`
- `--prompts`
- `--all`

Examples:

```bash
uv run python scripts/validation/validate_agent_artifacts.py --schemas
uv run python scripts/validation/validate_agent_artifacts.py --prompts --agent macro_planner
uv run python scripts/validation/validate_agent_artifacts.py --all
```

This delegates to the existing schema/prompt validation scripts and provides a single entrypoint.

## Recommended Usage Patterns

### During development

- Fast check (display XSQ syntax/overlap only):

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline display --mode xsq --quality-only 11_need_a_favor
```

- Full display validation with alias mapping:

```bash
uv run python scripts/validation/validate_artifacts.py \
  --pipeline display \
  --mode all \
  --display-target-map artifacts/11_need_a_favor/display_target_aliases.json \
  11_need_a_favor
```

- Full MH validation with explicit paths:

```bash
uv run python scripts/validation/validate_artifacts.py \
  --pipeline mh \
  --mode all \
  --raw-plan-path artifacts/need_a_favor/plan_raw_need_a_favor.json \
  --plan-path artifacts/need_a_favor/plan_need_a_favor.json \
  --evaluation-path artifacts/need_a_favor/evaluation_need_a_favor.json \
  --xsq-path artifacts/need_a_favor/need_a_favor_twinklr_mh.xsq \
  need_a_favor
```

## Troubleshooting

- `Pipeline: mh` selected unexpectedly
  - pass `--pipeline display` explicitly
  - verify `group_plan_set.json` exists and is valid JSON
- false positives on display target coverage
  - provide `--display-target-map`
  - ensure sidecar exists for placement-level checks
- no placement-level display checks running
  - verify `<xsq>.trace.json` exists (or pass `--display-xsq-trace-path`)
  - rerun display export using updated demos
- MH fixture-related XSQ warnings
  - provide `--fixture-config-path` for deeper channel/fixture checks

## Migration Summary

- Removed:
  - `scripts/validation/plan.py`
  - `scripts/validation/xsq.py`
- Use:
  - `scripts/validation/validate_artifacts.py`
- Legacy MH and display flows are both supported via the `--pipeline` flag.
