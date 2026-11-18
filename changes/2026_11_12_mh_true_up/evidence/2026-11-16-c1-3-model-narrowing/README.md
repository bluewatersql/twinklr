---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# C1.3: the shared models narrowed to the one renderer — 2026-11-17

C1.2 (`0ec65d47`) deleted the old moving-head renderer but left its fields in the shared
models. C1.3 removes them. A fixture file, template document or `--template-dir`
document that names one is now refused when it loads, with a message naming the key and
saying what to do. Nothing accepts such a key silently.

The work is in the working tree of `feat/mh-true-up-p3` on top of `0ec65d47`. Nothing is
committed. No provider was called, no xLights instance was touched, and no owner-local
data was read. Encoded frames, `.xsq`, `.xtiming` and `.xmap` are byte-identical to
`0ec65d47` (§6). Render fingerprints change, because the template and rig dumps they hash
lost the removed fields. `PHYSICAL_RENDERER_REVISION` is not bumped.

Paths are under `packages/twinklr/` unless they start with another top-level directory.
"Grep" means `git grep` over `packages scripts docs README.md catalog Makefile
pyproject.toml`; each result below is from the final tree.

## 1. What was removed, per scope item

### 1.1 `ChannelValue` and `FixtureSegment` (`sequencer/moving_heads/channels/state.py`)

- **`ChannelValue` fields removed:** `static_dmx`, `curve`, `value_points`, `base_dmx`,
  `amplitude_dmx`, `offset_centered`, `blend_mode`, `clamp_min` and `clamp_max`.
  `physical` is now required. The value keeps one validator, which checks the
  trajectory's unit against the channel.
- **Legacy-field refusal removed:** `_validate_physical`'s refusal of legacy fields beside a
  physical value is deleted. With `extra="forbid"` the fields cannot be set, so a payload
  naming one fails with pydantic's "Extra inputs are not permitted".
- **`FixtureSegment.allow_grouping` removed.**
- **Dead "not a physical value" branches removed:** they were in `slice_physical_segment`
  (`compile/physical.py`), `_checked` (`compile/preposition.py`), `quantized_cues` and
  `encode_fixture_frames` (`export/frame_encoder.py`).
- **`sequencer/models/enum.py::BlendMode` deleted.** `state.py` was its only production
  importer. The display `BlendMode` in `sequencer/vocabulary` is a different enum and is
  untouched.
- **Grep:** `static_dmx`, `value_points`, `base_dmx`, `amplitude_dmx`, `offset_centered`,
  `clamp_min`, `clamp_max`, `allow_grouping` and `models.enum import BlendMode` all have
  0 hits. A `static_dmx` field of `CurveAnalysis` was also removed (§1.6).

### 1.2 Templates (`sequencer/models/template.py`)

Removed fields:

| Model | Removed |
|---|---|
| `TemplateStep` | `geometry`, `color`, `shutter`, `gobo` |
| `Movement` | `movement_type`, `intensity`, `cycles`, `params`; `physical` is now required |
| `Dimmer` | `dimmer_type`, `intensity`, `min_norm`, `max_norm`, `params` and the min/max validator; `physical` stays optional |
| `StepTiming` | `phase_offset` |
| `Template` | `defaults` |
| `TemplatePreset` | `name`, `defaults` |
| `StepPatch` | `geometry`, `color`, `shutter`, `gobo` |

Removed models and libraries:

- **Models deleted:** `Geometry`, `Color`, `Shutter`, `Gobo`, `PhaseOffset` and
  `PhaseOffsetMode`.
- **Library modules deleted:** `libraries/geometry.py`, `libraries/movement.py` and
  `libraries/dimmer.py`. `template.py` was the only importer of `GeometryType`,
  `MovementType` and `DimmerType`.
- **Enum deleted:** `sequencer/models/enum.py::AimZone`. `Geometry` was its only user.
- **Module deleted:** `config/poses.py`, all 240 lines (`PanPose`, `TiltPose`,
  `PoseLibrary`, `STANDARD_POSES`, `resolve_pose`, `PoseConfig`). Its importers were
  `Geometry` and `FixtureConfig.get_standard_pose`, both removed.
- **Grep:** `GeometryType`, `MovementType`, `DimmerType`, `libraries.geometry`,
  `libraries.movement`, `libraries.dimmer`, `AimZone`, `PhaseOffset`, `config.poses`,
  `PanPose`, `TiltPose`, `PoseLibrary` and `STANDARD_POSES` all have 0 hits.

The `ColorPreset`, `GoboPattern` and `ShutterPattern` enums stay. The planner contract
still imports them (`agents/sequencer/moving_heads/models.py:22-24`), and T1 deletes them.

**Validators simplified.** `movement.physical` can no longer be absent, so these checks no
longer test for it: `TemplateStep._validate_visibility`, `_validate_zoom`,
`_validate_pose_source` and `Template._require_finite_steps`.

**Physical compile (`compile/physical.py`):** removed `is_physical_template`,
`_legacy_fields`, `_non_default_fields`, and `_require_physical_step`'s two refusals
("has no movement.physical data" and "sets legacy ..."). They are now model invariants:

- `movement.physical` is required.
- The legacy fields cannot be set.
- A template always has a step. `RepeatContract` needs a loop step id and `Template`
  checks that each one names a step.

The old message "Legacy normalized curves are never reinterpreted" goes with them.

**`offered_template_ids` (`pipeline.py`) deleted.** It filtered `is_physical_template`,
which now holds for every template that loads. Its callers and changes:

- **Callers updated:** `cli/main.py`, `cli/show_cmd.py` and
  `RenderPreflightStage.execute`. The stage's "would offer the planner templates
  without physical data" refusal went with it.
- **Empty-offer refusal moved into the gate.** The function also refused an empty offer.
  That refusal now lives in `check_physical_templates`, which previously admitted nothing
  silently when offered nothing (`if template_ids and not admitted` became
  `if not admitted`). The message ends "none is loaded".
