# Vision & Strategy
## Music-Driven Group Sequencing & Choreography

## Vision
Build a **music-first show compiler** that transforms audio, lyrics, and a display model graph into coordinated, layered lighting choreography using **built-in xLights effects** applied to **groups of models**.

The system emphasizes:
- Musical timing and structure
- Spatial contrast and coordination across the display
- Layered composition (base, rhythm, highlight)
- Reusability and automation without sacrificing artistic control

This is **not** a frame renderer.  
It produces **structured effect placements** aligned to timing and lyrics that can be refined or re-rendered later.

---

## Guiding Principles

1. **Music is the source of truth**  
   All sequencing decisions anchor to timing tracks and lyric events.

2. **Groups, not pixels**  
   Choreography operates on logical display groups (roofline, arches, windows, etc.).

3. **Layered composition**  
   Every song is built from multiple coordinated layers, not one monolithic effect track.

4. **Spatial intent**  
   Left/right, center/out, vertical contrast, and symmetry are deliberate design tools.

5. **Data-only choreography**  
   Effects are described declaratively and rendered later.

6. **Automation with escape hatches**  
   Auto-generation provides a strong first pass; humans can override anything.

---

## Phase Roadmap

### Phase 1 — Musical Backbone & Group Choreography

**Goal**  
Produce musically coherent, spatially interesting sequences for core display elements.

**Scope**
- Timing tracks (bars, beats, sections)
- Lyric tracks (phrases + words)
- Group-based sequencing:
  - House outlines
  - Eves / icicles
  - Windows
  - Arches
  - Snowflakes
- Emphasis on:
  - Layering
  - Spatial contrast
  - Repeatable orchestration patterns

**Success Criteria**
- One song can be auto-sequenced end-to-end with:
  - Multiple timing tracks
  - Lyrics aligned to effects
  - At least three coordinated layers
  - Visible spatial intent

---

### Phase 2 — Accent Props & Performance Awareness

**Goal**  
Elevate the show with hero elements while maintaining balance.

**Scope**
- Mega trees
- Spinners
- Chorus / drop showcase moments
- Shader profiling and render cost awareness

**Outcomes**
- Accent props feel intentional, not overwhelming
- Performance constraints inform effect density and layering

---

### Phase 3 — Singing Decor & Matrices

**Goal**  
Make lyrics visible and expressive.

**Scope**
- Singing faces driven by lyric timing
- Matrices for:
  - Text
  - Images
  - Lyric callouts
  - Beat-reactive visuals

---

### Phase 4 — Multi-Agent Choreography

**Goal**  
Automate artistic decision-making while preserving quality.

**Scope**
- Planning agents propose choreography per section
- Assignment agents bind effects to groups
- Critic agents evaluate:
  - Over-saturation
  - Spatial monotony
  - Lyric alignment quality
  - Repetition vs motif development

---

## What This Project Is NOT
- Not a pixel-level renderer
- Not a replacement for artistic judgment
- Not locked to a single display layout
- Not effect-centric — effects serve musical and spatial intent

---

## Long-Term Aspiration
A reusable choreography engine where:
- New songs plug into existing display graphs
- Timing and lyric intelligence compound over time
- Shows feel designed, not random — even when auto-generated
