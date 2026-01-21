# Curve Rewrite Gap Analysis

## Scope
This analysis compares the legacy curve system (`packages/blinkb0t/core/domains/sequencing/infrastructure/curves`) with
new rewrite docs in `changes/templates_rewrite` plus the offset-centered, late-DMX approach outlined in
`changes/templates/curve_approach.md`. It validates the current `packages/blinkb0t/core/curves` implementation against
those docs and identifies gaps that explain why the new curve generator falls short of expectations.

## Doc-aligned requirements (rewrite)
1. **Points-first curves** with normalized `(t, v)` in `[0,1]` and optional native curve IDs only for limited cases.
2. **Phase shift via sampling (Option B)** on a fixed grid in `[0,1)`.
3. **Fixed sampling + composition order**: sample → phase → envelope/modulation → simplify.
4. **RDP simplification** on `(t, v)` with deterministic tolerance.
5. **Movement curves are offset-centered** around `0.5` and later anchored by base + amplitude at export.
6. **Dimmer curves are absolute** in `[0,1]` and mapped to clamp range at export.
7. **Loop-ready curves** for movement (and usually dimmer), with continuity checks as quality gates.
8. **Late DMX conversion**: curve remains normalized until final export step.

## Validation of current `core/curves` implementation
### What matches the docs
- **Points-first schema**: `CurvePoint` and `PointsCurve` model normalized `t`/`v` in `[0,1]` with monotonic time.
- **Uniform sampling in `[0,1)`**: `sample_uniform_grid(n)` matches the fixed-grid requirement for phase and composition.
- **Phase shift via sampling**: `apply_phase_shift_samples` resamples base curves using `(t + offset) % 1.0`.
- **Composition**: `multiply_curves` / `apply_envelope` resample onto a fixed grid and compose deterministically.
- **RDP simplification**: `simplify_rdp` implements deterministic Ramer–Douglas–Peucker with scaling.

### What is missing or misaligned
- **Generator outputs are not offset-centered** (they are absolute `[0,1]` shapes). The rewrite requires movement
  curves to be centered at `0.5` before base+amplitude is applied.
- **No loop-ready enforcement**: the generators use `[0,1)` grids and do not emit explicit end points at `t=1.0`,
  so curves are not guaranteed to return to their start value.
- **No explicit movement-vs-dimmer semantics** in `core/curves`: there is no metadata or helpers that enforce
  offset-centered vs absolute semantics.
- **Native curves are not formally modeled**: the new `NativeCurve` is just an ID + params with no p1–p4 mapping
  or xLights export semantics.
- **Legacy curve library breadth is absent**: the new generators only implement linear/hold/sine/triangle/pulse
  and omit easing families, bounce/elastic, noise, Bezier/Lissajous, anticipate/overshoot, etc.
- **No preset/registry system**: the rewrite docs expect a curated catalog with repeat-safe behavior and
  template-friendly IDs, but the new module only exposes free functions.

## Legacy strengths that exceed the rewrite implementation
1. **Curve catalog breadth** (easing, bounce, elastic, noise, Bezier/Lissajous).
2. **Native curve parameter tuning** (p1–p4 mapped to xLights and bounded to DMX ranges).
3. **Normalization and DMX mapping utilities** in the legacy sequencing infrastructure.
4. **Modifier registry** with a path toward wrap/bounce/mirror/repeat/pingpong behaviors.

## Root causes of the shortfall
- The rewrite curve module was implemented as **pure math primitives** only (sampling, phase, compose, simplify),
  but the **movement/dimmer semantics** and **offset-centered contract** were not encoded in generators or helpers.
- The generator list is **too small** to cover the expressive curves already used by templates.
- The new model does not provide **catalog/preset metadata** required by template authors or compilers.

## Impact to output quality
- Movement curves are absolute rather than offset-centered, leading to incorrect base anchoring.
- Lack of loop-ready enforcement causes visible discontinuities on repeating steps.
- Missing advanced curves removes major creative capabilities from the rewrite pipeline.

## Priority gaps (ordered)
1. Offset-centered movement curve support + loop-ready enforcement.
2. Curve catalog parity with legacy system (easing, bounce, elastic, noise, Bezier/Lissajous, anticipate/overshoot).
3. Curve catalog/registry + preset system aligned to rewrite templates.
4. Optional native curve mapping/tuning for xLights where appropriate.
5. Export-time DMX conversion utilities aligned with `curve_approach`.