- **Where it is caught:** it is now caught right after audio analysis and before any
  planner or provider request, not before analysis.
- **Test:** `test_render_preflight_stage.py::test_a_job_offered_no_template_is_refused_before_planning`.

**`compile/preset.py`.** `apply_step_patch` merges only `movement`, `dimmer` and `timing`,
and `apply_preset` no longer merges `defaults`.

**Family JSON (`catalog/templates/moving_heads_physical/*.json`).** In all 7 families,
`"geometry": {}` is gone from each step and `"name"` from each preset (21 lines). Each
file was checked to equal the old document minus those keys. The `"dimmer": {}` of the
two cascades stays: `dimmer` is still a step field.

**Grep:** `is_physical_template`, `_legacy_fields`, `_non_default_fields` and
`offered_template_ids` all have 0 hits.

### 1.3 Compile contexts (`sequencer/models/context.py`)

- **Removed fields:**
  - `FixtureContext.calibration`.
  - `StepCompileContext.calibration`, `template_defaults` and `n_samples`.
  - `TemplateCompileContext.n_samples` and `intent`.
- **Removed models:** `SectionRenderIntent` and `TimedChannelIntent`. `intent` was their
  only user.
- **Writers removed:**
  - `compile_physical_template` wrote `calibration`, `template_defaults` and `n_samples`
    (`compile/template_compiler.py`).
  - `build_fixture_contexts` built the calibration dict, including
    `calibration["fixture_config"]` "for degree→DMX conversion in geometry handlers"
    (`fixture_builder.py`).
- **Rig calibration:** these writes were the only consumers of the rig's calibration, so
  these were removed from `sequencer/models/moving_heads/rig.py`:
  - `FixtureCalibration`;
  - `FixtureDefinition.calibration` and its default validator;
  - `RigProfile.default_dimmer_floor_dmx` and `default_dimmer_ceiling_dmx`;
  - `rig_profile_from_fixture_group`'s `dimmer_floor_dmx` parameter.

  `rig.py`'s `FixtureCalibration` was the only production reader of
  `FixtureConfig.limits`.
- **Rig leftovers (review fix round):** `SemanticGroup.order` (written as the constant
  `LEFT_TO_RIGHT` on every group, read by nothing) and the `ChaseOrder` enum
  (`sequencer/models/enum.py`; `order` and the deleted `PhaseOffset` were its only users)
  are removed. So are `rig_profile_from_fixture_group`'s unused `infer_orders` and
  `infer_roles` parameters (no caller passed them) and the docstring's "phase offset
  spreading". The `RigProfile` is not hashed into any fingerprint (the fingerprint hashes
  the `FixtureGroup`) and is not shown to the planner, so no fingerprint or pin moved for
  this (§6.4, §10).
- **Kept:** `FixtureContext.role` and `StepCompileContext.role`. The step context's
  `role` is required and set from the fixture context; target groups use the fixture
  context's role. The other registries went in C1.2.
- **Grep:** `SectionRenderIntent`, `TimedChannelIntent`, `template_defaults`,
  `FixtureCalibration`, `default_dimmer_floor_dmx` and `dimmer_floor_dmx` all have
  0 hits. `n_samples` hits remain only in `curves/` (the curve generators), in
  feature engineering (`train_samples`) and in `docs/feature_engineering`.

### 1.4 Fixture configuration (`config/fixtures/`)

Removed fields:

| Model | Removed |
|---|---|
| `DmxMapping` | `pan_fine_channel`, `tilt_fine_channel`, `use_16bit_pan_tilt`, `shutter_default`, `shutter_map`, `color_map`, `gobo_map` |
| `FixtureConfig`, `BaseFixtureConfig` | `inversions`, `pan_tilt_range`, `orientation`, `limits` |
| `FixturePosition` | `pan_offset_deg`, `tilt_offset_deg`; `position_index` stays |
| `FixtureGroup` | `xlights_semantic_groups` (§1.5) |

Removed classes and helpers:

- **Classes:** `ShutterMap`, `ChannelInversions`, `PanTiltRange`, `Orientation`,
  `MovementLimits` and the fixture `Pose` model.
- **Helpers:** `FixtureConfig.get_standard_pose`, `dmx_to_degrees`, `degrees_to_dmx`,
  `_degrees_to_raw_dmx`, `is_pose_safe`, `is_pan_in_bounds`, `is_tilt_in_bounds`,
  `pan_deg_to_dmx_delta` and `tilt_deg_to_dmx_delta`; `FixturePosition.apply_offset` and
  `remove_offset`.
- **No production caller:** none of these methods had a production caller at
  `0ec65d47`, and `degrees_to_dmx`/`dmx_to_degrees`/`apply_offset` had none at the tag
  `mh-last-with-legacy-renderer` either.
- **The old renderer's readers:**
  - `inversions.{pan,tilt}`: `config/adapter.py` and `export/dmx_settings_builder.py`.
  - `orientation` and `pan_tilt_range`: `deg_to_pan_dmx`/`deg_to_tilt_dmx`, which the
    geometry handlers called.
  - `limits`: `diagnostics.py`, and the calibration above.

  All of these were deleted in C1.2. Each has had no production reader since then (grep
  at `0ec65d47`).
- **`pan_offset_deg`/`tilt_offset_deg`:** these had no production reader at the tag
  either. Their only readers were `apply_offset`/`remove_offset`, which nothing called.
  They are removed as orphans of that deletion, with their own refusal message (§5).
- **Exports:** removed from `config/fixtures/__init__.py` and `config/__init__.py`.
- **Grep:** `ShutterMap`, `ChannelInversions`, `PanTiltRange`, `Orientation`,
  `MovementLimits`, `get_standard_pose`, `degrees_to_dmx`, `dmx_to_degrees`,
  `is_pose_safe`, `is_pan_in_bounds`, `deg_to_dmx_delta`, `apply_offset` and
  `remove_offset` all have 0 hits.

