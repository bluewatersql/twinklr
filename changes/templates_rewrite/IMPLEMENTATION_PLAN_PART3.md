# Moving Head Sequencer Rewrite - Implementation Plan (Part 3)

## Phase 1 (Continued) - Curve Generators and Integration

### Task 1.5: Curve Generation Helpers
**Effort:** 4 hours  
**Dependencies:** Task 1.1  
**File:** `packages/blinkb0t/core/curves/generators.py`

**Summary:** Implement standard curve generators (linear, hold, sine, triangle, pulse). Each generator creates N uniformly-sampled points. Critical for handlers to generate base movement/dimmer curves.

**Key Test Cases:**
- [ ] All generators produce exactly n_samples points
- [ ] All output values in [0, 1]
- [ ] Sine wave has correct number of peaks
- [ ] Triangle wave shape validation
- [ ] Pulse duty cycle accuracy

---

### Task 1.6: Curve Integration Tests
**Effort:** 3 hours  
**Dependencies:** Tasks 1.1-1.5  
**File:** `tests/core/curves/test_integration.py`

**Summary:** End-to-end pipeline tests: generate → shift → envelope → simplify. Validates complete curve workflow performs correctly and efficiently.

**Key Validations:**
- [ ] Pipeline preserves bounds [0, 1]
- [ ] Pipeline maintains monotonic time
- [ ] Performance < 10ms for 100-sample curve through full pipeline
- [ ] No data corruption in multi-step composition

---

### Phase 1 Exit Criteria

- [ ] All Tasks 1.1-1.6 completed
- [ ] `mypy --strict packages/blinkb0t/core/curves` passes
- [ ] Test coverage ≥ 90% for curves module
- [ ] All operations deterministic
- [ ] Performance benchmarks met
- [ ] No mutable state in curve operations
- [ ] Integration tests validate full pipeline

**Rollback Point:** Curve system is independent—can be reverted without affecting Phase 0.

---

## Phase 2 — Handlers (Geometry, Movement, Dimmer)

**Goal:** Implement pure handler functions  
**Duration:** 5-6 days  
**Success Criteria:** All handlers produce deterministic outputs

### Task 2.1: Handler Protocols
**Effort:** 2 hours  
**Summary:** Define `GeometryHandler`, `MovementHandler`, `DimmerHandler` protocols with clear contracts.

---

### Task 2.2: ROLE_POSE Geometry Handler
**Effort:** 4 hours  
**Summary:** Implement geometry handler that maps role tokens (WIDE_LEFT, CENTER, etc.) to DMX values. Handles calibration ranges and inversion flags.

**Key Features:**
- Pan pose tokens → normalized [0, 1] → calibrated DMX
- Tilt pose tokens → normalized [0, 1] → calibrated DMX
- Inversion flag support
- Role → fixture mapping via rig profile

---

### Task 2.3: SWEEP_LR Movement Handler
**Effort:** 5 hours  
**Summary:** Implement left-to-right sweep using sine wave. Maps intensity levels to amplitude. Returns offset-centered curves (v=0.5 means no motion).

**Key Features:**
- Intensity → amplitude mapping (SMOOTH=0.15, DRAMATIC=0.4)
- Cycles parameter support
- Offset-centered output (0.5 = neutral)
- Tilt remains static

---

### Task 2.4: FADE_IN / PULSE Dimmer Handlers
**Effort:** 5 hours  
**Summary:** Implement dimmer handlers. FADE_IN is linear ramp, PULSE is sine wave. Both respect min_norm/max_norm range.

**Key Features:**
- Absolute normalized output [0, 1]
- Respect min/max range
- Intensity affects pulse amplitude
- Loop-safe for integer cycles

---

### Task 2.5: Handler Registries
**Effort:** 3 hours  
**Summary:** Implement generic `HandlerRegistry` and type-specific registries. Supports registration and lookup with clear error messages.

---

### Task 2.6: Default Handler Setup
**Effort:** 2 hours  
**Summary:** Factory functions to create registries pre-populated with default handlers.

---

