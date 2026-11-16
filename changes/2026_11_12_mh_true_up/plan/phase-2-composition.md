---
type: plan
status: active
area: engineering
created: 2026-11-12
updated: 2026-11-14
---

# P2 — Reusable spatial composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Make `physical_v2` usable on real audio, then make a small set of expressive physical moving-head families reusable across named aims, odd/missing-head rigs, and independent attribute phases.

**Architecture:** Extend existing `TemplateDoc`, preset resolution and the Phase 1 physical compile; all physical output remains `FixtureSegment` with P1's typed trajectory alternative. Resolve named rig references and stable topology before path generation, then use the P1 transaction/encoding passes for visibility, travel and bytes. Numeric transforms remain template-owned; planners select versioned family/preset IDs.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest, the JSON template loader; no new runtime dependency.

**Spec:** `changes/2026_11_12_mh_true_up/report.md` §§6.2, 6.4 and 8/P2; P1 interfaces. Baseline source: `main` at `d6096254`.

**Kickoff recheck, 2026-11-14.** Rechecked against `main` at `d6096254` (Phase 1 merged as
`52191b15`, plus the `DmxChannelCount` fix `85b7aa1e`). Every task was corrected in place
to the Phase 1 code as it exists; `file:line` citations are to that commit. Where a
design changed, the reason is given beside it. P2.0, the split of P2.4 into P2.4a–c, the
[Phase 1 carry-forward placements](#phase-1-carry-forwards) and the
[ownership table](#file-ownership-and-ordering) were added at this recheck, then revised
the same day after an independent review (integrator decisions on rig-aware admission,
config invariance, boundary feasibility, the repeat contract and the P2.4 split). Paths
follow the [plan conventions](README.md#execution-conventions); `rendering_stage.py` and
`stage.py` are under `packages/twinklr/core/agents/sequencer/moving_heads/`.

## Global Constraints

- Proposed design and execution checklist only; the P2 APIs named below do not exist yet. Existing Phase 1 interfaces are cited by file and line.
- Requires P1's physical-profile, musical-phase, preposition and frame contracts. P2 family output requires explicit `physical_v2`; legacy templates remain unchanged.
- Every new template field is physical-only: it joins `TemplateStep.has_physical_data` (`sequencer/models/template.py:431-441`) or, for a template-level field, is refused by `compile_template`, so legacy compiles refuse it (`moving_heads/compile/step_compiler.py:71-74`). A physical step accepts no legacy data (`_legacy_fields`, `moving_heads/compile/physical.py:409-417`), `timing.phase_offset` included; P2 adds physical counterparts instead of reading legacy fields.
- **Config invariance.** Every new field, template, fixture or job, is left out of dumps at its default with `exclude_if`, as Phase 1's are (`template.py:263-267`, `config/models.py:665-695`, `config/fixtures/groups.py:52-57`). A render-only job key is added to `RENDER_ONLY_CONFIG_KEYS` (`packages/twinklr/core/caching/identity.py:32-40`) in the task that adds it, so it never re-keys the planner's session id (`:138`). Otherwise every legacy session id and render fingerprint (`moving_heads/identity.py:76`, `:81`) would change, orphaning cached plans.
- **Invariance check** (a step in every task): legacy session ids (`tests/unit/caching/test_cache_identity.py`), the 16 Phase 0 fingerprints (the [P0 evidence script](../evidence/2026-11-13-p0-baseline/README.md)) and the two Phase 1 request fingerprints and frames, as P2.0 records them at `d6096254`, are unchanged.
- The 20 ms frame grid stays the only source of sample times (P1.2 decision): new kernels are evaluated at the frame times `compile_physical_template` passes (`moving_heads/compile/template_compiler.py:390-392`).
- Repeat schedules keep satisfying `validate_repeat_contract` unchanged (`moving_heads/templates/library.py:69-74`, exact cycle span; `:79-100`, no hole in a multi-step cycle). Dark time inside a section comes only from P2.4a's section entry window, P2.4b's visibility envelope and P2.3's `ONCE` remainder, never from holes in the cycle.
- Pydantic owns schemas; LLMs choose creative intent, deterministic code resolves geometry/timing/DMX. No complete world-space solver or optical catalog is required.
- New template IDs/versions do not silently shadow builtins; the physical catalog is admitted as P2.4c states.
- `PHYSICAL_RENDERER_REVISION` (`moving_heads/identity.py:33`) is bumped in any commit that changes output for an input Phase 1 already rendered; a task that only adds new fields leaves it.
- All data is synthetic until an owner-authorized fixture case is supplied. Hardware/changed-look acceptance remains PENDING-OWNER.
- Task checkpoints/commits belong to the authorized integrator. Finish implementation with independent review and clean-tree `make validate`, not a plan-time claim of passing tests.

## Review Focus

- Silence must never acquire an inferred tempo: P2.0 tests that nothing renders outside the covered span and that `BeatGrid.extended_to_duration()` is never called.
- No new field may change a legacy session id or fingerprint: every task runs the invariance check.
- Missing preset entries must not silently aim a head at center: P2.1 explicitly rejects or uses a named declared fallback.
- Subset regeneration and missing heads must preserve canonical phase ranks: P2.2 tests full-rig versus subset output.
- Rotation, asymmetric ranges and finite events must not trigger implicit normalization/loop closure: P2.3 tests transformed bounds and end state.
- A temporary wheel flick must return to the currently applicable base state, with dark settling both ways: P2.4b tests a base step change during the overlay.
- A rig that lacks what one family needs must still get the others: P2.4c tests a zoomless, preset-less rig.
- A section's entry window must always fit its repositioning: P2.4a's fuzz tests that the bound dominates the transaction pass, including predecessor cues moving at the rate limit.
- Unsupported optics must be rejected or follow a declared alternative, never treated as interchangeable channels: P2.5 tests capability/range boundaries.

## P2.0 — Silent song edges: hold dark outside the detected beats

Added 2026-11-14. The owner deferred silent song edges from Phase 1 to Phase 2 on
2026-11-14 ([approvals](../implementation-brief.md#approvals)); the integrator chose this
policy and flagged it to the owner, with no objection recorded.

Today `build_musical_phase_map` (`sequencer/timing/musical_phase.py:69-139`) requires
knots spanning exactly `[0, duration_ms]` (validator `:55-62`) and extends an edge only
when it is no longer than the adjacent observed interval (`_adjacent_knot`, `:142-170`);
otherwise it raises, and the gate refuses the job (`rendering_stage.py:365-373`). A
120 BPM sweep accepted 18 of 961 grids.

**Policy.** The phase map covers only the detected span plus the existing bounded
adjacent-interval estimate at each edge. Before the first covered instant and after the
last, every fixture is held dark. A cue that would start outside the covered span is
dropped with a trace record; one that runs past the covered end is cut there on the
frame grid, under the same rule as the end-of-song truncation. No tempo is inferred and
`BeatGrid.extended_to_duration()` is not used. Explicit boundary knots stay a possible
later extension and are out of scope.

**Files:** Modify `sequencer/timing/musical_phase.py`; `moving_heads/compile/template_compiler.py` (`compile_physical_template` only, `:266-409`); `moving_heads/pipeline.py` (`check_physical_templates` `:225-292`, `_render_physical` `:665-835`); `rendering_stage.py` (`RenderPreflightStage.execute`, `:327-381`). Tests: extend `tests/unit/timing/test_musical_phase.py`, `tests/integration/test_mh_physical_pipeline.py`, `tests/unit/agents/sequencer/moving_heads/test_render_preflight_stage.py`; create `tests/unit/sequencer/moving_heads/compile/test_physical_edges.py`; add an edge-grid builder to `tests/support/mh_physical.py`. Docs: `docs/user-guide.md` `moving_heads.mode` row (`:259`), `docs/pipeline_guide.md` job-config paragraph (`:801-812`). Not changed: `moving_heads/compile/preposition.py`, `moving_heads/identity.py`, `BeatGrid`.

**Interfaces:**

- `MusicalPhaseMap`: knots must lie within `[0, duration_ms]`, no longer span it exactly. Add read-only `covered_start_ms`/`covered_end_ms` (first and last knot time). No stored field is added, so a map Phase 1 accepted dumps, and therefore fingerprints (`identity.py:86`), byte-identically. Evaluating outside the covered span raises `MusicalPhaseError` naming the span (`_beat_index`, `:259-271`; `musical_time_at` already bounds by knots, `:230-236`).
- `build_musical_phase_map(grid, *, boundary_knots=())` keeps its signature. An edge whose outermost pair is observed gets one `adjacent_interval` knot: at the edge when the gap is at most that interval (Phase 1 behavior, unchanged), otherwise exactly one interval beyond the outermost beat. An edge bounded by an explicit knot stays there. Fewer than two observed beats, with no explicit knots, still raises.
- `compile_physical_template(..., *, phase_map, start_limit_ms: int = 0, end_limit_ms)`: a step instance whose quantized start is below `start_limit_ms`, or at or after `end_limit_ms`, is dropped per target fixture and listed in `dropped_steps`; each record gains `start_limit_ms`. An end past `end_limit_ms` is cut there (`:342-367`, the Phase 1 rule). A cue that starts before the covered start is dropped, not cut, because its phase origin would lie outside the map. With the one-interval head estimate this only affects a cue requested more than one beat before the first observed beat; bar 1 starts on a detected downbeat (`sequencer/models/context.py:188-201`).
- `_render_physical` and `check_physical_templates` take both limits from one helper: start is the covered start rounded up to the frame grid; end is the earlier of the song's last whole frame and the covered end rounded down. The render record gains `covered_span: {start_ms, end_ms}` and the longest inter-beat interval in the covered span (`longest_beat_interval_ms`, evidence for [decision 1](#decisions-on-the-kickoff-open-questions)). `phase_boundaries` (`pipeline.py:347-351`, `:807`) already lists the edge knots with provenance, and `dropped_cues` lists each dropped cue.
- Trace format: for an input Phase 1 already rendered, the trace gains `covered_span`, `longest_beat_interval_ms` and `start_limit_ms` on drop records; frames and fingerprint are what stays pinned.
- The gate refuses only what `build_musical_phase_map` still refuses, with a message that no longer claims the whole song must be covered, and logs the covered span.

**Holding dark needs no new code.** `plan_prepositions` already authors every frame of
every fixture: the span before the first cue is a transaction that commands every
declared darkness from frame 0 (`_dark_commands`, `preposition.py:764-791`) and moves
only once the fixture is dark (`:428-564`); after the last cue the fixture parks dark at
that cue's aim through `sequence_end_ms` (`:413-426`); a fixture with no cue parks dark at
its initial state (`:126-127`). The "declared pose" is therefore the run's declared
initial pose until the dark move to the first cue's aim, and the last cue's terminal aim
after it. No pose setting is added.

**Mid-song gap (decision).** Two consecutive detected beats far apart are one long beat:
phase interpolates linearly between them, exactly as in Phase 1, and nothing is held
dark there. Detecting a "gap" needs a threshold against some typical interval, which is
the tempo inference this phase forbids; the planner's bars come from the same grid, so
they stretch with it; travel rate and pulse widths are still checked by the compile. A
dark hold inside a gap would need an owner rule ([decision 1](#decisions-on-the-kickoff-open-questions)).

**Stays refused:** fewer than two observed beats without explicit knots; observed beats
outside `[0, duration_ms]`; explicit knots that overwrite observed beats or break
monotonicity; every other gate check. Note: a section's final bar ends at an
average-bar extrapolation (`BeatGrid.get_bar_start_ms`, `sequencer/timing/beat_grid.py:339-349`);
phase never uses it, and the covered-end cut keeps any frame from rendering past one
observed interval beyond the last beat. Changing that shared helper is out of scope.

- [ ] Before any change, record the two render fingerprints and the frames the [xLights request script](../evidence/2026-11-13-p1-xlights-request/README.md#script) produces at `d6096254`, and the 16 Phase 0 fingerprints; these anchor every task's invariance check.
- [ ] In `test_musical_phase.py`, write: a 3 s lead-in (beats every 500 ms from 3000 ms) is covered from 2500 ms (`adjacent_interval`) and phase at 2000 ms raises naming the span; a long tail likewise; edges within one interval give the Phase 1 knots exactly (equal `model_dump`); a mid-song gap (500 ms beats to 2000 ms, then 5000, 5500, ...) gives phase exactly 4.5 at 3500 ms and adds no knot; zero or one observed beat still raises. Change deliberately: `test_unsupported_tail_is_rejected_without_explicit_knots` (`:88`) and `test_unsupported_head_is_rejected_without_explicit_knots` (`:101`) become covered-span tests; the `(2500, "tail")` case of `test_explicit_knots_cannot_overwrite_beats_or_break_monotonicity` (`:121-136`) and the first case of `test_phase_map_requires_a_covered_monotonic_domain` (`:155-172`) now build; their other cases stay.
- [ ] Add the sweep: 961 grids at 120 BPM, 31 lead-ins (0–3 s in 100 ms steps) by 31 tails (0–6 s in 200 ms steps). This reconstructs the P1.6 sweep's ranges and count; its exact steps were not recorded. Every grid builds, and its covered start and end are the song edge or one interval beyond the outermost beat, as computed from the grid.
- [ ] In `test_physical_edges.py`, write `test_cue_before_covered_start_is_dropped_with_a_record`, `test_cue_past_covered_end_is_cut_on_the_frame_grid`, `test_cue_starting_at_covered_end_is_dropped`, and `test_phase1_grid_compiles_identical_segments`.
- [ ] In the integration test, render a 3 s lead-in and 4 s tail: every frame before the covered start and from the covered end on commands darkness through the profile's declared mechanism; pan/tilt hold the initial pose until the dark move and the last cue's aim after it; the trace carries `covered_span` and the dropped cues; `assert_honest_transactions` passes; `BeatGrid.extended_to_duration`, patched to raise, is never called.
- [ ] Change `test_physical_job_whose_song_has_an_uncovered_tail_is_refused` (`test_render_preflight_stage.py:112`) deliberately to acceptance with the covered span logged; add a one-beat grid that is still refused.
- [ ] Run `uv run pytest tests/unit/timing/test_musical_phase.py tests/unit/sequencer/moving_heads/compile/test_physical_edges.py tests/integration/test_mh_physical_pipeline.py tests/unit/agents/sequencer/moving_heads/test_render_preflight_stage.py -q`; expect failures.
- [ ] Implement; update the two documents.
- [ ] Rerun, plus `uv run pytest tests/unit/sequencer/moving_heads/compile/test_physical.py tests/unit/sequencer/moving_heads/compile/test_preposition.py -q`; run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): hold physical output dark outside the detected beats`; do not combine unresolved task failures with the next task.

## P2.1 — Named component references and deterministic precedence

**Files:** Create `config/fixtures/presets.py` (`RigPresetLibrary`, `PositionPreset`, `AttributePreset`) and `moving_heads/compile/presets.py` (`resolve_component_refs`; plural, beside the step-patch module `compile/preset.py`). Modify `config/fixtures/groups.py` (`FixtureGroup.presets`, excluded from dumps when empty; class at `:126`), `sequencer/models/template.py` (`TemplateStep.component_refs`; `PhysicalMovementSpec.start_pan_deg`/`start_tilt_deg` become optional, `:191-192`; `has_physical_data`), `sequencer/models/context.py` (`TemplateCompileContext.presets`, class at `:129`; `StepCompileContext.resolved_pose: PoseDegrees | None` and `resolved_attributes: ResolvedStepComponents | None`, class at `:79-126`), `moving_heads/compile/template_compiler.py` (`compile_physical_template` resolves per target fixture and fills those two fields on each `StepCompileContext`, `:368-401`), `moving_heads/compile/physical.py` (`_movement_value` `:455-473` reads `resolved_pose`; the held discrete states read `resolved_attributes`, `:198-207`; `_require_physical_step` and `is_physical_template` `:367-406` accept a pose supplied by a reference), `moving_heads/pipeline.py` (pass `fixture_group.presets` at both `TemplateCompileContext` sites, `:255-268` and `:715-730`). `compile/preset.py` is not modified: presets already patch `movement.physical` through `StepPatch.movement`'s deep merge (`compile/preset.py:35-48`). Tests: create `tests/unit/sequencer/moving_heads/compile/test_component_presets.py`; a preset rig builder in `tests/support/mh_physical.py`; rerun `tests/unit/sequencer/moving_heads/templates/test_data_loader.py`, `templates/test_registry.py` and `compile/test_physical.py`.

**Interfaces:** `RigPresetLibrary(positions: dict[str,PositionPreset], attributes: dict[str,AttributePreset])` on `FixtureGroup.presets`, empty by default. `PositionPreset` maps fixture IDs to `PoseDegrees(pan_deg,tilt_deg)` without modulo wrapping. `AttributePreset` maps fixture IDs to named shutter/color/gobo states and a normalized dimmer level, validated against each fixture's `physical_profile`. `ComponentRefs(position_id: str | None, attribute_preset_ids: tuple[str,...])` is an optional `TemplateStep.component_refs`; `resolve_component_refs(step: TemplateStep, fixture_ids: tuple[str,...], presets: RigPresetLibrary) -> dict[str,ResolvedStepComponents]` returns explicit per-fixture physical settings and provenance. Unknown IDs or missing fixtures fail unless the preset declares a specific fallback preset ID; reject fallback cycles. This is rig data, not a global target database.

Precedence (corrected): Phase 1 applies a declared preset to the template before
compiling (`template_compiler.py:305-306`), so preset-patched physical values already
are values present on the step. Resolution is per axis and per channel. A referenced
position supplies `start_pan_deg`/`start_tilt_deg` only where the patched step leaves
the axis unset; an axis set on the step replaces the reference for that axis alone and
is recorded in provenance; an axis set by neither fails. Referenced attributes supply
per-fixture states; step-level `physical_shutter_state`/`physical_color`/`physical_gobo`
(`template.py:420-429`) replace them for that channel only. Conflicting attribute preset
IDs at the same level fail rather than last-write wins. Provenance (`component_provenance`
in segment metadata) records "step" for an axis set on the patched step; it cannot tell
the template's own value from a preset patch, because the patch is merged before
compile. The plan's fourth level, typed section overrides, is dropped: the physical
path applies no section intent (`pipeline.py:736-749`), and P3-T3's
`apply_arrangement_to_step` is its future producer.

Attribute presets also close the Phase 1 carry "portable state names across profiles"
(P1.2–P1.4 decisions): a template names a rig attribute preset, and the rig maps it to
each profile's own state names. A non-empty preset library is part of `FixtureGroup`'s
dump, so an edit changes the render fingerprint (`identity.py:76`), while the planner
cache key, which hashes only fixture count and groups (`orchestrator.py:244-247`), is
unchanged.

- [ ] Write `test_missing_fixture_preset_is_not_centered`, `test_step_axis_overrides_reference_only_for_that_axis`, `test_fallback_cycle_rejected`, `test_preset_change_only_changes_dependent_segments` (compare affected segments and untouched segment fingerprints), `test_attribute_preset_maps_one_name_to_each_profiles_state`, `test_component_refs_rejected_by_legacy_compile` and `test_empty_preset_library_is_left_out_of_the_group_dump`.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_component_presets.py -q`; expect missing-interface failures.
- [ ] Implement references and precedence; do not copy old preset values into generated documents: keep explicit versioned references and content hashes.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/templates/test_data_loader.py tests/unit/sequencer/moving_heads/templates/test_registry.py tests/unit/sequencer/moving_heads/compile/test_physical.py -q`; run the invariance check; record a review checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): resolve named position and attribute components`; do not combine unresolved task failures with the next task.

## P2.2 — Stable topology and separate phase domains

**Files:** Create `sequencer/models/moving_heads/topology.py`. Modify `config/fixtures/groups.py` (`FixtureGroup.topology: FixtureTopology | None`, excluded from dumps when absent), `sequencer/models/template.py` (physical-only `TemplateStep.physical_distribution: tuple[PhaseDistribution, ...]`; `has_physical_data`), `sequencer/models/context.py` (`TemplateCompileContext.topology`; `StepCompileContext.phase_offset_by_channel` and `pan_sign`), `moving_heads/compile/template_compiler.py` (`compile_physical_template`), `moving_heads/compile/physical.py` (`_movement_value`, `_pulse_high`, `_check_pulse_widths`, `_shutter_states`, `:455-540`), `moving_heads/pipeline.py` (pass the topology at both context sites). Not modified, although the plan listed them: `moving_heads/compile/phase_offset.py` and `moving_heads/fixture_builder.py`. Legacy `timing.phase_offset` stays legacy, a physical step refuses it (`compile/physical.py:416`), and `compile_physical_template` applies no legacy offsets (`template_compiler.py:282-283`). Tests: create `tests/unit/sequencer/moving_heads/compile/test_topology_phase.py`; multi-head topology rigs in `tests/support/mh_physical.py`.

**Interfaces:** `FixtureTopology(members: tuple[TopologyMember,...])`, with `TopologyMember(fixture_id,row,column,ordinal)` and unique identity/ordinal, describes a canonical full rig. `PhaseDistribution(domains: tuple[ChannelName,...], block_size:int=1, group_count:int|None=None, wings:Literal[1,2]=1, spread_cycles:float=0, direction:Literal["forward","reverse"]="forward")`. Domains are limited to PAN, TILT, DIMMER and SHUTTER: color and gobo are held states with no phase (`compile/physical.py:198-207`). `resolve_distribution(topology: FixtureTopology, specs: Sequence[PhaseDistribution], selected_fixture_ids: tuple[str,...]) -> dict[str,ResolvedFixturePhase]` returns `phase_by_channel` and mirror direction. Reject overlapping domain ownership between distribution specs.

Direction of the offset (pinned): a fixture's phase in a domain is the step phase minus
its offset, so slot 0 leads and higher slots lag. Phase is still measured from the
quantized step start, so `phase_origin_ms` (`compile/physical.py:157`) is unchanged; a
pulse's own `phase_cycles` (`template.py:227`) still adds. The finite `linear` kernel
clamps to `[0, 1]` (today `min(phase, 1)`, `:470-471`), so a lagging head holds at its
start until its phase reaches zero; Phase 1 phase is never negative, so P1 output is
unchanged. The mirror sign multiplies the pan displacement (`pan_extent_deg` term).

Define rank from canonical `(row,column,ordinal,fixture_id)` ordering, before filtering disabled/missing/selected heads; the selected heads are those `_resolve_target_fixtures` returns (`template_compiler.py:412-469`), and rank never goes through the role list in `_order_fixtures_for_chase` (`:472-546`). Wings fold the whole ordered rig, including multi-row rigs; per-row independent wings are deferred. For two mirrored wings, folded rank is `min(i,n-1-i)` and pan-displacement sign is left −1, right +1; the odd center has sign 0 and phase rank at the fold. Blocks use `b=floor(folded_rank/block_size)` (unfolded rank for one wing). Let `B=max(b)+1` over the full rig, `S=min(B,group_count)` if a group count is specified, otherwise `S=B`; slot is `b % group_count` or `b` respectively. `block_size`/`group_count` are positive integers. Phase offset is `spread_cycles * slot/(S-1)` for `S>1`, otherwise 0. Reverse uses `S-1-slot` before normalization. Thus spread specifies the first-to-last span, including endpoints; a full-cycle span intentionally repeats endpoint phase. Empty canonical slots persist, so removing a head leaves a deliberate hole instead of rephasing neighbors. Legacy phase continues unchanged.

A rig without `topology` gets a derived one-row topology when every fixture declares `FixturePosition.position_index`, in the order `rig_profile_from_fixture_group` already uses (`sequencer/models/moving_heads/rig.py:220-228`); otherwise a step with a distribution fails at compile and P2.4c leaves that template out of the offer ([decision 2](#decisions-on-the-kickoff-open-questions)). Test both cases.

Exact example: five ordered heads, wings 2, block_size 2, group_count 2, spread 0.5 produces folded ranks `[0,1,2,1,0]`, slots `[0,0,1,0,0]`, offsets `[0,0,0.5,0,0]`, signs `[-1,-1,0,1,1]`; reverse offsets are `[0.5,0.5,0,0.5,0.5]`. Removing the center preserves every remaining value.

- [ ] Write tests for 1/2/3/4/6 heads, an odd center, a missing middle head, two rows, blocks and interleaved phase groups. For subset IDs assert `subset[id] == full[id]`. Give dimmer a half-cycle spread with pan/tilt zero and assert only dimmer shifts.
- [ ] Assert the exact five-head folded/block/group offset and sign arrays above, including reverse and removed-center output; this pins the denominator and endpoint behavior.
- [ ] Write `test_lagging_linear_head_holds_at_start_until_its_phase_begins`: two heads, offset 0 and 0.25, finite `linear`; the second starts a quarter period later and both end at the terminal pose.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_topology_phase.py -q`; expect failures.
- [ ] Implement deterministic ranks/domain selection; preserve canonical order in trace and use it during P4 regeneration.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/compile/test_phase_offset.py tests/unit/sequencer/moving_heads/compile/test_physical.py -q`; run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): distribute independent phases over stable rig topology`; do not combine unresolved task failures with the next task.

## P2.3 — Relative transforms and finite motion

**Files:** Modify `sequencer/models/template.py` (`PhysicalMovementSpec`, `:177-217`: shapes and `transform`; `RepeatMode.ONCE`, `:37-39`), `moving_heads/compile/physical.py` (`evaluate_physical_path` replaces the kernel body of `_movement_value`, `:455-473`), `moving_heads/compile/scheduler.py` (a `ONCE` branch in `schedule_repeats`, `:61-192`), `moving_heads/compile/template_compiler.py` (`compile_template` refuses `ONCE`, `:91-263`). Not created or modified, although the plan listed them: `handlers/movement/physical.py` and `handlers/defaults.py`, because Phase 1 evaluates physical kernels in `compile/physical.py`, not through the legacy handler registry; `templates/library.py`, because a `ONCE` template's single cycle satisfies the contract as it stands (exact span, `:69-74`; no hole, `:79-100`) and its dark return happens after the cycle, in the unscheduled remainder. Test: create `tests/unit/sequencer/moving_heads/compile/test_physical_paths.py` (beside the compile it tests, not under `handlers/`); path fixtures in `tests/support/mh_physical.py`.

**Interfaces:** Add template-owned `PathTransform(rotation_deg, reverse, phase_cycles)` to `PhysicalMovementSpec`. Keep `pan_extent_deg`/`tilt_extent_deg` (`template.py:193-194`) as their sole owner. Extend its `shape` vocabulary (`:189`) with `circle`, `lissajous`, and `sweep`; `circle`/`lissajous` are periodic, and `sweep` declares periodic or finite return behavior. Lissajous axis frequency ratios are positive template-owned integers, default 1:2. `evaluate_physical_path(spec: PhysicalMovementSpec, *, pose: PoseDegrees, phase: float) -> PoseDegrees` returns unwrapped degrees: compute the centered displacement, rotate XY, scale each axis by its degree extent, then add the resolved base aim (P2.1's per-axis pose). For these kernels an extent is maximum signed displacement, not full width. Correction: P1's `sine_pan`/`sine_tilt` already add a signed displacement `extent*sin(2πφ)` (`compile/physical.py:473`) and `linear` is start-anchored (`:470-471`); the new kernels compute sin/cos directly, so no `[0,1]` curve-library kernel and no `2x−1` conversion is involved, and `linear` keeps its P1 meaning so P1 output is unchanged. Never add a resolved pose and start angles as separate offsets; do not force the endpoint closed. Bounds and rate stay with `check_physical_value` and `_check_travel_rate` (`:553-580`).

`RepeatMode.ONCE` schedules exactly one cycle at nominal musical rate and never compresses into a short section; every step of a `ONCE` template must be finite. What follows the cycle is decided by the existing `remainder_policy`, with semantics the `ONCE` branch defines for itself; every other mode keeps today's scheduling. `HOLD_LAST_POSE`: the branch extends the end of the instances that close the cycle to the section end, so each stays one cue with one phase origin. It does not call `_hold_last_pose` (`scheduler.py:163-171`, `:303-334`), which appends a new instance at the remainder start; the physical compile would give that instance its own phase origin (`compile/physical.py:157`, `template_compiler.py:340-401`), so a finite kernel would restart at its start pose with no gap, an error at the cue boundary (`preposition.py:599-606`) or a snap. Past its finite span a kernel evaluates to its terminal value: `linear` is `start + extent * clamp(phase, 0, 1)` (P2.2's clamp of `:470-471`), and a finite `sweep` clamps the same way, so the head holds the terminal pose, lit, for the rest of the section. `TRUNCATE`: the branch schedules nothing after the cycle, so `plan_prepositions` darkens and parks the head in the remainder. This is new, `ONCE`-only semantics; in every other mode `TRUNCATE` renders the start of the next cycle and clips it at the section end (`:172-185`), unchanged. `FADE_OUT` stays refused (`template_compiler.py:308-320`). Design change: the plan's `PhysicalEvent(repetitions, terminal)` is dropped. `terminal` would duplicate `remainder_policy`, and `repetitions > 1` of a non-closing finite path needs an instantaneous return between repetitions, which the rate check refuses (`compile/physical.py:553-580`); a repeated gesture is a `JOINER` template whose dark return comes from a P2.4b envelope. No dark-return trajectory is authored inside a cue (one dark-motion algorithm, P1.5).

Truncation, reconciled with Phase 1: cuts at a song edge (end of song, P2.0's covered end) keep P1's cut-without-error rule, because the template cannot control them; a section end that cuts a `ONCE` cycle short fails; no template field permits a dark cutoff, since the dropped `PhysicalEvent` was its only home and no family needs one. The gate cannot see planner section lengths, so this stays a plan-dependent failure ([carry 7](#phase-1-carry-forwards)). Periodic relative orbits continue using exact unwrapped phase.

- [ ] Write `test_rotated_orbit_uses_named_aim`, `test_reverse_changes_travel_not_visibility_phase`, `test_finite_snap_does_not_wrap`, `test_once_hold_extends_one_cue_and_holds_the_terminal_pose_lit` (one cue per fixture to the section end, one phase origin, terminal pose on every remainder frame), `test_once_truncate_leaves_the_remainder_dark`, `test_short_section_rejects_a_once_cycle_it_cuts`, `test_once_rejected_by_legacy_compile`, and `test_once_template_passes_validate_repeat_contract`; use asymmetric pan/tilt extents and compare a 90° normalized-path rotation before scaling.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_physical_paths.py -q`; require failure.
- [ ] Implement the path evaluator and the `ONCE` scheduling branch; legacy kernels, repeat behavior and `validate_repeat_contract` stay unchanged.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/compile/test_physical.py tests/unit/sequencer/moving_heads/compile/test_scheduler.py tests/unit/sequencer/moving_heads/templates/test_repeat_contract_validation.py -q`; run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add relative physical paths and finite events`; do not combine unresolved task failures with the next task.

## P2.4a — Reposition infrastructure: fallbacks, entry window, gate checks

Added 2026-11-14 (split from P2.4 on review). Testable with the Phase 1 test template.

**Files:** Modify `sequencer/models/template.py` (`TemplateStep.physical_reposition_fallback`), `moving_heads/compile/template_compiler.py` (fallback metadata; `apply_entry_window`), `moving_heads/compile/preposition.py` (time-zero reason; `worst_case_entry_ms`), `config/models.py` (`MHRenderPolicy.reposition_fallback`), `packages/twinklr/core/caching/identity.py` (`RENDER_ONLY_CONFIG_KEYS`), `moving_heads/pipeline.py` (pass `failure_mode`, `:760-767`; size and apply each section's entry window, with the skip, in `_render_physical`; `check_physical_templates` gains `initial_states`, `failure_mode` and an intra-template reposition check, and its cost is measured and reduced), `rendering_stage.py` (pass both to the gate, `:374`). Tests: create `tests/unit/sequencer/moving_heads/compile/test_entry_window.py`; extend `compile/test_preposition.py`, `compile/test_preposition_fuzz.py`, `test_render_preflight_stage.py`, `tests/unit/caching/test_cache_identity.py`, `tests/support/mh_physical.py`. Docs: `docs/user-guide.md` mode row (gate description) and a `moving_heads.reposition_fallback` row.

**Interfaces:**

- Fallbacks (carry 4): `TemplateStep.physical_reposition_fallback: Literal["preserve_aim","drop_accent"] | None` makes the compile set `metadata[FALLBACK_METADATA_KEY]` (`preposition.py:70`); `MHRenderPolicy.reposition_fallback: Literal["error","preserve_aim","drop_accent"] = "error"`, excluded from dumps at `"error"` and listed in `RENDER_ONLY_CONFIG_KEYS`, is passed as `failure_mode` to the render and to the gate. Both are needed because P1 requires the effect and the pass to opt in (`preposition.py:609-614`).
- Section entry window (replaces the first draft's per-cycle "entry span"; integrator decision). Why it is needed: back-to-back cues may differ only by one frame of travel and no wheel change (`_continuation`, `preposition.py:434-435`, `:583-606`), so without a gap any section boundary between differently aimed templates fails at render. The window is derived, not authored: `_render_physical` compiles each section uncut, in plan order, then sizes its window from `worst_case_entry_ms` (below), taking the maximum over the section's fixtures.
  - Entry side (single pass): the bound runs over the pose range of every cue the section compiled on that fixture, and every wheel state those cues select, not over the uncut first cue's entry pose. Cutting a moving first cue moves its entry to the pose at the window end, which can lie farther from the predecessor; any cut lands on a pose of some cue in the section, so the section's range always contains it, whatever window results. Rejected alternative: growing the window a beat at a time until the bound at the cut pose fits is tighter but iterates per section, and every step's cut pose must be recomputed.
  - Predecessor side: per fixture, from what was actually kept, not from the previous section. It is the terminal pose of the last cue kept on that fixture, after earlier windows, drops and skips, or the initial pose when none was kept. That covers a previous section with no cue on the fixture, with every cue dropped (P2.0 edge or inside its window), or shorter than its window and rendered dark: the head is still where the last kept cue left it. A substitution under a fallback is decided later, by `plan_prepositions` (`preposition.py:352-387`), so it is not known at sizing time; when the policy's `failure_mode` is not `error`, the envelope widens to the union of the pose ranges of every kept cue back to and including the last one that cannot be substituted (it does not opt into that mode, `:609-614`), or to the initial pose.
  - That time is rounded up to whole beats from the section start on the phase map (`musical_time_at`) at that section's tempo, and the window's end is rounded up to the frame grid. `apply_entry_window` cuts the section's first cues to begin at the window end with `slice_physical_segment` (`compile/physical.py:331-364`), so the phase origin is kept, and drops a cue wholly inside the window with a `dropped_cues` record. A section shorter than its window renders dark and is recorded, not refused. The window applies once per section, not per cycle, so continuous families do not blink dark every cycle, and it needs no hole in the repeat cycle. Every input is already render identity, so the window adds none.
- Dip skip (default, integrator decision): per fixture, when the last cue kept on that fixture ends exactly at the section start and cannot be substituted (see above), the section's first state needs no wheel change, and its pose is at most one frame of travel from the last kept cue's terminal pose at `travel_speed_per_s`, `_render_physical` keeps the uncut first cue instead of the cut one. `plan_prepositions` still validates the continuation (`:566-607`), so there is no new failure mode and no second dark-motion algorithm. This removes the dip only when the predecessor ends where the successor begins: for example the same family across a boundary when the section spans whole periods, since phase restarts at each section start. Every other entry still dips dark; whether those dips look acceptable is a look judgment, `PENDING-OWNER`. The trace records, per section and fixture, the window in ms and whether it was `cut` or `skipped`.
- `worst_case_entry_ms(profile, *, entry_pose, entry_wheels, pose_envelope, frame_ms) -> int | None`: the most time a transaction into a cue at `entry_pose`/`entry_wheels` can need, from any predecessor whose pose lies within `pose_envelope` (per-axis min/max) and whose wheels may hold any state, computed from the same terms the transaction uses (`preposition.py:455-517`): close latency plus extinguishing shutter settle, the larger of the slowest wheel settle and one frame, travel from the envelope extreme farthest from the entry pose at `travel_speed_per_s` plus latency, settle, and one more latency plus settle for predecessor motion still under way, each rounded up to whole frames. `None` when any needed term is unknown, which is never feasible; P2.4c excludes such a template.
- Gate: (a) after each combination's dry compile, run `plan_prepositions` with the run's `initial_states` and `failure_mode`, catching repositioning inside a template; (b) measure where the 0.8 s per combination goes on the 8-head, 4-minute synthetic song, then reduce it; the candidate to measure first is compiling over the song's fastest window (the shortest observed bars) instead of the whole song, since travel rate, pulse widths and in-beat gaps are all hardest where beats are shortest; per-head deduplication saves little once P2.2 gives heads distinct phases. The chosen reduction and its measured time are recorded before P2.4c builds on it.
- Time zero (carry 10): a lit cue at time zero that needs a move fails with the non-substitutable "darkness is never established" (`preposition.py:455-471`) although dropping it is safe. Report it as a substitutable `infeasible_transition` with an accurate reason, so `drop_accent` applies. A cue with an unauthored dimmer whose default byte is dark stays treated as lit: that only demands reveal feasibility and never claims darkness.

- [ ] Write `test_entry_window_cuts_first_cue_and_keeps_phase_origin`, `test_entry_window_is_whole_beats_at_the_section_tempo_ending_on_the_frame_grid`, `test_entry_window_applies_once_per_section_not_per_cycle`, `test_cue_inside_entry_window_is_dropped_with_a_record`, `test_section_shorter_than_its_window_renders_dark_with_a_record`, `test_dip_skipped_when_predecessor_ends_where_successor_begins`, `test_dip_kept_on_a_wheel_change`, `test_dip_kept_on_more_than_one_frame_of_travel` (each asserting the trace's `cut`/`skipped` record); `test_window_fits_a_moving_first_cue_cut_at_its_end` (a first cue whose pose at the window end is farther from the predecessor than its entry pose); and one test per predecessor case, each rendering without a transaction error: the previous section has no cue on the fixture, all its cues were dropped, it was shorter than its window and rendered dark, and a cue was substituted under `drop_accent`; a fallback test where a step opting into `drop_accent` under policy `drop_accent` keeps the cue dark and the default `error` refuses; a time-zero lit cue that `drop_accent` drops.
- [ ] Extend the fuzz: the transaction's `required_ms` never exceeds `worst_case_entry_ms` (the bound dominates the model it summarizes) for random predecessor states inside an envelope and random entry poses, and for predecessor cues that move at the rate limit up to their last frame, which leave the head arriving up to latency plus one frame after the gap starts (`_end_state`, `preposition.py:899-912`; `_follow`, `:618-638`): with zero and nonzero latency and settle, and with a short predecessor cue carrying a wheel change. Unknown terms return `None`.
- [ ] Write gate tests: a template whose own cycles cannot reposition is refused before planning under `error` and admitted under a fallback it declares.
- [ ] Write `test_default_reposition_fallback_leaves_session_id_and_fingerprint_unchanged` and a non-default value that changes the render fingerprint but not the session id.
- [ ] Run the new and extended test files; expect failures.
- [ ] Implement; record the gate measurement and the chosen reduction in the task checkpoint.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/compile tests/integration/test_mh_physical_pipeline.py -q`; run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): plan repositioning at section entry and enable declared fallbacks`; do not combine unresolved task failures with the next task.

## P2.4b — Visibility envelopes and masked temporary attributes

Added 2026-11-14 (split from P2.4 on review).

**Files:** Create `moving_heads/compile/visibility.py`. Modify `sequencer/models/template.py` (step-level `physical_visibility`; template-level `Template.physical_overlays`, refused by `compile_template`), `moving_heads/compile/template_compiler.py` (apply envelopes per compiled segment and overlays per fixture across steps). Tests: create `tests/unit/sequencer/moving_heads/compile/test_visibility.py`; synthetic templates in `tests/support/mh_physical.py`. Not modified, although the plan listed it: `compile/intent_resolution.py`, which resolves legacy section intent; the physical path applies none (`pipeline.py:736-749`).

**Interfaces:**

- `VisibilityEnvelope(visible_phase_start, visible_phase_end, attack_beats, release_beats, level: float = 1.0)`. Phases are fractions of the step's movement period (`movement.physical.period_beats`), evaluated at the fixture's movement phase including its P2.2 offset, so the lit window follows the path; pan and tilt must share an offset when an envelope is present. A `hold` step (no period) cannot carry an envelope. `apply_visibility(segment: FixtureSegment, envelope: VisibilityEnvelope, *, phase_map: MusicalPhaseMap) -> tuple[FixtureSegment, ...]` (a phase map, not a `BeatGrid`: phase comes from the musical phase map, P1.2) returns the lit slices of one compiled segment, cut with `slice_physical_segment` so the phase origin is kept. The dark complement is left between cues, so `plan_prepositions` performs every dark return as an ordinary transaction (`preposition.py:428-564`). Reason for the change: P1's pass masks only between cues and never checks darkness inside one (P1.5: mid-cue wheel changes were never emitted), so in-cue dark motion would be a second dark-motion algorithm.
- Envelope and the step's own channels: the envelope replaces the dimmer. A step with an envelope may not also set `dimmer.physical` or a `physical_shutter` pulse (validation error); inside each lit slice the envelope authors the dimmer at `level` with linear attack and release ramps, and a profile without a dimmer axis requires both ramps to be zero. The shutter in a lit slice is the step's static `physical_shutter_state` when set, otherwise the profile's `discrete.open_state` (`config/fixtures/capabilities.py:174`); a profile with neither rejects the step. This consumes the identity-only `discrete.open_state` path (carry 9).
- `AttributeOverlay(start_beats, end_beats, mask_beats, channel, state, release: Literal["resume_base"])` is template-level, with offsets in beats from the cycle start: absolute ms cannot be authored in a template, and a template-level overlay can span a step boundary. Per fixture it is realized by splitting every cue it intersects: base slice, dark mask gap, overlay slice (the base trajectory with `channel` replaced), dark mask gap, base slice. The resuming slice comes from whichever base step is in force at the release, so a base change during the overlay is what resumes. A mask gap too short fails as the transaction's `infeasible_transition`. Numeric zero in the wheel is never a blackout proxy. Overlapping same-priority overlays fail; overlays on different channels may compose if physical constraints permit.

- [ ] Write frame tests proving every frame between lit slices is dark, each fixture's first lit frame is settled, attack/release ramps sit inside the lit slice, and an envelope plus a dimmer pulse is rejected. Build the base-change test from two steps, A with color `red` on `[0, 1)` bar and B with `blue` on `[1, 2)`, and a gobo overlay on `[0.75, 1.25)`: after release the base is B's slice with `blue`, not a stale `red`. Test a mask/lock collision fails before emission and an insufficient mask gap fails.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_visibility.py -q`; expect failures.
- [ ] Implement the envelope and overlay composition; reuse `plan_prepositions` and `encode_fixture_frames`.
- [ ] Rerun; compare all encoded frames under repeated runs and full/subset output; run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add visibility envelopes and masked temporary attributes`; do not combine unresolved task failures with the next task.

## P2.4c — Rig-aware catalog admission, section succession and the six families

Added 2026-11-14 (split from P2.4 on review).

**Files:** Modify `moving_heads/templates/data_loader.py` (`PHYSICAL_TEMPLATE_DIR` and `admit_physical_catalog`), `moving_heads/templates/library.py` (a public accessor for `_source_by_id`, `:157`, `:234`), `packages/twinklr/cli/main.py` (call the helper, `:354-369`), `moving_heads/pipeline.py` (`check_physical_templates` returns an admission result instead of raising on the first failure; the succession check; the render record lists exclusions), `rendering_stage.py` (the gate publishes the admitted IDs and exclusions in context state; the render stage passes exclusions to the renderer), `stage.py` (`MovingHeadStage` offers the gate's admitted IDs when present, `:102`, `:207`, `:343`). Create `fly_out_cascade.json`, `fly_in_cascade.json`, `target_orbit.json`, `mirror_wings.json`, `finite_snap_hold.json`, `masked_wheel_flick.json` and a `README.md` in `catalog/templates/moving_heads_physical/`. Tests: create `tests/integration/test_mh_physical_families.py`; extend `test_render_preflight_stage.py`, `tests/unit/sequencer/moving_heads/templates/test_data_loader.py` (admission isolation), `tests/support/mh_physical.py` (a catalog context manager that restores the shared `REGISTRY`). Docs: the mode row, `--template-dir` row, overview and pipeline guide as listed below.

**Catalog location and loading.** The documents live outside
`catalog/templates/moving_heads`: that directory's documents must stay model-equal to
their Python builtins (its README), and it is loaded recursively
(`discover_template_documents`, `data_loader.py:72-78`) by
`test_tracked_data_proofs_load_alongside_all_python_builtins_only_with_override`
(`test_data_loader.py:180-198`), which asserts exactly three IDs and 37 entries.
`admit_physical_catalog(job_config, *, registry=REGISTRY) -> list[str]` loads
`PHYSICAL_TEMPLATE_DIR` only when `job_config.moving_heads.mode == "physical_v2"`;
`_run_pipeline_async` calls it after the builtins and before `--template-dir`
(`cli/main.py:354-369`, ahead of `offered_template_ids` at `:425`). A `--template-dir`
that resolves to `PHYSICAL_TEMPLATE_DIR` is not loaded a second time (which would raise
a duplicate-ID collision); the run logs that it is already admitted. Nothing else loads
the directory, so legacy runs, the deterministic selector's candidate set
(`packages/twinklr/core/agents/sequencer/moving_heads/deterministic_selector.py:157-160`)
and every 37-entry assertion are unchanged. A changed offer already enters the planner
cache key through admitted IDs and descriptions (`orchestrator.py:248-252`).

**Rig-aware admission (integrator decision).** Under `physical_v2`, a catalog template
that cannot resolve on this rig (a missing preset, axis, wheel, topology or footprint,
or any failure of the gate's dry compile or reposition check) is left out of the
planner's offer, with the reason logged and recorded in the render trace
(`admission_exclusions`); the run is refused only when no template remains. Where the
line is: exclusion applies only before planning and only to templates whose registry
source is `PHYSICAL_TEMPLATE_DIR`. A template the user supplied (`--template-dir`) that
fails the gate still refuses the run, as today (`pipeline.py:288-292`). A template a plan
or checkpoint already names fails hard at render (`_render_physical`,
`pipeline.py:750-756`); nothing is excluded after planning. The gate publishes the
admitted list in context state and `MovingHeadStage` offers that list. P2.5's zoom
family is excluded on a zoomless rig through the same path, by its dry compile's
capability failure.

**Section succession (integrator decision 3).** Two candidate checks:

| Check | Proves | Cannot prove | Cost |
|---|---|---|---|
| Two-cue `plan_prepositions` per ordered pair, from A's terminal state and B's first cue in the gate's existing dry compiles | That B's entry fits after A's terminal state at the dry compile's placement and tempo | A's terminal state at other placements (a periodic kernel cut at another section end ends elsewhere); B's window at other tempos | N² transaction plans, no recompiling |
| `worst_case_entry_ms` bound (P2.4a), sizing each section's window at render from the kept predecessor and the section's own pose range | That the window fits the transaction from any predecessor state in the envelope to any pose the cut can land on, at that section's placement and tempo | How long the dip is; it is conservative, so a wide-ranging section dips longer than its actual succession needs | One bound per section and fixture, no recompiling |

Choice: the bound, which holds at every placement and tempo and is O(N); the pair check
is not built. By integrator decision the bound sizes each section's window at render
(P2.4a), so section entry fits by construction and no template is excluded for a short
window. The gate excludes a template whose bound is unknown (`None`) on any fixture,
and reports each offered template's worst-case dip: the bound from the union, per
fixture, of every offered template's compiled pose range and the initial pose, in whole
beats at the song's fastest bars. Measure before fixing the design: compute those dips
for the six families on the synthetic profile and at travel speeds a real fixture
plausibly declares, across 60–180 BPM; if dips run to several bars, the integrator
decides whether to narrow family ranges or accept them before P2.4c builds the
families.

**What stays plan-dependent.** Section entry fits by construction (P2.4a's sizing and
fuzz). Two look degradations appear only after planning: a long entry dip, and a section
shorter than its window, which renders dark. The gate's report of each offered
template's worst-case dip is the pre-planning warning for both; whether they are
acceptable is `PENDING-OWNER`. Still checked only at the
gate's placement, or not at all before planning: a `ONCE` cycle cut by a short section
(P2.3); P2.0's edge cuts; repositioning inside a template at placements other than the
gate's (tempo-monotonic when the gate compiles the fastest window, P2.4a, but alignment
to bars differs). No automatic remedy is added at render: P1 forbids an automatic
delayed reveal, and fallbacks must be explicitly configured (architecture §6). Every
family step therefore declares `physical_reposition_fallback: drop_accent`, so a job that
sets `reposition_fallback: drop_accent` gets a residual failure as a dark cue recorded in
the trace; under the default `error` it fails after planning. Feeding render feasibility
into planner validation is carried to P3-T3.

**Families.** Fly-out lights center-to-edge travel and returns dark (envelope); fly-in
lights edge-to-center travel and returns dark. Both share the same path/visibility phase
origin per fixture, including phase offsets. Finite snap/hold is `ONCE` with
`HOLD_LAST_POSE`: its closing step's cue extends to the section end and holds the
terminal pose, lit (P2.3), with achievable travel; it cannot be instantaneous solely
because the name says snap. Target orbit and mirror wings are continuous (no envelope) and their
cycles span whole movement periods, so consecutive cycles continue within one frame of
travel; the gate's reposition check catches a family that does not. Every family sets
explicit start angles, using a position reference only as an optional override, so no
family hard-requires a rig preset; `masked_wheel_flick` names a rig attribute preset for
its flick state and is excluded on a rig without it. The catalog README and the user
guide list each family's required presets and capabilities. Each family authors its dimmer on every step, meets
`validate_template_document` (`templates/library.py:103-128`), and declares its
reach/rate variants as presets, which the gate dry-compiles and P3-T3 can later select.

- [ ] Write admission tests: with the catalog on disk, a legacy run's offered templates, planner context and the deterministic selector's candidates are unchanged and the shared registry holds 37 entries; a physical run offers the families plus any `--template-dir` documents; a zoomless, preset-less rig is offered every family that does not need them, with each exclusion and its reason in the trace; a rig that admits none is refused; a failing `--template-dir` template still refuses the run; `--template-dir catalog/templates/moving_heads_physical` loads nothing twice.
- [ ] Write succession tests: a template with an unknown bound term is excluded naming the fixture and term; every ordered pair of admitted families renders back to back on the synthetic rig at the song's fastest bars; the gate reports each family's worst-case dip.
- [ ] Write frame tests on the families: lit-direction signs of fly-out and fly-in differ; every return-travel frame is dark; orbit and wings never go dark between cycles.
- [ ] Run `uv run pytest tests/integration/test_mh_physical_families.py tests/unit/agents/sequencer/moving_heads/test_render_preflight_stage.py tests/unit/sequencer/moving_heads/templates/test_data_loader.py -q`; expect failures.
- [ ] Run the measurement above and record it; then implement admission, the succession check and the six documents.
- [ ] Rerun; compare all encoded frames under repeated runs and full/subset output; record the gate time for the full catalog and the emission time of an 8-head, 4-minute family render (emission's overlap scan is quadratic in effect count and unmeasured); run the invariance check; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): admit physical families the rig can render`; do not combine unresolved task failures with the next task.

## P2.5 — Bounded optical pilot

**Files:** Modify `config/fixtures/capabilities.py` (`AxisName` `:24` and `_AXIS_UNITS` `:27` gain `zoom` in `degree`; `AxisCapability` `:30-143` gains `dmx_min: int = 0` and `dmx_max: int | None = None` (meaning `full_word`), each excluded from dumps at its default, used by `_uninverted_word` `:112-115`, the inversion at `:110` and `check_default_word` `:117-143`), `sequencer/models/enum.py` (`ChannelName.ZOOM`, `:141-146`), `sequencer/models/moving_heads/physical.py` (`CONTINUOUS_UNITS` and `AXIS_KEYS`, `:69-80`), `sequencer/models/template.py` (a step-level physical zoom spec; `has_physical_data`), `moving_heads/compile/physical.py` (ZOOM trajectory and rate check), `moving_heads/compile/preposition.py` (zoom held and settled across gaps; `_center` `:746-757` inverts the word mapping and must honor the subrange). `export/frame_encoder.py` should need no change, since `_encode` is keyed by `AXIS_KEYS` (`:384`); verify. Add `zoom_wave.json` to `catalog/templates/moving_heads_physical/` and its requirements to that directory's README. The synthetic zoom profile is a payload in `tests/support/mh_physical.py`, not `tests/fixtures/moving_heads/physical_v2/zoom_profile.json`, because `physical_test_templates` loads every JSON in that directory as a template (`mh_physical.py:252`, `:268-288`). Test: create `tests/unit/sequencer/moving_heads/export/test_optical_axis.py`. Capability-aware admission is P2.4c's; this task adds no admission code.

**Interfaces:** `degree` is already an axis unit (`capabilities.py:40`); zoom is a new axis name in degrees, and `ChannelName.ZOOM` exists only for a declared zoom axis. Declare minimum/maximum beam angle, `dmx_min`/`dmx_max`, inversion, resolution and known settle. Encoding is `dmx_min + round-half-up(normalized * (dmx_max-dmx_min))`; inversion reflects around `dmx_min+dmx_max`. With the defaults, pan/tilt words and every Phase 1 profile dump are unchanged. The transaction pass authors only pose, dimmer, shutter and wheels in gaps (`_author`, `preposition.py:662-728`), so an unauthored zoom would fall to its default byte between cues and could reveal unsettled; P2.5 holds zoom through each gap and waits its settle before the reveal. No automatic "iris equals zoom" or continuous interpolation through gobo-rotation modes. `zoom_wave` uses existing phase domains on one supported continuous optical axis; categorical template selection remains the planner interface. Phase 1 decided a missing capability always fails; `omit_optional_zoom` is the first declared alternative and is recorded in the trace.

16-channel models (carry 8): the owner's moving-head models are 16 channels wide
(`DmxChannelCount="16"`), and `check_physical_models` refuses a profile footprint wider
than the model (`export/xsq_adapter.py:101-105`). The synthetic 18-channel test profile
stays for offline tests; the pilot profile prepared for owner validation keeps every
offset, zoom included, within 1–16 unless the owner widens the model in the layout.

- [ ] Write a synthetic 10°–40° zoom profile over bytes 20–220; assert endpoint encoding, monotonic mapping/inversion, out-of-range rejection, and unsupported-fixture rejection; assert pan/tilt words and Phase 1 profile dumps are unchanged with default subranges; assert zoom holds and settles across a gap. A template may declare `omit_optional_zoom` only as an explicit alternative recorded in trace.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/export/test_optical_axis.py -q`; expect failure.
- [ ] Implement only this axis through existing physical encoding, with synthetic provenance clearly recorded. Broader focus/iris/prism/rotation support requires a concrete fixture case and a separate extension.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/export/test_frame_encoder.py tests/unit/sequencer/moving_heads/compile/test_preposition.py tests/unit/config/test_mh_capabilities.py -q`; run the invariance check; prepare the exact 16-channel pilot profile/template for future authorized fixture validation. Synthetic proof is not a real-profile acceptance. Checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add a bounded capability-aware zoom pilot`; do not combine unresolved task failures with the next task.

## Compatibility, cache/data migration and rollback

P2 adds typed optional fields and an explicit finite repeat enum; existing `TemplateDoc` parsing and builtins stay valid, and `p1_linear_reveal.json`, which sets both start angles, parses unchanged. Physical-only fields are refused under legacy. Every new field is excluded from dumps at its default and render-only job keys are listed in `RENDER_ONLY_CONFIG_KEYS`, so legacy session ids and all existing fingerprints are unchanged (the invariance check). P2.0 changes the phase map only for grids Phase 1 refused; a grid Phase 1 accepted keeps its knots, fingerprint and frames, while its trace gains the keys P2.0 lists. Non-default presets and topology are fixture-group content and template fields are template content, so they enter the render fingerprint (`identity.py:76-80`); editing a preset invalidates only render output, not planning. A planner exposed to a changed template catalog already includes the admitted IDs and descriptions in its cache key (`orchestrator.py:248-252`); extend it only when additional exposed family metadata is introduced, with a targeted `tests/unit/agents/sequencer/moving_heads/test_orchestrator.py` cache test. Do not rewrite checkpoints or silently replace same-ID builtin documents; physical families have distinct IDs and provenance. Rollback selects legacy policy/previous template versions and ignores the physical catalog, which loads only under `physical_v2`; no accepted artifact is overwritten.

## Phase 1 carry-forwards

Added 2026-11-14. Where each item Phase 1 carried forward lands. Sources: the
[P1 decisions](phase-1-fixture-fidelity.md#decisions-and-carry-forwards-recorded-during-execution),
the [exit evidence](../evidence/2026-11-14-p1-exit/README.md#known-limits-at-exit) and the
[xLights result](../evidence/2026-11-14-p1-xlights-result/README.md#findings). Each
deferral is also recorded under the task it names.

| # | Carry | Placement |
|---|---|---|
| — | Silent song edges | P2.0 |
| 1 | Gate dry-compile cost (about 0.8 s per template-and-preset combination, 8 heads, 4 minutes) | P2.4a measures and reduces it before P2.4c builds on it; P2.4c records the full-catalog time; ceiling per [decision 3](#decisions-on-the-kickoff-open-questions) |
| 2 | No production template is physical | P2.4c: six families, admitted only under `physical_v2`, filtered by what the rig can render |
| 3 | Planner intensity not applied on the physical path | Deferred to [P3-T3](phase-3-arrangement.md#p3-t3--motif-resolution-restrained-signals-and-compilation), which binds categorical reach/rate to named variants a physical template declares. P2.4c families declare those variants as presets; until P3 the trace warning stays (`pipeline.py:736-749`) |
| 4 | Reposition fallbacks cannot be enabled from config | P2.4a |
| 5 | `locks` has no producer | Deferred to [P4-T1/T2](phase-4-refinement.md#p4-t2--dependency-aware-offline-patching), whose refinement requests produce locks; no P2 task needs one |
| 6 | Job `transitions` not applied; `FADE_OUT` refused | Stay as in Phase 1: `plan_prepositions` does the physical boundary work and no shipped template uses `FADE_OUT`; P2.4b's envelope gives fades inside a family. Whether `physical_v2` needs a section-transition mapping before it could become the default is deferred to [P5-T4](phase-5-evaluation.md#p5-t4--read-only-report-generation-and-feature-level-release-gates)'s feature-level release decision |
| 7 | Plan-dependent failures surface after paid planning | P2.4a/P2.4c: the section entry window, the intra-template reposition check and the succession bound move section-entry failures before planning; declared fallbacks degrade residual failures visibly when the job opts in. What remains is listed in P2.4c; feeding render feasibility into planner validation is deferred to P3-T3 |
| 8 | Owner's models are 16 channels wide | P2.5: the owner-facing pilot profile fits 1–16. Families name no offsets; any owner-facing P2.4c render needs a ≤16-channel profile |
| 9 | Identity-only registry paths | `discrete.open_state`: P2.4b consumes it. `profile_id`, `discrete.states.range_min`/`range_max`: no P2 consumer, since a range never chooses a byte (P1.1); deferred to [P4-T5](phase-4-refinement.md#p4-t5--bounded-gdtf-import-pilot), whose GDTF import reads manufacturer ranges |
| 10 | Reposition planner low items | Time-zero misleading reason: fixed in P2.4a. Unauthored dark-default dimmer treated as lit: left as is (conservative); P2.4c families always author the dimmer |
| — | A preset id the template does not declare applies no preset (exit limit) | Deferred to [P3-T2](phase-3-arrangement.md#p3-t2--capability-projection-and-cache-isolation), whose projection exposes only eligible family/variant pairs to the planner |
| — | Emission's overlap scan is quadratic and unmeasured (exit limit) | P2.4c measures emission time on an 8-head, 4-minute family render; any fix waits for a measurement that binds |
| — | Portable state names across profiles (P1.2–P1.4) | P2.1 attribute presets |
| — | Declared-optional alternative for a missing capability (P1.2–P1.4) | P2.5 `omit_optional_zoom` |

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; rechecked and rewritten 2026-11-14 at
`d6096254`. See the [shared rule](README.md#documentation-registry-and-test-surfaces).

- **Template counts.** The 37-entry assertions are `test_data_loader.py:129`, `:141`, `:198`, `test_repeat_contract_validation.py:158`, `test_documented_channel_scope.py:15-21`, `tests/integration/test_all_templates_compile.py:35`, and `BUILTIN_TEMPLATE_COUNT` (`tests/support/mh_physical.py:256`, used at `test_mh_physical_pipeline.py:695-721`). The three-ID assertion is `test_data_loader.py:193-197`. P2.4c's catalog sits outside `catalog/templates/moving_heads` and loads only under `physical_v2`, so none of these changes. Tests that load the families use a context manager that restores the shared registry, as `physical_test_templates` does.
- **Config inventory.** Physical-only fields are evidenced as P1.1 decided: an `EFFECT_TEST` record per exact path, pointing at a parameterized physical test that names the component the change alters, registered after the legacy fixture-repointing loop (`tests/config_effects_registry.py:2558-2569`). Existing components: `rejected`, `words`, `check`, `preposition`, `darkness`, `frames`, `changes` and identity-only (`:2576-2583`) for profile paths (`:2584-2646`, test `tests/unit/config/test_mh_capabilities.py:985`); template paths at `:2704-2760` (tests `compile/test_physical.py:806`, `compile/test_physical_discrete.py`). New paths by task: P2.1 `fixture.presets…` and `template.template.steps.component_refs…`; P2.2 `fixture.topology…` and `…steps.physical_distribution…`; P2.3 `…movement.physical.transform…` and the `ONCE` repeat value; P2.4a `…steps.physical_reposition_fallback` and `job.moving_heads.reposition_fallback`; P2.4b `…steps.physical_visibility…`, `template.template.physical_overlays…` and the repointed `discrete.open_state`; P2.5 `axes.dmx_min`/`axes.dmx_max` on both profile roots and the zoom spec. P2.0 and P2.4c add no field.
- **Documents.**
  - `docs/user-guide.md` `moving_heads.mode` row (`:259`): P2.0 replaces the silent-edge refusal sentence; P2.4a adds the intra-template reposition check to the gate description and a `moving_heads.reposition_fallback` row; P2.4c replaces "none of the builtins do yet" with the admitted physical catalog, rig-aware exclusion and the succession check, and lists each family's required presets and capabilities. Fixture-config section (`:316`): P2.1 presets, P2.2 topology, P2.5 zoom and `dmx_min`/`dmx_max`. The `--template-dir` row (`:342`) gains that the physical catalog loads automatically under `physical_v2` and is never loaded twice (P2.4c). The `--layout` row (`:344`) is already current after Phase 1 and `85b7aa1e`.
  - `docs/pipeline_guide.md` (`:801-812`): P2.0's edge behavior; P2.4c's catalog and admission.
  - `docs/overview.md` (`:35-42`): keep both "37 Python builtins" sentences verbatim (`test_documented_channel_scope.py`); P2.4c adds the physical catalog as a separate statement and drops "in Phase 1" from the planner-intent sentence.
  - `catalog/templates/moving_heads_physical/README.md`: new in P2.4c, listing each family's required presets and capabilities; the existing catalog README is unchanged.
  - `context/current-state.md` (`:47-49`, "no production templates and refuses most real audio") is corrected at phase closeout.

## File ownership and ordering

Added 2026-11-14; revised after review. Production files each task edits (tests and docs as listed in the task):

| Task | Production files |
|---|---|
| P2.0 | `musical_phase.py`, `template_compiler.py`, `pipeline.py`, `rendering_stage.py` |
| P2.1 | `config/fixtures/presets.py` (new), `compile/presets.py` (new), `groups.py`, `template.py`, `context.py`, `template_compiler.py`, `compile/physical.py`, `pipeline.py` |
| P2.2 | `topology.py` (new), `groups.py`, `template.py`, `context.py`, `template_compiler.py`, `compile/physical.py`, `pipeline.py` |
| P2.3 | `template.py`, `compile/physical.py`, `scheduler.py`, `template_compiler.py` |
| P2.4a | `template.py`, `template_compiler.py`, `preposition.py`, `config/models.py`, `caching/identity.py`, `pipeline.py`, `rendering_stage.py` |
| P2.4b | `visibility.py` (new), `template.py`, `template_compiler.py` |
| P2.4c | `data_loader.py`, `library.py`, `cli/main.py`, `pipeline.py`, `rendering_stage.py`, `stage.py`, catalog documents |
| P2.5 | `capabilities.py`, `enum.py`, `models/moving_heads/physical.py`, `template.py`, `compile/physical.py`, `preposition.py`, catalog document and catalog README |

Every pair of tasks shares a production file except P2.0 with P2.5, and P2.4c with P2.3
and with P2.4b. Every task edits
`tests/support/mh_physical.py`, and every task but P2.0 and P2.4c edits
`tests/config_effects_registry.py`. Under the
[execution conventions](README.md#execution-conventions), which forbid parallel edits to
a shared test support file, none may run in parallel: run them in sequence on
`feat/mh-true-up-p2`, each task's review and commit before the next starts. One narrow
exception: the capability and encoding half of P2.5 (`capabilities.py`, `enum.py`,
`models/moving_heads/physical.py`, `test_optical_axis.py`) shares no production file with
the others and may run in its own worktree if its registry, test-support and
documentation edits wait until it merges.

Recommended order: **P2.0 → P2.4a → P2.1 → P2.2 → P2.3 → P2.4b → P2.4c → P2.5.** P2.0
first, because it alone makes `physical_v2` accept real audio and it changes the compile
limits every later task's tests run under. P2.4a next: it depends only on Phase 1 and
P2.0, and its gate-cost measurement and entry-window bound inform the family design
before any family exists. P2.1 before P2.2 and P2.3, because named positions supply the
base aim both use. P2.4b needs P2.2's phase offsets and P2.3's kernels; P2.4c needs
everything before it. P2.5 is the optional pilot and last.

## Decisions and carry-forwards recorded during execution

P2.0, 2026-11-14 (reviewed separately from its author; one review and a fix round for
four low findings):

- **Result.** All 961 grids of the sweep build (18 before). The covered start is the
  song start when the lead-in is at most one beat interval, otherwise one interval
  before the first beat; the end follows the same rule. `physical_cue_limits` gives the
  gate and the render the same limits.
- **Invariance anchors at `d6096254`,** unchanged after P2.0: request fingerprints
  `4bd67b39cc934912847c07d2c109a01c2fd36257d211c34c612e6e2db07f00fc` and
  `458826581adea7e742598c113a6576ac1f9873caac9e035eded7e1d7834aa2d8`, with byte-identical
  `.xsq` files; the 16 Phase 0 fingerprints.
- **Reviewer's probes.** Twelve hand-built edge grids and 961 grids placed 7.3 ms off
  the frame grid: no frame outside the limits has an open shutter or a nonzero dimmer,
  and the gate never accepted a grid the render then refused.
- **Edge knot arithmetic.** A silent-edge knot's beat is derived from its stored float
  time, so time and beat agree exactly; the docstring states the rounding bound. Phase 1
  maps never take that path.
- **Park pose.** After the last cue the head parks at that cue's last frame, as
  `plan_prepositions` already did.
- **Trace.** `covered_span` holds the unrounded knot times; `longest_beat_interval_ms`
  is recorded; a render logs one warning with the dropped-cue count and the limits.
- **Not covered by the plan, left as Phase 1 behaved:** one observed beat plus an
  explicit knot on the other side still raises.
- **Unverified.** Real-audio beat grids; any physical template other than the test one.
  How the dark edges look is `PENDING-OWNER`.

P2.4a, 2026-11-14 (reviewed separately from its author; one review with four high
findings, a fix round, a re-review and a final confirmation):

- **Entry kept as authored when it already works.** A section's first cues stay uncut
  whenever `plan_prepositions` accepts the entry, and the transaction after the
  section's first gap, from the actual head state. The window applies only otherwise.
  This replaces the plan's one-frame, no-wheel skip rule and leaves every Phase 1
  output byte-identical, so `PHYSICAL_RENDERER_REVISION` was not bumped.
- **Window sizing follows the kept cues.** At render the predecessor term comes from
  the planner's own head model run over the cues actually kept (`follow_cues`), not
  from a fixed term. The plan's formula was unsound: on an 8-bit axis, in-limit motion
  that keeps crossing word boundaries leaves the model's head arbitrarily far behind
  (the reviewer found 20,420 ms needed against a 3,300 ms bound). The envelope form of
  `worst_case_entry_ms` remains only where the predecessor is unknown.
- **New refusal: motion an axis cannot follow.** The compile, and so the gate, refuses a
  cue that leaves the head more than one encoded word behind its commands
  (`follow_lag`), naming fixture, axis and rates. The reviewer found no false refusal
  on linear and sine motion at 30–100% of the speed limit, on 8-bit and 16-bit rigs
  from 45 to 720°/s. It could refuse an input Phase 1 rendered if one contained such
  motion; none is known.
- **Shutter-aware cut.** A cut moves to the next shutter change until the first state
  can take effect (`_holdable_cut`); the gate applies the same cut.
- **The gate compiles the whole song.** The plan's reduced window (the shortest bars)
  missed an isolated faster bar, and no window agrees exactly with the whole song
  because frame quantization makes instances at one tempo differ by a frame. A
  differential fuzz pins the agreement. Cost was cut by caching exact phase on the map
  and planning heads with identical inputs once.
- **Gate time, measured (8 heads, 4-minute synthetic song, 18 combinations):** 7.83 s
  for the Phase 1 test template, 19.7 s for dense fully lit sweeps (author); 0.63 s and
  1.34 s per combination (reviewer, loaded machine). The dense figure is about twice
  the 10 s target of [decision 3](#decisions-on-the-kickoff-open-questions). The
  target is not met and is not enforced; the gate runs before any paid call. P2.4c
  re-measures with the real families.
- **Fallbacks.** `TemplateStep.physical_reposition_fallback` and
  `MHRenderPolicy.reposition_fallback` (render-only, out of dumps at `"error"`).
- **Time zero.** A lit cue at time zero that needs a move is a substitutable
  `infeasible_transition` when darkness can be established at all.
- **Evidence at the final round.** Reviewer: 3,000 bound cases with the predecessor
  followed, 0 failures; 800 random multi-section renders across four rigs and three
  policies, 482 rendered and passed the byte-level check on every fixture, 318 refused
  at the gate, 0 failed after admission; 39 of 40 mutations caught, the survivor only
  lengthens the window.
- **Carried to P2.4b.** A wheel change inside a cue is covered by the render-time
  sizing but not by the envelope form used before planning.
- **Unverified.** Real fixtures; how the remaining dark dips look (`PENDING-OWNER`).

P2.1, 2026-11-15 (reviewed separately from its author; one review, then test gaps
closed):

- **Start angles are optional on the physical movement spec.** A step must still get
  each angle from itself or from a position reference; a position preset entry carries
  both angles, so "set by neither" is decided at template validation, and a reference
  that does not resolve on the rig is refused by the gate before planning. Existing
  templates dump and fingerprint as before.
- **Stricter than the plan.** Two attribute presets that set the same channel fail even
  when their values agree. A broken position reference fails even when the step sets
  both angles itself. A preset naming a fixture outside the group, or an attribute
  preset on a fixture without a physical profile, is refused when the fixture file
  loads, for legacy jobs too.
- **Provenance** is a SHA-256 of each preset entry used, in segment metadata
  (`component_provenance`); presets have no version field.
- **Identity, corrected from the plan's wording.** Presets stay out of the session id,
  so an edit never re-keys planning. The render fingerprint hashes the whole fixture
  group, so any preset edit changes the fingerprint of every render on that rig, not
  only of renders that depend on that preset, and adding presets to a rig changes its
  legacy fingerprints while the bytes stay identical. That over-invalidates and is safe.
- **Precedence** as the plan corrected it: a template preset patch counts as set on the
  step.
- **Mutations.** 21 tried by the reviewer; all are now caught.
- **Test time.** The full suite went from about 137 s to about 240 s in P2.4a; nine of
  the ten slowest tests are its fuzz and gate tests. Trimmed in a follow-up commit.

P2.2, 2026-11-15 (reviewed separately from its author; one review, then four low
findings closed):

- **Arithmetic verified independently.** The reviewer reimplemented the resolver from
  this plan's text and compared 75,435 head values across random rigs, blocks, groups,
  wings, spreads and subsets: no disagreement. Eighteen mutations, none survived.
- **Exactness.** `spread_cycles` is converted with `exact_decimal` and multiplied by
  `Fraction(slot, S-1)`; it must be 0 or more, and direction is set by `direction`.
- **Pan sign** comes only from the distribution that owns PAN and multiplies the pan
  displacement; a referenced base aim is not mirrored.
- **Lagging head.** It reaches the terminal pose once its phase reaches one; a step
  that ends sooner cuts it where its path has reached. Its pulse starts mid-cycle:
  intervals cut by the step start or end keep the Phase 1 exemption, and every interval
  inside the step is checked at that head's own phase.
- **Derived topology.** Without a declared topology, one row is ranked by
  `position_index`, gaps kept as empty slots, so a head absent from the file leaves a
  hole when the indices show it. A shared index refuses a distribution.
- **Gate grouping.** `_plan_key` hashes trajectories, not the distribution metadata, so
  heads with identical trajectories are still planned once. Gate time per combination
  on the 8-head, 4-minute song: distributed hold 0.83 s, distributed sine 2.02 s.
- **Found by this review, fixed in a follow-up to P2.4a:** the entry window was the
  maximum over a section's fixtures, so removing one head could change the others'
  frames; and one fuzz case fails the byte-level honesty check at a back-to-back cycle
  boundary, reproducible before P2.2.

P2.4a follow-up, 2026-11-15 (from the P2.2 review; reviewed separately, one fix round
and a confirmation):

- **Entry window per fixture.** Each head has its own kept-as-authored probe, bound,
  window and cut. A rig with any head removed renders every remaining head
  byte-identically to the full rig (reviewer: 978 comparisons across declared and
  derived topologies, presets, wings and all three fallback policies, no difference).
  Consequence: after a section boundary heads can re-enter at different times. How
  that looks is `PENDING-OWNER`.
- **Every head not kept as authored is cut where its first shutter state can take
  effect,** with or without a window. The probe checks shutter timing. This closed
  three cases the gate admitted and the render refused.
- **The honesty check was narrowed, deliberately.** `assert_honest_transactions` now
  treats only darkness the planner created (a transaction, a park, a substituted cue)
  as able to hide residual motion. It no longer flags motion inside a cue, or carried
  across back-to-back cues played as authored, that is still under way when a cue's own
  dark pulse ends. The reviewer traced the triggering case (the head on the next cue's
  authored sine, about 7 ms behind) and confirmed that transitions, the continuation
  jump limit, wheel changes, cue frame equality and substituted cues are still checked
  by unchanged rules; five constructed leak scenarios are each still caught, and no
  planner mutation newly survives.
- **Renderer revision stays 1.** No input renderable on `main` at `d6096254` changes
  bytes (34 of 700 random inputs render there; all identical, with the request and
  Phase 0 outputs). Inputs that need P2.2 or P2.4a did change between commits on this
  branch under an unchanged fingerprint; none of those was ever released.
- **Evidence at confirmation.** 800 random renders: 482 pass the honesty check, 318
  refused at the gate, 0 fail after admission. 46 of 46 mutations caught.
- **Low, left as is.** A head whose first cue is moved without a window is recorded in
  the trace as `action: "none"`, with the shift visible only in `first_cue_ms`.

P2.3, 2026-11-15 (reviewed separately from its author; a review with one high finding,
a fix round, a re-review, then three items closed):

- **Formulas.** Path position `u` is the step phase minus the head's distribution
  offset plus `transform.phase_cycles`, in exact fractions; `reverse` makes it `1 - u`.
  Circle `(cos 2πu, sin 2πu)`; lissajous `(sin 2πau, sin 2πbu)`, default 1:2; periodic
  sweep `(-cos 2πu, 0)`; finite sweep `(-cos π·clamp(u,0,1), 0)`. The displacement is
  rotated, scaled per axis by its extent, and added to the resolved aim; the mirror
  sign multiplies the pan component after rotation and scaling. The reviewer's
  independent evaluator agreed on 180,000 evaluations. The Phase 1 kernels are
  bit-identical over 200,000 values.
- **Where paths start.** A circle starts at the aim plus the pan extent, a periodic
  sweep at the aim minus the pan extent, a lissajous at the aim. This sets the entry
  aim.
- **Extents bound the unrotated path.** A lissajous turned by a non-quarter angle
  reaches up to √2 times its extents; limits are checked on real frames.
- **Pulses never see the transform or `reverse`.**
- **Refused at validation:** `transform` on `hold`, the sine kernels and `linear`;
  `reverse` on a periodic sweep (it would do nothing); an extent a turned sweep
  ignores; under `ONCE`, a dimmer or shutter pulse with duty below 1 (it would keep
  flashing through the hold; no planned family needs one).
- **`ONCE`.** One cycle at musical rate. `HOLD_LAST_POSE` extends the closing cues to
  the section end: a head reaches and holds its terminal pose, and a phase-lagged head
  finishes its move during the hold. `TRUNCATE` schedules nothing after the cycle; a
  lagging head is cut where it is and held dark. A step whose move cannot complete
  within it, `period × (1 − phase_cycles)` beats against the step's beats, is refused
  at compile, and so at the gate, because beats per bar come from the grid.
- **Gate for `ONCE`.** The gate compiles and reposition-checks every bar a full cycle
  can start from, over the cycle plus any lagging head's remaining move plus one bar,
  deduplicating placements identical relative to their start; bar 1 is never used to
  stand in for a later bar, because it enters from the initial state. Author's
  measurement on the 8-head, 4-minute song: 1.2 s at steady tempo, 4.8 s with 120
  distinct bars, 9.4 s with a lagging head as well.
- **Registry.** `repeat.mode` keeps its legacy record; `ONCE` is evidenced in
  `test_physical_paths.py`. `RepeatMode` is in no planner schema or context, and the
  selector does not read it.
- **Evidence at re-review.** Every admitted `ONCE` template rendered at every start bar
  from 2 on at three section lengths: 1,153 renders, 0 failures. 1,000 random renders:
  0 failures after admission.
- **Design choices awaiting a look judgment (`PENDING-OWNER`):** the finite sweep's
  cosine easing and the periodic sweep starting at an edge.

P2.4b, 2026-11-15 (reviewed separately from its author; a review with one high finding,
a fix round and a re-review):

- **The lit window is in pre-transform phase.** It is a time window in each movement
  period at the head's own P2.2 offset; the path's `transform` does not move it. A
  transform therefore changes which arc is lit: `reverse` on a finite sweep lit over
  (0, 0.5) lights the far edge to the centre. This corrects the plan's "follows the
  path", and P2.4c authors windows on this basis.
- **Envelope rules beyond the plan.** Pan and tilt must sit in one distribution;
  distributing the dimmer or shutter on a step with an envelope is refused. A lit
  window shorter than a frame is refused at compile. For a finite kernel the
  visibility phase clamps to [0, 1]: a window ending at 1 keeps a `ONCE` hold lit, and
  a release ramp on such a window is refused; a window ending earlier leaves the hold
  dark.
- **Overlay rules beyond the plan.** Refused: an overlay on a `PING_PONG` template, one
  running past the cycle end, level or ramps without a dimmer axis. An overlay does not
  apply to a `HOLD_LAST_POSE` remainder. A cue already holding the overlay's state is
  kept whole (`overlay_unchanged`). An overlay wholly inside an envelope's dark part
  does nothing. `AttributeOverlay.attribute_preset_id` was added for the flick family.
- **The plan's red/blue test is refused as written.** With a gobo overlay the base
  colour changes on a lit frame, which is refused with or without the overlay. The
  colour-overlay version is tested: the base in force at release resumes.
- **The honesty check was tightened.** `assert_honest_transactions` rejects any wheel
  change on a lit frame, cue content included. It flagged nothing in the existing
  suites and catches the in-cue flick mutant it used to miss.
- **Drop records** carry the frames actually dropped (`start_ms`, `end_ms`).
- **Registry.** `discrete.open_state` is now evidenced by its use in a lit slice.
- **Cost (reviewer, 8 heads, 4-minute song):** gate 1.0–2.3 s per template; at most
  52,285 effects and 5.9 MB.
- **Evidence at re-review.** 6,000 fuzz seeds: 2,368 admitted and rendered, no
  dishonest frame; 767 subset comparisons identical.
- **Gate gaps found by this review, fixed in a follow-up before P2.4c.** Seven of those
  seeds failed after gate admission, none caused by this task: a `drop_accent` cascade
  when a template mixes steps with and without the fallback; a repeating cycle started
  on a bar the gate never aligned it to; and the boundary into a `HOLD_LAST_POSE`
  remainder, which the gate never compiles (poses before this task, wheels with it).

Gate-coverage follow-up, 2026-11-16 (commit `5844117b`; reviewed separately from its
author over three rounds, the last two approving):

- **A planned show always renders (integrator decision, made under the owner's
  run-to-completion instruction; the owner can reverse it).** The first attempt widened
  the gate to enumerate every placement; review still found plans that passed it and
  failed at render (a `drop_accent` cascade reaching the song end, a window cut into a
  cue's dark tail). Correctness after paid planning no longer depends on the gate
  predicting every placement. New render-only policy field
  `MHRenderPolicy.on_unplayable: "dark" | "error"`, default `"dark"`, left out of dumps
  at its default and listed in `RENDER_ONLY_CONFIG_KEYS`.
- **This supersedes two statements in P2.4c above:** "No automatic remedy is added at
  render" and "under the default `error` it fails after planning". Darkness is the
  remedy, never a delayed or altered reveal; `"error"` restores fail-fast.
- **What degrades under `"dark"`.** A cue whose reposition still fails after its
  declared fallback is dropped dark. A too-short shutter state or failed park traced to
  a cue keeps that cue dark and the fixture is replanned; the dark set only grows, so
  it terminates. A step one fixture cannot compile at a section's placement
  (`PhysicalCompileError`, `PhysicalChannelError`, `EmptyStepError`) is left out for
  that fixture; a `ONCE` cycle too long for its section loses all its cues.
- **What still raises.** Unknown initial state, locks, an error no cue can absorb, a
  template that also fails from bar 1 over the song, and any other exception
  (`ValidationError` and plain `ValueError` included), so a code defect is not turned
  into a dark cue.
- **Reporting.** Each dropped cue is in trace `dropped_cues` (fixture, section,
  template, step, frames, reason, code); `unplayable_totals` per code in the render
  record; one warning per run. The CLI print of that warning has no test.
- **What the gate now guarantees.** An admitted template plays at every bar alignment
  (bars 1..p), from every `ONCE` start bar, and at revealing and song-start entries.
  Section ends, remainders, predecessor state and cascades are left to the degrade.
  The full remainder enumeration runs only under `"error"`.
- **Window-cut fix.** `apply_entry_window` drops a cut slice that stays commanded dark
  to its end; before, the planner miscounted that darkness. No input renderable on
  `main` changed bytes; the renderer revision stays "1".
- **Measured (reviewer).** 13,557 multi-section renders over admitted templates under
  `"dark"`: no exception, every fixture honest from encoded bytes, every record dark in
  the bytes, 4,781 subset comparisons identical. About 3.0% of authored cue frames
  were kept dark, 99% of them `ONCE` cycles too long for their section. Under
  `"error"` the known failing seeds still raise their original errors.
- **Gate time is over target.** Projected for 18 template-and-preset combinations on 8
  heads and a 4-minute song: 24.2 s steady, 27.6 s variable tempo (49.6 s under
  `"error"`), against a 20 s target. Per-head phase distribution defeats head
  deduplication and most of the time is the planner's per-frame follow. Carried to
  P2.4c's measurement with the six real families; a known cut is reusing a cue's
  encoded words across the two bar-1 entries.
- **Whether a dark cue is an acceptable look is `PENDING-OWNER`.**

## Phase exit

`physical_v2` accepts grids with silent edges, reports the covered span and holds every fixture dark outside it without inferring tempo; a grid Phase 1 accepted renders the same frames and fingerprint. Legacy session ids, the 16 Phase 0 fingerprints and the Phase 1 request fingerprints are unchanged. Six core families compile deterministically on the synthetic rig matrix and are offered only under `physical_v2`, each only on a rig that can render it; independent phase domains work; missing heads preserve canonical ranks; preset overrides have explicit scope; a `ONCE` hold stays one cue per fixture and holds its terminal pose to the section end; fly-in/out lit directions and dark returns are frame-proven; flicks settle while dark and resume the current base. Each section's entry window is sized at render from a bound the fuzz shows dominates the transaction pass, so section-entry repositioning fits by construction; the dip is skipped where the predecessor ends where the successor begins, and the plan-dependent failures P2.4c lists still surface at render. The zoom pilot is source/synthetic proven with any real-profile acceptance explicitly pending. Legacy regression and clean-tree `make validate` pass. Owner visual acceptance, including whether the remaining section-entry dips look acceptable, is a separate `PENDING-OWNER` record, not a consequence of a new effect name or passing bytes.

## Decisions on the kickoff open questions

Integrator decisions, 2026-11-14:

1. **Mid-song beat gap:** stays lit as one long beat (P2.0); the trace records the
   longest inter-beat interval so real-audio grids can revisit it.
2. **Rig without a topology:** derive one row from `FixturePosition.position_index` when
   every fixture declares one; otherwise exclude the template (P2.2, P2.4c).
3. **Gate time ceiling:** set from P2.4a's measurement, with 10 s on the 8-head,
   4-minute synthetic song as the target; reported in evidence, not enforced at run time.
4. **A failing template:** excluded from the offer; the run is refused only when none
   remains (P2.4c).
5. **Edge park pose:** no separate rest pose; P2.0 holds the declared initial pose, then
   the first cue's aim, and the last cue's aim after the final cue.
6. **Dark dip at section entry:** skipped by default where eligible (P2.4a); every other
   entry dips dark, and whether those dips look acceptable is `PENDING-OWNER`.
