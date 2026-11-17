---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# C1.1c: live `inject` and `regenerate` on physical output — 2026-11-16

Cutover step C1.1c from the [phase 3 plan](../../plan/phase-3-arrangement.md) and the
[cutover inventory](../../plan/cutover-inventory.md) (flag F1). Built on
`feat/mh-cutover-live` from `b5cbc658`: `b0943249`, the review-fix commit `b1b0816c`
that adds this record, and a verification-fix commit. One implementing agent; one
review (approve with fixes: one high, two medium, lows) and one verification (two
blockers: a hard-killed replacement over 25,000 effects could not be recovered, and
refusal timing was overstated), each fixed by the same agent.

**Nothing here has touched a running xLights.** Mutating a running show is owner-gated;
every result below is offline, against an in-memory stand-in for the automation client
(`tests/support/live_xlights.py`) and the existing httpx mock. Live injection of a
physical render is unproven against real xLights; the checks it needs are listed at the
end.

## What was proven offline, and how

| Claim | Evidence |
|---|---|
| The injected effects are the `.xsq`'s, one for one: model, layer (file layer + 99), effect, DMX settings, palette, frame-aligned times | `test_physical_live_effects_equal_the_written_xsq_element_by_element` (render, then the written file parsed back); the CLI tests compare the fake's contents with the `.xsq` each run wrote. Confirmed independently by the reviewer |
| Physical `inject` runs the real gate, planner stage (recorded planner), render stage and workflow; a second identical inject writes nothing | `test_inject_on_a_physical_job_injects_exactly_the_written_xsq` |
| `regenerate` re-plans one section, re-renders the whole song from the recorded plan and replaces all moving-head effects; other sections' plan and cues unchanged; fingerprint changes and is printed | `test_regenerate_on_a_physical_job_rerenders_the_whole_song_and_replaces_its_effects` |
| `regenerate` refuses before any planning request when no plan is recorded or the recorded one is stale (owned effects, audio, job or rig changed), and in the pre-planning check (`RenderPreflightStage`, right after the gate, before the profile or any planner) when a kept section's template or preset is not admitted | CLI tests `…without_an_injected_plan…`, `…refuses_a_stale_recorded_plan_before_planning` (×4), `…the_gate_no_longer_admits_before_any_planner` (asserts no planner, the profile included, ran); `test_regenerate_refuses_a_base_plan_this_run_cannot_render_as_recorded` |
| `regenerate` refuses after planning, before any write: a re-plan that is not one section over its recorded bars, or overlaps a kept section; another sequence open at write time | `test_regenerate_with_a_base_plan_refuses_a_replan_that_breaks_the_song` (×4), `…refuses_a_sequence_switched_during_the_run` |
| inject → regenerate → regenerate builds on each recorded plan | `test_regenerate_on_a_physical_job_twice_builds_on_each_recorded_plan` |
| Interrupted runs converge, at full size and after a kill that runs no handler: the manifest is saved before the first write (owned effects found and to-add effects) and on any interruption it survives (exact confirmed state); rows on a layer read but not found are dropped, so no never-added row lingers | `test_a_whole_render_replacement_killed_without_cleanup_converges_at_full_size` (30,000-for-30,000, killed at delete 15,000 and at add 15,000, only the pre-write save surviving; exact request counts; user effects untouched; manifest equals the sequence), `test_a_killed_section_regeneration_leaves_no_rows_after_another_section_runs`, `test_an_interrupted_replacement_records_its_state_and_the_rerun_converges` (Ctrl-C and cancellation); the reviewer's `kill_midway.py` and the verifier's `h1_danger.py` and `h1_probe.py` |
| Volume is linear: 30,000 effects inject, re-inject and replace with one request per effect operation and at most one interval comparison and one equality test per effect per command | `test_thirty_thousand_effects_inject_reinject_and_replace_in_linear_time` (the replaced pairwise check and list manifest took 43 s and about 1.35e9 comparisons) |
| The workflow's rewrites (sweep overlap check, bisection collision check, counter manifest, the later simplifications) behave as the original, except that manifest rows for effects not found in the sequence are dropped | The verifier's `diff_workflow.py` against the `b5cbc658` workflow, 20,000 scenarios (and 2,000 large): outcome, commands, results, failed command, final sequence and request order identical in every scenario; the saved manifest differs in 1,309 (284 large), each time only by dropping rows for effects the sequence does not hold, never one it holds; 100,000 overlap and 200,000 collision-predicate cases, 0 mismatches |
| Legacy `inject`/`regenerate` unchanged | Existing legacy tests pass unmodified; legacy reads through the same sequence reader |

