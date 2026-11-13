# P2 — Reusable spatial composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Make a small set of expressive physical moving-head families reusable across named aims, odd/missing-head rigs, and independent attribute phases.

**Architecture:** Extend existing `TemplateDoc`, preset resolution and handler registries; all physical output remains `FixtureSegment` with P1's typed trajectory alternative. Resolve named rig references and stable topology before path generation, then use the P1 transaction/encoding passes for visibility, travel and bytes. Numeric transforms remain template-owned; planners select versioned family/preset IDs.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest, existing curve library and JSON template loader; no new runtime dependency.

**Spec:** `changes/2026_11_12_mh_true_up/report.md` §§6.2, 6.4 and 8/P2; P1 interfaces. Baseline source: `9c55c2e72c4bfea30a5ab7ae197579e4feb74485`.

## Global Constraints

- Proposed design and execution checklist only; none of the new APIs below exists yet.
- Requires P1's physical-profile, musical-phase, lock, preposition and frame contracts. P2 family output requires explicit `physical_v2`; legacy templates remain unchanged.
- Pydantic owns schemas; LLMs choose creative intent, deterministic code resolves geometry/timing/DMX. No complete world-space solver or optical catalog is required.
- Reuse `catalog/templates/moving_heads` and the existing collision-safe registry. New template IDs/versions do not silently shadow builtins.
- All data is synthetic until an owner-authorized fixture case is supplied. Hardware/changed-look acceptance remains PENDING-OWNER.
- Task checkpoints/commits belong to the authorized integrator. Finish implementation with independent review and clean-tree `make validate`, not a plan-time claim of passing tests.

## Review Focus

- Missing preset entries must not silently aim a head at center: P2.1 explicitly rejects or uses a named declared fallback.
- Subset regeneration and missing heads must preserve canonical phase ranks: P2.2 tests full-rig versus subset output.
- Rotation, asymmetric ranges and finite events must not trigger implicit normalization/loop closure: P2.3 tests transformed bounds and end state.
- A temporary wheel flick must return to the currently applicable base state, with dark settling both ways: P2.4 tests a base change during the overlay.
- Unsupported optics must be rejected or follow a declared alternative, never treated as interchangeable channels: P2.5 tests capability/range boundaries.

## P2.1 — Named component references and deterministic precedence

**Files:** Create `packages/twinklr/core/config/fixtures/presets.py` and `packages/twinklr/core/sequencer/moving_heads/compile/presets.py` (plural; existing `compile/preset.py` remains the step-patch implementation). Modify `config/fixtures/groups.py`, `sequencer/models/template.py`, `sequencer/moving_heads/compile/preset.py`, `sequencer/moving_heads/compile/template_compiler.py`. Tests: new `tests/unit/sequencer/moving_heads/compile/test_component_presets.py`; extend `templates/test_data_loader.py` and `templates/test_registry.py` under that test tree.

**Interfaces:** `RigPresetLibrary(positions: dict[str,PositionPreset], attributes: dict[str,AttributePreset])` on `FixtureGroup.presets`, empty by default. `PositionPreset` maps fixture IDs to `PoseDegrees(pan_deg,tilt_deg)` without modulo wrapping. `AttributePreset` maps fixture IDs to semantic/normalized channel states, validated through P1 capabilities. `ComponentRefs(position_id: str | None, attribute_preset_ids: tuple[str,...])` is an optional `TemplateStep.component_refs`; `resolve_component_refs(step: TemplateStep, fixture_ids: tuple[str,...], presets: RigPresetLibrary) -> dict[str,ResolvedStepComponents]` returns explicit per-fixture physical settings and provenance. Unknown IDs or missing fixtures fail unless the preset declares a specific fallback preset ID; reject fallback cycles. This is rig data, not a global target database.

Precedence: resolve referenced component values; apply physical values explicitly present on the template step; apply existing named step-preset patches; apply typed section overrides only for the attribute they own. Conflicting attribute preset IDs at the same precedence fail rather than last-write wins. Record each overridden source; existing `TemplatePreset.defaults` remain legacy metadata unless a new typed physical field explicitly owns their meaning.

