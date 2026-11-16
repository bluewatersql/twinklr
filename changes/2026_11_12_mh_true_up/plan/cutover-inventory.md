---
type: plan
status: active
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# Single-path cutover inventory — 2026-11-16

Read-only inventory for task P3-C1 in [phase-3-arrangement.md](phase-3-arrangement.md),
made at `3113d062` by an agent separate from any implementer. It is evidence for the
cutover, not an authorization: nothing here is deleted until the owner has accepted a
physical render (P3-C0). Paths are under `packages/twinklr/` unless they start with
another top-level directory.

## Summary

The old path is about 15,000 lines of production code, about 13,400 lines of legacy-only tests and goldens, legacy cases inside 41 more test files, and 226 of the 503 records in `tests/config_effects_registry.py`. Grep evidence below supports each group. Four findings change how P3-C1 has to be done:

1. **`twinklr inject` and `regenerate` are also legacy-only**, and the brief's consumer list leaves them out (`cli/main.py:340-345`). Per-section regeneration has no obvious design on a whole-song physical render.
2. **T1 cannot land before C1.** The old renderer reads the planner fields T1 replaces, and the plan's "T1–T3a proceeds while C0 is pending" (`phase-3-arrangement.md:288`) contradicts that.
3. **Physical fingerprints change in C1 whatever is decided**, so the Phase 0 and Phase 1 fingerprint pins break.
4. **Phase 5's planned comparison against legacy Twinklr becomes impossible after C1** unless the owner has a legacy reference rendered first.

Recommendation: split C1 into consumer ports, then one atomic flip-and-delete, then model narrowing, renames and documents. Stack T1 directly on C1.

I worked read-only in `/Users/ondeck/work/github/twinklr-mh-true-up` at `3113d062` and edited nothing. Two read-only subagents built the test and document inventories. I spot-checked their key claims: the orphan fixtures, the harness import chain and the `JobConfig()` default in `harness.py:367-374`.

## Flags (surprising or risky)

| # | Finding | Evidence |
|---|---|---|
| F1 | Live `inject` and `regenerate` refuse physical jobs. Injection serializes through the legacy `XsqAdapter`. A physical render plans dark repositioning across section edges, and a coalesced run can span sections (its `section_id` comes from the earliest source). So `regenerate --section` on physical needs a real design. | `cli/main.py:340-345`, `api/xlights/injection.py:473-509`, `export/xsq_adapter.py:176-181` |
| F2 | T1 is blocked until C1. The old renderer reads `intensity`, `color_intent`, `shutter_events` and `gobo_events`, plus `transition_in` and energy preset ids. Removing those fields changes the accepted legacy look before acceptance. The plan line that lets T1–T3a proceed during C0 contradicts this. | `pipeline.py:1924-1958`, `:2025`, `:155-208`; `phase-3-arrangement.md:288` |
| F3 | C1 cannot fully delete `libraries/` or `models/transition.py`. The planner contract imports `ColorPreset`, `GoboPattern`, `ShutterPattern` and `TransitionHint`, so those survive until T1. | `agents/.../models.py:21-24`, `:224-227`; `tests/unit/agents/test_plan_schema_v2.py:39-41` |
| F4 | Physical fingerprints change no matter what. `policy.model_dump` includes `mode`, which has no `exclude_if`. `TemplateStep.geometry` is a required field with `extra="forbid"`, and every physical family JSON carries `"geometry": {}`, so all 7 documents and their sha256 change. The 16 Phase 0 and 2 Phase 1 fingerprint invariants cannot hold. | `config/models.py:657`, `pipeline.py:1553-1569`, `template.py:596-601`, `moving_heads_physical/mirror_wings.json` |
| F5 | The physical compile still requires the legacy handler registries. 11 physical test files build them with `create_default_registries`. | `models/context.py:148-151`, `:181-187`; `template_compiler.py:564-567`; `pipeline.py:1640-1646` |
| F6 | Phase 5 plans to compare "legacy Twinklr, P0 `reference_legacy_v1`, proposed". After C1 neither legacy arm can be rendered. `reference_policy.py` names four legacy template ids and no package code imports it; only its test does. | `phase-5-evaluation.md:175`; `reference_policy.py:23-29` |
| F7 | The deterministic selector raises `AssertionError` when every rung of its fallback ladder is empty. On a physical admitted set that can happen, for example a low-energy section in 3/4, where both low-energy families are excluded. It also loads the whole registry, not the per-rig admitted set. | `deterministic_selector.py:157-171`; catalog README "Meter" section |
| F8 | There is no default or synthetic profile path. A rig without `physical_profile` is refused before planning. After C1 that means no moving-head output at all. | `render_policy.py:44-50`; repo-wide grep of `FixtureCapabilities(` construction found none |
| F9 | Accepted look: `memories/decisions/mh-render-matches-pre-cleanup-look.md` is accepted and confirmed, and the golden `.settings.txt` banners and `tests/golden/README.md:45` restate it. The regression baseline `11_need_a_favor` may be re-pinned only by explicit decision. | `docs/qa-runbook.md:199` |
| F10 | Physical test support imports the legacy golden harness (`mh_physical` → `mh_true_up` → `tests.golden.harness`). | `tests/support/mh_true_up.py:23` |

