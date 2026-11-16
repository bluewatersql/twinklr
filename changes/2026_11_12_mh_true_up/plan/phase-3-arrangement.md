# P3 Musical Arrangement and Coordinated Intent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Make repeated phrases share identifiable motifs, deliberate variation and restrained attention while retaining exact deterministic rendering.

**Architecture:** Extend planner intent with an explicitly versioned V3 response, referencing the existing macro motif/focal contract. Resolve those categories into P2 components and P1 physical trajectories without replacing `FixtureSegment`, the template registry, BeatGrid or the shared emitter. Preserve the existing deterministic selector as an immutable comparison baseline; add an arrangement-aware wrapper.

**Tech Stack:** Python 3.13, Pydantic V2, existing prompt packs/provider adapters, pytest, uv.

**Spec:** `../report.md`, sections 6, 7 and Phase P3. This plan is proposed; implementation requires the owner to accept it.

## Global Constraints

- LLMs plan typed categorical intent; deterministic code owns timing, curves, fixture values and formats.
- `JobConfig.moving_heads.mode` remains `legacy_v1` by default; `physical_v2` is opt-in and requires explicit `JobConfig.schema_version='3.1'` (old/default jobs remain 3.0). Planner contract version is a separate setting and cache dimension.
- Preserve unversioned v1/v2 plan loading, private omitted-intent provenance and old replay output. No modification to the fixed existing three-arm experiment protocol or historical selector policy.
- Use existing `MacroPlan.motif_continuity`, `MotifThread`, `MotifEvolution` and `FocalRoleKind`; no second song-level motif registry.
- Synthetic fixtures and recorded provider responses prove implementation. Paid calls, owner media, xLights acceptance and taste judgments require separately recorded authorization.

## Review Focus

- Repeated display names versus unique section IDs: motif joins use IDs (T1/T3).
- A selected template becomes incompatible after a fixture-profile edit: capability constraints are never relaxed (T2).
- V3 segment flattening silently drops arrangement fields or legacy provenance: preserve both (T1/T3).
- No stems or low-confidence lyric events: no fabricated accents (T3).
- Combined-show timing masks expose a preposition movement or restart phase: coordinate visibility before final P1 feasibility pass (T5).

## Current seams and design

At baseline `9c55c2e`, `ChoreographyPlan` has no serialized schema-version field. Compatibility lives in `PlanSection._normalize_legacy_input`, `_capture_intent_provenance` and `flatten_plan_segment`; “v2” is an intent contract, not a wire discriminator. `MovingHeadStage` validates cached output directly with `ChoreographyPlan`, while `get_planner_spec` fixes the response model. `MovingHeadPlannerOrchestrator.get_cache_key` already hashes audio/lyrics, full macro plan, fixture context, admitted template IDs/descriptions, BeatGrid, provider settings and prompt content. Extend those seams deliberately.

`MacroPlan` already supplies motif threads and focal assignments. `coordinate_moving_head_plan` currently projects palette and role without changing templates; `coordinate_moving_head_segments` slices emitted segments after render. The physical path must apply shared visibility windows before P1's last feasibility check, because post-render masking can invalidate arrival/darkness assumptions. Keep legacy ordering unchanged.

### Proposed data contracts

Create `packages/twinklr/core/agents/sequencer/moving_heads/models_v3.py`:

- `MotionIntent`: required categorical `reach: INHERIT|COMPACT|MEDIUM|WIDE`, `rate: INHERIT|STILL|SLOW|PULSE|FAST`, `target_id: str|None`. Target IDs come from P2's admitted target catalog; no numeric coordinates.
- `ArrangementIntent`: `motif_id: str|None`, `relation: INTRODUCE|RESTATE|VARY|RESOLVE|NONE`, `source_section_id: str|None`, `role: FocalRoleKind`, `density: REST|SPARSE|BALANCED|BUSY`, `visibility: INHERIT|LIT|DARK|MOTION_GATED`, `variation: NONE|MIRROR|REVERSE|WIDEN|NARROW|RETARGET`. One controlled variation per section initially.
- `PlanSectionV3(PlanSection)`: required `motion: MotionIntent` and `arrangement: ArrangementIntent`. Existing intensity/color/shutter/gobo/MomentCue fields remain. Segment intent inherits section intent; no per-segment nested V3 expansion in this phase.
- `ChoreographyPlanV3`: required `schema_version: Literal['mh-plan.v3']`, `sections: list[PlanSectionV3]`, `overall_strategy: str`.
- `load_choreography_plan(payload: object) -> ChoreographyPlan | ChoreographyPlanV3`: return existing typed instances unchanged; unversioned mappings use the existing model; recognized V3 mappings use V3; reject unknown explicit versions. Do not invent previously supported versioned v1/v2 envelopes.

Add `JobConfig.moving_heads.planner_contract: Literal['legacy','v3']='legacy'` to the policy owner established in P0/P1. V3 generation initially requires `physical_v2`; invalid combinations fail before a provider request. Legacy plans can still use either renderer under existing opt-in rules. Plan schema, renderer mode, and template format are independently serialized identifiers.

