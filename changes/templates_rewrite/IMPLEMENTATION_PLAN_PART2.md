# Moving Head Sequencer Rewrite - Implementation Plan (Part 2)

## Phase 0 (Continued)

### Task 0.7: Template Step Models
**Effort:** 5 hours  
**Dependencies:** Task 0.6  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/template.py` (continuation)

**Actions:**
1. Implement `Geometry` model
2. Implement `Movement` model
3. Implement `Dimmer` model
4. Implement `StepTiming` model (wraps BaseTiming + PhaseOffset)
5. Implement `TemplateStep` model

**Code Template:**
```python
from typing import Any

class Geometry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    geometry_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    
    # ROLE_POSE specific fields
    pan_pose_by_role: dict[str, str] | None = Field(None)
    tilt_pose: str | None = Field(None)
    aim_zone: str | None = Field(None)

class Movement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    movement_id: str = Field(..., min_length=1)
    intensity: str = Field("SMOOTH")
    cycles: float = Field(1.0, gt=0.0)
    params: dict[str, Any] = Field(default_factory=dict)

class Dimmer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    dimmer_id: str = Field(..., min_length=1)
    intensity: str = Field("SMOOTH")
    min_norm: float = Field(0.0, ge=0.0, le=1.0)
    max_norm: float = Field(1.0, ge=0.0, le=1.0)
    cycles: float = Field(1.0, gt=0.0)
    params: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("max_norm")
    @classmethod
    def validate_range(cls, v: float, info) -> float:
        min_norm = info.data.get("min_norm", 0.0)
        if v < min_norm:
            raise ValueError(f"max_norm ({v}) < min_norm ({min_norm})")
        return v

class StepTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    base_timing: BaseTiming
    phase_offset: PhaseOffset | None = Field(None)

class TemplateStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    step_id: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    timing: StepTiming
    geometry: Geometry
    movement: Movement
    dimmer: Dimmer
```

**Test Requirements:**
- [ ] Test `Geometry` with minimal fields
- [ ] Test `Geometry` with ROLE_POSE params
- [ ] Test `Movement` requires positive cycles
- [ ] Test `Movement` with defaults
- [ ] Test `Dimmer` validates min_norm <= max_norm
- [ ] Test `Dimmer` rejects max_norm < min_norm
- [ ] Test `Dimmer` requires positive cycles
- [ ] Test `TemplateStep` complete structure
- [ ] Test `TemplateStep` with optional phase_offset
- [ ] Test JSON serialization for all models

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 10 test cases pass
- [ ] Can construct complete step from JSON

**Output Artifacts:**
- Updated `packages/blinkb0t/core/sequencer/moving_heads/models/template.py`
- `tests/core/sequencer/moving_heads/models/test_template_steps.py`

---

### Task 0.8: Template and Preset Models
**Effort:** 5 hours  
**Dependencies:** Task 0.7  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/template.py` (continuation)

**Actions:**
1. Implement `TemplateMetadata` model
2. Implement `Template` model
3. Implement `StepPatch` model
4. Implement `TemplatePreset` model
5. Implement `TemplateDoc` model
6. Add validator: loop_step_ids must reference real steps
7. Add validator: step targets must reference real groups