## 1. What goes

| Group | Paths (≈ lines) | Importer, config and doc evidence |
|---|---|---|
| Handlers and curve handlers | `sequencer/moving_heads/handlers/**`, 33 files (3,528) | Imported only by `models/context.py`, `diagnostics.py` and `pipeline.py`, all on legacy paths (importer grep). |
| Libraries | `sequencer/moving_heads/libraries/**` (1,598) | `geometry`, `movement` and `dimmer` are legacy-only. The enums in `color.py`, `gobo.py` and `shutter.py` stay until T1 (F3). |
| Builtin templates | `templates/builtins/*.py`, 37 plus `__init__` (3,705); `templates/utils.py` (55; its 19 importers are all builtins); `templates/converter.py` (42) and the `template-export` command (`cli/template_cmd.py:20-55`) | `load_builtin_templates` is called from `cli/main.py:362`, `show_cmd.py:81`, `deterministic_selector.py:157`, `validate.py:141` and `pipeline.py:1386`. Each call goes or is ported. The `register_template` decorator (`library.py:347-362`) has only builtin callers. |
| Legacy JSON templates | `catalog/templates/moving_heads/{3 json, README}` | `DEFAULT_DATA_TEMPLATE_DIR` is referenced only in `data_loader.py:40` and `test_data_loader.py`. |
| Legacy compile | `compile/{channel_blender 327, intent_resolution 166, phase_offset 102, step_compiler 291, transition_detector 81, transition_planner 362, transition_segment_compiler 281}`; `compile_template` (`template_compiler.py:126-312`) and its chase, clip and fade helpers (`:1090-1316`, to confirm by grep in C1) | Every importer is `template_compiler.py`, `pipeline.py` or `diagnostics.py`. |
| Legacy render in `pipeline.py` | `ENERGY_TO_INTENSITY` and `PALETTE_ROLE_TO_COLOR` (`:127-147`), `resolve_section_preset` (`:155-208`), `_compute_section_duration_ms`, the legacy body of `render()` (`:1433-1532`), the `diagnostics` property, `_resolve_section_intent` and `_event_time_ms` (`:1924-1972`), transitions (`:1990-2174`), `_export_delivery`. About 450 lines. | — |
| Transitions | `sequencer/models/transition.py` (346; `TransitionHint` stays until T1); `TransitionConfig` and `JobConfig.transitions` (`config/models.py:587-640`, `:775`); `enum.TransitionMode` | No display or feature-engineering use: their transition models are separate (grep). |
| Export and delivery | `XsqAdapter` (`xsq_adapter.py:211-700`, ~490); everything in `DmxSettingsBuilder` except `build_frame_settings` (`:119-158`, ~350 lines go); `delivery.build_sequence` and `export_delivery` (`:84-183`); `config/adapter.py` (115); `curves/dmx_conversion.py` (77) and `curves/phase.py` (63) | Their only callers are `dmx_settings_builder.py` and `step_compiler.py`. Display uses only `curves/{generator, library, models}`. |
| Diagnostics audit | `LegacyControl` and `audit_legacy_controls` with helpers (`diagnostics.py:54-63`, `:89-358`) | Called only from the `pipeline.py:1541` property and tests. |
| Fixture config | `FixtureConfig.{dmx_mapping (required), inversions, pan_tilt_range, orientation, limits}` and the `get_standard_pose`, `dmx_to_degrees` and `degrees_to_dmx` methods (`instances.py:95-110`, `:146-240`); the same fields in `groups.py:38-51`; `config/poses.py` (279); `FixtureCalibration` (`rig.py:27`) | Readers are `dmx_settings_builder`, `adapter`, `rig`, `diagnostics` and `wheels`, all legacy, plus the planner's channel listing (`cli/main.py:234-241`, `pipeline/definitions/show.py:69-74`), which the profile replaces. |
| Config switches | `MHRenderPolicy.mode`; `schema_version` 3.0/3.1 and the validator (`models.py:754`, `:787-791`); `require_legacy_render` (`render_policy.py:81-92`); the legacy early return (`:39`) | — |
| Old selector arm | `reference_policy.py` (131) | Its only importer is its test; the owner decides its fate (F6). |
| Registry records | 226 records: `fixture.{base_config, fixtures[*]}` × {dmx_mapping 83, orientation 9, inversions 7, limits 6, pan_tilt_range 3}; `job.transitions` plus 7 sub-keys (`:620-659`); `job.moving_heads.mode` (`:279`); `job.schema_version` (`:268`, reworked); the `template.*` effect tests re-pointed at legacy snapshots (`:2675-2703`) | `RENDER_ONLY_CONFIG_KEYS` (`caching/identity.py:32-38`) are all physical keys: keep them and drop the docstring's "mode stays in". |
| Tests (delete) | About 13,400 lines. Unit: blender, intent, phase offset, transitions, the per-channel `dmx_settings_builder` tests, handler tests, `test_registry`, `test_repeat_contract_validation`, `test_control_diagnostics`, `test_documented_channel_scope`, `test_export_core`, `test_movement_intensity`, `test_rendering_pipeline`, `test_tilt_variation`, `models/test_transition`. Integration: `test_all_templates_compile`, `test_handler_categorical_params`, `test_scheduler_section_coverage`, `test_transitions_multi_layer`. Golden: 11 test files plus the `mh4_*` and `mh8_reference` directories (4,015 lines of settings). Regression: the `11_need_a_favor.*` baselines. Orphans: `tests/fixtures/{fan_pulse_template, templates/test_sweep_pulse, example_rig_4fixtures}.json` (`git grep` finds no reference). | Owner-gated where they pin the accepted look (§6). |
| Tests (cut legacy cases from 41 mixed files) | For example `test_mh_render_policy` `:24`, `:155`; `test_cache_identity:201`; `test_session:169`; `test_live_injection_command:179`, `:393`, `:443`; `test_render_preflight_stage:88`; `test_stage:535`; `test_rendering_stage:91`; `test_mh_physical_families:150`, `:201`; `test_mh_physical_pipeline:725`, `:812-838`; `mh_physical.BUILTIN_TEMPLATE_COUNT` (`:262`); the legacy-refusal tests in the physical compile files (`test_physical:347,353,374,379` and others); the moving-head half of `test_xsq_parity` (`:131`, `:151`) | — |
| Scripts | `scripts/demo_moving_heads_pipeline.py` (404, delete). `scripts/validation/_core/mh_xsq_validation.py` (587) assumes value curves (`:257-346`) and needs a rewrite, not deletion. `mh_plan_validation.py` follows T1. | — |
| Documents | `docs/user-guide.md` (`:228-264`, `:281`, `:318-331`, `:369-371`, `:429-453`, physical-field clauses at `:456-560`); `docs/overview.md:10`, `:27-44`, `:152-180`; `docs/developer-guide.md:47-49`, `:250-276`, `:417-424`; `docs/pipeline_guide.md:800-826`, `:1015-1017`; `docs/qa-runbook.md:24`, `:147`, `:193-199`; `context/current-state.md:39-72`, `:88-89`; `context/architecture/multi-agent-planning.md:15-47`; `context/glossary.md:18-22`; `README.md:31-67`, `:140-228`; the intro of `catalog/templates/moving_heads_physical/README.md:3-7` | — |
| Memories (set superseded, never delete) | `mh-render-matches-pre-cleanup-look.md` (whole); `llm-plans-intent-renderer-implements-precision.md:28-38`, `:55-66` (the principle stays, the mechanism is superseded); `coordinated-show-contract.md:28-41`; `display-stays-lit.md:41-42`, `:98-100` (the rationale); `memories/INDEX.md:18`, `:26` | — |

