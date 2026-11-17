# Validation Scripts (Unified)

This directory contains the unified validation entrypoints for both sequencer pipelines:

- `validate_artifacts.py` — validates generated artifacts for:
  - `display` (group-plan + holistic + xLights XSQ)
  - `mh` (moving heads: the xLights XSQ only)
- `validate_agent_artifacts.py` — validates agent schemas and prompt artifacts

A moving-head plan is not validated here: `twinklr eval-report` re-renders a run's plan
checkpoint and reports on it (see the user guide).

## Quick Start

### Display pipeline

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline display --mode all 11_need_a_favor
```

### Moving-head pipeline

```bash
uv run python scripts/validation/validate_artifacts.py --pipeline mh --mode xsq need_a_favor
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
  - Checks the moving-head XSQ. `--mode plan` exits with status 2; `--mode all` runs the
    XSQ checks only
- `--pipeline auto`
  - Detects display from its plan or evaluation JSON, then from the XSQ filename
    (`_display.xsq` / `_twinklr_mh.xsq`); otherwise display when its default artifacts
    exist, else `mh`

## Artifact Discovery (default paths)

Given `sequence_name`, the validator looks under `artifacts/<sequence_name>/`.

### Display

- `group_plan_set.json`
- `holistic_evaluation.json`
- `<sequence_name>_display.xsq`
- optional sidecar: `<sequence_name>_display.xsq.trace.json`

### MH

- `<sequence_name>_twinklr_mh.xsq`

You can override any path with explicit CLI flags.

## CLI Reference (`validate_artifacts.py`)

### Common flags

- `--mode {plan,xsq,all}`
- `--pipeline {auto,display,mh}`
- `--xsq-path <path>`

### MH-only flags

- `--fixture-config-path <path>` (check only the effects on the fixtures' xLights models
  and the group)
- `--output-json <path>` (MH XSQ issue export)

### Display-only flags

- `--plan-path <path>`
- `--evaluation-path <path>`
- `--quality-only` (skip plan-vs-XSQ checks)
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

The canonical display command writes this automatically:

- `twinklr display`

Compatibility and focused renderer demos also write it:

- `scripts/demo_display_renderer.py`
- `scripts/demo_sequencer_pipeline.py` (delegates to `twinklr display`)

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

A moving-head `.xsq` holds one constant DMX effect per run of identical 20 ms frames, each
setting every channel of the head's profile footprint. The XSQ checks read the file
alone:

- `ref`s that name no EffectDB entry (an effect's `ref` is the entry's zero-based
  position)
- overlaps, identical timings and gaps longer than 100 ms per model
- DMX data presence: effects with no channel data, all-zero effects, values outside
  0-255

What the render planned (cues, dark repositioning, dropped cues) is in the
`.xsq.trace.json` beside the `.xsq`; `twinklr eval-report` re-renders the run and reports
per-channel motion.

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

- MH XSQ validation with explicit paths:

```bash
uv run python scripts/validation/validate_artifacts.py \
  --pipeline mh \
  --mode xsq \
  --xsq-path artifacts/need_a_favor/need_a_favor_twinklr_mh.xsq \
  --fixture-config-path fixture_config.json \
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
- MH effects from other models counted
  - provide `--fixture-config-path` so only the fixtures' models are checked
