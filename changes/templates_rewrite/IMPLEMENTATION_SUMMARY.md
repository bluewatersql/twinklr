# Moving Head Sequencer Rewrite - Executive Summary & Quick Reference

**Version:** 1.0  
**Date:** 2026-01-21  
**Status:** Ready for Implementation

---

## Quick Start for Autonomous Agents

### Read These First
1. **IMPLEMENTATION_PLAN_PART1.md** - Phase 0 (Foundations)
2. **IMPLEMENTATION_PLAN_PART2.md** - Phase 1 (Curves) + early Phase 2
3. **IMPLEMENTATION_PLAN_PART3.md** - Phases 2-6 + execution strategy

### Start Here
```bash
# Begin with Phase 0, Task 0.1
cd /path/to/repo
# Follow Task 0.1 instructions to create directory structure
```

---

## Document Map

### Specification Documents (Reference)
- `01_core_concepts_foundations.md` - Core contracts (geometry, movement, curves)
- `02_templates_methodology_design.md` - Template system design
- `02_configuration_rig_profiles.md` - Rig profile specification  
- `03_logical_architecture_process.md` - Pipeline overview
- `04_technical_architecture_design.md` - Architecture standards
- `05_current_system_migration.md` - Migration strategy
- `README.md` - Specification overview

### Implementation Plan (This Document Set)
- **IMPLEMENTATION_PLAN_PART1.md** - Phase 0 tasks (10 tasks, ~24 hours)
- **IMPLEMENTATION_PLAN_PART2.md** - Phase 1 tasks (6 tasks, ~26 hours)  
- **IMPLEMENTATION_PLAN_PART3.md** - Phases 2-6 summary + execution guide

---

## Implementation Overview

### Total Scope
- **6 Phases** spanning foundations → production
- **60+ discrete tasks** with clear acceptance criteria
- **~7 weeks** single developer, full-time
- **~4-5 weeks** with parallelization or team

### Phase Breakdown

| Phase | Goal | Tasks | Duration | Dependencies |
|-------|------|-------|----------|--------------|
| 0 | Pydantic models (no behavior) | 10 | 3-4 days | None |
| 1 | Pure curve operations | 6 | 4-5 days | Phase 0 |
| 2 | Geometry/Movement/Dimmer handlers | 6 | 5-6 days | Phase 0, 1 |
| 3 | Template patching & compilation | 8 | 6-7 days | Phase 0, 1, 2 |
| 4 | xLights export pipeline | 4 | 3-4 days | Phase 3 |
| 5 | LLM integration (minimal) | 3 | 2-3 days | Phase 3 |
| 6 | Acceptance testing & cleanup | 5 | 3-4 days | All phases |

---

## Key Architectural Decisions

### Non-Negotiable Standards
- ✅ **No god classes** - Small orchestrator + pure components
- ✅ **Dependency injection** - All services injected
- ✅ **Pydantic V2** - All models strictly typed
- ✅ **Python 3.12 + mypy strict** - No type: ignore without justification
- ✅ **TDD required** - Tests first, ≥80% coverage
- ✅ **No relative imports** - Absolute imports only

### Critical Design Patterns

#### 1. Separation of Concerns
```
Templates → describe choreography (rig-agnostic)
Rig Profile → describes physical fixtures
Handlers → pure functions (geometry/movement/dimmer)
Compiler → orchestrates (only orchestrates, no generation)
Exporters → adapt IR to output formats
```

#### 2. Phase Offset (Mandatory Approach)
```python
# Option B is MANDATORY (sampling-based)
def apply_phase_shift_samples(points, offset_norm, n_samples, wrap=True):
    # Generate fixed grid
    # Sample from (t + offset) % 1.0
    # Return uniformly-spaced points
```

#### 3. Curves (Points-First)
```python
# All curves ultimately become points
CurvePoint(t=0.5, v=0.7)  # Normalized [0,1] × [0,1]
# Fixed sampling (64 for movement, 32 for dimmer)
# Simplify with RDP after composition
```

