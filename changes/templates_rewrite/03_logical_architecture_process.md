# Section 3: Logical Architecture & Process Flow

**Version**: 1.0  
**Date**: January 2026  
**Status**: Process Architecture Specification

---

## Overview

This document defines the **end-to-end compilation pipeline** that transforms high-level choreography intent (templates + presets + plans) into executable DMX sequences (channel segments). This is the "how" that connects the declarative "what" to the concrete output.

**Key Concept**: The compiler is a pure transformation pipeline with no side effects. Dependencies are injected, not discovered.

---

## 1. System Architecture Overview

### 1.1 Conceptual Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUTS                                   │
├─────────────────────────────────────────────────────────────────┤
│  • Template (roles, steps, repeat contract)                     │
│  • Preset (parameter patches)                                   │
│  • Playback Plan (section window, BPM, modifiers)               │
│  • Rig Profile (fixtures, calibration, groups, orders)          │
│  • Audio Context (beat grid, section boundaries)                 │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    COMPILATION PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│  1. Load & Patch Template                                       │
│     ├─ Apply preset patches                                     │
│     ├─ Apply modifier patches (optional)                        │
│     └─ Validate combined template                               │
│                                                                  │
│  2. Time Resolution                                              │
│     ├─ Map section window to bars/milliseconds                  │
│     ├─ Calculate repeat cycles                                  │
│     └─ Compute step time boundaries                             │
│                                                                  │
│  3. Fixture Resolution                                           │
│     ├─ Map template groups → rig fixtures                       │
│     ├─ Validate role compatibility                              │
│     └─ Compute phase offsets per fixture                        │
│                                                                  │
│  4. Per-Step Compilation                                         │
│     ├─ Resolve Geometry (base pose)                             │
│     ├─ Generate Movement (offset curves)                        │
│     ├─ Generate Dimmer (normalized curves)                      │
│     ├─ Apply Phase Shifts                                       │
│     ├─ Generate Transitions                                     │
│     └─ Compose & Clamp                                          │
│                                                                  │
│  5. Emit Channel Segments                                        │
│     └─ Create ChannelSegment IR per fixture/channel             │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                        OUTPUT (IR)                               │
├─────────────────────────────────────────────────────────────────┤
│  List[ChannelSegment]:                                           │
│    • fixture_id, channel (PAN/TILT/DIMMER)                      │
│    • t0_ms, t1_ms (absolute time window)                        │
│    • curve: PointsCurve (normalized [0,1])                  │
│    • base_dmx, amplitude_dmx (for movement composition)         │
│    • clamp_min, clamp_max (safety limits)                       │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    EXPORT / RENDERING                            │
├─────────────────────────────────────────────────────────────────┤
│  • xLights Adapter: Convert to absolute DMX point arrays        │
│  • Other Outputs: OSC, ArtNet, visualization, etc.              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Separation of Concerns

| Layer                | Responsibility                           | Artifacts                      |
|---------------------|------------------------------------------|--------------------------------|
| **Template Layer**  | Choreographic intent                     | Template, Presets          |
| **Configuration**   | Hardware mapping                         | RigProfile                     |
| **Planning Layer**  | Musical timing, section selection        | PlaybackPlan                   |
| **Compilation**     | Transform intent → curves                | ChannelSegment IR              |
| **Export**          | Format conversion                        | xLights JSON, OSC, etc.        |

**Critical Rule**: Each layer only knows about the layer directly below it. Templates never touch DMX. Compilers never touch xLights formats.

---

## 2. Configuration Precedence

When the same parameter appears at multiple levels, **higher precedence wins**:

```
1. Base Template           (lowest)
   ↓
2. Preset Patch
   ↓
3. Modifier Patch
   ↓
4. Per-Cycle Override
   ↓
5. Safety Clamp            (highest)
```

### Example: Dimmer Floor Precedence

