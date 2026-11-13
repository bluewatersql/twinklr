---
type: plan
status: proposed
area: engineering
created: 2026-11-12
updated: 2026-11-13
---

# P0 Behavior Contracts and Reference Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Make legacy behavior, requested-but-ineffective controls, and comparison
inputs explicit before changing rendered output.

**Architecture:** Keep the current rendering path intact. Add a versioned render-policy
selection, structured diagnostics and functional identity, then extend synthetic test
support and compose a restrained reference policy from the existing catalog/selector.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest; existing renderer and catalog.

**Spec:** [Shared contracts](architecture.md), [report §8 P0](../report.md#phase-p0--establish-the-behavior-contract-and-reference-cases).

**Kickoff:** [implementation brief](../implementation-brief.md). Source seams below were
rechecked on 2026-11-13 at `f067a56`; the kickoff checklist in the brief repeats that
check against the actual starting `main`.

## Global constraints

- Python 3.13 only; uv workspace; Pydantic V2 for public/LLM-facing data.
- `legacy_v1` remains the default; physical behavior changes require explicit opt-in.
- The emitted effect grid remains 20 ms; timing markers remain source-exact.
- No project source is changed while preparing this plan; all tasks below are future work.
- Read all [shared requirements](architecture.md#1-goals-and-boundaries).
- Follow the [documentation, registry and test rule](README.md#documentation-registry-and-test-surfaces):
  a task that changes a documented or inventoried surface updates it in the same commit.

## Review focus

1. Old jobs must not accidentally select new behavior — T1 compatibility tests.
2. Claimed 16-bit/limit/intensity support must not hide ineffective output — T2 diagnostics.
3. A content-only preset edit must invalidate relevant render identity — T2 fingerprint tests.
4. Missing/odd-count fixtures and changing tempo must not be absent from the baseline — T3.
5. New reference policy must not change the frozen selector experiment — T4 regression.
6. A new config field must not land without its inventory record and published
   documentation — T1 registry and user-guide updates.

## File ownership and ordering

T1 and T2 both edit `pipeline.py` and run in that order in one worktree. T3 and T4
share no file with them or with each other and may run in parallel worktrees. The
integrator merges, then writes the evidence record.

| Path | Task | Notes |
|---|---|---|
| `packages/twinklr/core/config/models.py` | T1 | `MHRenderPolicy`, `JobConfig.moving_heads`, schema `3.0 \| 3.1` |
| `packages/twinklr/core/sequencer/moving_heads/pipeline.py` | T1, then T2 | Mode rejection (T1); diagnostics/fingerprint accessors (T2) |
| `tests/config_effects_registry.py`, `tests/unit/config/test_config_inventory.py` | T1 | Inventory dispositions for the changed and new job paths |
| `docs/user-guide.md`, `docs/overview.md`, `docs/pipeline_guide.md` | T1 | Published schema-version and job-config statements |
| `tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py` | T1 | One added test: the stage reports the unsupported mode as a failure |
| `tests/unit/config/test_mh_render_policy.py` (new) | T1 | |
| `moving_heads/diagnostics.py`, `moving_heads/identity.py` (new) and their two test files | T2 | |
| `tests/support/__init__.py`, `tests/support/mh_true_up.py`, `tests/unit/sequencer/moving_heads/test_true_up_cases.py` (new) | T3 | |
| `agents/sequencer/moving_heads/reference_policy.py` and its test file (new) | T4 | |
| `changes/2026_11_12_mh_true_up/evidence/<date>-p0-baseline/` | Integrator | After T1–T4 merge |

## Technical design

### Baseline and policy

Current sources: [JobConfig](../../../packages/twinklr/core/config/models.py),
[render pipeline](../../../packages/twinklr/core/sequencer/moving_heads/pipeline.py),
[golden harness](../../../tests/golden/harness.py),
[selector](../../../packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py).
The old plan schema's omission provenance and accepted goldens remain authoritative
for legacy behavior. Do not regenerate them just because new physical math differs.
The owner decision that fixes the legacy look is
[mh-render-matches-pre-cleanup-look](../../../memories/decisions/mh-render-matches-pre-cleanup-look.md);
P0 reports the controls that decision leaves ineffective and repairs none of them.

Proposed `MHRenderPolicy` has `mode: Literal['legacy_v1','physical_v2']='legacy_v1'`.
P1 adds the physical policy's supported settings. Add `JobConfig.moving_heads` with a
default factory and allow schema `3.0 | 3.1`, retaining `3.0` by default. Validate that
`physical_v2` requires `3.1`. Until P1 is integrated, requesting physical mode raises
an explicit unsupported-mode exception before rendering, never silently falling back.

The rejection lives at the top of `RenderingPipeline.__init__`, before any template
load or output path is touched, and raises a new `UnsupportedRenderModeError(ValueError)`
defined in `pipeline.py` beside the existing pattern of
`UnsupportedRigShapeError(ValueError)` in the template compiler. All three constructors
of the pipeline (`rendering_stage.py`, `pipeline/show_stages.py`,
`reporting/evaluation/rerender.py`) pass `job_config`, so one check covers them.
`MovingHeadRenderingStage` wraps render failures in a broad `except Exception`; T1
adds `test_unsupported_render_mode_fails_the_stage` to the existing
`test_rendering_stage.py`, asserting the stage reports a failure that names the mode
and writes no deliverable.

`JobConfig` is `extra="ignore"`, so a `3.0` job with no `moving_heads` key keeps loading
and gets the default policy. `MHRenderPolicy` itself forbids extra fields.

### Published and inventoried surfaces changed by T1

`job.schema_version` stops being a single fixed value, and `job.moving_heads` is a new
external config path. Three existing guards and three documents depend on that:

| Surface | Today | T1 change |
|---|---|---|
| `tests/config_effects_registry.py` → `job.schema_version` | `INVARIANT_TEST` pointing at `test_fixed_policy_config_paths_are_invariant` | Becomes `EFFECT_TEST` pointing at `tests/unit/config/test_mh_render_policy.py::test_physical_mode_requires_schema_31`: the value now selects whether physical mode is admissible |
| `tests/config_effects_registry.py` → new `job.moving_heads`, `job.moving_heads.mode` | Absent; `test_every_external_config_path_has_an_accountable_disposition` fails on any unregistered path | Add both as `EFFECT_TEST` pointing at `test_unimplemented_physical_mode_is_rejected` |
| `tests/unit/config/test_config_inventory.py::test_fixed_policy_config_paths_are_invariant` | Asserts `JobConfig(schema_version="future")` is rejected, under a docstring saying fixed policies reject every alternate value | Keep the `"future"` rejection; move it out of the "fixed policy" test or reword the docstring so the test no longer claims the schema version has one value |
| `docs/user-guide.md` job-config section | Says "Schema version 3.0"; the `schema_version` row says "Fixed schema identity; other values fail validation" | State that `3.0` is the default and `3.1` is accepted; add a `moving_heads.mode` row with ledger path `job.moving_heads.mode`, default `"legacy_v1"`, and the fact that `physical_v2` needs schema `3.1` and is rejected until the physical renderer ships |
| `docs/overview.md` configuration section | "Schema version is 3.0" | Same correction |
| `docs/pipeline_guide.md` job-config section | "The live schema is version 3.0" | Same correction |

`tests/unit/config/test_documented_config.py` requires every user-guide ledger row to
have a live registry record with a collecting test node, so the registry entries and
the new guide row land in the same commit. `docs/qa-runbook.md` mentions
`schema_version` only as a load failure cause and needs no change.

### Diagnostics and fingerprint

Proposed `diagnostics.py` owns `MHDiagnostic` (frozen Pydantic model):
`code: str`, `severity: Literal['info','warning','error']`, `message: str`,
`fixture_id: str|None`, `section_id: str|None`, `channel: str|None`,
`control: LegacyControl | None`,
`action: Literal['unchanged','rejected','substituted']`. Codes are the shared contract's
bounded vocabulary; implement them as `Literal`/enum, not unconstrained arbitrary codes.

Every P0 diagnostic carries code `legacy_ignored`, so the code alone cannot tell one
ineffective control from another. `control` names it, from a closed `LegacyControl`
enum with the five members in the table below. It is `None` for the non-legacy codes
that later phases emit.

`audit_legacy_controls(plan: ChoreographyPlan, fixtures: FixtureGroup,
templates: Sequence[TemplateDoc]) -> tuple[MHDiagnostic, ...]` diagnoses only actually
requested ineffective fields, not every theoretical feature. Diagnostics have
deterministic ordering and do not mutate a plan or generated output.

Each control's current behavior is already pinned by a test. That test, not this table,
is the authority: the implementer confirms each starting predicate against the cited
source and pinning test before writing the diagnostic test, and corrects the table in
the same commit if they disagree.

| `control` | Starting predicate | Source | Pinned today by |
|---|---|---|---|
| `pan_tilt_fine` | A fixture's `DmxMapping` sets `use_16bit_pan_tilt` with a fine channel mapped | `export/dmx_settings_builder.py` emits the fine channel's inversion flag but no fine-channel values | The flag's effect on emitted settings is pinned by `test_dmx_settings_builder.py::test_inversions_and_16bit_flag_change_emitted_settings`. Nothing pins the absence of fine values; T2's test is the first to do so |
| `movement_intensity` | A section or preset resolves a movement intensity other than `SMOOTH` and the template step's movement params carry no `intensity` key | `handlers/movement/default.py` replaces the argument with `params.get("intensity", SMOOTH)` | `tests/unit/sequencer/moving_heads/test_movement_intensity.py::test_intensity_argument_does_not_change_the_movement` |
| `movement_limits` | A fixture's `MovementLimits` differ from the model defaults and the section's template has dynamic movement | Dynamic excursion is bounded to normalized 0–1, not the window | `tests/golden/test_movement_ignores_calibrated_range.py` |
| `template_dimmer_floor` | A selected template declares a dimmer floor above the minimum its own dimmer steps reach | The floor survives as metadata only | `tests/golden/test_dimmer_template_floor_not_applied.py` |
| `shutter_channel_scope` | The plan or template carries shutter intent and the fixture maps shutter above channel 16 | Intent is dropped with a trace; the declared default is still emitted | `tests/golden/test_shutter_channel_emission.py::test_shutter_channel_17_emits_its_declared_default` |

For `shutter_channel_scope` the diagnostic distinguishes the two facts the golden
pins: shutter *intent* above 16 is ignored, while the channel's declared *default*
is emitted. A fixture with shutter on channel 17 and no shutter intent in the plan
produces no diagnostic.

Default values never trigger a diagnostic: a fixture carrying the default movement
limits, or a template with no declared floor, has requested nothing. A fine channel
mapped without `use_16bit_pan_tilt` is likewise not a request for 16-bit output and
produces none.

`identity.py` owns `render_fingerprint(*, plan: BaseModel, beat_grid: BeatGrid,
fixtures: FixtureGroup, templates: Sequence[TemplateDoc], policy: MHRenderPolicy,
backend_id: str, renderer_revision: str, seed: int | None=None,
phase_map: BaseModel | None=None) -> str`. The optional phase map is P1's typed boundary
map; P0 accepts a BaseModel to avoid depending on a future implementation. Hash canonical JSON of functional
inputs, including template content, not just IDs. Include the 20 ms grid and emitted
version stamp, read from `EFFECT_GRID_MS` and `XLIGHTS_VERSION_STAMP` in
`formats/xlights/sequence/fresh.py` rather than restated. Treat diagnostic wording/output paths as nonfunctional; motion/profile,
ordering, seed and preset changes are functional. Legacy artifacts need no new cache
read path; record the fingerprint in the new research/physical manifests first.

`identity.py` also defines the two legacy constants callers pass for the current
path, `LEGACY_BACKEND_ID` and `LEGACY_RENDERER_REVISION`. The revision is bumped by
hand in the commit that intentionally changes legacy rendering; nothing derives it.

`PlanSection` keeps its legacy omitted-intent flag in a Pydantic private attribute
(`_legacy_intent_omitted`), which `model_dump` does not serialize. The flag is
functional: `RenderingPipeline._resolve_section_intent` returns an empty
`SectionRenderIntent` when it is set. The canonical payload therefore includes
`legacy_intent_omitted` per section, and a test proves two plans differing only in
that flag hash differently.

Pipeline exposure is read-only and lazy: `RenderingPipeline.diagnostics` returns the
audit tuple for the plan's resolved templates, and `RenderingPipeline.fingerprint()`
returns the hash for the legacy constants. Neither runs during `render()`, and P0
changes no sidecar, trace schema (`twinklr-xsq-trace.v2`), delivery artifact or log
contract. The P0 consumer of both is the evidence record in the exit section; P1.6
is the first to persist them beside artifacts.

### Synthetic matrix

Reuse golden harness construction patterns without loading local fixture files.
New support module `tests/support/mh_true_up.py` provides
`synthetic_case(case_id: str) -> SyntheticMHCase` containing a plan, BeatGrid, fixture
group and expected-case metadata. `tests/support/` does not exist yet; create it as a
package, importable as `tests.support.mh_true_up` the way tests already import
`tests.golden.harness`. Explicit cases:

| Case | Content | What it exposes | Runs through the legacy pipeline in P0 |
|---|---|---|---|
| `counts` | 1,2,3,4,6,8 fixtures with stable IDs | Role/topology and subset behavior | Yes; see below |
| `fine_carry` | Nonadjacent coarse/fine mappings | 255→256 word carry and inversion | Yes, for the `pan_tilt_fine` diagnostic; the carry vectors are input only |
| `channel_edges` | Shutter17, final supported48, unsupported49 | Backend versus old intent ceiling | Shutter 17 only; 48 and 49 are input only |
| `tempo` | Beat ms `[0,500,1000,1500,2000,2400,2800,3200,3600]`; bars `[0,2000,3600]` | Exact internal musical phase | Yes |
| `meter3` | Three beats per bar; constant beat interval | No assumed four-beat subdivision | Yes |
| `finite` | Non-closing fade, one-shot accent, section shorter than cycle | End-state/wrap semantics | Yes |
| `state` | Unknown initial pose, known darkness, too-short dark gap | Honesty about feasibility | No; input only |
| `locks` | Motion locked while intensity changes | Future boundary/lock checks | No; input only |

Matrices specify synthetic speed/range values as test inputs, not calibration facts.
Physical cases can be model-validation fixtures until P1 supplies the compiler; do
not mark unimplemented physical behavior passing or permanently xfail its desired tests.

`SyntheticMHCase` is a frozen dataclass. `legacy_runnable: bool` records the last
column. Input-only data is held as plain typed values (ints, floats, strings, tuples)
in a `physical_inputs` mapping; P0 imports no P1 type, and P1 converts these values
into its own models when it adopts a case.

Build coarse-only fixtures with the harness's `RigSpec` and `build_fixture_group`.
`RigSpec` has no fine-channel or 16-bit field and the harness is not edited, so
`fine_carry` and the channel 48/49 inputs construct `FixtureGroup` and `DmxMapping`
directly in `mh_true_up.py`. Build the
nonuniform `tempo` grid the way `build_uneven_beat_grid` does (explicit bar and beat
boundaries, eighth/sixteenth boundaries derived from the beats). Each legacy-runnable
case is a single-section plan naming one builtin template, recorded in the case
metadata.

The legacy compiler raises `UnsupportedRigShapeError` when a template step targets a
fixture group the rig cannot supply. `tests/golden/test_8head_rig_renders.py` pins that
rejection for a single-fixture rig given a template addressing LEFT and RIGHT, and
pins that the 8-head rig renders. For `counts`, the baseline for each head count is
therefore whichever of "rendered" or "rejected with this error" the legacy pipeline
actually produces for the case's template. Record it; a rejection is a baseline
outcome, not a defect for P0 to repair.

### Restrained reference policy

The existing selector and `three_arm.py` contain fixed experiment policies. Preserve
them. Add a separate **reference policy adapter**, sharing catalog lookup, candidate
resolution and validation rather than changing those fixed defaults. Use deterministic
preferred existing templates: quiet sections `hold_center_out_breathe`, choruses
`sweep_lr_pingpong_phase`, section-entry emphasis `sweep_lr_fan_hold`, ending
`wave_scattered_fade_out`. A preference is filtered against admitted capabilities and
catalog availability; missing preference uses the existing selector's candidates with
stable seeded order and an explicit trace. No eligible template is an error.

This is a restrained comparison using existing templates, **not a claim to reproduce
xLights' precise envelopes**, which would require new components in P2. Label its arm
`reference_legacy_v1`; a later physical reference has its own fingerprint/arm identity.
No LLM calls, heuristic retuning after seeing comparison scores, or old-experiment edits.
Preference precedence is final section → ending template; chorus/drop/peak role →
chorus template; build/lift role → entry-emphasis template; energy≤33 → quiet
template; otherwise unchanged candidate-helper fallback. This is a declared policy,
not a classifier inferred from section display names.

Resolution per section, in order:

1. Run the unchanged `DeterministicSelector(seed=seed).select(sections)` once and keep
   its `SelectorResult` as `baseline`.
2. Compute the preference from the precedence above. "Final section" is the last
   element of `sections`; roles compare case-insensitively, as the selector does.
3. If the preferred template exists in the registry and is in `admitted_template_ids`,
   select it. A preferred pick is exempt from the selector's variety constraints
   (repeat cap, consecutive repeats, distinct roles): every chorus gets the chorus
   template by design.
4. Otherwise select the baseline's choice for that section if it is admitted.
5. Otherwise select from that section's baseline `eligible_template_ids` intersected
   with the admitted set, ordered by SHA-256 of `"{seed}:{section_id}:{template_id}"`,
   the selector's own ordering formula. That list is the baseline's candidates after
   its variety filtering, taken as traced; the reference arm applies no variety
   constraint of its own in steps 4 and 5.
6. Otherwise raise `ValueError` naming the section.

A selected template that differs from the baseline needs a `PlanSection` built from
that template's document, because the selector derives color, shutter and gobo intent
from the document. That builder is the selector's private `_build_plan_section`. The
adapter calls it on its own `DeterministicSelector` instance, as
`reporting/evaluation/rerender.py` already calls a private pipeline method across
modules. `deterministic_selector.py` is not edited at all, which keeps the
old-experiment guarantee literal.

## Implementation tasks

### P0-T1 — Render-policy compatibility boundary

**Files:** Modify `packages/twinklr/core/config/models.py`,
`packages/twinklr/core/sequencer/moving_heads/pipeline.py`,
`tests/config_effects_registry.py`, `tests/unit/config/test_config_inventory.py`,
`tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py`,
`docs/user-guide.md`, `docs/overview.md` and `docs/pipeline_guide.md`; create
`tests/unit/config/test_mh_render_policy.py`.

**Interfaces:** Produces `MHRenderPolicy`, `JobConfig.moving_heads` and
`UnsupportedRenderModeError` described above; consumes existing `JobConfig` and
`RenderingPipeline` constructor.

- [ ] Write `test_omitted_policy_retains_legacy`: assert `JobConfig().schema_version == '3.0'`
  and `JobConfig().moving_heads.mode == 'legacy_v1'`, and that a `3.0` payload with no
  `moving_heads` key validates equal to `JobConfig()`.
- [ ] Write `test_physical_mode_requires_schema_31` (a `3.0` job selecting `physical_v2`
  fails validation; a `3.1` job with `legacy_v1` loads) and
  `test_unimplemented_physical_mode_is_rejected`: build the pipeline from the golden
  harness's plan, grid and `mh4_minimal` rig with a `3.1`/`physical_v2` job and an
  `output_path` under `tmp_path`; assert `UnsupportedRenderModeError` and that no file
  was written. No silent mode change or partial file.
- [ ] Run `uv run pytest tests/unit/config/test_mh_render_policy.py -q`; verify the new
  tests fail for missing behavior, then add the fields/validators and explicit dispatch.
- [ ] Add `test_unsupported_render_mode_fails_the_stage` to `test_rendering_stage.py`.
- [ ] Update the three inventory/registry surfaces and the three documents in the table
  above. Run `uv run pytest tests/unit/config -q`; expect the inventory, documented-config
  and discriminator suites to pass with the new paths registered.
- [ ] Rerun
  `uv run pytest tests/unit/config/test_mh_render_policy.py tests/golden/test_settings_golden.py tests/unit/sequencer/moving_heads/test_rendering_pipeline.py tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py -q`;
  expect all selected tests pass without `--regen-goldens`. Unchanged goldens are the
  proof that the default path renders as before.
- [ ] Have a separate reviewer inspect the default-path diff; integrator commits
  `feat(mh): define versioned render policy without changing legacy output`.

### P0-T2 — Effective-control diagnostics and render identity

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/diagnostics.py`,
`identity.py` in the same directory, and
`tests/unit/sequencer/moving_heads/test_render_identity.py`, `test_control_diagnostics.py`.
Modify the MH pipeline only to expose diagnostics/identity, not to repair controls.

**Interfaces:** Consumes T1 policy plus existing plan/grid/template/fixture models;
produces the audit and fingerprint functions above, the `LegacyControl` enum, the two
legacy constants, and the two read-only pipeline accessors.

- [ ] Confirm each row of the control table against its source and pinning test;
  correct the table where the pinned behavior differs.
- [ ] Write one test per `LegacyControl` member asserting its predicate produces
  exactly that diagnostic and its absence produces none; ordinary
  supported coarse-only output is unchanged; unavailable shutter intent is distinguished
  from an available default channel; source inputs are not mutated.
- [ ] Write identity tests: reorder irrelevant dict keys → same hash; change template
  content, fixture order, policy or BeatGrid → different hash; change output path → same
  hash. Assert `len(hash) == 64`, with deterministic results across repeated calls.
  Add the omitted-intent test: two plans differing only in that flag hash differently.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/test_render_identity.py tests/unit/sequencer/moving_heads/test_control_diagnostics.py -q`;
  confirm failures, implement canonical serialization/audit, rerun for PASS.
- [ ] Rerun `uv run pytest tests/golden/test_settings_golden.py tests/unit/sequencer/moving_heads/test_rendering_pipeline.py -q`;
  the accessors must not change rendered output.
- [ ] Integrator commits `feat(mh): report effective controls and fingerprint render inputs`.

### P0-T3 — Reusable adversarial synthetic cases

**Files:** Create `tests/support/__init__.py`, `tests/support/mh_true_up.py` and
`tests/unit/sequencer/moving_heads/test_true_up_cases.py`. Reuse, do not replace,
`tests/golden/harness.py`/existing accepted golden files. P0 adds no golden file.

**Interfaces:** Produces `SyntheticMHCase` and `synthetic_case(case_id)`; fixture data
is constructed in memory and has no disk-local configuration dependency.

- [ ] Write case-contract tests asserting the exact tempo arrays above, unique ordered
  fixture IDs, intentional channel edges and nonadjacent byte mappings. Unknown case ID
  raises `ValueError`; fixture construction never reads environment/local config.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/test_true_up_cases.py -q`,
  verify missing-case failures, implement fixtures, rerun for PASS.
- [ ] Exercise every `legacy_runnable` case through the real pipeline and assert it is
  deterministic across two runs. For `counts`, assert the recorded per-count outcome
  (rendered, or `UnsupportedRigShapeError`). Preserve existing snapshots;
  label physical-only fixtures as input definitions rather than completed behavior.
- [ ] Integrator commits `test(mh): add synthetic precision timing and state cases`.

### P0-T4 — Restrained reference arm without changing the old experiment

**Files:** Create `packages/twinklr/core/agents/sequencer/moving_heads/reference_policy.py`
and `tests/unit/agents/sequencer/moving_heads/test_reference_policy.py`. No existing
file is modified.

**Interfaces:** `build_reference_plan(sections: list[SelectorSection], *, seed: int,
admitted_template_ids: frozenset[str]) -> ReferenceSelectionResult`; consume existing
catalog and selector helpers. Define frozen `ReferenceSelectionDecision(section_id,
preferred_template_id: str|None, selected_template_id, reason)` and
`ReferenceSelectionResult(plan: ChoreographyPlan, baseline: SelectorResult,
decisions: tuple[ReferenceSelectionDecision,...], seed: int,
policy_revision: Literal['reference.v1'])` in `reference_policy.py`. Preserve the
baseline object and its frozen trace model unchanged; the new wrapper owns preference
and substitution provenance. Never label the newly selected plan as the old experiment:
its `overall_strategy` names `reference_legacy_v1` and the seed. `reason` is one of the
resolution steps above (`preferred`, `baseline`, `seeded_fallback`).

- [ ] Write tests for the preferred quiet/chorus/entry/ending choices and their
  precedence (a final chorus gets the ending template), identical seed/input
  reproducibility, a third chorus still receiving the chorus template, filtered-out
  preference fallback through steps 4 and 5, and no eligible template error.
  Assert the existing selector's output is unchanged for its original test inputs.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_reference_policy.py -q`;
  verify failure, implement the adapter, then rerun with
  `tests/unit/agents/sequencer/moving_heads/test_deterministic_selector.py` and
  `tests/unit/reporting/evaluation/test_three_arm_experiment.py` included; expect PASS.
- [ ] Integrator commits `feat(mh): add a separate restrained reference policy`.

## Exit, rollback and next phase

Complete T1–T4, independent review, and clean-tree `make validate`; disclose any skipped
checks. No new physical correctness/taste claim follows from P0.

The integrator then writes the dated evidence record at
`changes/2026_11_12_mh_true_up/evidence/<YYYY-MM-DD>-p0-baseline/README.md`, from
commands run in that session:

- the commit and the `make validate` result;
- for the five golden rigs and every `legacy_runnable` synthetic case, the
  `RenderingPipeline.diagnostics` tuple — this is the effective/ignored status of
  each selected control — and the `fingerprint()` value;
- the `counts` outcome per head count;
- the reference arm's decisions for one synthetic section list and seed.

Closeout for the phase also updates this change's handoff and its `changes/ACTIVE.md`
row. P0 changes no current truth beyond the three documents T1 corrects, so no
`context/` or `memories/` promotion is expected; record that as checked, not assumed.

Rollback removes the opt-in additions without changing old plan/config/golden behavior.
P1 consumes the policy, diagnostics, identity and cases; P5 can begin its evidence
adapter once the frame contract is ready.