### Phase 2 Exit Criteria

- [ ] All Tasks 2.1-2.6 completed
- [ ] `mypy --strict` passes on all handler modules
- [ ] Test coverage ≥ 85%
- [ ] All handlers deterministic
- [ ] No orchestration logic in handlers
- [ ] Can call each handler independently

**Rollback Point:** Handlers are independent of compiler.

---

## Phase 3 — Template Patching and Compilation

**Goal:** Implement patch engine and compilation orchestrator  
**Duration:** 6-7 days  
**Success Criteria:** Can compile complete template to IR segments

### Task 3.1: Patch Data Structures
**Effort:** 3 hours  
**Summary:** Implement immutable deep merge for patch dictionaries. Add provenance tracking for debugging.

---

### Task 3.2: Preset Application
**Effort:** 4 hours  
**Summary:** Apply preset patches to templates (defaults + per-step patches). Returns new template, original unchanged.

---

### Task 3.3: Template Loader
**Effort:** 3 hours  
**Summary:** Load and validate templates from JSON. Cache loaded templates. Verify template_id matches filename.

---

### Task 3.4: Repeat Scheduler
**Effort:** 6 hours  
**Summary:** Core scheduler logic. Computes step occurrences for playback window. Handles PING_PONG mode and remainder policies.

**Key Algorithms:**
- Cycle counting with forward/backward passes
- Remainder handling (truncate/hold/fade)
- Step occurrence generation with timing

---

### Task 3.5: Phase Offset Calculator
**Effort:** 5 hours  
**Summary:** Compute per-fixture phase offsets based on GROUP_ORDER. Maps fixtures to ordered positions using chase orders and spatial positions.

**Key Features:**
- LEFT_TO_RIGHT ordering
- OUTSIDE_IN ordering
- Linear distribution of spread
- Wrap vs. no-wrap modes

---

### Task 3.6: Step Compiler
**Effort:** 6 hours  
**Summary:** Compile single step to IR segments. Orchestrates geometry → movement → dimmer handlers. Applies phase offsets and generates curves.

**Pipeline:**
1. Resolve target fixtures from group
2. Call geometry handler → base poses
3. Call movement handler → offset curves
4. Call dimmer handler → absolute curves
5. Apply phase offsets
6. Compose movement with geometry
7. Generate IR segments

---

### Task 3.7: Template Compiler (Orchestrator)
**Effort:** 5 hours  
**Summary:** Main compiler orchestrator. Loads template, applies patches, schedules repeats, compiles all steps.

**Pipeline:**
1. Load template
2. Apply preset patch
3. Apply modifier patches
4. Schedule step occurrences
5. Compile each step
6. Return IR segments

---

### Task 3.8: Compiler Integration Tests
**Effort:** 4 hours  
**Summary:** End-to-end tests. Compile fan_pulse template with ENERGETIC preset for 4-fixture rig. Validate IR structure and properties.

---

### Phase 3 Exit Criteria

- [ ] All Tasks 3.1-3.8 completed
- [ ] Can compile complete template end-to-end
- [ ] IR segments have correct structure
- [ ] Phase offsets applied correctly
- [ ] Repeat scheduling works for PING_PONG
- [ ] Integration tests pass
- [ ] Performance acceptable (< 5s for typical template)

**Rollback Point:** Compiler is self-contained—can be rewritten without affecting handlers/curves.

---

## Phase 4 — Export Pipeline

**Goal:** Convert IR to xLights/XSQ format  
**Duration:** 3-4 days  
**Success Criteria:** Exported files work in xLights

### Task 4.1: xLights Data Models
**Effort:** 3 hours  
**Summary:** Pydantic models for xLights XML structure (sequence, timing, layers, effects).

---

### Task 4.2: Curve to DMX Converter
**Effort:** 4 hours  
**Summary:** Convert normalized curves to absolute DMX values. Handle offset-centered vs. absolute curves. Apply final clamping.

**Algorithms:**
- Offset-centered: `dmx = base + (v - 0.5) * amplitude`
- Absolute: `dmx = lerp(min_dmx, max_dmx, v)`
- Clamp to [clamp_min, clamp_max]

