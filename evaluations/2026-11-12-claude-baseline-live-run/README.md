# 2026-11-12 — first Claude-backed live run (`Hey Come Look At My House`)

The baseline live end-to-end run from
[runbook 05 §2](../../changes/twinklr-reactivation-review/runbooks/05-phase-2p-and-3-live-evidence.md),
and the first pipeline run with Claude (`llm_provider: anthropic`) as the LLM for every
agent role. The owner approved live requests and asked for Claude on 2026-11-11.

## Inputs

| Field | Value |
|---|---|
| Window (UTC) | 2026-11-12T14:35:41Z – 14:39:45Z (242.2 s pipeline time) |
| Commit | `f0ae0da884a32baca1c86cf5c429d17a8ceb911b` (clean tree; `make validate` passed: 5701 passed, 39 skipped) |
| Audio | `data/music/Hey Come Look At My House.mp3`, 140.9 s, owner-local and not committed (sha256 prefix `a96c6dba9a6c4830`) |
| Rig | 4 moving heads `MH1`–`MH4` (xLights models `Dmx MH1`–`Dmx MH4`, group `90 - MH`), from the owner-local `fixture_config.valid.json` (gitignored; sha256 prefix `f3c2d084448469de`) |
| Provider | Anthropic, `claude-opus-5-5` for every role. Server-side refusal fallback is on. |
| Effort | plan `high`, judge `low`, refinement / profile / lyrics `medium`, asset enricher `low` |
| Job config | `max_iterations` 2, `success_threshold` 70, `timeout_seconds` 900 (sha256 prefix `da32fcd44a1ce553`) |
| Session | `sess_28a1f0e95a5f4b1c` |

The 2026-08 reference song (`11 - Need A Favor.mp3`) is not in the restored `data/music`,
so this run used the shortest restored song. The metrics comparison below is therefore
indicative and not like-for-like.

## Result

**PASS.** `Overall Success: ✅`, `Stages Completed: 6/6`, exit 0. Emitted
`hey_come_look_at_my_house_twinklr_mh.xsq` plus `.xtiming` / `.xmap` / trace sidecars and
`checkpoints/plans/final.json`. These are copied here as [`rendered.xsq`](rendered.xsq) and
[`checkpoint.json`](checkpoint.json).

| Stage | Outcome |
|---|---|
| audio | completed. Analyzer warned `Low downbeat phase confidence: 0.04`. |
| profile | completed in 57.2 s, 0 repairs |
| lyrics | skipped (`Condition not met`) |
| macro | completed in 2 iterations. Iteration 1 failed heuristic validation with 16 errors, the first five all `Unknown theme tag` (`bold`, `immediate`, `festive`, `groove`, `sweeping`). Iteration 2 passed and the judge returned `APPROVE` at 7.6. |
| moving_heads | completed. Planner took 99.1 s; judge returned `APPROVE` at 7.4 in 1 iteration. A one-bar `outro` collapsed onto bar 175 (warning). |
| render | completed: 13 sections, 254 segments |

### Structured outputs on Claude

Claude's structured outputs reject every planner schema with HTTP 400 `The compiled
grammar is too large`. Attempt 1 at `2be39df` failed at the profile stage on that error
(see the change evidence linked below). Commit `f0ae0da` resends such a request once with
the schema carried only by the prompt, and remembers the rejection for later calls. In this
run:

- `AudioProfileModel`, `MacroPlan` and `ChoreographyPlan` were each rejected once, then
  answered prompt-only. The second macro call skipped the 400 because the rejection was
  remembered.
- Both judges ran with server-enforced `json_schema`.
- Every call validated first time: 0 schema repairs and 0 validation errors.

## Token use and spend

From `data/logging/*/sess_28a1f0e95a5f4b1c/` (6 logged calls). Spend is computed at
`claude-opus-5-5` list prices ($4 per MTok input, $20 per MTok output, thinking included in
output). Confirm exact figures in the Anthropic console for the window above.

| Call | Input | Output | Duration |
|---|---|---|---|
| audio_profile | 19,069 | 6,144 | 57.2 s |
| macro_planner iteration 1 | 9,708 | 4,463 | 35.6 s |
| macro_planner iteration 2 | 14,222 | 3,527 | 24.8 s |
| macro_judge | 12,345 | 1,005 | 10.9 s |
| mh_planner | 20,228 | 11,653 | 99.1 s |
| mh_judge | 21,330 | 1,400 | 13.9 s |
| **Total** | **96,902** | **28,192** | about **$0.95** |

The 2026-08 OpenAI live run used about 93k tokens for about $1–2. The three rejected
requests returned no usage.

## Sophistication metrics (runbook 05 §3, qa-runbook §4)

`extract_xsq_metrics` on the emitted `.xsq`, against
`tests/regression/baselines/11_need_a_favor.metrics.json`:

| Metric | This run | Baseline | Note |
|---|---|---|---|
| distinct_effect_types | `["DMX"]` | `["DMX"]` | same emission modality |
| sequence_timing | 20 ms | 20 ms | same grid |
| max_layers | 2 | 2 | base + transition layering kept |
| placed_effect_count | 251 | 262 | comparable volume on a 141 s song |
| value_curve_channel_count | 741 | 622 | value-curve richness kept and exceeded |
| effectdb_entry_count | 207 | 262 | |
| element_count | 5 | 11 | set by the rig: 4 heads here |
| max_dmx_channel | 13 | 16 | set by the rig |

On the four axes qa-runbook §4 uses to define "on par" (modality, delivery invariants,
placed-effect volume, value-curve richness), this run is on par with the pinned baseline.
Element count and max channel follow the rig, not the plan.

## Automated evaluation report

[`report.md`](report.md) / [`report.json`](report.json) / [`plots/`](plots/) come from
`twinklr eval-report` on the checkpoint, run offline after the live run.

- Status: 13 errors and 15 warnings.
- 13 physics violations, all pan/tilt acceleration over the 1000°/s² limit.
- For comparison, the deterministic golden fixture
  ([2026-08-13](../2026-08-13-golden-fixture-mh4-minimal/report.md)) involves no LLM and
  reports 9 physics violations. The violations therefore come from template rendering,
  not from this provider.

## Related evidence

- Claude provider live findings (schema probe, attempt 1):
  [`changes/twinklr-reactivation-review/evidence/2026-11-12-claude-provider-live/`](../../changes/twinklr-reactivation-review/evidence/2026-11-12-claude-provider-live/README.md)
- Human judgment: [`judgment.md`](judgment.md) (PENDING-OWNER)
