# Unified Templates


## Template Handling

### Template Structure

Example: packages/blinkb0t/core/domains/sequencing/templates/unified/fan_pulse.json

```json
{
  "templates": { "fan_pulse": { ... } },
  "presets": {
    "fan_pulse": [
      { "preset_id": "ENERGETIC", ... },
      { "preset_id": "PEAK", ... }
    ]
  }
}
```

### Template Processing
1. Read json doc
    - templates -> unified_template pydantic model
    - presets -> unified_preset pydantic model
2. If preset is defined -> apply to template
3. Modified can be specified by the LLM
4. At rendering:
    - Per iteration-cycle adjustments for variation
    - Boundaries are clamped

**Configuration Precedence**
1. base template
2. preset patch
3. modifier patch
4. per-cycle patch
5. safety clamps


## End-to-end Template Steps

1.Planner/LLM selects
    - template_id = fan_pulse
    - preset_id = ENERGETIC
    - modifiers (categorical)
2. Load template + presets
3. Apply preset patches
    - patch step intensities, phase_offset order/spread, dimmer ID, pose tokens, etc.
4. Apply modifier patches
    - same mechanism, but generated from categorical knobs
5. Compile to channel segments (not frames)
    - compute repeat count for the section window
    - for each cycle:
        - apply per-cycle overrides (from the playback plan)
        - for each step:
            - resolve fixtures in target group
            - compute phase offsets → offset_norm
            - resolve geometry → base_dmx for pan/tilt
            - compile movement → custom points (normalized)
            - compile dimmer → custom points (normalized)
            - compile transitions → envelope points (normalized)
            - compose (envelope + phase shift + blend)
            - output final [t,v] arrays per channel per fixture
6. Final clamp pass
    - especially dimmer: enforce floor/ceiling


## Movement & Geometry - What geometry and movement return
**Geometry resolver Contract**
- Input: fixtures/roles + geometry_id + geometry_params + aim context
- Output: per-fixture base pose (targets in your internal units, typically 0–255)

```python
base_pose[fixture] = {
  pan_base: 0..255,
  tilt_base: 0..255
}
```

- Geometry should not animate. It defines where the rig “is” in space.

**Movement resolver contract**
- Input: movement_id + movement_params + t_local + step_duration
- Output: per-fixture delta (or an absolute if you choose, but delta is cleaner)
- Movement should not decide the rig’s static formation. It provides motion around/through that formation.

```python
delta[fixture] = {
  pan_delta: -A..+A  (in 0..255 units or normalized)
  tilt_delta: -A..+A
}
```

**Combine Geometry and Movement**

```python
pan = base_pose.pan_base + delta.pan_delta
tilt = base_pose.tilt_base + delta.tilt_delta

pan  = clamp_pan(pan)
tilt = clamp_tilt(tilt)
```

## Pseudo Code Examples
**Applying Presets**

```python
def apply_preset(template: UnifiedTemplate, preset: TemplatePreset) -> UnifiedTemplate:
    tpl = template.model_copy(deep=True)

    # 1) template-wide defaults
    if preset.defaults:
        for k, v in preset.defaults.model_dump(exclude_none=True).items():
            setattr(tpl.defaults, k, v)

    # 2) step patches
    step_by_id = {s.step_id: s for s in tpl.steps}
    for step_id, patch in preset.step_patches.items():
        step = step_by_id[step_id]

        if patch.movement:
            if patch.movement.intensity is not None:
                step.movement.intensity = patch.movement.intensity
            if patch.movement.movement_params:
                step.movement.movement_params.update(patch.movement.movement_params)

        if patch.phase_offset and step.timing.phase_offset:
            if patch.phase_offset.order is not None:
                step.timing.phase_offset.order = patch.phase_offset.order
            if patch.phase_offset.spread_bars is not None:
                step.timing.phase_offset.spread_bars = patch.phase_offset.spread_bars

        if patch.geometry:
            # Apply role pose token remaps if role_pose exists
            if step.geometry.role_pose and patch.geometry.pan_pose_by_role:
                step.geometry.role_pose.pan_pose_by_role.update(patch.geometry.pan_pose_by_role)
            if patch.geometry.geometry_params:
                step.geometry.geometry_params.update(patch.geometry.geometry_params)

        if patch.dimmer:
            if patch.dimmer.dimmer_id is not None:
                step.dimmer.dimmer_id = patch.dimmer.dimmer_id
            if patch.dimmer.intensity is not None:
                step.dimmer.intensity = patch.dimmer.intensity
            if patch.dimmer.floor_dmx is not None:
                step.dimmer.floor_dmx = patch.dimmer.floor_dmx
            if patch.dimmer.group_modulation is not None:
                step.dimmer.group_modulation = patch.dimmer.group_modulation
            if patch.dimmer.final_clamp is not None:
                step.dimmer.final_clamp = patch.dimmer.final_clamp
            if patch.dimmer.dimmer_params:
                step.dimmer.dimmer_params.update(patch.dimmer.dimmer_params)

    return tpl
```

