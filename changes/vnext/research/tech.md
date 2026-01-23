# Technical Design
## Music-Driven Group Sequencing Engine

## System Overview
The system compiles **music analysis**, **display structure**, and **choreography rules**
into **effect placement instructions** targeting built-in xLights effects.

**Pipeline**
1. Audio analysis produces timing tracks
2. Lyrics become time-aligned lyric events
3. Display graph defines groups and spatial metadata
4. Choreography engine generates layered effect plans
5. Export produces xLights-compatible structures

---

## Canonical Timebase
All timing data resolves to:
- Absolute time in milliseconds
- Normalized position from 0.0 to 1.0

This allows:
- Tempo-aware reasoning
- Rescaling without recomputation

---

## Timing Tracks

### TimingTrack
A named collection of ordered time markers.

**Typical tracks**
- bars: downbeats / measure boundaries
- beats: quarter notes
- phrases: musical sections (4, 8, or 16 bars)
- micro: optional fine detail (e.g. 16ths)

**TimingMarker fields**
- time_ms
- normalized_position
- index

**Rules**
- Effects snap to a specific timing track
- Different layers prefer different tracks
- Manual adjustment is a first-class operation

---

## Lyric Tracks
Lyrics are treated as **timing events**, not text blobs.

### LyricToken

**Fields**
- text
- start_ms
- end_ms
- type: PHRASE or WORD
- confidence
- source: manual or auto

**Capabilities**
- Phrase-level events for large visual moments
- Word-level events for hits and accents
- Future extension to phonemes (Phase 3)

---

## Display Graph

### DisplayGroup
Logical collections of models.

**Fields**
- id
- models
- spatial_tags: LEFT, RIGHT, CENTER, TOP, BOTTOM, FRONT
- symmetry_group (optional)

**Examples**
- Roofline
- Windows
- Arches
- Icicles
- Snowflakes

Groups are the **primary choreography target**.

---

## Spatial Roles & Zones
Spatial metadata enables contrast and coordination.

**Common roles**
- OUTER_LEFT
- INNER_LEFT
- CENTER
- INNER_RIGHT
- OUTER_RIGHT

**Used for**
- Call-and-response
- Mirrored motion
- Ripples
- Directional sweeps

---

## Layering Model

### Base Layer
- Slow and continuous
- Anchors the visual look
- Uses bars or phrases
- Examples: color wash, slow gradient, ambient twinkle

### Rhythm Layer
- Responds to beats
- Adds energy and pulse
- Examples: pulses, short chases, on/off accents

### Highlight Layer
- Short, intentional moments
- Driven by lyrics or section hits
- Examples: bursts, sweeps, sparkle hits

---

## Spatial Pattern Library

Reusable orchestration patterns applied across layers.

**Core patterns**
- CALL_RESPONSE (left to right)
- MIRROR (symmetrical)
- RIPPLE (center outward)
- SWEEP (directional)
- VERTICAL_SPLIT (roof vs windows vs ground)

Patterns are:
- Independent of effect choice
- Reusable across props and songs

---

## Effect Placement Model

Effects are described declaratively.

**EffectPlacement fields**
- group_id
- layer_type
- timing_track
- start_marker
- end_marker
- effect_type
- parameters
- spatial_pattern

**Notes**
- No pixel math
- No fixture assumptions
- Parameters may be static or automated later

---

## Phase 1 Constraints
- Built-in xLights effects only
- No per-pixel shaders
- No singing faces
- Manual overrides allowed everywhere

---

## Extensibility Hooks
Designed for future phases:
- Shader metadata (Phase 2)
- Lyric-driven animation (Phase 3)
- Agent-based planning and critique (Phase 4)

---

## Definition of Done (Phase 1)
A single song can be processed to produce:
- Multiple timing tracks
- A lyric track
- Layered effect plans for all core display groups
- Clear spatial contrast and coordination
- A sequence that feels musically intentional

---

## Key Design Philosophy
Structure first, polish later.

If timing, grouping, and layering are correct,
effect selection becomes refinement — not rescue.