#### 4. IR Strategy (Compiler Emits DMX)
```python
# Compiler outputs absolute DMX curves (chosen approach)
ChannelSegment(
    fixture_id="fix1",
    channel=ChannelName.PAN,
    t0_ms=0, t1_ms=2000,
    curve=PointsCurve(points=[...]),  # DMX values 0-255
    clamp_min=0, clamp_max=255
)
```

---

## Critical Path Tasks

These tasks are highest risk or block multiple downstream tasks:

### Phase 0
- **Task 0.2** - Curve models (blocks all of Phase 1)
- **Task 0.5** - Rig profile (blocks handlers)
- **Task 0.8** - Template models (blocks everything)

### Phase 1
- **Task 1.2** - Phase shift (blocks compilation)
- **Task 1.4** - RDP simplification (quality-critical)

### Phase 2
- **Task 2.1** - Handler protocols (blocks all handlers)

### Phase 3
- **Task 3.4** - Repeat scheduler (complex algorithm)
- **Task 3.5** - Phase offset calculator (complex algorithm)
- **Task 3.7** - Template compiler (orchestration)

---

## Acceptance Criteria Summary

### Models (Phase 0)
Every model must:
- [ ] Pass `mypy --strict` with no errors
- [ ] Have 100% branch coverage on validators
- [ ] Serialize/deserialize to JSON correctly
- [ ] Have docstrings on all public classes
- [ ] Reject invalid data with clear error messages

### Curve Operations (Phase 1)
Every curve function must:
- [ ] Be deterministic (same input → same output)
- [ ] Be pure (no mutable state)
- [ ] Meet performance benchmarks
- [ ] Preserve value bounds [0, 1]
- [ ] Maintain monotonic time

### Handlers (Phase 2)
Every handler must:
- [ ] Implement protocol contract exactly
- [ ] Be pure/near-pure (explicit inputs only)
- [ ] Have no orchestration logic
- [ ] Be independently testable
- [ ] Produce deterministic output

### Compiler (Phase 3)
Compilation must:
- [ ] Be repeatable (same input → same output)
- [ ] Apply patches immutably
- [ ] Generate valid IR segments
- [ ] Apply phase offsets correctly
- [ ] Handle all repeat modes

---

## Common Pitfalls to Avoid

### ❌ Don't Do This
1. **Mutate input models** - Always return new instances
2. **Put orchestration in handlers** - Handlers generate, compiler orchestrates
3. **Skip validation** - Every model must validate on construction
4. **Use relative imports** - Hard review fail
5. **Embed fixture IDs in templates** - Templates must be rig-agnostic
6. **Apply phase offset by mutating points** - Use sampling approach (Option B)
7. **Clamp before composition** - Clamp once at final export
8. **Create backwards compat shims** - This is a rewrite, not a refactor

### ✅ Do This
1. **Validate early with Pydantic** - Fail fast on bad data
2. **Test first** - Write tests before implementation
3. **Use dependency injection** - Never import singletons
4. **Document public APIs** - Docstrings with examples
5. **Benchmark critical paths** - Curve operations, compilation
6. **Use fixed sampling** - Prevents jitter and enables exact phase offsets
7. **Apply patches immutably** - Never modify source documents
8. **Separate concerns strictly** - Templates, rig, handlers, compiler, exporter

---

## Testing Strategy

### Unit Tests (Fast, Isolated)
- Every Pydantic validator
- Every curve operation
- Every handler in isolation
- Patch engine immutability
- Repeat scheduler logic

### Integration Tests (Cross-Component)
- Full curve pipeline (generate → shift → envelope → simplify)
- Handlers with real rig profiles
- Template loading + patching
- Step compilation (geometry + movement + dimmer)

### Golden Tests (Stability)
- Compile fan_pulse template
- Export to xLights XML
- Compare against committed baseline
- Detect unintended changes

### Performance Tests
- Curve operations < 1-5ms per operation
- Compilation < 5s for typical template
- Memory usage < 100MB for largest show

---

## Phase Exit Checklists

### Phase 0 → Phase 1
- [ ] All models implemented
- [ ] `mypy --strict` passes on models
- [ ] 95%+ test coverage
- [ ] Example fixtures validate
- [ ] No type: ignore comments

