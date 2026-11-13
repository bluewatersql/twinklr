# P4 Constrained Refinement and Selective Interoperability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no execution.

**Goal:** Preserve approved fixture/attribute intervals during revision, show exact output differences, and evaluate narrowly scoped interoperability without weakening DMX output correctness.

**Architecture:** Store an immutable baseline of existing `FixtureSegment` output and canonical encoded frames, build a dependency-aware offline patch, validate locks, and only then pass a complete section replacement set through the existing shared emitter/injection workflow. Keep GDTF import and native Moving Head emission as opt-in adapters; BlenderDMX is a bounded optional experiment.

**Tech Stack:** Python 3.13, Pydantic V2, existing frame encoder/xLights emitter and preview utilities, standard-library ZIP/XML parsing, pytest/uv. No new mandatory dependency.

**Spec:** `../report.md`, sections 6.2–6.3 and Phase P4; P1 physical/frame/preposition contracts and P2 reusable presets. All interfaces below are proposed additions unless identified as existing.

## Global Constraints

- `JobConfig.moving_heads.mode='legacy_v1'` stays default. Physical V2 jobs explicitly use `JobConfig.schema_version='3.1'`; old jobs remain 3.0. New fixture data lives at `FixtureConfig.physical_profile`, never the retired `capabilities` key.
- Preserve `FixtureSegment`/`ChannelValue` as the IR. Reuse P1 `RenderLock`, `InitialFixtureState`, `EncodedFixtureFrame`, `slice_physical_segment` and `plan_prepositions`.
- No live xLights mutation or owner data is authorized by this plan alone. Tests use synthetic data and fake clients; later live checks require a recorded owner authorization and scratch sequence/show.
- Existing xLights automation is **not transactional**. Do not promise rollback, atomic application, or safe automatic replay after ambiguous POST failure.
- P4 requires P1/P2 only and can run before P3. Baseline serialization and offline preparation do not import P3 models or its dispatcher.
- Core refinement can close independently of optional importer/backend experiments. Their decisions and evidence must still be recorded, including NO-GO results.

## Review Focus

- Attribute lock includes coarse and fine bytes, not just visible coarse movement (T1/T2).
- A revised cue changes a preceding dark move or subsequent arrival (T2).
- Live effects diverged since the user reviewed a diff (T3).
- Imported channel functions overlap or depend on an unsupported mode master (T5).
- Native backend silently approximates an unsupported trajectory or fixture map (T6).

## Existing implementation seams

`LiveInjectionWorkflow.inject(effects, *, dry_run=False, replace_sections=None, raise_on_partial=True)` preflights ownership and collisions, calculates exact deletes/adds and updates an atomic **local manifest**. The upstream changes occur sequentially. `regenerate_section` accepts exactly one section; `LiveEffect.signature` includes canonical settings/palette, target/layer and interval. Existing CLI regeneration runs a selected-section planning input with a nonce and then calls this one-section API. It does not preserve arbitrary channel locks or calculate neighboring transition dependencies.

`live_effects_from_segments` uses `XsqAdapter.convert` and emitter traces; new workflow output must continue through that seam. `FrameSampler.sample`, `compose_contact_sheets` and `XLightsAutomationClient.render_preview` already exist. The trace sidecar is `twinklr-xsq-trace.v2`; add a separate refinement report rather than silently changing its schema.

### Proposed contracts and decisions

Create `packages/twinklr/core/sequencer/moving_heads/refinement/models.py`:

