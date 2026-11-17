---
type: review
status: complete
area: engineering
change: 2026_11_12_mh_true_up
created: 2026-11-16
updated: 2026-11-16
---

# C1.1b: `eval-report` on physical output — 2026-11-16

`twinklr eval-report` reads a `physical_v2` run's checkpoint and reports on the physical
render. Written on `feat/mh-cutover-eval` from `b5cbc658` in two commits: `070050ca`
and the review-fix commit that adds this record. One implementing agent; one review
(approve with fixes: one high, four medium, six low), fixed in the second commit. No
provider, owner data or xLights was used: every run below is synthetic.

## How the re-render is guaranteed to be the run's render

After a physical render, the render stage adds a `render` record to the plan checkpoint
(`checkpoints/plans/final.json`), written atomically. A failure there is logged and does
not fail the delivered render. The record holds:

- `render_fingerprint`: the run's;
- `policy`: the full moving-head policy, initial states included;
- `beat_grid`: the grid the run rendered against. Re-analyzing the audio is not
  guaranteed to give it back, and the old re-render built its grid without the
  duration the run passes;
- `admission`: the pre-planning gate's result, null if none ran. It decides the variant
  a section naming no preset renders, and the fingerprint includes preset substitutions;
- `inputs`: the trace's input hashes (each fixture's profile hash and model name, each
  template's hash, the beat grid's hash, the renderer and encoder revisions).

The report re-renders under that policy, grid and admission, with the physical catalog
admitted as `twinklr run` admits it. It compares the re-render's fingerprint with the
run's. A mismatch is a `RENDER_FINGERPRINT_MISMATCH` error naming each recorded input
that differs, and the command prints it too. These are refused before audio analysis:

- a physical checkpoint without a readable record;
- a plan naming a template that is neither built in nor in the catalog, such as a
  `--template-dir` template. `eval-report` has no template directory option.

Only `eval-report` reads the checkpoint. A physical checkpoint written before this record, or with a record lacking `inputs`, is refused as malformed: re-run the job.

## What the physical report contains

Values are decoded from the encoded frames through each profile
(`AxisCapability.decode`, added). Each section is read over the frames its cues land
on, its bounds quantized as cues are.

| Legacy metric | What it measured | Physical report |
|---|---|---|
| min, max, range, mean, std (pan, tilt) | Positions used | Degrees, every frame. **Meaning changed:** legacy was a fraction of the DMX range. `lit_range` added: lit frames only |
| same (dimmer) | Brightness | **Emitted intensity**: the dimmer, 0 where the shutter extinguishes |
| `energy` | Movement rate | **Per second** over 20 ms frames; legacy was per sample. `lit_rate` added: consecutive lit frames only |
| zoom | Not reported by legacy | Degrees, like pan and tilt, where the profile has a zoom axis |
| `clamp_pct`, CLAMP flags | Curve clipped at DMX bounds | Null: the renderer refuses out-of-range values |
| LIMITED_RANGE, STATIC_CURVE | Heuristics on legacy curve types | Null: no curve types |
| Loop continuity | Section start against end | Null. A repeating cycle spans whole periods and continues its phase. A finite move restarts each repeat dark, through a transaction, when the restart needs more than one frame's travel; otherwise lit, as one step within travel speed (reported as the largest lit step); a repeat for which neither fits is kept dark |
| curve type, handler, base position, static DMX | Legacy segment metadata | Null |
| Physics check | Speed and acceleration against assumed 540°/270° ranges | Null. The renderer plans within travel speed, latency and settle; acceleration is modelled nowhere. Largest lit step and its allowance (travel speed plus one DMX word) reported, `LIT_STEP_EXCEEDS_TRAVEL` if beyond, decided exactly in words. Necessary, not sufficient: it misses sustained overspeed of up to one word per frame and a reveal before travel or settle ends |
| Template compliance | Curve types, handlers, planner modifiers | Null: physical_v2 applies no planner modifiers |
| Section transitions | Jumps at boundaries | Null. A head that must reposition does so dark, in its entry window (`cut`) or before the section (`none`); a `skipped` head plays through lit. Entry windows, transactions and each skipped head's change across the boundary reported |

Each section also carries the trace's facts for it: entry windows, transactions by
status, kept-dark cues and diagnostics. The flags are:

- `CUES_KEPT_DARK`;
- `SECTION_DARK_FOR_ENTRY`: an entry window that outlasts its section;
- `LIT_STEP_EXCEEDS_TRAVEL`;
- `RENDER_DIAGNOSTIC`.

The report-level `physical` block holds:

- both fingerprints and `mismatched_inputs`;
- the gate's exclusions, variant exclusions and effective variants;
- `unplayable_totals`;
- `not_reported`, the list above with its reasons.

Reproduced during review and now reported: on the family rig, MH1 plays from
`target_orbit` (bars 5–8) into `mirror_wings` (bars 9–12) lit at full intensity, and
its pan steps from 24.95° to 35.0° in one frame (16000 → 16020 ms). That is within the
14.41° its 720°/s travel allows in a frame, plus one word.

## Verification

