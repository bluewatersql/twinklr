---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# C1.4: names of the one renderer — 2026-11-17

C1.2 (`0ec65d47`) deleted the old moving-head renderer and C1.3 (`079831df`) narrowed the
shared models. The code still named the surviving renderer as one of two: `physical_v2`
in logs, diagnostics, the render record and the revision string, `physical_*` and
`legacy_*` in identifiers, a `moving_heads_physical/` catalog, and `physical_*` and
`*.physical` template keys. C1.4 renames or removes those names so the code reads as if
there had only ever been one renderer, under the rule of the cutover inventory (§4):
rename only what names the mode or carries a qualifier freed by a deleted counterpart;
keep "physical" where it means physical units, values or the physical profile.

The work is in the working tree of `feat/mh-true-up-p3` on top of `079831df`. Nothing is
committed. No provider was called, no xLights instance was touched, no owner-local data
was read, and `make validate` was not run (the brief forbids it). Encoded frames, `.xsq`,
`.xtiming` and `.xmap` are byte-identical to `079831df` (§4). Render fingerprints change,
because the revision string and the template documents they hash were renamed.
`RENDERER_REVISION` (formerly `PHYSICAL_RENDERER_REVISION`) is still `"2"`.

Paths are under `packages/twinklr/` unless they start with another top-level directory.
Scratch files are under
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/c14/`
(called `c14/` below).

## 1. What changed, per scope item

### 1.1 `physical_v2` literals

| Where | Before | After |
|---|---|---|
| Fingerprint revision string (`RenderingPipeline.fingerprint`) | `physical_v2.2+encoder.N` | `renderer.2+encoder.N` |
| `render_record["renderer"]` (trace `render`, show trace `render`, stage output `render_record`) | `"physical_v2"` | key removed (§6, D1) |
| 9 runtime messages in `sequencer/moving_heads/pipeline.py`: 8 `logger` calls and the `unplayable_warning` string | prefix `physical_v2: ` | prefix `moving heads: ` (D3) |
| Preset diagnostic (`_section_preset`, written to the trace's `diagnostics`) | `...; physical_v2 applies no preset` / `...; physical_v2 applies its effective variant 'x'` | `...; the renderer applies no preset` / `...; the renderer applies its effective variant 'x'` |
| Intent diagnostic (`render`, written to the trace's `diagnostics`) | `... is not applied by physical_v2 in Phase 1; the template's physical data renders as authored` | `... is not applied by the renderer in Phase 1; the template renders as authored` |
| Tag in the 7 family JSONs, the P1 test template and `loop_template_doc` | `"physical_v2"` | removed |
| `compile/physical.py` module docstring, `_section_preset` docstring | `physical_v2` | removed |
| `docs/user-guide.md` (7 occurrences, such as "A `physical_v2` template step may ...") | `physical_v2` | removed |

`physical_v2` remains in exactly these places (each checked with
`git grep -n physical_v2 -- packages tests scripts docs catalog README.md`):

- `config/models.py:686`, the refusal of the removed key `moving_heads.mode`. It names the
  value a user's job would hold ("moving heads have one renderer, the one 'physical_v2'
  selected"). A refusal of a removed key, not a second path.
- `tests/unit/config/test_config_inventory.py:554` and
  `tests/unit/config/test_mh_render_policy.py:49` (`id="mode-physical"`): tests that a job
  naming `mode: physical_v2` is refused.
- `tests/unit/reporting/evaluation/test_report.py:553`: a test that a checkpoint record
  whose policy names `mode` is refused.
- `tests/regression/test_mh_pins.py:229`: the provenance of the gated pin's frames and
  `.xsq` hashes, rendered from `mh-last-with-legacy-renderer` whose job carried
  `mode: physical_v2`. History, true as written.

### 1.2 Constants, functions, classes and modules

All references in `packages/`, `tests/`, `docs/` and `catalog/` were renamed with them.