- `RenderBaseline(schema_version='mh-baseline.v1', plan_contract_id:str, plan_snapshot:dict[str,JsonValue], segments:tuple[FixtureSegment,...], frames:tuple[EncodedFixtureFrame,...], initial_states:dict[str,InitialFixtureState], dependency_records:tuple[TransitionDependency,...], input_hashes:dict[str,str])`: store canonical plan JSON plus its explicit contract ID as provenance. Existing unversioned plans use `mh-plan.unversioned`; future V3 snapshots use `mh-plan.v3`. Baseline read/write and offline byte-lock preparation preserve this snapshot without interpreting it; planning or rerendering validates it through the dispatcher available in that installed version and rejects unsupported contracts. No P3 import is required. Hashes cover rig/profile, targets, BeatGrid, template documents, render policy and encoder version. Store baseline under the run artifact directory, never overwrite a user sequence.
- Reuse P1 `RenderLock(start_ms,end_ms,fixture_ids,channels)`, half-open. Normalize intervals outward to frame boundaries (samples 0,20,40... at default 20ms cadence); reject unknown fixture/channel and empty/inverted intervals. A PAN lock protects its entire encoded coarse/fine pair. An empty lock collection means no added locks; an empty fixture/channel list is invalid, not a wildcard.
- `RefinementRequest(section_ids:tuple[str,...], locks:tuple[RenderLock,...], allow_dependency_expansion:bool=False)`. No autonomous expansion by default. Locks always win over expansion.
- `PreparedRefinement(schema_version='mh-refinement.v1', baseline_hash, requested_sections, affected_sections, replacement_segments, desired_live_effects, frame_deltas, dependencies, diagnostics, payload_hash)`. `FrameDelta` records fixture/time/channel offset/old/new byte and semantic attribute. Diagnostics distinguish preserved bytes, re-encoded-but-equal data and changed output.
- `prepare_refinement(baseline:RenderBaseline, candidate_segments:Sequence[FixtureSegment], request:RefinementRequest, *, capabilities:Mapping[str,FixtureCapabilities], frame_ms:int) -> PreparedRefinement` is pure offline logic. It returns no network actions.

Candidate compilation uses P2 templates and P1 physical trajectories. Split with `slice_physical_segment` so cropping evaluates original phase/curve boundaries; never renormalize a cropped circle to a fresh cycle. Merge locked attribute trajectories from baseline, recompute prepositions with locks and explicit initial states, then encode complete footprints. Compare every locked mapped byte at every frame; fail on any difference. Whole-fixture/full-effect locks additionally preserve original `LiveEffect.signature` when effect topology permits direct retention; attribute locks guarantee semantic output bytes, not identical XML settings.

Dependency closure follows P1 `TransitionDependency(source_section_id,target_section_id,fixture_id,channels,start_ms,end_ms)` until no affected boundary state changes. Include both incoming and outgoing dependencies. If closure leaves requested sections and expansion is false, raise a diagnostic listing exact additional sections/intervals. If approved expansion is true, recompute only those dependencies while retaining unrelated baseline channels. If no legal feasible result respects locks, fail; do not weaken the lock, shorten visibility, or silently switch fallback.

Cache/diff identity includes baseline, request, capabilities, requested intent, affected neighbor states and all render inputs. A change to frame cadence/profile invalidates refinement baseline; require a full rerender/new baseline rather than interpreting old locks against different bytes.

Physical output isolation is an additional requirement: current reserved-layer collision checks do not inspect every layer or overlapping model/group. An unowned dimmer effect on another layer can defeat a dark move despite an unchanged Twinklr layer. The first physical apply path therefore supports only an explicitly isolated scratch/owned sequence with a verified patch and full effect inventory. Reject overlapping external effects on any contributing fixture/group layer or channel-overlapping model. If current API/layout evidence cannot enumerate contributing layers, groups and channel mappings completely, report live physical application `unsupported` and retain offline `.xsq` delivery; do not infer isolation from layer 99 or a saved manifest. This restriction applies to the new physical apply wrapper, leaving legacy injection semantics unchanged.

## File ownership

P4 owner creates `packages/twinklr/core/sequencer/moving_heads/refinement/{models.py,prepare.py,baseline.py,__init__.py}`, `packages/twinklr/core/reporting/evaluation/refinement.py`, `packages/twinklr/core/config/fixtures/importers/{gdtf.py,__init__.py}` and optional `packages/twinklr/core/sequencer/moving_heads/export/native_moving_head.py`. Integrator alone changes CLI `main.py`, `api/xlights/injection.py`, shared config, delivery and P1 interfaces. P4 stores plan snapshots without taking ownership of plan models; importer consumes P1 capabilities without extending schema unilaterally.

