# Phase 4 — Moving-Heads Rendering (Stage 3 source review)

_Authored 2026-08-13 by the Stage 3 phase-4 author (opus), read-only against baseline
`aa8d325`. No source was modified. No code was executed: the workspace `.venv/` is
unpopulated (`.venv/bin/python -c "import twinklr"` → `ModuleNotFoundError`), so every
claim below is **static** — source reading, exhaustive `grep` over `packages/`, `tests/`,
`scripts/`, and AST extraction of the 37 builtin template files. Claims are marked
OBSERVED (read directly in source) or INFERRED (derived by analysis, not executed).
Runtime confirmation of the INFERRED items is deferred to Stage 4._

**Phase verification status: VERIFIED (2026-08-13, opus code-reviewer, non-author).**

_Verification outcome: 16 findings ACCEPTED, 11 REVISED, 0 outright rejected (2 sub-rows
of P4-F20 rejected), 8 missed findings added as P4-M1…M8. Both CRITICALs (P4-F1, P4-F2)
and the V-categorical REFUTES verdict held exactly, each independently re-derived. This
revision incorporates every correction; the full verification record is
[reviews/verification.md](../verification.md) §"Phase 4". Corrections adopted from the
verifier are marked **[V]** at the point of use._

---

## 1. Scope & exclusions

**In scope (reviewed):**

| Area | Path | LOC |
|---|---|---|
| Moving-heads renderer | `packages/twinklr/core/sequencer/moving_heads/**` (pipeline, compile/, channels/, handlers/, templates/ incl. all 37 builtins, libraries/, export/, xsq_export, fixture_builder, utils) | ~9,900 |
| Curves | `packages/twinklr/core/curves/**` | ~3,381 |
| Resolvers | `packages/twinklr/core/resolvers/poses.py` | 242 |
| Categorical rendering | `packages/twinklr/core/sequencer/rendering/**` | 218 |
| Timing | `packages/twinklr/core/sequencer/timing/**` | 1,058 |
| Vocabulary | `packages/twinklr/core/sequencer/vocabulary/**` | ~1,300 |

**Read as necessary context but owned by other phases** (findings referred, not claimed):
`core/sequencer/models/{enum,template,context,transition}.py` (phase 5), `core/config/fixtures/**`
and `core/config/models.py` (phase 1), `core/agents/sequencer/moving_heads/**` (phase 3),
`core/formats/xlights/**` (phase 5).

**Exclusions:** display rendering, `formats/xlights` parser/exporter internals, agent
orchestration, and the LLM planner's own quality. Where a finding straddles a seam it is
marked with the co-owning phase.

**Dimensions marked N/A:** security/trust boundaries (no network, no deserialization of
untrusted input in this phase — the `.xsq` parse boundary belongs to phase 5);
concurrency (the render path is entirely synchronous, single-threaded); i18n.

---

## 2. Purpose, entry points, contracts, state, invariants, dependencies, consumers

**Purpose.** Turn a `ChoreographyPlan` (a list of sections, each naming a `template_id`
and optional `preset_id`) plus a `BeatGrid` and a `FixtureGroup` into an xLights `.xsq`
containing DMX effects for moving-head fixtures.

**Entry points.**
- `RenderingPipeline.render()` — `moving_heads/pipeline.py:134`. Constructed at
  `agents/sequencer/moving_heads/rendering_stage.py:133` (the shipped CLI path) and at
  `reporting/evaluation/rerender.py:125` (the offline eval tool). Those are the only two
  construction sites (OBSERVED, exhaustive grep).
- `compile_template(template, context, preset)` — `compile/template_compiler.py:63`.
- `export_to_xsq(...)` — `xsq_export.py:28`.

**Contracts.**
- *Inbound (planner → renderer):* `ChoreographyPlan` /
  `PlanSection` (`agents/sequencer/moving_heads/models.py:31`). See §11 P4-F26 for what
  is actually read.
- *Template contract:* `Template` → `RepeatContract` + `list[TemplateStep]`, each step
  carrying exactly three creative axes — `Geometry`, `Movement`, `Dimmer`
  (`models/template.py:328-337`). There is no fourth axis.
- *Handler contract:* three `Protocol`s — `GeometryHandler.resolve`,
  `MovementHandler.generate`, `DimmerHandler.generate`
  (`moving_heads/handlers/protocols.py:101,135,169`), registered in three registries
  built by `create_default_registries()` (`handlers/defaults.py:143`).
- *IR:* `FixtureSegment` (`channels/state.py:72`) — `{fixture_id, t0_ms, t1_ms,
  channels: dict[ChannelName, ChannelValue]}`. This IR is **channel-generic**: the
  channel map is open, which matters for the color question (§11 P4-F16).
- *Outbound:* `EffectPlacement` → xLights `DMX` effect with a settings string built by
  `DmxSettingsBuilder.build_settings_string` (`export/dmx_settings_builder.py:42`).

**State.** The renderer is stateless per call except for one process-global: the template
registry `REGISTRY` (`templates/library.py:123`), populated by import side effects via the
`@register_template` decorator (`library.py:126`). `TemplateRegistry.get` deep-copies by
default (`library.py:93`) — a genuine strength (confirms the discovery "deep-copy defaults"
positive signal).

**Invariants asserted by the code.** Curve values in `[0,1]` (`curves/models.py:35-36`,
a *raising* pydantic constraint, not a clamp); DMX in `[0,255]`; `t1_ms >= t0_ms`
(`channels/state.py:115`); segments partition each section's bar range. §11 P4-F6 shows
the last invariant is violated in practice.

**Dependencies.** `core/curves` (curve generation), `core/config/fixtures` (DMX mapping,
calibration, poses), `core/sequencer/models` (enums, template models, context),
`core/sequencer/timing` (BeatGrid), `core/formats/xlights` (XSequence, exporter).
Notably **absent**: `core/sequencer/vocabulary` — zero imports (§11 P4-F17).

**Consumers.** `rendering_stage.py` (CLI path) and `reporting/evaluation/rerender.py`.
Nothing else consumes `FixtureSegment` outside the moving-heads package.

---

## 3. Representative execution paths inspected

**Path A — nominal section render.**
`render()` (`pipeline.py:164`) → `iterate_plan_sections` flattens segments
(`pipeline.py:287`) → `get_template(section.template_id)` (`pipeline.py:176`) → preset
resolution or auto-synthesis from `ENERGY_TO_INTENSITY` (`pipeline.py:186-220`) →
`TemplateCompileContext` built from five plan fields (`pipeline.py:226-238`) →
`compile_template` (`template_compiler.py:63`) → `apply_preset` (`preset.py:90`) →
`schedule_repeats` (`scheduler.py:50`) → per instance: role filter
(`template_compiler.py:124`), chase ordering (`:142`), phase offsets (`:150`), then per
fixture `compile_step` (`step_compiler.py:44`) → geometry handler `.resolve` → movement
handler `.generate` → dimmer handler `.generate` → `apply_phase_shift_samples`
(`curves/phase.py`) → `FixtureSegment` with PAN/TILT/DIMMER channels.

**Path B — transition generation** (on by default: `TransitionConfig.enabled=True`,
`config/models.py:462`). `_detect_and_plan_transitions` (`pipeline.py:318`) →
`TransitionDetector.detect_section_boundaries` (`transition_detector.py:30`) →
`TransitionPlanner.plan_transition` (`transition_planner.py:47`) →
`_get_segments_at_boundary` (`pipeline.py:441`) →
`TransitionSegmentCompiler.compile_transition` → segments placed on xLights layer 1
(`xsq_adapter.py:90-92`).

**Path C — export.** `export_to_xsq` (`xsq_export.py:28`) parses the template `.xsq` or
creates one stamped `"2024.10"` (`:67`) → adds timing tracks from
`beat_grid.{beat,bar}_boundaries` (`formats/xlights/sequence/timeline.py:104,128`) →
`XsqAdapter.convert` groups identical segments onto semantic-group models
(`xsq_adapter.py:211`) or writes per fixture (`:144`) → `DmxSettingsBuilder` emits
`E_SLIDER_DMX{1..16}` + `E_VALUECURVE_DMX{n}` → `XSQExporter.export`.

**Path D — short section.** A section whose bar count is below the template's
`cycle_bars` returns zero instances (`scheduler.py:96-107`) and therefore zero segments.
See P4-F4.

**Path E — preset auto-synthesis.** `preset_id` not found on the template → uppercase
lookup in `ENERGY_TO_INTENSITY` (`pipeline.py:48,196`) → a synthetic `TemplatePreset`
patching `{"intensity": ...}` on every step's movement and dimmer (`:199-211`). This is
the path taken for 33 of 37 templates (only 4 define presets at all).

---

## 4. Implementation assessment

### 4.1 What is well built

- **Template registry.** Factory-per-template with materialize-on-register validation and
  deep-copy on `get` (`templates/library.py:52,93`) genuinely prevents cross-section state
  bleed. Alias normalization (`_norm_key`, `:17`) is sensible.
- **Layered compile decomposition.** `schedule → order → offset → compile step → clip` is
  a clean pipeline with each stage in its own module and its own result model. The
  boundaries are real, not nominal.
- **Handler indirection.** `GeometryType`/`MovementType`/`DimmerType` → registry →
  protocol-typed handler is a decent extension seam; 17 geometry handlers implement it.
- **`FixtureSegment` IR is channel-generic** — `dict[ChannelName, ChannelValue]` with
  static-or-curve mutual exclusion enforced by a validator (`channels/state.py:56-69`).
  This is the single most important architectural asset in the phase (see §8).
- **Grouping heuristic** in `XsqAdapter._write_group_effects` (`xsq_adapter.py:211`) —
  finds the largest fully-covered semantic group, refuses to group when curves differ or
  when phase offsets are in play (`:300-305`, `_segments_have_identical_curves` at `:348`).
  This is careful, correct-looking code that materially shrinks output size.
- **Provenance/metadata.** Every segment carries handler ids, resolved params, base poses
  and phase offset as metadata (`step_compiler.py:167-195`), and the effect label encodes
  `section_step_template_preset` (`channels/state.py:105`). Good debuggability.

### 4.2 What is not

The renderer's problems are not stylistic. **Six** of them change what the user sees, and
not one is caught by a test that would fail — one is actively *pinned* by a passing test.
They are detailed as findings P4-F1…F7 and P4-M1/M2 in §11 and §11b. In summary:

- The **movement intensity axis is disconnected** at the handler boundary — every movement
  in every show renders at `Intensity.SMOOTH` (P4-F1), and the integration test suite
  encodes that as correct (P4-M4).
- **Three incompatible time grids**: the planner floors section starts against a nominal
  tempo, the renderer places effects on a uniform average-tempo grid, and the timing tracks
  written into the same file use the actual detected downbeats (P4-F2, P4-M3).
- The exporter **drives every DMX channel it did not choreograph to 0**, including
  shutter, whose own library in this repo defines `DMX_CLOSED = 0` (P4-F3).
- The scheduler renders **nothing at all** for sections shorter than one template cycle
  (P4-F4), renders **only the loop step** of the two narrative multi-step templates
  (P4-F5), and **overruns the section by 2×** for one template (P4-F6).
- **[V]** Every template's declared dimmer floor of 60 is silently dropped, so dimmers
  drive to 0 instead of the anti-flicker level (P4-M1).
- **[V]** The two BLACKOUT templates render **full brightness** under every preset except
  MODERATE — on exactly the drop sections a planner selects them for (P4-M2).

Secondary implementation observations:

- **Dead weight is substantial.** Within phase-4 scope, ≈1,900 LOC has zero non-test
  importers: all of `resolvers/` (242), all of `sequencer/rendering/` (218), the three
  channel libraries `libraries/{color,gobo,shutter}.py` (643), `ChannelState`
  (`channels/state.py:215-357`, ~143), and seven curve modules
  (`taxonomy`, `protocols`, `simplification`, `composition`, `adapters`, `modifiers`,
  `providers/native`) totalling ~987. Two of those (`curves/taxonomy.py`,
  `curves/protocols.py`) have **no importer at all, not even a test**.
- **Duplication.** `_resolve_static_dmx_value` is near-identical in
  `handlers/movement/default.py:201-204` and `handlers/dimmers/default.py:171-174`; the
  same `[0,1]` clamp appears three times each in the movement handler (`:340,:361,:378`)
  and dimmer handler (`:241,:265,:278`); `PhaseOffsetResult.get_normalized`
  (`phase_offset.py:33`) and `calculate_normalized_offset` (`:128`) duplicate logic that
  `template_compiler.py:169` re-implements inline — and both helpers have **zero callers**
  anywhere including tests.
- **A reverse dependency exists purely to serve dead code**: `curves/adapters.py:13`
  imports `MovementCategoricalParams` from `sequencer/moving_heads/libraries/movement.py`,
  inverting the intended layering (`curves` is meant to be the lower layer). Deleting
  `adapters.py` removes the inversion.
- **Perf.** Per-section cost is `O(instances × fixtures × n_samples)` with `n_samples`
  fixed at 64 (`models/context.py:86`, never overridden). For a 4-head rig and a 3-minute
  song at ~90 bars with 4-bar cycles that is on the order of 10^4–10^5 float operations
  total. Perf is a non-issue and no optimization is warranted. The fixed 64 is a
  *fidelity* concern, not a speed one: a `DimmerType.PULSE` at `Intensity.INTENSE`
  (`period=0.25` bars, `libraries/dimmer.py:37`) yields 16 cycles across a 4-bar step —
  4 samples per cycle, at the Nyquist limit. INFERRED; currently unreachable because the
  auto-preset cannot select INTENSE (P4-F8), but it becomes real the moment presets are
  fixed.

---

