# Moving Head Sequencer Rewrite - Implementation Plan (Part 1)

**Version:** 1.0  
**Last Updated:** 2026-01-21  
**Status:** Ready for Phase 0 execution

## Executive Summary

This plan breaks down the moving head sequencer rewrite into **6 phases** with **60+ discrete tasks**. Each task includes:
- Clear acceptance criteria (checkboxes for agent tracking)
- Explicit inputs/outputs
- Test requirements with specific test case counts
- Estimated effort in hours
- Dependencies (task IDs)

The plan is optimized for **autonomous agent execution** with clear checkpoints and rollback points.

---

## How to Use This Plan

### For Autonomous Agents
1. **Work linearly through phases** (0 → 1 → 2 → 3 → 4 → 5)
2. **Within each phase, respect dependencies** (Task X.Y depends on Task X.Z)
3. **Complete all acceptance criteria** before marking task done
4. **Run phase exit checklist** before proceeding to next phase
5. **Use rollback points** if phase fails validation

### Task Format
Each task specifies:
- **Effort:** Expected time investment
- **Dependencies:** Which tasks must complete first
- **File:** Exact file path to create/modify
- **Actions:** Step-by-step implementation steps
- **Code Template:** Starter code with contracts
- **Test Requirements:** Specific test cases (checkboxes)
- **Acceptance Criteria:** Must-pass conditions (checkboxes)
- **Output Artifacts:** Files that must exist after task completion

### Progress Tracking
- [ ] indicates incomplete
- [x] indicates complete

---

## Phase 0 — Foundations (Models + Contracts)

**Goal:** Establish type-safe foundation with no behavioral logic  
**Duration:** 3-4 days  
**Success Criteria:** All Pydantic models validate, mypy passes strict mode, 100% model coverage

### Task 0.1: Project Structure Setup
**Effort:** 2 hours  
**Dependencies:** None

**Actions:**
```bash
# Create package structure
mkdir -p packages/blinkb0t/core/curves
mkdir -p packages/blinkb0t/core/sequencer/moving_heads/{models,templates,compile,handlers,export,di,observability}
mkdir -p tests/core/{curves,sequencer/moving_heads/{models,templates,compile,handlers,export}}

# Create __init__.py files for all directories
find packages/blinkb0t/core/curves -type d -exec touch {}/__init__.py \;
find packages/blinkb0t/core/sequencer -type d -exec touch {}/__init__.py \;
find tests/core/curves -type d -exec touch {}/__init__.py \;
find tests/core/sequencer -type d -exec touch {}/__init__.py \;
```

**Acceptance Criteria:**
- [ ] All directories exist
- [ ] All `__init__.py` files present
- [ ] `mypy packages/blinkb0t/core/curves` passes (empty modules)
- [ ] `mypy packages/blinkb0t/core/sequencer` passes (empty modules)
- [ ] Directory structure matches Section 4.2 of spec

**Output Artifacts:**
- Complete directory structure under `packages/blinkb0t/core/`
- Complete test directory structure under `tests/core/`

---

### Task 0.2: Curve Schema Models
**Effort:** 3 hours  
**Dependencies:** Task 0.1  
**File:** `packages/blinkb0t/core/curves/models.py`

**Actions:**
1. Implement `CurvePoint` model with frozen=True
2. Implement `PointsCurve` with monotonic time validation
3. Implement `NativeCurve` model
4. Create `BaseCurve` union type
5. Add comprehensive docstrings with examples

**Code Template:**
```python
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Literal, Any

class CurvePoint(BaseModel):
    """A single point on a normalized curve.
    
    Both t and v are normalized to [0, 1].
    This model is immutable (frozen).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)
    
    t: float = Field(..., ge=0.0, le=1.0, description="Normalized time [0,1]")
    v: float = Field(..., ge=0.0, le=1.0, description="Normalized value [0,1]")


class PointsCurve(BaseModel):
    """Curve defined by explicit points.
    
    Points must have non-decreasing t values (monotonic).
    """
    model_config = ConfigDict(extra="forbid")

    kind: Literal["POINTS"] = "POINTS"
    points: list[CurvePoint] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _validate_monotonic_t(self) -> "PointsCurve":
        last_t = -1.0
        for p in self.points:
            if p.t < last_t:
                raise ValueError("PointsCurve.points must have non-decreasing t")
            last_t = p.t
        return self


class NativeCurve(BaseModel):
    """Curve defined by native curve ID (e.g., LINEAR, HOLD)."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["NATIVE"] = "NATIVE"
    curve_id: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


# Union type for curve specifications
BaseCurve = PointsCurve | NativeCurve
```