## Tasks

### P4-T1 — Baseline and exact lock normalization

**Files:** create `packages/twinklr/core/sequencer/moving_heads/refinement/models.py`, `packages/twinklr/core/sequencer/moving_heads/refinement/baseline.py`; modify `packages/twinklr/core/sequencer/moving_heads/delivery.py` to save physical-mode baseline; test `tests/unit/sequencer/moving_heads/refinement/test_baseline.py`.

**Interfaces:** `write_render_baseline(baseline:RenderBaseline,path:Path)->None`, `read_render_baseline(path:Path)->RenderBaseline`, `normalize_locks(locks:Sequence[RenderLock],*,frame_ms:int,capabilities:Mapping[str,FixtureCapabilities])->tuple[RenderLock,...]`. Canonical sorted JSON hashes; reject incompatible baseline schema/input identities.

- [ ] Write `test_baseline_roundtrip_preserves_segments_frames_and_provenance`, `test_lock_rounds_outward_to_frames`, `test_pan_lock_includes_fine_byte`, `test_unknown_fixture_and_empty_channel_lock_rejected`, `test_baseline_and_prepare_work_without_p3_installed`, `test_unknown_plan_snapshot_roundtrips_but_rerender_rejects`. Example: [21,59) becomes [20,60) at 20ms; fine channel change alone violates PAN lock.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/refinement/test_baseline.py -q`; observe expected failures.
- [ ] Implement serialization and normalization; no live state inferred from fixtures' defaults.
- [ ] Rerun command; require green including changed frame/profile hash rejection.
- [ ] Integrator commits `feat: persist moving-head refinement baselines and locks`; independent review checks baseline immutability.

### P4-T2 — Dependency-aware offline patching

**Files:** create `packages/twinklr/core/sequencer/moving_heads/refinement/prepare.py`; test `tests/unit/sequencer/moving_heads/refinement/test_prepare.py`.

**Interfaces:** `prepare_refinement` above calls P1 `plan_prepositions(...,initial_states=...,locks=...,frame_ms=...,failure_mode='error')`, consumes its replacement segments/dependencies, then `encode_fixture_frames(segments,capabilities,frame_times_ms=...)` per fixture.

- [ ] Write `test_locked_gobo_and_pan_bytes_survive_dimmer_revision`, `test_incoming_and_outgoing_dependency_closure`, `test_expansion_disabled_lists_neighbor_sections`, `test_unfeasible_locked_preposition_fails`, `test_slice_does_not_restart_phase`, `test_other_fixture_unchanged`. Assert `after_locked_frames==before_locked_frames` and no candidate leak into unrelated intervals.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/refinement/test_prepare.py -q`; verify failures.
- [ ] Implement closure, phase-preserving slicing and immutable baseline merge. Protect discrete channels against interpolation. A group-target effect that mixes locked/unlocked fixtures is expanded to individual fixtures for the replacement and traced; locked entire effects remain signature-identical when retained.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/refinement/test_prepare.py tests/unit/sequencer/moving_heads/compile/test_preposition.py tests/unit/sequencer/moving_heads/export/test_frame_encoder.py -q`; require green (P1 owns those two shared test paths).
- [ ] Integrator commits `feat: prepare locked refinements with boundary dependencies`; independent review checks both interval ends and grouping.

### P4-T3 — Reviewable diff and guarded application

**Files:** new `packages/twinklr/core/reporting/evaluation/refinement.py`; modify `packages/twinklr/core/api/xlights/injection.py`, `packages/twinklr/cli/main.py`; tests `tests/unit/reporting/evaluation/test_refinement.py`, `tests/unit/api/xlights/test_refinement_injection.py`, `tests/unit/cli/test_refinement_command.py`.

**Interfaces:** `write_refinement_report(prepared:PreparedRefinement,output_dir:Path)->tuple[Path,Path]` writes JSON and Markdown. Add `apply_prepared_refinement(workflow:LiveInjectionWorkflow,prepared:PreparedRefinement,*,expected_live_hash:str|None=None,dry_run:bool=True)->InjectionResult` and CLI `twinklr refine prepare --baseline PATH --request PATH --candidate PATH --output DIR`, then `twinklr refine apply PREPARED` performs read-only live preflight and writes exact planned commands plus the observed snapshot hash; `twinklr refine apply PREPARED --apply --expected-live-hash HASH` performs the authorized mutation. A hash is required only for mutation, not for the read-only preflight. Prepare defaults offline and never calls a provider. Candidate generation remains the existing authorized planning workflow.

Define `PhysicalIsolationEvidence(sequence_identity, patch_hash, full_effect_inventory_hash, covered_fixture_ids, inspected_layers, inspected_groups, complete:bool, conflicts)` in refinement models and `validate_physical_isolation(evidence:PhysicalIsolationEvidence,prepared:PreparedRefinement)->None`. The read-only preflight produces this evidence from actual inspected state; a caller-supplied `complete=True` alone is not proof. Inventory covers every layer of contributing models/groups and patch overlaps. Snapshot identity includes that inventory and patch/layout hash, not only affected owned effect signatures. If the available connector cannot retrieve this scope, the wrapper returns unsupported before any mutation rather than adding an unbounded layout-discovery subsystem in P4.

- [ ] Write `test_diff_equals_exact_emitted_frame_changes`, `test_stale_live_snapshot_aborts_before_write`, `test_apply_replaces_dependency_sections_only`, `test_ambiguous_post_returns_confirmed_prefix_without_retry`, `test_prepare_command_never_constructs_live_client`. Assert recorded commands equal those reviewed, and client mutation count is zero on stale data/collision.
- [ ] Add `test_foreign_dimmer_on_other_layer_blocks_physical_apply`, `test_group_or_patch_overlap_blocks_physical_apply`, and `test_incomplete_inventory_allows_offline_report_only`; fake effects at layer0 and group targets must block even when the reserved layer is clear.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_refinement.py tests/unit/api/xlights/test_refinement_injection.py tests/unit/cli/test_refinement_command.py -q`; verify failures.
- [ ] Implement report and a preflight snapshot hash including full isolation evidence. Recheck isolation and expected hash immediately before mutation, then call `inject(prepared.desired_live_effects,replace_sections=frozenset(prepared.affected_sections))` with complete desired retained/replaced effects for those sections. Reuse existing collision checks, ownership store and partial-error behavior. This narrows the review race; it cannot prevent another process changing xLights between calls.
- [ ] Rerun command and existing `tests/unit/api/xlights/test_injection.py`; require green. No automatic save/rollback/retry is added.
- [ ] Integrator commits `feat: review and apply prepared moving-head refinements`; independent review checks nontransactional recovery language.