| Before | After | Note |
|---|---|---|
| `PHYSICAL_RENDERER_REVISION` | `RENDERER_REVISION` | value `"2"` unchanged |
| `LEGACY_BACKEND_ID` | `BACKEND_ID` | value `"xlights_dmx"` unchanged; no other legacy revision existed after C1.2 |
| `PHYSICAL_TEMPLATE_DIR` | `TEMPLATE_CATALOG_DIR` | the one catalog constant; `DEFAULT_DATA_TEMPLATE_DIR` was already deleted in C1.2 |
| `admit_physical_catalog` | `load_template_catalog` | |
| `in_physical_catalog` | `in_template_catalog` | |
| `RenderingPipeline._render_physical` | inlined into `RenderingPipeline.render` | the old `render()` (a debug log and the call) is deleted; its debug log is the first statement of the new `render()` |
| `compile_physical_template` | `compile_template` | |
| `compile/physical.py` | `compile/step.py` (`git mv`) | named for the mode; it holds `compile_step` |
| `compile_physical_step` | `compile_step` | |
| `slice_physical_segment` | `slice_segment` | |
| `evaluate_physical_path` | `evaluate_path` | |
| `_require_physical_step` | `_require_step` | |
| `PhysicalCompileError` | `CompileError` | |
| `build_physical_sequence` | `build_sequence` | |
| `export_physical_delivery` | `export_delivery` | |
| `physical_cue_limits` | `cue_limits` | |
| `check_physical_templates` | `admit_templates` | |
| `_physical_preset` | `_section_preset` | D7 |
| `PhysicalRenderError` | `RenderRefusedError` | D4; message `Physical render refused: ` → `Moving-head render refused: ` |
| `PhysicalOutputError` (`export/frame_encoder.py`) | `OutputError` | messages `Physical output rejected: ...` → `Moving-head output rejected: ...`, `Physical output needs single-color DMX models ...` → `Moving-head output needs single-color DMX models ...` |
| `check_physical_models` (`export/xsq_adapter.py`) | `check_models` | |
| `physical_run_requests` | `run_requests` | |
| `ShowStage._render_physical` (`pipeline/show_stages.py`) | `ShowStage._render_moving_heads` | |
| `MIN_PHYSICAL_PERIOD_BEATS` | `MIN_PERIOD_BEATS` | |
| `config/fixtures/physical.py` | `config/fixtures/removed_fields.py` (`git mv`) | review fix: it holds only the retired and removed fixture-field refusals; its 3 importers (`dmx.py`, `instances.py`, `groups.py`) and the package docstring updated; its logger name follows the module |
| `PhysicalMovementSpec` | `Movement` | merged with the deleted `Movement` wrapper (§1.4) |
| `PhysicalPulseSpec`, `PhysicalDimmerPulse`, `PhysicalShutterPulse`, `PhysicalZoomSpec` | `PulseSpec`, `DimmerPulse`, `ShutterPulse`, `ZoomSpec` | |
| `Dimmer` (wrapper with one optional `physical` field) | deleted | §1.4 |
| `TemplateStep._validate_physical_shutter` | `_validate_shutter` | |
| `EvaluationReport.physical` (report.json key `physical`) | `EvaluationReport.render` (key `render`) | D9 |
| `PhysicalRenderSummary` | `RenderSummary` | |
| `PhysicalRerender`, `RerenderResult.physical` | `RerenderOutput`, `RerenderResult.output` | |
| `_physical_summary`, `_render_physical_markdown` | `_render_summary`, `_render_summary_markdown` | report heading `## Physical render` → `## Render` |

Test-support and test renames:

| Before | After |
|---|---|
| `tests/support/mh_physical.py` | `tests/support/moving_heads.py` |
| `tests/fixtures/moving_heads/physical_v2/` | `tests/fixtures/moving_heads/templates/` |
| `tests/regression/test_mh_physical_pins.py` | `tests/regression/test_mh_pins.py` |
| `tests/integration/test_combined_show_physical.py`, `test_mh_physical_adaptation.py`, `test_mh_physical_families.py`, `test_mh_physical_pipeline.py` | `test_combined_show.py`, `test_mh_adaptation.py`, `test_mh_families.py`, `test_mh_pipeline.py` |
| `tests/unit/reporting/evaluation/test_physical_report.py`, `test_show_metrics_physical.py` | `test_report.py`, `test_show_metrics_moving_heads.py` |
| `tests/unit/sequencer/moving_heads/compile/test_physical.py`, `test_physical_discrete.py`, `test_physical_edges.py`, `test_physical_paths.py` | `test_step.py`, `test_step_discrete.py`, `test_song_edges.py`, `test_paths.py` |
| `tests/unit/sequencer/moving_heads/test_physical_compile_to_frames.py` | `test_compile_to_frames.py` |
| helpers `physical_rig`, `physical_job`, `physical_grid`, `physical_plan`, `physical_test_templates`, `physical_layout_xml` (the P1.6 pipeline case) | `p1_rig`, `p1_job`, `p1_grid`, `p1_plan`, `p1_templates`, `p1_layout_xml` |
| helpers `physical_catalog`, `physical_template_doc`, `physical_sections`, `physical_preset_rig`, `physical_bars_grid`, `physical_edge_grid`, `physical_segment`, `physical_step_payload`, `PHYSICAL_INITIAL_STATE` | `family_catalog`, `loop_template_doc`, `sections_plan`, `preset_rig`, `bars_grid`, `edge_grid`, `fixture_segment`, `linear_step_payload`, `INITIAL_STATE` |
| 53 test functions, e.g. `test_physical_job_renders_and_delivers_through_the_stage`, `test_regenerate_on_a_physical_job_twice_builds_on_each_recorded_plan`, `test_physical_template_field_changes_compile` | `test_job_renders_and_delivers_through_the_stage`, `test_regenerate_twice_builds_on_each_recorded_plan`, `test_step_field_changes_compile` (full list: `c14/tools/rename_tests.py`) |
| 15 test-local names (`_physical_context`, `_PhysicalBackend`, `PHYSICAL_TEMPLATE_PATHS`, `_PHYSICAL_TEMPLATE_REJECTED`, ...) | `_render_context`, `_FamilyBackend`, `STEP_FIELD_PATHS`, `_TEMPLATE_REJECTED`, ... (same file) |
| test data: `template_id="physical_probe"`, song `physical_show`, `physical-show.wav`, session `physical-eval`, `physical.xsq` | `step_probe`, `combined_show`, `combined-show.wav`, `family-eval`, `frames.xsq` |

No target name collided with an existing definition. `RenderError` would have shared its
name with `agents/prompts/renderer.py`'s `RenderError`, so the render refusal is
`RenderRefusedError` (D4). Two tests bound a local `compile_step = ...compile_physical_step`;
`test_gate_reuse.py` now imports the module as `step_module`, and `test_unplayable.py`
names its local `real_compile_step`.

### 1.3 Catalog

- `catalog/templates/moving_heads_physical/` → `catalog/templates/moving_heads/` with
  `git mv` (7 JSON documents and the README). The directory name was freed in C1.2.
- `TEMPLATE_CATALOG_DIR` (`sequencer/moving_heads/templates/data_loader.py:29`) is the one
  catalog constant.