```python
def resolve_dimmer_floor(rig, template, step, override) -> int:
    """
    Combine multiple sources with precedence rules.
    """
    floors = [
        rig.calibration.global_.dimmer_floor_dmx,      # 30 (hardware minimum)
        template.defaults.dimmer_floor_dmx,            # 60 (template policy)
        step.dimmer_floor_dmx,                         # 80 (step override)
        override.get("dimmer_floor_dmx")               # 100 (cycle override)
    ]
    
    # Remove None values, take maximum
    valid_floors = [f for f in floors if f is not None]
    return max(valid_floors) if valid_floors else 0
```

**Result**: Most restrictive (highest) floor wins → ensures safety and intent.

---

## 3. End-to-End Process Flow

### 3.1 Phase 1: Template Loading & Patching

#### Input
- Template ID: `"fan_pulse"`
- Preset ID: `"ENERGETIC"`
- Optional modifiers: `{"intensity": "HIGH"}`

#### Process

```python
def load_and_patch_template(
    template_id: str,
    preset_id: str | None,
    modifiers: dict[str, str] | None,
    template_registry: dict[str, Template],
    preset_registry: dict[str, TemplatePreset]
) -> Template:
    """
    Load base template and apply patches.
    """
    # 1. Load base
    template = template_registry[template_id].model_copy(deep=True)
    
    # 2. Apply preset
    if preset_id:
        preset = preset_registry[f"{template_id}:{preset_id}"]
        template = apply_preset(template, preset)
    
    # 3. Apply modifiers (if any)
    if modifiers:
        modifier_patch = generate_modifier_patch(modifiers)
        template = apply_modifier_patch(template, modifier_patch)
    
    # 4. Validate
    template.model_validate(template)
    
    return template
```

#### Modifier Generation (Optional)

Modifiers are **categorical knobs** that generate patches:

```python
def generate_modifier_patch(modifiers: dict[str, str]) -> dict:
    """
    Map categorical modifiers to parameter adjustments.
    """
    patches = {}
    
    if "intensity" in modifiers:
        intensity_map = {
            "LOW": {"movement": {"intensity": "smooth"}, "dimmer": {"intensity": "smooth"}},
            "MEDIUM": {"movement": {"intensity": "dramatic"}, "dimmer": {"intensity": "dramatic"}},
            "HIGH": {"movement": {"intensity": "intense"}, "dimmer": {"intensity": "intense"}}
        }
        patches.update(intensity_map[modifiers["intensity"]])
    
    if "speed" in modifiers:
        speed_map = {
            "SLOW": {"movement": {"cycles": 0.5}, "dimmer": {"cycles": 1.0}},
            "NORMAL": {"movement": {"cycles": 1.0}, "dimmer": {"cycles": 2.0}},
            "FAST": {"movement": {"cycles": 2.0}, "dimmer": {"cycles": 4.0}}
        }
        patches.update(speed_map[modifiers["speed"]])
    
    return patches
```

**LLM Impact**: Instead of selecting from 50 templates, LLM selects:
- 1 base template
- 1 preset (or None)
- 0-3 categorical modifiers

**Complexity reduction**: 50 templates → 12 templates × 3 presets × ~2 modifier combos = ~70 effective variations (but only 12 files to maintain).

---

### 3.2 Phase 2: Time Resolution & Beat Mapping

#### Input
- Template (with timing in bars)
- Plan window: `start_bar=64.0, duration_bars=16.0`
- Audio context: `bpm=120, beats_per_bar=4`

#### Process

##### Step 1: Convert Bars to Milliseconds

```python
def bars_to_ms(bars: float, bpm: float, beats_per_bar: int = 4) -> int:
    """
    Musical time → absolute time.
    """
    ms_per_beat = 60_000.0 / bpm
    ms_per_bar = ms_per_beat * beats_per_bar
    return round(bars * ms_per_bar)
```

Example:
- BPM = 120
- 1 beat = 500ms
- 1 bar (4 beats) = 2000ms
- 16 bars = 32,000ms

##### Step 2: Calculate Repeat Cycles

```python
def calculate_cycles(
    section_duration_bars: float,
    cycle_bars: float,
    repeatable: bool
) -> tuple[int, float]:
    """
    Determine full cycles + remainder.
    """
    if not repeatable:
        return (1, 0.0)
    
    full_cycles = int(section_duration_bars // cycle_bars)
    remainder = section_duration_bars - (full_cycles * cycle_bars)
    
    return (full_cycles, remainder)
```

