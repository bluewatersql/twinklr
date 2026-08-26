# Script inventory

This directory contains manual utilities, compatibility shims, and validation helpers.
It is not one unified command surface: use the `twinklr` CLI for production workflows.
Commands below assume the repository root and `uv run python`.

## Supported validation entry points

| File | Purpose and status |
|---|---|
| `validation/validate_artifacts.py` | Validates moving-head/display plans and XSQ artifacts. See [`validation/README.md`](validation/README.md). It is tested, but neither Make nor CI invokes the entry point. |
| `validation/validate_agent_artifacts.py` | Runs saved-response schema and prompt checks. It is tested, but neither Make nor CI invokes the entry point. |
| `validation/test_prompt_validation.py` | Manual prompt-validation harness invoked by `validate_agent_artifacts.py`. Despite its filename, pytest collects no tests from it. |
| `validation/test_schema_validation.py` | Manual saved-response schema harness invoked by `validate_agent_artifacts.py`. Despite its filename, pytest collects no tests from it. |

The validation implementation package consists of `validation/__init__.py`,
`validation/_core/__init__.py`, `validation/_core/io.py`,
`validation/_core/mh_plan_validation.py`, `validation/_core/mh_xsq_validation.py`,
`validation/_core/models.py`, and `validation/_core/reporting.py`. Together with the
top-level `scripts/__init__.py`, these eight package/internal modules are library support,
not standalone commands.

## Make-wired tools

| File | Purpose and status |
|---|---|
| `check_version_consistency.py` | Checks the five version declarations. Wired to the explicit `make version-check` target; it is not part of `make validate`. |
| `test_audio_pipeline.py` | Manual, real-audio harness used by `make test-audio`, `make test-audio-whisperx`, and `make test-audio-all`. Despite its name, pytest collects no tests from it. It can download models or use network providers when explicitly enabled. |

## Compatibility shims

| File | Purpose and status |
|---|---|
| `demo_sequencer_pipeline.py` | Forwards existing invocations to the production `twinklr display` command. It is no longer the only caller of `build_display_pipeline`; production display/show wiring owns that path. |
| `demo_recipe_builder.py` | Deprecated shim forwarding to `twinklr curate-catalog`. Prefer the CLI command directly. |

To exercise the display workflow through the compatibility shim:

```bash
uv run python scripts/demo_sequencer_pipeline.py \
  --audio path/to/song.mp3 \
  --layout path/to/xlights_rgbeffects.xml \
  --config path/to/job_config.json \
  --out artifacts
```

This is equivalent to `uv run twinklr display ...`; it does not restore the removed
unified feature-engineering entry point described historically in
[`docs/pipeline_guide.md`](../docs/pipeline_guide.md).

## Data-dependent demos

These are exploratory/manual programs, not clean-checkout acceptance tests. Read each
module's help/docstring before use and provide the named local inputs.

| File | Inputs / effect |
|---|---|
| `demo_display_renderer.py` | Local group plan and audio-profile artifacts; writes a demo XSQ. |
| `demo_eval_report.py` | Local audio, checkpoint, fixture config, and rendered XSQ under `artifacts/`/`data/`. |
| `demo_feature_engineering.py` | Local music index/corpus under gitignored `data/`; writes FE artifacts. |
| `demo_moving_heads_pipeline.py` | Local audio/config plus configured provider access; writes moving-head artifacts. |
| `demo_profiling.py` | Local vendor archives under `data/vendor_packages` or explicit inputs. |
| `demo_recipe_pipeline.py` | Synthetic mode works without a corpus; `--load-fe-data` requires local FE artifacts. |

## Corpus and template tools

These commands depend on gitignored corpus/feature artifacts unless their docstring says
otherwise. Several mutate their requested output or the tracked catalog; inspect dry-run
support and the diff before retaining results.

| File | Purpose and status |
|---|---|
| `cleanup_display_templates.py` | Mutates the tracked display-template catalog; maintenance utility, not a routine build step. |
| `enrich_builtin_templates.py` | Enriches tracked builtin templates; supports `--dry-run`. |
| `evaluate_recipe_dictionary.py` | Reads a promoted recipe catalog from an FE run. |
| `query_template_retrieval.py` | Reads `template_retrieval_index.json`. It is referenced only by the script-specific FE notes, with no runtime, test, Make, or CI caller; treat it as likely dead pending a later deletion decision. |
| `report_quality_gate_distributions.py` | Builds owner-review evidence from a staged mining run; never promotes candidates. |
| `validate_fe_output.py` | Checks a local `data/features/` database and artifacts against historical FE-remediation expectations. |

Detailed feature-engineering examples are in [`docs/feature_engineering.md`](docs/feature_engineering.md).

## Offline analyses

All three require gitignored `data/features/...` corpus artifacts and are not runnable
meaningfully from a clean checkout:

- `analysis/cross_lane_profile_analysis.py`
- `analysis/normalize_unknown_effects.py`
- `analysis/validate_rules_against_profiles.py`

## Removed and quarantined tools

- `scripts/build/` was deleted on 2026-02-24 (`82aaf38`). The old unified FE workflow
  is an ABANDON candidate, not a supported command. Do not copy its historical commands
  from the pipeline guide into automation.
- `scripts/show_coverage_by_component.py` was deleted on 2026-01-30. It is restorable but
  not restored with
  `git show c67bbdd^:scripts/show_coverage_by_component.py`; consequently the current
  `make coverage` and `make coverage-detailed` recipes are known-broken.
- `utils/video_demo.py` is outside this script catalog. It has no product/test/Make/CI
  caller and can issue paid OpenAI video-generation work plus local ffmpeg processing.
  P4-T6 does not promote or delete it; treat it as quarantined experimental code pending
  a separately reviewed dead-code decision.

`scripts/__init__.py` only makes shared helpers importable. This README and
`validation/README.md` are the two documentation-only files in the script tree.