- Packaging: no packaging or data-file configuration names the catalog
  (`git grep -n catalog -- '*.toml' MANIFEST.in` finds only a pytest marker description
  in `pyproject.toml:182` naming `catalog/templates/`). The loader resolves the directory
  from the source tree (`parents[6]`), as before.
- References updated: the data loader docstring, `docs/overview.md`,
  `docs/developer-guide.md`, `docs/pipeline_guide.md`, `docs/user-guide.md`,
  `tests/integration/test_mh_families.py` and the catalog README.

### 1.4 Template step fields (the optional tier)

**Design.** `Movement` was a wrapper whose one field was `physical`, and `Dimmer` a
wrapper whose one field was an optional `physical`. Flattening removes both wrappers:
`step.movement` is the motion itself and `step.dimmer` is the pulse or nothing. Every
step-level `physical_*` key drops its prefix, and so does the template's
`physical_overlays`. The flattened model has no wrapper that only forwards, and each key
reads as what it sets, so it is better on its own terms; I found no case where it is
worse. The one consequence is that `dimmer` became optional (it was a required wrapper,
which the cascades filled with `"dimmer": {}`); "no dimmer pulse" is now "no `dimmer`".

| Before | After |
|---|---|
| `steps[].movement.physical.{shape, mode, start_pan_deg, start_tilt_deg, pan_extent_deg, tilt_extent_deg, period_beats, lissajous_ratio, transform}` | `steps[].movement.{...}` |
| `steps[].dimmer.physical.{period_beats, duty_cycle, phase_cycles, low, high}`; `"dimmer": {}` for none | `steps[].dimmer.{...}`; `dimmer` left out for none |
| `steps[].physical_shutter`, `physical_shutter_state`, `physical_color`, `physical_gobo`, `physical_zoom`, `physical_distribution`, `physical_visibility`, `physical_reposition_fallback` | `shutter`, `shutter_state`, `color`, `gobo`, `zoom`, `distribution`, `visibility`, `reposition_fallback` |
| `template.physical_overlays` | `template.overlays` |
| preset step patch `movement: {physical: {...}}`, `dimmer: {physical: {...}}` | `movement: {...}`, `dimmer: {...}` |

Rewritten: the 7 family JSONs (with `json.dumps(indent=2)`, which reproduces the
original bytes for an unchanged document; checked on all 7 before rewriting), the P1 test
template (by hand; it is hand-formatted), `apply_step_patch` (`compile/preset.py`), the
compile modules, the models' validator messages, every test payload and
`docs/user-guide.md`. Step patches still patch `movement`, `dimmer` and `timing` only.

**Refusals.** A document using an old key is refused when it loads, by name, with the new
key (exact messages, from `TemplateStep`/`TemplateDoc` validation on the final tree):

- `template-step fields were renamed: 'physical_color' is now 'color', 'physical_gobo' is now 'gobo'`
  (one clause per renamed key present; `RENAMED_STEP_FIELDS`, `sequencer/models/template.py:446`).
- `movement field 'physical' was flattened into movement: move its keys (shape, mode, start angles, extents, period_beats, ...) up into movement itself`
- `dimmer field 'physical' was flattened into dimmer: move its keys (period_beats, duty_cycle, phase_cycles, low, high) up into dimmer itself`
- `an empty dimmer object no longer means no pulse: leave dimmer out instead`
- `template field 'physical_overlays' was renamed: it is now 'overlays'`
- `dimmer: {"physical": null}`: `dimmer field 'physical' was flattened into dimmer, and a null pulse is no pulse: leave dimmer out`
  (review fix; it no longer says to move keys up, which led to a second refusal).
- In a preset: `preset 'SNAPPY', step patch 'reveal': movement field 'physical' was flattened into movement: ...`
  (the same for `dimmer`, including `physical: null`), at load, as C1.3's patch refusals are.

These are refusals, not aliases: no old key is accepted. They are tested in
`tests/unit/config/test_config_inventory.py`
(`test_a_renamed_template_key_is_refused_by_name_when_the_document_loads`, 12 cases,
`test_renamed_overlays_are_refused_by_name_when_the_document_loads`,
`test_a_step_patch_naming_a_flattened_key_is_refused_when_the_document_loads`, 3 cases),
each through `load_template_document`, as `--template-dir` and `template-validate` load.

**C1.3 refusals that changed.** C1.3 refused the old renderer's step keys `geometry`,
`color`, `shutter` and `gobo` by name. `color`, `shutter` and `gobo` are now the
flattened keys, so:

- `geometry` is still refused by name (`template-step field 'geometry' was removed with
  the old moving-head renderer, its only reader; delete it and state the step's aim in
  movement or component_refs`). Every old-renderer step carried a required `geometry`
  (inventory F4), so an old-renderer document is still refused by name.
- An old-renderer object under `color`, `shutter` or `gobo` is refused by the new key's
  shape (e.g. `color: Input should be a valid string`), not by name. Tested:
  `test_an_old_renderer_wheel_object_on_a_reused_key_is_refused` (3 cases).
- `color: null`, `shutter: null` or `gobo: null`, which old-renderer documents wrote, is
  now accepted and means "none", which is what it meant there. Nothing else old is
  accepted.
- A step patch naming `geometry` is still refused by name as removed. A step patch
  naming `color`, `shutter` or `gobo` is refused with the truth (review fix): `a step
  patch sets only movement, dimmer or timing; set ['color'] on the step itself`. Tested:
  `test_a_step_patch_naming_a_step_wheel_key_is_told_to_set_it_on_the_step` (3 cases).