Example:
- Section: 16 bars
- Cycle: 4 bars
- Result: 4 full cycles, 0 remainder

##### Step 3: Compute Step Windows

For each step in each cycle:

```python
def compute_step_window(
    step: Step,
    cycle_index: int,
    cycle_offset_bars: float,
    plan: PlaybackPlan
) -> StepWindow:
    """
    Map step timing to absolute time.
    """
    base_timing = step.timing.base_timing
    
    step_start_bars = cycle_offset_bars + base_timing.start_offset_bars
    step_end_bars = step_start_bars + base_timing.duration_bars
    
    t0_ms = bars_to_ms(step_start_bars, plan.bpm, plan.beats_per_bar)
    t1_ms = bars_to_ms(step_end_bars, plan.bpm, plan.beats_per_bar)
    
    return StepWindow(t0_ms=t0_ms, t1_ms=t1_ms)
```

**Cycle Offset Calculation**:

```python
for cycle_index in range(total_cycles):
    cycle_offset_bars = plan.window.start_bar + (cycle_index * template.repeat.cycle_bars)
    # Compile steps with this offset
```

Example timeline:
```
Section: bars [64, 80)  (16 bars total)
Cycle 0: [64, 68)   → intro [64, 65), main [65, 68)
Cycle 1: [68, 72)   → main [68, 72)
Cycle 2: [72, 76)   → main [72, 76)
Cycle 3: [76, 80)   → main [76, 80)
```

---

### 3.3 Phase 3: Group Targeting & Phase Offsets

#### Step 1: Resolve Fixtures from Target Group

```python
def resolve_target_fixtures(
    step: Step,
    rig: RigProfile
) -> list[str]:
    """
    Map step.target (group name) to fixture IDs.
    """
    target_group = step.target
    
    if target_group not in rig.groups:
        raise ValueError(f"Unknown target group: {target_group}")
    
    return list(rig.groups[target_group])
```

Example:
- Step target: `"ALL"`
- Rig groups: `{"ALL": ["mh1", "mh2", "mh3", "mh4"]}`
- Result: `["mh1", "mh2", "mh3", "mh4"]`

#### Step 2: Compute Phase Offsets

```python
def compute_phase_offsets(
    step: Step,
    fixtures: list[str],
    rig: RigProfile,
    plan: PlaybackPlan
) -> dict[str, int]:
    """
    Calculate per-fixture time offset in milliseconds.
    """
    phase_spec = step.timing.phase_offset
    
    # No phase offset
    if not phase_spec or phase_spec.mode == PhaseOffsetMode.NONE:
        return {fx: 0 for fx in fixtures}
    
    # GROUP_ORDER mode
    if phase_spec.mode == PhaseOffsetMode.GROUP_ORDER:
        # Get ordered fixtures
        order_name = phase_spec.order.value
        full_order = rig.orders[order_name]
        
        # Filter to target group + apply order
        ordered = [fx for fx in full_order if fx in fixtures]
        
        n = len(ordered)
        if n <= 1:
            return {fx: 0 for fx in fixtures}
        
        # Convert spread_bars to milliseconds
        spread_ms = bars_to_ms(phase_spec.spread_bars, plan.bpm, plan.beats_per_bar)
        
        # Linear distribution
        offsets = {}
        for i, fx in enumerate(ordered):
            offsets[fx] = round((i / (n - 1)) * spread_ms)
        
        # Fixtures not in order get 0 offset
        for fx in fixtures:
            offsets.setdefault(fx, 0)
        
        return offsets
    
    raise ValueError(f"Unsupported phase offset mode: {phase_spec.mode}")
```

Example:
- Order: LEFT_TO_RIGHT = ["mh1", "mh2", "mh3", "mh4"]
- Spread: 0.5 bars = 1000ms (at 120 BPM)
- Result:
  ```python
  {
      "mh1": 0ms,
      "mh2": 333ms,
      "mh3": 667ms,
      "mh4": 1000ms
  }
  ```