**Top-level render: section → repeated template cycles**
```python
def render_section(section, template, rig, song_ctx):
    # section.duration_bars could be 16
    # template.repeat.cycle_bars could be 8
    cycle_bars = template.repeat.cycle_bars
    repeats = floor(section.duration_bars / cycle_bars)
    remainder = section.duration_bars - repeats * cycle_bars

    timeline = []

    for cycle_index in 0..repeats-1:
        cycle_start_bar = section.start_bar + cycle_index * cycle_bars

        cycle_overrides = section.play.per_cycle_overrides.get(cycle_index, {})
        timeline += render_template_cycle(
            template, rig, song_ctx,
            cycle_start_bar,
            cycle_bars,
            cycle_overrides
        )

    if remainder > 0:
        timeline += handle_remainder(
            template.repeat.remainder_policy,
            timeline,
            remainder,
            rig,
            song_ctx
        )

    return timeline
```

**Render one template cycle: resolve steps + timing**
```python
def render_template_cycle(template, rig, song_ctx, cycle_start_bar, cycle_bars, overrides):
    # 1) Apply overrides into a working template instance (no mutation)
    tpl = apply_overrides(template, overrides)

    # 2) Resolve step schedule within the cycle
    steps = []
    for step in tpl.steps:
        step_start = cycle_start_bar + step.timing.base_timing.start_offset_bars
        step_end   = step_start + step.timing.base_timing.duration_bars
        steps.append({step, step_start, step_end})

    # 3) Render each step into frames/events (bars -> ticks -> frames)
    frames = []
    for scheduled in steps:
        frames += render_step(scheduled.step, rig, song_ctx, scheduled.step_start, scheduled.step_end)

    return frames
```

**Render one step: compute base pose + per-fixture phase offsets + channels**
```python
def render_step(step, rig, song_ctx, step_start_bar, step_end_bar):
    fixtures = resolve_target(step.target, rig)     # e.g. ALL -> [mh1..mh4]
    duration_bars = step_end_bar - step_start_bar

    # A) Precompute per-fixture phase offsets (REPLACES per_fixture_offsets[])
    phase_offsets = compute_phase_offsets(step.timing.phase_offset, fixtures, rig, duration_bars)
    # phase_offsets[fixture_id] = offset_bars (usually within [0, spread_bars))

    # B) Resolve geometry base pose per fixture (role_pose or classic fan)
    base_pose = resolve_geometry(step.geometry_id, step.geometry_params, fixtures, rig, song_ctx)
    # base_pose[fixture] = {pan_base, tilt_base}

    # C) Build channel renderers for this step
    pan_renderer   = make_movement_renderer(step.movement_id, step.movement_params)
    tilt_renderer  = make_tilt_renderer(step.movement_id, step.movement_params)  # could be part of movement
    dimmer_renderer= make_dimmer_renderer(step.dimmer_id, step.dimmer_params)

    # D) Iterate time and generate frames/events
    frames = []
    for t_bar in sample_times(step_start_bar, step_end_bar, song_ctx.fps_or_tick):
        frame = {}
        for fixture in fixtures:
            # 1) time-warp per fixture via phase offset
            t_local = (t_bar - step_start_bar) + phase_offsets[fixture]
            if step.timing.phase_offset.wrap:
                t_local = t_local mod duration_bars

            # 2) pan/tilt = base_pose + movement(t_local)
            pan = base_pose[fixture].pan + pan_renderer.eval(t_local, duration_bars)
            tilt= base_pose[fixture].tilt + tilt_renderer.eval(t_local, duration_bars)

            # 3) dimmer from curve/range etc.
            dim = dimmer_renderer.eval(t_local, duration_bars, fixture)

            # 4) Apply transitions (entry/exit crossfade) per step if you do it here
            pan, tilt, dim = apply_step_transitions(step, pan, tilt, dim, t_bar, step_start_bar, step_end_bar)

            # 5) Clamp channels (CRITICAL: include dimmer clamp now)
            pan  = clamp_pan(pan, fixture)       # you already do
            tilt = clamp_tilt(tilt, fixture)     # you already do
            dim  = clamp_dimmer(dim, step, template, fixture)  # you said you don’t yet

            frame[fixture] = {pan, tilt, dim}
        frames.append(frame)

    return frames
```