`config/fixtures/physical.py` now holds only the retired- and removed-field handling:

- `drop_retired_fields`, unchanged.
- The `REMOVED_*_FIELDS` sets.
- `reject_removed_fields` and `reject_removed_position_fields`, the new refusal helpers.

The other remaining grep hits for the removed keys are the refusals themselves
(`config/fixtures/physical.py`, `groups.py`) and `docs/user-guide.md:314`, which documents
them. `scripts/validation/_core/mh_xsq_validation.py:110` and `:553` still read
`xlights_semantic_groups` from raw fixture JSON; that script is C1.5's (§8).

A stale comment in `config/models.py`, the P1P-T6 note, was deleted. It justified
deleting `ChannelDefaults` by pointing at `DmxMapping.shutter_default`/`color_map`/
`gobo_map` "at the layer the exporter actually reads from". Neither those fields nor that
exporter exists now.

**Kept:**

- **`dmx_mapping`, required, with `pan_channel`, `tilt_channel`, `dimmer_channel`,
  `shutter_channel`, `color_channel` and `gobo_channel`.** The planner reads these
  numbers: `cli/main.py:338-345` and `pipeline/definitions/show.py:70-80` list them to
  the moving-head planner as `fixture_groups`. Removing them would change what the
  planner is shown, which is out of scope (T1).
- **`position.position_index`.** `rig_profile_from_fixture_group` orders the rig by it
  (`rig.py`), and the topology derives a row from it (`models/moving_heads/topology.py`).
- **`physical_profile`.**

The planner-visible bytes are unchanged (§6.4).

**Test-only helpers and the snapshot.** `degrees_to_dmx`/`dmx_to_degrees` are deleted.
The fixture-effect snapshot (`test_effect_discriminators.py::_fixture_snapshot`) used them
as evidence that orientation, range, limit and inversion fields "change pose
conversion". It now holds only production seams:

- the xLights group mapping `twinklr run` hands the planner (`build_moving_head_graph`);
- the rig profile that `build_fixture_contexts` reads (its order);
- each fixture's model name and the planner's channel listing.

The paths it covered that still exist all change that snapshot. Its `config_overrides`
alternative was `{"inversions": ...}`, which is now refused; it now overrides
`dmx_mapping`.

### 1.5 `fixture.xlights_semantic_groups`: removed, with its reader

`reconcile_live_layout` (`api/xlights/injection.py`) did two things with it:

- It reported each configured semantic group that was missing from the live layout under
  `missing-groups`.
- It filtered the reconciled rig's copy.

**The reader was vestigial.** Nothing on the current path writes to or reads those groups:

- The render writes each head's own model (`physical_run_requests`).
- The planner's xLights mapping names only `xlights_group` (`build_moving_head_graph`).
- No production code reads the reconciled rig's semantic groups.

The warning therefore reported a divergence with no consequence. The field and both uses
are removed. `missing_configured_groups` still reports `xlights_group` when the live
layout lacks it, and `test_injection.py:79` covers that. `FixtureGroup` refuses the key by
name (§5).

### 1.6 Evaluation report models (`reporting/evaluation/models.py`)

Removed, each produced as a constant `None`, an empty list or not at all:

- **Summary counts:** `ReportSummary.physics_violations`, `compliance_issues` and
  `harsh_transitions`, always `None`.
- **Curve statistics:** `CurveStats.clamp_pct`, always `None`.
- **Curve fields:** `CurveAnalysis.continuity`, `curve_type`, `handler`, `base_position`,
  `static_dmx` and `physics_check`, always `None`.
- **Section fields:** `SectionReport.template_compliance` and `transition_to_next`,
  always `None`.
- **Template steps:** `TemplateSelection.steps`, always `[]`.
- **`not_reported`:** `PhysicalRenderSummary.not_reported` and its source
  `generator.NOT_REPORTED_FOR_PHYSICAL`, the curve-era list. `report.md` loses its
  "Not reported for physical output" section.
- **Models:** `ContinuityCheck`, `StepConfig`, `PhysicsCheck`, `ModifierCompliance`,
  `TemplateCompliance`, `TransitionAnalysis`, `ComparisonMetrics` and
  `LegacyComparisonReport` (no importer; the three-arm `ComparisonReport` is a different
  model and stays).

Narrowed:

- **Required now:** `EvaluationReport.physical` and `SectionReport.render_facts` were
  `X | None` with `exclude_if=None`, and the generator always sets both. When present they
  dump exactly as before.
- **Unconditional now:** `cli.py`'s and `render.py`'s `is not None` checks on them.
- **Descriptions corrected:** `CurveAnalysis.space` and `CurveStats.energy` lost their
  curve-era ("legacy curves") wording. The `PhysicalRenderSummary` docstring was
  corrected too.

**Grep:** all of these names have 0 hits: `LegacyComparisonReport`, `ComparisonMetrics`,
`ContinuityCheck`, `PhysicsCheck`, `ModifierCompliance`, `TemplateCompliance`,
`TransitionAnalysis`, `StepConfig`, `not_reported`, `NOT_REPORTED`, `physics_violations`,
`compliance_issues`, `harsh_transitions` and `clamp_pct`.

**Kept:**

- **`ReportSummary.max_concurrent_layers`.** It is always 0 (`# TODO: compute`), but it
  is not an old-renderer field.
- **`SectionReport.segments`** (always `None`) **and `TargetResolution.bindings`**
  (always `{}`). They are plan structure, not old-renderer output.

These are listed for the integrator (§9).

### 1.7 Orphan sweep

Two token-level sweeps compared the baseline tree (`git archive 0ec65d47`) with the final
tree.

**First sweep.** The C1.2 reviewer's scripts (`c12rev/scripts/{dead,orphans,deadconst}.py`)
were rerun on both trees. They report symbols with at most one token, and modules nothing
imports. Each found nothing new in the final tree; the dead lists shrank by 13 and 43.