#### Step 3: Apply Offsets to Segment Windows

```python
def apply_phase_offset(
    step_window: StepWindow,
    offset_ms: int,
    wrap: bool
) -> StepWindow:
    """
    Shift segment time by offset, optionally wrapping.
    """
    t0_shifted = step_window.t0_ms + offset_ms
    t1_shifted = step_window.t1_ms + offset_ms
    
    if wrap:
        # Wrap within step duration
        duration_ms = step_window.t1_ms - step_window.t0_ms
        t0_rel = (t0_shifted - step_window.t0_ms) % duration_ms
        t1_rel = t0_rel + duration_ms
        
        return StepWindow(
            t0_ms=step_window.t0_ms + t0_rel,
            t1_ms=step_window.t0_ms + t1_rel
        )
    else:
        return StepWindow(t0_ms=t0_shifted, t1_ms=t1_shifted)
```

**Visual Effect**:
```
Without phase offset:
mh1: [────────]
mh2: [────────]
mh3: [────────]
mh4: [────────]

With LEFT_TO_RIGHT cascade (spread=1000ms):
mh1: [────────]
mh2:    [────────]
mh3:       [────────]
mh4:          [────────]
```

---

### 3.4 Phase 4: Per-Step Compilation

For each step, for each cycle:

#### Step 1: Resolve Geometry (Base Pose)

```python
def compile_geometry(
    step: Step,
    fixtures: list[str],
    rig: RigProfile,
    geometry_resolver: IGeometryResolver
) -> dict[str, tuple[int, int]]:
    """
    Resolve base pose: fixture → (pan_dmx, tilt_dmx).
    """
    return geometry_resolver.resolve_base_pose(
        rig=rig,
        fixtures=fixtures,
        geometry=step.geometry
    )
```

Output example:
```python
{
    "mh1": (38, 128),   # Wide left, horizon
    "mh2": (90, 128),   # Mid left, horizon
    "mh3": (165, 128),  # Mid right, horizon
    "mh4": (217, 128)   # Wide right, horizon
}
```

#### Step 2: Generate Movement Curves

```python
def compile_movement(
    step: Step,
    step_window: StepWindow,
    movement_generator: IMovementGenerator
) -> MovementCurves:
    """
    Generate normalized offset curves centered at 0.5.
    """
    duration_ms = step_window.t1_ms - step_window.t0_ms
    
    curves = movement_generator.generate(
        spec=step.movement,
        duration_ms=duration_ms
    )
    
    # Ensure repeat-readiness
    if curves.pan:
        curves.pan = ensure_loop_ready(curves.pan)
    if curves.tilt:
        curves.tilt = ensure_loop_ready(curves.tilt)
    
    return curves
```

Output example (SWEEP_LR):
```python
MovementCurves(
    pan=PointsCurve(points=[
        Point(t=0.0, v=0.5),    # Start at center
        Point(t=0.25, v=1.0),   # Peak right
        Point(t=0.5, v=0.5),    # Back to center
        Point(t=0.75, v=0.0),   # Peak left
        Point(t=1.0, v=0.5)     # Return to center (loop-ready)
    ]),
    tilt=None,
    amplitude_norm=0.70  # "dramatic" intensity
)
```

#### Step 3: Generate Dimmer Curves

```python
def compile_dimmer(
    step: Step,
    step_window: StepWindow,
    dimmer_generator: IDimmerGenerator
) -> PointsCurve | None:
    """
    Generate normalized dimmer curve [0, 1].
    """
    duration_ms = step_window.t1_ms - step_window.t0_ms
    
    return dimmer_generator.generate(
        spec=step.dimmer,
        duration_ms=duration_ms
    )
```

Output example (PULSE):
```python
PointsCurve(points=[
    Point(t=0.0, v=0.5),   # Mid brightness
    Point(t=0.25, v=1.0),  # Peak
    Point(t=0.5, v=0.5),   # Mid
    Point(t=0.75, v=1.0),  # Peak
    Point(t=1.0, v=0.5)    # Return to mid
])
```