**Test Requirements:**
- [ ] Test `CurvePoint` accepts valid values (0.0, 0.5, 1.0)
- [ ] Test `CurvePoint` rejects t < 0
- [ ] Test `CurvePoint` rejects t > 1
- [ ] Test `CurvePoint` rejects v < 0
- [ ] Test `CurvePoint` rejects v > 1
- [ ] Test `CurvePoint` is immutable (cannot modify after creation)
- [ ] Test `PointsCurve` validates monotonic t
- [ ] Test `PointsCurve` rejects non-monotonic points
- [ ] Test `PointsCurve` requires min 2 points
- [ ] Test `PointsCurve` rejects 1 point
- [ ] Test `NativeCurve` requires non-empty curve_id
- [ ] Test `NativeCurve` accepts params dict
- [ ] Test `BaseCurve` union discriminates correctly (POINTS vs NATIVE)
- [ ] Test JSON serialization roundtrip for all models

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] 100% branch coverage on validators
- [ ] All 14 test cases pass
- [ ] Models can serialize to/from JSON
- [ ] No `# type: ignore` comments

**Output Artifacts:**
- `packages/blinkb0t/core/curves/models.py`
- `tests/core/curves/test_models.py`

---

### Task 0.3: Channel and DMX Enums
**Effort:** 1 hour  
**Dependencies:** Task 0.1  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/channel.py`

**Actions:**
1. Define `ChannelName` enum (PAN, TILT, DIMMER)
2. Define `BlendMode` enum (OVERRIDE, ADD)
3. Add docstrings explaining each enum value

**Code Template:**
```python
from enum import Enum

class ChannelName(str, Enum):
    """DMX channel names for moving head fixtures."""
    PAN = "PAN"
    TILT = "TILT"
    DIMMER = "DIMMER"

class BlendMode(str, Enum):
    """How to blend overlapping channel segments."""
    OVERRIDE = "OVERRIDE"  # Later segment replaces earlier
    ADD = "ADD"            # Values are added (for future use)
```

**Test Requirements:**
- [ ] Test enum values are strings
- [ ] Test enum serialization to JSON
- [ ] Test enum deserialization from JSON
- [ ] Test enum in Pydantic model field
- [ ] Test unknown enum value raises error

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 5 test cases pass
- [ ] Enums serialize correctly

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/channel.py`
- `tests/core/sequencer/moving_heads/models/test_channel.py`

---

### Task 0.4: IR Segment Model
**Effort:** 4 hours  
**Dependencies:** Task 0.2, Task 0.3  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/ir.py`

**Actions:**
1. Implement `ChannelSegment` model from Section 4.4
2. Add validator: must have either static_dmx OR curve (not both, not neither)
3. Add validator: t1_ms >= t0_ms
4. Add validator: clamp_max >= clamp_min
5. Add validator: offset_centered requires base_dmx and amplitude_dmx
6. Add comprehensive docstrings

**Code Template:**
```python
from pydantic import BaseModel, Field, ConfigDict, model_validator
from packages.blinkb0t.core.curves.models import BaseCurve
from packages.blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName, BlendMode

class ChannelSegment(BaseModel):
    """IR segment for a single fixture + channel over a time range.

    Either `static_dmx` is set OR `curve` is set (mutually exclusive).
    
    For offset-centered curves (movement), set offset_centered=True
    and provide base_dmx and amplitude_dmx.
    """
    model_config = ConfigDict(extra="forbid")

    fixture_id: str = Field(..., min_length=1)
    channel: ChannelName

    t0_ms: int = Field(..., ge=0)
    t1_ms: int = Field(..., ge=0)

    # Option A: static value
    static_dmx: int | None = Field(default=None, ge=0, le=255)

    # Option B: curve
    curve: BaseCurve | None = Field(default=None)

    # Composition hints (for movement offset curves)
    base_dmx: int | None = Field(default=None, ge=0, le=255)
    amplitude_dmx: int | None = Field(default=None, ge=0, le=255)
    offset_centered: bool = Field(
        default=False,
        description="If true, interpret curve values as offset around 0.5",
    )

    blend_mode: BlendMode = Field(default=BlendMode.OVERRIDE)

    clamp_min: int = Field(default=0, ge=0, le=255)
    clamp_max: int = Field(default=255, ge=0, le=255)

    @model_validator(mode="after")
    def _validate_constraints(self) -> "ChannelSegment":
        # Time ordering
        if self.t1_ms < self.t0_ms:
            raise ValueError("t1_ms must be >= t0_ms")

        # Must have exactly one of static_dmx or curve
        if self.static_dmx is None and self.curve is None:
            raise ValueError("ChannelSegment must set either static_dmx or curve")
        if self.static_dmx is not None and self.curve is not None:
            raise ValueError("ChannelSegment cannot set both static_dmx and curve")

        # Clamp bounds
        if self.clamp_max < self.clamp_min:
            raise ValueError("clamp_max must be >= clamp_min")

        # Offset-centered validation
        if self.curve is not None and self.offset_centered:
            if self.base_dmx is None or self.amplitude_dmx is None:
                raise ValueError("offset_centered curves require base_dmx and amplitude_dmx")

        return self