**Second sweep** (`c13/fell_to_zero.py`). It takes every top-level def, class and
assignment, and every class-body name in `packages/`. It reports any whose uses outside
its definition (tokens in `packages/`, `scripts/` and `pyproject.toml`) were more than 0
at the baseline and 0 now. It found nothing.

A check of names defined only in the new tree that have no other token finds only
`ChannelValue._validate_unit`. It is a pydantic validator, called through its decorator.

Removed as orphans of this narrowing, each found by grep and then confirmed by the
sweeps: `BlendMode` (sequencer enum), `AimZone`, the three library modules,
`config/poses.py`, `SectionRenderIntent`, `TimedChannelIntent`, `FixtureCalibration` and
`offered_template_ids`.

## 2. Tests

Each test was removed only where what it exercised was deleted. The refusals that replace
the deleted ones are tested.

**Before and after:** 6,570 tests collected at `0ec65d47` and 6,521 now, a net change of
−49. Collected ids that went: 155; new: 106.

The 155 that went:

| Count | Test | Why |
|---|---|---|
| 37 | `test_fixture_field_of_the_removed_renderer_changes_identity_only[...]` | Its fields are removed |
| 28 | `test_fixture_field_changes_shipped_behavior_snapshot[...]` | Paths of removed fields (inversions, range, orientation, limits) |
| 26 | `test_template_compile_field_changes_emitted_snapshot[...]` | Removed template paths. The `steps.movement` and `steps.dimmer` ids stay, now on physical mutations |
| 15 | `test_physical.py::test_legacy_data_beside_physical_data_is_rejected` | Compile refusal deleted; the model refuses instead (below) |
| 9 / 26 | `test_retired_template_config_fails_loudly_with_migration_message` | Auto-generated ids renumbered: 9 old ids went and 26 now exist. 5 old cases are kept, 4 for deleted models went (`PhaseOffset`, `Color`, `Shutter`, `Gobo`), and 21 C1.3 cases were added |
| 7 + 1 + 1 | `test_physical_values.py` legacy-option tests | Replaced by `test_the_old_renderer_value_fields_are_refused` (9) and `test_a_channel_value_is_a_physical_value` |
| 4 + 3 | Template preset discriminators and identity-only template cases | Removed paths |
| 4 + 2 + 1 + 1 + 7 | `test_fixtures.py`: offsets, `avoid_backward`, `Pose`, pose library, and seven tests of `degrees_to_dmx`, `dmx_to_degrees` (two), the standard pose, calibration, pose safety and the safety-limits workflow | Deleted methods and fields |
| 3 | `test_physical.py` legacy circle, defaults round trip; `test_frame_encoder.py` legacy value | Deleted branches |
| 1 | `test_config_inventory.py::test_retired_fixture_config_loads_with_a_warning[...]` (`orientation.tilt_up_dmx`) | `orientation` itself is now refused |
| 1 | `test_reporting/test_models.py::TestContinuityCheck` | Became `TestCurveAnalysis` |
| 1 | `test_mh_physical_pipeline.py::test_failure_delivers_nothing[template-without-physical-data]` | That template cannot load now |
| 1 + 1 | `test_render_preflight_stage.py`: offered without physical data; `preset-adds-legacy-data` | The first's filter is deleted. The second case cannot reach the gate now: a preset patch naming a removed key is refused when its document loads, naming the preset and step (`test_a_step_patch_naming_a_removed_field_is_refused_when_the_document_loads`) |
| 1 | `test_live_injection_command.py::test_run_refuses_a_physical_job_when_no_template_has_physical_data` | Its refusal moved to the gate, tested by `test_a_job_offered_no_template_is_refused_before_planning` |

The 106 new:

- **48** `test_removed_config_path_is_absent_from_public_schema` cases, for the C1.3
  paths.
- **17** `test_fixture_config_of_the_removed_renderer_is_refused_by_name`. Each removed
  fixture key is refused by name: in `base_config`, in a full fixture's `config`
  (including its `dmx_mapping`), in `config_overrides` (including `position` there), in
  `position`, and at group level.
- **3** `test_a_step_patch_naming_a_removed_field_is_refused_when_the_document_loads`
  (`movement`, `dimmer`, `timing`), through `load_template_document`, asserting the
  preset id and the step id.
- **26** renumbered loud-refusal ids, above.
- **9 + 1** `test_physical_values.py`.
- **1** `TestCurveAnalysis`.
- **1** `test_a_job_offered_no_template_is_refused_before_planning`.

**Ported, not removed:**

- Tests that used a legacy step only as a vehicle now build a physical step:
  - the "absent from dumps" tests in `test_physical.py`, `test_physical_discrete.py`,
    `test_topology_phase.py`, `test_visibility.py`, `test_entry_window.py` and
    `test_component_presets.py`;
  - `test_component_refs_are_physical_data`;
  - `test_data_loader.py`;
  - `test_repeat_contract_validation.py`.
- `test_discrete_physical_data_alone_is_not_a_physical_step` now asserts the model's
  "movement.physical Field required".
- `test_render_identity.py::test_preset_content_changes_the_hash` now edits a step patch
  instead of the removed `defaults`.
- `test_physical_report.py` now asserts that every removed report key is absent from
  `report.json` and `report.md`, instead of `null`.

**Test data:**

- **Orphan fixtures deleted:** `tests/fixtures/{fan_pulse_template,
  example_rig_4fixtures}.json` and `tests/fixtures/templates/test_sweep_pulse.json`. They
  are legacy-shaped and nothing references them. `git grep` finds them only in
  `plan/cutover-inventory.md`, which listed them for deletion.
- **`tests/conftest.py`:** `mock_fixture_instance` and `mock_fixture_group` were removed.
  Nothing used them, and they imported `config.poses` and two modules that do not exist.