#### Step 4: Apply Iteration Policy (PING_PONG)

```python
def apply_repeat_mode(
    movement: MovementCurves,
    template: Template,
    cycle_index: int
) -> MovementCurves:
    """
    Modify movement for alternating cycles (PING_PONG).
    """
    if template.repeat.mode != RepeatMode.PING_PONG:
        return movement
    
    # Reverse on odd cycles
    if cycle_index % 2 == 1:
        pan = reverse_curve(movement.pan) if movement.pan else None
        tilt = reverse_curve(movement.tilt) if movement.tilt else None
        return movement.model_copy(update={"pan": pan, "tilt": tilt})
    
    return movement

def reverse_curve(curve: PointsCurve) -> PointsCurve:
    """
    Reverse curve in time: t → 1-t.
    """
    reversed_points = [
        Point(t=1.0 - p.t, v=p.v)
        for p in reversed(curve.points)
    ]
    return PointsCurve(points=reversed_points)
```

**Visual**:
```
Cycle 0 (even): sweep left → right → left
Cycle 1 (odd):  sweep right → left → right  (reversed)
Cycle 2 (even): sweep left → right → left
```

Creates seamless back-and-forth motion.

#### Step 5: Generate Transition Envelopes

```python
def compile_transitions(
    step: Step,
    step_window: StepWindow,
    plan: PlaybackPlan,
    curve_ops: CurveOps
) -> dict[str, ChannelSegment]:
    """
    Create entry/exit transition segments for dimmer.
    """
    transitions = {}
    
    # Entry transition (before step)
    if step.entry_transition and step.entry_transition.duration_bars > 0:
        duration_ms = bars_to_ms(step.entry_transition.duration_bars, plan.bpm)
        
        # Fade-in envelope
        envelope = curve_ops.sample(lambda t: t, n_samples=16)
        
        transitions["entry"] = ChannelSegment(
            fixture_id=...,  # Per fixture
            channel=ChannelName.DIMMER,
            t0_ms=step_window.t0_ms - duration_ms,
            t1_ms=step_window.t0_ms,
            curve=envelope,
            clamp_min=...,
            clamp_max=...
        )
    
    # Exit transition (after step)
    if step.exit_transition and step.exit_transition.duration_bars > 0:
        duration_ms = bars_to_ms(step.exit_transition.duration_bars, plan.bpm)
        
        # Fade-out envelope
        envelope = curve_ops.sample(lambda t: 1.0 - t, n_samples=16)
        
        transitions["exit"] = ChannelSegment(
            fixture_id=...,
            channel=ChannelName.DIMMER,
            t0_ms=step_window.t1_ms,
            t1_ms=step_window.t1_ms + duration_ms,
            curve=envelope,
            clamp_min=...,
            clamp_max=...
        )
    
    return transitions
```

#### Step 6: Compose Final Segments

```python
def emit_channel_segments(
    fixture_id: str,
    step_window: StepWindow,
    base_pose: tuple[int, int],
    movement: MovementCurves,
    dimmer_curve: PointsCurve | None,
    rig: RigProfile,
    template: Template,
    step: Step
) -> list[ChannelSegment]:
    """
    Generate PAN, TILT, DIMMER segments for one fixture.
    """
    segments = []
    pan_base, tilt_base = base_pose
    
    # PAN channel
    if movement.pan:
        pan_amp_dmx = rig.calibration.global_.pan_amplitude_dmx
        segments.append(
            ChannelSegment(
                fixture_id=fixture_id,
                channel=ChannelName.PAN,
                t0_ms=step_window.t0_ms,
                t1_ms=step_window.t1_ms,
                curve=movement.pan,
                offset_centered=True,
                base_dmx=pan_base,
                amplitude_dmx=round(pan_amp_dmx * movement.amplitude_norm),
                clamp_min=rig.calibration.fixtures[fixture_id].pan_min,
                clamp_max=rig.calibration.fixtures[fixture_id].pan_max
            )
        )
    else:
        # Static hold
        segments.append(
            ChannelSegment(
                fixture_id=fixture_id,
                channel=ChannelName.PAN,
                t0_ms=step_window.t0_ms,
                t1_ms=step_window.t1_ms,
                static_dmx=pan_base,
                clamp_min=...,
                clamp_max=...
            )
        )
    
    # TILT channel (similar to PAN)
    # ...
    
    # DIMMER channel
    dimmer_floor, dimmer_ceiling = resolve_dimmer_clamp(rig, template, step)
    
    if dimmer_curve:
        segments.append(
            ChannelSegment(
                fixture_id=fixture_id,
                channel=ChannelName.DIMMER,
                t0_ms=step_window.t0_ms,
                t1_ms=step_window.t1_ms,
                curve=dimmer_curve,
                clamp_min=dimmer_floor,
                clamp_max=dimmer_ceiling,
                blend_mode=step.blend_mode
            )
        )
    
    return segments
```