## 2. Shared code that stays but is reworked

| Item | Change when the old path goes |
|---|---|
| `FixtureSegment` and `ChannelValue` (`channels/state.py:20-61`, `:143`) | Remove options A and B (`static_dmx`, `curve`, `value_points`, `base_dmx`, `amplitude_dmx`, `offset_centered`, `blend_mode`, `clamp_*`) and `allow_grouping`. Channels then hold only the physical payload. |
| `TemplateStep`, `Template` and `StepPatch` (`template.py:164-197`, `:433-575`, `:577-645`, `:799-870`) | Remove `geometry`, the non-physical fields of `Movement`/`Dimmer`, `color`, `shutter`, `gobo`, `timing.phase_offset`, `Template.defaults`, and the matching `StepPatch` keys. `is_physical_template` and `_legacy_fields` (`physical.py:565-597`) become model invariants and are deleted. |
| Compile contexts (`context.py:102-194`) | Remove the 7 registries, `intent`, `n_samples`, `calibration` and `template_defaults`, which fixes F5. `FixtureContext.role` stays because target groups use it. |
| `template_compiler.py`, `scheduler.py`, `preset.py`, `patch.py`, `presets.py`, `visibility.py`, `preposition.py` | Keep. `compile_physical_template` uses `apply_preset`, `schedule_repeats`, `resolve_component_refs` and `apply_visibility` (`:393-425`, `:525`, `:679`). |
| Registry (`library.py`) and loader (`data_loader.py`) | Collapse to one catalog directory. Remove the decorator. Keep `--template-dir` and the overrides (overriding now shadows a catalog family). |
| `rig.py`, `fixture_builder.py`, `utils.resolve_semantic_group` | Keep the role and group derivation; drop calibration. |
| `identity.render_fingerprint` | Remove the `transitions` parameter and `LEGACY_RENDERER_REVISION`. |
| BeatGrid, emission core, `MHDiagnostic`, `frame_encoder`, `build_frame_settings`, `physical_run_requests`, `check_physical_models` | Unchanged; only names change (§4). |
| Planner: `models.py`, prompts, `heuristic_validator.py`, the context's `TemplateDescription` | Unchanged in C1. T1 replaces the contract and deletes the leftover enums from F3. |

