# P1 — Reliable fixture behavior Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Add opt-in physical motion, exact musical phase, true coarse/fine DMX encoding, and feasible dark pre-positioning without changing legacy output.

**Architecture:** Extend `FixtureSegment`/`ChannelValue` with an explicitly typed physical-value alternative; retain the existing legacy channel representation and shared xLights emitter. Physical templates resolve into the same segment container, a multi-channel transaction pass establishes darkness and arrival feasibility, and a frame encoder converts resolved physical state into DMX bytes. No normalized legacy curve is implicitly reinterpreted as an angle.

**Tech Stack:** Python 3.13, uv, Pydantic V2, pytest; existing BeatGrid, template registry, xLights emission core. No new runtime dependency.

**Spec:** `changes/2026_11_12_mh_true_up/report.md` §§6.1–6.3, 8/P1; P0 behavior contract. Source inspected at `9c55c2e72c4bfea30a5ab7ae197579e4feb74485`.

## Global Constraints

- Planning only now; all APIs named below are **proposed**, not existing features.
- P0 owns `MHRenderPolicy` in `config/models.py`, `JobConfig.moving_heads`, modes `legacy_v1` and `physical_v2`, default `legacy_v1`. Schema evolution is independent of this render policy: `JobConfig.schema_version` accepts `3.0` and `3.1`, defaults to `3.0`, and `physical_v2` requires explicit `3.1`. Old readers reject `3.1` instead of silently ignoring the policy.
- LLMs select typed creative intent; fixture/template configuration owns numeric mapping, timing and physical values.
- Existing accepted output and legacy regression records remain intact. No live provider, owner-local data or xLights/hardware mutation is authorized by this plan.
- New physical transitions fail closed on unknown or infeasible motion by default. A declared `preserve_aim` or `drop_accent` alternative is permitted only when its intended behavior is part of the selected template/policy.
- Every task's commit/checkpoint is integrator-owned, after execution authorization. Before completion, commit the owned changes and run `make validate` from that clean owned tree; disclose any skipped or failing gate. The commands below are planned, not executed.

## Review Focus

- A coarse-byte carry must not create a spurious 16-bit jump; P1.3 tests frame reconstruction around 255/256 and inversion.
- A channel offset above 48 must fail before output; P1.1 tests 17, 48 and 49 against the actual DMX backend.
- Unknown initial state or unknown motor speed must never be reported as feasible; P1.5 tests both and a visible cue at time zero.
- Quantization and wheel settling must not illuminate an in-flight move; P1.5/P1.6 test transactions at frame boundaries and locked output.
- Variable tempo and finite events must not silently loop on average BPM; P1.2 tests nonuniform beats and explicit terminal state.

## Design decisions and current seams

`channels/state.py` currently constrains static and clamp values to 0–255; `FixtureSegment.t1_ms` documents legacy inclusive semantics. Preserve those fields/semantics. Add `ChannelValue.physical` with exactly-one validation across `static_dmx`, `curve`, and `physical`; prohibit `value_points`, base/amplitude, or nondefault legacy clamps when physical is set. New physical trajectories use absolute `t_ms`, explicit units and half-open **sampling** intervals. Existing readers only receive legacy values; v2 dispatch must occur before the old blender/exporter.

The first correct transport uses frame-aligned **constant DMX effects**, run-length coalesced only when the complete bytes are identical. This is more verbose than value curves, but avoids independently interpolating coarse/fine bytes across carries. Compression/native effects can follow only after frame equivalence is proved; P1 does not change the shared 20 ms grid. `EmissionSession` already quantizes effect endpoints and rejects collisions; v2 emits already-aligned intervals so that it cannot shift physical transactions a second time.