---

### 3.5 Phase 5: Final Assembly & Validation

#### Segment Collection

```python
def compile_section(
    template: Template,
    plan: PlaybackPlan,
    rig: RigProfile,
    compiler: TemplateCompiler
) -> list[ChannelSegment]:
    """
    Full compilation pipeline.
    """
    all_segments = []
    
    # Calculate cycles
    total_cycles, remainder = calculate_cycles(
        section_duration_bars=plan.window.duration_bars,
        cycle_bars=template.repeat.cycle_bars,
        repeatable=template.repeat.repeatable
    )
    
    # Compile each cycle
    for cycle_index in range(total_cycles):
        cycle_offset_bars = plan.window.start_bar + (cycle_index * template.repeat.cycle_bars)
        
        # Compile each step in cycle
        for step in template.steps:
            # Skip non-loop steps after first cycle
            if cycle_index > 0 and step.step_id not in template.repeat.loop_step_ids:
                continue
            
            step_segments = compiler.compile_step(
                rig=rig,
                plan=plan,
                template=template,
                step=step,
                cycle_offset_bars=cycle_offset_bars,
                iteration_index=cycle_index
            )
            
            all_segments.extend(step_segments)
    
    # Handle remainder (if any)
    if remainder > 0:
        all_segments.extend(
            handle_remainder(template, remainder, rig, plan, compiler)
        )
    
    # Clip to section window
    start_ms = bars_to_ms(plan.window.start_bar, plan.bpm)
    end_ms = start_ms + bars_to_ms(plan.window.duration_bars, plan.bpm)
    clipped = clip_segments_to_window(all_segments, start_ms, end_ms)
    
    return clipped
```

#### Segment Validation

```python
def validate_segments(segments: list[ChannelSegment]) -> list[str]:
    """
    Post-compilation sanity checks.
    """
    errors = []
    
    # Check for overlapping segments (same fixture + channel + time)
    by_key = defaultdict(list)
    for seg in segments:
        key = (seg.fixture_id, seg.channel)
        by_key[key].append(seg)
    
    for key, segs in by_key.items():
        sorted_segs = sorted(segs, key=lambda s: s.t0_ms)
        for i in range(len(sorted_segs) - 1):
            if sorted_segs[i].t1_ms > sorted_segs[i + 1].t0_ms:
                errors.append(f"Overlapping segments for {key}")
    
    # Check clamp consistency
    for seg in segments:
        if seg.clamp_max < seg.clamp_min:
            errors.append(f"Invalid clamp range for {seg.fixture_id}.{seg.channel}")
    
    # Check curve validity
    for seg in segments:
        if seg.curve:
            if len(seg.curve.points) < 2:
                errors.append(f"Curve has < 2 points")
    
    return errors
```

---

## 4. Dependency Injection Architecture

### 4.1 Compiler Initialization

```python
@dataclass
class TemplateCompiler:
    """
    Orchestrates template compilation with injected dependencies.
    """
    geometry_resolver: IGeometryResolver
    movement_generator: IMovementGenerator
    dimmer_generator: IDimmerGenerator
    curve_ops: CurveOps
    iteration_policy: IIterationPolicy | None = None
    
    def compile(
        self,
        rig: RigProfile,
        plan: PlaybackPlan,
        template: Template
    ) -> list[ChannelSegment]:
        """Main compilation entry point."""
        # Implementation per Phase 5 above
```