- **`tests/support/mh_physical.py::_fine_carry_rig`:** no longer sets fine channels or
  inversions. The 16-bit and inverted behaviour is in the profiles `physical_rig` adds.

**Config ledger (`tests/config_effects_registry.py`).** 655 entries became 551: 444
effect tests became 340, while the 204 removed and 7 invariant entries are unchanged.

- **Rows removed: 104**, every non-`REMOVED` entry whose path the models no longer
  declare:
  - 33 for `fixture.base_config`;
  - 35 for `fixture.fixtures[FixtureInstance].config`: the same 33 fields plus the 2
    position offsets;
  - 2 for `fixture.fixtures[SimplifiedFixtureInstance].position`;
  - 1 for `fixture.xlights_semantic_groups`;
  - 33 for `template`.

  This follows C1.2's convention: the paths join `REMOVED_CONFIG_PATHS` and the loud-refusal
  cases in `test_config_inventory.py`.
- **Code removed with them:**
  - the identity-only loops (`_OLD_RENDERER_FIXTURE_FIELDS`, `_OLD_RENDERER_FIXTURE_PATHS`,
    `_IDENTITY_ONLY_REASONS`, the template identity-only branch);
  - the identity-only test functions in `test_effect_discriminators.py` and
    `test_template_effect_discriminators.py`.
- **Protected paths:** `PROTECTED_EXACT_EFFECT_PATHS` is now only
  `job.timeline_tracks.sections` (§9).
- **Notes corrected:** 18 notes said a path "changes ... pose conversion"; 32 said "the
  physical compile refuses its non-default value". Both are untrue now and were corrected.
- **Guards pass:**
  - the import guard (no ledger entry names a missing test);
  - `test_every_external_config_path_has_an_accountable_disposition`;
  - `test_registered_effect_and_invariant_nodeids_collect`.

## 3. Kept, with its live reader

| Kept | Live reader |
|---|---|
| `dmx_mapping` primary channels | The planner's `fixture_groups` listing (`cli/main.py:338-345`, `pipeline/definitions/show.py:70-80`) |
| `FixturePosition.position_index` | `rig_profile_from_fixture_group` ordering; topology row derivation |
| `Dimmer` with only an optional `physical` | Every step's `dimmer`; the cascades carry `"dimmer": {}` (a visibility envelope replaces the dimmer) |
| `ColorPreset`, `GoboPattern`, `ShutterPattern`, `Intensity`, `TransitionHint` | The planner contract (T1) |
| `drop_retired_fields` for the P4 keys (`dmx_universe`, `dmx_start_address`, `channel_count`, `capabilities`, `movement_speed`, channel `config`) | Fixture files written before 2026-08 still load with a warning; that was an earlier owner-facing decision, not part of C1.3 |
| `ReportSummary.max_concurrent_layers`, `SectionReport.segments`, `TargetResolution.bindings` | Not old-renderer fields (§1.6, §9) |

## 4. Fingerprint changes and their cause

Every render fingerprint changes, because two inputs the payload hashes changed
(`sequencer/moving_heads/identity.py::render_fingerprint`):

- **`templates`:** each `TemplateDoc.model_dump`. It lost the removed step fields, which
  dumped at their defaults on every step, `Template.defaults`, and the preset `name` and
  `defaults`.
- **`fixtures`:** the `FixtureGroup.model_dump`. It lost the removed fixture fields,
  which dumped at their defaults on every fixture, and `xlights_semantic_groups`.

The render record's `template_sha256` values change for the same reason. The policy dump
is unchanged. `PHYSICAL_RENDERER_REVISION` is not bumped.

For three rigs (`physical_rig`, `family_rig`, `zoom_rig`), the baseline dump minus the
removed keys equals the new dump exactly (`c13/rig_dump_cmp.py`).

Re-recorded:

- **`tests/regression/test_mh_physical_pins.py`:** all 44 fingerprints, through
  `c13/repin.py`. It checks first that every frames hash and both `.xsq` hashes equal the
  pinned ones, and writes only if they do. All 44 frames hashes and both `.xsq` hashes
  were unchanged.
- **`tests/golden/fixtures/combined_show_drop.json`:** the fingerprint `19dd3c21…0406`
  became `46767038c9f517ff12875e582b6fd1870516e7d9a1c52c1ff4ff289500f087b0`. The effect
  count (195), `effects_sha256`, `trace_sha256`, display effects and display trace are
  equal (`c13/golden_snap.py`).
- **`tests/unit/sequencer/moving_heads/export/test_optical_axis.py`:** the `rig` dump hash
  `bd9e604b…c775` became `93ffb351c0110e3208a9dcd7f161e296a04ebb117f57005354eeb6b065a6f192`.
  The profile, head and initial-state dumps and the word hash are unchanged.
- **Phase 1 request** (`c13/p1_request.py`, both trees). The `.xsq`, `.xmap` and
  `.xtiming` are byte-identical. Each trace differs in three leaves: `render_fingerprint`,
  `template_sha256/p1_linear_reveal`, and the wall-clock `serialization_ms`.
  `fixtures.json` differs only by the removed keys.

  | Case | `0ec65d47` | Now |
  |---|---|---|
  | `p1_linear_reveal` | `70267891d1c3429c4b7cf5dd51a799fc439f8b2255c94e6740727be511a13145` | `50e6b255a06c3bdf1d523107ddf84f242ed7300a9ffd6cb312bb66bc16a9d4df` |
  | `p1_linear_reveal_48ch` | `41dd84a9869892ab38b53c206bbfb8f1a0acea239092cfd1071f06175a4eefb8` | `7a96d383cdc4a3fe81844ca4264a41ee588987e7d9b04eb09b12d96a19015315` |

  The fixture `p1_linear_reveal.json` lost its `"geometry": {}`.

## 5. Breaking changes

Every key below is refused when its file loads: `load_fixture_group`,
`load_template_document`, `--template-dir` and `template-validate`. The user sees the
message shown.

