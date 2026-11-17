---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# C1.2: the old moving-head renderer removed — 2026-11-16

C1.2 deletes the second moving-head renderer (`legacy_v1`), its switches and its
tests, so one render path remains: the physical renderer that `physical_v2` used to
select. The work is in the working tree of `feat/mh-true-up-p3` on top of `5d50580c`
(tag `mh-last-with-legacy-renderer`). Nothing is committed. No provider was called, no
xLights instance was touched, and no owner-local data was read.

**Authority.** Deleting the old renderer, its templates, its switches and the tests and
goldens that pin its output (including the `11_need_a_favor` baseline) rests on the
owner's look acceptance of 2026-11-16, "Look accepted, start the cutover"
(`implementation-brief.md:141`). `reference_policy.py` and its arm were deleted under
the integrator's note in `plan/phase-3-arrangement.md:596-601` ("The integrator will
delete it in C1.2 unless the owner says otherwise"); the owner has not ruled on it.

The encoded frames and delivered `.xsq` files are byte-identical to the tag on every
case checked. The render fingerprint changes everywhere, because the render policy's
dump lost its `mode` key and the fingerprint payload lost its `"transitions": null`
key. `PHYSICAL_RENDERER_REVISION` is not bumped.

## 1. Switches removed

- **`config/models.py`.** Removed `MHRenderPolicy.mode`, `JobConfig.transitions`,
  `TransitionConfig` and `require_schema_for_render_mode`. `schema_version` is now
  `Literal["3.1"]` with default `"3.1"`. `reject_removed_fields` refuses three things
  by name, each with what to do:
  - `transitions` gets "job field 'transitions' was removed with the old moving-head
    renderer ... Delete the key".
  - `moving_heads.mode` gets "job field 'moving_heads.mode' was removed: moving heads
    have one renderer, the one 'physical_v2' selected. Delete the key; ...".
  - `schema_version` "3.0" gets "job schema_version '3.0' is no longer accepted: ...
    Set schema_version to '3.1' or delete it; ...".

  These are tested in `tests/unit/config/test_mh_render_policy.py::test_keys_of_the_removed_renderer_are_refused_by_name`
  (through the model and through `load_job_config`), and in `test_config_inventory.py`'s
  loud-refusal cases.
- **`config/render_policy.py`.** Removed the legacy early return and
  `require_legacy_render`. The refusal reads "the moving-head renderer cannot render
  this rig: ...".

## 2. Mode branch sites

Each site in `plan/cutover-inventory.md` §2 is listed with what happened to it:

| Site (tag lines) | Outcome |
|---|---|
| `config/models.py:657-664`, `:754`, `:787-791` | Removed (§1). |
| `render_policy.py:39`, `:75-78`, `:81-92` | Removed (§1). |
| `data_loader.py:125-163` | `admit_physical_catalog(*, registry=REGISTRY)` takes no job and always admits. `DEFAULT_DATA_TEMPLATE_DIR` is deleted. |
| `pipeline.py:238`, `:1352`, `:1430`, `:1552-1567`, `:1801` | `render()` returns `_render_physical()`. `fingerprint()` is physical-only. `offered_template_ids(template_ids)` takes no job. The transitions and diagnostics paths are deleted. |
| `rendering_stage.py:369` | `RenderPreflightStage` has no legacy early return. `record_render` runs on every render. |
| `stage.py:419-421`; `collect.py:44-51` | The checkpoint no longer writes `render_mode`. `checkpoint_render_policy` is deleted, and `recorded_render` requires a render record. |
| `rerender.py:98` | `rerender_plan(..., recorded: RecordedRender)` is required. |
| `cli/main.py:324-329`, `:340-345`, `:451-471`, `:696-698` | The live branch is unconditional (`live_effects_from_sequence`). Removed: the legacy branch, the `--layout` legacy message, `load_builtin_templates` and the `template-export` dispatch. |
| `cli/show_cmd.py:78`; `show_wiring.py:142` | `show_cmd` admits the catalog and offers templates unconditionally. `show_wiring.py:142` held no branch at the tag (it is the docstring of `prepare_combined_show_pipeline`), so nothing changed there. The show's xLights model check stays in the `render_preflight` gate, as at the tag. |
| `template_compiler.py:157-166`; `step_compiler.py:69-73` | `compile_template` and `step_compiler.py` are deleted. |
| `physical.py:539-551` | Kept. This is the physical compile refusing a step without physical data, not a mode branch. Its message no longer says "render it under physical_v2". |
| `instances.py:118-124`; `groups.py:60`, `:161-174` | The descriptions and comments are corrected. |