## 5. Tests & validation assessment

**Inventory** (OBSERVED, `tests/unit/sequencer/moving_heads/**` = 2,891 lines across 10
files; `tests/unit/curves/**` = 18 files; `tests/unit/timing/**` = 5 files).

The distribution is **inverted relative to risk**:

| Subsystem | Prod LOC | Dedicated test LOC | Notes |
|---|---|---|---|
| Transitions (blender, detector, planner, segment compiler) | ~1,120 | **1,861** | 64% of all moving-heads test lines |
| `compile/scheduler.py` | 225 | **39** | decides whether anything renders at all |
| `compile/template_compiler.py` | 451 | **0** | |
| `compile/step_compiler.py` | 232 | **0** | |
| `compile/phase_offset.py`, `preset.py`, `patch.py` | 409 | **0** | |
| `handlers/movement/default.py` | 381 | 4 integration tests | **[V] not zero — but they PIN the defect**, see below and P4-F1 / P4-M4 |
| `handlers/**` (17 geometry + dimmer + registry) | ~1,720 | **0** | |
| `export/xsq_adapter.py` | 412 | 4 integration tests | **[V] layer assignment only**; grouping + settings content untested |
| `export/dmx_settings_builder.py`, `xsq_export.py` | 436 | **0** | the output boundary proper |
| `channels/state.py`, `fixture_builder.py`, `utils.py` | 574 | **0** | |
| `resolvers/poses.py` | 242 | **0** | confirmed, §11 P4-F19 |
| `sequencer/rendering/categorical_resolver.py` | 203 | **0** | confirmed, §11 P4-F18 |

**[V] Corrections to the original inventory.** Two rows previously read "0" and were wrong:
- `handlers/movement/default.py` is exercised by
  `tests/integration/test_handler_categorical_params.py` (`:23`, `:51`, `:84`, `:112`).
  This is **worse than no coverage**: every call passes intensity both as a `params` key
  and as the `intensity=` argument, so the tests pass *because* they supply the key that
  production never sets, encoding P4-F1 as intended behaviour. Two are named `…_currently`.
- `export/xsq_adapter.py` has four integration tests in
  `tests/integration/test_transitions_multi_layer.py:74,117,188,223`, covering layer
  assignment only.

**Test realism is weak where it matters most.** `tests/unit/sequencer/moving_heads/test_rendering_pipeline.py:262`
(`test_render_returns_segments`) is the only end-to-end render test, and it **patches
`compile_template`** with a `MagicMock` — so it never executes the compiler, the handlers,
the curves, or the exporter. The remaining tests in that file assert construction and
fixture-context shape.

**No golden/regression test exists for DMX output.** No test asserts the content of a
generated settings string, an `E_VALUECURVE_DMX` payload, or a byte of `.xsq`. Findings
P4-F1, F3, F7, F9, F10, M1 and M2 would each have been caught by one snapshot test over
`DmxSettingsBuilder.build_settings_string` for a single 4-bar section. **[V]** A post-hoc
validator that already performs much of this checking exists but is not wired into any
gate — `scripts/validation/_core/mh_xsq_validation.py` (587 LOC, unit-tested); see P4-F22
and P4-M8.

**Curve tests cover the library but not the live path.** `tests/unit/curves/test_phase.py`
contains exactly two tests, both error paths (`:18`, `:23`) — not one assertion about a
shifted value, despite `apply_phase_shift_samples` being on the shipped path for every
chase effect. `curves/functions/movement.py` — the module whose `center_curve` call
cancels the amplitude parameter (P4-F13) — has **no dedicated test file**.
`curves/dmx_conversion.py::movement_curve_to_dmx` has zero tests and is dead (P4-F9).

**Tests exist for dead code.** `tests/unit/curves/{test_simplification,test_composition,
test_parameter_adapters,test_modifiers,test_native}.py` and
`tests/unit/sequencer/moving_heads/libraries/test_curve_intensity_params.py` all exercise
code with no production caller. This inflates the apparent coverage of the phase.

**Validation gates.** `make validate` was **not run** — it mutates source (format +
lint-fix) and this review is read-only; Stage 4 owns that evidence.

---

## 6. Critical assessment — should this subsystem exist in its current form?

Stage 2 names this subsystem — "the template library + renderer + selector logic" — as
Twinklr's moat, and stakes the recommended direction on it: *"Twinklr's defensible core is
deterministic audio analysis + the tested pan/tilt/dimmer renderer."* Phase 4 was asked to
test that claim. The verdict is **split, and the split matters**:

**The architecture deserves to exist. The current implementation does not deserve the
word "tested".**

*What is genuinely defensible.* The decomposition is right. A template library expressing
choreography as (geometry × movement × dimmer × repeat contract), compiled against a beat
grid into a channel-generic IR, then adapted to xLights DMX effects, is a sound design that
a competitor would have to reproduce. The 37 templates encode real domain knowledge — 34
distinct (geometry, movement, dimmer) combinations drawn from 17 geometries and 20 movement
patterns (§7, §11 P4-F25), with coherent energy annotations. That library is months of
domain work and it is the asset. The handler seam, the deep-copying registry, and the
grouping heuristic in `XsqAdapter` are all above-average code.

*What the "tested renderer" claim does not survive.* Stage 2's phrase implies the
pan/tilt/dimmer path is the trustworthy part. It is the **least tested** part: 436 lines of
settings-string/export code, ~1,720 lines of geometry and dimmer handlers, and 683 lines of
the two compilers have zero dedicated tests, while 64% of the test mass sits on the
transition subsystem — and where a test *does* touch the movement handler it holds the
defect in place rather than catching it (P4-M4). That is where the **six** output-changing
defects live. Concretely, at baseline `aa8d325` the renderer:

- ignores movement intensity entirely (P4-F1), so the one plan field that carries energy
  into movement is discarded;
- places effects on a time grid shared with neither the plan's bar numbers nor the timing
  marks it writes into the same file (P4-F2, P4-M3);
- writes an explicit 0 to every unchoreographed DMX channel in the emitted window, which by
  this repository's own `ShutterLibrary.DMX_CLOSED = 0` means "shutter closed" (P4-F3);
- renders silence for short sections (P4-F4) and renders only the middle step of both
  narrative templates (P4-F5);
- **[V]** discards every template's declared dimmer floor, driving dimmers to 0 (P4-M1);
- **[V]** renders the two blackout templates at **full brightness** under three of the four
  presets, on the drop sections where they are chosen (P4-M2).

**Is the renderer "good"?** The design is good; the wiring is not. Nearly all of
P4-F1…F7 and P4-M1/M3 are *connection* defects — a parameter dropped at a boundary, a grid
not consulted, a channel not written. The exceptions are narrow arithmetic errors
(P4-M2's `int × 255` unit confusion, P4-F9's multiply-by-zero, P4-F12's missing phase
term), not design errors. The curve mathematics, the geometry resolution, and the grouping
logic are sound in isolation. That is the most repairable possible failure mode, and it is
strong evidence that this code was written against a design and then never validated
against an actual light show. Stage 2's observation that "no evaluation result has ever
been committed" and "there is not one recorded human opinion about a generated show" is the
direct cause: nothing in the loop could have caught a closed shutter, a constant movement
intensity, or a blackout that shines at full.

**Verdict** (confirmed clean by the phase verifier)**.** Keep the subsystem; retract the
"tested" adjective. The moat is the *template library plus the compile architecture*, not
the current renderer build. The repair is bounded — the findings are localized fixes — but
two of them are larger than a line: P4-F1a needs ~100 missing intensity entries filled in
across the movement library, and P4-F2 cannot be closed without phase 3. The work must be
sequenced **before** any comparison of LLM vs deterministic arms, because at baseline both
arms render through the same broken wiring and the comparison would measure nothing. This
sharpens Stage 2's own sequencing ("instrument
first, then decide, then repair") into: **repair the render path first, then instrument,
then decide.** A blind human ranking run against `aa8d325` output would be scoring a show
whose movement never changes intensity and whose fixtures may be shuttered closed.

---

## 7. Comparison with simpler / modern alternatives

**Template authoring as Python code vs. data.** All 37 templates are Python modules
registered by import side effect. Adding template #38 means: create a file, import ~15
symbols, construct a nested `TemplateDoc` (~90 lines, of which ~55 are boilerplate
imports and structure), add it to `templates/builtins/__init__.py`, and reinstall the
package. There is no schema file, no validation CLI, no hot reload, no way for a non-Python
user to contribute. Since the models are already Pydantic, a YAML/JSON representation with
`TemplateDoc.model_validate` is a near-free alternative that would (a) make the library
user-extensible, (b) allow diffing/reviewing templates as data, (c) enable a template
linter that would have caught P4-F5 and P4-F6 mechanically. **Recommend: keep the Python
form as an authoring convenience, but make the loader data-first.** This is the single
highest-leverage modernization in the phase and it is small.

**Curve generation.** The 41-entry hand-rolled `CurveLibrary` over NumPy-free Python
functions is fine and does not need replacing — the outputs are 64-point polylines. The
*two* parallel parameterization APIs (legacy `**kwargs` vs. the categorical
adapter/taxonomy/protocol trio) should collapse to one; the categorical one is entirely
dead and has already drifted out of signature agreement with its own generators.
**[V] Restated precisely:** `adapt_bezier_params` (`curves/adapters.py:153`) emits a
`control_points` kwarg, but `generate_bezier` (`curves/functions/parametric.py:14`) takes
discrete `p1`/`p2` parameters and **has no structural way to consume a `control_points`
collection at all** — it is not a rename or a missing keyword but an incompatible shape,
absorbed silently by `**kwargs`. The adapter layer could never have worked against the
current generator. **Recommend: delete the categorical curve API** — `adapters.py`,
`taxonomy.py`, `protocols.py` (610 LOC) outright, plus `modifiers.py` (44 LOC) once its
importer at `curves/registry.py:10` is unwound (P4-F20). This also removes the layering
inversion.

**Timing.** `BeatGrid` + `TimeResolver` are a reasonable local implementation; there is no
compelling third-party alternative for bar/beat grids in this domain. The problem is not
the implementation but that the renderer bypasses it (P4-F2). No replacement needed —
a wiring fix.

**Intensity/categorical resolution.** Three independent implementations of "categorical
level → number" now exist: `sequencer/rendering/categorical_resolver.py` (dead),
`vocabulary/intensity.py::INTENSITY_MAP` (dead), and
`display/composition/engine.py:93 _INTENSITY_MAP` (live, display-only) — plus the
moving-heads `MovementCategoricalParams`/`DimmerCategoricalParams` tables, which are a
fourth and are the only ones on the shipped path. **Recommend: delete the two dead ones**
rather than unify; unification across the display/moving-heads split is a phase-5/8
decision, not a phase-4 one.

**Export.** The `E_SLIDER_DMX`/`E_VALUECURVE_DMX` string construction is inherently
xLights-specific; no library alternative exists. It should, however, be moved behind a
golden test before anything else changes.

---

## 8. Doc / context claims touching this phase

| Claim | Source | Status |
|---|---|---|
| "Renderer implements precision" / renderer owns every numeric | `memories/decisions/llm-plans-intent-renderer-implements-precision.md` | **Half-true, worse than Stage 2 stated.** The renderer does own the numerics, but the categorical *contract* the decision describes (`sequencer/vocabulary/`) is never imported by the moving-heads renderer (P4-F17). Stage 2 already flagged this decision; phase 4 supplies the decisive evidence. |
| Six channels choreographed | `docs/overview.md:24` | **Refuted.** Three channels (pan, tilt, dimmer). 0/37 templates reference color/gobo/shutter (P4-F16). |
| "BeatGrid is the sole timing authority" (strength) | discovery §3, manifest row "Timing & vocabulary" | **Refined to a defect.** BeatGrid is the sole *source*, but the moving-heads renderer consumes only its scalar average `ms_per_bar`; the detected per-bar boundaries reach the output only as timing tracks (P4-F2). |
| "vocabulary = planner/renderer contract" | manifest row "Timing & vocabulary" | **Refuted for moving heads.** True only for the display/group-planner side (P4-F17). |
| "Template registry deep-copy defaults" (strength) | discovery §5 | **Confirmed** (`templates/library.py:93`). |
| "Curve bounds double-enforced" (strength) | manifest row "Curves" | **Confirmed and then some** — 3–4 enforcement sites on the shipped pan path; the `curves/dmx_conversion.py` clamp is provably a no-op (P4-F9). More redundancy than the word "double" implies; it is defensive but has masked the calibration bug. |
| "simplify_rdp dead" | discovery §5 | **Confirmed** (`curves/simplification.py:65`, sole importer `tests/unit/curves/test_simplification.py:8`). |
| "dual legacy/categorical curve APIs" | discovery §5 | **Confirmed and sharpened**: the categorical API is 100% dead and signature-drifted (§7). |
| "triangle-phase TODO" | manifest | **Confirmed** (`curves/functions/basic.py:163`); `phase` is accepted, documented, and silently dropped. |
| "TRUNCATE/FADE_OFF remainder policies" (inherited confirmed finding) | phase brief | **Refined**: all 37 templates use `HOLD_LAST_POSE`; TRUNCATE and FADE_OUT are unreachable, and FADE_OUT is additionally broken by a case mismatch (P4-F21). |
| "transition cycle detection stubbed (TODO)" | discovery §5 | **Confirmed** (`compile/transition_detector.py:166`); additionally `detect_step_boundaries` (`:88`) has no production caller. |
| "movement handler production-hardening TODO" | discovery §5 | **Confirmed** (`handlers/movement/default.py:272`), and the surrounding code contains P4-F1. |
| "38 code-defined templates" | manifest row "Sequencer: moving heads" | **Corrected to 37** (AST count of `templates/builtins/*.py` excluding `__init__.py`), matching Stage 2's correction. |
| "46 enums / 266 members" in vocabulary | Stage 2 §"vocabulary design" prompt | **Corrected: 46 enums / 253 members** (AST count of all `class X(...Enum)` in `vocabulary/*.py` and their `NAME = value` assignments). Enum count confirmed; member count was overstated by 13. |