**Fixture file** (`FixtureGroup`):

| Key | Message (pydantic prefixes "Value error, ") |
|---|---|
| `base_config.{inversions,pan_tilt_range,orientation,limits}`, the same in a full fixture's `config` | `fixture fields ['limits'] were removed with the old moving-head renderer, their only reader; delete them. The renderer reads each fixture's physical_profile` (in a full fixture's `config`: `fixture 'MH1' fields [...]`) |
| `dmx_mapping.{pan_fine_channel,tilt_fine_channel,use_16bit_pan_tilt,shutter_default,shutter_map,color_map,gobo_map}` | `dmx_mapping fields ['shutter_map'] were removed with the old moving-head renderer, their only reader; delete them. ...` (in a full fixture's `config`: `fixture 'MH1' dmx_mapping fields [...]`) |
| A simplified fixture's `config_overrides` naming any of the above | `config_overrides fields [...] ...` / `config_overrides.dmx_mapping fields [...] ...` |
| A simplified fixture's `config_overrides.position` (any content) | `config_overrides field 'position' never took effect: each fixture's position is its own `position`, which replaces it. Move it there`. `expand_fixtures` set `config_dict["position"] = fixture.position` after applying the overrides, so it never had an effect, before or after this change |
| `position.{pan_offset_deg,tilt_offset_deg}` | `position fields ['pan_offset_deg'] were removed: nothing read them; delete them` (in a full fixture's `config`: `fixture 'MH1' position fields [...]`). For a simplified fixture, pydantic also reports the `fixtures` union's other branch (`config` "Field required") |
| `xlights_semantic_groups` | `fixture group field 'xlights_semantic_groups' was removed: nothing renders to those groups. Delete it; xlights_group names the group of every head` |

**The `fixtures` union.** A full fixture whose `config` named a removed key would fail as
a `FixtureInstance`. The `fixtures` union would then silently take it as a
`SimplifiedFixtureInstance`, dropping `config`. To prevent that, `FixtureGroup` refuses
the key before the union runs, naming the fixture.

**`DmxMapping` and `FixtureConfig` keep `extra` at its default.** An unrelated unknown
key is still ignored, as before. Only the keys above are refused.

**Template documents** (`TemplateDoc`, catalog and `--template-dir`):

| Key | Message |
|---|---|
| `steps[].{geometry,color,shutter,gobo}` | `template-step fields [...] were removed with the old moving-head renderer, their only reader; delete them and state the step's aim in movement.physical or component_refs, and its wheels in physical_shutter_state, physical_shutter, physical_color and physical_gobo` |
| `steps[].movement.{movement_type,intensity,cycles,params}` | `movement fields [...] were removed with the old moving-head renderer, their only reader; delete them and state the motion in movement.physical` |
| `steps[].movement` without `physical` | pydantic `movement.physical Field required` |
| `steps[].dimmer.{dimmer_type,intensity,min_norm,max_norm,params}` | `dimmer fields [...] were removed ...; delete them and state the pulse in dimmer.physical` |
| `steps[].timing.phase_offset` | `timing field 'phase_offset' was removed with the old moving-head renderer, its only reader; delete it and spread phase with physical_distribution` |
| `template.defaults` | `template field 'defaults' was removed with the old moving-head renderer, its only reader; delete it` |
| `presets[].{name,defaults}` | `preset fields [...] were removed with the old moving-head renderer, their only reader; delete them` |
| `presets[].step_patches.*.{geometry,color,shutter,gobo}` | `step-patch fields [...] were removed ...; delete them and patch movement, dimmer or timing` |

A step patch whose `movement`, `dimmer` or `timing` dict names a key those models refuse
is refused when the document loads (`load_template_document`, so `--template-dir` and
`template-validate` too), with the component's message prefixed by the preset and step:
`preset 'SNAPPY', step patch 'reveal': movement fields ['intensity'] were removed with
the old moving-head renderer, their only reader; ...` (`TemplatePreset`). The checks are
the same functions the `Movement`, `Dimmer` and `StepTiming` validators call.

**Other breaking changes:**

- **`ChannelValue`:** naming a removed field raises "Extra inputs are not permitted".
  Nothing persists or loads a `ChannelValue`; it is internal.
- **Fingerprints:** every fingerprint, and every record's `template_sha256`, changes (§4).
  `eval-report` on a checkpoint recorded before this change reports
  `RENDER_FINGERPRINT_MISMATCH`, naming the templates and the rig among the differing
  inputs. A fixture file that still names a removed key cannot be loaded for that
  re-render at all.
- **`twinklr show` session ids change, so a `show` re-run re-plans (paid).** Its session
  id hashes `(app_config, job_config, fixture_group)` (`cli/show_cmd.py:123-126`,
  `derive_session_id` → `config_fingerprint`, which dumps each model). The
  `FixtureGroup` dump lost the removed fields, so every `show` session id changes, and the
  agent cache is addressed by session id (`caching/identity.py`). Every cached planner
  stage of a `show` misses once and re-plans. There is no compatibility key; it would be
  a shim.
- **Other rig and fixture hashes** (a sweep of `derive_session_id`/`config_fingerprint`
  callers and of every `model_dump` of the rig or fixture group in `packages/`):
  - `twinklr run` (`cli/main.py:643-646`) and `twinklr display`
    (`cli/display_cmd.py:121-124`) hash `(app_config, job_config)` only. Their session ids
    are unchanged.
  - The moving-head planner's own cache key (`MovingHeadPlannerOrchestrator.get_cache_key`)
    hashes the fixture count and the `fixture_groups` listing, which are unchanged (§6.4).
  - `inject`/`regenerate`: the live-plan `rig_sha256` (`cli/main.py:162-171`) hashes
    `rig.model_dump_json()` (next item).
  - The render fingerprint (`identity.render_fingerprint`) and the checkpoint record's
    `inputs.rig` (`RenderingPipeline.checkpoint_record`) hash the fixture-group dump
    (fingerprints, above).
  - The three-arm manifest's `fixture_config_sha256` hashes the fixture file's bytes, not
    a dump. It is unchanged for an unchanged file, but a file naming a removed key no
    longer loads.
- **`twinklr regenerate` refuses every sequence injected before this change.** The live
  plan recorded at `inject` carries `rig_sha256` of the rig dump, and the dump changed,
  so `regenerate` reports the recorded plan as stale. Remedy: run `twinklr inject` again
  for that sequence; the message already ends "run `twinklr inject` first". The `rig`
  reason was made truthful without detecting old records: "the rig differs (fixture
  config, live layout, or the fields this Twinklr version records for a rig)"
  (`LIVE_PLAN_IDENTITY`, `cli/main.py`).