**Mode branch sites, all removed in C1:**
- `config/models.py:657-664`, `:754`, `:787-791`
- `render_policy.py:39`, `:75-78`, `:81-92`
- `data_loader.py:125-163` (`admit_physical_catalog` at `:138`)
- `pipeline.py:238`, `:1352`, `:1430`, `:1552-1567`, `:1801`
- `rendering_stage.py:369`
- `stage.py:419-421` (the checkpoint's `render_mode`); `collect.py:44-51`
- `rerender.py:98`
- `cli/main.py:340-345`, `:451-471`, `:324-329`, `:696-698`
- `cli/show_cmd.py:78`; `show_wiring.py:142`
- `template_compiler.py:157-166`; `step_compiler.py:69-73`; `physical.py:539-551`
- Stale field descriptions: `instances.py:118-124` and `groups.py:60`, `:161-174`

## 3. Consumers that work only on the old path today

| Consumer | What is needed | Size | Risk |
|---|---|---|---|
| `twinklr show` (`show_cmd.py:59-95`, `show_wiring.py:125-142`, `show_stages.py:57-125`, `definitions/show.py`, `show_coordination.py:511-597`) | Load the physical catalog. Add the `RenderPreflightStage` gate as `audio_gate`, as the moving-head pipeline does (`definitions/moving_heads.py:72`). Render physically and put `physical_run_requests` into the shared sequence instead of the legacy `build_sequence`. Apply the output budget. The post-render `coordinate_moving_head_segments` slicing breaks darkness and transactions, so coordination windows must come before `plan_prepositions` (overlaps T5). `coordinate_moving_head_plan` sets intensity and color the physical renderer ignores. The combined-show golden's moving-head half changes. | M–L | High |
| `eval-report` (`rerender.py`, `collect.py`, `extract.py:147-162`, `generator.py:439-476`, `physics.py`) | The metrics read normalized curves, `static_dmx` and `*_static_dmx` metadata. A port must read physical trajectories (degrees and normalized values) or the encoded frames. The physics checks duplicate what the profile-based renderer already enforces. | M (~1,000 lines touched) | Medium: metric meaning changes |
| Live `inject` / `regenerate` (F1) | `live_effects_from_segments` has to be rebuilt on `physical_run_requests`. Regeneration needs section-bounded runs and an answer for transactions at section edges. Physical renders emit far more effects (up to about 95k on 8 heads, `models.py:640`). | M for inject, L for regenerate | High; testing it needs xLights (owner-gated) |
| Deterministic selector and three-arm experiment (`deterministic_selector.py:154-171`, `:302-383`; `three_arm.py:888-892`) | Take the admitted set (the gate runs per song and rig) instead of `REGISTRY.list_all()`. An empty ladder must raise a typed error before any provider call, without relaxing constraints (F7). The legacy step color, shutter and gobo derivation is a no-op on the families. The analysis snapshot must carry the admission. Fold D12 in here. | M | Medium; this changes the fixed P2P-T13 protocol, so the owner is told |
| Checkpoints and caches | Drop `render_mode` from checkpoints (`stage.py:419`, `collect.py:51`). Saved plans that name legacy ids fail with "Template not found" (`pipeline.py:1628-1630`). Session ids re-key because the job dump changes. | S | Low; user-facing |
| Rigs without a profile | No default exists (F8). The user must supply, per fixture, a `FixtureCapabilities` (footprint, a default byte for every offset, axes with offsets, ranges, `travel_speed_per_s`, `latency_ms`, `settle_ms`, discrete states, visibility), a settled `moving_heads.initial_states` entry, and a unique non-blank model name (`render_policy.py:44-79`). | Docs S; any authoring aid is an owner call | High for adoption |
| Meter and rig coverage | 3/4 and 6/8 admit 4 of 7 families. Without topology or `position_index`, 3 families (target orbit, snap, flick), and the flick also needs a `flick` attribute preset. Without a dimmer axis, only the 2 cascades. If nothing is admitted, the run is refused (`pipeline.py:754-759`), and after C1 there is no fallback. | — | High; owner told |
| `scripts/validation/mh_xsq_validation.py` | Assumes value curves (`:257-346`). | S–M | Low |
| `show_metrics.py:245-304` | Trace-based. Physical traces target per-fixture models, and dark park runs may count as onsets. Not verified. | S | Uncertain |

## 4. Naming after cutover

Rule: rename only identifiers that name the mode, or that carry a qualifier freed by a deleted counterpart. Keep "physical" where it means physical units or data (`physical_profile`, `PhysicalValue`, `PhysicalChannelError`).

| Now | After |
|---|---|
| `mode`, `"physical_v2"` and `"legacy_v1"` literals, log and error strings | Removed. The `render_record["renderer"]` value and the fingerprint string `physical_v2.N+encoder.M` (`pipeline.py:1563`, `:1801`) become `renderer.N+encoder.M`. |
| `schema_version: Literal["3.0","3.1"]` | `Literal["3.1"]`, default `"3.1"`. A job that says "3.0" or names `moving_heads.mode` is then refused loudly, because the policy is `extra="forbid"`. |
| `PHYSICAL_RENDERER_REVISION`, `LEGACY_RENDERER_REVISION`, `LEGACY_BACKEND_ID` | `RENDERER_REVISION`; the legacy revision deleted; `BACKEND_ID`. |
| `moving_heads_physical/`, `PHYSICAL_TEMPLATE_DIR`, `DEFAULT_DATA_TEMPLATE_DIR`, `admit_physical_catalog`, `in_physical_catalog` | Move the families to `catalog/templates/moving_heads/`; one `TEMPLATE_CATALOG_DIR`; `load_template_catalog`; `in_template_catalog`. |
| `_render_physical`, `compile_physical_template`, `compile_physical_step`, `build_physical_sequence`, `export_physical_delivery`, `physical_cue_limits`, `check_physical_templates` | Inline into `render()`; `compile_template`; `compile_step`; `build_sequence`; `export_delivery`; `cue_limits`; `admit_templates`. Each name is freed by a deletion. |
| `REFERENCE_ARM_ID = "reference_legacy_v1"` | Follows the owner's decision on F6. |
| `"physical_v2"` tag in the 7 family JSONs | Drop the tag. It reaches the planner's template descriptions. |
| Step fields `physical_shutter`, `physical_color`, `movement.physical` and the rest | **Optional tier.** Flatten to the freed names. This changes the JSON format and `--template-dir` documents. Do it in the same release as F4, because the fingerprints change anyway. |

## 5. Cutover order (each step ends green on `make validate`)

**Before acceptance:**
- **P1** Move the rig builders from `tests/golden/harness.py:71-160` into `tests/support/`. Test-only.
- **P2** Gate additions D8 and D9 (`pipeline.py:545-777`). Bump `PHYSICAL_RENDERER_REVISION` if output changes.
- **P3** `motif_schedule.py`.

All three are independent and can run in parallel worktrees.

**After acceptance:**

| Step | Content | Owner files | Parallel? |
|---|---|---|---|
| C1.1a | `show` on physical (was T5a) | `show_cmd`, `show_wiring`, `show_stages`, `definitions/show.py`, `show_coordination` | Yes, alongside 1.1b–d |
| C1.1b | `eval-report` port | `reporting/evaluation/{rerender, collect, extract, generator, analyze, physics, continuity}` | Yes |
| C1.1c | Live `inject` and `regenerate` | `cli/main.py` live block, `api/xlights/injection.py` | Yes |
| C1.1d | Selector and three-arm port (D12 folded in); `reference_policy` per the owner | `deterministic_selector.py`, `three_arm*.py`, `reference_policy.py` | Yes |
| C1.2 | One atomic flip: remove `mode`, the schema switch and `transitions`; delete the legacy render, compile, handlers, libraries (except the F3 enums), builtins, legacy export and delivery, the audit, the legacy tests, goldens, baseline and registry records; delete `template-export` | Integrator only | No |
| C1.3 | Narrow the models: `ChannelValue`, `TemplateStep`, contexts, fixture legacy fields, JSON `geometry` removal | Integrator | No |
| C1.4 | Renames (§4) | Integrator | No |
| C1.5 | Docs, context, memories (superseded), catalog README, scripts | Writer | Yes, alongside C1.4 |

Then:
- **T1**, stacked directly on C1. It replaces the contract in place, edits the existing prompt packs, and deletes the F3 enums, `TransitionHint`, the `Intensity` field and the legacy intent.
- **T2**, the projection over the gate from P2.
- **T3a**.
- **T3b**, with T4 reduced to an arrangement extension of the selector ported in C1.1d.
- **T5**, which inherits physical `show` from C1.1a.

## 6. Owner-gated or irreversible items

| Item | What the owner must decide or be told |
|---|---|
| C0 acceptance | Precondition. The verdict stays `PENDING-OWNER` until given. |
| Accepted look (F9) | Approve superseding the memory and deleting `tests/golden/mh*` (6 directories, 4,015 lines), the 11 golden tests, and the `11_need_a_favor` baseline. Evaluations stay as history. |
| Legacy reference for Phase 5 (F6) | Either have the legacy arm rendered before C1 (needs real audio and xLights) or rescope Phase 5. |
| Fingerprints (F4) | The Phase 0 and Phase 1 pins change with no byte change. Approve and record. |
| Three-arm protocol | Its candidate set changes (D12). |
| Job files | `moving_heads.mode` and `"3.0"` are refused. Today `transitions` would be silently ignored (`JobConfig` is `extra="ignore"`). Decide whether to add `transitions` to `reject_removed_fields` (`models.py:746-764`), the existing rejection idiom, which is not a shim. |
| Fixture configs | A profile and initial states are required. Today `FixtureConfig` silently ignores unknown keys, which would cover the removed legacy fields. Decide reject or ignore. |
| Caches, plans and checkpoints | Session ids re-key, so re-runs pay for planning again. Old plans fail to render. |
| Commands | `template-export` is removed. `inject` and `regenerate` output changes; testing them is an xLights mutation. |
| Coverage | Some meters and rigs get no moving-head output after C1 (§3). |
| Permanent boundaries | P3-T4, P3-T7 and WhisperX are not touched. The "Live evidence" rows become history of the legacy renderer. |

## 7. What can be built before acceptance

P1–P3 above are safe: they are physical-only or test-only and survive the cutover.

Not safe: T1 and T3a (F2); any deletion; any rename that touches legacy code; the selector port (it has no mode switch, so it would become a second selector).

The C1.1a–c ports could be built now behind the existing `mode`: the code survives and only the legacy guard goes later. That is a judgement the owner should make, because of guardrail 9.

## Trade-offs

| Option | Pros | Cons |
|---|---|---|
| A. Consumer ports after acceptance (recommended) | No new branches on the existing switch; strictly follows guardrail 9 | C1 is longer, and live, show and eval stay legacy until then |
| B. C1.1a–c pre-built behind `mode` | Shrinks C1 and its risk | Temporarily widens the mode switch the owner wants gone |
| C. A single C1 commit | One review | Unreviewable size (~30k lines) and a hard bisect |

## References

- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/moving_heads/pipeline.py:155-208, 228-252, 1351-1569, 1924-2174`: legacy render, presets, transitions, fingerprint branch
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/moving_heads/compile/template_compiler.py:126-312, 315-733`: legacy and physical compile
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/models/context.py:102-194`: registry coupling (F5)
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/config/models.py:647-791`: mode, schema and transitions
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/config/render_policy.py:17-92`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/cli/main.py:340-471`: live guard and layout
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/api/xlights/injection.py:473-509`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/pipeline/show_stages.py:57-125`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/show_coordination.py:511-597`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/reporting/evaluation/rerender.py:98`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/reporting/evaluation/extract.py:147-162`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py:154-171`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/reference_policy.py:23-29`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/agents/sequencer/moving_heads/models.py:21-24, 224-227`
- `/Users/ondeck/work/github/twinklr-mh-true-up/packages/twinklr/core/sequencer/moving_heads/templates/data_loader.py:40-163`
- `/Users/ondeck/work/github/twinklr-mh-true-up/tests/config_effects_registry.py:268-283, 620-659, 690-2025, 2675-2703`
- `/Users/ondeck/work/github/twinklr-mh-true-up/tests/support/mh_true_up.py:23`
- `/Users/ondeck/work/github/twinklr-mh-true-up/tests/golden/harness.py:367-374`
- `/Users/ondeck/work/github/twinklr-mh-true-up/changes/2026_11_12_mh_true_up/plan/phase-3-arrangement.md:252-291`
- `/Users/ondeck/work/github/twinklr-mh-true-up/changes/2026_11_12_mh_true_up/plan/phase-5-evaluation.md:175`
- `/Users/ondeck/work/github/twinklr-mh-true-up/memories/decisions/mh-render-matches-pre-cleanup-look.md`