---

### Task 4.3: xLights Exporter
**Effort:** 5 hours  
**Summary:** Convert IR segments to xLights XML. Generate timing tracks, fixture layers, and effect blocks.

---

### Task 4.4: Golden Test
**Effort:** 3 hours  
**Summary:** Compile fan_pulse template and export to xLights. Commit as golden reference. Compare future exports for stability.

---

### Phase 4 Exit Criteria

- [ ] Exporter produces valid xLights XML
- [ ] Exported files work in xLights player
- [ ] Golden test establishes baseline
- [ ] DMX conversion accurate
- [ ] No orchestration logic in exporter

---

## Phase 5 — LLM Integration (Minimal)

**Goal:** Implement simplified LLM selection. Non-parallel implementation. Refactor and implement in place. 
**Duration:** 2-3 days  
**Success Criteria:** LLM can select template + preset + modifiers

### Task 5.1: LLM Response Schema
**Effort:** 2 hours  
**Summary:** 
   - Refactor Pydantic model for LLM output (template_id, preset_id, modifiers) aligned.
**Files to Refactor:** `packages/blinkb0t/core/agents/moving_heads/models_agent_plan.py`
---

### Task 5.2: Template Context Building
**Effort:** 2 hours  
**Summary:** Update llm context building & shaping do dynamically handle templates/presets. Simplify and remove the extraneous data while including data the llm would need to reason over the templates pattern and behavior for choreography.
**Files to Refactor:** `packages/blinkb0t/core/agents/moving_heads/context.py`

---

### Task 5.3: Template Selection Prompt Building
**Effort:** 2 hours  
**Summary:** Refactor, simplify & optimize llm prompts to align with new template-driven paradigm:
      - Planner system & user prompt
      - Implementation system & user prompt
      - Judge system & user prompt
      - Refinement implementation prompt
      - Refinement replan prompt
**Files to Refactor:** `packages/blinkb0t/core/agents/moving_heads/prompts/*`

---

### Task 5.4: Heuristic Validation
**Effort:** 2 hours  
**Summary:** Refactor the heursitics validator to align with the new template approach. Eliminate the domains/choice no longer relevent, while adding coverage for the dimensions.
**Files to Add/Refactor:** `packages/blinkb0t/core/agents/moving_heads/heuristic_validator.py`

---

### Phase 5 Exit Criteria

- [ ] LLM contract simplified (no raw plan generation)
- [ ] Response validated with Pydantic
- [ ] Integration test passes

---

## Phase 6 — Acceptance Testing and Cleanup

**Goal:** Production readiness  
**Duration:** 3-4 days  
**Success Criteria:** Ready to delete legacy code

### Task 6.1: Real Show Compilation
**Effort:** 4 hours  
**Summary:** Compile multiple templates for real show config. Validate visual quality in xLights.

---

### Task 6.2: Performance Profiling
**Effort:** 3 hours  
**Summary:** Profile compilation for 5-minute show. Identify bottlenecks. Optimize if needed.

---

### Task 6.3: Documentation
**Effort:** 4 hours  
**Summary:** Write handler development guide, template authoring guide, troubleshooting guide.

---

### Task 6.4: Dependency Audit
**Effort:** 2 hours  
**Summary:** Verify no dependencies from new code into `core/domains/`. Ready to delete legacy.

---

### Phase 6 Exit Criteria

- [ ] Real show compiles successfully
- [ ] Performance acceptable
- [ ] Documentation complete
- [ ] No legacy dependencies

---

## Execution Strategy for Autonomous Agents

### Daily Workflow
1. **Start of day:** Review phase exit criteria
2. **Select next task:** Pick lowest incomplete task number in current phase
3. **Implement task:** Follow actions, create files, write tests
4. **Verify acceptance criteria:** Check all boxes before marking complete
5. **Run local validation:** `mypy --strict`, tests, coverage
6. **Mark task complete:** Update checkboxes
7. **End of day:** Commit progress, update status