**Registry (`tests/config_effects_registry.py`).** Template paths were renamed with the
fields. `template.template.steps.movement` and `.dimmer` are now both the generic
snapshot loop's paths and the P1.2 component paths (formerly `movement.physical` and
`dimmer.physical`); the P1.2 entries are registered after the loop and replace its two
entries, as a comment there says. Both tests still run:
`test_template_compile_field_changes_emitted_snapshot[template.template.steps.movement]`
and `[...dimmer]` are parametrized in their module, not from the registry.
`REMOVED_CONFIG_PATHS` (`test_config_inventory.py`) loses `template.template.steps.color`,
`.shutter` and `.gobo` (declared again) and gains the 11 renamed paths.

### 1.5 `REFERENCE_ARM_ID` / `reference_legacy_v1` and the three arms

Nothing is left: `reference_policy.py`, which held `REFERENCE_ARM_ID =
"reference_legacy_v1"`, and its test were deleted in C1.2 (`git show 0ec65d47 --stat`).
`git grep -n -e REFERENCE_ARM_ID -e reference_legacy -- packages tests scripts docs
catalog README.md` finds nothing.
`reporting/evaluation/three_arm.py` and `three_arm_cli.py` are the P2P-T13 experiment,
whose arms A, B and C are the deterministic selector and LLM planner configurations,
not renderers; no rename applies. Inventory F6 (whether Phase 5 compares against the old
renderer) remains the owner's decision; nothing in the code depends on it.

### 1.6 Remaining `legacy` and `physical` hits

**`legacy`** (`git grep -n -i legacy -- packages tests scripts docs catalog README.md`),
each a refusal of a removed key or another meaning:

- Refusals and their tests: `legacy_v1` in `tests/unit/test_session.py:174`,
  `tests/unit/config/test_mh_render_policy.py:54,56` (a job naming `mode: legacy_v1` is
  refused) and `tests/unit/cli/test_live_injection_command.py:787,805` (the old renderer
  is never suggested; the test name `..._without_suggesting_legacy` says so).
- Planner contract (T1, out of scope): `_normalize_legacy_input` and
  `legacy_intent_omitted` in `agents/sequencer/moving_heads/models.py` (14 lines),
  `identity.py:113,123` (part of the plan dump, so of the fingerprint),
  `pipeline.py:1713`, `deterministic_selector.py:459`, `three_arm.py:792`, the
  `TransitionHint` normalizers in `sequencer/models/transition.py:55,131`, and their tests
  (`test_render_identity.py:208,230,231`, `test_rendering_pipeline.py:77`,
  `test_deterministic_selector_admission.py`).