---

## 9. Architecture worth preserving

1. **The 37-template library and its metadata** — fully populated, discriminating, and
   the actual domain asset (P4-F24, P4-F25).
2. **`FixtureSegment` / `ChannelValue` as a channel-generic IR** — this is what makes
   adding color plumbing rather than redesign (P4-F16).
3. **The compile decomposition** (schedule → order → offset → step-compile → clip) and
   the three-registry handler seam.
4. **Deep-copying template registry** and effect-label provenance.
5. **`XsqAdapter` semantic grouping**, including its refusal to group phase-offset or
   non-identical segments.
6. **`BeatGrid` as an artifact** — the detected boundary lists are correct and already
   flow into the output's timing tracks; only the renderer's consumption is wrong.

---

## 10. Deterministic-selector feasibility — full template annotation table (V3)

All 37 registered builtins, extracted by AST from `templates/builtins/*.py`.
`E` = `energy_range`, `RS` = `recommended_sections`, `Cat` = `TemplateCategory`,
`G/M/D` = geometry / movement / dimmer types, `cyc` = `cycle_bars`.

| # | template_id | Cat | E | RS | tags | G / M / D | cyc |
|---|---|---|---|---|---|---|---|
| 1 | accent_snap_tunnel_hit | HIGH | 80–100 | drop, peak | accent_snap, tunnel, hit | TUNNEL_CONE / ACCENT_SNAP / PULSE | 4 |
| 2 | ambient_random_wash | LOW | 5–25 | intro, ambient, verse | ambient, random_walk, wall_wash, atmospheric | WALL_WASH / RANDOM_WALK / HOLD | 8 |
| 3 | ballyhoo_chaos | HIGH | 80–100 | drop, peak, breakdown | ballyhoo, chaos, random | SCATTERED_CHAOS / RANDOM_WALK / PULSE | 2 |
| 4 | bounce_fan_pulse | HIGH | 55–85 | chorus, drop | bounce, fan, pulse, phase_offset | ROLE_POSE / BOUNCE / PULSE | 4 |
| 5 | build_drop_recover | HIGH | 60–100 | drop, chorus | multi_step, build, drop, recover, transition | ROLE_POSE,TUNNEL_CONE,ROLE_POSE / SWEEP_LR,ACCENT_SNAP,GROOVE_SWAY / FADE_IN,PULSE,FADE_OUT | 2 |
| 6 | cascade_pulse_lr | MED | 45–80 | verse, groove, build | phase_offset, cascade, pulse | ROLE_POSE / HOLD / PULSE | 4 |
| 7 | circle_asym_left_strobe | HIGH | 70–100 | drop, peak | circle, asym, strobe | AUDIENCE_SCAN_ASYM / CIRCLE / PULSE | 4 |
| 8 | circle_asym_right_pulse | MED | 55–85 | chorus, drop | circle, asym, pulse | AUDIENCE_SCAN_ASYM / CIRCLE / PULSE | 4 |
| 9 | circle_fan_hold | MED | 35–60 | verse, bridge | circle, fan, hold | ROLE_POSE / CIRCLE / HOLD | 4 |
| 10 | crossfade_between_steps | MED | 40–75 | build, chorus | transition, crossfade, multi_step | FAN,CHEVRON_V / SWEEP_LR,PENDULUM / PULSE,HOLD | 4 |
| 11 | dual_sweep_audience_pulse | HIGH | 70–90 | chorus, drop | dual_sweep, audience, pulse | AUDIENCE_SCAN / DUAL_SWEEP / PULSE | 4 |
| 12 | fan_iris_tilt_bias_breathe | LOW | 15–40 | verse, bridge | fan_iris, tilt_bias, breathe | ROLE_POSE_TILT_BIAS / FAN_IRIS / PULSE | 4 |
| 13 | fan_pulse | MED | 40–70 | verse, chorus | fan, pulse, static | FAN / HOLD / PULSE | 4 |
| 14 | figure8_mirror_strobe | HIGH | 75–100 | drop, peak | figure8, mirror, strobe | MIRROR_LR / FIGURE8 / PULSE | 4 |
| 15 | groove_sway_rainbow_breathe | LOW | 15–40 | verse, intro | groove_sway, rainbow, breathe, gentle | RAINBOW_ARC / GROOVE_SWAY / PULSE | 4 |
| 16 | hold_center_out_breathe | LOW | 10–35 | verse, bridge | center_out, breathe, static, gentle | CENTER_OUT / HOLD / PULSE | 4 |
| 17 | infinity_mirror_chase | MED | 40–65 | verse, chorus | infinity, mirror, chase | MIRROR_LR / INFINITY / PULSE | 4 |
| 18 | inner_pendulum_breathe | LOW | 15–40 | verse | group_target, inner, pendulum | ROLE_POSE / PENDULUM / PULSE | 4 |
| 19 | intro_main_outro_phrase | MED | 35–70 | verse, chorus | phrase, multi_step, repeat | ROLE_POSE ×3 / HOLD,SWEEP_LR,HOLD / FADE_IN,PULSE,FADE_OUT | 4 |
| 20 | lean_right_scan | LOW | 10–40 | verse, groove | audience_scan, asymmetric | AUDIENCE_SCAN_ASYM / HOLD / HOLD | 4 |
| 21 | pendulum_chevron_breathe | LOW | 20–50 | verse, bridge | pendulum, chevron, breathe | CHEVRON_V / PENDULUM / PULSE | 4 |
| 22 | pop_lock_spotlight_blackout | HIGH | 75–100 | drop, peak | pop_lock, spotlight, blackout | SPOTLIGHT_CLUSTER / POP_LOCK / BLACKOUT | 4 |
| 23 | spiral_xross_blackout | HIGH | 70–95 | drop, breakdown | spiral, x_cross, blackout | X_CROSS / SPIRAL / BLACKOUT | 4 |
| 24 | split_lr_sweep_counter | MED | 40–65 | chorus, build | group_target, split, counter_sweep, left_right | WAVE_LR ×2 / SWEEP_LR ×2 / PULSE ×2 | 4 |
| 25 | stomp_tilt_bias_pulse | HIGH | 75–95 | drop, peak | stomp, tilt_bias, hit | TILT_BIAS_BY_GROUP / STOMP / PULSE | 4 |
| 26 | sweep_lr_chevron_breathe | MED | 40–70 | verse, chorus | sweep_lr, chevron, breathe | CHEVRON_V / SWEEP_LR / PULSE | 4 |
| 27 | sweep_lr_continuous_phase | MED | 35–60 | verse, chorus | loop_safe, sweep_lr, phase_offset | ROLE_POSE / SWEEP_LR / PULSE | 4 |
| 28 | sweep_lr_fan_hold | LOW | 25–50 | verse, bridge | sweep_lr, fan, hold, gentle | ROLE_POSE / SWEEP_LR / HOLD | 4 |
| 29 | sweep_lr_fan_pulse | MED | 45–75 | chorus, build | sweep_lr, fan, pulse | ROLE_POSE / SWEEP_LR / PULSE | 4 |
| 30 | sweep_lr_pingpong_phase | MED | 35–60 | build, chorus | loop_safe, ping_pong, sweep_lr, phase_offset | ROLE_POSE / SWEEP_LR / PULSE | 4 |
| 31 | sweep_ud_chevron_swell | MED | 40–70 | build, lift | sweep_ud, chevron, swell | CHEVRON_V / SWEEP_UD / PULSE | 4 |
| 32 | tilt_rock_wall_wash_fade | LOW | 10–35 | intro, verse | tilt_rock, wall_wash, fade_in, ambient | WALL_WASH / TILT_ROCK / FADE_IN | 4 |
| 33 | wave_fan_hold | LOW | 25–55 | verse, intro | wave, fan, hold, gentle | FAN / WAVE_HORIZONTAL / HOLD | 4 |
| 34 | wave_scattered_fade_in | MED | 35–60 | intro, build | wave_horizontal, scatter, fade_in | SCATTERED_CHAOS / WAVE_HORIZONTAL / FADE_IN | 4 |
| 35 | wave_scattered_fade_out | MED | 35–60 | outro | wave_horizontal, scatter, fade_out | SCATTERED_CHAOS / WAVE_HORIZONTAL / FADE_OUT | 4 |
| 36 | wave_vertical_spotlight_fade | MED | 30–55 | outro, bridge | wave_vertical, spotlight, fade_out | SPOTLIGHT_CLUSTER / WAVE_VERTICAL / FADE_OUT | 4 |
| 37 | zigzag_alternating_pulse | MED | 45–70 | chorus, build | zigzag, alternating, pulse | ALTERNATING_UPDOWN / ZIGZAG / PULSE | 4 |

**Population: 37/37 complete.** Every template has a non-empty `energy_range`,
`recommended_sections`, and `tags`. Zero sparse or missing annotations. Category
distribution: 9 LOW / 18 MEDIUM / 10 HIGH.

**Discrimination — section join.** 12 distinct section labels; the join is genuinely
partitioning, not degenerate:

| section | # templates | section | # templates |
|---|---|---|---|
| verse | 17 | breakdown | 2 |
| chorus | 14 | groove | 2 |
| drop | 11 | outro | 2 |
| build | 8 | ambient | 1 |
| peak | 6 | lift | 1 |
| bridge | 6 | intro | 5 |

**Discrimination — energy join.** Coverage is continuous and well-shaped across 0–100:
5 templates match at energy 10, 10 at 30, 19 at 50, 12 at 80, 6 at 100. Energy 0–4 has
zero matches (a trivial gap; the lowest `energy_range` floor is 5). Combining
`recommended_sections ∩ energy_range` narrows a typical `(chorus, energy=70)` query to a
handful of candidates.

**VERDICT on V3 — CONFIRMS Stage 2.** The annotations are **populated and discriminating**;
the deterministic selector is feasible on the data as it stands. Confirmed sub-claims:
(a) **37 templates, not 38** — AST count of `templates/builtins/*.py` (OBSERVED);
(b) `recommended_sections` **is loaded** into the planner context at
`agents/sequencer/moving_heads/stage.py:238` and carried on
`agents/sequencer/moving_heads/context.py:46`; (c) it is **never rendered into the prompt**
— `prompts/planner/user.j2:47` emits only `description`, `energy_range`, `tags` (OBSERVED,
full line read). The exact join column that would make the selector exact is computed,
carried, and then dropped one line before the model sees it.

**Phase 4 adds a caveat Stage 2 could not see.** The output space is smaller than Stage 2's
"193 discrete outcomes". `preset_id` resolves to at most **two** distinguishable renders
(P4-F8) and 7 templates are preset-invariant entirely, so the true per-section space is
**[V] 30 × 2 + 7 = 67**, and movement is identical
across all of them (P4-F1). This *strengthens* the deterministic-selector case
(the space is even more exhaustively testable) and simultaneously means **the A/B
experiment Stage 2 proposes cannot distinguish the arms until P4-F1 and P4-F8 are fixed** —
both arms currently render through the same two-outcome preset bottleneck.

---

## 11. Candidate findings

Severity: CRITICAL (wrong output every run) / HIGH / MEDIUM / LOW / INFO.
Confidence: HIGH (read directly, exhaustively grepped) / MEDIUM (analysis, needs runtime
confirmation) / LOW.
Disposition: FIX / DELETE / DOCUMENT / KEEP / DEFER.

---

### P4-F1 — Movement intensity is discarded; every show renders at `Intensity.SMOOTH`
**Severity: CRITICAL · Confidence: HIGH · Disposition: FIX (with P4-F1a)**

`handlers/movement/default.py:81`:

```python
def generate(self, params, n_samples, cycles, intensity: Intensity) -> MovementResult:   # :48-54
    ...
    intensity = params.get("intensity", Intensity.SMOOTH)                                 # :81
```

The caller-supplied `intensity` parameter is unconditionally overwritten by a lookup in
`params`. `params` is `movement_params`, built at `compile/step_compiler.py:95` as
`dict(step.movement.params)` plus `base_pan_norm`, `base_tilt_norm`, `calibration`,
`geometry`, and (injected at `handlers/registry.py:207`) `movement_pattern` — it never
contains an `"intensity"` key. The real value arrives via the parameter at
`step_compiler.py:113` (`intensity=step.movement.intensity`).

Confirmed the two are different containers: `Movement.intensity` is a model *field*
(`models/template.py:184`), and `apply_step_patch` (`compile/preset.py:41-42`) merges
preset patches into `movement_dict` — i.e. into the field, not into `params`. Exhaustive
grep for `"intensity"` as a dict key under `moving_heads/` returns only the preset patches
(`pipeline.py:201`, and four template files) and this line.

**Impact.** `DEFAULT_MOVEMENT_PARAMS` (`libraries/movement.py:61-67`) maps intensity to
`(amplitude, frequency, center_offset)`; pinned to SMOOTH that is always
`(0.4, 0.5, 0.5)`. Consequences: (1) the auto-synthesized energy preset
(`pipeline.py:199-206`, the path taken for 33/37 templates) has **zero effect on
movement**; (2) the hand-authored `gentle`/`intense` presets on 4 templates affect movement
only through their `cycles` patch, not intensity; (3) movement amplitude and frequency are
constant across the entire song regardless of section energy. INFERRED for the visual
result; OBSERVED for the code path. The verifier independently confirmed the overwrite is
unconditional with no surviving path.