### P4-T4 — Cue review and curated preset workflow

**Files:** extend `packages/twinklr/core/reporting/evaluation/refinement.py`; create `packages/twinklr/core/sequencer/moving_heads/templates/preset_review.py`; tests `tests/unit/reporting/evaluation/test_refinement_preview.py`, `tests/unit/sequencer/moving_heads/templates/test_preset_review.py`.

**Interfaces:** `build_refinement_contact_sheets(before_video:Path,after_video:Path,prepared:PreparedRefinement,output_dir:Path)->tuple[Path,...]` reuses `FrameSampler`/`compose_contact_sheets`; `validate_preset_candidate(document:TemplateDoc,capabilities:Sequence[FixtureCapabilities])->PresetReview` validates existing registry/collision/capability rules. Input target/preset files use P2 schemas; no parallel catalog format.

- [ ] Write `test_overlay_uses_effective_arrival_and_settle_diagnostics`, `test_preview_missing_video_reports_unavailable`, `test_changed_fixture_labels_match_diff`, `test_preset_id_collision_rejected`. Assert explanations reference effective output, not requested intent, and absent videos do not become fictitious screenshots.
- [ ] Run `uv run pytest tests/unit/reporting/evaluation/test_refinement_preview.py tests/unit/sequencer/moving_heads/templates/test_preset_review.py -q`; verify failures.
- [ ] Implement optional contact sheets/trajectory overlays plus a JSON/Markdown preset review artifact. Existing timestamp sampling is for review, not frame-precision proof. Preview rendering remains a separate explicitly requested xLights operation.
- [ ] Rerun command and `tests/unit/reporting/evaluation/test_vision_frames.py`; require green.
- [ ] Integrator commits `feat: add cue-level refinement and preset review artifacts`; reviewer checks warning visibility and no hidden catalog admission.