- Provenance: the tag `mh-last-with-legacy-renderer` in `tests/regression/test_mh_pins.py:14,228`.
- Retired fixture config: `tests/unit/config/test_mh_capabilities.py:360` ("Nothing is
  filled in from legacy fixture defaults").
- Other subsystems' own meanings: the planner-input shapes in
  `agents/sequencer/moving_heads/context.py:64`, `heuristic_validator.py:8,99`,
  `moment_cues.py:75`, `orchestrator.py:6`; audio profile and lyrics models,
  `agents/issues.py`, judge models, group planner, asset catalog, `config/loader.py`
  (Genius token), feature engineering, profiling (`LEGACY_PROFILE_SCHEMA_VERSION`),
  `curves/registry.py`, `audio/structure/sections.py`, planning, theming and vocabulary
  models, the group template store, the recipe builder, `formats/xlights/sequence/xmap.py`,
  `scripts/demo_recipe_pipeline.py`, `docs/pipeline_guide.md:279,1118`,
  `docs/qa-runbook.md:93`, the tests of those, `tests/conftest.py:33`,
  `tests/unit/test_repo_hygiene_templates_path.py` and
  `tests/unit/sequencer/moving_heads/templates/test_data_loader.py:138,148` (a display
  name in an alias test).
- `scripts/validation/` (C1.5): `README.md:10,287` and `_core/mh_xsq_validation.py:50`.
- Two test section headers named `Legacy` (`test_topology_phase.py:649`,
  `test_component_presets.py:398`) headed tests that no longer concern the old renderer;
  renamed `Dumps and identity` and `Validity and identity`.

**`physical`.** The remaining hits mean physical units or values (`PhysicalValue`,
`PhysicalPoint`, `PhysicalChannelError`, `check_physical_value`, `ChannelValue.physical`,
`models/moving_heads/physical.py`, `physical_min`/`physical_max`,
`physical_channel_values`/`physical_channel_stats`), the physical profile
(`physical_profile`, `physical_head_profile`) or real hardware (fixtures, rigs, positions,
display elements). `c14/tools/remaining_physical.py` removes those allowed terms from each
line and reports every `physical` left, so a line that holds an allowed term and a
mode-sense `physical` is still reported. (The first sweep, `remaining_physical.sh`, dropped
such lines whole and so missed `sequencer/models/context.py:20` and the docstring of
`test_rig_without_profiles_fails_the_stage`; both are fixed, with two
`test_mh_capabilities.py` strings that said "physical evidence path" and "physical
contract".) On the final tree it reports only physical values: the
`ChannelValue.physical` field (`channels/state.py:26`), local variables holding a
trajectory (`test_paths.py:1034`, `test_optical_axis.py:318`), "a discrete physical
value" (`compile/step.py:419`), "without physical profiles"
(`tests/support/moving_heads.py:728`), "explicit physical data" (`docs/overview.md:28`),
tests named for physical values (`test_physical_values.py`, `test_physical_metrics.py:81`,
`test_preposition.py:453`, `test_frame_encoder.py:304`) and the refusal test id
`mode-physical` (§1.1). The terms it allows also cover these, each checked:

- The refusals of §1.4 and their tests and docs (`template.py:373-454,790-791`,
  `test_config_inventory.py`, `docs/user-guide.md:545-548`).
- `config/models.py:686` and the refusal tests listed in §1.1.
- `tests/support/moving_heads.py:728` ("without physical profiles"),
  `docs/developer-guide.md:252` ("typed physical trajectories"),
  `catalog/templates/moving_heads/README.md:131` ("the same physical encoding": encoding
  physical values to words), `docs/overview.md:28` ("explicit physical data"), the
  test names `test_travel_is_timed_on_encoded_words_not_physical_values` and
  `test_unencodable_physical_values_fail`: physical values.
- `sequencer/vocabulary/display.py:4`, the group planner's prompt example: display
  hardware.
- `tests/regression/test_mh_pins.py:229`: history (§1.1).

`tests/unit/sequencer/moving_heads/test_physical_values.py` and
`tests/unit/reporting/evaluation/test_physical_metrics.py` keep their names: they test
`PhysicalValue` and the metrics in physical units (the latter's docstring now says so).

### 1.7 Documents

Corrected because a rename made them false: `docs/user-guide.md` (template keys and the
sections on distributions, relative paths, zoom, `ONCE`, whole-period cycles, envelopes
and overlays; `reposition_fallback`; the report's `render` block; the catalog path and
offer sentence; "physical renderer revision 2"; a new paragraph naming the step keys and
the refused old keys), `docs/overview.md`, `docs/developer-guide.md`,
`docs/pipeline_guide.md`, `docs/qa-runbook.md` (pins path),
`catalog/templates/moving_heads/README.md` (title, `reposition_fallback`, `zoom`,
"renderer revision 2", function names) and `tests/golden/README.md`. `README.md` needed
no change (its one `physical` is "physical positions"). Code docstrings and comments that
said "physical renderer", "physical compile", "physical render", "physical job" and the
like were reworded in the same files as the renames.

## 2. User-visible changes

- **Template documents and `--template-dir`:** the key renames and refusals of §1.4.
- **Render trace and show trace (`.xsq.trace.json`, `render`):** the `renderer` key is
  gone; `render_fingerprint` and `template_sha256` change (§3); the two diagnostic
  messages of §1.1 change; admission reasons that named a renamed key now name the new
  key (`sets zoom, but profile ...`, `distribution needs the rig's topology`, §4.1).
  `renderer_revision` is still `"2"` and `backend_id` still `"xlights_dmx"`.
- **Checkpoint render record (`render` in the plan checkpoint):** its shape is unchanged
  (it never carried `renderer`); `render_fingerprint` and `inputs.template_sha256` change.
- **Evaluation report:** `report.json` key `physical` → `render`; markdown heading
  `## Physical render` → `## Render`. `schema_version` stays `"2.0.0"` (D9).
- **CLI text (`twinklr run` and the template catalog load):** `📄 Physical templates
  loaded:` → `📄 Moving-head templates loaded:`; `🎛️  Physical templates offered:` →
  `🎛️  Moving-head templates offered:`; `ERROR: Could not load the physical template
  catalog` → `... the moving-head template catalog`; `--template-dir X is the physical
  catalog, already admitted; ...` → `... is the moving-head catalog, ...`; after
  `twinklr regenerate <section>` (`cli/main.py:709-715`), `...: a physical render plans
  each head's dark repositioning ...` → `...: the render plans each head's dark
  repositioning ...`. No CLI help text named the mode.
- **Logs:** the `physical_v2: ` prefix of 9 moving-head messages (including the
  unplayable warning `twinklr run` prints) is now `moving heads: `.
- **Error messages:** `Moving-head render refused: `, `Moving-head output rejected: `,
  `Moving-head output needs single-color DMX models ...`; template validation and
  compile messages that named `movement.physical`, `dimmer.physical` or a `physical_*`
  key now name the flattened key; `physical compile needs ...` → `the step compile
  needs ...`; the FADE_OUT refusal says "which the renderer does not implement".
  `twinklr eval-report`'s refusal of a record whose policy names `mode`
  (`reporting/evaluation/collect.py:124-129`) now reads "... its render record was
  written before the cutover to one moving-head renderer (its policy names `mode`); re-run
  the command that planned it to plan and record it again" (review fix; it said "written
  while the job could choose between two moving-head renderers").
- **Config schema descriptions:** `MHRenderPolicy` field descriptions say "moving-head
  render(er)" and `reposition_fallback` instead of "physical". Descriptions are not in
  any dump.
- **Planner prompt:** each family's tag list loses `physical_v2` (§4.4).
- **Consequences of the fingerprint and description changes:**
  - The moving-head planner's stage cache key hashes the template descriptions
    (`orchestrator.py:252-256`), so the first `twinklr run` or `twinklr show` of a song
    after this change plans again and pays. Session ids do not change: they hash the
    audio and the app, job and fixture configs (`caching/identity.py:136-140`), and no
    app, job or fixture model dump changes.
  - `twinklr eval-report` on a checkpoint recorded before this change re-renders it and
    reports a fingerprint mismatch: the recorded `template_sha256` differ from the
    re-render's, which `_mismatched_inputs` names per template (the case
    `test_a_fingerprint_mismatch_is_reported_with_the_input_that_differs[template]`
    covers). Not run against a real pre-C1.4 checkpoint.
  - `twinklr regenerate` is unaffected: its recorded identity is the effects, audio, job
    and rig (`LIVE_PLAN_IDENTITY`, `cli/main.py:144-151`), none of which changes.
  - Three-arm experiment: the gate's exclusion reasons travel into
    `SelectorAdmission.exclusions` (`SelectorAdmission.from_gate`,
    `deterministic_selector.py:84-122`), whose dump is hashed into the held-constant
    `HeldConstantIdentity.admission_sha256` (`three_arm.py:233-275`; a result's held
    identity must equal the recomputed one, `three_arm.py:1012-1013`). On a rig that
    excludes a template for a zoom axis or a topology, the reason now says `sets zoom` /
    `distribution needs` (§4.1), so a three-arm snapshot or result recorded before C1.4
    will not match its recomputed `admission_sha256`. None is in the repository
    (`git grep -l admission_sha256` outside `packages/` and `tests/` finds only
    `changes/` records).

## 3. Byte classes that changed, and why

| Class | Why | Evidence |
|---|---|---|
| Render fingerprints | the hashed revision string (`physical_v2.` → `renderer.`) and every hashed template document (renamed keys, flattened `movement`/`dimmer`, `"dimmer": {}` gone, tag gone) | §4.1-4.3 |
| `template_sha256` in record, trace and checkpoint `inputs` | the same document dumps | §4.2 |
| Render record and trace (`render`) | `renderer` removed; fingerprint and template hashes; the two diagnostics of §1.1 when emitted; admission reasons naming renamed keys when a gate result is recorded | §4.1, §4.3 |
| Gate exclusion reasons | two compile messages named renamed keys | §4.1 |
| Three-arm `admission_sha256` | it hashes the selector admission, which carries those reasons | §2 |
| Pin and golden fingerprints | the fingerprints above | §4.5 |
| Planner-visible template descriptions | the `physical_v2` tag | §4.4 |
| `report.json`, report markdown | §2 | tests in `test_report.py`, `test_combined_show.py` |

`RENDERER_REVISION` is not bumped: nothing rendered changes.

## 4. Proof that output is unchanged

### 4.1 Byte matrix

The C1.3 harness was copied to `c14/matrix_base.py` (old names) and
`c14/matrix_new.py` (new names). `diff c14/matrix_base.py c14/matrix_new.py` shows only
the import of the support module, `check_physical_templates` → `admit_templates`, the
four helper names and one comment naming a helper. Both share one `normalized()`, which
drops `render_fingerprint`, `template_sha256` and `renderer` and maps the old diagnostic
wording to the new (a no-op on the new tree). The baseline ran on `git archive 079831df` extracted to
`c14/base/`; the new run on this tree; `c14/run_matrix.sh` runs either.

- 360 configurations (8 rigs × 3 fixture timings × 5 grids × 3 policies), 15,930 leaf
  comparisons, 2,430 differences (`c14/cmp_base_new3.txt`):
  - 2,160 = 360 × 6: `render_a`/`render_b` `fingerprint`, `record` (its hash) and
    `files/song.xsq.trace.json` (its hash);
  - 270: `gate/exclusions`, in every configuration of the 6 zoomless rigs (`fam8`, `fam4`,
    `fam4_noMH2`, `fam4_notopo`, `fam4_nopresets`, `fam1`); the 2 zoom rigs' gates are
    identical.
- `record_norm` and `trace_norm` are identical in all 720 renders. So are `frames`,
  `frame_count`, `segments`, `segments_canon` and the `.xsq`, `.xtiming`
  (`song.audiosections.xtiming`) and `.xmap` hashes: 6,480 leaves, 0 differences; no
  render raised in either tree.
- Gate (`c14/gate_norm_compare.py`): after mapping `sets physical_zoom, but profile` →
  `sets zoom, but profile` (675 occurrences in the baseline) and
  `: physical_distribution needs the rig's topology` → `: distribution needs the rig's
  topology` (540), the gate results are identical in all 360 configurations; neither old
  phrase occurs in the new run. Admitted templates, presets, effective variants and entry
  dips are identical.
- The baseline run equals C1.3's final run of the same tree (`c13/matrix_new4.jsonl`):
  0 differences in frames, segments, fingerprints, record hashes, file hashes and gate.
- Four runs on this tree (`matrix_new1` to `new4`; `new4` on the tree after the review
  fixes) match each other with 0 differences; `new4` against the baseline gives the same
  2,430 differences and the same gate mapping result.

### 4.2 Template documents

`c14/template_dump_base.py` and `template_dump_new.py` dump the 7 families and the P1
test template as the render hashes them, from each tree. Applying the C1.4 key mapping
(`c14/tools/flatten.py`, the same function that rewrote the JSONs) to each baseline dump
gives the new dump exactly, for all 8:

| Document | `079831df` sha256 | C1.4 sha256 | mapped equal |
|---|---|---|---|
| `finite_snap_hold` | `80e253f7deaab832…` | `211a8cd59bb0c292…` | yes |
| `fly_in_cascade` | `6b759324e646ab01…` | `ab95946faf57e46b…` | yes |
| `fly_out_cascade` | `109936afdcf1cff3…` | `6c6fc285e47baa61…` | yes |
| `masked_wheel_flick` | `f76f4eba1e34aeb3…` | `2b4ae3f97d44a5fd…` | yes |
| `mirror_wings` | `ec6c05ba3e161933…` | `7ba3b6b2f0cb9252…` | yes |
| `p1_linear_reveal` | `6f2817f47d6fb173…` | `57b6d8e5d786346b…` | yes |
| `target_orbit` | `83858de093e273f7…` | `1c6baf099012314b…` | yes |
| `zoom_wave` | `94277791803bf26d…` | `d797030bc10ab5d8…` | yes |

### 4.3 Phase 1 request

`c14/p1_request_base.py` (old names, on `c14/base/`) and `p1_request_new.py` (new names,
this tree; `diff` shows only the helper names) were run and their outputs compared with
`cmp`:

| Case | `079831df` fingerprint | C1.4 fingerprint |
|---|---|---|
| `p1_linear_reveal` | `50e6b255a06c3bdf1d523107ddf84f242ed7300a9ffd6cb312bb66bc16a9d4df` | `8f1635e9aae6002e15897c1070092824ad020ea48832fc43b2d1147ae3451c2c` |
| `p1_linear_reveal_48ch` | `7a96d383cdc4a3fe81844ca4264a41ee588987e7d9b04eb09b12d96a19015315` | `55bb8ba6b2b99a8d9255b47b13144692296333bfc93336d0f928951a2d8ea84a` |

The baseline fingerprints equal those C1.3 recorded. The `.xsq`, `.xmap`,
`.audiosections.xtiming` and `fixtures.json` files are byte-identical. Each
`.xsq.trace.json` differs in exactly four leaves (`c14/jsondiff.py`):
`render/render_fingerprint`, `render/renderer` (absent now),
`render/template_sha256/p1_linear_reveal` (`6f2817f4…` → `57b6d8e5…`, §4.2) and
`render/output/serialization_ms` (wall clock). The printed frame tables are identical
apart from the fingerprint lines. A rerun on the final tree gave identical output.

### 4.4 Planner-visible bytes

`c14/planner_bytes_base.py` / `planner_bytes_new.py`: the response-model schema, the
planning-context schema, the `dmx_mapping` channel listing and the planner graph and
mapping are identical. The template descriptions differ: in each of the 7, the tag list
loses `physical_v2` and nothing else changes (checked field by field,
`c14/descriptions_base.json` vs `descriptions_new3.json`). The baseline values equal
C1.3's final planner bytes. No other planner-visible byte changes, and no meaning: the
tag named the renderer, which the planner never chose. It reaches the prompt as the
bracketed tag list in `prompts/planner/user.j2:47`. No code filters templates by tag
(`git grep -n "has_tag="` finds no caller).

### 4.5 Pins and goldens

- `tests/regression/test_mh_pins.py`: `c14/repin_c14.py` re-rendered every pin on this
  tree, found frames and `.xsq` equal to the pinned values for all 44 cases (42 family
  variants, the multi-section plan and the gated plan), and replaced the 44 fingerprints
  only. An AST comparison with `079831df`'s `test_mh_physical_pins.py` confirms: all 42
  frame hashes and both `(frames, .xsq)` pairs unchanged, all 44 fingerprints changed.
  The module docstring records the C1.4 re-record.
- `tests/golden/fixtures/combined_show_drop.json`: `c14/golden_snap_c14.py` found the
  snapshot equal to the golden apart from `moving_heads.render_fingerprint`, and the
  display trace equal to `combined_show_drop.trace.json`. Only that fingerprint was
  replaced (`46767038…` → `3be80a97c64ada912d7c99ecd3fb5104dd11b34808c46fa3c25c260f515f786c`).
- Display: `tests/regression/baselines/02_rudolph*`, `tests/golden/fixtures/*.xsq` and the
  display trace golden are unchanged in git and their tests pass.

### 4.6 Checks run on the final tree, this session

- `uv run pytest tests -q --no-cov`: 6,515 passed, 30 skipped, 0 failed (6,545 collected).
  Before: 6,521 collected on `079831df` (`c14/collect_base.txt`, this session); 6,491
  passed and 30 skipped is the count the brief and the C1.3 record give for
  `079831df` (not rerun here).
- `uv run ruff check packages tests scripts`: all checks passed.
- `uv run ruff format --check packages tests scripts`: 1,289 files already formatted.
- `uv run mypy packages/twinklr`: no issues in 644 source files.
- The byte matrix, P1 request, planner bytes, template dumps, pins and golden checks
  above.

## 5. Tests

`c14/test_id_map.py` maps every baseline test id through the renames (files, functions,
registry parameter ids) and compares with the new collection. 6,497 ids map one to one.
The rest:

- **Removed (9), because the keys are live again:**
  `test_removed_config_path_is_absent_from_public_schema[template.template.steps.{color,shutter,gobo}]`
  and `test_retired_template_config_fails_loudly_with_migration_message` for
  `TemplateStep` and `StepPatch` `color`, `shutter`, `gobo`. Replaced in substance by
  `test_an_old_renderer_wheel_object_on_a_reused_key_is_refused` (3) and
  `test_a_step_patch_naming_a_step_wheel_key_is_told_to_set_it_on_the_step` (3).
- **Renumbered (15):** the other cases of
  `test_retired_template_config_fails_loudly_with_migration_message` keep their
  assertion; their ids change because cases before them left or because `Dimmer`
  became `DimmerPulse`. The raw diff is 24 baseline ids without a counterpart (9 + 15)
  and 48 new ids without one (33 + 15).
- **Added (33):** the 6 above, 12 + 1 + 3 refusal tests (§1.4) and 11
  `test_removed_config_path_is_absent_from_public_schema` cases for the renamed paths.

6,521 − 9 + 33 = 6,545. Tests whose assertion had to change, each to keep its intent:

- `trace["render"]["renderer"] == "physical_v2"` (`test_rendering_stage.py`,
  `test_combined_show.py`) → `trace["render"]["renderer_revision"] == RENDERER_REVISION`.
- `test_absent_step_fields_stay_out_of_template_dumps`: `dumped["dimmer"] == {}` →
  `"dimmer" not in dumped` (there is no wrapper to dump empty).
- `test_discrete_states_alone_are_not_a_step`: the missing field is now
  `movement.shape`, not `movement.physical`.
- Message assertions follow the new wording (`test_mh_families.py`, `test_mh_pipeline.py`),
  `report.physical` → `report.render`, `written["physical"]` → `written["render"]`,
  `"Physical render" in markdown` → `"## Render\n" in markdown`.
- Stub render dicts in `show_test_support.py`, `test_show_manifest.py` and
  `test_show_metrics_moving_heads.py` hold `renderer_revision` instead of `renderer`.

## 6. Decisions

- **D1. `renderer` removed, not renamed.** Its value could only ever be one thing.
  Readers: none in `packages/` or `scripts/` (`git grep -n '"renderer"'`); tests that
  asserted it now assert `renderer_revision`.
- **D2. Revision string** `renderer.{RENDERER_REVISION}+encoder.{ENCODER_VERSION}`, as the
  inventory names it; N not bumped.
- **D3. Log prefix kept as `moving heads: `** rather than dropped: `twinklr show` logs
  display and moving-head messages together, and `twinklr run` prints the unplayable
  warning on its own line (`cli/main.py:802-804`).
- **D4. `RenderRefusedError`,** not `RenderError`, which `agents/prompts/renderer.py`
  already defines.
- **D5. `CompileError`, `OutputError`:** the qualifier dropped. Their messages say
  "Moving-head output" where a user sees them.
- **D6. `compile/step.py`** for the module that holds `compile_step`.
- **D7. `_section_preset`** for `_physical_preset` ("the preset a section renders");
  `_preset` alone said nothing.
- **D8. Test helpers:** the P1.6 case's helpers take `p1_` (its module docstring calls it
  "the P1.6 pipeline case"); the rest take a descriptive name. Plain names (`rig`, `job`,
  `segment`) were rejected: tests bind those as locals, which would shadow the helper.
- **D9. Report key `render`, `schema_version` still `2.0.0`.** `2.0.0` was introduced by
  C1.3 on this unmerged branch (`main` still has `1.0.0`), and nothing in the repository
  reads `report.json` back. Renaming a key inside an unreleased version needs no bump;
  the integrator may prefer one (§9).
- **D10. Flattening done** (§1.4); `dimmer` optional.
- **D11. Kept names** (rule: physical units, values or profile): `PhysicalValue`,
  `PhysicalPoint`, `PhysicalChannelError`, `ChannelValue.physical`,
  `models/moving_heads/physical.py`, `physical_channel_values`/`_stats`,
  and `physical_head_profile` (§1.6).
- **D12 (review fixes).** The registry's profile and initial-state note constants are
  `_PROFILE_*` (were `_PHYSICAL_*`), their comment says "the profile and initial-state
  contract", the identity-only note reads "identity only; no consumer yet" (also in
  `test_mh_capabilities.py`), and the two `reposition_fallback` paths have their own note:
  "exact path changes whether a cue that cannot be repositioned is kept dark or the
  render is refused". Dead `movement is None` guards are removed from `compile/step.py`,
  `compile/presets.py` and, the same guard, three in `compile/template_compiler.py`
  (`movement` is a required field).