**[V] The defect is not untested — it is PINNED BY A TEST.** This corrects the original
report, which listed handlers as zero-coverage.
`tests/integration/test_handler_categorical_params.py` exercises
`DefaultMovementHandler.generate` four times (`:23`, `:51`, `:84`, `:112`) and **every call
passes intensity twice** — once as `params={"intensity": …}` and once as the `intensity=`
argument (e.g. `:34` with `:43`, `:63` with `:69`). Production supplies only the argument.
So `test_handler_intensity_affects_curves_currently` (`:51`) asserts that higher intensity
yields more curve energy **and passes**, but only because the test itself injects the
`params` key that production never sets. Two of the four tests are literally named
`…_currently`, and the comment at `:25-26` acknowledges that "categorical params are
already extracted and passed to generate_curve". The test suite therefore encodes the
defect as intended behaviour. **Remediation must change this test, not merely add one** —
a fix that keeps these tests green has not fixed anything. §5's handlers row is corrected
accordingly.

**P4-F1a (blocking co-requisite) — larger than first stated. [V]** The movement handler
indexes `categorical_params_set[intensity]` at `:83` **with no membership guard**, unlike
the dimmer handler which guards at `handlers/dimmers/default.py:86-89`. AST census of all
`MovementPattern` constructions in `libraries/movement.py`: **29 patterns; 2 declare no
`categorical_params` at all** (falling back to the complete 5-entry
`DEFAULT_MOVEMENT_PARAMS`), **10 declare exactly one entry**
(`sweep_ud` `:270`, `circle`, `figure8`, `tilt_bounce` `:382`, `groove_sway`,
`trampoline`, `laser_snap` `:438`, `stomp`, `fan_iris`, `radial_fan`), and 17 declare two.
**Only 2 of 29 patterns cover all five intensities — so a naive fix at `:81` would raise
`KeyError` for 27 of 29 patterns** on any non-SMOOTH intensity. The fix is therefore not
one line: it is *guard + data fill-in across the movement library*, and the data half is
the bulk of the work (choosing amplitude/frequency/center values for ~100 missing
intensity entries is a choreographic judgement, not a mechanical edit).

**Relationship to assessments:** NEW — not anticipated by discovery or Stage 2. It is the
single most consequential defect found in this phase.

---

### P4-F2 — Three incompatible time grids; effects land on none of the ones the user sees
**Severity: CRITICAL · Confidence: HIGH (code) / MEDIUM (magnitude) · Disposition: FIX (spans phases 3+4)**

**[V] Three grids coexist, not two.** The original report identified grids A and B; the
verifier found a third that sits *upstream* of both and compounds the error.

*Grid 0 (the plan's bar numbers) — phase 3's code.* The section boundaries the planner is
given, and therefore the `start_bar`/`end_bar` the renderer receives, are produced by
`MovingHeadContext._ms_to_bar` (`agents/sequencer/moving_heads/context.py:246-271`, called
at `:194-195`). It converts with a **nominal tempo** (`self.tempo`, or a hard-coded 120 BPM
fallback at `:258-259`), anchored at 0 ms, and **floors**:
`bar_number = int(beat_number / beats_per_bar) + 1` (`:269`). The floor quantizes every
section start *down* to a bar boundary — an error of up to one full bar, ≈2 s at 120 BPM
in 4/4. So a chorus detected at 47.3 s is handed to the planner as a bar whose start the
renderer will place at 46 s.

*Grid A (effects).* `TemplateCompileContext._bar_to_ms` (`models/context.py:132`):
`int((bar - 1) * self.beat_grid.ms_per_bar)`. `BeatGrid.ms_per_bar`
(`timing/beat_grid.py:189-201`) is `(bar_boundaries[-1] - bar_boundaries[0]) /
(len(bar_boundaries) - 1)` — **a single song-wide average**. Every section start, every
step start, and every transition boundary
(`compile/transition_detector.py:69`, same formula) derives from it, anchored at 0 ms.

*Grid B (timing tracks).* `formats/xlights/sequence/timeline.py:128` writes a "Twinklr
Bars" marker at each `beat_grid.bar_boundaries[i]` and `:104` a "Twinklr Beats" marker at
each `beat_boundaries[i]` — the **actual detected** positions from librosa analysis
(`BeatGrid.from_song_features` → `from_resolver`, `beat_grid.py:125,47`; this is the
shipped construction path, called at `agents/sequencer/moving_heads/stage.py:136`).

Both are written by `export_to_xsq` into the same `.xsq` (`xsq_export.py:77-84` for tracks,
`:88-101` for effects).

**Divergence.** Grid 0 → Grid A contributes a quantization error of up to one bar (≈2 s at
120 BPM) on every section start, *before* Grid A → Grid B contributes
`bar_boundaries[i] - i·avg_ms_per_bar`: (a) a **constant offset** equal to
`bar_boundaries[0]` — the time of the first detected downbeat, non-zero for essentially
every real recording (intro silence, pickup bar) — plus (b) accumulated **drift** wherever
the tempo is not perfectly constant. The errors do not cancel; they are independent. The
user opens the sequence in xLights, sees the bar markers on the beat, and sees the
moving-head effects offset from them.

**Aggravating evidence. [V]** `BeatGrid.snap_to_nearest_bar` (`beat_grid.py:252`) exists
precisely for this and its docstring reads *"Critical for precise beat synchronization —
ensures effect timing aligns exactly with bar boundaries even if LLM-generated times are
slightly off."* Corrected from the original report: it has **zero callers repo-wide** —
the sole reference is one intra-class call from another `BeatGrid` method
(`beat_grid.py:344`); no consumer anywhere invokes it. `get_bar_start_ms` (`:218`) has
**zero callers of any kind**. The only consumers of `bar_boundaries`/`beat_boundaries`
outside `timing/` are `display/composition/{section_map,timing_resolver}.py` (unreachable
display pipeline) and `formats/xlights/sequence/timeline.py` (OBSERVED, exhaustive grep).
And `models/context.py:113-115` documents the *opposite* of what the code does:
*"Uses detected beat boundaries to stay synced with actual music, not tempo-based
calculation which can drift."*

**Relationship to assessments:** REFINES discovery's "BeatGrid sole-timing-authority
(strength)" into a defect. BeatGrid is the sole *source*; the renderer consumes one scalar
from it. Directly undercuts the "renderer implements precision" decision record.

**Fix shape — spans two phases. [V]** Phase 4 side: route `_bar_to_ms` through
`beat_grid.get_bar_start_ms(bar - 1)` with a bounds fallback to the average for bars past
the detected range. Phase 3 side: `_ms_to_bar` must round to the *nearest* detected
downbeat rather than flooring against a nominal tempo — ideally by taking the same
`BeatGrid` the renderer uses instead of a scalar tempo. Fixing only the phase-4 half leaves
the ≤2 s quantization in place, so the two must be sequenced together. Tracked as
**P4-M3** and as a cross-phase dependency in §12.

---

### P4-F3 — The exporter drives every unchoreographed DMX channel 1–16 to 0, including shutter
**Severity: HIGH · Confidence: HIGH (emitted bytes) / MEDIUM (physical effect) · Disposition: FIX**

`export/dmx_settings_builder.py:77-83`:

```python
for ch in range(1, max_channel + 1):
    if ch in channel_curves:
        parts.append(f"E_SLIDER_DMX{ch}=0")
    else:
        parts.append(f"E_SLIDER_DMX{ch}={int(channel_values.get(ch, 0))}")
```

`max_channel` has a floor of 16 and rounds up to a multiple of 16
(`_calculate_max_channel`, `:233-259`). `channel_values` is populated only from the
segment's channels, which are exactly PAN, TILT, DIMMER (`step_compiler.py:198-227`).
**Every other channel in 1–16 is emitted with an explicit value of 0**, whether or not the
fixture maps it and whether or not the user configured a default.

This repository's own model says what 0 means on the shutter: `ShutterLibrary.DMX_CLOSED =
0`, `DMX_OPEN = 255` (`libraries/shutter.py:53-54`).

**[V] Three separate declarations of channel convention exist; the exporter honours none
of them** (the third was added by the verifier):

1. `DmxChannelMapping.shutter_default = 255`, commented *"usually open"*
   (`config/fixtures/dmx.py:94-95`) — **zero readers** anywhere.
2. `JobConfig.is_channel_enabled` / `ChannelDefaults` (`config/models.py:565`, `:129`) —
   **zero readers**.
3. `config/adapter.py:77 get_max_channel` — computes the rig's *actual* highest DMX channel
   across pan, tilt, dimmer, fine channels, shutter, colour and gobo (`:99-115`) — **zero
   callers**. `DmxSettingsBuilder._calculate_max_channel` (`:233-259`) instead reinvents a
   floor-16 / round-up-to-16 rule from only the channels it happened to write.

Likewise `color_map`, `gobo_map`, `shutter_map`, `has_color_wheel`, `has_gobo_wheel`,
`color_change_ms`, `gobo_change_ms` — all declared, none read.

**Emitted bytes: certain.** That the settings string contains `E_SLIDER_DMX{ch}=0` for
every unwritten channel in the emitted window is OBSERVED and not in doubt.

**[V] Physical consequence: conditional — counter-evidence carried.** The zeroing only
reaches a channel that falls *inside* the emitted window. Because `_calculate_max_channel`
takes its maximum over written channels only (PAN/TILT/DIMMER) and rounds to 16, the window
is normally 1–16. **The only fixture configuration tracked in this repository puts the
shutter at channel 17** (`tests/unit/config/test_fixtures.py:399`, `shutter_channel=17`) —
outside the window, so for that profile no `E_SLIDER_DMX17` is emitted at all and the
console/model default governs. The no-light outcome therefore holds for fixtures whose
shutter is mapped within 1–16 (common on 12- and 16-channel moving heads) and **not** for
profiles like the one in-repo. Severity stays HIGH with the conditional stated.

**[V] Concrete Stage 4 test spec** (replaces the vague "inspect the output" instruction):
render one 4-bar section twice against two otherwise-identical fixture configs — one with
`shutter_channel=6`, one with `shutter_channel=17` — and assert on the emitted settings
string that (a) the first contains `E_SLIDER_DMX6=0`, and (b) the second contains no
`E_SLIDER_DMX17` token. That distinguishes "actively shuttered closed" from "left to the
console" and settles the no-audio/no-light question without needing physical hardware.

**Relationship to assessments:** EXTENDS V1 materially. Stage 2 asked what the exporter
emits for color/gobo/shutter; the answer is not "omitted" — it is **an active zero**
within the emitted window. That is a stronger claim than "unwired".

**Fix shape:** emit only mapped channels (using `get_max_channel`, which already exists),
or seed `channel_values` from `shutter_default`/`ChannelDefaults` before the loop. Small.

---

### P4-F4 — Sections shorter than one template cycle render nothing
**Severity: HIGH · Confidence: HIGH · Disposition: FIX**

`compile/scheduler.py:96-107`: when `duration_bars // cycle_bars == 0`, `schedule_repeats`
logs a warning and returns `ScheduleResult(instances=[])`. `compile_template` then produces
zero segments (`template_compiler.py:119` iterates an empty list) and the section is dark.
No exception, no validation failure — only a `logger.warning` that the CLI does not
surface at default verbosity.

**[V] Corrected census:** **34** templates have `cycle_bars = 4.0`, **1** has 8.0
(`ambient_random_wash`), **2** have 2.0 (`ballyhoo_chaos`, `build_drop_recover`) —
AST-verified; the original report said 35/1/2. Restating the consequence precisely:

- a **1-bar** section renders nothing for **all 37** templates (the smallest cycle is 2.0);
- a **1–3-bar** section renders nothing for **35 of 37** (the 34 at `cycle_bars=4.0` plus
  the one at 8.0);
- a **1–7-bar** section renders nothing for `ambient_random_wash`.

The `remainder_bars` is correctly reported in the result but nothing acts on it.

**Relationship to assessments:** NEW. It interacts with the "ultra-short-section bypass"
in the moving-heads planner flagged by discovery §3 (phase 3) — the two together determine
whether short sections can occur in practice. **Cross-phase dependency: phase 3 must state
whether the planner can emit a section shorter than 4 bars.**

**Fix shape:** for `num_complete_cycles == 0`, schedule one partial cycle and clip, or fall
back to the section's own duration. Either is a few lines.

---

### P4-F5 — The two narrative multi-step templates render only their middle step
**Severity: HIGH · Confidence: HIGH · Disposition: FIX**

`schedule_repeats` instantiates steps exclusively from `contract.loop_step_ids`
(`scheduler.py:116-130` via `_get_step_order`, `:206`). Steps defined on the template but
absent from `loop_step_ids` are **never scheduled**. AST extraction over all 37 templates
found exactly two with unscheduled steps:

| template | steps defined | `loop_step_ids` | never rendered |
|---|---|---|---|
| `build_drop_recover` | build (2 bars), drop (2), recover (2) | `["drop"]` | **build, recover** |
| `intro_main_outro_phrase` | intro (2), main (4), outro (2) | `["main"]` | **intro, outro** |

`build_drop_recover` advertises `tags=["multi_step","build","drop","recover","transition"]`
and `description` promising the arc; it renders a 2-bar `ACCENT_SNAP`/`PULSE` loop.
`intro_main_outro_phrase` (`tags=["phrase","multi_step","repeat"]`) renders only its
`SWEEP_LR`/`PULSE` middle. The `FADE_IN` and `FADE_OUT` dimmer steps in both — the only
places in the whole library where a template shapes its own entry and exit — are dead.

**Relationship to assessments:** NEW, and it materially reduces the effective library:
two of the three most sophisticated templates are silently degraded to single-step loops.

**Fix shape:** either author's error (`loop_step_ids` should list all three) or a scheduler
that plays non-loop steps once at entry/exit. The former is a two-line data fix; a
template linter would have caught it.

---

### P4-F6 — `split_lr_sweep_counter` overruns its section by 2× with no clipping
**Severity: HIGH · Confidence: HIGH · Disposition: FIX**

`schedule_repeats` computes `num_complete_cycles = duration_bars // contract.cycle_bars`
(`scheduler.py:92`) but advances the schedule clock by the **sum of the loop steps' own
`duration_bars`** (`:119-130`). Nothing checks that these agree. AST comparison across all
37 templates found one mismatch:

- `split_lr_sweep_counter`: `cycle_bars = 4.0`, `loop_step_ids = ["left_sweep",
  "right_sweep"]`, each step `duration_bars = 4.0` → **loop duration 8.0 bars per
  "cycle"**.

For a 16-bar section: `num_complete_cycles = 4`, scheduled span `4 × 8 = 32` bars. The
segments run 16 bars past the section end. Its `remainder_policy` is `HOLD_LAST_POSE`
(as with all 37), so `_clip_segments_to_boundary` (`template_compiler.py:211`) is **not**
invoked — clipping only runs for TRUNCATE/FADE_OUT, which no template uses (P4-F21).

**INFERRED downstream effect:** overlapping effects on the same xLights model on the same
layer. `XsqAdapter` places all non-transition segments on layer 0 (`xsq_adapter.py:84`)
and performs no overlap check; `_write_individual_effects` sorts by `(fixture_id, t0_ms)`
(`:167`) but does not detect collisions. xLights does not accept two effects overlapping in
time on one layer — Stage 4 should check whether the file loads at all when this template
is selected. `split_lr_sweep_counter` is recommended for `chorus, build`, so it is
selectable on a typical song.

**Relationship to assessments:** NEW.

**Fix shape:** validate `sum(step_durations[s] for s in loop_step_ids) == cycle_bars` at
registration time (would also have caught P4-F5), and clamp the schedule to
`duration_bars` regardless of remainder policy.

---

### P4-F7 — `HOLD_LAST_POSE` replays the last step's *movement* time-compressed instead of holding a pose
**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX or RENAME**

`scheduler.py:134-145` handles the remainder by appending another `ScheduledInstance` of
the last step spanning `remainder_bars`. `template_compiler.py:156` then compiles that
instance with `duration_ms = instance.duration_bars × ms_per_bar`, and
`step_compiler.py:109-133` generates the step's **full** movement curve across that
shortened window. A 1-bar remainder after a 4-bar cycle therefore replays the entire 4-bar
pan/tilt pattern **at 4× speed**, not a held pose.

**[V] The dimmer half of the original claim was wrong and is struck.** The dimmer handler
does *not* time-compress: it recomputes cycles from a musical period,
`computed_cycles = template_duration_ms / (period_bars × beat_grid.ms_per_bar)`
(`handlers/dimmers/default.py:120-126`), so a shorter window yields proportionally fewer
pulse cycles at the *same* musical rate. Dimmer behaviour across the remainder is correct.
The defect is confined to movement.

This is the remainder policy used by **all 37 templates**, so it fires on every section
whose bar count is not an exact multiple of `cycle_bars` — the common case.

**Relationship to assessments:** REFINES the inherited "remainder policies" finding.

---

### P4-F8 — `preset_id` collapses to two distinguishable renders
**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX**

Chain (all OBSERVED):

1. The planner prompt offers exactly three values: *"Optionally add `preset_id` (CHILL,
   MODERATE, ENERGETIC)"* (`agents/sequencer/moving_heads/prompts/planner/user.j2:162`).
   `PlanSection.preset_id` is an unconstrained `str | None`
   (`agents/sequencer/moving_heads/models.py:54`) — no enum, no validator.