**Code Template:**
```python
class TemplateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    tags: list[str] = Field(default_factory=list)
    energy_range: tuple[int, int] | None = Field(None)
    description: str | None = Field(None)

class Template(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    template_id: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    
    roles: list[str] = Field(..., min_length=1)
    groups: dict[str, list[str]] = Field(..., min_length=1)
    
    repeat: RepeatContract
    defaults: dict[str, Any] = Field(default_factory=dict)
    steps: list[TemplateStep] = Field(..., min_length=1)
    metadata: TemplateMetadata = Field(default_factory=TemplateMetadata)
    
    @field_validator("repeat")
    @classmethod
    def validate_loop_steps_exist(cls, repeat: RepeatContract, info) -> RepeatContract:
        steps = info.data.get("steps", [])
        step_ids = {s.step_id for s in steps}
        
        for loop_step_id in repeat.loop_step_ids:
            if loop_step_id not in step_ids:
                raise ValueError(f"Loop step {loop_step_id} not found in template steps")
        
        return repeat
    
    @field_validator("steps")
    @classmethod
    def validate_step_targets(cls, steps: list[TemplateStep], info) -> list[TemplateStep]:
        groups = info.data.get("groups", {})
        
        for step in steps:
            if step.target not in groups:
                raise ValueError(f"Step {step.step_id} targets unknown group: {step.target}")
        
        return steps

class StepPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    geometry: dict[str, Any] | None = Field(None)
    movement: dict[str, Any] | None = Field(None)
    dimmer: dict[str, Any] | None = Field(None)
    timing: dict[str, Any] | None = Field(None)

class TemplatePreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    preset_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    defaults: dict[str, Any] = Field(default_factory=dict)
    step_patches: dict[str, StepPatch] = Field(default_factory=dict)

class TemplateDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    template: Template
    presets: list[TemplatePreset] = Field(default_factory=list)
```

**Test Requirements:**
- [ ] Test minimal valid `Template`
- [ ] Test `Template` with all fields populated
- [ ] Test loop_step_ids validation (non-existent step_id fails)
- [ ] Test step target validation (non-existent group fails)
- [ ] Test groups reference valid roles
- [ ] Test `TemplatePreset` structure
- [ ] Test `TemplateDoc` wraps template + presets
- [ ] Test JSON roundtrip for complete TemplateDoc
- [ ] Test example from Section 2.8 validates

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 9 test cases pass
- [ ] Example template from Section 2.8 validates successfully

**Output Artifacts:**
- Completed `packages/blinkb0t/core/sequencer/moving_heads/models/template.py`
- `tests/core/sequencer/moving_heads/models/test_template_full.py`
- `tests/fixtures/fan_pulse_template.json` (from Section 2.8)

---

### Task 0.9: Playback Plan Model
**Effort:** 2 hours  
**Dependencies:** Task 0.8  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/plan.py`

**Actions:**
1. Implement `PlaybackPlan` model
2. Add validator: window_end_ms >= window_start_ms

**Code Template:**
```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Any

class PlaybackPlan(BaseModel):
    """Plan for compiling a template into a playback window."""
    model_config = ConfigDict(extra="forbid")
    
    template_id: str = Field(..., min_length=1)
    preset_id: str | None = Field(None)
    modifiers: dict[str, str] = Field(default_factory=dict)
    
    window_start_ms: int = Field(..., ge=0)
    window_end_ms: int = Field(..., ge=0)
    
    @field_validator("window_end_ms")
    @classmethod
    def validate_window(cls, window_end_ms: int, info) -> int:
        window_start_ms = info.data.get("window_start_ms", 0)
        if window_end_ms < window_start_ms:
            raise ValueError(
                f"window_end_ms ({window_end_ms}) < window_start_ms ({window_start_ms})"
            )
        return window_end_ms
```

**Test Requirements:**
- [ ] Test minimal valid plan (no preset/modifiers)
- [ ] Test plan with preset
- [ ] Test plan with modifiers
- [ ] Test window_end < window_start raises ValueError
- [ ] Test window_end = window_start (valid, zero duration)

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 5 test cases pass

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/plan.py`
- `tests/core/sequencer/moving_heads/models/test_plan.py`

---

### Task 0.10: Beat Mapper Protocol
**Effort:** 2 hours  
**Dependencies:** Task 0.1  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/protocols.py`

**Actions:**
1. Define `BeatMapper` Protocol
2. Add comprehensive docstrings
3. Create `MockBeatMapper` for testing

**Code Template:**
```python
from typing import Protocol

class BeatMapper(Protocol):
    """Protocol for converting between musical time and absolute time."""
    
    def bars_to_ms(self, bars: float) -> float:
        """Convert bars to milliseconds."""
        ...
    
    def ms_to_bars(self, ms: float) -> float:
        """Convert milliseconds to bars."""
        ...
    
    def get_beat_at(self, ms: float) -> int:
        """Get beat number at given time (1-indexed)."""
        ...