```

**Test Requirements:**
- [ ] Test static DMX segment creation (valid)
- [ ] Test curve segment creation (valid)
- [ ] Test offset-centered curve with base/amplitude (valid)
- [ ] Test rejects both static_dmx and curve
- [ ] Test rejects neither static_dmx nor curve
- [ ] Test t1_ms < t0_ms raises ValueError
- [ ] Test clamp_max < clamp_min raises ValueError
- [ ] Test offset_centered without base_dmx raises ValueError
- [ ] Test offset_centered without amplitude_dmx raises ValueError
- [ ] Test invalid fixture_id (empty string) raises ValueError
- [ ] Test all field constraints (ge=0, le=255, min_length=1)
- [ ] Test JSON serialization roundtrip

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] 100% branch coverage on validators
- [ ] All 12 test cases pass
- [ ] Can serialize/deserialize to JSON

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/ir.py`
- `tests/core/sequencer/moving_heads/models/test_ir.py`

---

### Task 0.5: Rig Profile Models
**Effort:** 6 hours  
**Dependencies:** Task 0.3  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/rig.py`

**Actions:**
1. Define `ChaseOrder` enum (LEFT_TO_RIGHT, OUTSIDE_IN, etc.)
2. Define `AimZone` enum (SKY, HORIZON, CROWD, STAGE)
3. Implement `FixtureCalibration` model
4. Implement `FixtureDefinition` model
5. Implement `SemanticGroup` model
6. Implement `RigProfile` model
7. Add validator: all fixture_ids in groups must exist in fixtures
8. Add validator: dimmer_floor <= dimmer_ceiling

**Code Template:**
```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum

class ChaseOrder(str, Enum):
    """Order for phase offset spreading."""
    LEFT_TO_RIGHT = "LEFT_TO_RIGHT"
    RIGHT_TO_LEFT = "RIGHT_TO_LEFT"
    OUTSIDE_IN = "OUTSIDE_IN"
    INSIDE_OUT = "INSIDE_OUT"

class AimZone(str, Enum):
    """Predefined aim targets."""
    SKY = "SKY"
    HORIZON = "HORIZON"
    CROWD = "CROWD"
    STAGE = "STAGE"

class FixtureCalibration(BaseModel):
    """Calibration settings for a fixture."""
    model_config = ConfigDict(extra="forbid")
    
    pan_min_dmx: int = Field(0, ge=0, le=255)
    pan_max_dmx: int = Field(255, ge=0, le=255)
    tilt_min_dmx: int = Field(0, ge=0, le=255)
    tilt_max_dmx: int = Field(255, ge=0, le=255)
    
    pan_inverted: bool = Field(False)
    tilt_inverted: bool = Field(False)
    
    dimmer_floor_dmx: int = Field(0, ge=0, le=255)
    dimmer_ceiling_dmx: int = Field(255, ge=0, le=255)
    
    @field_validator("dimmer_ceiling_dmx")
    @classmethod
    def validate_dimmer_range(cls, v: int, info) -> int:
        floor = info.data.get("dimmer_floor_dmx", 0)
        if v < floor:
            raise ValueError(f"dimmer_ceiling_dmx ({v}) < dimmer_floor_dmx ({floor})")
        return v

class FixtureDefinition(BaseModel):
    """Physical fixture definition."""
    model_config = ConfigDict(extra="forbid")
    
    fixture_id: str = Field(..., min_length=1)
    universe: int = Field(..., ge=1, le=512)
    start_address: int = Field(..., ge=1, le=512)
    
    role: str | None = Field(None)
    spatial_position: tuple[float, float] | None = Field(None)
    
    calibration: FixtureCalibration = Field(default_factory=FixtureCalibration)

class SemanticGroup(BaseModel):
    """Logical grouping of fixtures."""
    model_config = ConfigDict(extra="forbid")
    
    group_id: str = Field(..., min_length=1)
    fixture_ids: list[str] = Field(..., min_length=1)
    order: ChaseOrder = Field(ChaseOrder.LEFT_TO_RIGHT)

class RigProfile(BaseModel):
    """Complete rig configuration."""
    model_config = ConfigDict(extra="forbid")
    
    rig_id: str = Field(..., min_length=1)
    fixtures: list[FixtureDefinition] = Field(..., min_length=1)
    groups: list[SemanticGroup] = Field(default_factory=list)
    
    default_dimmer_floor_dmx: int = Field(60, ge=0, le=255)
    default_dimmer_ceiling_dmx: int = Field(255, ge=0, le=255)
    
    @field_validator("groups")
    @classmethod
    def validate_group_fixtures(cls, groups: list[SemanticGroup], info) -> list[SemanticGroup]:
        fixtures = info.data.get("fixtures", [])
        fixture_ids = {f.fixture_id for f in fixtures}
        
        for group in groups:
            for fid in group.fixture_ids:
                if fid not in fixture_ids:
                    raise ValueError(
                        f"Group {group.group_id} references unknown fixture: {fid}"
                    )
        
        return groups