### 4.2 Dependency Wiring

```python
def build_compiler(config: dict) -> TemplateCompiler:
    """
    Dependency injection container.
    """
    # Curve operations (pure functions)
    curve_ops = CurveOps()
    
    # Geometry resolvers
    pose_tokens = load_pose_token_mapping(config)
    aim_zones = load_aim_zone_mapping(config)
    
    role_pose_resolver = RolePoseGeometryResolver(
        pan_pose_table=pose_tokens,
        tilt_pose_table=aim_zones
    )
    
    geometry_id_resolver = GeometryIdResolver(
        # ... registry of parametric geometries
    )
    
    geometry_dispatcher = GeometryDispatchResolver(
        role_pose_resolver=role_pose_resolver,
        geometry_id_resolver=geometry_id_resolver
    )
    
    # Movement generator
    movement_generator = MovementGenerator(
        curve_ops=curve_ops,
        default_samples=64
    )
    
    # Dimmer generator
    dimmer_generator = DimmerGenerator(
        curve_ops=curve_ops,
        default_samples=32
    )
    
    # Iteration policy
    iteration_policy = StandardIterationPolicy()
    
    # Assemble compiler
    return TemplateCompiler(
        geometry_resolver=geometry_dispatcher,
        movement_generator=movement_generator,
        dimmer_generator=dimmer_generator,
        curve_ops=curve_ops,
        iteration_policy=iteration_policy
    )
```

### 4.3 Interface Contracts

```python
class IGeometryResolver(Protocol):
    """Geometry resolution interface."""
    
    def resolve_base_pose(
        self,
        rig: RigProfile,
        fixtures: list[str],
        geometry: Geometry
    ) -> dict[str, tuple[int, int]]:
        """Return fixture → (pan_dmx, tilt_dmx)."""
        ...

class IMovementGenerator(Protocol):
    """Movement curve generation interface."""
    
    def generate(
        self,
        spec: Movement,
        duration_ms: int
    ) -> MovementCurves:
        """Return normalized offset curves."""
        ...

class IDimmerGenerator(Protocol):
    """Dimmer curve generation interface."""
    
    def generate(
        self,
        spec: Dimmer,
        duration_ms: int
    ) -> PointsCurve | None:
        """Return normalized dimmer curve or None for HOLD."""
        ...
```

---

## 5. Intermediate Representation (IR)

### 5.1 ChannelSegment Model

```python
@dataclass
class ChannelSegment:
    """
    IR segment: one fixture + one channel + one time window + one behavior.
    """
    fixture_id: str
    channel: ChannelName  # PAN, TILT, DIMMER
    
    t0_ms: int  # Absolute start time
    t1_ms: int  # Absolute end time
    
    # Behavior (mutually exclusive)
    static_dmx: int | None = None          # Static value
    curve: PointsCurve | None = None   # Dynamic curve
    
    # Composition metadata (for movement offset curves)
    offset_centered: bool = False
    base_dmx: int | None = None
    amplitude_dmx: int | None = None
    
    # Blending & safety
    blend_mode: BlendMode = BlendMode.OVERRIDE
    clamp_min: int = 0
    clamp_max: int = 255
```

### 5.2 Why IR Matters

**Separation of Concerns:**
- Compiler outputs IR (platform-agnostic)
- Exporters convert IR to target format (xLights, OSC, ArtNet)
- Testing is done on IR (stable, predictable)
- Visualization can consume IR directly

**Example Export Flow:**