Bound: `MAX_LIVE_EFFECTS = 50,000` effects to add (refused before any read) and owned
effects to delete (counted after reading, refused before any write) per command; the
recorded manifest rows are only capped at twice that before reading, a level no manifest
saved before a killed run's first write reaches. Chosen, not
measured. A synthetic four-head, three-minute render emitted 18,860 effects; the owner's
song about 30,000.

## What C1.2 deletes in the files this step touched

- `packages/twinklr/cli/main.py`: the legacy `else:` branch of the live block
  (`rendered_segments`, `live_effects_from_segments`, `workflow.regenerate_section`) and
  its import; the `physical` conditions become unconditional (the regenerate preflight,
  the dry-run summary, the plan record); the `unplaced` check's mode test; the
  `--layout ... ignored for legacy` branch.
- `packages/twinklr/core/api/xlights/injection.py`: `live_effects_from_segments` and its
  imports (`XsqAdapter`, `build_fresh_sequence`, `FixtureSegment`, and `FixtureGroup` if
  then unused); `LiveInjectionWorkflow.regenerate_section`; the `replace_sections`
  parameter and the section scoping in `inject` (the `sections` set, `retained`, the
  owned-in-scope filter: every owned effect is in scope); the `TWINKLR_LAYER` alias (no
  importer in packages or tests at this commit). `LiveEffect.section_id` and
  `NO_SECTION_ID` remain as provenance only (manifest rows, partial-failure reports).
- `packages/twinklr/core/api/xlights/__init__.py`: the `live_effects_from_segments` export.
- `packages/twinklr/core/agents/sequencer/moving_heads/rendering_stage.py`: the
  `rendered_segments` state if nothing else reads it (`show_stages.py` also sets it); the
  `render_record is not None` guard collapses.
- `packages/twinklr/core/config/render_policy.py`: `require_legacy_render` and its
  suggestion to "set the mode to 'legacy_v1'" (`:115`), still used by `show_cmd.py`,
  `show_wiring.py` and `rerender.py`. The two suggestions this step's paths reached
  (`render_policy.py:101`, `pipeline.py:255`) are already removed.
- `packages/twinklr/core/agents/sequencer/moving_heads/stage.py` and
  `rendering_stage.py`: nothing; the regeneration merge (`_with_base_plan`), the
  `check_regeneration_base` call in the pre-planning check and the
  `regeneration_base_plan`/`regeneration_section_id` state are the physical path.
- Tests: `test_injection_settings_match_golden_export_builder`,
  `test_golden_live_layers_preserve_xsq_topology_without_self_overlap`,
  `test_regenerate_section_touches_only_that_section`,
  `test_regenerate_empty_section_removes_owned_effects_on_disappearing_target`,
  `test_legacy_live_effects_read_through_the_same_sequence_reader`; re-point
  `test_run_pipeline_reports_structured_partial_injection_failure` to the physical path.

## Checks that need the owner and a running xLights

None of these is verified. Each needs an expendable scratch sequence (owner-gated).

1. `addEffect` accepts the physical DMX settings string (`E_SLIDER_DMX1..48`, the
   `E_CHECKBOX_INVDMX*` and notebook keys) on a per-fixture DMX model and plays it as the
   imported `.xsq` does.
2. An empty `palette` in `addEffect` equals the `.xsq` effect with no palette attribute.
3. `getEffectSettings` returns the DMX settings string unchanged, and the start and end
   times as sent. If not, every identical re-inject deletes and re-adds everything, and
   an interrupted run cannot recognise its own effects.
4. `addEffect` does not snap times to the open sequence's frame interval (25 or 50 ms)
   or clamp an effect past the sequence end. Either breaks read-back matching, so every
   later inject would refuse a "user-owned" collision with Twinklr's own effects.
5. `addEffect` at layer 99 on a model with one layer (it creates the layers between).
6. Back-to-back effects (one ends where the next starts) are accepted as sent.
7. Throughput: time per `addEffect`, `getEffectSettings` and `deleteEffect` at
   20,000-90,000 sequential requests, including the 30,000 reads an identical re-inject
   makes.
8. Undo-stack growth: each command records an undo step (from the earlier read of
   `xLightsAutomations.cpp`), so a run adds tens of thousands.
9. UI responsiveness and autosave during a long run.
10. A `getEffectIDs` response of about 7,500 ids per model within the 30 s timeout.
11. A target model in the layout but not in the open sequence's elements.
12. `getEffectIDs` on an owned model that no longer exists in the layout.
13. Blending of the user's own layers, and of effects on group models, over layer 99.
14. The 50,000 bound.
15. Live runs do not check model channel counts (there is no `--layout` for them).
16. An effect the user places on layer 99 or above that exactly matches one Twinklr placed
    or was about to place (model, layer, times, effect, settings, palette) is treated as
    Twinklr's (by design; documented).