### Phase 1 → Phase 2
- [ ] All curve operations work
- [ ] Integration tests pass
- [ ] Performance benchmarks met
- [ ] 90%+ test coverage
- [ ] Deterministic behavior verified

### Phase 2 → Phase 3
- [ ] All handlers implemented
- [ ] All handlers registered
- [ ] Handler tests pass
- [ ] No orchestration in handlers
- [ ] 85%+ test coverage

### Phase 3 → Phase 4
- [ ] Full compilation works
- [ ] Phase offsets correct
- [ ] Repeat scheduling correct
- [ ] Integration tests pass
- [ ] Performance acceptable

### Phase 4 → Phase 5
- [ ] xLights export works
- [ ] Golden test established
- [ ] Manual xLights validation passed

### Phase 5 → Phase 6
- [ ] LLM integration works
- [ ] End-to-end test passes

### Phase 6 → Production
- [ ] Real show compiles
- [ ] Performance profiled
- [ ] Documentation complete
- [ ] No legacy dependencies
- [ ] Legacy code deleted

---

## Progress Tracking

### Daily Checklist
1. [ ] Review current task acceptance criteria
2. [ ] Implement according to code template
3. [ ] Write tests BEFORE implementation where possible
4. [ ] Run `mypy --strict` on new files
5. [ ] Run tests with coverage report
6. [ ] Verify all acceptance criteria pass
7. [ ] Mark task complete
8. [ ] Commit progress

### Weekly Checklist
1. [ ] Review phase exit criteria
2. [ ] Run full test suite
3. [ ] Check overall coverage trend
4. [ ] Profile performance if in Phase 3+
5. [ ] Update progress document
6. [ ] Identify blockers

---

## File Structure Quick Reference

```
packages/blinkb0t/core/
├── curves/                     # Phase 1
│   ├── models.py               # CurvePoint, BaseCurve
│   ├── sampling.py             # Uniform grid, interpolation
│   ├── phase.py                # Phase shift (Option B)
│   ├── composition.py          # Multiply, envelope
│   ├── simplification.py       # RDP algorithm
│   └── generators.py           # Linear, sine, etc.
│
└── sequencer/moving_heads/      
    ├── models/                 # Phase 0
    │   ├── channel.py          # ChannelName, BlendMode
    │   ├── ir.py               # ChannelSegment
    │   ├── rig.py              # RigProfile, FixtureDefinition
    │   ├── template.py         # Template, TemplateDoc
    │   ├── plan.py             # PlaybackPlan
    │   └── protocols.py        # BeatMapper
    │
    ├── handlers/               # Phase 2
    │   ├── protocols.py        # Handler protocols
    │   ├── geometry.py         # RolePoseGeometryHandler
    │   ├── movement.py         # SweepLRMovementHandler
    │   ├── dimmer.py           # FadeIn, Pulse handlers
    │   ├── registry.py         # HandlerRegistry
    │   └── defaults.py         # Default registries
    │
    ├── templates/              # Phase 3
    │   ├── patching.py         # Patch engine
    │   └── loader.py           # TemplateLoader
    │
    ├── compile/                # Phase 3
    │   ├── scheduler.py        # RepeatScheduler
    │   ├── phase_offset.py     # PhaseOffsetCalculator
    │   ├── step_compiler.py    # StepCompiler
    │   └── compiler.py         # TemplateCompiler (main)
    │
    └── export/                 # Phase 4
        ├── xlights.py          # xLights exporter
        └── models.py           # xLights data models

tests/
└── core/
    ├── curves/                  # Mirror structure
    └── sequencer/moving_heads/  # Mirror structure
```

---

## Key Equations & Algorithms

### Phase Offset (Normalized Time)
```
offset_norm = offset_bars / step_duration_bars
t_shifted = (t + offset_norm) % 1.0  # if wrap enabled
```

### Movement Composition (Offset-Centered)
```
dmx = base_dmx + (v - 0.5) * amplitude_dmx
# where v ∈ [0, 1], v=0.5 means no motion
```