Other branch sites removed:

- `pipeline/show_stages.py`: `_render_legacy`, the dispatch, `available_templates` and
  the `rendered_segments` state.
- `pipeline/definitions/show.py`: `available_templates` is no longer passed.
- `sequencer/show_coordination.py`: the legacy plan and segment coordination.
- `api/xlights/injection.py`: `live_effects_from_segments`, `regenerate_section` and
  section scoping.
- `deterministic_selector.py`: `admission` is required.
- `three_arm.py`: `admission` and `admission_sha256` are required.
- `show_metrics.py`: the `render is None` return.
- `show_manifest.py`: `render` is required.
- `generator.py`, `analyze.py`, `extract.py`, `plot.py`, `render.py`, `config.py` and
  `validate.py`: the curve-based report paths.
- `MHDiagnostic.control` and `DiagnosticCode` "legacy_ignored".
- The `requires_xlights` pytest marker.

**Messages naming a refused key.** The gate's two refusals (`pipeline.py:858`, `:867`)
said "moving_heads.mode 'physical_v2' would offer ..." and "... has no template ...";
they now read "the moving-head renderer would offer the planner templates this rig
cannot render: ..." and "the moving-head renderer has no template this rig can render,
...", matching `render_policy.py`. A sweep of `packages/` for `moving_heads.mode`,
`legacy_v1`, `transitions` and `schema_version` in messages finds no other message
telling the user to set a refused key: the remaining hits are the refusals themselves
(`config/models.py:689-706`). The `physical_v2:` log prefixes and the "physical_v2
applies ..." diagnostic (`pipeline.py:1364-1366`) name the renderer, not a key; they go
with the other renames in C1.4.

## 3. Deleted paths

`git diff --stat mh-last-with-legacy-renderer` (with the new pin test, without this
record) reports 349 files changed, +2,802 and −36,251: `packages/` 144 files, +520
−16,646; `tests/` 190 files, +2,178 −18,771; docs, README, catalog, scripts and
`pyproject.toml` 15 files, +104 −834. 220 files are deleted outright (25,837 lines):

| Group | Files | Lines |
|---|---|---|
| `sequencer/moving_heads/handlers/**` | 33 | 3,528 |
| `templates/builtins/**` (the 37 builtins and their package) | 38 | 3,705 |
| `templates/utils.py`, `templates/converter.py` | 2 | 97 |
| Compile: `channel_blender`, `intent_resolution`, `phase_offset`, `step_compiler`, `transition_detector`, `transition_planner`, `transition_segment_compiler` | 7 | 1,610 |
| `config/adapter.py`, `curves/dmx_conversion.py`, `curves/phase.py`, `agents/.../reference_policy.py`, `utils/fixtures.py` (its only importer was `XsqAdapter`) | 5 | 455 |
| `reporting/evaluation/{physics,continuity,compliance}.py` | 3 | 905 |
| `catalog/templates/moving_heads/` (3 legacy JSON templates and README) | 4 | 272 |
| `scripts/demo_moving_heads_pipeline.py` | 1 | 404 |
| Golden suite: 11 legacy test modules, `conftest.py`, `harness.py`, `xlights_client.py`, `mh4_*`/`mh8_reference` goldens | 92 | 6,510 |
| `tests/regression/baselines/11_need_a_favor.*` | 4 | 1,601 |
| Integration tests (all templates compile, handler params, scheduler coverage, transitions, legacy combined show, legacy show layout) | 6 | 1,295 |
| Unit tests of deleted code | 24 | 5,145 |
| `tests/support/mh_true_up.py` | 1 | 310 |

Trimmed in place:

- `libraries/{color,gobo,shutter,geometry,movement,dimmer}.py`: only the enums remain.
- `models/transition.py`: `BoundaryType`, `Boundary`, `TransitionPlan` and
  `TransitionRegistry` are gone.