- [ ] Write `test_missing_fixture_preset_is_not_centered`, `test_preset_patch_overrides_reference_only_for_owned_axis`, `test_fallback_cycle_rejected`, and `test_preset_change_only_changes_dependent_segments`; compare affected segments and untouched segment fingerprints.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_component_presets.py -q`; expect missing-interface failures.
- [ ] Implement references and precedence through existing registry/patching. Do not copy old preset values into generated documents: keep explicit versioned references and content hashes.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/templates/test_data_loader.py tests/unit/sequencer/moving_heads/templates/test_registry.py -q`; record a review checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): resolve named position and attribute components`; do not combine unresolved task failures with the next task.

## P2.2 — Stable topology and separate phase domains

**Files:** Create `packages/twinklr/core/sequencer/models/moving_heads/topology.py`; modify `config/fixtures/groups.py`, `sequencer/models/template.py`, `moving_heads/fixture_builder.py`, `moving_heads/compile/phase_offset.py`, `moving_heads/compile/template_compiler.py`. Tests: new `tests/unit/sequencer/moving_heads/compile/test_topology_phase.py`.

**Interfaces:** `FixtureTopology(members: tuple[TopologyMember,...])`, with `TopologyMember(fixture_id,row,column,ordinal)` and unique identity/ordinal, describes a canonical full rig. `PhaseDistribution(domains: tuple[ChannelName,...], block_size:int=1, group_count:int|None=None, wings:Literal[1,2]=1, spread_cycles:float=0, direction:Literal["forward","reverse"]="forward")`. `resolve_distribution(topology: FixtureTopology, specs: Sequence[PhaseDistribution], selected_fixture_ids: tuple[str,...]) -> dict[str,ResolvedFixturePhase]` returns `phase_by_channel` and mirror direction. Reject overlapping domain ownership between distribution specs.

Define rank from canonical `(row,column,ordinal,fixture_id)` ordering, before filtering disabled/missing/selected heads. Wings fold the whole ordered rig, including multi-row rigs; per-row independent wings are deferred. For two mirrored wings, folded rank is `min(i,n-1-i)` and pan-displacement sign is left −1, right +1; the odd center has sign0 and phase rank at the fold. Blocks use `b=floor(folded_rank/block_size)` (unfolded rank for one wing). Let `B=max(b)+1` over the full rig, `S=min(B,group_count)` if a group count is specified, otherwise `S=B`; slot is `b % group_count` or `b` respectively. `block_size`/`group_count` are positive integers. Phase is `spread_cycles * slot/(S-1)` for `S>1`, otherwise0. Reverse uses `S-1-slot` before normalization. Thus spread specifies the first-to-last span, including endpoints; a full-cycle span intentionally repeats endpoint phase. Empty canonical slots persist, so removing a head leaves a deliberate hole instead of rephasing neighbors. New topology consumers use actual identity/rank; they must not translate back through the old finite role-name list. Legacy phase continues unchanged.

Exact example: five ordered heads, wings2, block_size2, group_count2, spread0.5 produces folded ranks `[0,1,2,1,0]`, slots `[0,0,1,0,0]`, phases `[0,0,0.5,0,0]`, signs `[-1,-1,0,1,1]`; reverse phases are `[0.5,0.5,0,0.5,0.5]`. Removing the center preserves every remaining value.

- [ ] Write tests for 1/2/3/4/6 heads, an odd center, a missing middle head, two rows, blocks and interleaved phase groups. For subset IDs assert `subset[id] == full[id]`. Give dimmer a half-cycle spread with pan/tilt zero and assert only dimmer shifts.
- [ ] Assert the exact five-head folded/block/group phase and sign arrays above, including reverse and removed-center output; this pins the denominator and endpoint behavior.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_topology_phase.py -q`; expect failures.
- [ ] Implement deterministic ranks/domain selection; preserve canonical order in trace and use it during P4 regeneration.
- [ ] Rerun plus `uv run pytest tests/unit/sequencer/moving_heads/compile/test_phase_offset.py -q`; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): distribute independent phases over stable rig topology`; do not combine unresolved task failures with the next task.

## P2.3 — Relative transforms and finite motion

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/handlers/movement/physical.py`; modify `sequencer/models/template.py`, `moving_heads/compile/physical.py`, `moving_heads/compile/scheduler.py`, `moving_heads/templates/library.py`, `moving_heads/handlers/defaults.py`. Test new `tests/unit/sequencer/moving_heads/handlers/test_physical_paths.py`.

**Interfaces:** Add template-owned `PathTransform(rotation_deg, reverse, phase_cycles)` and `PhysicalEvent(repetitions:int, terminal:Literal["hold","return_dark"])` to the physical movement definition. Keep `pan_extent_deg`/`tilt_extent_deg` on P1's `PhysicalMovementSpec` as their sole owner; do not duplicate extents inside the transform. Extend its shape vocabulary with `circle`, `lissajous`, and `sweep`; `circle`/`lissajous` are periodic, and `sweep` declares periodic or finite return behavior. Lissajous axis frequency ratios are positive template-owned integers, default1:2. `evaluate_physical_path(spec: PhysicalMovementSpec, *, pose: PoseDegrees, phase: float) -> PoseDegrees` returns unwrapped degrees. Convert existing [0,1] kernel values to centered `[-1,1]` using `2*x-1`, rotate XY, scale each axis by its degree extent, then add resolved base aim. For these centered kernels an extent is maximum signed displacement, not full width. The resolved pose replaces P1 start angles when a named position is used; never add both as separate offsets. Do not use legacy `center_curve` rescaling or force the endpoint closed. Explicit physical extents are checked by P1 limits/rate validation.