2. The 4 templates that define real presets use ids `gentle` / `intense`
   (`templates/builtins/{sweep_lr_chevron_breathe,cascade_pulse_lr,pendulum_chevron_breathe,
   circle_fan_hold}.py`). The prompt never names them, so they are effectively
   unreachable.
3. Any other id falls to auto-synthesis via `ENERGY_TO_INTENSITY` (`pipeline.py:48`):
   CHILL→`SLOW`, MODERATE→`SMOOTH`, ENERGETIC→`DRAMATIC`, INTENSE→`FAST`.
4. Movement intensity is then discarded (P4-F1).
5. Dimmer intensity survives, but `DEFAULT_DIMMER_PARAMS` (`libraries/dimmer.py:34-38`)
   defines only `SMOOTH`, `DRAMATIC`, `INTENSE` — **no `SLOW`, no `FAST`** — and the
   handler falls back to SMOOTH for anything missing (`handlers/dimmers/default.py:86-89`).

Net: CHILL → SMOOTH dimmer; MODERATE → SMOOTH dimmer; ENERGETIC → DRAMATIC dimmer.
`Intensity.INTENSE` dimmer params are unreachable from any prompt-offered value.
**Two distinguishable outcomes.**

**[V] Corrected outcome count: ≈67, not ≈74.** A further 7 templates are entirely
preset-invariant because their only dimmer types are `HOLD` or `BLACKOUT`, both of which
declare a single `Intensity.SMOOTH` entry that every preset collapses onto
(`libraries/dimmer.py:66-88`): `ambient_random_wash`, `circle_fan_hold`, `lean_right_scan`,
`sweep_lr_fan_hold`, `wave_fan_hold`, `pop_lock_spotlight_blackout`,
`spiral_xross_blackout` (AST-verified). So the space is
**30 × 2 + 7 × 1 = 67** distinguishable per-section renders.
(For the two BLACKOUT templates that collapse is itself a defect — see P4-M2.)

**Relationship to assessments:** REFINES Stage 2's "~5 effective presets → 193 discrete
outcomes" to **2 effective presets → ≈67 outcomes**. Strategic conclusion unchanged and
strengthened: the deterministic-selector case gets better, and any A/B experiment run
before this is fixed is invalidated (§10).

---

### P4-F9 — Fixture calibration limits are arithmetically annihilated; emitted DMX can exceed the fixture's mechanical safe range
**Severity: HIGH (raised from MEDIUM by verifier) · Confidence: HIGH · Disposition: FIX**

`DmxSettingsBuilder._extract_channel_data` (`export/dmx_settings_builder.py:127`) branches
on `channel_value.offset_centered`. Exhaustive grep: `offset_centered=True` is set
**nowhere** in `packages/` or `tests/` — the only assignments are
`step_compiler.py:203,215,226`, all `False`. So `movement_curve_to_dmx`
(`curves/dmx_conversion.py:8`) is dead and pan/tilt take the dimmer branch.

`step_compiler.py:198-227` also never passes `clamp_min`/`clamp_max`/`base_dmx`/
`amplitude_dmx`, so `ChannelValue` defaults `0`/`255` apply (`channels/state.py:53-54`)
and `dimmer_curve_to_dmx` computes `(0 + v·255)/255 = v` — **an identity function**.

Calibration is read (`handlers/movement/default.py:95-98`) and converted to
`pan_max_amplitude_norm`/`tilt_max_amplitude_norm` (`:118,:122`), but that value is used
only to scale the *centre offset* at `:268`; the actual amplitude limiting at `:310` uses
`1.0 - adjusted_base_norm` / `adjusted_base_norm`, i.e. the full 0–255 span.

**[V] The one surviving use of the calibration is arithmetically annihilated, so the
severity is HIGH, not MEDIUM.** The centre offset is
`center_offset_normalized = (center - 0.5) * max_amplitude_norm * 1.0`
(`handlers/movement/default.py:268`). Every `MovementCategoricalParams` in the library
declares `center_offset = 0.5` — it is the field default (`libraries/movement.py:19-21`)
and no pattern overrides it. So `(0.5 - 0.5) * max_amplitude_norm = 0` **identically**:
the calibration-derived term is multiplied by zero at the only place it is consumed.
Calibration has *no* effect on emitted DMX by any route.

*Worked example.* A fixture calibrated to `tilt_min_dmx=110, tilt_max_dmx=145` (a narrow,
physically-safe tilt window) with a base tilt at the centre of that window
(`base_tilt_norm = 0.5`) and `Intensity.SMOOTH` (`amplitude = 0.4`):
`desired_amplitude = 0.4 × 0.5 = 0.2` (`:301`); the excursion limits at `:308-310` are
`1.0 − 0.5 = 0.5` and `0.5 − 0.0 = 0.5`, so `effective_amplitude = 0.2` — **the calibrated
window never enters the calculation**. Output spans `0.5 ± 0.2` → normalized `[0.3, 0.7]` →
**DMX 76.5–178.5**, against a calibrated safe range of `[110, 145]`. Nothing downstream
re-clamps: `dimmer_curve_to_dmx` is the identity (above) and `ChannelValue.clamp_min/max`
are left at `0`/`255`. On a physical moving head this is mechanical-limit exposure, not an
aesthetic issue. INFERRED (analytic; the venv is unpopulated so it was not executed) —
Stage 4 should confirm by rendering with a narrow calibration and reading the emitted
value curve.

**Relationship to assessments:** NEW; surfaced by the delegated curves review, verified
independently here (`offset_centered` and `clamp_*` greps re-run), and raised to HIGH by
the phase verifier on the annihilation argument above.

---

### P4-F10 — Value curves are quantized to 2-decimal places, discarding ~8× the channel's resolution
**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX**

`export/dmx_settings_builder.py:291-293` rounds both `t` and `v` to two decimals before
emitting `Values=t:v;…`. The curve header declares `Min=0.00|Max=255.00` (`:321-322`), so
a `v` resolution of 0.01 is **2.55 DMX steps**. Every value curve on the shipped path is
affected; slow fades will show visible stepping. Additionally, `t` at 2 dp produces
**duplicate time keys** for any `n_samples > 100` (currently safe: `n_samples` is fixed at
64, grid step 0.015625). Emitting 3–4 decimals is a one-character change per format string.

---

### P4-F11 — `PING_PONG` is a no-op for 35 of 37 templates
**Severity: LOW · Confidence: HIGH · Disposition: DOCUMENT or FIX**

`_get_step_order` (`scheduler.py:206-225`) implements PING_PONG solely as reversing the
*order of `loop_step_ids`* on odd cycles. **[V] 35 of 37** templates have a single loop
step (corrected from 34; AST-verified — §10), so reversal is a no-op; only
`crossfade_between_steps` and `split_lr_sweep_counter`
(two loop steps each) are affected. Nothing reverses the *curve direction*.
`sweep_lr_pingpong_phase` — named and tagged `ping_pong` — has `loop_step_ids=["main"]`
and therefore repeats an identical sweep rather than sweeping back and forth. Choreographic
intent is not delivered.

---

### P4-F12 — Three Lissajous movement patterns trace a straight diagonal line
**Severity: MEDIUM · Confidence: HIGH (raised from MEDIUM by verifier) · Disposition: FIX**

**[V] Attribution corrected.** The registry default is the *starting* condition, not the
defect by itself: `curves/library.py:197-203` and `:246-251` both register the Lissajous
generators with `params = DEFAULT_PARAMETRIC_PARAMS | {"b": 2, "delta": 0}`, overriding the
generator's own `delta = π/2` (`curves/functions/parametric.py:55`). Pan and tilt invoke the
*same* generator, so a pattern must supply a per-axis phase difference to get a
two-dimensional figure. The mechanism for doing so exists and works:
`_filter_base_params("curve", "tilt", …)` (`handlers/movement/default.py:182-186`) strips
the prefix with `removeprefix`, so a `base_params` key `curve_tilt_delta` arrives at the
tilt generator as `delta`.

The defect is that **three of the four Lissajous patterns never set it**:
`MovementType.INFINITY` (`libraries/movement.py:304-313`), `SPIRAL` (`:513-522`) and
`CROSS_PATTERN` (`:577-586`) declare `pan_curve` and `base_tilt_curve` as Lissajous with no
`curve_tilt_delta`, so both axes get `delta = 0` and are **numerically identical (verified
equal to 1e-12)** — the fixture traces a straight diagonal, not an infinity, spiral, or
cross. Affects templates `infinity_mirror_chase` and `spiral_xross_blackout`.

Secondary: `SPIRAL` and `CROSS_PATTERN` reference `CurveLibrary.LISSAJOUS`, which is
registered as `CurveKind.DIMMER_ABSOLUTE` (`library.py:200`), not `MOVEMENT_LISSAJOUS`,
so they also take the wrong branch in `_generate_curve` — a second, independent bug in the
same three patterns.

Fix: add `curve_tilt_delta` to the three patterns (as `FIGURE8` does at
`libraries/movement.py:298`) and point them at `MOVEMENT_LISSAJOUS`. See P4-M7 for why
`FIGURE8`'s escape is only partial.

---

### P4-F13 — Curve-level `amplitude` cancels in `center_curve` — LATENT, zero current effect
**Severity: LOW / latent (lowered from MEDIUM by verifier) · Confidence: HIGH · Disposition: DEFER**

`curves/functions/movement.py:21` post-processes with `center_curve`, which rescales
`(v-min)/(max-min)` (`curves/semantics.py:36-37`). For `generate_sine`
(`0.5 + 0.5·a·sin θ`) the amplitude `a` cancels exactly; likewise `generate_triangle` and
`generate_pulse`. Affects `MOVEMENT_SINE`, `MOVEMENT_TRIANGLE`, `MOVEMENT_PULSE`,
`MOVEMENT_LINEAR`, `MOVEMENT_HOLD`.