- `export/dmx_settings_builder.py`: only `build_frame_settings` remains.
- `export/xsq_adapter.py`: `XsqAdapter` is gone; the physical model check and run
  requests remain.
- `delivery.py`: `build_sequence` and `export_delivery` are gone.
- `templates/library.py`: `register_template` is gone.
- `sequencer/models/context.py`: the seven handler registries are gone.
- `cli/template_cmd.py`: the `template-export` command is gone.

**Dead code removed** (each lost its last production caller in this deletion; checked
by grep, then by a token-level sweep of `packages/` and `scripts/` for symbols whose
code uses fell from more than zero at the tag to zero, rerun until it found nothing
new; tests that only exercised them went with them):

- `TemplateRegistry.unregister` (`templates/library.py`).
- `log_performance` and `get_renderer_logger` (`utils/logging.py`).
- `FixtureSegment.add_channel` (`channels/state.py`).
- `FixtureGroup.get_xlights_mapping` and `FixtureGroup.get_fixture`
  (`config/fixtures/groups.py`), with `test_get_xlights_mapping` and `test_get_fixture`.
  The fixture-effect snapshot now reads the xLights group mapping `twinklr run` hands
  the planner (`build_moving_head_graph`) instead.
- `BeatGrid.bar_span_ms` and `BeatGrid.get_beat_time_ms` (`timing/beat_grid.py`).
- `PanPose`/`TiltPose` `pose_id` and `norm_value` (`config/poses.py`).
- `ChannelTransitionOverrides.items`/`__getitem__` and `TransitionHint.is_snap`
  (`models/transition.py`). Methods and properties are not in the JSON schema, so the
  planner-facing schema is unchanged.
- `TemplateStep.has_physical_data` (`models/template.py`); its only caller was the
  deleted `step_compiler.py`.
- `DmxMapping.pan_fine`/`tilt_fine` and their private normalized storage
  (`config/fixtures/dmx.py`).
- `FixtureConfig.deg_to_pan_dmx`, `deg_to_tilt_dmx`, `clamp_pan` and `clamp_tilt`
  (`config/fixtures/instances.py`); their callers were the geometry handlers.
- `interpolate_linear` (`curves/sampling.py`); its caller was `curves/phase.py`. The
  curve-test fixture `simple_linear_points` went with its tests.

Not removed: `FixtureConfig.is_pan_in_bounds`, `is_tilt_in_bounds`,
`pan_deg_to_dmx_delta` and `tilt_deg_to_dmx_delta` had no caller at the tag either, so
this deletion did not orphan them; `XSQEmissionSession.emit` and the display
`TimingResolver.snap` likewise had no production caller at the tag.

**Grep evidence.** Searching `packages tests scripts docs README.md catalog Makefile
pyproject.toml` finds no hit for any of these:

- `templates.utils`, `templates.converter`, `template-export`, `template_export`,
  `channel_blender`, `intent_resolution`, `compile.phase_offset`, `step_compiler`,
  `transition_detector`, `transition_planner`, `transition_segment_compiler`
- `TransitionConfig`, `TransitionPlan`, `TransitionRegistry`, `XsqAdapter`,
  `config.adapter`, `dmx_conversion`, `curves.phase`,
  `evaluation.{physics,continuity,compliance}`, `reference_policy`, `utils.fixtures`
- `_render_legacy`, `require_legacy_render`, `LEGACY_RENDERER_REVISION`,
  `live_effects_from_segments`, `regenerate_section`, `coordinate_moving_head_*`,
  `export_delivery`, `build_sequence(`
- `tests.golden.harness`, `regen-goldens`, `requires_xlights`, `legacy_ignored`,
  `render_mode`, `demo_moving_heads_pipeline`

The remaining hits are not live references:

- `templates.builtins` and `load_builtin_templates` (2): display group builtins
  (`catalog/templates/builtins/`), which are unrelated.
- `11_need_a_favor`: song names in the validation script, its README and its test;
  and the qa-runbook sentence recording the baseline's removal.
- `mh_true_up` (1): the `tests/golden/README.md` link to this record.

## 4. Kept, with the importer that needs it