- **`report.json`:** loses `summary.physics_violations`, `compliance_issues` and
  `harsh_transitions`; `physical.not_reported`; each curve's `continuity`,
  `physics_check`, `curve_type`, `handler`, `base_position`, `static_dmx` and
  `stats.clamp_pct`; each section's `template_compliance` and `transition_to_next`; and
  `selected_template.steps`. `report.md` loses "Not reported for physical output".
  `EvaluationReport.schema_version` is now `2.0.0` (was `1.0.0`).
- **Empty offer:** a run with no template loaded is refused by the render-preflight gate,
  after audio analysis and still before any LLM provider request. It was refused by
  `twinklr run`/`show` before analysis. Audio analysis now runs first, and it may make
  non-LLM metadata lookups (its enabled enhancements, such as AcoustID, MusicBrainz or
  lyrics lookup) before the refusal.
- **Live reconciliation:** `inject`/`regenerate` no longer list semantic groups under
  `missing-groups`.
- **Python API:** the classes and helpers in §1 are gone, as are their exports from
  `twinklr.core.config` and `twinklr.core.config.fixtures`.

## 6. Proof that output is unchanged

### 6.1 Byte matrix

The C1.2 gate matrix was copied to `c13/` with two changes:

- **`segments_canon`:** a segment hash over the fields both trees have. The raw
  `repr(segments)` now differs only because the removed fields are gone from it.
- **`template_sha256`:** dropped from the normalized record and trace, as `render_fingerprint` already was.

It ran on the baseline (`git archive 0ec65d47`) and on this tree: 360 configs, 15,930
leaf comparisons.

**Differences: 2,880 = 360 × 8.** They are exactly `render_a` and `render_b` × these four
fields:

- `fingerprint`;
- `record` and the `.xsq.trace.json` file hash, which embed the fingerprint and
  `template_sha256`;
- the raw `segments` repr.

**Identical in all 720 renders:**

- frames;
- frame count;
- `segments_canon`;
- the normalized record and trace;
- every `.xsq`, `.xmap` and `.xtiming` (2,160 files).

The gate result is identical in all 360 configs, and no render raised in either tree.