**[V] Current impact is nil, so this is latent rather than active.** The handler
**deliberately does not pass amplitude to the curve generator** — `curve_params`
(`handlers/movement/default.py:280-286`) contains only `cycles`, `frequency` and filtered
base params, with an explicit comment at `:283-284`: *"amplitude is NOT passed here — it's
applied to the generated curve below"*. The generator therefore always receives the
registry default `DEFAULT_MOVEMENT_PARAMS["amplitude"] = 1.0` (`curves/defaults.py:24-28`).
A constant 1.0 cancelling to 1.0 changes nothing. Intensity amplitude does reach the output,
via the post-hoc scaling path at `handlers/movement/default.py:301-330`.

The finding is retained because it is a **trap for the P4-F1 fix**: anyone restoring
intensity plumbing who assumes the curve-level `amplitude` kwarg is the lever will find it
silently inert for these five families. Correcting the original report: this does *not*
block P4-F1, since the working lever is the scaling path.

---

### P4-F14 — Phase-shift wrap seam — NOT the source of the flat tail
**Severity: INFO (lowered from LOW by verifier) · Confidence: HIGH · Disposition: DOCUMENT**

The mechanism described in the original report is real but **fully masked on the movement
path**, and the flat tail that is actually observable in output comes from somewhere else.

*What was claimed:* `curves/phase.py:57` wraps shifted time with `% 1.0`, but
`interpolate_linear` (`curves/sampling.py:65-66`) is not cyclic and returns `points[-1].v`
for `t >= points[-1].t`; since `sample_uniform_grid` excludes 1.0 the last input `t` is
`(n-1)/n`, so `t_shifted ∈ ((n-1)/n, 1.0)` returns a constant.

*[V] Why it does not bite:* every movement curve passes through `ensure_loop_ready`
(`curves/functions/movement.py:22`), which appends a point at exactly `t=1.0`
(`curves/semantics.py:77`). With that point present, `points[-1].t == 1.0` and the
non-cyclic branch is unreachable for the entire `[0,1)` domain. Movement curves are the
only ones that carry phase offsets.

*[V] The real flat-tail mechanism is in the exporter, not the curve layer:*
`DmxSettingsBuilder._curve_points_to_xlights_string` appends an anchor at `t=1.00` carrying
the **last point's value** whenever the final point falls below `t=0.99`
(`export/dmx_settings_builder.py:307-310`). That is what emits a held final value into the
`.xsq`, and it applies to every channel including dimmers. It is benign for loop-ready
movement curves and is the same code path implicated in P4-M5.

Retained as INFO because the non-cyclic interpolation remains a latent trap if
`ensure_loop_ready` is ever removed. Test coverage of `apply_phase_shift_samples` is still
two error-path tests only (`tests/unit/curves/test_phase.py:18,23`) — no test asserts a
shifted value.

---

### P4-F15 — Template step timing fields `mode`, `quantize_type`, `start_offset_bars` are inert
**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX or DELETE**

Every one of the 37 templates declares
`BaseTiming(mode=TimingMode.MUSICAL, start_offset_bars=0.0, quantize_type=QuantizeMode.DOWNBEAT)`.
The compiler reads **only** `duration_bars` (`template_compiler.py:106,168`). Exhaustive
grep confirms `quantize_type` and `start_offset_bars` have no reader under
`sequencer/moving_heads/`; the quantization machinery that would honour them
(`timing/resolver.py:291-337`) operates on a **different** model — `timing/models.py::MusicalTiming`
— which the moving-heads path never constructs. A template author writing
`start_offset_bars=2.0` gets silent no-op. This is the same defect class as
`token_budget`/`is_channel_enabled` flagged by Stage 2 §8 item 5 (dead configuration
surfaces as a class) — **phase 4 contributes three more members to that class**, plus the
fixture-config members listed in P4-F3.

Related: there are **two `QuantizeMode` enums** — `sequencer/models/enum.py:11` (UPPER-ish
lower values, used by templates) and `sequencer/vocabulary/timing.py:83` (lower values,
used by display) — with no relationship.

---

### P4-F16 — Color, gobo and shutter are unwired end-to-end (V1)
**Severity: HIGH (product) · Confidence: HIGH · Disposition: FIX (strategic — Stage 8)**

**VERDICT: CONFIRMS Stage 2, and extends it in three directions. [V] The verifier
re-derived the entire evidence set — all ten zero-reader configuration fields — and
confirmed it clean.**

*Confirmed exactly as claimed:*
- **0 of 37 templates reference color, gobo or shutter.** Case-insensitive grep for
  `color|gobo|shutter` over the entire `templates/` tree returns **zero matches** in any
  file (OBSERVED).
- **`ColorLibrary`, `GoboLibrary`, `ShutterLibrary` have zero consumers.** Exhaustive grep
  over `packages/`, `tests/`, `scripts/` returns only their own definitions
  (`libraries/color.py:67`, `libraries/gobo.py:59`, `libraries/shutter.py:46`) — **not even
  a test imports them**. 643 LOC.
- **`JobConfig.is_channel_enabled` (`config/models.py:565`) and `ChannelDefaults`
  (`:129`) are never read** — only defined and referenced in their own docstrings.
- **[V] A third channel-convention declaration also goes unread**: `get_max_channel`
  (`config/adapter.py:77`) computes the rig's true highest DMX channel *including* shutter,
  colour and gobo (`:99-115`) and has **zero callers**; the exporter substitutes its own
  floor-16/round-to-16 rule (P4-F3). All three declared conventions are honoured nowhere.
- **DMX addressing exists.** `ChannelName.{COLOR,GOBO,SHUTTER}` (`models/enum.py:166-171`),
  the mapping in `DmxSettingsBuilder._get_dmx_channel_number` (`:162-164`), and the
  inversion flags (`:209-219`) are all present and correct.
- **The shipped product choreographs pan, tilt, dimmer only** — `step_compiler.py:198-227`
  adds exactly those three channels and no other code path adds any.

*Extension 1 — what the exporter emits is worse than "nothing":* it emits an explicit
**zero** (P4-F3), which on the shutter means closed by this repo's own constant.

*Extension 2 — a dead runtime channel layer:* `ChannelState` (`channels/state.py:215-357`), the
class that maps logical channels to DMX including COLOR/GOBO/SHUTTER (`:226-233`), applies
inversion and clamping, has **zero importers** — only `FixtureSegment` and `ChannelValue`
from that module are imported anywhere. It is a complete, unused implementation of the
runtime channel layer.

**ASSESSMENT — how hard is adding color? PARAMETER PLUMBING, not structural redesign.**
This is the answer Stage 2 needs for its co-primary option (c).

*Already built and correct:* the IR is channel-generic (`FixtureSegment.channels` is an
open `dict[ChannelName, ChannelValue]`); the exporter already writes any mapped channel
with correct inversion; fixture config already carries `color_channel`/`gobo_channel`/
`shutter_channel` plus `color_map`/`gobo_map`/`shutter_map`/`shutter_default`
(`config/fixtures/dmx.py:91-131`); `ColorLibrary` already defines 14 presets with DMX wheel
positions (`libraries/color.py:26-41`) and `ShutterLibrary` 6 patterns.

*Actually missing:*
1. A fourth axis on `TemplateStep` (`models/template.py:328-337`) — e.g.
   `color: Color | None`, mirroring `Dimmer`. **~40 LOC.**
2. A `ColorHandler` protocol + registry + default handler, mirroring `DimmerHandler`
   (`handlers/protocols.py:169`, `handlers/registry.py:219`,
   `handlers/dimmers/default.py`). **~250 LOC**, structurally identical to existing code.
3. Three lines in `step_compiler.py` to emit the channel; one line in
   `handlers/defaults.py:152` to register.
4. **Re-authoring 37 Python template files** — the real cost, and it is mechanical but
   manual because templates are code (§7). ~37 × 10 lines.
5. Widening the planner contract: a color field on `PlanSection` and a prompt section.
   Phase 3 seam.

*One genuine design question, not a blocker:* a colour **wheel** is a discrete DMX index
(`ColorPresetDefinition.dmx_value`, `libraries/color.py:62`), not a continuous curve, so
colour changes are step functions with a mechanical settling time
(`capabilities.py:44 color_change_ms`, currently unread). The `ChannelValue.static_dmx`
branch already models exactly this. RGB-mixing fixtures would need three channels, which
the current `DmxChannelMapping` does not model — but that is an additive config change.

**Conclusion for Stage 2/8:** the "widen the channel" option (c) is **substantially
cheaper than Stage 2 assumed**. The renderer-side work is ~300 LOC of code that mirrors
an existing family; the bulk is template re-authoring, which argues strongly for the
data-first template loader recommended in §7 — do that first and the 37-template
re-authoring becomes a data edit rather than 37 Python diffs.

---

### P4-F17 — `sequencer/vocabulary/` never reaches moving-heads rendering (V-categorical)
**Severity: HIGH (as a contract claim) · Confidence: HIGH · Disposition: DOCUMENT + DELETE dead members**

**VERDICT: REFUTES the "vocabulary = planner/renderer contract" framing for moving heads;
CONFIRMS Stage 2's flagged conflict with the `llm-plans-intent-renderer-implements-precision`
decision record.**

*Census (AST over `vocabulary/*.py`):* **46 enum classes, 253 members** — enum count
matches the prior estimate; **member count corrected from 266 to 253**. Value-casing is
inconsistent: 40 enums use UPPER string values, 5 use lower (`TargetType`, `GPBlendMode`,
`BackgroundMode`, `SnapMode`, `QuantizeMode`), 1 mixed (`MatrixAspect`).

*Reachability (OBSERVED, exhaustive grep):* **zero files under
`sequencer/moving_heads/`, `core/curves/`, `sequencer/models/`, or `core/resolvers/` import
`sequencer.vocabulary` at all.** Importers by package: `sequencer/templates/assets` (14),
`sequencer/templates/group` (13), `sequencer/display` (10), `agents/sequencer/group_planner`
(7), `recipe_builder` (3), `agents/assets` (3), `feature_engineering` (3),
`sequencer/planning` (2), `sequencer/timing` (2 — `TimeRefKind` only),
`agents/sequencer/macro_planner` (1), `sequencer/rendering` (1 — the dead resolver), plus
theming and CLI. **Every one of these except `sequencer/timing` is on the display /
group-planner side, which discovery §2 established is unreachable from the CLI.**

*The moving-heads categorical contract is a different, unrelated set:* `Intensity`,
`ChaseOrder`, `SemanticGroupType`, `TemplateCategory`, `QuantizeMode`, `TimingMode`,
`ChannelName`, `BlendMode`, `TransitionMode` — all in `sequencer/models/enum.py`.

*Decisive evidence on the intensity question the brief asked about:*
`Intensity` (`models/enum.py:111`; members SLOW, SMOOTH, FAST, DRAMATIC, INTENSE) and
`IntensityLevel` (`vocabulary/intensity.py:11`; members WHISPER, SOFT, MED, STRONG, PEAK)
are **two entirely separate enums with no conversion function anywhere in the repository**.
The moving-heads numerics come from `MovementCategoricalParams`/`DimmerCategoricalParams`
tables keyed by `Intensity` (`libraries/movement.py:61`, `libraries/dimmer.py:34`);
`IntensityLevel` resolves via `display/composition/engine.py:93 _INTENSITY_MAP` on the
display side. `Intensity.amplitude` (`models/enum.py:132`) — a property that looks like the
bridge — has zero callers.

*Where `IntensityLevel`/`EffectDuration` resolve for moving heads:* **they do not.** The
moving-heads planner emits no categorical value at all — `PlanSection`
(`agents/sequencer/moving_heads/models.py:31`) carries `template_id: str`, `preset_id: str`,
`modifiers: dict[str,str]`, `reasoning: str`, `section_role: str|None`,
`energy_level: int|None`, and `TransitionHint`. **Not one field is typed with a vocabulary
enum.**

*Dead vocabulary members:* `vocabulary/intensity.py:35 INTENSITY_MAP` (sole consumer is the
dead `categorical_resolver.py:16,67`) and `:44 resolve_intensity` (zero consumers).

**Implication for the decision record.** `memories/decisions/llm-plans-intent-renderer-implements-precision.md`
describes a categorical-vocabulary contract between planner and renderer. That contract is
real — for the display pipeline, which does not ship. For the moving-heads path the LLM
emits two free-form strings and the renderer's categorical layer is a private enum the
planner has never heard of. Stage 8 must reconcile the record.

---

### P4-F18 — `sequencer/rendering/categorical_resolver.py` is dead, not merely untested
**Severity: MEDIUM · Confidence: HIGH · Disposition: DELETE**

**VERDICT: answers the brief's V-categorical question — it is DEAD.** Exhaustive grep for
`CategoricalResolver`, `ResolvedPlacement`, `categorical_resolver`, and
`sequencer.rendering` across `packages/`, `tests/`, `scripts/` returns hits only inside
`sequencer/rendering/__init__.py` (re-exports) and the file itself. **No module anywhere
imports `twinklr.core.sequencer.rendering`.** No dynamic-import mechanism exists that could
reach it (the only `importlib` uses in the tree are `pkgutil.extend_path` and
`importlib.metadata`). 218 LOC, zero coverage — the coverage gap the critic flagged is a
consequence of deadness, not a separate problem.

Had it been live it would map `PlanningTimeRef → ms` (`:69-98`),
`EffectDuration → end_ms` (`:100-140`), and `IntensityLevel × LaneKind → float`
(`:142-157`). It also carries a latent bug: `int(bar_start + beat_offset + hint_offset)`
(`:98`) can go negative for an `ANTICIPATE` hint on bar 1 with no guard.

**Manifest update required:** the row "Sequencer: planning/models/rendering" should record
`rendering/` as DEAD (delete candidate), not "zero test coverage".

