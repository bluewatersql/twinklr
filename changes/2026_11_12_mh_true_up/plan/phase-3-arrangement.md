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