| Kept | Needed by |
|---|---|
| `GeometryType`, `MovementType`, `DimmerType` (`libraries/{geometry,movement,dimmer}.py`) | `sequencer/models/template.py`. The fields stay until C1.3, and removing them would change `TemplateDoc` dumps and so every fingerprint. |
| `ColorPreset`, `GoboPattern`, `ShutterPattern` (`libraries/{color,gobo,shutter}.py`) | `template.py`, `models/context.py` and the planner contract `agents/.../moving_heads/models.py`. Deleted in T1 (inventory F3). |
| `PanPose`/`TiltPose` enum values (`poses.py`) | `template.py` and `config/fixtures/instances.py`. Their helper properties are removed. |
| `LEGACY_BACKEND_ID` (`"xlights_dmx"`) | `identity.py` and `pipeline.py`. It is part of the fingerprint payload; renamed `BACKEND_ID` in C1.4. |
| `TransitionHint`, `ChannelTransitionOverrides`, `TransitionStrategy`, `enum.TransitionMode` | The planner contract's `transition_in` (T1). Their helper methods are removed. |
| `ChannelValue` legacy options and `channels/state.py`'s legacy-field refusal | C1.3 narrows `ChannelValue`. |
| `is_physical_template`, `_legacy_fields`, the physical compile's refusal of legacy data | Templates and `--template-dir` documents still carry the legacy fields until C1.3, so a document that sets them must still be refused. |
| `dmx_mapping` listing and the fixture legacy fields | C1.3. Their 36 ledger paths are reclassified (§6). |
| The selector's `unresolved` intent constant (`("shutter_events", "gobo_events")`) | The deterministic selector's projection (T1 replaces it). |
| `DmxSettingsBuilder.build_frame_settings` | `xsq_adapter.physical_run_requests`. |
| `StepCompileContext` `calibration`, `n_samples`, `template_defaults`; `TemplateCompileContext` `n_samples`, `intent` | Nothing reads them: the template compile writes the first three and `n_samples`, and `intent` is never set. They are kept only because C1.3 narrows the contexts; their docstrings now say so (`models/context.py`). |

## 5. Left for later tasks

- **C1.3** narrows the models:
  - `ChannelValue`, `FixtureSegment`, `TemplateStep` and the contexts;
  - the fixture legacy fields and their ledger records;
  - the JSON `geometry`;
  - the eval report models (`LegacyComparisonReport`, curve-era descriptions, the
    `not_reported` strings) and the physics/compliance/continuity models.
- **C1.4** does the renames in §4 of the inventory:
  - the `physical_v2:` log prefixes and the "physical_v2 applies ..." diagnostic;
  - the `"renderer": "physical_v2"` record value and the `physical_v2.N+encoder.M`
    revision string;
  - `LEGACY_BACKEND_ID`, `PHYSICAL_RENDERER_REVISION`, the catalog directory and
    `admit_physical_catalog`;
  - the `physical_v2` tags in the family JSON and the template docs.
- **C1.5** handles `context/`, `memories/`, `scripts/validation/_core/mh_xsq_validation.py`
  (it still assumes value curves) and its README.
- **T1** replaces the planner contract and deletes the F3 enums, `TransitionHint`, the
  `Intensity` field and the legacy intent (`legacy_intent_omitted`, `_normalize_legacy_input`).

## 6. Fingerprint change and byte proof

Every fingerprint changes for two reasons:

- `policy.model_dump()` no longer carries `mode`.
- The payload no longer carries `"transitions": null`.

The trace's diagnostics also lose `"control": null`.

**Byte matrix.** The gate's byte matrix was copied to the scratchpad and run on the tag
(from `git archive`) and on this tree. It covers 360 configs and 15,210 leaf
comparisons, with 2,160 differences. Every difference is one of these six fields:

- `render_a/fingerprint` and `render_b/fingerprint`;
- `render_a/record` and `render_b/record`, the record hash, which embeds the
  fingerprint and the policy;
- `render_a/files/song.xsq.trace.json` and `render_b/files/song.xsq.trace.json`, the
  trace hash, which embeds the fingerprint, the policy and the diagnostics.

Each field differs in all 360 configs. Normalized record and trace hashes (with
`render_fingerprint`, `policy.mode` and diagnostics `control` dropped) are identical in
all 360 configs. Every other field is identical: frames, segments, `.xsq`, `.xtiming`,
`.xmap`, and gate admissions and exclusions. A rerun on the final tree matches the
earlier run with 0 differences.