**Compute phase offsets (the replacement for per_fixture_offsets[])**
```python
def compute_phase_offsets(phase_spec, fixtures, rig, duration_bars):
    # Default: no offsets
    if phase_spec is null:
        return {f: 0.0 for f in fixtures}

    # Determine ordered fixtures
    ordered = order_fixtures(fixtures, rig, phase_spec.order)  # LEFT_TO_RIGHT, OUTSIDE_IN, etc.

    N = len(ordered)
    spread = phase_spec.spread_bars

    offsets = {}
    for idx, f in enumerate(ordered):
        # LINEAR distribution across spread
        # idx/N gives [0, 1) not including 1
        offsets[f] = (idx / N) * spread

    return offsets
```

**Clamp Dimmer**
```python
def clamp_dimmer(dim, step, template, fixture):
    # If blackout is explicitly requested, allow true off
    if step.dimmer_params.blackout == true:
        return 0

    # Determine floor/ceiling
    floor = step.dimmer_params.final_clamp.min_dmx
         or template.defaults.dimmer_floor_dmx
         or 0

    ceiling = step.dimmer_params.final_clamp.max_dmx or 255

    return clamp(dim, floor, ceiling)
```

**Blending/Priority**
```python
def composite_frames(frames_by_layer, rig):
    out = init_zero_frame(rig)

    for fixture in rig.fixtures:
        # Pan/Tilt usually: highest-priority override wins (or blend)
        out[fixture].pan  = composite_channel(frames_by_layer, fixture, "pan")
        out[fixture].tilt = composite_channel(frames_by_layer, fixture, "tilt")

        # Dimmer: usually max() or override depending on your rules
        out[fixture].dim  = composite_dimmer(frames_by_layer, fixture)

        # FINAL safety clamp (highly recommended)
        out[fixture].dim = clamp(out[fixture].dim, global_floor, 255)

    return out
```

```python
def resolve_geometry_role_pose(fixtures, rig, geometry_params):
    # geometry_params.pan_pose maps roles -> pose token
    # rig maps fixture -> role
    base = {}

    for fixture in fixtures:
        role = rig.role_of(fixture)                 # OUTER_LEFT, etc.
        pan_token = geometry_params.pan_pose[role]  # WIDE_LEFT, MID_LEFT...
        base[fixture].pan_base = resolve_pan_token(pan_token, fixture, rig)

        tilt_spec = geometry_params.tilt_pose
        base[fixture].tilt_base = resolve_tilt_pose(tilt_spec, fixture, rig)

    return base

def resolve_geometry_fan(fixtures, rig, geometry_params):
    ordered = rig.order("LEFT_TO_RIGHT", fixtures)
    N = len(ordered)

    base = {}
    for i, fixture in enumerate(ordered):
        # normalize position 0..1
        u = i / (N - 1)

        # map u to a token bucket; you can tune this table
        pan_token = fan_token_from_u(u, geometry_params.width) 
        base[fixture].pan_base = resolve_pan_token(pan_token, fixture, rig)

        base[fixture].tilt_base = resolve_tilt_pose({mode:"AIM_ZONE", aim: geometry_params.aim or "CROWD"}, fixture, rig)

    return base

```


**Standardize Curve Definition**
```json
{
  "channel": "PAN",
  "fixture": "mh2",
  "t0_bars": 64.0,
  "t1_bars": 66.0,
  "base_dmx": 128,
  "blend_mode": "ADD",
  "curve": {
    "kind": "custom_points",
    "points": [[0.0, 0.5], [0.5, 1.0], [1.0, 0.5]]
  },
  "time_warp": {
    "offset_norm": 0.25,
    "wrap": true
  },
  "clamp": { "min_dmx": 0, "max_dmx": 255 }
}
```
**Key**: points are always normalized; you convert to DMX using:
- value_dmx = base_dmx + (v_norm - 0.5) * amplitude_dmx (for movement)
- or value_dmx = lerp(min_dmx, max_dmx, v_norm) (for dimmer curves)



##Heurstics

### Curve Selection
**Native curves**

Use them when possible:
- HOLD, LINEAR, maybe EASE_IN_OUT, maybe SINE (if you support it natively)

**Custom curves**

Use them when:
- you need a sine/triangle/pulse you don’t have native support for
- you need to apply phase offsets cleanly
- you need to combine shapes (envelopes + motion)

Practically: you’ll likely end up generating custom points a lot — that’s normal.


### Phase offset in a point-array world (important)

Since xLights gives you t∈[0,1], phase offset is just a time shift in normalized space.

If your step duration is the segment duration, and you compute a phase offset like “0.25 bars” across a “2 bar step”:
- offset_norm = offset_bars / step_duration_bars
Then for any point (t, v):
- shifted time is t' = (t + offset_norm) % 1.0 if  wrap
and then you re-sample the curve at t'

There are two easy implementations:

**Option A: Apply phase by shifting points**
- Move each point’s t forward by offset_norm, wrap around, then re-sort.
- Works best for dense point sets.

**Option B (better): Apply phase by sampling**
- Keep the base curve points unchanged.
- When converting to xLights points, generate a new point set by sampling the curve at fixed ts and shifting t on lookup.

This is cleaner when you also want to do envelopes / blends.


### Avoiding Jitter

To avoid jitter and keep file sizes manageable:
- generate points at a fixed resolution, e.g. 32 or 64 samples per segment
- then optionally simplify (drop near-collinear points)

**Why this matters**
1. Prevents jitter when combining curves

If two curves have:
    - different point densities
    - slightly misaligned time samples

Then when you:
    - apply phase offsets
    - blend movement + envelope
    - repeat cycles

…you get subtle “zipper” motion or stepping artifacts.

Fixed sampling avoids this entirely.

2. Makes phase offsets trivial and exact

With fixed samples:
    - phase offset = index shift
    - no interpolation errors
    - wrap is clean

Example:
    - 32 samples
    - offset_norm = 0.25
    - offset_samples = 32 × 0.25 = 8 samples
    - rotate the array by 8 positions

That’s way more robust than shifting arbitrary points.

3. Keeps output predictable and testable

If every segment always produces:
    - exactly 32 points

Then:
    - file size is predictable
    - diffing outputs is easier
    - bugs are reproducible

**Drop near-collinear points**” actually means**

Given three consecutive points:

P0 = (t0, v0)
P1 = (t1, v1)
P2 = (t2, v2)

If P1 lies almost on the straight line from P0 to P2, then P1 is redundant.

Mathematically:
    - compute the vertical distance from P1 to the line (P0 → P2)
    - if that distance < ε (tiny threshold), drop P1

This preserves shape while shrinking the list.

**Recommended defaults (practical, tested)**
For movement curves (pan/tilt)
    - Base sampling: 64 points
    - Simplify tolerance: ε ≈ 0.01 (1% of normalized range)
For dimmer curves
    - Base sampling: 32 points
    - Simplify tolerance: ε ≈ 0.02
For envelopes (fade in/out)
    - Often only need 3–5 points, no need to oversample

**Do not simplify before applying phase offsets or envelopes.**

Always:
    - generate dense samples
    - apply phase shift
    - apply envelopes / modulation
    - then simplify

Otherwise you distort timing.

```python
def sample_curve(fn, n_samples):
    points = []
    for i in range(n_samples + 1):
        t = i / n_samples
        v = fn(t)  # v must be normalized 0..1
        points.append((t, v))
    return points


def simplify_points(points, epsilon=0.01):
    if len(points) <= 2:
        return points

    simplified = [points[0]]

    for i in range(1, len(points) - 1):
        p0 = simplified[-1]
        p1 = points[i]
        p2 = points[i + 1]

        if not is_near_collinear(p0, p1, p2, epsilon):
            simplified.append(p1)

    simplified.append(points[-1])
    return simplified

```


## Configuration

**Rig Config**

```json
{
  "rig_id": "rooftop_4",
  "fixtures": ["mh1", "mh2", "mh3", "mh4"],
  "role_bindings": {
    "mh1": "OUTER_LEFT",
    "mh2": "INNER_LEFT",
    "mh3": "INNER_RIGHT",
    "mh4": "OUTER_RIGHT"
  },
  "groups": {
    "ALL": ["mh1", "mh2", "mh3", "mh4"],
    "LEFT": ["mh1", "mh2"],
    "RIGHT": ["mh3", "mh4"],
    "INNER": ["mh2", "mh3"],
    "OUTER": ["mh1", "mh4"],
    "ODD": ["mh1", "mh3"],
    "EVEN": ["mh2", "mh4"]
  },
  "orders": {
    "LEFT_TO_RIGHT": ["mh1", "mh2", "mh3", "mh4"],
    "OUTSIDE_IN": ["mh1", "mh4", "mh2", "mh3"]
  }
}
```

**Applying Config to Templates**
```json
{
  "template_id": "fan_pulse",
  "requires": {
    "groups": ["ALL", "OUTER", "INNER"],
    "orders": ["OUTSIDE_IN"],
    "roles": ["OUTER_LEFT", "INNER_LEFT", "INNER_RIGHT", "OUTER_RIGHT"]
  },
  "steps": [
    {
      "step_id": "intro",
      "target": "ALL",
      "timing": { "...": "...", "phase_offset": { "group": "ALL", "order": "OUTSIDE_IN" } }
    }
  ]
}
```

**Applying Config to Plan**
```json
{
  "template_id": "fan_pulse",
  "preset_id": "ENERGETIC",
  "per_cycle_overrides": [...]
}

```