### Dimmer Composition (Absolute)
```
dmx = lerp(min_dmx, max_dmx, v)
# where v ∈ [0, 1]
```

### RDP Simplification
```
perpendicular_distance(point, line_segment, scale_t, scale_v)
recursively keep point if distance > epsilon
always preserve endpoints
```

### Repeat Cycle Count (PING_PONG)
```
full_cycle_ms = cycle_duration_ms * 2  # forward + backward
num_full_cycles = window_duration_ms // full_cycle_ms
remainder_ms = window_duration_ms % full_cycle_ms
```

---

## Troubleshooting Guide

### Problem: Mypy errors on Pydantic models
**Solution:** Ensure `model_config = ConfigDict(extra="forbid")` is set. Check all Field() definitions have proper types.

### Problem: Curve values exceed [0, 1]
**Solution:** Check composition order. Apply envelopes and phase shifts before simplification. Clamp at export boundary.

### Problem: Phase offset not working
**Solution:** Verify using Option B (sampling approach). Check offset_norm calculation. Verify wrap flag is set correctly.

### Problem: Repeat scheduling incorrect
**Solution:** Check PING_PONG forward/backward logic. Verify remainder policy. Test with exact multiples first.

### Problem: Tests flaky
**Solution:** Check for mutable state. Ensure all operations are pure. Use fixed seeds for randomness if needed.

### Problem: Performance slow
**Solution:** Profile with cProfile. Check n_samples (64 for movement is max needed). Verify no redundant operations.

---

## Success Indicators

### Phase 0 Success
- ✅ Example rig validates without errors
- ✅ Example template validates without errors
- ✅ All models have 100% validator coverage
- ✅ Zero mypy errors

### Phase 1 Success
- ✅ Can generate, shift, envelope, simplify in < 10ms
- ✅ Phase shift is bit-exact for integer offsets
- ✅ RDP simplification reduces 256 points to ~20 points

### Phase 2 Success
- ✅ ROLE_POSE handler maps 4 roles correctly
- ✅ SWEEP_LR produces smooth sine wave
- ✅ PULSE dimmer is loop-safe

### Phase 3 Success
- ✅ fan_pulse template compiles without errors
- ✅ IR has expected number of segments (steps × fixtures × channels)
- ✅ Phase offsets differ across fixtures as expected

### Phase 4 Success
- ✅ xLights XML is valid
- ✅ Sequence plays correctly in xLights
- ✅ Golden test baseline is stable

### Phase 6 Success
- ✅ Real 5-minute show compiles in < 30 seconds
- ✅ Visual quality matches expectations
- ✅ Legacy code deleted successfully

---

## Next Actions

### For Implementation Start
1. **Read all spec documents** (01-05, README)
2. **Read IMPLEMENTATION_PLAN_PART1** in detail
3. **Set up development environment** (Python 3.12, mypy, pytest, ruff)
4. **Begin Task 0.1** - Create directory structure
5. **Follow tasks sequentially** within each phase
6. **Track progress** using checkboxes

### For Code Review
1. **Verify acceptance criteria** for completed tasks
2. **Check phase exit criteria** before approving phase
3. **Run full test suite** with coverage report
4. **Verify mypy --strict** passes on all new code
5. **Review for anti-patterns** (see "Don't Do This" section)

### For Production Deployment
1. **Complete Phase 6** acceptance testing
2. **Run performance profiling** on real shows
3. **Verify golden tests** are stable
4. **Delete legacy code** after sign-off
5. **Deploy with monitoring** for compilation times

---

**This completes the implementation plan documentation set.**

These three documents provide everything needed to execute the rewrite from start to finish, with clear tasks, acceptance criteria, and quality gates throughout. An autonomous agent can follow this plan linearly, checking off boxes and verifying criteria at each step.

**CRITICAL**

- Do NOT invent steps, change scope or deviate from design documents and implementation plan.
- Do NOT defer or stub steps unless documented by implementation plan.
- Do NOT make assumptions. If design is ambigious or clarity is needed, STOP and prompt for clarity or direction from developer.
- If token budget does not allow for task to be completed as designed, do NOT start. Ensure all status and handoff documents are up to date and report back to developer.