**Phase 1 request.** The script was rerun and its outputs compared with `cmp`:

| Case | Tag fingerprint | New fingerprint |
|---|---|---|
| `p1_linear_reveal` | `60e0d5eb4575eea28273e84c8b008c56a8879a410a584339f5ab9fe43f9411c7` | `70267891d1c3429c4b7cf5dd51a799fc439f8b2255c94e6740727be511a13145` |
| `p1_linear_reveal_48ch` | `b40905ecab2faca953644eff81f54daee9bf93e41fbad4f0c0ac19480779cc86` | `41dd84a9869892ab38b53c206bbfb8f1a0acea239092cfd1071f06175a4eefb8` |

The `.xsq`, `.xmap`, `.xtiming` and `fixtures.json` files are byte-identical. Each
`.xsq.trace.json` differs in exactly three leaves:

- `render/render_fingerprint`;
- `render/policy/mode`, which is absent now;
- `render/output/serialization_ms`, a wall-clock measurement (0.796 vs 0.806 ms).

**New output pins** (`tests/regression/test_mh_physical_pins.py`, 45 tests):

- Every family variant (base and each preset) is pinned on a steady and a varied grid,
  42 cases in all, by fingerprint and the SHA-256 of its encoded frames.
- One four-family plan on the varied grid also pins its delivered `.xsq` bytes.
- One gated plan renders under a hand-built gate result (`mirror_wings`' `narrow` not
  admitted, `mirror_wings` and `target_orbit` playing a preset as their effective
  variant), over the dark span 6000-7500 ms, with `reposition_fallback="preserve_aim"`,
  and pins its frames and delivered `.xsq`. Its frames and `.xsq` hashes were rendered
  from the tag (`git archive` into the scratchpad, the job carrying
  `mode: physical_v2`); the fingerprint is this tree's.

All 44 frame hashes and both `.xsq` hashes equal those rendered from the tag. A
mutation check changed one byte of the first encoded frame of every render; 44 of the
45 tests failed. The one that passed is the enumeration test, which checks only that
every variant has a pin.

**Combined-show golden.** The golden was replaced
(`tests/golden/test_combined_show_golden.py`, `fixtures/combined_show_drop*.json`):

- **Display:** byte-identical to the tag's golden. That covers effects, settings,
  palettes, media and duration, and trace entries (without shared-table indices).
- **Moving heads:** now physical. It uses `family_rig(("MH1",))`, `mirror_wings` and
  the show's dark spans, with fingerprint
  `19dd3c219de7842e268cbf581ff57fdbff63b6502104453e9c6f7e5c307a0406`, 195 effects,
  `effects_sha256` `6b5d28aa…811b` and `trace_sha256` `0dfeb0a4…bc5d`.
- **Trace header:** `schema_version` "twinklr-xsq-trace.v2" and
  `fallback_substitutions` 0, as in the tag's golden, are asserted.

`git diff --stat mh-last-with-legacy-renderer -- tests/regression/baselines/02_rudolph*`
is empty, and so is the diff of the display `.xsq` fixtures.

**Gate time.** `bench.py` was copied, with 8 heads, 120 bars and two rounds. The figures
are seconds, round 1 / round 2:

| Rig, tempo | Tag | This tree |
|---|---|---|
| zoomless, steady | 8.24 / 8.58 | 8.32 / 8.47 |
| zoomless, variable | 9.01 / 9.23 | 9.18 / 9.15 |
| zoom, steady | 11.69 / 11.78 | 11.58 / 11.75 |
| zoom, variable | 12.61 / 12.75 | 12.78 / 12.60 |

The differences are within noise, so the gate time has not regressed. Admissions are
unchanged (6 zoomless, 7 zoom).

**Ledger reclassification** (`tests/config_effects_registry.py`):

- **Removed paths:** `job.moving_heads.mode` and `job.transitions*` are added to the
  removed paths and the loud-refusal cases.
- **Invariant:** `job.schema_version` is now an INVARIANT_TEST.
- **Rig refusal:** `job.moving_heads` now points to the test that refuses a rig
  without profiles.