Create `packages/twinklr/core/agents/sequencer/moving_heads/arrangement.py` with `ResolvedArrangement` holding the validated plan, per-section motif realization (template family, target, distribution, effective categories), signal provenance and decisions. `resolve_arrangement(plan:ChoreographyPlanV3,context:MovingHeadPlanningContext,eligible_templates:CapabilityProjection,*,policy:ArrangementPolicy) -> ResolvedArrangement` resolves IDs and constraints; it does not emit DMX. `packages/twinklr/core/sequencer/moving_heads/compile/arrangement.py` applies approved categories to P2 component requests before physical compilation. Its proposed `apply_arrangement_to_step(step:TemplateStep,intent:PlanSectionV3,*,presets:RigPresetLibrary,fixture_ids:tuple[str,...])->TemplateStep` preserves the source step and sets validated P2 component references on a copy; use `resolve_component_refs(step,fixture_ids,presets)` and P2 `resolve_distribution(topology,specs,selected_fixture_ids)` afterward. Qualitative reach/rate overrides require named variants explicitly declared by that physical template; missing variants exclude the candidate, rather than inventing degrees or scaling a legacy normalized curve. All new Pydantic response fields are required; null denotes unused references; `extra='forbid'`; use fixed enums plus admitted ID lists in context, not dynamic huge enums.

Deterministic policy: first occurrence introduces the macro motif; later occurrence relations follow the referenced thread's evolution, with repeated INTRODUCE normalized to RESTATE and traced. The V3 section cannot redefine the macro motif identity or membership. RESTATE keeps the source template family/path/distribution and changes only macro-required palette/role; VARY changes exactly the declared permitted dimension; RESOLVE uses the motif with slower rate/compact reach; unresolved or forward source references fail. Without a macro plan, each section is its own introduced motif; repeated names alone do not prove musical equivalence. Density controls nonessential accent opportunities: REST=0, SPARSE=1 per four bars, BALANCED=1 per two bars, BUSY=1 per bar. Visibility is independent: DARK emits closed/zero visibility, MOTION_GATED uses the P2 template's shared-phase envelope, INHERIT keeps the envelope, and LIT requests continuous illumination subject to P1 feasibility. Add `ArrangementPolicy.max_busy_fraction=0.25`; heuristic validation rejects plans whose BUSY sections exceed one quarter of total section duration, allowing the existing refinement loop to revise them. The deterministic wrapper selects highest-energy eligible sections up to that duration cap, tie-breaking by section ID. These are deterministic proposal caps, not musical truths. No automatic strobe. Rank eligible accents by confidence, strength, then stable cue ID; use a minimum confidence 0.7 only for sources exposing calibrated [0,1] confidence, otherwise omit and trace `confidence_unavailable`. Existing explicit user cues are validated, not silently discarded by density.

## File ownership

One P3 implementer owns new `packages/twinklr/core/agents/sequencer/moving_heads/models_v3.py`, `packages/twinklr/core/agents/sequencer/moving_heads/arrangement.py`, `packages/twinklr/core/agents/sequencer/moving_heads/capability_projection.py`, `packages/twinklr/core/agents/sequencer/moving_heads/selector_arrangement.py`, `packages/twinklr/core/sequencer/moving_heads/compile/arrangement.py` and tests below. Shared files `stage.py`, `specs.py`, `orchestrator.py`, `context.py`, planner/judge prompt packs, `pipeline.py`, `show_coordination.py`, `show_stages.py`, config policy and emission trace are integrator-owned changes applied sequentially. P2 owns target/motion/distribution models; P1 owns physical/frame/preposition contracts. No independent rewrites.

## Tasks

### P3-T1 — Versioned intent and legacy dispatch

**Files:** create `packages/twinklr/core/agents/sequencer/moving_heads/models_v3.py`; modify `models.py` flattening helper, `specs.py`, `stage.py`, rendering loaders and `pipeline/show_stages.py`; tests `tests/unit/agents/sequencer/moving_heads/test_models_v3.py`.

**Interfaces:** produce models/loader above; add keyword `planner_contract='legacy'` to `get_planner_spec`; preserve old positional parameters.