The first run (`matrix_new1`) preceded the last edits: docstrings, the deleted P1P-T6
comment and the position refusal message. The matrix was rerun after them
(`matrix_new2`, `matrix_new3`), and again after the review fix round (§10,
`matrix_new4`). Each rerun equals `matrix_new1` with 0 differences in 15,930
comparisons, and against the baseline gives the same 2,880. Files are in
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/c13/`
(`matrix.py`, `compare.py`, `matrix_{base,new1,new2,new3,new4}.jsonl`, `cmp_*.txt`).

### 6.2 Pins and goldens

- **Pins:** `tests/regression/test_mh_physical_pins.py`, 45 tests, passes. Its frames and
  `.xsq` hashes were not changed (§4).
- **Display goldens:** `git diff --stat` on `tests/regression/baselines/`,
  `tests/golden/fixtures/*.xsq` and `combined_show_drop.trace.json` is empty, so the
  display baselines (`02_rudolph*`) and display `.xsq` fixtures are byte-identical.
- **Combined show:** its display half is equal. Its moving-head half is equal except the
  fingerprint.

### 6.3 Checks run on the final tree, this session

- **Tests:** `uv run pytest tests -q --no-cov`: 6,491 passed, 30 skipped, 0 failed
  (6,521 collected), after the fix round.
- **Lint:** `uv run ruff check packages tests scripts`: all checks passed.
- **Format:** `uv run ruff format --check packages tests scripts`: 1,289 files already
  formatted.
- **Types:** `uv run mypy packages/twinklr`: no issues in 644 source files. That is 648
  at C1.2, minus the four deleted modules.

### 6.4 Planner-visible bytes

`c13/planner_bytes.py` ran on both trees and found these identical:

- `ChoreographyPlan.model_json_schema()` (the response schema);
- `MovingHeadPlanningContext.model_json_schema()`;
- the catalog's `TemplateDescription`s from `MovingHeadStage._build_template_descriptions`;
- the `dmx_mapping` channel listing;
- the planner graph and xLights mapping (`build_moving_head_graph`).

## 7. Documents

- **`docs/user-guide.md:314`** said the old renderer's fixture fields "no longer affect
  any output". It now says they are refused, and lists them with the semantic groups.
- **`docs/user-guide.md:316`** said "inferring anything from the legacy fields above". It
  now says "from `dmx_mapping`".
- **`docs/user-guide.md:257`** said "a run with none is refused before analysis". It now
  says "right after audio analysis, before any planning".
- **The `physical`-block paragraph of the evaluation report section** described
  `not_reported` and `null` metrics. It now says those metrics are not in the report.
- **Docstrings and comments corrected:**
  - `template.py`'s "Physical renderer only" comments and its module docstring;
  - `compile/physical.py`, `template_compiler.py` and `frame_encoder.py`, which mentioned
    legacy refusals;
  - `capabilities.py:5`;
  - the gate docstring (`pipeline.py`), which mentioned "legacy data a preset adds" and
    now also states the empty-offer refusal;
  - `_physical_preset`, which said "it would add legacy data".

## 8. What later tasks inherit

**C1.4** inherits the renames, unchanged:

- `physical_v2` in log prefixes and messages, including `_physical_preset`'s docstring;
- `PHYSICAL_*`, `LEGACY_BACKEND_ID`, the `moving_heads_physical/` directory and
  `admit_physical_catalog`;
- the `"renderer": "physical_v2"` record value and the revision string;
- the `physical_v2` family tags;
- `compile_physical_*` and `physical_cue_limits`.

The inventory's optional tier also falls to C1.4: flattening `movement.physical`,
`dimmer.physical` and the `physical_*` step fields into the freed names. It would change
the JSON format again. The two cascades' `"dimmer": {}` would go with it.

**C1.5** inherits:

- `README.md:175` ("geometry + movement + dimmer") and `docs/overview.md:147`.
- `scripts/validation/_core/mh_xsq_validation.py:110` and `:553`, which still read
  `xlights_semantic_groups` from fixture JSON. A fixture file that carries it no longer
  loads in Twinklr.
- `context/` and `memories/`.
- The user guide's remaining two-renderer history.
- The user guide's live-injection section: a sequence injected before this change must be
  injected again (`twinklr inject`) before `twinklr regenerate` accepts it, and a
  `twinklr show` re-run re-plans once (§5).

**T1** inherits the planner contract, unchanged:

- `agents/sequencer/moving_heads/models.py` with `Intensity`, `ColorPreset`,
  `GoboPattern`, `ShutterPattern`, `TransitionHint` and `_normalize_legacy_input`;
- the `dmx_mapping` channel listing shown to the planner. If T1 drops it, `dmx_mapping`
  can go too.

## 9. For the integrator to decide

1. **Protected ledger paths removed.** `PROTECTED_EXACT_EFFECT_PATHS` lost the
   `limits.avoid_backward` and `position.{pan,tilt}_offset_deg` entries (six paths) with
   their fields, and `test_restored_effect_paths_keep_their_exact_public_nodeids` was cut
   to `job.timeline_tracks.sections`. Earlier work protected those paths as "public pose
   safety/conversion". The public methods behind them (`is_pose_safe`, `apply_offset`)
   had no production caller.
2. **`pan_offset_deg`/`tilt_offset_deg` are removed beyond the brief's list**, on the
   grounds in §1.4. Their message says "nothing read them".
3. **Refusal is by name, not `extra="forbid"`.** Fixture models keep pydantic's default
   `extra` (ignore), so other unknown fixture keys still load silently, as before. Making
   the fixture models `extra="forbid"` would also refuse unrelated keys, which this task
   did not take on.
4. **`report.json` schema version** is now `2.0.0` (review fix round). Nothing in the
   repository reads `report.json` back.
5. **Empty offer moved later.** It is now refused after audio analysis instead of before
   it: after any non-LLM metadata lookups, still before any LLM provider request.
6. **Fields left in place.** `ReportSummary.max_concurrent_layers` (always 0),
   `SectionReport.segments` (always `None`) and `TargetResolution.bindings` (always `{}`)
   were left because they are not old-renderer fields.

## 10. Review fix round — 2026-11-17

An independent review found the code sound and the output byte-identical, and asked for
these changes, made in the same tree:

1. **Record:** `twinklr show` session ids change, so a `show` re-run re-plans. A sweep of
   every other rig or fixture hash is in §5. No code change: keeping the old dump would be
   a shim.
2. **Record:** `twinklr regenerate` refuses sequences injected before this change, with
   the remedy, in §5 and in the C1.5 carry-over (§8). The `rig_sha256` reason in
   `LIVE_PLAN_IDENTITY` now also names a Twinklr version change. Old records are not
   detected.
3. **`config_overrides.position` is refused.** It never took effect: `expand_fixtures`
   replaced it with the fixture's own `position`. Test:
   `test_fixture_config_of_the_removed_renderer_is_refused_by_name[...config_overrides field 'position'...]`.
4. **A step patch naming a removed key is refused at load**, naming the preset and step
   (`TemplatePreset.reject_removed_fields` → `_reject_removed_patch_fields`). The removed-key
   checks of `Movement`, `Dimmer` and `StepTiming` became module functions so the preset
   can reuse them. The gate case `preset-patch-names-a-removed-field` is gone (its
   template can no longer be built). Three load-time tests replace it, and they assert the
   step id that case had dropped.
5. **Rig leftovers removed** (§1.3): `SemanticGroup.order`, `ChaseOrder`, `infer_orders`,
   `infer_roles` and the phase-offset docstring.
6. **`EvaluationReport.schema_version` is now `2.0.0`** (§5).
7. **Record:** the empty-offer refusal now follows audio analysis and any non-LLM metadata
   lookups, and is still before any LLM provider request (§5).

After the round, these were rerun on the final tree: the full suite, ruff check, the
format check, mypy, the byte matrix (`matrix_new4`), the pins and goldens, the P1 request
and the planner-visible bytes. Results are in §4, §6 and below.

- **Tests:** 6,491 passed, 30 skipped, 0 failed (6,521 collected).
- **ruff check:** passes. **Format check:** 1,289 files already formatted.
- **mypy:** no issues in 644 source files.
- **Byte matrix (`matrix_new4`):** 0 differences against `matrix_new1`. Against the
  baseline, the same 2,880 fingerprint, record, trace and raw-segment differences. Frames,
  `.xsq`, `.xtiming` and `.xmap` are identical.
- **Pins and goldens:** they pass with no further re-record. The fix round changed no
  `FixtureGroup` or `TemplateDoc` dump, so no fingerprint moved again.
- **P1 request:** the fingerprints are unchanged from §4 (`50e6b255…d4df`,
  `7a96d383…5315`). The `.xsq`, `.xmap` and `.xtiming` equal the baseline's.
- **Planner-visible bytes:** identical to the baseline.