A new explicit `RepeatMode.ONCE` permits a finite template to run once at nominal musical rate, then hold its declared terminal state or finish a validated dark return; it never compresses into a short section. A truncated finite event that cannot reach its requested terminal state fails unless its template explicitly permits a dark cutoff. This differs from existing periodic remainder handling and needs an explicit schema value, not an overloaded JOINER name. Periodic relative orbits continue using exact unwrapped BeatGrid phase.

- [ ] Write `test_rotated_orbit_uses_named_aim`, `test_reverse_changes_travel_not_visibility_phase`, `test_finite_snap_does_not_wrap`, `test_short_finite_event_rejects_unreachable_terminal`; use asymmetric pan/tilt extents and compare a 90° normalized-path rotation before scaling.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/handlers/test_physical_paths.py -q`; require failure.
- [ ] Implement the handler and finite scheduling branch; update `validate_repeat_contract` to validate a finite event's declared span without demanding a second cycle. Preserve legacy kernels and repeat behavior.
- [ ] Rerun with existing scheduler tests; checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add relative physical paths and finite events`; do not combine unresolved task failures with the next task.

## P2.4 — First expressive families and masked temporary states

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/compile/visibility.py`; modify `sequencer/models/template.py`, `moving_heads/compile/physical.py`, `moving_heads/compile/intent_resolution.py`. Create JSON documents in `catalog/templates/moving_heads/physical_v2/`: `fly_out_cascade.json`, `fly_in_cascade.json`, `target_orbit.json`, `mirror_wings.json`, `finite_snap_hold.json`, `masked_wheel_flick.json`. Test new `tests/integration/test_mh_physical_families.py` and `tests/unit/sequencer/moving_heads/compile/test_visibility.py`.

**Interfaces:** `VisibilityEnvelope(visible_phase_start,visible_phase_end,attack_beats,release_beats)` is template-owned; `apply_visibility(segments: Sequence[FixtureSegment], envelope: VisibilityEnvelope, *, grid: BeatGrid) -> tuple[FixtureSegment,...]`. Define `AttributeOverlay(start_ms,end_ms,channel,state,release:Literal["resume_base"])` for the flick; retain base trajectory separately during composition, evaluate it at release time, and pass both entry/exit wheel changes to P1 preposition masking. Numeric zero in the wheel is never used as a blackout proxy. Overlapping same-priority overlays fail; different channel overlays may compose if physical constraints permit.

Fly-out lights center-to-edge travel and returns dark; fly-in lights edge-to-center travel and returns dark. Both share the same path/visibility phase origin per fixture, including phase offsets. Finite snap/hold uses achievable travel and an explicit hold; it cannot be instantaneous solely because the name says snap. Families are only registered after P1 capability/limit checks; existing similarly named legacy templates remain separate versions.

- [ ] Write frame tests proving lit-direction signs differ, every return-travel frame is dark, each fixture's first lit frame is settled, and release restores a base color changed during the overlay (not a stale entry color). Test a mask/lock collision fails before emission and an insufficient dark return window fails.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_visibility.py tests/integration/test_mh_physical_families.py -q`; expect failures.
- [ ] Implement the visibility/overlay composition and six data documents through the existing loader. Reuse P1 `plan_prepositions` and `encode_fixture_frames`; do not implement a second dark-motion algorithm.
- [ ] Rerun; compare all encoded frames under repeated runs and full/subset output. Checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add directional cascades and masked temporary attributes`; do not combine unresolved task failures with the next task.

## P2.5 — Bounded optical pilot and capability-aware admission

**Files:** Modify `packages/twinklr/core/config/fixtures/capabilities.py`, `sequencer/models/enum.py`, `sequencer/models/template.py`, `moving_heads/export/frame_encoder.py`; add `catalog/templates/moving_heads/physical_v2/zoom_wave.json` and synthetic profile `tests/fixtures/moving_heads/physical_v2/zoom_profile.json`. Test new `tests/unit/sequencer/moving_heads/export/test_optical_axis.py`.

**Interfaces:** Extend P1 continuous-axis unit support with `degree` for zoom beam angle and add `ChannelName.ZOOM` only for a declared zoom capability. Declare minimum/maximum beam angle, `dmx_min`/`dmx_max`, inversion, resolution and known settle. Encoding is `dmx_min + round-half-up(normalized * (dmx_max-dmx_min))`; inversion reflects around `dmx_min+dmx_max`. Pan/tilt retain P1's full-resolution domain. No automatic “iris equals zoom” or continuous interpolation through gobo-rotation modes. `zoom_wave` uses existing phase domains on one supported continuous optical axis; categorical template selection remains the planner interface.

- [ ] Write a synthetic 10°–40° zoom profile over bytes 20–220; assert endpoint encoding, monotonic mapping/inversion, out-of-range rejection, and unsupported-fixture rejection. A template may declare `omit_optional_zoom` only as an explicit alternative recorded in trace.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/export/test_optical_axis.py -q`; expect failure.
- [ ] Implement only this axis through existing physical encoding, with synthetic provenance clearly recorded. Broader focus/iris/prism/rotation support requires a concrete fixture case and a separate extension; it is not a prerequisite for these first families.
- [ ] Rerun; prepare the exact pilot profile/template for future authorized fixture validation. Synthetic proof is not a real-profile acceptance. Checkpoint.