- **Fixture fields, identity only:** the 36 fixture fields only the old exporter read,
  and `fixture.xlights_semantic_groups` (no render code reads it since
  `get_xlights_mapping` went; `reconcile_live_layout` in `api/xlights/injection.py`
  still reads it for the `inject`/`regenerate` missing-groups warning), point to
  `test_fixture_field_of_the_removed_renderer_changes_identity_only[...]`. Each changes
  the fingerprint and leaves the frames unchanged.
- **Static entries corrected:** 98 static entries named tests this deletion removed,
  though a routing loop replaced each one: 38 named deleted files
  (26 `export/test_dmx_settings_builder.py`, 8 `handlers/test_parameterized_channels.py`,
  4 `compile/test_phase_offset.py`), 56 named three functions removed from
  `templates/test_data_loader.py` (54 `test_data_template_registers_and_renders`, one
  each for the phase-offset order and `aim_zone` tests), and 4 named
  `test_get_xlights_mapping`. Each now carries, as written, the disposition the loops
  give it, as do the identity-only entries above.
- **Guard:** the module keeps the entries as written (`_STATIC_EFFECTS`) and fails on
  import when any names a test file or function that does not exist. The identity-only
  loops assert that each entry as written equals its identity-only disposition rather
  than assigning it, and the generic fixture loop skips those paths, so an entry and a
  loop cannot disagree.
- **Template fields, identity only:** template `defaults`, `presets.defaults` and
  `presets.name` point to `test_template_field_of_the_removed_renderer_changes_identity_only[...]`.
- **Effect test:** `movement.intensity` is an EFFECT_TEST, and every template case
  either changes the physical compile or is refused by it.
- **Not protected:** `aim_zone` is no longer in the protected set.

## 7. Breaking changes

- A job naming `moving_heads.mode` (any value), `transitions`, or `schema_version`
  "3.0" is refused when it loads.
- A job without a `moving_heads` block now renders physically. `twinklr run`, `show`,
  `inject` and `regenerate` refuse, before planning, a rig in which any fixture lacks a
  `physical_profile` or a usable `moving_heads.initial_states` entry, or in which two
  fixtures share an xLights model name or one is blank. When the gate admits no family
  for the rig and song, the run is refused; there is no fallback renderer.
- The old renderer's fixture fields (`dmx_mapping.shutter_map`, `color_map`,
  `gobo_map`, `shutter_default`, the fine channels, `use_16bit_pan_tilt`,
  `inversions.{dimmer,shutter,color,gobo}`) are still
  accepted but have no output effect; they change only the render fingerprint. C1.3
  removes them, and from then a config naming them is refused.
  `xlights_semantic_groups` likewise has no render effect, but the live layout
  reconciliation behind `inject`/`regenerate` still reads it, so C1.3 must decide that
  reader with the field rather than simply remove it. This is an integrator
  deferral to C1.3 under guardrail 9 (the same cutover removes them; C1.3 is the step
  that narrows the models), not an owner decision.
- `--template-dir` documents without physical data are no longer offered to the
  planner (the gate refuses a run offered one). `--allow-template-overrides` now
  shadows catalog families, since the catalog is the only registry content.
  `twinklr template-validate` is unchanged: it validated in an isolated registry at the
  tag too, so it never checked builtin-id collisions; what changed is that a
  `--template-dir` document at run time now collides with catalog family ids, not the
  37 builtin ids.
- `twinklr run --layout` always runs the xLights model check (at the tag only a
  physical job did).
- Plan checkpoints no longer carry `render_mode`.
- The `twinklr template-export` command is removed.
- A plan checkpoint written by the old renderer has no `render` record and is refused
  by `eval-report`. A record whose policy names `mode` (the physical renderer wrote
  those while two renderers existed) is refused with its own message: the record was
  written while the job could choose between two renderers and no longer matches what
  this version computes; re-running the command that planned it records it again.
  There is no compatibility reading of the old record.
- A saved plan or checkpoint that names one of the 37 deleted builtin template ids no
  longer renders, because those ids are unknown.
- Session ids and live-plan job digests change for every job: the job dump lost `mode`
  and `transitions`. Planner caches are re-keyed, and `twinklr regenerate` refuses a
  live plan recorded before this change as stale until `twinklr inject` runs again.
