---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-17
updated: 2026-11-17
---

# C1.5: documents, context, memories and scripts for one renderer — 2026-11-17

C1.2 (`0ec65d47`), C1.3 (`079831df`) and C1.4 (`24c22b79`) left one moving-head renderer.
C1.5 brings the published documents, `context/`, `memories/` and `scripts/` in line with
that. The work was done on `feat/mh-true-up-p3` on top of `24c22b79` and committed as
`9e7205cf`; an independent review requested changes, which are applied in a follow-up
commit (§13). No provider was called, no xLights instance was touched, no
owner-local data was read, and `make validate` was not run (the brief forbids it). Every
statement written was checked against the code at `24c22b79` or a dated record; the
sources are named below. The planner contract is unchanged and is not described as
changing. §1–§3 record the first pass; §11 records the revision made the same day after
the owner's song-intent direction, and §13 the review corrections; where they differ the
later section is current.

Scratch files are under
`/private/tmp/claude-501/-Users-ondeck-work-github-twinklr/9cfb5b66-fff4-47db-adcb-766b50dc61e9/scratchpad/c15/`
(called `c15/` below).

## 1. `docs/`, `README.md` and the catalog README

| File | Was stale | Now says | Checked against |
|---|---|---|---|
| `README.md` | Stage 4 "Templates → curves → DMX values → fixture segments"; "Template Library — … fan formations, sweeps, chases, pulses … phase offsets"; the renderer "maps [categories] to precise DMX values"; `:175` "geometry + movement + dimmer" | Frames, DMX values, curves; seven data-form families with presets and per-head phase distribution, offered after a pre-planning gate; display resolves categories, the moving-head renderer applies no planner intensity, colour, shutter or gobo; each template's steps carry motion, pulses, wheel states and phase spread, dry-compiled on the rig | `catalog/templates/moving_heads/*.json`; `sequencer/vocabulary/intensity.py`, `display/composition/engine.py:96`; `pipeline/show_stages.py:189-200` |
| `docs/overview.md` | `:10` the engine resolves intensity/colour/shutter/gobo/lyric intent; `:147` "tested geometry, movement, and channel behavior"; Curves "used for smooth DMX value transitions" | Moving-head renderer renders templates as authored and does not apply categorical intent; the Template Library section describes JSON `TemplateDoc` steps, the catalog-then-`--template-dir` registry, refusal of removed or renamed keys, presets, and the `render_preflight` gate; Curves serve the display's value curves | `templates/data_loader.py:29`; `models/template.py:446`; `pipeline/definitions/common.py:66-77`; importers of `twinklr.core.curves` (display composition, `models/transition.py` only) |
| `docs/user-guide.md` | `:228` and `:314` "keys of the removed second moving-head renderer" / "fields only the removed renderer read"; stage list without `render_preflight` and "compiles the plan into DMX values, curve data, and fixture segments"; `eval-report` paragraph naming "the removed second renderer" and "the removed renderer's curve metrics"; troubleshooting "missing template XSQ file"; no note on `regenerate` after an upgrade or on re-planning | Keys "Twinklr no longer has / no longer reads"; seven stages with `render_preflight`; render compiles templates against each profile into 20 ms frames and plans dark repositioning; a record whose policy names `mode` "written by an earlier Twinklr version"; "the report holds no curve metrics"; render-stage failures are `Moving-head render refused: …` or `output_budget_exceeded`; new: the rig digest covers the fields this version records, so after an upgrade that changes them `regenerate` refuses earlier injections until `inject` runs again; new: cached results are keyed on the configs as this version models them and on the offered templates' descriptions, so after such an upgrade the first `run`/`show` of each song plans again (paid) | `config/models.py:657-697`; `pipeline/definitions/moving_heads.py:66-114`; `cli/main.py:144-170` (`LIVE_PLAN_IDENTITY`, `rig_sha256`); `cli/main.py:643-646`, `cli/show_cmd.py:123-126`; `orchestrator.py:238-272`; `sequencer/moving_heads/pipeline.py:1359`; `export/frame_encoder.py:438`; C1.3 record §5, C1.4 record §2 |
| `docs/pipeline_guide.md` | DAG without `render_preflight`; "keys of the removed second moving-head renderer"; `:845` `twinklr display` "ignores the mode"; Render "compiles the plan into DMX channel data" | DAG with `render_preflight` and what it does; "keys Twinklr no longer has"; `display` renders no moving heads and does not read the `moving_heads` block; render compiles templates against each profile into 20 ms DMX frames | `pipeline/definitions/common.py`, `moving_heads.py`; `cli/display_cmd.py` (no `moving_heads` or render-policy use) |
| `docs/developer-guide.md` | Chain without `render_preflight`; Curves "transition interpolation and DMX value smoothing"; Intensity "mapped to DMX dimmer values"; "`.xsq` regression parity … (moving-head and display)"; `validate_artifacts.py` "moving-head/display plans" | Chain with the gate; Curves serve the display, the moving-head renderer writes no curves; Intensity maps to per-lane display brightness, not applied to moving heads; regression pins describe the display replay and `test_mh_pins.py`; the validator checks display plans/XSQ and moving-head XSQ | `tests/regression/` listing; `test_mh_pins.py` docstring; `frame_encoder` settings test (`"E_VALUECURVE" not in settings`) |
| `docs/qa-runbook.md` | "Stages Completed: 6/6"; §4 narrated the deleted `11_need_a_favor` baseline | `7/7` (a skipped conditional stage still counts as completed, `pipeline/executor.py:124-131`); §4 states there is no moving-head metrics baseline and points at the trace, `eval-report` and the pins | `pipeline/definitions/moving_heads.py` (7 stages); `cli/main.py:770` |
| `catalog/templates/moving_heads/README.md` | "How any family looks is `PENDING-OWNER`" | The owner accepted the six zoomless families on their base variants for one song, rig and house preview on 2026-11-16; presets and `zoom_wave` not viewed; no hardware | [viewing-render record](../2026-11-16-p3-viewing-render/README.md) ("each on its base variant", "No section named a preset", `zoom_wave` excluded) |