## 7. Hand-off

**C1.5** (`context/`, `memories/`, `scripts/validation/`), places that name something
renamed here or describe two renderers:

- `context/current-state.md:47` ("An opt-in `physical_v2` moving-head mode") and `:49`
  ("seven physical template families").
- `scripts/validation/README.md:287` ("Legacy MH and display flows are both supported").
- `memories/`: `git grep` for every old name of §1.2 and §1.4 finds nothing.
- Still open from C1.3 and untouched here: `README.md:175` ("geometry + movement +
  dimmer"), `docs/overview.md:147`,
  `scripts/validation/_core/mh_xsq_validation.py:110,553` (`xlights_semantic_groups`),
  the user guide's re-inject note.
- Found, not made false by C1.4: `docs/pipeline_guide.md:845` says `twinklr display`
  "ignores the mode"; `moving_heads.mode` has been refused since C1.2.
- The active plan (`changes/.../plan/phase-3-arrangement.md`) and `changes/ACTIVE.md` need
  the C1.4 entry; the phase-1 request fingerprints are those of §4.3.

**T1** (planner contract, unchanged here): `agents/sequencer/moving_heads/models.py`
(`Intensity`, `ColorPreset`, `GoboPattern`, `ShutterPattern`, `TransitionHint`,
`_normalize_legacy_input`, `legacy_intent_omitted`), the `TransitionHint` normalizers in
`sequencer/models/transition.py`, `legacy_intent_omitted` in the plan dump
(`identity.py:113-123`), and the intent diagnostic ("planner intent ... is not applied by
the renderer in Phase 1"), which T1 replaces with the contract.

## 8. Not done

Nothing in the brief's scope is left undone. Not run, by the brief: `make validate`,
commits, provider calls, xLights. Not checked against real artifacts: the eval-report
consequence in §2 (derived from code and its test).

## 9. For the integrator

1. **Owner notice:** the first `twinklr run`/`show` of a song after this change plans
   again (planner cache key, §2); `eval-report` on an older checkpoint reports a
   fingerprint mismatch naming each template.
2. **Report schema:** `report.json`'s `physical` → `render` within the unreleased `2.0.0`
   (D9). Bump to `3.0.0` if you count `2.0.0` as published.
3. **Old-renderer wheel objects** under `color`/`shutter`/`gobo` are refused by shape now,
   not by name; `null` there is accepted (§1.4). The by-name `geometry` refusal still
   catches every old-renderer step.
4. **Index state:** the 23 moved files and `config/fixtures/removed_fields.py` (review
   fix, `git mv`) are staged as renames; edits made after staging, including the review
   fixes to three of the moved files, and every other change are unstaged.