- A show trace's `render` record is required.
- The section-scoped injection API (`regenerate_section`, `live_effects_from_segments`)
  is removed. Injection always reconciles every owned effect.

## 8. Checks run (this tree, this session)

- `uv run pytest tests -q --no-cov` on the final tree: 6,540 passed, 30 skipped,
  0 failed, 6,570 in all, against 7,233 at the tag. The deleted test files held 604
  tests (collected from the tag copy). The new pins add 45. The remaining 104 are cases
  removed from kept files: legacy-only tests, parametrizations over the deleted
  registries and builtins, the replaced combined golden, and the tests of the dead
  helpers removed in §3.
- `ruff check packages tests scripts` passes, and `ruff format` leaves no file to
  change.
- `mypy packages/twinklr` reports no issues in 648 source files.
- The byte matrix and the pin script were rerun after the fix round: 0 differences
  from the previous run, and the frames and `.xsq` hashes still equal the tag's.

## 9. `legacy` and `legacy_v1` hits that remain

`legacy_v1` remains only in tests, and each hit asserts its absence or its refusal:

- `test_mh_render_policy.py:54` and `test_session.py:174` check that a job naming it is
  refused.
- `test_live_injection_command.py:792` and `:810` check that the old renderer is never
  suggested.

`legacy` remains in these groups:

- **Planner-contract legacy intent (T1):** `agents/.../moving_heads/models.py`
  (`_normalize_legacy_input`, `legacy_intent_omitted`), `identity.py:113-123` (part of
  the plan dump, so of the fingerprint), `pipeline.py:1747`,
  `deterministic_selector.py:459`, `three_arm.py:792` and `heuristic_validator.py`. The
  same applies to `transition.py`'s `_normalize_legacy_*` input normalizers on
  `TransitionHint`.
- **Template and `ChannelValue` legacy fields (C1.3):** `compile/physical.py`
  (`_legacy_fields` and the refusals), `channels/state.py`,
  `export/frame_encoder.py:267`, `template.py:454` and `:610`, `pipeline.py:132`,
  `:629` and `:1334`, `template_compiler.py:139`, `config/fixtures/capabilities.py:5`
  and `docs/user-guide.md:316`.
- **Names renamed in C1.4:** `LEGACY_BACKEND_ID`.
- **Eval report content (C1.3):** `generator.py:451-469` (the `not_reported` reasons),
  `models.py:99`, `:124`, `:379` and `LegacyComparisonReport` (the three-arm comparison;
  F6).
- **Other meanings of the word:** audio profile and lyrics models, `agents/issues.py`,
  feature engineering, profiling, `formats/xlights/sequence/xmap.py`,
  `curves/registry.py`, `audio/structure/sections.py`, planning and theming models,
  the group template store, the recipe builder, the judge, the group planner, the asset
  catalog, the `GENIUS_CLIENT_TOKEN` fallback in `config/loader.py`, the planner-input
  shapes in `context.py`, `orchestrator.py` and `moment_cues.py`,
  `scripts/demo_recipe_pipeline.py`, `scripts/validation/**` (C1.5),
  `docs/pipeline_guide.md:279` and `:1118` (the feature-engineering corpus run), and
  `docs/qa-runbook.md:93` (retired config fields in general).
- **Tests:** tests of the physical compile refusing legacy steps and fields
  (`test_physical*.py`, `test_component_presets.py`, `test_entry_window.py`,
  `test_topology_phase.py`, `test_visibility.py`, `test_physical_values.py`,
  `test_frame_encoder.py`), the `_LEGACY_PRESET` preflight case, `LEGACY_BACKEND_ID` in
  identity tests, and unrelated uses (model retargeting, the feature store, profiling,
  curation and the template-name alias test).

## 10. Uncertainties

- **Docs outside the brief.** `docs/` pages outside the brief's list were not swept.
  `scripts/README.md` lost its row for the deleted demo script. `context/` and
  `memories/` still describe two renderers (C1.5).
- **Test-only conversion helpers.** `FixtureConfig.degrees_to_dmx`/`dmx_to_degrees`
  have had no production caller since before the tag; the fixture-effect snapshot still
  uses them as evidence that position and limit fields change behaviour. C1.3, which
  narrows the fixture models, should decide whether those paths keep that evidence.