- [ ] Write `test_unversioned_plan_preserves_omitted_intent`, `test_v3_round_trip_and_flatten_preserve_arrangement`, `test_unknown_version_rejected`, and `test_v3_legacy_renderer_rejected_before_provider`: assert old section flag remains true, flattened motif ID survives, unknown version raises, provider mock has zero calls.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_models_v3.py -q`; require failures exposing missing V3 behavior.
- [ ] Implement dispatch and required-field V3 schema; route all MH stage, checkpoint, rerender and combined-show plan loads through it.
- [ ] Rerun that command plus `uv run pytest tests/unit/agents/sequencer/moving_heads/test_models.py tests/unit/agents/sequencer/moving_heads/test_specs.py -q`; require green.
- [ ] Integrator commits `feat: add versioned moving-head arrangement intent`; independent review checks compatibility dispatch and flattening.

### P3-T2 — Capability projection and cache isolation

Carried from Phase 2 kickoff, 2026-11-14 ([P2 carry-forwards](phase-2-composition.md#phase-1-carry-forwards)): under `physical_v2` a preset id the template does not declare applies no preset (`moving_heads/pipeline.py:295-321`); the projection exposes only declared family/variant pairs so the planner cannot name one. P2.4c's rig-aware admission already excludes templates the rig cannot render; the projection builds on its admitted list.

**Files:** create `packages/twinklr/core/agents/sequencer/moving_heads/capability_projection.py`; modify `context.py`, `stage.py`, `orchestrator.py`; test `tests/unit/agents/sequencer/moving_heads/test_capability_projection.py`.

**Interfaces:** `project_template_capabilities(documents:Sequence[TemplateDoc], capabilities:Mapping[str,FixtureCapabilities], *, presets:RigPresetLibrary, target_fixtures:Mapping[str,tuple[str,...]]) -> CapabilityProjection`. Keys of `target_fixtures` are named P2 position targets; each value explicitly identifies the fixtures intended to realize that target. Check each target exists in `presets` and supplies the required pose for every selected fixture. Reject unknown/empty fixture selections. Eligibility is evaluated per target/fixture set, not from an anonymous capabilities list.

Define frozen types in `packages/twinklr/core/agents/sequencer/moving_heads/capability_projection.py` (the projection `input_hash` covers its semantic planner inputs, not raw numeric calibration): `TargetTemplateAdmission(target_id:str,fixture_ids:tuple[str,...],template_ids:tuple[str,...])`; `TemplateExclusion(target_id:str,template_id:str,fixture_ids:tuple[str,...],reason:str)`; `CapabilityProjection(admissions:tuple[TargetTemplateAdmission,...],exclusions:tuple[TemplateExclusion,...],input_hash:str)`. Derive `eligible_template_ids` as the sorted union and `admitted_target_ids` from nonempty admissions. Prompt and validator preserve the target/template pairing; the union alone never authorizes an incompatible pair. Require every selected fixture to satisfy required capabilities; missing optional capability is admitted only with the template's explicit fallback. An empty required target candidate set raises before provider or render.

- [ ] Write `test_required_gobo_never_relaxed`, `test_missing_capability_is_unknown_not_supported`, `test_projection_change_invalidates_plan_cache`, `test_v3_schema_stays_within_provider_limits`, `test_named_target_requires_all_selected_fixture_poses`, `test_target_template_pair_cannot_borrow_other_target_admission`, `test_empty_target_candidates_fail_before_provider`; assert no incompatible ID reaches the prompt and `strict_json_schema(ChoreographyPlanV3)` passes existing ceilings 5,000 properties/10 depth/1,000 enum values.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_capability_projection.py -q`; observe new-path failures.
- [ ] Implement projection before request, including semantic capability/target admissions, policy and response-schema hashes in V3 cache key. Hash what the planner sees: supported categories, target IDs/fixture membership, eligible family/variant pairs and stable exclusion codes. Numeric calibration, DMX bytes and target coordinates belong to render identity; they invalidate planning only when admission or exposed intent changes. Keep legacy key path unchanged. Empty eligible set fails locally.
- [ ] Add `test_calibration_only_edit_retains_plan_key_but_changes_render_key` and `test_calibration_edit_that_removes_admission_changes_plan_key`; these distinguish a numerical retune from a capability change.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_capability_projection.py tests/unit/agents/sequencer/moving_heads/test_orchestrator.py -q`; require green.
- [ ] Integrator commits `feat: constrain moving-head planning to rig capabilities`; fresh review inspects exclusion/fallback semantics.

### P3-T3 — Motif resolution, restrained signals and compilation

Carried from Phase 2 kickoff, 2026-11-14 ([P2 carry-forwards](phase-2-composition.md#phase-1-carry-forwards)): (1) bind planner intensity on the physical path, which Phase 1 and Phase 2 leave unapplied with a trace warning (`moving_heads/pipeline.py:736-749`), through the reach/rate variants P2.4c families declare as presets; (2) feed render feasibility (section-length-dependent failures such as a `ONCE` cycle cut by a short section) into heuristic validation so the refinement loop revises the plan instead of failing at render; (3) produce the typed section overrides P2.1 dropped from its precedence, through `apply_arrangement_to_step`.

**Files:** create `packages/twinklr/core/agents/sequencer/moving_heads/arrangement.py`, `packages/twinklr/core/sequencer/moving_heads/compile/arrangement.py`; modify `packages/twinklr/core/config/models.py`, `heuristic_validator.py`, planner/judge prompts and pipeline integration; test `tests/unit/agents/sequencer/moving_heads/test_arrangement.py`.

**Interfaces:** resolver above consumes MacroPlan IDs, existing MomentCue references, BeatGrid and capability projection; returns decisions with no LLM-supplied numeric motion. Define frozen `ArrangementPolicy(max_busy_fraction:float=0.25, minimum_calibrated_confidence:float=0.7, sparse_period_bars:int=4, balanced_period_bars:int=2, busy_period_bars:int=1)` in integrator-owned `packages/twinklr/core/config/models.py` alongside `MHRenderPolicy`; fractions are [0,1], periods positive, REST permits zero optional accents. Expose it as `JobConfig.moving_heads.arrangement` with that default factory. Define in `packages/twinklr/core/agents/sequencer/moving_heads/arrangement.py`: `ArrangementDiagnostic(section_id:str,code:str,detail:str,cue_id:str|None)`; `SectionArrangementDecision(section_id:str,motif_id:str|None,source_section_id:str|None,template_id:str,target_id:str|None,motion:MotionIntent,arrangement:ArrangementIntent,accepted_cue_ids:tuple[str,...])`; `ResolvedArrangement(plan:ChoreographyPlanV3,sections:tuple[SectionArrangementDecision,...],diagnostics:tuple[ArrangementDiagnostic,...],policy:ArrangementPolicy)`. Section/segment selection is expanded before producing one decision per concrete rendered section identity.

- [ ] Write `test_restate_preserves_source_family`, `test_vary_changes_only_one_dimension`, `test_forward_motif_reference_rejected`, `test_sparse_density_caps_optional_accents`, `test_missing_stems_does_not_invent_events`, `test_dark_visibility_is_independent_of_motion`, `test_busy_duration_budget_rejected`; assert two same-named sections remain distinct IDs and no unsupported target is emitted.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_arrangement.py -q`; verify failures.
- [ ] Implement deterministic resolution/policy described above; add explicit tracing of requested versus effective categories and rejected optional events. Integrate before P1 physical compilation, after template selection.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_arrangement.py tests/unit/sequencer/moving_heads/test_rendering_pipeline.py tests/regression -q`; require green including unchanged legacy replay. Run the P2 preset/distribution tests named in that plan after its integrator confirms those interfaces.
- [ ] Integrator commits `feat: resolve recurring motifs and restrained accents`; reviewer inspects source-reference ordering and effects of segmentation.

### P3-T4 — Arrangement-aware deterministic reference

**Files:** create `packages/twinklr/core/agents/sequencer/moving_heads/selector_arrangement.py`; test `tests/unit/agents/sequencer/moving_heads/test_selector_arrangement.py`. Do not alter `DeterministicSelector`, `SelectorConfig`, fixed fallback/relaxation rules or the existing three-arm experiment.

**Interface:** `select_arrangement(context: MovingHeadPlanningContext, projection: CapabilityProjection, *, seed:int, policy:ArrangementPolicy) -> ArrangementSelectionResult`; define frozen `ArrangementSelectionTrace(section_id:str,target_id:str|None,baseline_template_id:str,selected_template_id:str,reason:str)` and `ArrangementSelectionResult(plan:ChoreographyPlanV3,baseline:SelectorResult,policy:ArrangementPolicy,traces:tuple[ArrangementSelectionTrace,...],resolved:ResolvedArrangement)` in `packages/twinklr/core/agents/sequencer/moving_heads/selector_arrangement.py`. The baseline object is copied without changing any legacy fields. Base selection runs unchanged; incompatible baseline choices are visibly replaced from the eligible subset using SHA256 of seed/section/template IDs; an empty eligible candidate set raises before provider invocation or rendering; capability constraints are never relaxed to make selection total.

- [ ] Write `test_same_inputs_same_plan_and_trace`, `test_existing_selector_result_unchanged`, `test_capability_filter_never_relaxes`, `test_reprise_reuses_admitted_family`; assert deterministic equality and logged baseline substitutions.
- [ ] Run `uv run pytest tests/unit/agents/sequencer/moving_heads/test_selector_arrangement.py -q`; require failures.
- [ ] Implement wrapper and shared resolver consumption; do not use hidden randomness or providers.
- [ ] Rerun plus existing `test_deterministic_selector.py`; require green.
- [ ] Integrator commits `feat: add arrangement-aware deterministic reference`; independent review checks frozen baseline preservation.

### P3-T5 — Shared MH/display motif and visibility realization

**Files:** modify `packages/twinklr/core/sequencer/show_coordination.py`, `pipeline/show_stages.py`, `pipeline/display_stages.py`; create `packages/twinklr/core/sequencer/motif_schedule.py`; tests `tests/unit/sequencer/test_motif_schedule.py`, extend `test_show_coordination.py`.

**Interface:** `build_motif_schedule(macro: MacroPlan, grid: BeatGrid, graph: ChoreographyGraph) -> tuple[MotifWindow,...]`; window stores motif/section ID, start/end milliseconds, role/target and existing coordination mode. Reuse `coordination_schedule` boundaries; both branches consume the same immutable result. Do not force identical visual effects onto unlike fixture types.

- [ ] Write `test_branches_share_motif_id_and_exact_boundaries`, `test_call_response_preserves_one_attention_owner`, `test_visibility_mask_precedes_final_preposition`, `test_legacy_coordination_unchanged`; assert delayed MH reveal never overlaps reserved movement and display retains the same source motif.
- [ ] Run `uv run pytest tests/unit/sequencer/test_motif_schedule.py tests/unit/sequencer/test_show_coordination.py -q`; verify new-path failures.
- [ ] Implement V3/physical ordering, pass motif provenance into existing segment metadata and display event source metadata, and add backward-compatible optional trace fields. Final P1 feasibility validation sees final visibility.
- [ ] Run `uv run pytest tests/unit/sequencer/test_motif_schedule.py tests/unit/sequencer/test_show_coordination.py tests/integration/test_combined_show_pipeline.py tests/golden/test_combined_show_golden.py -q`; require green. Integrator runs full clean-tree `make validate` after committing and records actual output.
- [ ] Integrator commits `feat: coordinate motif visibility across moving heads and pixels`; independent phase review. Owner taste exits remain pending until authorized comparisons establish recurrence, contrast and focal clarity.

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; see the
[shared rule](README.md#documentation-registry-and-test-surfaces). Recheck at
P3 kickoff.

- **Config inventory.** P3-T1 registers `job.moving_heads.planner_contract`; P3-T3
  registers `job.moving_heads.arrangement` and each of its fields, with collecting
  evidence tests.
- **Prompt and spec guards.** P3-T1 and P3-T3 change the planner response model and
  prompt packs. `tests/unit/agents/sequencer/moving_heads/test_prompts.py` and
  `test_specs.py` are existing guards on those; run them with each task and update
  them only where the legacy contract itself is unchanged and the new contract adds
  cases.
- **Documents.** `docs/user-guide.md`: job-config rows for the two new settings.
  At phase closeout, `context/architecture/multi-agent-planning.md` gains the V3
  planner contract once it is accepted behavior.

## Kickoff recheck and amendments — 2026-11-16

The plan above was written at `9c55c2e`, before Phases 0–2 existed. It was rechecked
read-only against `7356b376` by an agent separate from any implementer, on the owner's
go-ahead of 2026-11-16. Where this section and the text above disagree, this section
governs. Line numbers are at `7356b376`.

### What the recheck found

- **No family names a position preset** (catalog README), so there is no target
  catalog for the planner to choose from.
- **Variants are template presets only:** `narrow` (smaller extents) and `slow`
  (doubled period). `TemplatePreset` has no category field.
- **Admission is per template:** one failing preset excludes its family
  (`pipeline.py:615`, `:691`).
- **Nothing on the physical path renders accents,** and `MomentCue` has `emphasis` but
  no confidence (`lyrics/models.py:158-180`).
- **`twinklr show` refuses `physical_v2`** (`show_wiring.py:142`, `cli/show_cmd.py:78`),
  so T5 as written could never run.
- **Two plan-rebuild sites would drop V3 fields:** lyric binding
  (`moment_cues.py:64,107,173`) and the fingerprint payload (`identity.py:116`).
- **Render no longer fails on an unplayable cue** (default `on_unplayable="dark"`), so
  the "render feasibility into validation" carry becomes: reject a plan that would be
  darkened.
- **The provider-limit check already covers every registered spec**
  (`tests/unit/agents/test_structured_outputs.py`); the V3 spec only needs registering.
- **Any byte added under `prompts/planner/` re-keys every legacy plan**
  (`agents/prompts/fingerprint.py:30-53`), and `TemplateDescription`'s dump is part of
  the legacy cache key (`orchestrator.py:252-256`).

### Owner decisions, 2026-11-16

| # | Question | Decision |
|---|---|---|
| D1 | Targets, with no family that uses one | Cut `target_id`, `RETARGET` and per-target admission from Phase 3; carried to the phase that ships a family using position presets |
| D2 | T5 cannot run while `show` refuses `physical_v2` | Enable `physical_v2` in `twinklr show` inside Phase 3 (new task T5a), then T5 |
| D3 | Density and accents | One `density: REST\|SPARSE\|BALANCED\|BUSY`. REST makes the section dark; BUSY is capped at 25% of song duration by the validator; SPARSE and BALANCED are recorded only. Accent ranking, the confidence threshold, the period fields and `LIT`/`MOTION_GATED` are deferred |
| D12 | Deterministic reference | A new selector over the admitted physical families, same role/energy ladder, SHA-256 seeded tie-break, no legacy `SelectorResult` baseline. `deterministic_selector.py` stays untouched. This changes what Phase 5 compares against |

### Integrator decisions (reversible)

- **D4 Categories to variants.** `reach: INHERIT|COMPACT` (COMPACT → `narrow`);
  `rate: INHERIT|SLOW` (SLOW → `slow`); one preset per section, COMPACT with SLOW
  rejected by the validator. A fixed preset-id table documented in the catalog README;
  no new template field. The model emits `preset_id: null`; the resolver fills it.
  `STILL`, `PULSE`, `FAST` and `WIDE` are left out of the enums until a variant exists.
- **D5 Variation.** `NONE|NARROW|WIDEN|SLOWER|FASTER`, relative to the source
  section's effective preset. RESTATE keeps template and preset. RESOLVE uses SLOW or
  COMPACT where declared, otherwise restates and traces.
- **D6 Relation, source and role are derived** from the macro plan (first section in a
  thread introduces; later ones take `thread.evolution`). The model picks only
  `motif_id` (one of the section's `motif_ids`) and `variation`. A motif section is
  unsegmented.
- **D7 Intensity and colour** stay unapplied on the physical path; the diagnostic names
  them. The Phase 2 intensity carry is closed by substitution (reach and rate), which
  the owner is told at exit.
- **D8 Feasibility.** The gate publishes `min_section_bars` per template and preset;
  the validator rejects shorter sections. Other dark outcomes stay degrade-and-trace.
- **D9 Per-preset admission.** The base is admitted if it passes; only failing presets
  are excluded, and a non-admitted preset is treated as undeclared.
- **D10 Prompt packs.** New sibling packs `prompts/planner_v3/` and
  `prompts/judge_v3/`; the legacy packs are not edited.
- **D11 Cache key.** V3 additions are conditional on the V3 contract. A pinned legacy
  `get_cache_key` anchor, computed at `7356b376`, is added before T1 changes anything.
  `MOVING_HEAD_CACHE_VERSION` stays "2".
- New job fields (`planner_contract`, `arrangement`) change the plan, so they are not
  render-only; they are excluded from dumps at their defaults so legacy session ids
  hold.

### Corrected tasks

- **T1 Versioned intent.** Create `models_v3.py` with the fields of D3–D6. Modify
  `models.py` (flatten returns the parent's type), `moment_cues.py` (keeps the plan's
  type), `specs.py` (`planner_contract=`), `stage.py` (all three plan loads through
  `load_choreography_plan`), `orchestrator.py` (types), `rendering_stage.py`,
  `pipeline.py` (plan type), `identity.py`, `config/models.py` (`planner_contract`; V3
  requires `physical_v2`), new packs, `tests/config_effects_registry.py`,
  `test_structured_outputs.py`, `docs/user-guide.md`. `show_stages.py` moves to T5a.
  The round-trip test goes through the orchestrator's normalizer.
- **T2 Capability projection.** `project_capabilities(admission, documents) ->
  CapabilityProjection(templates, exclusions, input_hash)`, each entry holding the
  template id, its admitted reach/rate presets and `min_section_bars`. Built from the
  gate's result, with no second compile. Adds per-preset admission (D9) and
  `min_section_bars` (D8) to the gate. No `target_fixtures`. The plan's schema-limit
  test is cut; the calibration and empty-candidate tests stay as pins.
- **T3a Resolver (pure).** `resolve_arrangement(plan, context, projection, *, policy)`
  derives relation, source, role, the effective preset and a dark flag, and writes
  `preset_id`; it runs in the plan normalizer. `heuristic_validator.py` gains the busy
  budget, variant pairs, minimum section length and motif membership.
  `ArrangementPolicy` keeps `max_busy_fraction` only. `apply_arrangement_to_step` and
  `compile/arrangement.py` are dropped.
- **T3b Render integration.** `_render_physical` masks a REST section before
  `_enter_section` and records it as `arrangement_dark`; the unapplied-intent
  diagnostic is narrowed; an `arrangement` trace key appears only under V3.
- **T4 Deterministic reference** per D12, in `selector_arrangement.py`.
- **T5a Physical in `twinklr show`** (new, D2). Designed at its kickoff from the
  combined-show stages; legacy combined-show goldens must not change.
- **T5 Shared motif schedule and visibility,** on the physical combined show.

Order: **T1 → T2 → T3a → (T3b ∥ T4) → T5a → T5.** T1, T2 and T3a share `stage.py`,
`context.py`, `orchestrator.py`, the V3 packs, config, the registry and the docs.
`motif_schedule.py` and its test touch no shared file and may be built early.

### Invariants to hold

Legacy bytes and goldens; the 16 Phase 0 and two Phase 1 fingerprints for a
legacy-contract physical plan; legacy session ids; legacy planner cache keys. If D9
changes output for an input that rendered before, `PHYSICAL_RENDERER_REVISION` is
bumped and the owner told.

## Single-path direction — 2026-11-16 (supersedes parts of the amendments above)

The owner ruled the same day that the moving-head work must end with one path: no
backward-compatibility layers and no old implementation left beside the new one
([guardrail 9](../../shared/agent_guardrails.md)). This reverses the global constraints
at the top of this plan that keep `legacy_v1` as the default, preserve unversioned plan
loading and forbid touching the selector, and it withdraws these amendments: D10
(sibling prompt packs), D11 (conditional cache key and a legacy key anchor), the
`planner_contract` setting, and the "invariants to hold" for legacy bytes, session ids
and legacy planner cache keys.

Owner decisions:

| Question | Decision |
|---|---|
| Reach and timing | The cutover is Phase 3's first task. The old path is removed after the owner has viewed a real-audio physical render in xLights and accepted it |
| Deterministic selector and three-arm experiment | Ported to the physical families; one implementation. D12's separate arrangement selector folds into that port |
| The rule itself | Added to the shared guardrails |

Revised order:

1. **P3-C0 Owner viewing render.** A real-audio `twinklr run` on the physical path,
   rendered in xLights on an expendable show, for the owner to look at. Needs the
   owner to name the audio and rig. The look verdict is the owner's; `PENDING-OWNER`
   until given.
2. **P3-C1 Cutover (after acceptance).** Remove the old renderer and curve handlers,
   the 37 built-in templates, `moving_heads.mode`, the 3.0/3.1 schema switch, the
   moving-head goldens and regression fixtures that pin old output, and their documents
   and inventory records. Paths and grep evidence are recorded here before deletion
   ([AGENTS.md → Implementation](../../../AGENTS.md#implementation)). `twinklr show`
   renders moving heads physically as part of this (was T5a). The selector and the
   experiment are ported.
3. **T1–T5 as corrected above, with one planner contract:** the arrangement response
   model replaces the current one in place, the existing prompt packs are edited, and
   saved plans in the old shape are not loaded.

Corrected the same day by the [cutover inventory](cutover-inventory.md): the old
renderer reads the planner fields T1 replaces, so **T1 and T3a cannot land before the
cutover**, and the selector port would be a second selector until then. Before the
owner's acceptance only work that survives the cutover and adds no second path is
built: the gate additions D8 and D9, the pure `motif_schedule.py`, and moving the rig
builders out of the golden harness into `tests/support/`. Nothing is deleted from the
old renderer before acceptance. The inventory splits C1 into consumer ports (`show`,
`eval-report`, live `inject`/`regenerate`, selector and experiment), one atomic
flip-and-delete, model narrowing, renames and documents, and lists the owner decisions
the cutover needs.

## Execution record

### Gate-time cut — 2026-11-16 (commits `3113d062` and the test follow-up)

Done before any Phase 3 task, on owner direction. Implemented by one agent; reviewed
by a second (approve with fixes: one medium on test strength, five low), fixed by a
third, re-reviewed by a fourth (approve with two low test gaps, closed in the
follow-up).

- **What changed.** Preposition plans are remembered across one placement's section
  entries (`plan_prepositions(memo=...)`); heads of one step instance with the same
  profile and offsets share channel trajectories (`compile_physical_step(shared=...)`);
  phase, path and DMX-word arithmetic on the hot path is done in exact integers; plan
  grouping compares instead of hashing. `evaluate_physical_path` is now the single
  path implementation (phase passed as `n / d`); its `Fraction` wrapper is gone.
- **Measured (8 heads, 4-minute synthetic song, first reviewer, load average 3–5 on 18
  cores).** Zoom rig, 21 combinations: 57.5 s → 17.0 s variable tempo, 52.3 s → 15.7 s
  steady. Zoomless, 18 combinations: 11.9 s and 10.8 s after (author's before: 40.0 s
  and 36.7 s). With four gates running at once the author measured 19.4 s and 18.1 s on
  the zoom rig. The 20 s target is met; the margin under heavy load is thin.
- **Output unchanged.** Against a pristine `7356b376`: the author's 360-configuration
  matrix (13,338 comparisons) and gate fuzz (59,499), rerun after the fix round; the
  first reviewer's 192 mixed-profile configurations (4,944 comparisons); the
  re-reviewer's 96. Zero differences in all. The 16 Phase 0 and two Phase 1
  fingerprints match. No golden or regression file changed.
- **Test strength.** The first review found eight mutations of the memo and checks
  that no test caught, one of which (dropping `known_dark` from the memo's view)
  produces a wrong plan. A seeded memo-against-memo-free property test and targeted
  cases now kill them.
- **Equivalent mutants, recorded not tested.** Dropping `start`, `dimmer_dark_since`
  or `shutter_dark_since` from the memo's view, or `frame_ms` from its key, cannot
  change a plan: the first three follow from `source` and the profile, and a frame
  other than 20 ms is refused before the memo is used. They stay in the view and key
  so its definition remains "the whole state, past times collapsed" (integrator
  decision on the re-reviewer's recommendation).
- **Remaining cost.** Garbage collection is about 4 s of 17 s. Pausing collection
  around the gate would remove most of it but is a process-wide change; not done.
- **Validation.** `make validate` on `3113d062`: 6832 passed, 39 skipped, tree clean
  before and after.

### Owner decisions on the cutover inventory — 2026-11-16

| Inventory item | Decision |
|---|---|
| When `show`, `eval-report`, `inject` and `regenerate` move to the physical renderer | After the owner accepts the look; nothing new is built behind the mode switch |
| `regenerate --section` (F1) | Re-plan the chosen section, re-render the moving heads for the whole song and inject all of it |
| Old-renderer comparison for Phase 5 (F6) | Render the old-renderer version of the viewing song or songs before the cutover and keep the files as the reference |
| Rig without a physical profile (F8) | Refuse before planning with guidance naming the fixtures and what a profile needs; and give profile fields reasonable defaults wherever possible, so configuration is not a blocker ("avoid config hell") |

The last adds a cutover task, **C1.0 Profile defaults:** find which `FixtureCapabilities`
and `initial_states` fields can default safely (timings, default bytes, a dark initial
state) and which a rig must state (channel offsets, ranges, model name). Defaulted
timings are chosen, not measured; the trace says which values were defaulted. This
survives the cutover and adds no second path, so it may be built before acceptance.

### Viewing render stopped at the gate — 2026-11-16

The first real-audio gate on the owner's rig admitted one family of seven
([evidence](../evidence/2026-11-16-p3-real-audio-gate/README.md)). Owner decisions the
same day: fix robustness before any viewing (a sane beat grid when meter confidence is
low or tempo is doubled; families adapt to tempo and fixture speed instead of being
excluded), and use 150°/s, the layout's limit, for the rig's profile. A read-only
diagnosis and design precedes the implementation tasks, which are added here when it
reports.

### Per-preset admission (D9) — 2026-11-16

Implemented by one agent, reviewed by a second (approve with fixes), fixed by a third.

- **Behaviour.** A catalog family whose base passes the gate is admitted; only its
  failing presets are excluded, recorded on `TemplateAdmission`
  (`admitted_presets`, `preset_exclusions`) and in the trace
  (`admission_preset_exclusions`). A family whose base fails is excluded whole. A
  `--template-dir` template that fails anywhere still refuses the run. A section
  naming a preset that was not admitted renders the family's base with a warning, on
  the same path as an undeclared preset. `RenderingPipeline(admission=...)` replaces
  `admission_exclusions=`.
- **Effect.** In 6/8 the orbit, wings and zoom wave are now offered without `slow`;
  2/4 likewise. In 3/4 their bases fail, so nothing changes there yet.
- **Output.** 13,338 matrix comparisons and the reviewer's own rerun: zero differences
  for inputs that rendered before; Phase 0 and Phase 1 fingerprints hold.
  `PHYSICAL_RENDERER_REVISION` stays "1".
- **Known consequences, by the documented union rule.** Admitting more families widens
  the predecessor envelope, so another family's entry dip can grow; a template whose
  entry wheel state has no known settle time can lose its bound and be excluded (a
  user template: the run is refused). Not reachable with the shipped catalog. Where the
  offer grows (6/8, 2/4, 5/4), the planner cache key changes and one re-plan is paid.
  A saved plan naming a previously excluded family with its non-admitted preset now
  renders the base.
- **D8 withdrawn.** `min_section_bars` was implemented and then removed before commit
  (integrator decision): it was 1 for every shipped family, had no consumer, and its
  definition did not hold under `on_unplayable="dark"` or beside entry windows. If the
  T3a validator needs a feasibility bound, it defines what it needs then.

### Beat-grid fix — 2026-11-16

Meter, tempo octave and downbeat detection were replaced on owner direction; Need A
Favor now analyses as 78.3 BPM in 4/4. What changed, the before/after table for the
owner's songs, the review history, the limits and the consequences for other
pipelines are in the
[evidence record](../evidence/2026-11-16-p3-beat-grid-fix/README.md). Integrator
decisions inside it: 2/4 is no longer reported; the unused `tempo_changes` and
`is_stable` outputs are removed; key, chords and structure keep full-mix chroma.

### Family adaptation: variant ladder, whole-period cycles, continuity — 2026-11-16

One implementing agent; two review rounds by separate agents (each approve with
fixes, nothing critical; one high in round one, on gate time outside 4/4), and a last
round of low fixes verified after commit.

- **Variant ladder.** A catalog family is admitted through its first passing rung:
  base, then its declared presets in order. That rung is its *effective variant* on
  this rig and song (`TemplateAdmission.effective_preset`, trace
  `admission_effective_presets`). A section naming no preset, or one that was not
  admitted, renders the effective variant. A failed base is recorded like a failed
  preset. `--template-dir` templates stay strict: any failing rung refuses the run
  (integrator decision; the user guide promises it).
- **Whole-period cycles.** A repeating cycle whose steps all span it grows to the
  smallest whole number of bars that holds whole movement periods, pulse periods with
  duty below 1, and its overlays; more than 8 bars is refused. It applies in every
  meter and to user templates, including in 4/4 (integrator decision).
- **Continuity.** Gap-free repeats of a step continue the first repeat's musical phase
  exactly, instead of each restarting from its own frame-rounded start. This removed a
  real jump of up to one frame of motion at every cycle join, which had excluded
  variants on heads near their speed limit. Finite moves still restart by design.
- **Render identity.** The fingerprint includes each section's rendered preset where it
  differs from the named one.
- **Entry bounds** are resolved to a fixpoint, so a rung that fails late no longer
  widens other families' dips.
- **Scheduler exactness** (shared with the old renderer): cycle bounds, counts and
  step ends are computed exactly. Two pre-existing one-frame overlap defects on
  non-dyadic user cycles, found by widening the fuzz to meters 2–6, are fixed. Old
  renderer output is unchanged: 11,580 renders of the 37 built-in templates before and
  after the first scheduler change, zero byte differences (reviewer); re-verified
  after the last round (see the verification note below).
- **Revision.** `PHYSICAL_RENDERER_REVISION` is "2". The Phase 1 request fingerprints
  are now `60e0d5eb…11c7` and `b40905ec…cc86`; their frames and `.xsq` are
  byte-identical to before. Phase 0 fingerprints are unchanged.

Output changes, all on the physical path: non-4/4 renders (families newly admitted,
longer cycles); on any grid whose bars drift against the 20 ms frame, lit poses move
by at most about 2° and the edges of lit windows and masks by one frame, with no cue
dropped in the reviewer's 147 configurations; steady 4/4 grids are byte-identical.

Measured:

- **Owner rig, Need A Favor on the corrected grid (78.3 BPM, 4/4), offline:** six of
  seven families admitted, all on their base variant; entry dips 740–900 ms (two
  beats); gate 4.5 s. The zoom wave is out for want of a zoom axis.
- **Floor at 150°/s:** all six zoomless families from 50 to 180 BPM; all but the flick
  at 200 BPM. Slower heads lose families at fast tempos; thresholds are in the catalog
  README. At 90°/s: four families at 150 BPM, two at 200 BPM.
- **Gate time, 8 heads, 4 minutes (reviewer, unloaded):** 4/4 11.7–13.0 s; 6/8 15.9 s;
  3/4 26.7–30.9 s. At 16 heads and 6 minutes: 4/4 30.5 s, 3/4 71.8 s. The 20 s target
  holds only in 4/4, 2/4 and 6/8 at 8 heads. Accepted as a meter- and size-dependent
  cost (integrator decision): the audio analysis reports only 4/4, 3/4 or 6/8, the
  gate runs once per song before any paid call, and the remaining cuts are a process
  pool or a rewrite of per-frame data structures.
- **Garbage collection is paused for the gate call** and restored on every exit
  (integrator decision). Results are identical with and without; about a quarter
  faster; peak memory 557 MB against 539 MB at 16 heads and 6 minutes.

Known and recorded, not fixed:

- The entry-bound fixpoint can drop two user templates that are each bounded alone
  but unbounded only through each other's wheel states. Not reachable with the shipped
  catalog.
- The old `zigzag_alternating_pulse` template renders different bytes under different
  `PYTHONHASHSEED` values, on `main` as well. It belongs to the old renderer, which the
  cutover deletes.
- For the planner contract (T3a): `INHERIT` means the effective variant, and the
  admitted presets vary with rig speed and grid.

### Profile defaults (C1.0) — 2026-11-16

Written on `feat/mh-profile-defaults` (`fee944c4`, `7b1adf91`, `076c417d`) and applied
here as one commit; the user-guide conflict with the family adaptation was resolved by
the integrator. One implementing agent, one review (approve with fixes: one high), a
fix round, and a verification of the fixes by separate agents.

- **Defaults live in the existing profile models;** no second schema, and nothing
  reads the old fixture fields. A wrap validator fills only absent keys, then
  validates the result as an explicit profile, so a minimal profile dumps, fingerprints
  and renders exactly as its explicit equivalent. What was filled is listed in the
  trace (`fixtures[*].defaulted`).
- **Defaulted:** axis units; the dimmer's 0–1 range; default bytes (pan, tilt and
  dimmer at the word for 0, others 0, a wheel at its default state); a state's range;
  one `settle_ms` per wheel inherited by its states; the shutter's `closed`/`open`
  states by name; the visibility claims the profile already supports.
- **Never defaulted:** which offset does what, physical ranges, state bytes, and every
  timing. A guessed timing that is too fast would let the renderer reveal a head that
  is still moving. This corrects the task text above, which listed timings as
  candidates (integrator wording, not an owner requirement).
- **Initial states are not defaulted** (integrator decision on the reviewer's high
  finding; the owner was told). Assuming a head rests settled and dark at its default
  bytes before frame 0 claims what nothing establishes: the renderer's own park leaves
  heads at their last aim. A fixture without an entry is refused before planning, and
  the refusal prints the entries its profile's default bytes give, ready to paste,
  saying that pasting asserts the heads really rest there. The zero-configuration
  alternative, offered to the owner, is a planner change that treats the start pose as
  unknown and keeps each head dark for a worst-case arrival.
- **Measured** on a synthetic equivalent of the owner's 4-head, 16-channel rig: 587
  values written by hand before; 98 now, including the pasted initial states.
- **Output:** zero differences in the 360-configuration byte matrix against the branch
  point (author and reviewer); Phase 0 fingerprints identical.
- **For the cutover inventory:** `FixtureConfig.dmx_mapping` is still required until
  the cutover, so the guide's minimal example carries a placeholder mapping; a profile
  dumped and reloaded loses its `defaulted` record (the profile stays correct), which
  matters if `regenerate` or `inject` ever render from a dumped group.
- **Not done:** deriving travel speed from the xLights layout's `SlewLimit`. Feasible
  (the layout profiler already parses it) but it is a preview limit, not a
  measurement; left as an owner option.