- **Legacy report**, `b5cbc658` against each commit: identical. That covers
  `report.json` without run provenance, `report.md` without timestamp and SHA, and plot
  names and sizes. No golden or `evaluations/` file changed.
- **Lit-step sweep:** every ordered pair of admitted shipped families, as two
  consecutive 4-bar sections, at 375, 500 and 600 ms beats. It ran on the family rig
  (with the `flick` preset) and on the zoom pilot rig with all seven families.
  - 255 renders.
  - Every re-render's fingerprint matched its run's.
  - `LIT_STEP_EXCEEDS_TRAVEL` never fired.
  - Largest lit step as a share of its allowance: pan 0.70, zoom 0.46, tilt 0.17.
- **Independent verification sweep:** a further 170 renders, on jittered and 3/4 grids among others. The warning fired 0 times; the largest ratio was pan 0.70.
- **Mutation checks:** 21 mutations of the review fixes, then 12 more for the
  verification round, each applied alone; all killed by the new tests. The second set
  covers the five mutants the verifier found surviving (renderer revision and beat grid
  not compared, the boundary `lit` forced true, `lit_rate` counting dark pairs, the
  "differs" lines missing from `report.md`), the float tie, the file mode, the
  validation of `inputs`, the non-mapping record and the mismatch fallback message.
  The first set covers:
  - frame alignment;
  - the boundary search;
  - the lit filter;
  - the flag condition and the allowance;
  - the template check;
  - lit-only motion;
  - the mismatch comparison and the command's output;
  - the recorded inputs;
  - the atomic and non-fatal write;
  - the malformed-record refusal;
  - validation against the catalog;
  - zoom;
  - `decode` inversion;
  - the section-dark flag.

## For C1.2: delete

- `rerender.py`:
  - the `MHRenderPolicy` arm of `render_policy` (legacy grid from features, schema "3.0");
  - `RerenderResult.segments` and `song_features`, if nothing else reads them.
- `collect.py`: `checkpoint_render_policy` and the `render_mode` read. `stage.py` stops
  writing `render_mode`.
- `extract.py`: `extract_curves_from_segments`, `_sample_channel_over_window`,
  `_sample_at_time`, `_interpolate_curve_points`.
- `analyze.py`: `analyze_curve`, `check_loop_continuity`, `_calculate_clamp_percentage`
  (`_calculate_energy` stays).
- Whole files: `physics.py`, `continuity.py`, `compliance.py`.
- `generator.py`:
  - the legacy window and the legacy per-channel body;
  - the physics and compliance counts, the transitions loop and the compliance block;
  - the `physical is None` guards.
- `plot.py`: the DMX ×255 branch.
- `render.py`: the legacy metric line and the compliance and transition blocks.
- `config.py` (`EvalConfig`): `samples_per_bar`, the clamp, loop, physics and
  continuity thresholds and toggles.
- `models.py`: `ContinuityCheck`, `PhysicsCheck`, `TemplateCompliance`,
  `ModifierCompliance`, `TransitionAnalysis`, and their `__init__` exports.
- Tests: the legacy cases in `test_extract.py`, `test_analyze.py` and `test_plot.py`;
  `test_end_to_end.py`; the refusal tests in `test_rerender_contract.py`.

## For C1.3: fields left null or mode-dependent after C1.2

- Remove: `CurveStats.clamp_pct`.
- Remove from `CurveAnalysis`: `continuity`, `curve_type`, `handler`, `base_position`,
  `static_dmx`, `physics_check`.
- Remove from `SectionReport`: `template_compliance`, `transition_to_next`.
- Remove from `ReportSummary`: `physics_violations`, `compliance_issues`,
  `harsh_transitions`.
- Remove `PhysicalRenderSummary.not_reported` and `NOT_REPORTED_FOR_PHYSICAL`; the
  physical block may then fold into the report.
- Single meaning only: `CurveAnalysis.space` (only `degree` and `normalized`) and
  `CurveStats.energy` (only per second).
- `RerenderResult.segments` and `song_features`.

## Not verified

- No real audio: song metadata comes from a stand-in analysis in the tests.
- No real or measured profiles: only the synthetic family and zoom pilot profiles.
- Grids: 4/4 at 375, 430, 500 and 600 ms beats, plus jittered and 3/4 grids in the verification sweep. No 6/8 grid.
- No xLights.
- Rendering time on a full song, for a report decoding every frame of every head.

## Addendum, later on 2026-11-16

After the four ports were combined, a verifier found that `twinklr show` wrote no
render record, so `eval-report` refused its checkpoint with advice that was untrue.
The record is now built by `RenderingPipeline.checkpoint_record` and written by one
writer for `run`, `inject`, `regenerate` and `show`. It also carries the coordination
`dark_spans` (when there are any) and `inputs.rig`: a hash of the rendered fixture
group, a hash per top-level field, and whether the rig was reconciled with a live
layout. A record without `rig`, the form this port first wrote, is refused as
malformed. `eval-report` reproduces a show's moving-head fingerprint, reports its dark
spans, and names "dark spans" or the rig field when they differ. A live run on a
layout lacking the configured group is named as such; it cannot be reproduced from a
fixture file.