class MockBeatMapper:
    """Mock implementation for testing (120 BPM, 4/4 time)."""
    
    def __init__(self, bpm: float = 120.0, beats_per_bar: int = 4):
        self.bpm = bpm
        self.beats_per_bar = beats_per_bar
        self.ms_per_beat = 60_000.0 / bpm
        self.ms_per_bar = self.ms_per_beat * beats_per_bar
    
    def bars_to_ms(self, bars: float) -> float:
        return bars * self.ms_per_bar
    
    def ms_to_bars(self, ms: float) -> float:
        return ms / self.ms_per_bar
    
    def get_beat_at(self, ms: float) -> int:
        return int(ms / self.ms_per_beat) + 1
```

**Test Requirements:**
- [ ] Test `MockBeatMapper` at 120 BPM
- [ ] Test `MockBeatMapper` at 90 BPM
- [ ] Test bars_to_ms roundtrip accuracy
- [ ] Test ms_to_bars roundtrip accuracy
- [ ] Test get_beat_at for beat 1, 2, 3, 4
- [ ] Test fractional bars conversion

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 6 test cases pass
- [ ] Protocol properly typed

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/protocols.py`
- `tests/core/sequencer/moving_heads/models/test_protocols.py`

---

### Phase 0 Exit Criteria

**Before proceeding to Phase 1, verify:**

- [ ] All Tasks 0.1-0.10 completed
- [ ] `mypy --strict packages/blinkb0t/core/curves` passes
- [ ] `mypy --strict packages/blinkb0t/core/sequencer/moving_heads/models` passes
- [ ] Test coverage ≥ 95% for all models
- [ ] All models serialize/deserialize to JSON correctly
- [ ] Example fixture files (rig, template) validate
- [ ] No `# type: ignore` comments in models
- [ ] All Pydantic validators have test coverage
- [ ] Documentation strings present on all public classes/methods
- [ ] All acceptance criteria checkboxes marked

**Rollback Point:** If Phase 0 fails, no behavioral code exists yet—safe to restart.

---

## Phase 1 — Curve Provider (Shared)

**Goal:** Implement pure curve operations  
**Duration:** 4-5 days  
**Success Criteria:** All curve operations deterministic, tested, and performant

### Task 1.1: Curve Sampling Infrastructure
**Effort:** 4 hours  
**Dependencies:** Task 0.2  
**File:** `packages/blinkb0t/core/curves/sampling.py`

**Actions:**
1. Implement `sample_uniform_grid(n: int) -> list[float]`
2. Implement `interpolate_linear(points, t) -> float`
3. Add edge case handling

**Code Template:**
```python
from packages.blinkb0t.core.curves.models import CurvePoint

def sample_uniform_grid(n: int) -> list[float]:
    """Generate N evenly-spaced samples in [0, 1).
    
    Returns N samples: [0.0, 1/N, 2/N, ..., (N-1)/N]
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    return [i / n for i in range(n)]

def interpolate_linear(points: list[CurvePoint], t: float) -> float:
    """Linearly interpolate value at time t."""
    if not points:
        raise ValueError("points cannot be empty")
    if not (0.0 <= t <= 1.0):
        raise ValueError(f"t must be in [0, 1], got {t}")
    
    # Edge cases
    if t <= points[0].t:
        return points[0].v
    if t >= points[-1].t:
        return points[-1].v
    
    # Find bracket
    for i in range(len(points) - 1):
        if points[i].t <= t <= points[i + 1].t:
            t0, v0 = points[i].t, points[i].v
            t1, v1 = points[i + 1].t, points[i + 1].v
            if t1 > t0:
                alpha = (t - t0) / (t1 - t0)
                return v0 + alpha * (v1 - v0)
            else:
                return v0
    
    return points[-1].v
```