### When Stuck
1. Review task dependencies—are they truly complete?
2. Check spec documents for clarification
3. Review code templates for guidance
4. Create minimal implementation that passes tests
5. Iterate to improve

### Quality Gates
- **After each task:** All acceptance criteria must pass
- **After each phase:** Exit criteria checklist must pass
- **Before commit:** `mypy --strict` + tests + coverage

---

## Progress Tracking Template

```markdown
## Current Status

**Phase:** [0-6]  
**Current Task:** [X.Y]  
**Started:** [Date]  
**Estimated Completion:** [Date]

### Completed Tasks
- [x] Task 0.1: Project Structure Setup
- [x] Task 0.2: Curve Schema Models
- [ ] Task 0.3: ... (in progress)

### Blockers
- None

### Next Steps
1. Complete Task 0.3
2. Begin Task 0.4
```

---

## Risk Mitigation

### High-Risk Areas
1. **Phase offset calculation** (Task 3.5): Complex logic, easy to get wrong
   - Mitigation: Extensive unit tests, visual validation
2. **Repeat scheduling** (Task 3.4): Edge cases in ping-pong mode
   - Mitigation: Test all remainder policies
3. **DMX conversion** (Task 4.2): Clamping and composition
   - Mitigation: Golden tests, manual verification

### Rollback Strategy
- Each phase is independent enough to revert without cascading failures
- Models (Phase 0) are pure data—no behavior to break
- Curves (Phase 1) are pure functions—no state
- Handlers (Phase 2) are pure—no side effects
- Compiler (Phase 3) is orchestrator—can be rewritten

---

## Success Metrics

### Phase 0
- [ ] 100% model coverage
- [ ] Zero mypy errors
- [ ] All fixtures validate

### Phase 1
- [ ] 90%+ curve coverage
- [ ] Performance benchmarks met
- [ ] Zero flaky tests

### Phase 2
- [ ] 85%+ handler coverage
- [ ] All handlers deterministic
- [ ] No orchestration leakage

### Phase 3
- [ ] End-to-end compilation works
- [ ] Golden test baseline established
- [ ] Performance < 5s per template

### Phase 4
- [ ] xLights files work
- [ ] Golden test stable
- [ ] Export is pure adapter

### Phase 5
- [ ] LLM integration minimal
- [ ] Categorical selection only

### Phase 6
- [ ] Real show compiles
- [ ] Legacy deleted
- [ ] Documentation complete

---

## Estimated Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 0: Foundations | 3-4 days | 4 days |
| 1: Curves | 4-5 days | 9 days |
| 2: Handlers | 5-6 days | 15 days |
| 3: Compilation | 6-7 days | 22 days |
| 4: Export | 3-4 days | 26 days |
| 5: LLM | 2-3 days | 29 days |
| 6: Acceptance | 3-4 days | 33 days |

**Total: ~7 weeks** (assuming 8-hour days, single developer)

With parallel work or multiple developers, could compress to 4-5 weeks.

---

## Final Checklist (Before Production)

- [ ] All 60+ tasks completed
- [ ] All phase exit criteria passed
- [ ] `mypy --strict` passes on entire codebase
- [ ] Test coverage ≥ 80% overall
- [ ] Performance benchmarks met
- [ ] Golden tests stable (no unexplained diffs)
- [ ] Documentation complete
- [ ] No `# type: ignore` comments (or all justified)
- [ ] No relative imports
- [ ] Legacy code deleted
- [ ] Acceptance testing passed
- [ ] Code review approved

---

## Post-Launch

### Monitoring
- Track compilation times for real shows
- Monitor test stability
- Watch for mypy regressions

### Iteration
- Add new handlers as needed (geometry/movement/dimmer)
- Add new template presets
- Optimize hot paths if performance degrades

### Support
- Handler development guide
- Template authoring examples
- Troubleshooting playbook

---

**END OF IMPLEMENTATION PLAN**

This plan provides a complete, executable roadmap from empty directories to production-ready rewrite. Follow phases sequentially, complete all acceptance criteria, and use exit checklists to maintain quality throughout development.