- [ ] After independent task review, integrator commits `feat(mh): add a bounded capability-aware zoom pilot`; do not combine unresolved task failures with the next task.

## Compatibility, cache/data migration and rollback

P2 adds typed optional fields and an explicit finite repeat enum; keep existing `TemplateDoc` parsing and builtins valid. Reject physical-only fields under legacy render policy. Content-hash the resolved preset values, full topology, distribution, path, envelope and template version as dependencies of P0/P1 render identity; editing a preset invalidates only dependent render output, not unrelated planning. A planner exposed to a changed template catalog must include the changed catalog identity in its context/cache key; existing `agents/sequencer/moving_heads/orchestrator.py:get_cache_key` already hashes available IDs/descriptions, so extend only when additional exposed family metadata is introduced, with a targeted `tests/unit/agents/sequencer/moving_heads/test_orchestrator.py` cache test. Do not rewrite checkpoints or silently replace same-ID builtin documents; new physical families have distinct IDs and provenance. Rollback selects legacy policy/previous template versions and ignores the opt-in physical catalog; no accepted artifact is overwritten.

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; see the
[shared rule](README.md#documentation-registry-and-test-surfaces). Recheck at P2 kickoff.

- **Catalog admission is unspecified above and must be settled in P2.4 before any
  document is added.** Three facts at `f067a56`: the render pipeline and the planner
  load Python builtins only and never call the data loader;
  `discover_template_documents` walks `catalog/templates/moving_heads` recursively, so
  `twinklr template-validate --template-dir catalog/templates/moving_heads` would pick
  up a new `physical_v2/` subdirectory; and the existing three documents there are
  required to stay model-equal and render-identical to their Python builtins. P2.4
  therefore names the one loader call that admits `physical_v2/` documents, makes it
  run only under `physical_v2`, and adds tests that the legacy planner context, the
  deterministic selector's candidate set and the 37-entry registry assertions are
  unchanged when the physical catalog exists on disk.
  `test_data_loader.py::test_tracked_data_proofs_load_alongside_all_python_builtins_only_with_override`
  loads that directory recursively and asserts exactly three IDs, so it fails the
  moment a `physical_v2/` document is added there; P2.4 either places the physical
  catalog outside that root or changes that test deliberately. Update
  `catalog/templates/moving_heads/README.md` to describe the subdirectory.
- **Config inventory.** Register every new field with collecting evidence in the task
  that adds it: P2.1 `FixtureGroup.presets` and `TemplateStep.component_refs`; P2.2 the
  topology on the fixture group and `PhaseDistribution`; P2.3 `PathTransform`,
  `PhysicalEvent` and the new repeat mode; P2.4 `VisibilityEnvelope` and the overlay;
  P2.5 the zoom capability. The physical-only evidence approach chosen in P1.1 applies.
- **Documents.** `docs/user-guide.md`: the data-form template section and the
  fixture-config section for presets and topology. `docs/overview.md`: the "37 Python
  builtins" sentences stay true because the new families are data documents; add the
  physical families as a separate statement rather than changing that count.

## Phase exit

Six core families compile deterministically on the synthetic rig matrix; independent phase domains work; missing heads preserve canonical ranks; preset overrides have explicit scope; finite events retain meaningful terminal states; fly-in/out lit directions and dark returns are frame-proven; flicks settle while dark and resume the current base. The zoom pilot is source/synthetic proven with any real-profile acceptance explicitly pending. Legacy regression and clean-tree `make validate` pass. Owner visual acceptance is a separate record, not a consequence of a new effect name or passing bytes.
