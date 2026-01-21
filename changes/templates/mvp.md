# Sequencing v2 – MVP Implementation Plan

This document outlines a **clean, sustainable MVP architecture** for the moving-head sequencing engine rewrite.

The goal is to move from the current monolithic “default handler” model to a **compiler-based architecture** with strict separation of concerns, while remaining compatible with xLights-style curve output.

---

## Guiding Principles

* Fixtures, groups, orders, and calibration are **rig configuration**, not template concerns
* **Pydantic** is used for all data models (no dataclasses)
* **Dependency Injection** is used for all handlers and registries
* Strong **separation of concerns** to avoid logic entanglement
* No frame rendering — output is **static values or normalized curves**

---

## MVP Definition of Done

Given:

* A `RigProfile`
* A unified `TemplateDoc` (template + presets)
* A `PlaybackPlan`

Produce:

* Per-fixture, per-channel **ChannelSegments**
* Each segment is either:

  * static DMX value, or
  * custom curve defined as normalized points `[t, v]` where `t, v ∈ [0,1]`

For MVP scope:

* 4 moving heads (rooftop)
* `fan_pulse` template + `ENERGETIC` preset
* pan / tilt / dimmer only
* repeat-ready templates
* phase offsets for intro cascade

---

## Module Layout (Hard Boundary)

```
sequencing_v2/
  models/           # Pydantic models only
  rig/              # Rig resolution helpers (groups, orders)
  compile/          # TemplateCompiler + orchestration
  resolve/          # Geometry, movement, dimmer generators
  curves/           # Curve generation & transforms (pure)
  export/           # xLights exporter
  di/               # Dependency injection wiring
  tests/
```

**Rule:** Only `compile/` orchestrates. All other modules are pure or near-pure.

---

## Step 1 — Core Pydantic Models

### 1.1 Rig Models (Configuration)

`RigProfile`

* `rig_id`
* `fixtures: list[str]`
* `groups: dict[str, list[str]]`
* `orders: dict[str, list[str]]`
* `role_bindings: dict[str, str]`
* `calibration` (pan/tilt limits, dimmer floor – minimal for MVP)

**Deliverable:** Rig profile JSON validates via Pydantic.

---

### 1.2 Template Models (Portable Choreography)

Unified template document:

* `template_id`, `version`
* `steps`
* `repeat`
* `defaults`
* `presets[]`
* optional `requires` (groups / orders / roles)

No fixture IDs allowed in templates.

**Deliverable:** Template + presets validate via Pydantic.

---

### 1.3 Playback Plan Model

`PlaybackPlan`

* `template_id`
* `preset_id`
* `window: { start_bar, duration_bars }`
* `modifiers: dict[str, Enum]`
* optional `per_cycle_overrides`

**Deliverable:** A plan object can describe a 16-bar chorus.

---

### 1.4 Intermediate Representation (IR)

These models define the compiler output.

* `Point(t: float, v: float)`
* `PointsCurveSpec(points: list[Point])`
* `NativeCurveSpec(curve_id: str, params: dict)`

`ChannelSegment`

* `fixture_id`
* `channel: PAN | TILT | DIMMER`
* `t0_ms`, `t1_ms`
* `static_dmx` **or**
* `curve`
* `base_dmx` (pan/tilt)
* `amplitude_dmx`
* `offset_centered: bool`
* `blend_mode`
* `clamp_min`, `clamp_max`

**Deliverable:** Compiler output validates against IR schema.

---

## Step 2 — Dependency Injection & Registries

Define interfaces and inject them into the compiler:

* `IGeometryResolver`
* `IMovementGenerator`
* `IDimmerGenerator`
* `ICurveEngine`
* `IXLightsExporter`

Registries:

* `movement_generators: dict[MovementID, Callable]`
* `geometry_handlers: dict[GeometryID, Callable]`
* `dimmer_generators: dict[DimmerID, Callable]`

**Deliverable:** A DI container constructs a fully-wired `TemplateCompiler`.

---

## Step 3 — Curve Engine (Points-First MVP)

### Responsibilities

* Generate normalized curves
* Apply curve transforms
* Stay completely lighting-agnostic

### Required Operations

* `sample(fn, n_samples)`
* `invert(points)`
* `time_shift(points, offset_norm, wrap=True)`
* `multiply(points, envelope)`
* `clamp(points)`

**Deliverable:** Unit tests validate inversion and phase shifts.

---

## Step 4 — Geometry Resolver (Spatial Only)

### Output

Geometry resolves **base pose per fixture**:

```
{ fixture_id: (pan_dmx, tilt_dmx) }
```

### MVP Support

* `role_pose` resolution (via rig role bindings)
* optional `FAN` geometry

No time logic, no curve logic.

**Deliverable:** 4-fixture rooftop resolves consistent fan poses.

---

## Step 5 — Movement Generator (Temporal Only)

### Output

Normalized offset curves centered at `v=0.5`:

* `pan_curve`
* `tilt_curve`

### MVP Movements

* `SWEEP_LR`
* `CIRCLE`
* `HOLD`

Amplitude is applied later by the compiler.

**Deliverable:** Generated curves are repeat-ready (start == end).

---

## Step 6 — Dimmer Generator

### Output

Normalized absolute curves (`v ∈ [0,1]`).

### MVP Dimmers

* `FADE_IN`
* `PULSE`
* `HOLD`

Dimmer floor applied later.

**Deliverable:** Dimmer curves validate and stay within bounds.

---

## Step 7 — TemplateCompiler (Orchestrator)

### Responsibilities

1. Load template
2. Apply preset
3. Apply modifiers
4. Expand repeats
5. Compile steps into per-fixture `ChannelSegment`s

### Step Compilation Flow

For each step:

1. Resolve fixtures from rig groups
2. Compute phase offsets via rig orders
3. Resolve geometry → base poses
4. Generate movement curves
5. Generate dimmer curves
6. Apply phase offsets
7. Apply transitions (optional MVP+)
8. Emit per-fixture PAN/TILT/DIMMER segments

**Deliverable:** Compiler produces segments for a 16-bar window.

---

## Step 8 — xLights Exporter

### MVP Strategy

* Export **absolute DMX point curves**
* Convert normalized `[t,v]` to DMX at export time
* Ignore native curve optimization for MVP

**Deliverable:** Exported JSON matches existing pipeline expectations.

---

## Step 9 — Golden Test Harness

Create one golden test:

* Rig: rooftop_4
* Template: fan_pulse + ENERGETIC
* Plan: 16 bars

Assertions:

* Correct number of segments
* Phase offsets differ per fixture in intro
* Dimmer never drops below floor
* Start/end of repeat aligns

---

## Step 10 — Post-MVP Extensions (In Order)

1. Entry/exit transitions as envelopes
2. Curve inversion support
3. Point simplification
4. Additional movements/geometries
5. Native xLights curve optimization

---

## Key MVP Design Choice

For simplicity and correctness:

> **The compiler outputs absolute DMX point curves**, even if internally using base + offset separation.

This minimizes exporter complexity and makes the MVP immediately usable.

---

## Summary

This plan replaces the monolithic default handler with a compiler-based architecture that is:

* deterministic
* testable
* repeat-safe
* template-portable
* rig-agnostic

It preserves your strongest ideas (categorical parameters, curve abstraction) while eliminating the entanglement that currently blocks growth.
