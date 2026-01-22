# Agent-Optimized Implementation Plan (Task-Based)

## Guiding rules
- Keep `core/curves` pure and deterministic.
- Encode movement/dimmer semantics explicitly in helper layers.
- Maintain fixed-grid sampling and Option B phase shifting.
- Ensure tests for every curve operation and generator.

## Phase 0 — Discovery & baselines (0.5 day)
1. **Inventory legacy curve types**
   - Extract curve list from `sequencing/infrastructure/curves/generator.py`.
   - Categorize: easing, motion, noise, parametric, musical.
2. **Doc alignment checklist**
   - Validate requirements from `templates_rewrite` and `curve_approach.md`.
3. **Create golden fixtures**
   - Capture expected points for a small subset (sine, triangle, ease-in/out, bounce).

**Exit criteria**: curve catalog list + golden fixtures curated.

## Phase 1 — Semantics helpers & loop-ready enforcement (1–2 days)
1. **Add helpers** in `core/curves`:
   - `ensure_loop_ready(points, mode="append")`.
   - `center_curve(points)`.
   - `curve_kind` enum or metadata wrapper.
2. **Add unit tests**:
   - Loop-ready: `v(0) == v(1)`.
   - Centering: average of min/max equals 0.5.
3. **Update generator usage**:
   - Movement generators go through `center_curve` + `ensure_loop_ready`.

**Exit criteria**: movement curves are centered and loop-safe by default.

## Phase 2 — Expand generator catalog (3–5 days)
1. **Port easing families**:
   - sine/quad/cubic/expo/back in, out, in-out.
2. **Port bounce/elastic**.
3. **Port noise** (perlin/simplex approximations).
4. **Port parametric** (Bezier/Lissajous).
5. **Port anticipate/overshoot**.

**Validation**:
- Add unit tests for range `[0,1]` and determinism.
- Update golden fixtures.

**Exit criteria**: curve catalog parity with legacy.

## Phase 3 — Registry + presets (2–3 days)
1. **Implement curve registry**:
   - map `curve_id → CurveGeneratorSpec`.
2. **Add `CurveDefinition`** for presets/modifiers.
3. **Add `resolve_curve(def)`**:
   - resolves base curve, applies params, modifiers.
4. **Add tests** for preset resolution and modifier application.

**Exit criteria**: templates can reference stable curve IDs with presets.

## Phase 4 — Export-time DMX conversion utilities (2 days)
1. **Implement conversion helpers**:
   - `movement_curve_to_dmx`.
   - `dimmer_curve_to_dmx`.
2. **Add tests** using `curve_approach.md` example.
3. **Add clamping logic** + verify boundary behavior.

**Exit criteria**: normalized curves convert to DMX at export time with clamping.

## Phase 5 — Optional native curve support (2–4 days)
1. **Define native curve spec** (p1–p4 mapping).
2. **Add tuning helpers** for DMX boundaries.
3. **Add serialization for external exporters if needed.**

**Exit criteria**: only if native curves are required in export pipeline.

## Phase 6 — Integration & perf (1–2 days)
1. **Integration tests**: generate → phase → envelope → simplify.
2. **Perf checks**: 64-sample operations under 1–5ms.

**Exit criteria**: stable, performant curve pipeline.

## Suggested task order for an agent
1. Implement helpers (center + loop-ready) + tests.
2. Expand generator catalog incrementally (per family) + tests.
3. Add registry/presets + tests.
4. Add DMX conversion utilities + tests.
5. Add integration tests + perf measurements.