```python
def export_to_xlights(segments: list[ChannelSegment]) -> dict:
    """
    Convert IR to xLights JSON format.
    """
    xlights_data = {}
    
    for seg in segments:
        channel_key = f"{seg.fixture_id}:{seg.channel.value}"
        
        if seg.static_dmx is not None:
            # Static value → hold effect
            xlights_data[channel_key] = {
                "type": "HOLD",
                "value": seg.static_dmx,
                "start_ms": seg.t0_ms,
                "end_ms": seg.t1_ms
            }
        else:
            # Curve → custom points
            points = convert_to_absolute_dmx(seg)
            xlights_data[channel_key] = {
                "type": "CUSTOM",
                "points": points,
                "start_ms": seg.t0_ms,
                "end_ms": seg.t1_ms
            }
    
    return xlights_data

def convert_to_absolute_dmx(seg: ChannelSegment) -> list[dict]:
    """
    Convert normalized curve to absolute DMX points.
    """
    if seg.offset_centered:
        # Movement curve: base ± amplitude * (v - 0.5)
        return [
            {"t": p.t, "v": seg.base_dmx + seg.amplitude_dmx * (p.v - 0.5)}
            for p in seg.curve.points
        ]
    else:
        # Dimmer curve: map [0,1] to [clamp_min, clamp_max]
        return [
            {"t": p.t, "v": seg.clamp_min + (seg.clamp_max - seg.clamp_min) * p.v}
            for p in seg.curve.points
        ]
```

---

## 6. Testability & Debugging

### 6.1 Unit Test Targets

```python
def test_phase_offset_computation():
    """Phase offsets distribute correctly."""
    offsets = compute_phase_offsets(
        fixtures=["mh1", "mh2", "mh3", "mh4"],
        order="LEFT_TO_RIGHT",
        spread_bars=1.0,
        rig=test_rig,
        plan=test_plan
    )
    
    assert offsets["mh1"] == 0
    assert offsets["mh4"] == 2000  # 1 bar at 120 BPM
    assert offsets["mh2"] < offsets["mh3"]

def test_movement_repeat_readiness():
    """Movement curves are loop-safe."""
    movement = movement_generator.generate(
        spec=Movement(movement_id=MovementID.SWEEP_LR, intensity="dramatic", cycles=1.0),
        duration_ms=2000
    )
    
    assert movement.pan is not None
    assert movement.pan.points[0].v == movement.pan.points[-1].v

def test_dimmer_clamp_precedence():
    """Higher precedence floor wins."""
    floor = resolve_dimmer_floor(
        rig=rig_with_floor_30,
        template=template_with_floor_60,
        step=step_with_floor_80,
        override={"dimmer_floor_dmx": 100}
    )
    
    assert floor == 100  # Override wins
```

### 6.2 Integration Test

```python
def test_full_compilation():
    """End-to-end compilation produces valid segments."""
    template = load_template("fan_pulse.json")
    preset = load_preset("fan_pulse:ENERGETIC")
    rig = load_rig("rooftop_4.json")
    
    plan = PlaybackPlan(
        template_id="fan_pulse",
        preset_id="ENERGETIC",
        window=SectionWindow(start_bar=64.0, duration_bars=16.0),
        bpm=120,
        beats_per_bar=4
    )
    
    patched_template = apply_preset(template, preset)
    compiler = build_compiler(config)
    
    segments = compiler.compile(rig, plan, patched_template)
    
    # Validate output
    assert len(segments) > 0
    assert all(seg.t1_ms > seg.t0_ms for seg in segments)
    assert all(seg.clamp_max >= seg.clamp_min for seg in segments)
    
    # Check fixture coverage
    fixture_channels = {(s.fixture_id, s.channel) for s in segments}
    expected_fixtures = set(rig.fixtures)
    assert {fc[0] for fc in fixture_channels} == expected_fixtures
```

---

## Summary

The logical architecture provides:

✅ **Clear Pipeline**: Load → Patch → Time → Fixture → Compile → Emit  
✅ **Dependency Injection**: All handlers are injected, not discovered  
✅ **Intermediate Representation**: Platform-agnostic output format  
✅ **Configuration Precedence**: Deterministic parameter resolution  
✅ **Testability**: Each stage is independently testable  
✅ **Separation of Concerns**: Each layer has single responsibility

**Next Section**: Technical Architecture & Design (implementation patterns, code organization, standards)