Pinned xLights [`DMXEffect.h`](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/src-core/effects/DMXEffect.h) limits DMX effects to **48 model-relative channels**. Its [`DMXEffect.cpp`](https://github.com/xLightsSequencer/xLights/blob/fe78fdddb7524cea71ee4c2ac4c22e20c16d478f/src-core/effects/DMXEffect.cpp) defaults unspecified channel values to zero. Therefore a v2 profile must declare the complete footprint/default byte state, including unused channels, and reject footprint or used offsets above 48. Channel 17 is supported; universe addressing is not the same concept as model-relative offsets. P1 supports single-color DMX fixture models with validated channel count; do not silently send RGB-node model layouts through that mapping.

## File ownership and interfaces

The implementing workstream owns the files listed in these tasks; shared changes to `config/models.py`, `models/template.py`, `models/context.py`, `pipeline.py`, and export adapters are serialized by the integrator. No parallel edit ownership is implied.

### P1.1 — Capability and typed physical-value contracts

**Files:** Create `packages/twinklr/core/config/fixtures/capabilities.py` and `packages/twinklr/core/sequencer/models/moving_heads/physical.py`. Modify `config/models.py`, `config/fixtures/instances.py`, `sequencer/moving_heads/channels/state.py`, `sequencer/models/context.py`, `sequencer/moving_heads/fixture_builder.py`. Test `tests/unit/config/test_mh_capabilities.py` and `tests/unit/sequencer/moving_heads/test_physical_values.py` (new).

**Interfaces:** Define frozen Pydantic `FixtureCapabilities(schema_version="1", profile_id, provenance, footprint, defaults, axes, discrete, visibility)`; `AxisCapability` contains unit, ordered physical min/max, coarse/fine offsets, inversion, optional positive speed bound, and nonnegative configured latency/settle. `DiscreteCapability` owns one channel offset and maps semantic states to validated DMX ranges plus one explicit selected byte per state, default/closed/open keys and optional settle times. A range alone never chooses a byte implicitly. Provenance distinguishes `synthetic`, `manufacturer`, and `measured`; no unknown speed becomes a numeric default. Reject duplicate offset ownership and incomplete defaults for 1..footprint. Add `FixtureConfig.physical_profile: FixtureCapabilities | None = None`; old ignored `capabilities`/`movement_speed` keys remain retired and never acquire new meaning. Profile speed is an explicitly configured conservative travel estimate, not a physical certification; distinguish it from a manufacturer maximum-rate claim.

Physical min/max describe the calibrated mapping endpoints, in fixture-local unwrapped coordinates. Separate `allowed_min`/`allowed_max` restrict operation within that mapping; narrowing the allowed window must **not** rescale degrees to a new DMX range. Initial pan/tilt uses DMX word endpoints 0..255 or 0..65535; P2's bounded zoom pilot adds explicitly declared word subranges. Profile visibility declares whether dimmer zero extinguishes output and which semantic shutter states extinguish output, with `close_latency_ms` and `open_latency_ms` as nullable nonnegative values. Unknown extinction/settle latency cannot establish a guaranteed dark interval; synthetic zero latency must be explicit. Imported defaults never imply these properties.

Define `ContinuousTrajectory(unit: Literal["degree", "normalized"], points: tuple[PhysicalPoint,...], interpolation: Literal["linear","hold"])`, where `PhysicalPoint(t_ms: int, value: float)` is finite. `DiscreteTrajectory(events: tuple[DiscretePoint,...])` uses `DiscretePoint(t_ms, state: str)`. Strictly increasing times; semantic values must be profile-supported. `InitialFixtureState` specifies unwrapped pan/tilt degrees, all authored attribute states at time zero, and explicit settled/visibility evidence. It is a run input, not a manufacturer profile's claim that a fixture is currently at home. Define this type in `config/fixtures/capabilities.py` and expose `MHRenderPolicy.initial_states: dict[str, InitialFixtureState]` with an empty default. A missing fixture key means unknown. Reusable `FixtureCapabilities` carries no current pose; explicit run state is included in render identity. `RenderLock(start_ms: int, end_ms: int, fixture_ids: tuple[str,...], channels: tuple[ChannelName,...])` has exclusive end and can include PAN/TILT/DIMMER/SHUTTER/COLOR/GOBO. Define `PhysicalChannelError` with fixture/channel/time/reason.

- [ ] Write `test_physical_values_cannot_mix_with_legacy_curve`, `test_duplicate_offsets_rejected`, `test_backend_offsets_17_and_48_allowed_49_rejected`, `test_missing_default_or_unknown_initial_state_reported`; assert `ChannelValue(..., static_dmx=1, physical=trajectory)` rejects and explicit unknown speed remains `None`.
- [ ] Add `test_allowed_window_does_not_rescale_calibrated_axis` and `test_profile_defaults_do_not_supply_live_initial_state`; the same admitted angle encodes identically before/after narrowing limits.
- [ ] Run `uv run pytest tests/unit/config/test_mh_capabilities.py tests/unit/sequencer/moving_heads/test_physical_values.py -q`; expect missing-interface/behavior failures initially.
- [ ] Implement the contracts, adapter propagation and validators; do not auto-fill physical capabilities from coarse legacy defaults.
- [ ] Rerun the command; require all assertions passing. Record a checkpoint for integrator review.

- [ ] After independent task review, integrator commits `feat(mh): add explicit fixture capabilities and physical channel values`; do not combine unresolved task failures with the next task.

### P1.2 — Physical template resolution and exact musical phase

**Files:** Create `sequencer/moving_heads/compile/physical.py` and `sequencer/timing/musical_phase.py` under `packages/twinklr/core/`. Modify `sequencer/models/template.py`, `sequencer/models/context.py`, `sequencer/moving_heads/compile/step_compiler.py`, `sequencer/moving_heads/compile/template_compiler.py`, `sequencer/moving_heads/pipeline.py`. Test new `tests/unit/timing/test_musical_phase.py` and `tests/unit/sequencer/moving_heads/compile/test_physical.py`.

**Interfaces:** `build_musical_phase_map(grid: BeatGrid, *, boundary_knots: tuple[PhaseKnot,...]=()) -> MusicalPhaseMap` builds an explicit phase domain; `musical_phase_at(phase_map: MusicalPhaseMap, time_ms: int, *, origin_ms: int, period_beats: float) -> float` returns unwrapped cycles by piecewise-linear interpolation, subtracting phase at the origin then dividing by period. `PhaseKnot(time_ms:float, beat_index:float, provenance:Literal['observed','adjacent_interval','explicit'])` and `MusicalPhaseMap(knots:tuple[PhaseKnot,...],duration_ms:float)` are defined in `musical_phase.py`. Observed beat starts have indexes0..n-1. Because BeatGrid stores starts, not a guaranteed terminal sentinel, extend its first/last **adjacent observed interval** to time 0/duration only when each uncovered edge is at most one such interval; mark inferred boundary knots `adjacent_interval`. No average BPM inference occurs. Longer uncovered edges or fewer than two observed beats require explicit boundary knots with provenance, otherwise fail before compiling. Explicit knots cannot overwrite observed beats or make phase nonmonotonic. Only evaluate within `[0,duration_ms]`. Record boundary provenance in render identity/trace; a boundary estimate is not an observed beat.

`PhysicalMovementSpec` is an additive `Movement.physical` field: explicit `start_pan_deg`/`start_tilt_deg`, independent `pan_extent_deg`/`tilt_extent_deg`, `period_beats`, `shape: Literal["hold","sine_pan","sine_tilt","linear"]`, and `mode: Literal["periodic","finite"]`. P1 implements exactly those four kernels: hold keeps the start; sine-pan/tilt add the selected extent times sine of `2*pi*phase_cycles` (the unused-axis extent must be zero); finite linear moves from start to start-plus-extent over one declared period then holds. Reject periodic linear and finite sine variants in P1 rather than inventing reset semantics. P2 expands this validated vocabulary. It is renderer/template-owned, not an LLM numeric control. `compile_physical_step(step: TemplateStep, context: StepCompileContext, *, sample_times_ms: tuple[int,...]) -> FixtureSegment` uses existing step identity and target resolution. Under v2 an unsupported legacy-only step fails with a migration diagnostic; there is no automatic dimensional reinterpretation.

Reach and rate are independently resolved from explicit physical template settings; an optional qualitative override selects a declared template table. Plan intensity controls brightness unless the template explicitly declares a reach/rate mapping. Enforce physical axis bounds by default rejection, not flattening a path against a clamp. Brightness is normalized, shutters/wheels are semantic discrete states; v2 pulses evaluate musical phase, not sample-index parity. Finite paths preserve their terminal value and never close to start automatically. Validate travel rates between consecutive physical trajectory points against the configured conservative speed; nonconstant motion with unknown speed fails in v2. Define `slice_physical_segment(segment: FixtureSegment, start_ms: int, end_ms: int) -> FixtureSegment`: interpolate continuous boundary values, carry the last preceding discrete state, and preserve the original phase origin and provenance; do not restart motion after a slice.

Add template-owned `PhysicalPulseSpec(period_beats:float, duty_cycle:float, phase_cycles:float=0)` with positive period and `0 < duty_cycle <= 1`. Dimmer pulse endpoints are explicit normalized `low`/`high`; shutter pulse endpoints are named `low_state`/`high_state`. Evaluate the high interval when fractional musical phase is in `[0,duty_cycle)`, then pass shutter changes through latency/settle validation. A rate that cannot satisfy those bounds is rejected. This is a deterministic pulse definition, not an authorization for automatic strobe selection.

- [ ] Write tests with beat positions `[0, 500, 1000, 2000]`: phase at 1500 ms is 2.5 beats for period one; phase at the beat marks is exactly integer. Assert a finite fade ends at its final value, independent reach/rate changes do not alter the other, and a legacy normalized circle cannot enter v2 without explicit physical data.
- [ ] Add variable-tempo dimmer/shutter pulse tests with period one beat and duty0.5: high at beat onset, low at exact half-beat; adding intermediate sampling points must not change existing samples. Assert unresolved shutter latency rejects a claimed pulse schedule.
- [ ] Add `BeatGrid.from_tempo(120,1)` full-duration test: phase at 1980 ms is3.96 and at 2000 ms is4 for period1/origin0. A first observed beat at 100 ms with next at 600 ms supplies phase −0.2 at 0 ms relative to origin 100 ms; trace the inferred pickup. Reject a two-second unsupported tail after a 500 ms last interval unless explicit boundary knots are supplied.
- [ ] Run `uv run pytest tests/unit/timing/test_musical_phase.py tests/unit/sequencer/moving_heads/compile/test_physical.py -q`; require discriminating failures.
- [ ] Implement exact phase and the additive physical compile branch; preserve existing v1 handler behavior and output.
- [ ] Rerun those tests and `uv run pytest tests/unit/sequencer/moving_heads/test_movement_intensity.py tests/unit/sequencer/moving_heads/compile/test_scheduler.py -q`; require both new and legacy behavior. Checkpoint for integrator review.

- [ ] After independent task review, integrator commits `feat(mh): compile physical templates against exact musical phase`; do not combine unresolved task failures with the next task.

### P1.3 — Frame-accurate byte encoding

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/export/frame_encoder.py`. Modify `export/dmx_settings_builder.py` and `export/xsq_adapter.py` in the same moving-head directory, plus `packages/twinklr/core/config/models.py` for output budgets. Test new `tests/unit/sequencer/moving_heads/export/test_frame_encoder.py`.

**Interfaces:** Frozen `EncodedFixtureFrame(time_ms: int, fixture_id: str, channels: tuple[tuple[int,int],...])`; `encode_fixture_frames(segments: Sequence[FixtureSegment], capabilities: FixtureCapabilities, *, frame_times_ms: tuple[int,...]) -> tuple[EncodedFixtureFrame,...]`; `DmxSettingsBuilder.build_frame_settings(frame: EncodedFixtureFrame) -> str`. Global sampling uses existing `EFFECT_GRID_MS=20`, at each frame start in `[start,end)`. Quantize intended cue times once using existing nearest-grid/ties-later policy and trace requested/actual times (maximum 10 ms cue displacement). For sequence-tail frames, sample every frame start below source duration and let the final frame interval end at the next grid boundary; do not alter source-exact timing tracks or sequence duration.

Map bounded degrees to `round-half-up(normalized * (65535 if fine else 255))`, apply inversion once to that integer. For a fine-channel axis, coarse=`q >> 8` and fine=`q & 255`; for an 8-bit axis, coarse=`q` with no fine output. Use full unwrapped calibrated physical range, not `Pose`'s modulo normalization or the narrower allowed window. One-byte dimmer quantizes normalized intensity; semantic wheels select declared bytes. Set exported inversion flags to zero for v2. Resolve overlapping same-attribute writes only through an explicit transaction/override; equal-priority conflicts fail. Fill the complete footprint from declared defaults plus resolved states; do not rely on omitted-channel hold. Emit individual fixture effects initially; disable grouping until its full-byte equivalence is proved.

P1 adds `MHRenderPolicy.max_effects=100_000` and `max_xsq_bytes=134_217_728` (128 MiB), both positive configurable limits applying only to physical output. Count coalesced effects and exact serialized UTF-8 bytes before final publication; fail with `output_budget_exceeded`, never decimate frames to fit. These are proposed pilot resource bounds, not measured optimal values. Record actual counts, serialization time and size for P5. Build in a temporary artifact and publish only after the entire sequence validates; do not promise atomicity for subsequent live injection.

- [ ] Write tests reconstructing `255,256,257,65535` from emitted pairs and the inverted complement; assert no intermediate carry glitch. Assert absent authored channels receive declared defaults and undefined defaults fail.
- [ ] Add 8-bit endpoint/midpoint tests (`0,128,255` before inversion), and explicit small effect/byte budgets that reject before final output with no dropped frames. Two identical adjacent states merge; any one-byte change prevents merging.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/export/test_frame_encoder.py -q`; expect failure before implementation.
- [ ] Implement sampling, complete state, byte encoding and RLE constant-effect serialization, retaining the shared emission core. Set a typed error for unsupported model mode or offset >48.
- [ ] Rerun and include `uv run pytest tests/unit/sequencer/moving_heads/export/test_dmx_settings_builder.py tests/unit/sequencer/moving_heads/test_export_core.py -q`; no legacy change. Checkpoint for integrator review.

- [ ] After independent task review, integrator commits `feat(mh): encode complete physical fixture frames without byte carry artifacts`; do not combine unresolved task failures with the next task.

### P1.4 — Discrete semantics and effective channel scope

**Files:** Modify `packages/twinklr/core/sequencer/moving_heads/handlers/wheels.py`, `compile/intent_resolution.py`, and v2 `compile/physical.py`; test new `tests/unit/sequencer/moving_heads/compile/test_physical_discrete.py`.

**Interfaces:** `resolve_discrete_state(capability: DiscreteCapability, state: str) -> int` selects a named state or rejects it; it never interpolates through unselected wheel modes. v2 shutter events use profile values on channels 1–48. Existing legacy 1–16 behavior is retained and diagnosed by P0, not silently broadened for old plans. An absent required capability is an error; any optional alternative must be declared in the selected effect, with a trace naming it.

- [ ] Write `test_shutter_17_uses_profile_closed_value`, `test_wheel_change_never_sweeps_intermediate_modes`, and `test_unknown_state_has_no_open_fallback`; closed may be 64 and open 8, proving numeric zero is not assumed.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_physical_discrete.py -q`; expect failure.
- [ ] Implement semantic resolution; route wheel changes requiring masking/settle into P1.5 instead of the legacy channel blender.
- [ ] Rerun and checkpoint for integrator review.

- [ ] After independent task review, integrator commits `feat(mh): resolve semantic shutter and wheel states`; do not combine unresolved task failures with the next task.

### P1.5 — Feasible extinguish/move/settle/reveal transactions

**Files:** Create `packages/twinklr/core/sequencer/moving_heads/compile/preposition.py`. Modify `compile/transition_planner.py`, `pipeline.py`, and `sequencer/models/moving_heads/physical.py`. Test new `tests/unit/sequencer/moving_heads/compile/test_preposition.py`.

**Interfaces:** `plan_prepositions(segments: Sequence[FixtureSegment], capabilities: Mapping[str, FixtureCapabilities], *, initial_states: Mapping[str, InitialFixtureState], locks: Sequence[RenderLock], frame_ms: int, failure_mode: Literal["error","preserve_aim","drop_accent"]="error") -> PrepositionResult`. Define `PrepositionResult(segments: tuple[FixtureSegment,...], diagnostics: tuple[TransitionDiagnostic,...], dependencies: tuple[TransitionDependency,...])`. `TransitionDependency(source_section_id: str | None, target_section_id: str, fixture_id: str, channels: tuple[ChannelName,...], start_ms: int, end_ms: int)` records the full affected half-open span, including predecessor state and settle/reveal; initial-state dependencies have no source section. This is P4's invalidation boundary, not permission to change locked frames. Result contains replacement segments plus typed `TransitionDiagnostic(fixture_id, cue_ms, status, required_ms, available_ms, reason, provenance)`; an error status aborts emission. Input has already quantized reveal boundaries. Snap lock start outward down and end outward up to frame boundaries; initial frame is at time zero, followed by 20, 40, etc. A logical pan/tilt lock covers both coarse and fine bytes.

This pass schedules repositioning between cues and optical state changes; intentional visible trajectory motion remains visible and is independently rate/limit-constrained. It must not black out an entire orbit merely because pan/tilt changes. Reconstruct previous state; find intervals actually dark under declared dimmer/shutter semantics; reserve only unlocked intervals. Determine legal unwrapped axis travel, use `max(abs(delta_pan)/speed_pan, abs(delta_tilt)/speed_tilt)` plus configured latency/settle (parallel axes); wheel settle runs concurrently only when declared independent. Round required durations upward to whole frames. Close/dim and wait for declared extinction latency before movement, move only while dark, hold final values through settle, then issue reveal. Distinguish the command reveal time from expected optical reveal after open latency; do not claim zero optical timing error when latency is nonzero. Validate sampled path limits and continuous segment endpoints. Unknown speed for a nonzero move, unknown initial pose or optical/settled state, no darkness guarantee, a lock conflict or insufficient time fails by default. A zero-time visible cue succeeds only if declared initial state already meets its pose/settled optical state. No negative-time pre-roll or invented instantaneous travel.

`preserve_aim` retains known settled aim and changes only allowed non-positional attributes; `drop_accent` keeps the cue dark and returns a terminal state for subsequent planning. Both produce visible diagnostics and must be explicitly enabled for that effect. Neither can invent unknown state or bypass a lock. No automatic delay-reveal or reach reduction in P1.

- [ ] Write tests: 90° travel at 90°/s plus 40 ms settle requires 1040 ms; 1020 ms available fails. At 1040 ms, every movement frame is optically dark and reveal is exactly the aligned cue. Include different shutter closed values, simultaneous axis travel, wheel settling, unknown speed, time-zero cue, and a one-frame lock inside travel.
- [ ] Add nonzero close-latency case: 40 ms to extinguish plus the same move/settle requires 1080 ms; moving at the close command fails. With 20 ms open latency, trace optical reveal 20 ms after its command and report that musical mismatch; unknown latency cannot pass as zero.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/compile/test_preposition.py -q`; expect meaningful failures.
- [ ] Implement deterministic transaction placement and state propagation. Legacy transitions remain on their existing path; never feed physical channels to `ChannelBlender`.
- [ ] Rerun; require explicit fallback tests and no false-feasible result. Checkpoint for integrator review.

- [ ] After independent task review, integrator commits `feat(mh): schedule feasible dark reposition transactions`; do not combine unresolved task failures with the next task.

### P1.6 — Pipeline integration, identity and rendered evidence

**Files:** Modify `packages/twinklr/core/agents/sequencer/moving_heads/rendering_stage.py`, `sequencer/moving_heads/pipeline.py`, `formats/xlights/sequence/trace.py`, `sequencer/moving_heads/delivery.py`. Create `tests/integration/test_mh_physical_pipeline.py` and `tests/fixtures/moving_heads/physical_v2/p1_linear_reveal.json`; extend `tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py`. Use P0's in-memory synthetic case builder; do not add owner profiles.

The test template uses P1's finite linear kernel, a 90° pan delta over two beats at 120 BPM, explicit dimmer/shutter endpoints and 40 ms settle; synthetic initial state is known and dark. It is loaded by the existing data loader for integration tests, not auto-admitted to the production catalog. Thus P1 can compile and deliver a physical sequence before P2's expressive families exist.

**Interfaces:** Render trace records policy, physical/template/profile content hashes, initial state, ordered full fixture identities, BeatGrid hash, encoder version, frame grid, requested/actual cue timing and transaction diagnostics. Rendering is currently executed directly by `MovingHeadRenderingStage`; do not invent a render cache. Persist the identity alongside artifacts and require any future reuse to match it. Planner cache changes only if its actual schema/context changes; fixture calibration-only changes should not incur a provider request.

- [ ] Write a synthetic variable-tempo, channel-17 shutter, 16-bit two-head sequence; assert decoded emitted frames equal encoded frames, default/full fixture state is complete, no locked frame changes, and failure produces no partial deliverable. Change only calibration and assert render identity changes while plan identity remains unchanged.
- [ ] Run `uv run pytest tests/integration/test_mh_physical_pipeline.py tests/unit/agents/sequencer/moving_heads/test_rendering_stage.py -q`; expect failure before wiring.
- [ ] Wire physical dispatch through existing stage/delivery/trace, preserve stable full-head ordering during subset output, and add atomic fail-before-write behavior for physical errors.
- [ ] Rerun the narrow checks; after the reviewed commit below, integrator runs the clean-tree `make validate` gate. Prepare an expendable-show test request with exact synthetic profiles and expected frames; owner-authorized xLights render must reconstruct carries and channel-17 behavior before claiming transport acceptance. Physical arrival/settle and changed-look acceptance remain PENDING-OWNER.

- [ ] After independent task review, integrator commits `feat(mh): integrate opt-in physical rendering and evidence identity`; do not combine unresolved task failures with the next task.

## Compatibility, migration and rollback

Legacy input defaults to `legacy_v1` and retains its old serialization/output. Physical input requires explicit profiles and physical template fields; provide diagnostics and a reviewed migration document, not an auto-converter from normalized DMX. New optional fields change generated schemas only where those models are exposed; preserve old version parsing and test explicit rejection of v2-only payload under legacy policy. Roll back by selecting `legacy_v1` and the previous templates/checkpoint; refuse physical-only templates there. Retain physical artifacts under their identity for evidence rather than overwriting the accepted baseline.

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; see the
[shared rule](README.md#documentation-registry-and-test-surfaces). Recheck at P1 kickoff.

- **Config inventory.** Each task registers the fields it adds, with a collecting
  evidence test: P1.1 everything under `FixtureConfig.physical_profile` and
  `job.moving_heads.initial_states`; P1.2 `Movement.physical` and the pulse spec under
  the template root; P1.3 `job.moving_heads.max_effects` and `max_xsq_bytes`.
  `FixtureCapabilities` is a deep model and every nested field is its own inventory
  path, so P1.1's registry work is sized by that model, not by one line.
- **Physical-only fixture and template fields.** The registry's default evidence for
  `fixture.*` and `template.*` effect records is a parameterized test that requires the
  field to change shipped legacy output. Physical-profile and physical-movement fields
  do not, by design. P1.1 decides and records how these paths are evidenced: listed in
  `PROTECTED_EXACT_EFFECT_PATHS` with their own physical-path test nodes, or covered
  by an equivalent physical discriminator.
- **P0's rejection test.** P1.6 replaces P0-T1's unconditional
  `UnsupportedRenderModeError` with real dispatch. Update
  `test_unimplemented_physical_mode_is_rejected` deliberately to the new behavior
  (physical mode without the required profiles fails with diagnostics) and repoint the
  `job.moving_heads.mode` registry record in the same commit.
- **Test-template isolation (P1.6).** The pipeline resolves templates through the
  process-wide `REGISTRY`, `DeterministicSelector` reads every entry in it, and several
  tests assert it holds exactly 37. The fixture that loads `p1_linear_reveal.json`
  must remove it again (or the test must run against an isolated registry), and a test
  asserts the shared registry is back to 37 afterward.
- **Documents.** `docs/user-guide.md`: job-config rows for the new `moving_heads`
  fields and a `physical_profile` description in the fixture-config section.
  `docs/overview.md`: its moving-head support paragraph describes the legacy channel
  set only and does not mention the legacy 1–16 shutter-intent ceiling. Add the opt-in
  physical path and its 1–48 model-relative range there, keeping verbatim the two
  sentences `test_documented_channel_scope.py` pins.

## Phase exit

All task tests and `make validate` pass; 16-bit frames reconstruct correctly across carries; supported offsets are 1–48; v2 limits/discrete values/phase/initial state work as declared; insufficient or unknown travel never reports feasible; optical darkness covers travel and settle; legacy regression output is unchanged. Source/offline proof and authorized xLights proof are recorded separately. Hardware accuracy and aesthetic acceptance remain pending until observed, not inferred from the profile's provenance.