**Test Requirements:**
- [ ] Test `sample_uniform_grid(2)` returns [0.0, 0.5]
- [ ] Test `sample_uniform_grid(4)` returns [0.0, 0.25, 0.5, 0.75]
- [ ] Test `sample_uniform_grid(1)` raises ValueError
- [ ] Test `interpolate_linear` at exact points
- [ ] Test `interpolate_linear` midpoint between two points
- [ ] Test `interpolate_linear` before first point (clamps)
- [ ] Test `interpolate_linear` after last point (clamps)
- [ ] Test `interpolate_linear` with t < 0 raises ValueError
- [ ] Test `interpolate_linear` with t > 1 raises ValueError
- [ ] Benchmark: 1000 interpolations < 10ms

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 10 test cases pass
- [ ] Performance benchmark met

**Output Artifacts:**
- `packages/blinkb0t/core/curves/sampling.py`
- `tests/core/curves/test_sampling.py`

---

### Task 1.2: Phase Shift Implementation (MANDATORY Option B)
**Effort:** 5 hours  
**Dependencies:** Task 1.1  
**File:** `packages/blinkb0t/core/curves/phase.py`

**Actions:**
1. Implement `apply_phase_shift_samples()` using sampling approach
2. Handle wrap vs. no-wrap modes
3. Optimize for exact integer sample offsets

**Code Template:**
```python
from packages.blinkb0t.core.curves.models import CurvePoint
from packages.blinkb0t.core.curves.sampling import sample_uniform_grid, interpolate_linear

def apply_phase_shift_samples(
    points: list[CurvePoint],
    offset_norm: float,
    n_samples: int,
    wrap: bool = True
) -> list[CurvePoint]:
    """Apply phase shift by resampling (MANDATORY Option B).
    
    Generates N uniformly-spaced output samples, each sampling
    from the original curve at (t + offset_norm).
    """
    if not points:
        raise ValueError("points cannot be empty")
    if n_samples < 2:
        raise ValueError("n_samples must be >= 2")
    
    t_grid = sample_uniform_grid(n_samples)
    
    shifted_points = []
    for t in t_grid:
        t_shifted = t + offset_norm
        
        if wrap:
            t_shifted = t_shifted % 1.0
        else:
            t_shifted = max(0.0, min(1.0, t_shifted))
        
        v = interpolate_linear(points, t_shifted)
        shifted_points.append(CurvePoint(t=t, v=v))
    
    return shifted_points
```

**Test Requirements:**
- [ ] Test zero offset (identity)
- [ ] Test offset=0.25 on linear 0→1 ramp
- [ ] Test offset=0.5 (half cycle)
- [ ] Test offset > 1.0 wraps correctly
- [ ] Test negative offset wraps correctly
- [ ] Test wrap=False clamps at boundaries
- [ ] Test exact integer sample offset (n=4, offset=0.25 → 1 sample shift)
- [ ] Test on sine wave (visual phase shift)
- [ ] Test n_samples=2 (minimal case)
- [ ] Benchmark: 64-sample curve shift < 1ms

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 10 test cases pass
- [ ] Performance < 1ms for 64 samples
- [ ] Bit-exact for integer sample offsets

**Output Artifacts:**
- `packages/blinkb0t/core/curves/phase.py`
- `tests/core/curves/test_phase.py`

---

### Task 1.3: Curve Composition (Envelope/Multiply)
**Effort:** 4 hours  
**Dependencies:** Task 1.1  
**File:** `packages/blinkb0t/core/curves/composition.py`

**Actions:**
1. Implement `multiply_curves(a, b) -> list[CurvePoint]`
2. Implement `apply_envelope()` as alias
3. Handle aligned/unaligned grids

**Code Template:**
```python
from packages.blinkb0t.core.curves.models import CurvePoint
from packages.blinkb0t.core.curves.sampling import sample_uniform_grid, interpolate_linear

def multiply_curves(
    a: list[CurvePoint],
    b: list[CurvePoint],
    n_samples: int | None = None
) -> list[CurvePoint]:
    """Pointwise multiplication: (a * b)."""
    if not a or not b:
        raise ValueError("Both curves must be non-empty")
    
    if n_samples is None:
        n_samples = max(len(a), len(b))
    
    t_grid = sample_uniform_grid(n_samples)
    
    result = []
    for t in t_grid:
        va = interpolate_linear(a, t)
        vb = interpolate_linear(b, t)
        result.append(CurvePoint(t=t, v=va * vb))
    
    return result

def apply_envelope(
    curve: list[CurvePoint],
    envelope: list[CurvePoint],
    n_samples: int | None = None
) -> list[CurvePoint]:
    """Apply envelope to curve (alias for multiply_curves)."""
    return multiply_curves(curve, envelope, n_samples)
```