---

### P4-F19 — `core/resolvers/poses.py` is 100% dead
**Severity: MEDIUM · Confidence: HIGH · Disposition: DELETE**

First review of this package. Exhaustive grep for `PoseResolver`, `resolvers.poses`,
`core.resolvers` over `packages/`, `tests/`, `scripts/`, `utils/` returns hits only inside
the file itself and in this review's own documents. `core/resolvers/__init__.py` is
**0 bytes** — it does not even re-export the class. Zero test coverage confirmed.

It is **not** on the render path: pose resolution happens through a separate normalized
mechanism, `PanPose(...).norm_value` / `TiltPose(...).norm_value`
(`handlers/geometry/role_pose.py:119-125`, tables at `config/poses.py:124-137,163-175`).

Latent defects if ever revived: three colliding casing conventions between
`_normalize_pose_id` (uppercases, `config/poses.py:73-79`), the dict keys used by
`_build_pose_library` (`resolvers/poses.py:198-199`, verbatim), and `resolve_pose`
(lowercases then falls through un-normalized, `:87-93`); `_validate_ranges` limits
(±270 pan / ±135 tilt, `:219-223`) are strictly wider than the pydantic constraints on
`Pose` (±180 / ±90, `config/poses.py:62-68`), so the clamp can never fire on a base pose;
pan offsets clamp rather than wrap (`:141-142`), which is wrong for a rotational axis; and
the degrees table and the normalized table are **not interconvertible by any single linear
transform** (−60°→0.3 and 0°→0.5 implies 300° full scale; −120°→0.1 and −90°→0.2 imply 300°
and 600°).

---

### P4-F20 — Dead code inventory for the phase
**Severity: LOW (individually) / MEDIUM (aggregate) · Confidence: HIGH · Disposition: DELETE**

**[V] Two rows were rejected and are re-labelled below.** `curves/modifiers.py` and
`curves/providers/native.py` are **imported at module level** — by `curves/registry.py:10`
and `curves/generator.py:11` respectively — so deleting either file breaks the build. They
are *unreachable at runtime*, not deletable-as-is; removing them requires unwinding the
importer first. Every other inventory row was confirmed exact by the verifier.

≈1,900 LOC in phase-4 scope that is dead or unreachable at runtime:

| Item | Path | LOC | Note |
|---|---|---|---|
| `PoseResolver` (whole file) | `core/resolvers/poses.py` | 242 | P4-F19 — safe delete |
| Categorical resolver (whole package) | `core/sequencer/rendering/` | 218 | P4-F18 — safe delete |
| Colour/gobo/shutter libraries | `moving_heads/libraries/{color,gobo,shutter}.py` | 643 | P4-F16; **keep if option (c) is chosen** |
| `ChannelState` | `moving_heads/channels/state.py:215-357` | 143 | P4-F16 ext. 2 — safe delete |
| `curves/adapters.py` | | 332 | safe delete; + removes layering inversion |
| `curves/taxonomy.py` | | 151 | **no importer at all, not even a test** — safe delete |
| `curves/protocols.py` | | 127 | **no importer at all** — safe delete |
| `curves/simplification.py` | | 128 | confirmed by discovery — safe delete |
| `curves/composition.py` | | 89 | safe delete |
| `curves/modifiers.py` | | 44 | **[V] NOT deletable as-is** — imported by `curves/registry.py:10`; unreachable at runtime because `CurveDefinition.modifiers` is never set in prod |
| `curves/providers/native.py` + `generate_native_spec`/`tune_native_spec` | | 116+ | **[V] NOT deletable as-is** — imported by `curves/generator.py:11`; instantiated but never exercised |
| `curves/dmx_conversion.py:8 movement_curve_to_dmx` | | ~30 | P4-F9 |
| `PhaseOffsetResult.get_normalized`, `calculate_normalized_offset` | `compile/phase_offset.py:33,128` | ~25 | zero callers incl. tests |
| `Movement.get_categorical_params` → `CURVE_INTENSITY_PARAMS` (~100 lines) + `get_curve_categorical_params` | `models/template.py:193`, `libraries/movement.py:72,178` | ~130 | tests exist (`test_curve_intensity_params.py`) but no prod caller |
| `Intensity.amplitude` | `models/enum.py:132` | 15 | |
| `vocabulary/intensity.py` `INTENSITY_MAP` + `resolve_intensity` | | ~20 | |
| `TransitionDetector.detect_step_boundaries` / `detect_cycle_boundaries` | `compile/transition_detector.py:88,148` | 80 | latter is a TODO stub |

---

### P4-F21 — `FADE_OUT` remainder policy is unreachable and additionally broken by a case mismatch
**Severity: LOW · Confidence: HIGH · Disposition: FIX or DELETE**

All 37 templates use `HOLD_LAST_POSE` (§10), so `TRUNCATE` and `FADE_OUT` — and therefore
the 148 lines of `_clip_segments_to_boundary` / `_clip_curve_points` / `_apply_fade_out`
(`template_compiler.py:304-451`) — are **never reached on the shipped path**. Independently,
the fade gate at `template_compiler.py:349` tests `channel_name.value == "DIMMER"` while
`ChannelName.DIMMER.value == "dimmer"` (`models/enum.py:166`), so FADE_OUT would degenerate
to a hard truncate even if selected. **REFINES** the inherited "TRUNCATE/FADE_OFF remainder
policies" finding from a behaviour concern to dead-and-broken code. Note the clipping code
is also what P4-F6 needs, so repair rather than delete.

---

### P4-F22 — Test mass is inverted relative to risk; the render integration test mocks the compiler
**Severity: HIGH · Confidence: HIGH · Disposition: FIX**

See §5. Headline: 64% of moving-heads test lines cover transitions, and
`test_rendering_pipeline.py:262` patches `compile_template` so the one end-to-end render
test never executes the compiler, handlers, curves or exporter.

**[V] Two scope corrections that change the remediation, not the conclusion:**

1. **`XsqAdapter` is not untested.** It has four integration tests covering layer
   assignment — `tests/integration/test_transitions_multi_layer.py:74,117,188,223`. What is
   untested is the *content* path: settings-string construction and the grouping decision.
   `dmx_settings_builder.py` and `xsq_export.py` still have **zero** direct tests.
2. **A DMX validator already exists and is unit-tested.**
   `scripts/validation/_core/mh_xsq_validation.py` (587 LOC, covered by
   `tests/unit/scripts/validation/test_mh_xsq_core_validation.py`, driven by
   `scripts/validation/validate_artifacts.py`) already parses `E_SLIDER_DMX` and
   `E_VALUECURVE_DMX` entries (`:77`), **flags all-zero effects as CRITICAL**
   (`:272-297` — "NO ACTUAL MOVEMENT IMPLEMENTED"), and cross-checks shutter/colour/gobo
   channels against the fixture map (`:414-416`, `:452-454`). It is post-hoc and
   **not wired into CI or `make validate`**.

The consequence is that the highest-value remediation is **cheaper than first stated**: it
is *wire the existing validator into CI and add a golden settings string*, not *write a
validator*. Tracked as **P4-M8**; §13 step 1 is rewritten accordingly. A golden test over
`DmxSettingsBuilder.build_settings_string` for one 4-bar section would still have caught
P4-F1, F3, F7, F9, F10, M1, M2 and the effects of F5 and F6 — and the existing validator's
all-zero check would plausibly have caught P4-F3 and P4-M1 on any real run. **This must
land before any of the fixes, so the fixes are verifiable.**

---

### P4-F23 — Only five plan fields reach the renderer (V2)
**Severity: INFO · Confidence: HIGH · Disposition: DOCUMENT**

**VERDICT: CONFIRMS Stage 2 with one refinement.** `TemplateCompileContext`
(`pipeline.py:226-238`) is built from exactly `section_name`, `start_bar`, `end_bar`,
`template_id`, `preset_id`. Exhaustive grep across `packages/twinklr/core/sequencer/`
confirms the discards: `modifiers`, `reasoning`, `section_role`, `energy_level` and
`transition_out` are copied into the flattened `PlanSection` by `iterate_plan_sections`
(`pipeline.py:303-313`) and **never read by anything** — no transition code, no preset
code, no caching, no export. `overall_strategy` has zero readers in `sequencer/` at all.
The only non-`sequencer/` reader of `transition_out` is
`reporting/evaluation/generator.py:77`, which reconstructs a plan for the offline eval
tool.

**Refinement to "exactly five":** a **sixth** field is read — `transition_in`, at
`pipeline.py:350`, when `job_config.transitions.enabled` (default `True`,
`config/models.py:462`). In practice it is almost certainly always `None`: the moving-heads
planner prompts contain no instruction to emit a structured `TransitionHint`
(`prompts/planner/{system,user}.j2` mention transitions only in prose —
`system.j2:13,34,50`, `user.j2:147`), so `plan_transition` falls to
`_create_default_hint()` from config. So the accurate statement is: **five fields are read
unconditionally; a sixth is read but never populated.** Also read is `segments`, consumed
by the flattening itself (`pipeline.py:297`).

---

### P4-F24 — Template library quality: 37 genuinely distinct templates
**Severity: INFO (positive) · Confidence: HIGH · Disposition: KEEP**

**34 of 37 (geometry, movement, dimmer) combinations are unique.** Two clusters repeat:
`(ROLE_POSE, SWEEP_LR, PULSE)` ×3 — `sweep_lr_fan_pulse`, `sweep_lr_continuous_phase`,
`sweep_lr_pingpong_phase`, which differ in repeat mode, phase-offset config and poses, so
they are defensible variants rather than duplicates — and
`(AUDIENCE_SCAN_ASYM, CIRCLE, PULSE)` ×2 (`circle_asym_left_strobe` /
`circle_asym_right_pulse`, left/right mirrors). Vocabulary breadth: **17 geometry types,
20 movement types, 5 dimmer types**. This is a real library, not a template pile, and it
corroborates Stage 2's "the moat is the template library".

The **dimmer axis is the weak one**: **[V] 26 of 37** templates use `PULSE` (23 with
`PULSE` as their only dimmer type, plus 3 multi-step templates that include it —
AST-verified; corrected from 27), and only 5 dimmer
types exist against 17 geometries and 20 movements. If the channel is widened (P4-F16),
colour would add far more perceptual variety per unit of authoring effort than another
geometry.

---

### P4-F25 — Template authoring surface: cost of adding template #38
**Severity: LOW · Confidence: HIGH · Disposition: FIX (data-first loader)**

Adding a template means writing ~90 lines of Python of which ~55 are import boilerplate
and nested-model structure, registering it via a decorator side effect
(`templates/library.py:126`), listing it in `templates/builtins/__init__.py`, and
reinstalling. No schema file, no validation CLI, no non-Python path. Two of the defects
above (P4-F5 unscheduled steps, P4-F6 cycle/step-duration mismatch) are *data* errors that
a five-line registration-time validator would catch mechanically — and `TemplateRegistry.register`
already materializes each template for validation (`library.py:52`), so the hook exists.
See §7 for the data-first recommendation.

---

### P4-F26 — Minor correctness observations
**Severity: LOW · Confidence: MEDIUM–HIGH · Disposition: DEFER**

- `_order_fixtures_for_chase` (`template_compiler.py:227`) hard-codes an 11-element role
  order and a fixed centre index of 5, then computes OUTSIDE_IN/INSIDE_OUT by distance from
  it. Correct for symmetric rigs; for asymmetric or odd-count rigs the "centre" is the
  nominal `CENTER` role position, not the rig's actual middle. Unmapped roles sort to 999
  and cluster. Acceptable for the 4-head reference rig; fragile beyond it.
- `_get_segments_at_boundary` (`pipeline.py:441`) uses a magic ±100 ms tolerance and, when
  nothing matches, falls back to the single furthest/nearest segment (`:480-487`) — so a
  transition is *always* compiled, even at a boundary with no adjacent material.
- Transition-compile failures are caught and swallowed with a log (`pipeline.py:435-437`),
  continuing silently. Deliberate, but it means a systematically broken transition path
  would be invisible.
- `curves/functions/basic.py:163` — `generate_triangle` accepts and documents `phase`,
  never uses it; `CurveLibrary.TRIANGLE` is registered with `DEFAULT_WAVE_PARAMS` which
  includes `phase: 0.0` (`curves/defaults.py:19`), so the parameter is accepted and dropped.
- `curves/modifiers.py:22 reverse_curve` docstring says "invert vertically"; the body
  reverses time.
- `pattern.base_params` is filtered to `curve_pan_*` / `curve_tilt_*` prefixes
  (`handlers/movement/default.py:182-186`), so `SWEEP_LR`'s
  `{"amplitude","center","frequency"}` (`libraries/movement.py:267`) and `HIT`'s
  `{"hit_pan_offset_deg","snap_time_ms",…}` (`:454-460`) are silently discarded.

---

## 11b. Findings added by the phase verifier (P4-M1…M8)

_Eight findings the original review missed, adopted in full. M1 and M2 are output-changing
and join P4-F1 and P4-F3 on the step-2 fix list in §13._

### P4-M1 — `Template.defaults` is never read; every template's dimmer floor of 60 is dropped and dimmers drive to 0
**Severity: HIGH · Confidence: HIGH · Disposition: FIX**

All 37 templates declare `defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255}` —
an explicit anti-flicker floor. `Template.defaults` is read at exactly one site,
`compile/preset.py:118` (`new_defaults = deep_merge(template.defaults, preset.defaults)`),
whose result is stored on the reconstructed `Template` at `:151` and **never read again**
by any consumer (OBSERVED, exhaustive grep).