The published blog series (`docs/audio_profile/`, `docs/feature_engineering/`) was not
changed: it is narrative, and its moving-head examples (`06_the_thread.md:200` names the
deleted template `fan_pulse`) describe the system as it was when written (§6).

## 2. `context/`

| File | Was stale | Now says |
|---|---|---|
| `current-state.md` | `:39-46` templates "resolve schema-v2 intent", "Python factories and … JSON share one registry", the pre-clean-up look held; `:47-55` "An opt-in `physical_v2` moving-head mode", "seven physical template families", gate "36–62 s", "families written for 4/4", "no look result"; quality gate "moving-head replay-render parity"; "One change is active"; live evidence only from the deleted renderer | A **Moving-head rendering** item: one renderer ([decision](../../../../memories/decisions/mh-single-renderer.md)); schema `3.1` only and removed keys refused by name; profile, settled initial state and own model per fixture, refused before analysis; the `render_preflight` gate and effective variants; the seven-family catalog, any meter; dark edges and `on_unplayable`; planner intent not applied though the contract still carries it; all five commands use it; gate time 12–13 s (4/4) and 27–31 s (3/4) at 8 heads, 4 minutes (measured 2026-11-16, plan); the pins as the output guard; the accepted look with its limits; `inject`/`regenerate` against a fake only. A separate **Display rendering** item. The gate section names the pins and points to the branch's own gate record. Active work names the cutover branch; the P1P golden-fixture exit notes that its fixture rendered the deleted renderer. A 2026-11-16 live-evidence row for the viewing render, and a note that the earlier runs' effect counts came from the deleted renderer |
| `glossary.md` | Template "geometry + movement + dimmer … fan formation, sweep, chase, pulse"; categorical planning resolved by "the renderer" | New entries **Physical profile** and **Gate**; Template is a JSON `TemplateDoc`, families in `catalog/templates/moving_heads/`; Preset patches steps (`narrow`, `slow`); categorical planning does not reach the moving-head renderer |
| `architecture/pipeline.md` | Sequencer row "template registry" generic | Sequencer row names the moving-head registry, compiler, frame encoder and export; new **Pre-planning gate** execution rule |
| `architecture/multi-agent-planning.md` | "The moving-head renderer now resolves schema-v2 intensity, color, shutter, gobo, and MomentCue intent"; "geometry + movement + dimmer"; "Python builtins load first … two forms coexist"; "resolves categories to DMX values" | The renderer renders template and preset as authored and applies none of that intent; the planner is offered gate-admitted templates; data-only loading, catalog first; display resolves categories |
| `engineering/conventions.md` | `job_config.json` "transitions"; `fixture_config.json` "names, DMX channels, physical positions" | The moving-head render policy; profiles, models, planner-listed `dmx_mapping`, positions, presets and topology |
| `product/overview.md` | "optional mapped shutter, color, and gobo output" | Profile-declared axes and wheel states rendered as complete DMX frames |
| `INDEX.md` | No routing row for moving-head rendering | A **Moving-head rendering** row linking the snapshot, user guide, catalog README and decision |

