---
type: change
status: active
area: engineering
created: 2026-11-12
updated: 2026-11-12
---

# P4-T2 Ollama cloud — full pipeline run (2026-11-12)

> The raw console log and LLM call logs stay in the owner's checkout under the gitignored
> `artifacts/ollama-runs/attempt-01/` and `data/logging/*/sess_08ff6badf0b275a7/`. The
> tables below reproduce their results.

This follows the
[2026-11-11 smoke](../2026-11-11-p4-t2-ollama-cloud-smoke/README.md). There, the bare
one-request smoke parsed schema-shaped JSON but failed one cross-field `MacroPlan` rule.
That smoke runs without the real prompt pack and without repair. On 2026-11-12 the owner
approved live Ollama cloud runs until the path works. This run therefore uses the real
path: `twinklr run` with every agent role on Ollama cloud, through the real prompt packs,
`AsyncAgentRunner` validation and repair, and the judge loop. No local model is involved.

| Field | Value |
|---|---|
| Window (UTC) | 2026-11-12T15:41:41Z – 15:46:44Z (about 5 min) |
| Commit | `9766a84cc1882bcbeca706e629d9933f56f98b7a` (clean tree; `make validate` green) |
| Provider | `llm_provider: ollama`, `llm_base_url: http://127.0.0.1:11434/v1` (loopback daemon 0.34.2, which forwards `:cloud` models to ollama.com) |
| Model | `glm-5.3:cloud` for every role. Efforts, iterations (2) and timeouts match the Claude baseline run. |
| Audio / rig | `Hey Come Look At My House.mp3` (140.9 s), 4-head owner rig `MH1`–`MH4`, the same inputs as the [Claude baseline](../../../../evaluations/2026-11-12-claude-baseline-live-run/README.md) |
| Session | `sess_08ff6badf0b275a7` |

## Result: PASS

`Overall Success: ✅`, `Stages Completed: 6/6`, exit 0. The run emitted
`hey_come_look_at_my_house_twinklr_mh.xsq` (268 segments, 7 sections) plus timing, mapping
and trace sidecars.

| Call | Input | Output | Duration | Outcome |
|---|---|---|---|---|
| audio_profile | 12,921 | 27,674 | 132.6 s | valid, 0 repairs |
| macro_planner iteration 1 | 6,081 | 4,864 | 20.3 s | schema-valid; heuristic validation failed with 27 errors (unknown theme ids and tags such as `mood.dreamy` and `cold_open`) |
| macro_planner iteration 2 | 9,086 | 2,543 | 7.4 s | valid |
| macro_judge | 4,865 | 870 | 4.7 s | **APPROVE 7.4** |
| mh_planner iteration 1 | 13,071 | 21,518 | 112.7 s | schema-valid; heuristic validation failed with 8 errors (units past bar 167, overlapping section bars) |
| mh_planner iteration 2 | 17,470 | 4,513 | 17.0 s | valid |
| mh_judge | 11,114 | 1,022 | 5.9 s | **APPROVE 8.2** |
| **Total** | **74,608** | **63,004** | | |

- Every call validated against its schema on the first response: 0 schema repairs and 0
  validation errors.
- Ollama Cloud is billed by subscription, so the run has no per-token charge.
- Lyrics were skipped (`Condition not met`), as in the Claude run.

### Sophistication metrics against the pinned baseline (qa-runbook §4)

| Metric | Ollama `glm-5.3:cloud` | Claude `claude-opus-5-5` | Baseline (`Need A Favor`) |
|---|---|---|---|
| distinct_effect_types | DMX | DMX | DMX |
| sequence_timing | 20 ms | 20 ms | 20 ms |
| max_layers | 2 | 2 | 2 |
| placed_effect_count | 256 | 251 | 262 |
| value_curve_channel_count | 651 | 741 | 622 |
| effectdb_entry_count | 191 | 207 | 262 |

This run is on par on all four qa-runbook §4 axes. The baseline song differs, so the
comparison is indicative.

## What this proves

- **P4-T2 real-schema validity through the real path.** `glm-5.3:cloud` produced a
  `MacroPlan` that passed schema, heuristic and judge validation inside the production
  pipeline. Every other planner and judge role did the same.
- **What it does not prove.** The bare one-request smoke
  (`tests/local_only/test_ollama_structured_outputs.py`) still has no prompt pack and no
  repair, so it remains a weaker check than this run. Whether this run satisfies the P4-T2
  exit in place of that smoke is recorded in the HANDOFF.

## Incidental finding (not caused by this run)

Both this run and the Claude run log 61 `Failed to parse issue record` warnings. They come
from older records in the owner-local `data/agent_analytics` that carry `estimated_effort`
and `scope`, fields the current `IssueRecord` model forbids. The repository skips those
records, so planning is unaffected. This is a follow-up item: migrate or tolerate the old
records.