The dimmer handler instead reads its floor from the *fixture calibration* dict
(`handlers/dimmers/default.py:94-95,103-104`), which is populated in
`fixture_builder.py:82-83` from `FixtureCalibration`, which the shipped path builds via
`rig_profile_from_fixture_group(fixture_group)` (`pipeline.py:109`) — called **without**
the optional `dimmer_floor_dmx` argument, so `rig.py:242` evaluates
`dimmer_floor_dmx or 0` → **0**.

Net: the template-declared floor of 60 is silently discarded and the effective floor is 0,
so dimmers are driven fully to black rather than to the intended anti-flicker level. This
is the **fourth** member of the dead-configuration class in this phase (after
`is_channel_enabled`, `ChannelDefaults`, `shutter_default`) and **the only one with a
direct output consequence**. Fix: either read `Template.defaults` in the compile context,
or pass the floor through `rig_profile_from_fixture_group`.

### P4-M2 — BLACKOUT templates render FULL BRIGHTNESS under every preset except MODERATE
**Severity: HIGH · Confidence: HIGH (verified numerically) · Disposition: FIX**

Two independent bugs compose into a plan-triggerable inversion on exactly the templates a
planner picks for drops.

1. `DimmerType.BLACKOUT` declares a single categorical entry —
   `Intensity.SMOOTH: (min_intensity=0, max_intensity=0, period=1.0)`
   (`libraries/dimmer.py:66-76`). For any other intensity the handler's guard
   (`handlers/dimmers/default.py:85-89`) falls back to
   **`DEFAULT_DIMMER_PARAMS[Intensity.SMOOTH]`**, i.e. `max_intensity = 128`
   (`libraries/dimmer.py:35`) — the blackout's own `0` is discarded.
2. BLACKOUT's curve is `CurveLibrary.HOLD`, so it takes the static branch at
   `handlers/dimmers/default.py:100-112`, calling
   `_resolve_static_dmx_value(categorical_params.max_intensity, floor, ceiling)`. That
   helper computes `value = int(normalized_value * 255)` (`:172`) — but `max_intensity` is
   an **int in [0,255]**, not a normalized [0,1] value. So `128 × 255 = 32 640`, clamped to
   the ceiling → **255**.

Result, tracing the preset chain of P4-F8: CHILL→SLOW, ENERGETIC→DRAMATIC and
INTENSE→FAST all miss the SMOOTH entry and render **DMX 255 — full brightness**. Only
MODERATE→SMOOTH hits the blackout's own entry and yields `0 × 255 = 0`. The affected
templates are `pop_lock_spotlight_blackout` and `spiral_xross_blackout`, whose
`recommended_sections` are `drop, peak` and `drop, breakdown` — the planner will select
them precisely where a blackout is the intended effect, and get the maximum-visibility
opposite. Fix both halves together: the unit bug at `:172` and the fallback that discards a
pattern's own semantics.

(The same unit bug affects `DimmerType.HOLD`, whose SMOOTH entry is `max_intensity=255`;
`255 × 255` also clamps to 255, which happens to be the intended "hold at full", so the bug
is invisible there. It must still be fixed as part of the same change or HOLD will break.)

### P4-M3 — The planner's floored nominal-tempo bar conversion (third grid)
**Severity: MEDIUM-HIGH · Confidence: HIGH · Disposition: FIX (cross-phase, owned jointly with phase 3)**

Detailed inline in P4-F2. `agents/sequencer/moving_heads/context.py:246-271` floors
milliseconds to bars against a nominal tempo (120 BPM fallback at `:258-259`), quantizing
every section start down by up to one bar (≈2 s at 120 BPM) before the renderer's own grid
error applies. Listed separately because the fix site is in phase 3's code and must be
sequenced with the phase-4 half.

### P4-M4 — The test suite pins P4-F1 as intended behaviour
**Severity: MEDIUM · Confidence: HIGH · Disposition: FIX**

Detailed inline in P4-F1 and §5. `tests/integration/test_handler_categorical_params.py`
supplies intensity via `params` as well as the argument, so its assertions pass despite the
production defect. Recorded as its own finding because it changes the remediation contract:
**a fix that leaves these tests green has not fixed P4-F1.**

### P4-M5 — Full-excursion snap-back in the final 1/64 of most movement segments
**Severity: MEDIUM · Confidence: MEDIUM (analytic) · Disposition: FIX**

`_movement_post_process` (`curves/functions/movement.py:21-22`) calls `ensure_loop_ready`,
which in `"append"` mode adds `CurvePoint(t=1.0, v=points[0].v)` whenever the curve's end
value differs from its start (`curves/semantics.py:70-77`). For any movement whose sampled
window does not close on its starting value — which includes every non-integer `cycles`
setting and every curve family whose period does not divide the window — the emitted curve
therefore jumps from wherever the motion ended back to the **start** value across a single
sample interval, `1/64` of the segment. On a physical head that is a full-excursion snap
rather than a continuation. It affects most of the movement library and is invisible in the
curve statistics because the value range is unchanged. Interacts with P4-F14: the exporter's
`t=1.00` anchor (`export/dmx_settings_builder.py:307-310`) preserves it into the `.xsq`.

### P4-M6 — `frequency` silently changes physical excursion, inverting the SLOW/SMOOTH intent
**Severity: MEDIUM · Confidence: MEDIUM (analytic) · Disposition: FIX**

`frequency` is passed to the curve generator (`handlers/movement/default.py:281`) where it
scales cycles, and the result is then normalized by `center_curve`
(`curves/semantics.py:36-37`), which rescales the sampled window's actual min/max to the
full `[0,1]` range. When `frequency < 1` the window contains less than a full oscillation,
so the observed min/max span is *narrower* — and `center_curve` stretches that partial arc
back to full range. **Halving the frequency therefore roughly doubles the physical
excursion**, and the fixture ends the step parked at an extreme rather than near centre.

Because `DEFAULT_MOVEMENT_PARAMS` pairs low intensity with low frequency
(`SLOW: frequency=0.25`, `SMOOTH: 0.5` — `libraries/movement.py:62-63`), the intent is
inverted: `SLOW` produces the *largest* swing. Currently masked by P4-F1 (everything is
pinned to SMOOTH), so this becomes visible **the moment P4-F1 is fixed** — it must be
addressed in the same change or the fix will make output worse.

### P4-M7 — `FIGURE8` traces a circle
**Severity: LOW-MEDIUM · Confidence: HIGH (verified: constant radius) · Disposition: FIX**

`MovementType.FIGURE8` (`libraries/movement.py:290-302`) escapes the P4-F12 straight-line
degeneracy by setting `curve_tilt_delta: math.pi / 2` (`:298`), so pan and tilt are in
quadrature. But both axes use the *same* Lissajous frequency (`b = 2` for both, from the
registry defaults at `curves/library.py:250`), and `x = sin(2t), y = sin(2t + π/2) =
cos(2t)` is a **circle of constant radius**, geometrically identical to
`MovementType.CIRCLE`. A figure-of-eight requires a 2:1 frequency ratio between the axes.
So `figure8_mirror_strobe` and `MovementType.CIRCLE` produce the same path, which also
slightly reduces the library-distinctness count in P4-F24.

### P4-M8 — An unwired DMX validator already exists
**Severity: INFO (positive) · Confidence: HIGH · Disposition: KEEP + WIRE**

Detailed inline in P4-F22. `scripts/validation/_core/mh_xsq_validation.py` (587 LOC,
unit-tested) already parses emitted DMX settings, flags all-zero effects as CRITICAL, and
cross-checks shutter/colour/gobo mappings — but runs only post-hoc via
`scripts/validation/validate_artifacts.py` and is absent from `make validate` and CI. This
converts §13 step 1 from "build a validator" into "wire an existing one in".

---

## 12. Unresolved questions & cross-phase dependencies

**Requires Stage 4 (runtime):**
1. **P4-F3 empirical check** — run the two-config test spec given in P4-F3
   (`shutter_channel=6` vs `17`; assert `E_SLIDER_DMX6=0` present and `E_SLIDER_DMX17`
   absent). This decides whether the shipped product emits shows that produce no light.
   **Highest-priority Stage 4 item in this phase.**
2. **P4-M2 check** — render `pop_lock_spotlight_blackout` under `preset_id=ENERGETIC` and
   assert the emitted dimmer value; expected 255 (the inversion) rather than 0.
3. **P4-F2 magnitude** — compute `bar_boundaries[0]`, the max `|bar_boundaries[i] − i·avg|`
   for a real song, and the phase-3 flooring error from P4-M3; those three sum to the total
   sync error in ms.
4. **P4-F6** — does xLights load a file with overlapping layer-0 effects on one model?
   Select `split_lr_sweep_counter` and try.
5. **P4-F12, P4-M5, P4-M6, P4-M7** — sample the curves and confirm the analytic results
   (pan≡tilt for the three Lissajous patterns; the `t=1.0` snap-back; the
   frequency/excursion inversion; FIGURE8's constant radius).
6. **P4-F9** — render with a narrow tilt calibration and confirm the emitted curve exceeds
   it.
7. Confirm the 37 templates all compile without exception for a 4-fixture rig — no test
   does this today, and P4-F1a means 27 of 29 movement patterns would `KeyError` after a
   naive P4-F1 fix.

**Cross-phase dependencies:**
- **Phase 3 (planner):** (a) can the planner emit a section shorter than 4 bars? (P4-F4);
  (b) does the "ultra-short-section bypass" interact with it? (c) confirm the planner never
  emits `transition_in` (P4-F23); (d) phase 3 owns the prompt line
  `user.j2:162` that limits `preset_id` to three values (P4-F8) and the
  `recommended_sections` omission at `user.j2:47` (§10);
  (e) **[V] phase 3 owns the fix site for the third time grid** — `_ms_to_bar`
  (`agents/sequencer/moving_heads/context.py:246-271`) must round to the nearest detected
  downbeat instead of flooring against a nominal tempo. **P4-F2/P4-M3 cannot be closed by
  phase 4 alone**; the two halves must ship together or the ≤2 s quantization survives the
  renderer fix.
- **Phase 5 (xLights I/O):** owns whether `E_SLIDER_DMX` semantics are "write this channel"
  (P4-F3), whether overlapping effects are rejected (P4-F6), the `"2024.10"` stamp
  (`xsq_export.py:67`), and `sequencer/models/{enum,template,context}.py`.
- **Phase 1 (config):** `is_channel_enabled`, `ChannelDefaults`, `shutter_default`,
  `color_map`, `gobo_map`, `has_color_wheel` and friends are dead config surfaces
  belonging to Stage 2 §8 item 5's "dead configuration as a class".
- **Phase 7:** the test-architecture finding (P4-F22) is phase-4 evidence for a
  repo-wide claim.

**Open questions phase 4 could not settle:**
- Whether P4-F1 is a regression or was never wired. `git log -S` on the line would answer
  it; not run (out of read-only scope for history archaeology this phase).
- Whether the four hand-authored presets (`gentle`/`intense`) were meant to be exposed to
  the planner and the prompt drifted, or whether `ENERGY_TO_INTENSITY` superseded them.
- Whether the display-side `_INTENSITY_MAP` and the moving-heads `Intensity` tables should
  ever converge — a Stage 8 architecture decision, not a phase-4 one.

---

## 13. Inputs to Stage 8 (remediation ordering)

Phase 4 recommends this order; each step is prerequisite to the next.

1. **[V] Wire the existing validator into CI, then add a golden settings string.** Not
   "write a validator": `scripts/validation/_core/mh_xsq_validation.py` already parses
   emitted DMX, flags all-zero effects as CRITICAL, and cross-checks shutter/colour/gobo
   (P4-M8). Add it to `make validate`/CI, then add one snapshot test over
   `DmxSettingsBuilder.build_settings_string` for a 4-bar section on the reference rig
   (P4-F22). Nothing else in this list is verifiable without step 1.
2. **The four output-changing defects:** **P4-F3** (channel zeroing), **P4-F1 + P4-F1a**
   (movement intensity — guard *and* the movement-library data fill-in for the 27 of 29
   patterns with incomplete intensity coverage), **P4-M1** (template dimmer floor dropped),
   **P4-M2** (BLACKOUT renders full brightness). **P4-M6** must land with P4-F1, since
   fixing intensity without it makes SLOW produce the largest excursion.
   **P4-M4:** the fix is not done until `test_handler_categorical_params.py` is rewritten
   to stop supplying the `params["intensity"]` key.
3. **P4-F2 + P4-M3** (timing grids — requires the phase-3 half; see §12),
   **P4-F4/F5/F6** (scheduler), **P4-F8** (preset space).
   Add a registration-time template validator; it closes F5 and F6 permanently.
4. **P4-F9** (calibration annihilation — raised to HIGH), **P4-F10** (curve precision),
   then **P4-F12**, **P4-M5**, **P4-M7**. P4-F13 and P4-F14 are latent/INFO — no action
   needed beyond the notes.
5. **Delete** the dead inventory (P4-F20) — **excluding** `curves/modifiers.py` and
   `curves/providers/native.py`, which are imported and need their importers unwound first,
   and **retaining** the colour/gobo/shutter libraries if Stage 8 selects Stage 2 option (c).
6. **Data-first template loader** (P4-F25) — prerequisite for cheap colour re-authoring.
7. **Colour widening** (P4-F16) — ~300 LOC renderer-side plus template data.

**The load-bearing message for Stage 5/8:** steps 1–3 must precede any LLM-vs-deterministic
comparison. At baseline `aa8d325` both arms render through identical broken wiring, so
the experiment Stage 2 proposes would measure nothing. P4-M2 and P4-M3 reinforce this: a
blind human ranking at baseline would be scoring shows in which blackouts render at full
brightness and every section start can be up to two seconds early.