**Test Requirements:**
- [ ] Test multiply by identity (a * 1.0 = a)
- [ ] Test multiply by zero (a * 0.0 = 0)
- [ ] Test multiply two linear ramps
- [ ] Test envelope fade-in (0→1) on constant
- [ ] Test envelope fade-out (1→0) on constant
- [ ] Test mismatched sample counts (resamples)
- [ ] Test n_samples override
- [ ] Test result bounds [0, 1]
- [ ] Benchmark: 64-sample multiply < 1ms

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 9 test cases pass
- [ ] Performance < 1ms

**Output Artifacts:**
- `packages/blinkb0t/core/curves/composition.py`
- `tests/core/curves/test_composition.py`

---

### Task 1.4: RDP Simplification
**Effort:** 6 hours  
**Dependencies:** Task 1.1  
**File:** `packages/blinkb0t/core/curves/simplification.py`

**Actions:**
1. Implement perpendicular distance calculation
2. Implement recursive RDP algorithm
3. Add tolerance parameter (default ε = 1/255)
4. Validate output properties

**Code Template:**
```python
from packages.blinkb0t.core.curves.models import CurvePoint
import math

def perpendicular_distance(
    point: CurvePoint,
    line_start: CurvePoint,
    line_end: CurvePoint,
    scale_t: float = 1.0,
    scale_v: float = 1.0
) -> float:
    """Perpendicular distance in scaled space."""
    px, py = point.t * scale_t, point.v * scale_v
    ax, ay = line_start.t * scale_t, line_start.v * scale_v
    bx, by = line_end.t * scale_t, line_end.v * scale_v
    
    abx, aby = bx - ax, by - ay
    ab_len_sq = abx * abx + aby * aby
    
    if ab_len_sq < 1e-10:
        return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)
    
    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))
    
    cx, cy = ax + t * abx, ay + t * aby
    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2)

def simplify_rdp(
    points: list[CurvePoint],
    epsilon: float = 1.0 / 255.0,
    scale_t: float = 1.0,
    scale_v: float = 1.0
) -> list[CurvePoint]:
    """Ramer-Douglas-Peucker simplification."""
    if len(points) <= 2:
        return points
    
    def rdp_recursive(start_idx: int, end_idx: int) -> list[int]:
        if end_idx - start_idx <= 1:
            return []
        
        max_dist = 0.0
        max_idx = start_idx
        
        for i in range(start_idx + 1, end_idx):
            dist = perpendicular_distance(
                points[i], points[start_idx], points[end_idx],
                scale_t, scale_v
            )
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        
        if max_dist > epsilon:
            left = rdp_recursive(start_idx, max_idx)
            right = rdp_recursive(max_idx, end_idx)
            return left + [max_idx] + right
        else:
            return []
    
    keep_indices = [0] + rdp_recursive(0, len(points) - 1) + [len(points) - 1]
    keep_indices = sorted(set(keep_indices))
    
    return [points[i] for i in keep_indices]
```

**Test Requirements:**
- [ ] Test preserves endpoints
- [ ] Test collinear points removed
- [ ] Test sine wave (some interior kept)
- [ ] Test epsilon=0 (no simplification)
- [ ] Test epsilon=large (aggressive)
- [ ] Test scaled space preference
- [ ] Verify monotonic t in output
- [ ] Verify max deviation <= epsilon
- [ ] Benchmark: 256-point curve < 5ms

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 9 test cases pass
- [ ] Performance < 5ms for 256 points
- [ ] Max deviation validation passes

**Output Artifacts:**
- `packages/blinkb0t/core/curves/simplification.py`
- `tests/core/curves/test_simplification.py`

---

*This plan continues with Phase 1 completion and Phase 2-6 in subsequent parts...*