```

**Test Requirements:**
- [ ] Test minimal valid `RigProfile`
- [ ] Test `FixtureCalibration` with defaults
- [ ] Test `FixtureCalibration` with custom ranges
- [ ] Test dimmer_ceiling < dimmer_floor raises ValueError
- [ ] Test group references non-existent fixture raises ValueError
- [ ] Test group with valid fixture IDs (passes)
- [ ] Test pan/tilt inversion flags
- [ ] Test universe/address bounds (1-512)
- [ ] Test empty fixture list raises ValueError
- [ ] Test multiple groups
- [ ] Test spatial_position for ordering
- [ ] Test JSON serialization roundtrip

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] 100% branch coverage on validators
- [ ] All 12 test cases pass
- [ ] Example rig profile serializes correctly

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/rig.py`
- `tests/core/sequencer/moving_heads/models/test_rig.py`
- `tests/fixtures/example_rig_4fixtures.json` (4-fixture example)

---

### Task 0.6: Template Timing Models
**Effort:** 4 hours  
**Dependencies:** Task 0.5  
**File:** `packages/blinkb0t/core/sequencer/moving_heads/models/template.py`

**Actions:**
1. Define `RepeatMode` enum (PING_PONG, JOINER)
2. Define `RemainderPolicy` enum (HOLD_LAST_POSE, FADE_OUT, TRUNCATE)
3. Define `PhaseOffsetMode` enum (NONE, GROUP_ORDER)
4. Define `Distribution` enum (LINEAR)
5. Implement `BaseTiming` model
6. Implement `PhaseOffset` model
7. Implement `RepeatContract` model

**Code Template:**
```python
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum

class RepeatMode(str, Enum):
    PING_PONG = "PING_PONG"
    JOINER = "JOINER"

class RemainderPolicy(str, Enum):
    HOLD_LAST_POSE = "HOLD_LAST_POSE"
    FADE_OUT = "FADE_OUT"
    TRUNCATE = "TRUNCATE"

class PhaseOffsetMode(str, Enum):
    NONE = "NONE"
    GROUP_ORDER = "GROUP_ORDER"

class Distribution(str, Enum):
    LINEAR = "LINEAR"

class BaseTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    start_offset_bars: float = Field(..., ge=0.0)
    duration_bars: float = Field(..., gt=0.0)

class PhaseOffset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    mode: PhaseOffsetMode
    group: str | None = Field(None)
    order: str | None = Field(None)  # ChaseOrder name
    spread_bars: float = Field(0.0, ge=0.0)
    distribution: Distribution = Field(Distribution.LINEAR)
    wrap: bool = Field(True)
    
    @field_validator("group")
    @classmethod
    def validate_group_required(cls, v: str | None, info) -> str | None:
        mode = info.data.get("mode")
        if mode == PhaseOffsetMode.GROUP_ORDER and v is None:
            raise ValueError("group required when mode=GROUP_ORDER")
        return v

class RepeatContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    repeatable: bool = Field(True)
    mode: RepeatMode = Field(RepeatMode.PING_PONG)
    cycle_bars: float = Field(..., gt=0.0)
    loop_step_ids: list[str] = Field(..., min_length=1)
    remainder_policy: RemainderPolicy = Field(RemainderPolicy.HOLD_LAST_POSE)
```

**Test Requirements:**
- [ ] Test `BaseTiming` with valid values
- [ ] Test `BaseTiming` rejects duration <= 0
- [ ] Test `BaseTiming` allows start_offset = 0
- [ ] Test `PhaseOffset` with mode=NONE
- [ ] Test `PhaseOffset` with mode=GROUP_ORDER requires group
- [ ] Test `PhaseOffset` spread_bars >= 0
- [ ] Test `RepeatContract` requires positive cycle_bars
- [ ] Test `RepeatContract` requires non-empty loop_step_ids
- [ ] Test JSON serialization for all models

**Acceptance Criteria:**
- [ ] `mypy --strict` passes
- [ ] All 9 test cases pass
- [ ] Models serialize to JSON

**Output Artifacts:**
- `packages/blinkb0t/core/sequencer/moving_heads/models/template.py` (partial)
- `tests/core/sequencer/moving_heads/models/test_template_timing.py`

---

*This plan continues with Tasks 0.7-0.10 in Part 2...*