Promoted, with owners linked instead of restated: what the renderer requires and refuses,
the gate, the catalog location and the pins (`current-state.md`, linking the user guide
and catalog README for detail).

## 3. `memories/`

| Memory | Action |
|---|---|
| `decisions/mh-render-matches-pre-cleanup-look.md` | `status: historical`; dated supersession note at the top pointing at the viewing-render record, the C1.2 record and the new decision. Body unchanged |
| `decisions/mh-single-renderer.md` | **Added.** The owner's single-path direction and look acceptance (2026-11-16, recorded in `implementation-brief.md`), what was deleted, the new reference look and its guard, consequences |
| `decisions/llm-plans-intent-renderer-implements-precision.md` | Dated note on its "Implementation resolution (2026-08-14)" section: superseded for moving heads; the decision itself stands |
| `decisions/coordinated-show-contract.md` | Dated note: the moving-head halves of items 3 and 4 (focal roles to INTENSE/SMOOTH/SLOW, palette to a wheel preset) are superseded; `show` applies neither (`pipeline/show_stages.py:189-200`; C1.1a record) |
| `learnings/live-provider-run-lessons.md` | Dated note: the zero-width-transition and adapter fixes (`a8ce12b` in `pipeline.py`'s transition path, `08ce6d5` in `xsq_adapter.py`) touched code deleted in C1.2 |
| `learnings/model-dump-hashes-rekey-caches.md` | **Added.** Removing or renaming a field of a hashed model re-keys session ids and planner caches, refuses old live plans and changes fingerprints; the sweep to do and the owner notice. Evidence: C1.2 §7, C1.3 §5 and §10, C1.4 §2 |
| `patterns/render-output-proof.md` | **Added.** The byte matrix against a baseline commit, then committed pins, as used for the gate-time cut, D9, C1.0 and C1.2–C1.4 |
| `patterns/code-patterns.md` | Added the idiom "refuse a removed or renamed config key by name; never alias it", with citations and the `drop_retired_fields` exception |
| `INDEX.md` | Entries for the three new memories; the superseded decision marked; the two partly superseded decisions annotated |

Candidates considered and not added: the config ledger's import guard against entries
naming missing tests (`tests/config_effects_registry.py`) enforces itself on import, so a
memory would only restate code.

## 4. Scripts

`scripts/validation/` held the only scripts that targeted the deleted renderer. Every
`twinklr` and `scripts` import under `scripts/` resolves at `24c22b79` and after C1.5
(`c15/check_script_imports.py`).

**Deleted: `scripts/validation/_core/mh_plan_validation.py`** and its test
`tests/unit/scripts/validation/test_mh_plan_core_validation.py`. It validated
`plan_raw_<name>.json`, `plan_<name>.json`/`final_<name>.json` sections with
`start_ms`/`end_ms`/`template_id`, `channels` and `instructions[].movement.period_bars`,
and `evaluation_<name>.json` with `channel_scoring`. Nothing produces those artifacts:
`git grep -n -E 'plan_raw_|"evaluation_|channel_scoring|period_bars' -- packages` finds
nothing, and a run's plan is written to `checkpoints/plans/final.json` as a
`ChoreographyPlan`, which `twinklr eval-report` re-renders. Importers before deletion:
`validate_artifacts.py:945,973` and the test; doc references: `scripts/README.md:19`,
`scripts/validation/README.md` (both updated). No Makefile or CI reference
(`grep -n validation Makefile .github/workflows/*.yml`).

**Updated: `scripts/validation/_core/mh_xsq_validation.py`.** Kept: missing EffectDB
refs, overlaps, identical timings, gaps, DMX data presence; these hold for the current
`.xsq`. Removed:

- the reads of `xlights_semantic_groups` (`:110`, `:553`), a key Twinklr now refuses;
- `validate_value_curves`, which flagged as critical any "dynamic" template id (it would
  have matched `zoom_wave`) whose effects had no value curves; the renderer writes none;
- `validate_section_coverage` and `validate_channel_usage_vs_plan`, which read the
  deleted plan artifacts above;
- the `implementation_path`, `raw_plan_path` and `quality_only` inputs they needed.

**Defect fixed in the script:** `_load_effectdb` numbered EffectDB entries from 1, while
an effect's `ref` is the entry's zero-based position (Twinklr reserves entry 0 as empty,
`formats/xlights/sequence/registry.py:19-25`). So every effect was read with the
settings of the entry before its own. On the rendered sample below the HEAD version
matched 0 of 1,726 effects to their own entry; the updated one matches all 1,726
(`c15/compare_refs.py`).

**Updated: `scripts/validation/validate_artifacts.py`.** Moving heads: XSQ only. `--mode
plan --pipeline mh` prints that `twinklr eval-report` re-renders a plan and exits 2;
`--mode all` prints the same note and runs the XSQ checks. Removed the MH plan paths,
`--raw-plan-path`, `_run_mh_plan_mode*`, `_effective_mh_plan_path` and the JSON
detection of the deleted MH plan shapes (with its test,
`test_detect_pipeline_from_mh_plan_shape`). `--plan-path`, `--evaluation-path` and
`--quality-only` are display flags now. The display paths are unchanged.

**Tests added** (`tests/unit/scripts/validation/test_mh_xsq_core_validation.py`):
`test_an_effect_reads_the_effectdb_entry_its_ref_names` (fails with the old numbering,
checked by reverting it) and `test_a_rendered_moving_head_xsq_passes` (renders two
families on a two-head family rig into `tmp_path` and expects no issue).

**Runs on current output.** `c15/render_sample.py` renders the pins' multi-section plan
(`test_mh_pins.py`, `MULTI_SECTIONS`, variable grid) into `c15/out/`: fingerprint
`343c91a4…737d` and `.xsq` SHA-256 `9ef5b7a1…c6fb`, both equal to `MULTI_PIN`, so the
input is the pinned delivered output.

| Command (from the worktree root) | Result |
|---|---|
| `validate_artifacts.py --pipeline mh --mode all --xsq-path c15/out/sample_twinklr_mh.xsq --fixture-config-path c15/out/fixture_config.json --output-json c15/out/mh_xsq_issues.json` | Note printed; `MH XSQ Validation: PASS`; 4 models, 1,726 effects, 0 issues; exit 0 |
| `validate_artifacts.py --mode xsq --xsq-path c15/out/sample_twinklr_mh.xsq nonexistent_seq` (auto) | Detected `mh` from the filename; PASS |
| `validate_artifacts.py --pipeline mh --mode plan --xsq-path …` | Note printed; exit 2 |
| `validate_artifacts.py --pipeline mh --mode xsq --xsq-path c15/out/mutated_twinklr_mh.xsq` (one `ref` set to 9999, one effect moved to overlap) | `MISSING_REF` error and `OVERLAP` warning; exit 1 |
| `validate_artifacts.py --pipeline display --mode all --xsq-path tests/regression/baselines/02_rudolph_display.xsq --plan-path tests/regression/baselines/02_rudolph.group_plan_set.json nonexistent_seq` | Display path runs as before: plan mode reports the missing holistic evaluation; XSQ mode reports 10 target-coverage warnings (no alias map) |

`scripts/README.md`, `scripts/validation/README.md` and `docs/developer-guide.md`
describe the result. No other script under `scripts/` targets the deleted renderer
(`git grep` for the removed names in §7 finds none in `scripts/` outside
`scripts/validation`, and every import resolves).

## 5. `changes/`

- `changes/ACTIVE.md`: the true-up row says the cutover C1.1–C1.5 is complete on
  `feat/mh-true-up-p3` (not merged, not pushed); revised in §11 (next W0–W9).
- `plan/handoff.md`: a "Start here" section at the top with the commit list, validation,
  owner-gated items and open owner questions, and a dated cutover entry at the end;
  frontmatter `status: active`.
- `plan/phase-3-arrangement.md`: a dated C1.5 section.

## 6. Not changed, and why

Historical, by the brief: other change folders and `evaluations/`. Flagged for the
integrator because they are used operationally and now name deleted things:

- `changes/twinklr-reactivation-review/runbooks/04-xlights-gui-and-human-acceptance.md`
  (`:133`, `:169`, `:181`, `:188`, `:283`, `:309`, `:320`): commands and layout content
  for the deleted golden acceptance suite (`tests/golden/test_xlights_acceptance.py`,
  `harness.py`, `xlights_client.py`, the `requires_xlights` marker, `mh4_*` goldens).
- `changes/twinklr-reactivation-review/runbooks/05-phase-2p-and-3-live-evidence.md:197`:
  compares with the deleted `tests/regression/baselines/11_need_a_favor.metrics.json`.
- `evaluations/INDEX.md` and `evaluations/2026-08-13-golden-fixture-mh4-minimal/`:
  a `PENDING-OWNER` judgment of a fixture the deleted renderer rendered;
  `evaluations/2026-11-12-claude-baseline-live-run/` likewise rendered with it. Records,
  not rewritten; `context/current-state.md` notes the golden-fixture exit.
- `changes/ACTIVE.md`'s reactivation-review row asks for the Claude-baseline judgment of
  a `rendered.xsq` from the deleted renderer. Not changed (another workstream's row).
- `docs/audio_profile/` and `docs/feature_engineering/`: narrative series (§1).
- `memories/decisions/display-stays-lit.md:98-100` cites the superseded decision as its
  reason for keeping the detected grid on the moving-head path; the statement is still
  true of the current renderer, and the cited memory now carries its supersession note.

## 7. Final grep

Across `docs/ context/ memories/ prompts/ scripts/ README.md HOME.md AGENTS.md`, with
`grep -rn -I` (so the three new, untracked memories are included):

| Pattern | Hits | Each justified |
|---|---|---|
| `legacy_v1` | 1 | `memories/decisions/mh-single-renderer.md:31`: the decision's context names the deleted default |
| `physical_v2` | 1 | the same line |
| `moving_heads_physical` | 0 | — |
| `template-export`, `template_export` | 1 | `mh-single-renderer.md:24`: lists what was deleted |
| `transitions` (word, case-sensitive) | 36 lines | Refused job key: `docs/user-guide.md:228`, `docs/pipeline_guide.md:804`, `context/current-state.md:44`. History of the deletion: `memories/decisions/mh-single-renderer.md:23`, `memories/learnings/model-dump-hashes-rekey-caches.md:26`, `memories/learnings/live-provider-run-lessons.md:31` (with its dated note). A metric the report does not hold: `docs/user-guide.md:990`. The feature-engineering transition graph, another subsystem: `docs/pipeline_guide.md:328`, `scripts/demo_feature_engineering.py:466,989,992,1595,1598`. Musical or FE sense in the narrative series: 23 lines in `docs/audio_profile/03_the_architecture.md` and `docs/feature_engineering/*.md` |
| `moving_heads.mode` | 5 lines | The refused key: `docs/user-guide.md:228`, `docs/pipeline_guide.md:804`, `context/current-state.md:44`. History: `memories/decisions/mh-single-renderer.md:23`, `memories/learnings/model-dump-hashes-rekey-caches.md:26`. Every other `mode` hit is a `--mode` flag, `movement.mode`, `repeat.mode` or a coordination mode |
| Old names from the C1.2–C1.4 records (`PHYSICAL_RENDERER_REVISION`, `LEGACY_BACKEND_ID`, `admit_physical_catalog`, `compile_physical_*`, `Physical*Error`, `Physical*Spec`, `PhysicalRenderSummary`, `XsqAdapter`, `TransitionConfig`, `load_builtin_templates`, `xlights_semantic_groups`, `use_16bit_pan_tilt`, `shutter_map`, `color_map`, `gobo_map`, `pan_offset_deg`, `ShutterMap`, `ChannelInversions`, `PanTiltRange`, `MovementLimits`, `movement.physical`, `dimmer.physical`, `physical_shutter` …, `phase_offset`, `templates/builtins`, `step_compiler`, `regen-goldens`, `golden.harness`) | 8 lines | `docs/user-guide.md:314` and `:545-548`: the lists of refused keys, named so a user can delete them; `memories/learnings/live-provider-run-lessons.md:34` (`XsqAdapter`, the dated history note) and `memories/decisions/mh-render-matches-pre-cleanup-look.md:84` (`MovementLimits`, superseded history); `scripts/enrich_builtin_templates.py:4`: `catalog/templates/builtins/`, the display recipe builtins |
| `legacy` (any case) | 8 lines | `docs/pipeline_guide.md:279,1122` (FE corpus run), `docs/qa-runbook.md:93` (retired config fields in general), `memories/decisions/typed-macro-coordination-contract.md:30` and `lane-blend-mode-overrides-recipe.md:23` (other subsystems' history), `scripts/demo_recipe_pipeline.py:684` (recipe synthesis), and the two new memories naming the tag `mh-last-with-legacy-renderer` and `legacy_v1` |

## 8. Checks run (this tree, this session)

| Command | Result |
|---|---|
| `uv run pytest tests -q --no-cov` | 6,512 passed, 30 skipped, 0 failed: the C1.4 count (6,515) minus the 4 deleted plan-validator tests and the deleted MH-shape detection test, plus the 2 added |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | 1,287 files already formatted |
| `uv run mypy packages/twinklr` | Success: no issues found in 644 source files |
| Doc link checker | The repository has none (no Makefile target, no CI step, no test). `c15/check_links.py` checked every relative link and `#anchor` (GitHub slugs) in the 29 Markdown files changed or added here: 0 broken |
| `uv run pytest tests/unit/scripts -q --no-cov` | 26 passed |
| Script runs | §4 |

## 9. Could not verify

- The integrator's report that `make validate` passed on `24c22b79` (6,515 passed, 30
  skipped) is recorded as theirs; the C1.4 record has the same pytest counts.
- The user-guide statement that an upgrade re-plans each song once and makes `regenerate`
  refuse older injections is derived from code and the C1.3/C1.4 records; it was not
  observed against a real cache or a real injected sequence.

## 10. Noticed, not fixed (outside the renderer cutover)

- `scripts/demo_eval_report.py` cannot run: it passes `xsq_path=` to
  `generate_evaluation_report`, which has not taken it since `5c74992f` (P1P-T11), and
  reads `artifacts/need_a_favor/checkpoints/plans/need_a_favor_final.json` where runs
  write `checkpoints/plans/final.json`. It does not target the deleted renderer;
  `twinklr eval-report` is the supported entry point. Owner or integrator to decide
  between fixing and deleting it.
- `validate_artifacts.py`'s default display `.xsq` path is
  `artifacts/<name>/<name>_display.xsq`, while `twinklr display` writes
  `<song>_twinklr_display.xsq`; `--xsq-path` works around it. Display code, not changed.
- `parse_dmx_settings` reads any key containing `DMX`, so `E_CHECKBOX_INVDMXn=0` is parsed
  as channel n and only the later `E_SLIDER_DMXn` entry restores the slider value. The
  builder writes the sliders after the checkboxes, so current output parses correctly
  (`test_frame_encoder.py` asserts it); the parser depends on that order.

## 11. Revision: the unrendered song intent is a known regression — 2026-11-17

The first pass described the renderer as rendering "templates as authored" and not
applying planner intent, as if that were the design. The owner has since ruled
([plan](../../plan/phase-3-arrangement.md#2026-11-17-owner-direction--the-planners-song-intent-must-be-rendered-not-cut),
[song-intent rendering](../../plan/song-intent-rendering.md)): the cutover regressed the
planner's song intent, all of it is to be rendered on the single path (W0–W9), and
nothing is cut from the planner contract. Facts used, checked at `24c22b79`: the
renderer applies template, segment bars, preset and section bounds only and emits the
"not applied" diagnostic per section (`sequencer/moving_heads/pipeline.py:1713-1726`);
`twinklr show` does not project the macro palette or focal role
(`pipeline/show_stages.py:63-68`); the deleted renderer's handling is in the plan's gap
table.

| File | Change |
|---|---|
| `docs/overview.md` | `:10` and Current Scope: a "Known regression" statement naming what is not rendered yet, linking the plan; the "renders as authored, does not apply" wording removed |
| `docs/user-guide.md` | `moving_heads` row: renders template, preset and bars "but not yet the planner's song intent", linking a new **Known regression** paragraph under What the Pipeline Does (what is not rendered, `show`'s palette and focal role, that the earlier renderer rendered them, the plan); the `show` paragraph says palette and focal role are "not yet" projected, a known regression |
| `docs/pipeline_guide.md` | Render step: what is not rendered yet, a known regression, linking the plan |
| `docs/developer-guide.md` | Intensity: "does not yet render planner intensity, a known regression being fixed" |
| `README.md` | Categorical Planning and the design table: "does not yet render … known regression", linking the plan |
| `context/current-state.md` | Multi-agent planning item and a **Known regression** bullet in the moving-head item (what is applied, what is ignored, `show`, that the deleted renderer rendered them, the owner's direction, W0–W9, "the renderer is not complete until then"); Active work names the regression and W0–W9 |
| `context/architecture/multi-agent-planning.md` | A **Known regression** paragraph with the owner's ruling and links; the principles line says "does not yet render" |
| `context/glossary.md` | Categorical planning: "does not yet render planner intensity: a known regression" |
| `memories/decisions/mh-single-renderer.md` | Consequences: the cutover deleted the intent layer without a counterpart, the proof showed only unchanged surviving bytes, the owner rejected cutting the intent; links to the plan and the new learning |
| `memories/decisions/llm-plans-intent-renderer-implements-precision.md`, `coordinated-show-contract.md` | Notes say "not yet", call it a regression and link the plan (W9 for `show`) |
| `memories/learnings/prove-parity-before-deleting.md` | **Added.** Before deleting a replaced implementation, compare old and new on the same inputs; unchanged surviving bytes do not show nothing was lost. Existing owner searched: `patterns/render-output-proof.md` covers the byte matrix only; it gains a "Limit" section pointing here rather than a duplicate |
| `memories/INDEX.md` | The new learning; the decision and pattern entries annotated |
| `changes/ACTIVE.md`, `plan/handoff.md` | Next work is W0–W9 (song-intent rendering), not T1–T5; the known regression stated; open question (a) answered (owner: keep and render colour and lyric cues; `variation` stays planner-chosen); the T1 design draft and D7 withdrawn; W2's live probe and the W4–W9 views listed as owner-gated |
| `plan/phase-3-arrangement.md` | The C1.5 section notes this revision |

Checks after the revision: see §12.

## 12. Checks after the revision (this session)

| Command | Result |
|---|---|
| `uv run pytest tests/unit/config tests/unit/agents/test_model_retarget.py tests/unit/agents/test_structured_outputs.py tests/unit/scripts tests/unit/sequencer/moving_heads/export/test_frame_encoder.py tests/regression -q --no-cov` (tests that read documents, plus the touched script tests) | 769 passed |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | 1,287 files already formatted |
| `c15/check_links.py` on the 31 Markdown files changed or added | 0 broken |
| `grep` for "as authored and does not apply", "does not apply planner", "applies no planner", "T1–T5" in `docs/*.md context README.md memories changes/ACTIVE.md` | No hits |

The full suite was not rerun after the revision, which touched Markdown only; its last
run (§8) was 6,512 passed, 30 skipped.

## 13. Review corrections — 2026-11-17

An independent review of `9e7205cf` requested changes. Applied in the working tree (no
`packages/` change; another agent's uncommitted W0 files were not touched):

| Finding | Change |
|---|---|
| HIGH: merging would put the regression on `main` | `changes/ACTIVE.md` and `plan/handoff.md` state that `main` still has the renderer that applies song intent, so the branch stays unmerged until W0–W9 land unless the owner says otherwise; "owner: merge and push" removed as a next action; the owner-gated merge item says "after W0–W9" |
| Look acceptance called the reference | `memories/decisions/mh-single-renderer.md` (decision and consequences) and `context/current-state.md` (moving-head item, live-evidence row): that render applied no planner intensity, colour, events or cues; the acceptance covers the templates' motion and timing, not the absence of song intent, which W4–W9 add with owner views |
| Regression statement missing | `context/product/overview.md` (moving-head scope) and `docs/qa-runbook.md` §7 state it with the plan link; §6 notes moving-head colour, intensity and transitions are not planner-driven yet |
| Plan: field mapping | `plan/song-intent-rendering.md` gains an old → new field mapping table, one row per current planner field (from `agents/sequencer/moving_heads/models.py` and `sequencer/models/transition.py` at `24c22b79`), marked kept / reshaped same range / reshaped narrower / new, and "W2 does not start until the owner has seen this table and given their word on every narrower row". Narrower rows: `preset_id` → `reach`/`rate` (open points: COMPACT+SLOW has no catalog preset; `--template-dir` presets with other names are unreachable), `modifiers`, `transition_in`, `transition_out`. The additions list is corrected (section `gobo`, `reach`, `rate`, `variation`, `density`, `motif_id`, HIT, COLOR events, `entry`/`exit`/`transition_length`) |
| Plan: intensity | Null and SMOOTH as authored; SLOW and FAST as SMOOTH (owner revert of 2026-11-12, W0 record); DRAMATIC and INTENSE add a beat-locked pulse and raise the floor, never below the authored look; W5's view judges the table |
| Plan: refusals | Replaced by deterministic repair: drop or adjust the one item, record it in the trace, feed it back to the planner; the run never fails for it; W2 tests the loop |
| Plan: timing | New rules: dark lead before a reveal bounded to half a beat (proposed), the gate publishes dark phases, HIT forces a lit frame, colour-change dips at boundaries that play lit today are a look change judged at W4 |
| Plan: W1 layout read | Owner-gated; W1 tests derivation on a synthetic layout only; added to the handoff's owner-gated list |
| Plan: T2, T4; cache consequences | T2 → W3; T4 emits the new contract in W2, arrangement after W9; W2 re-keys planner caches and refuses old checkpoints and live plans, owner told before merge |
| Plan: W0 result | 20 strict xfails mapped W4: 5, W5: 2, W6: 5 + cue-bound shutter, W7: 2, W8: 4, W9: 1; the focal-role rule needs its own W9 check; old defects not carried over |
| Plan: schema figure | Marked as the architect's scratch measurement; W2 measures and pins the real one |
| Plan: stale diagnostics | Listed under W2 (`sequencer/moving_heads/pipeline.py:1719-1721`, `pipeline/show_stages.py:66-68` and `:189-200`) |
| LOW: intensity vocabularies | `README.md`, `context/architecture/multi-agent-planning.md`, `context/glossary.md`, `docs/developer-guide.md`: WHISPER…PEAK is the display's; SLOW/SMOOTH/FAST/DRAMATIC/INTENSE the moving-head planner's (`sequencer/models/enum.py`) |
| LOW: refusal exception | `context/current-state.md`: fixture fields retired before 2026-08 are dropped with a warning (`config/fixtures/removed_fields.py:28-40`; call sites `groups.py:53-57`, `instances.py:60`, `dmx.py:28`) |
| LOW: C1.5 status | Consistent in `plan/handoff.md`, `phase-3-arrangement.md` and this record: committed as `9e7205cf`, reviewed, corrections in a follow-up commit; the handoff's commit table says it lists code and record commits only (`6caf7cba`, `462ad93e` named as left out) and gains a W0 row; the start-here section is separated from the 2026-11-12 planning log by a heading |
| Provenance | The architect's gap inventory is committed as `evidence/2026-11-17-song-intent-gap-inventory/README.md`: header (read-only, 2026-11-17, `5d50580c` vs `24c22b79`, superseded where the plan differs) plus the final report extracted from the agent's JSONL transcript by reading from the end (`c15/extract_final.py`); a comparison after reversing the heading demotion found it identical (26,126 characters). The plan's "Source" line points at it |

Checks after these corrections: §14.

## 14. Checks after the review corrections (this session)

| Command | Result |
|---|---|
| `uv run pytest tests/unit/config tests/unit/agents/test_model_retarget.py tests/unit/agents/test_structured_outputs.py tests/unit/scripts tests/unit/sequencer/moving_heads/export/test_frame_encoder.py tests/regression/test_mh_pins.py tests/regression/test_xsq_parity.py -q --no-cov` | 769 passed |
| `uv run ruff check packages tests scripts` | All checks passed |
| `uv run ruff format --check packages tests scripts` | 1,289 files already formatted (includes the uncommitted W0 files) |
| `c15/check_links.py` on every Markdown file changed or added in the tree, plus the plan, the decision and the snapshot | 0 broken |
