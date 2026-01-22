# Curve Rework Progress

## Status

- **Phase:** 6 — Integration & perf
- **State:** complete

## Completed
- [x] Task 0.1 — Inventory legacy curve types
- [x] Task 0.2 — Doc alignment checklist
- [x] Task 0.3 — Golden fixtures
- [x] Task 1.1 — Add semantics helpers (`center_curve`, `ensure_loop_ready`, `CurveKind`)
- [x] Task 1.2 — Add unit tests for helpers
- [x] Task 1.3 — Add movement generator wrappers
- [x] Task 2.1 — Port easing families (sine/quad/cubic/expo/back)
- [x] Task 2.2 — Port bounce/elastic
- [x] Task 2.3 — Port noise (perlin/simplex approximations)
- [x] Task 2.4 — Port parametric (bezier/lissajous)
- [x] Task 2.5 — Port anticipate/overshoot
- [x] Task 3.1 — Add curve registry
- [x] Task 3.2 — Preset definition modeling (default params + modifiers)
- [x] Task 3.3 — Resolve curve definitions helper
- [x] Task 4.1 — Implement DMX conversion helpers
- [x] Task 4.2 — Add DMX conversion tests
- [x] Task 5.1 — Add native curve spec mapping
- [x] Task 5.2 — Add native curve tuning + serialization
- [x] Task 6.1 — Add integration tests
- [x] Task 6.2 — Perf checks (existing curve perf tests)
- [x] Task 6.3 — Curve library wiring

## Notes
- Native curve helpers live in `core/curves/native.py` with tests in `tests/core/curves/test_native.py`.
- Phase 6 integration tests in `tests/core/curves/test_phase6_integration.py`.
- Perf coverage already exists in `tests/core/curves/test_integration.py` and related performance tests.
