# Remediation Plan

## Objectives
- Align curve handling with the **offset-centered, late-DMX** approach.
- Restore feature parity with the legacy curve catalog.
- Ensure curve operations remain **pure, deterministic, and testable**.
- Provide a **template-friendly curve registry** with presets and metadata.

## Phase 0 — Alignment & guardrails (1–2 days)
1. **Document the offset-centered contract** inside the curves module README and add a short usage guide.
2. **Add validation helpers** for loop-ready curves (C0, optional C1) to make requirements explicit.
3. **Add generator tests** that encode loop-ready expectations for movement curves.

## Phase 1 — Offset-centered movement curves (2–4 days)
1. **Introduce offset-centered helpers**:
   - `center_curve(points) -> PointsCurve` (maps absolute `[0,1]` to centered around `0.5`).
   - `ensure_loop_ready(points) -> PointsCurve` (enforces `v(0) == v(1)`; optional slope continuity).
2. **Update movement generator usage** to always produce centered curves and run loop validation.
3. **Add curve metadata** (e.g., `curve_kind = MOVEMENT_OFFSET | DIMMER_ABSOLUTE`) for downstream clarity.

## Phase 2 — Curve catalog parity (4–7 days)
1. **Port legacy generator functions** from `sequencing/infrastructure/curves/generator.py`:
   - easing families (sine/quad/cubic/expo/back)
   - bounce/elastic
   - noise (perlin/simplex approximations)
   - lissajous/bezier
   - anticipate/overshoot
2. **Create a generator registry** that maps curve IDs → generator + parameter schema.
3. **Add tests** for each curve type: range checks, loop-ready checks (if movement), and determinism.

## Phase 3 — Presets + registry (2–4 days)
1. **Introduce `CurveDefinition` + `CurveLibrary`** equivalents (rewrite-safe, points-first).
2. **Support preset curves** with parameter overrides and modifier chains.
3. **Add migration tooling** to map old curve IDs to new curve IDs.

## Phase 4 — Export-time DMX conversion utilities (2–3 days)
1. **Implement channel conversion helpers** consistent with `curve_approach.md`:
   - offset-centered movement curves: `base + amplitude * (v - 0.5)`
   - dimmer absolute curves: map `[0,1]` to `[clamp_min, clamp_max]`
2. **Add clamping and calibration hooks**.
3. **Integration tests**: movement + dimmer curves → DMX points.

## Phase 5 — Native curve support (optional, 3–5 days)
1. **Add native curve spec mapping** (p1–p4) only for low-variance curves.
2. **Implement tuning to DMX boundaries** (preserve shapes, avoid clipping).
3. **Add export serialization** if required by xLights pipeline.

## Success criteria
- Movement curves are offset-centered, loop-ready, and deterministic.
- All doc-specified curve operations are implemented and tested.
- Curve catalog meets or exceeds legacy breadth.
- Export pipeline produces correct DMX output for movement and dimmer curves.