### P4-T5 — Bounded GDTF import pilot

**Decision:** choose GDTF 1.2 first because it has physical endpoints and motion timing semantics; defer OFL runtime ingestion. OFL remains a future export-plugin option, not a second parser in this phase. Source: [GDTF DMX mode specification](https://www.gdtf.eu/gdtf/file-spec/dmx-mode-collect/), [OFL format stability warning](https://github.com/OpenLightingProject/open-fixture-library/blob/master/docs/fixture-format.md).

**Files:** create `packages/twinklr/core/config/fixtures/importers/gdtf.py`; test `tests/unit/config/fixtures/test_gdtf_import.py`, synthetic archives under `tests/fixtures/gdtf/`.

**Interface:** `import_gdtf(path:Path,*,mode_name:str)->FixtureImportResult`; result has candidate `FixtureCapabilities`, proposed `DmxMapping`, provenance hash/mode/version and diagnostics. It never writes active fixture config. Installation/orientation/targets require explicit rig data afterward. Imported RealFade/RealAcceleration remain manufacturer provenance, not an automatically accepted conservative speed bound; physical rendering requires the separately authored bound P1 specifies.

- [ ] Write `test_8_and_16bit_axis_offsets_in_significance_order`, `test_physical_range_and_unknown_zero_speed`, `test_single_wheel_and_shutter_semantics`, `test_mode_master_or_geometry_references_rejected`, `test_overlapping_channels_rejected`, `test_archive_limits_and_path_escape_rejected`.
- [ ] Run `uv run pytest tests/unit/config/fixtures/test_gdtf_import.py -q`; verify failures.
- [ ] Implement ZIP/XML reader with 100 files/10MiB uncompressed/2MiB XML limits, no archive extraction, DTD/entity rejection. Support one explicitly named mode, footprint offsets 1–48 as required by P1, single emitter/head, 8/16-bit pan/tilt, 8-bit dimmer, shutter open/closed/strobe ranges, one color wheel and one gobo wheel with discrete slots. Reject switching/mode-master dependencies, geometry references/multicell, RGB/CMY, continuous wheel rotation and unsupported movement ranges. Never guess unsupported channel names or treat zero timing defaults as measured capability.
- [ ] Rerun command; review two synthetic supported modes plus every declared rejection. A third-party profile pilot requires separately authorized input provenance and its own validation record.
- [ ] Integrator commits `feat: add opt-in bounded GDTF fixture import`; independent review. GO only if supported profiles preserve physical/DMX mapping and all unsupported cases fail clearly; otherwise keep experimental.

### P4-T6 — Native Moving Head backend representability spike

**Files:** new `packages/twinklr/core/sequencer/moving_heads/export/native_moving_head.py`; tests `tests/unit/sequencer/moving_heads/export/test_native_moving_head.py`; synthetic scratch assets/runbook in this change's evidence folder when executed.

**Interfaces:** `assess_native_representability(segments:Sequence[FixtureSegment],capabilities:Mapping[str,FixtureCapabilities],fixture_numbers:Mapping[str,int])->NativeAssessment` returns representable flag and reasons; `build_native_effects(segments:Sequence[FixtureSegment],capabilities:Mapping[str,FixtureCapabilities],fixture_numbers:Mapping[str,int],model_names:Mapping[str,str],assessment:NativeAssessment)->tuple[EmissionRequest,...]` only accepts a successful assessment with the same canonical input hash. Config `JobConfig.moving_heads.export_backend='dmx'|'native_experimental'` defaults DMX; experimental unsupported fixture/time blocks fall back wholly to DMX, with trace reason and no overlapping dual-backend output.

- [ ] Write `test_static_and_linear_supported_subset`, `test_arbitrary_curve_and_unsupported_channel_fall_back`, `test_fixture_number_limit_rejected`, `test_native_dmx_never_overlap_same_attribute`; assert no lossy approximation.
- [ ] Run `uv run pytest tests/unit/sequencer/moving_heads/export/test_native_moving_head.py -q`; verify failures.
- [ ] Implement initial subset: supported xLights fixture-number mapping 1–8, static targets and linear two-endpoint pan/tilt, constant supported intensity/color; no custom path, 3D target, gobo/prism or nonlinear transition. Serialize to pinned xLights settings through the existing emitter. Retain DMX as authoritative output.
- [ ] Rerun unit tests; then, only with owner authorization, render native and DMX scratch sequences with the pinned xLights build and compare every fixture/channel/frame using the independent P5 rendered-frame oracle: separately extract the actual native and DMX xLights FSEQ1 output, compare both to P5's hand-derived reference cases, and compare the rendered streams to one another. P1 `EncodedFixtureFrame` expectations are additional diagnostics, never the sole truth or an oracle implemented by calling the production encoder. Convert verified nonsparse inputs only with `fseq_convert -i rendered.fseq -o rendered-v1.fseq -f 1 -n` if required, following P5 metadata/provenance checks. Sparse input is unsupported by this pilot recipe; `-n` alone does not prove expansion. Do not modify existing `compare_fseqs` semantics. Require exact supported-byte parity; any mismatch removes that case from representable subset.
- [ ] Integrator commits experiment/results after independent review. GO requires exact frame parity and owner evidence that native editing saves meaningful work; otherwise retain disabled experiment/NO-GO record. Offline unit tests alone cannot establish xLights acceptance.

### P4-T7 — Conditional BlenderDMX validation decision and phase gate

**Scope/default:** no Blender dependency or production backend. Run only if an unresolved fixture-coordinate/optical question remains after frame-correct xLights tests and the owner authorizes a synthetic replay. The project itself reports real-time limits; use offline capture. [BlenderDMX status](https://blenderdmx.eu/)

- [ ] Record a single concrete question and predicted observable difference in the phase evidence record; if none remains, record NO-GO/not needed and stop this experiment.
- [ ] If authorized, prepare one synthetic two-head scene, five known target poses, dimmer/shutter states and one slow movement. Pin Blender/BlenderDMX/GDTF versions and source hashes; use no owner layout or media.
- [ ] Replay captured P1 frames offline, compare expected pan/tilt orientation and visibility at named timestamps, and record limitations. No network playback to hardware, physical accuracy or taste claim follows.
- [ ] Independent reviewer records whether the experiment resolves its question; keep it optional regardless of outcome.
- [ ] Integrator runs full clean-tree `make validate` after committing implementation, records real output, and obtains independent phase review. Core exit requires exact lock preservation, verified dependency closure, accurate diff/application recovery and measured refinement effort in later owner trials; importer/native/Blender decisions remain separate, explicit records.

## Documentation, registry and existing-test updates

Added 2026-11-13 from a recheck at `f067a56`; see the
[shared rule](README.md#documentation-registry-and-test-surfaces). Recheck at P4 kickoff.

- **Config inventory.** P4-T6 registers `job.moving_heads.export_backend` with a
  collecting evidence test.
- **CLI documentation.** P4-T3 adds `twinklr refine prepare` and `twinklr refine apply`.
  Document them in `docs/user-guide.md` beside the existing "Live injection and section
  regeneration (LOCAL-ONLY)" section, including that `apply` without `--apply` is a
  read-only preflight and that application is not transactional.
- **Existing guards.** `tests/unit/cli/test_live_injection_command.py` and
  `tests/unit/api/xlights/test_injection.py` pin the legacy injection path P4-T3 must
  leave unchanged; run both with that task.
- **Documents for the optional pilots.** A GDTF import or native backend that reaches
  GO is documented in `docs/user-guide.md` as opt-in and experimental; a NO-GO is
  recorded in this change's evidence only.
