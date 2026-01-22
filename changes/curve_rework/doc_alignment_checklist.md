# Doc Alignment Checklist (Task 0.2)

## Source docs
- `changes/templates/curve_approach.md`
- `changes/templates_rewrite/01_core_concepts_foundations.md`
- `changes/templates_rewrite/03_logical_architecture_process.md`
- `changes/templates_rewrite/04_technical_architecture_design.md`

## Checklist
| Requirement | Expected behavior | Current state | Notes |
| --- | --- | --- | --- |
| Points-first curves | Curves are represented as normalized `(t, v)` points in `[0,1]` | ✅ `core/curves/models.py` | Matches `PointsCurve` model. |
| Optional native curve IDs | Native curves only when limited set + no composition | ⚠️ Partial | `NativeCurve` exists but lacks mapping/constraints. |
| Fixed sampling grid | Use uniform `[0,1)` grid for sampling and phase | ✅ | `sample_uniform_grid` returns `[0,1)` samples. |
| Phase shift Option B | Resample on fixed grid with `(t + offset) % 1.0` | ✅ | `apply_phase_shift_samples` matches. |
| Composition order | sample → phase → envelope/modulation → simplify | ⚠️ Doc-only | Code has primitives; pipeline order not enforced by helpers. |
| RDP simplification | Deterministic RDP on `(t, v)` | ✅ | `simplify_rdp` implements. |
| Movement curves offset-centered | Movement curves centered at `0.5` | ❌ | Generators currently output absolute shapes. |
| Dimmer curves absolute | Dimmer curves are absolute `[0,1]` | ⚠️ | Generators are absolute, but no semantic distinction. |
| Loop-ready curves | Movement curves must return to start for repeats | ❌ | No loop-ready enforcement. |
| Late DMX conversion | Convert to DMX at export only | ⚠️ | Planned in docs; helpers not implemented in `core/curves`. |
| Export transform | Movement uses `base + amplitude * (v - 0.5)` | ❌ | No helper for offset-centered conversion. |
| Export transform | Dimmer maps `[0,1]` to clamp range | ❌ | No helper. |
| Curve catalog parity | Support legacy curve families | ❌ | Only linear/hold/sine/triangle/pulse implemented. |
| Preset/registry | Stable curve IDs + modifiers | ❌ | No registry/preset system in `core/curves`. |

## Summary
- **Green:** core curve math primitives (sampling, phase, composition, simplification) are aligned.
- **Yellow:** native curve handling and pipeline ordering exist conceptually but lack enforcement.
- **Red:** movement offset-centered semantics, loop readiness, export conversion, and catalog parity.
