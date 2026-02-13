# Blog Series — Illustration Index

Every illustration needed across the series, with descriptions, context, and placement info. Each entry corresponds to a `<!-- ILLUSTRATION: ILL-XX-NN -->` placeholder in the blog posts.

## Global Style Guide (applies to all illustrations)

- **Look:** sketch/hand-drawn technical illustrations with personality (whiteboard energy), not sterile architecture diagrams.
- **Theme:** dark background preferred (Twinklr dark theme), high-contrast strokes, minimal clutter.
- **Readability:** big shapes, labeled callouts, **no tiny text**.
- **Motion/time:** whenever the concept involves time, show a **time axis**, ghosted frames, arrows, or small “frame strip” panels.
- **“So what would I see?”** each illustration must include a small **VIEW** callout describing what the street-view audience sees (beams, pulses, fan opens, etc.).

**Format:** PNG, minimum 1400px wide (2x for Retina).
**Output directory:** `data/blog/assets/illustrations/`

---

## Part 0: Overview

### ILL-00-00 — Blog Header Banner — From Beats to Beams

**File:** `assets/illustrations/00_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Twinklr blog header showing beat ticks transforming into moving-head beams over a house roofline

**Description / Prompt:**
A wide banner illustration. Left side: subtle audio waveform / beat ticks. Right side: a residential roofline at night with several moving-head beams. In the middle, the waveform morphs into beams via a few “categorical tiles” (PHRASE, HIGH, fan_pulse) floating like stickers.
Include a small **VIEW:** callout: “Audience sees: big fan-open + beat-synced pulses.”

---

### ILL-00-01 — Moving Heads on a Roofline

**File:** `assets/illustrations/00_moving_heads_roofline.png`
**Placement:** After the opening paragraph, before “Moving Heads: The Show-Offs of the Rig”.
**Alt text:** Eight moving head fixtures mounted across a residential roofline at night, beams fanning outward

**Description / Prompt:**
Night scene: eight moving-head fixtures spaced along a suburban roofline. Beams are visible (light haze), arranged as a clean symmetrical fan. Add simple labels for “pan / tilt / dimmer” with arrows.
**Motion cue:** show faint ghosted beam positions (3-frame fan-open) to imply movement.
**VIEW:** “From the street: the whole roof ‘opens’ like wings.”

---

### ILL-00-02 — The Creative ↔ Deterministic Boundary

**File:** `assets/illustrations/00_boundary_split.png`
**Placement:** Near the section explaining the boundary between LLM intent and deterministic rendering.
**Alt text:** Split panel: LLM creative intent on the left, deterministic renderer on the right, bridged by categorical vocabulary

**Description / Prompt:**
Split-panel. Left: speech bubbles / fuzzy ideas (“bigger, dramatic, chase!”), soft shapes. Right: clean rails of DMX lanes (pan/tilt/dimmer curves). Center bridge: a strip of **categorical vocabulary tiles** (SECTION/PHRASE, LOW/MED/HIGH, motif ids).
**Motion cue:** a small arrowed timeline flowing left→right.
**VIEW:** “The audience gets smooth, repeatable motion—not random jitter.”

---

### ILL-00-03 — End-to-End Pipeline (Illustrated, not Mermaid)

**File:** `assets/illustrations/00_full_pipeline.png`
**Placement:** Replace the mermaid pipeline diagram.
**Alt text:** Illustrated pipeline from audio analysis through planning to rendering and export

**Description / Prompt:**
A single, playful pipeline illustration with 5–7 large nodes:
Audio → Profiles → Plan → Validate/Judge Loop → Compile Curves → Export (xLights/DMX).
Each node has a tiny icon (waveform, filter funnel, planner card, stoplight gate, curve graph, export file).
**Motion cue:** curved arrows with “iteration loop” swirl around Validate/Judge.
**VIEW:** “What you see: beats become synchronized motion and brightness hits.”

---

## Part 1: Audio Analysis & Feature Extraction

### ILL-01-00 — Blog Header Banner — Hearing the Music

**File:** `assets/illustrations/01_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing a waveform and beat grid aligning with a light show timeline

**Description / Prompt:**
Wide banner. Top layer: waveform + beat ticks. Bottom layer: a simplified “light lane” timeline (pulses aligned to beats). Include a ‘snap’ magnet icon pulling raw hits onto ticks.
**VIEW:** “The pulses land exactly on the beat.”

---

### ILL-01-01 — Energy Curves at Multiple Scales

**File:** `assets/illustrations/01_energy_curves.png`
**Placement:** In the “Energy Curves” section.
**Alt text:** Three overlaid energy curves on a shared time axis at beat/phrase/section smoothing levels

**Description / Prompt:**
Plot-like sketch with one time axis and three colored-ish strokes (don’t rely on color; use line styles). Show beat-scale jitter, phrase-scale smoother, section-scale smoothest.
**Motion cue:** a small ‘zoom’ strip showing smoothing windows expanding.
**VIEW:** “Bigger sections get broader lighting moves; beats get punches.”

---

### ILL-01-02 — Lyrics Waterfall Fallback

**File:** `assets/illustrations/01_lyrics_waterfall.png`
**Placement:** In the lyrics retrieval section.
**Alt text:** A five-stage lyrics fallback waterfall from best/fastest to slowest/last resort

**Description / Prompt:**
Waterfall diagram with 5 steps (API source → cache → alt API → transcription → manual). Each step has cost/time bars increasing.
**VIEW:** “More reliable lyrics means cleaner mouth/phoneme timing later.”

---

### ILL-01-03 — Audio Analysis Pipeline (Illustrated, not Mermaid)

**File:** `assets/illustrations/01_audio_pipeline.png`
**Placement:** Replace the mermaid audio pipeline diagram.
**Alt text:** Pipeline for extracting beats, sections, energy, and lyric anchors

**Description / Prompt:**
Pipeline nodes: Load audio → Beat tracking → Section detection → Energy curves → Lyrics anchors → Build BeatGrid.
**Motion cue:** show a little timeline strip at bottom that gains more tick marks as pipeline progresses.
**VIEW:** “All later choreography snaps to these ticks.”

---

### ILL-01-04 — Snap to Grid (Before/After)

**File:** `assets/illustrations/01_snap_to_grid.png`
**Placement:** Immediately after the paragraph describing `snap_to_grid()` and drift removal.
**Alt text:** Raw event times snapping onto a beat grid, showing drift removed

**Description / Prompt:**
Two-panel before/after.
- BEFORE: raw event dots near beat ticks (slightly off).
- AFTER: dots snapped exactly onto ticks (with a small label: “binary search”).
Add an inset of a moving-head pulse lane: BEFORE looks late/early; AFTER lands perfectly.
**VIEW:** “The audience sees hits that feel ‘tight’ and musical.”

---

## Part 2: Audio Profiling (Context Compression)

### ILL-02-00 — Blog Header Banner — Compression With Taste

**File:** `assets/illustrations/02_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing a big messy feature cloud compressed into a crisp profile card

**Description / Prompt:**
Banner: left is a messy cloud of raw features; right is a clean “AudioProfile” card (energy arc, groove, lyric anchors). A compression lens/funnel sits in the middle.
**VIEW:** “Cleaner profile → more coherent lighting choices.”

---

### ILL-02-01 — Profiling Pipeline (Filtering the Signal)

**File:** `assets/illustrations/02_profiling_pipeline.png`
**Placement:** In the profiling pipeline section (replaces generic flow references).
**Alt text:** Illustration of profiling turning raw audio features into a compact, decision-ready profile

**Description / Prompt:**
Show a pipeline where raw features enter a “taste filter” funnel and emerge as a small set of actionable knobs (energy arc, intensity bands, groove, sentiment).
**Motion cue:** show size shrinking (100KB → 10KB) along the arrow.
**VIEW:** “The planner stops rambling and makes confident, repeatable moves.”

---

### ILL-02-02 — Profiling Pipeline (Illustrated, not Mermaid)

**File:** `assets/illustrations/02_profiling_pipeline_overview.png`
**Placement:** Replace the mermaid profiling pipeline diagram.
**Alt text:** End-to-end view of raw features → compression → profile artifact

**Description / Prompt:**
A simplified overview with 4–5 nodes and a bold “10x smaller” callout.
Include a tiny “Profile Card” output with 5 fields.
**VIEW:** “Same song, but the AI focuses on what changes the show.”

---

### ILL-02-03 — What Survives Compression (Feature Sieve)

**File:** `assets/illustrations/02_survives_compression.png`
**Placement:** Right after the first paragraph in “The 10x Compression: Why Less Is More”.
**Alt text:** A sieve keeping only actionable musical signals and dropping raw noise

**Description / Prompt:**
A sieve/sorting tray illustration labeled:
KEEP: energy arc, section boundaries, groove pattern, lyric anchors, mood tags.
DROP: raw MFCC dump, overly granular transients, redundant metadata.
**Motion cue:** particles falling through; kept items form a neat stack of cards.
**VIEW:** “The show still feels like the song—without overfitting.”

---

## Part 3: Multi-Agent Planning

### ILL-03-00 — Blog Header Banner — Planner vs Judge

**File:** `assets/illustrations/03_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing planner cards and judge feedback looping over a timeline

**Description / Prompt:**
Banner: timeline across the bottom. Above it, planner emits a plan card; judge stamps it (green/red) and arrows loop back.
**VIEW:** “Iteration turns ‘okay’ into ‘wow’ without chaos.”

---

### ILL-03-01 — Planner/Judge Dialogue

**File:** `assets/illustrations/03_iteration_loop.png`
**Placement:** In the section describing the refinement loop.
**Alt text:** A conversational loop where planner proposes and judge critiques with structured feedback

**Description / Prompt:**
Comic-strip style: panel 1 plan card, panel 2 judge notes, panel 3 revised plan. Keep text minimal.
**Motion cue:** looping arrows and iteration count (1→2→3).
**VIEW:** “Each pass adds variety + tighter beat hits.”

---

### ILL-03-02 — Planning Loop Overview (Illustrated, not Mermaid)

**File:** `assets/illustrations/03_multi_agent_loop.png`
**Placement:** Replace the mermaid multi-agent diagram.
**Alt text:** High-level view of section planners running in parallel and a holistic judge across sections

**Description / Prompt:**
Show parallel lanes (Section A/B/C planners) feeding into a “Holistic Judge” node. Include a merge fan-in.
**Motion cue:** parallel arrows moving forward in time; the judge sits above as a ‘roof’.
**VIEW:** “The whole show feels cohesive, not random sections stitched together.”

---

### ILL-03-03 — Validator Stoplight Gate (Tier 1 → Tier 2)

**File:** `assets/illustrations/03_validator_gate.png`
**Placement:** Immediately under “Tier 1: Heuristic Validator (free, instant)”.
**Alt text:** Stoplight gate showing cheap validation before expensive judge calls

**Description / Prompt:**
A stoplight gate at the front of a tunnel:
- Red lane: “schema invalid”, “timing out of bounds”, “reused template too much”
- Green lane: pass to judge
Include a small cost icon: Tier 1 = $0, Tier 2 = $$.
**Motion cue:** cars/plan-cards moving through gate.
**VIEW:** “Fewer weird glitches make it to rendering.”

---

## Part 4: Categorical Planning

### ILL-04-00 — Blog Header Banner — Categorical Tiles

**File:** `assets/illustrations/04_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing categorical tiles (PHRASE/HIGH/motifs) bridging to smooth curves

**Description / Prompt:**
Banner: categorical tiles sliding onto a timeline, generating smooth curves underneath.
**VIEW:** “The audience sees smooth motion that still follows intent.”

---

### ILL-04-01 — Numbers Out, Categories In

**File:** `assets/illustrations/04_categorical_bridge.png`
**Placement:** In the section describing the pivot to categorical planning.
**Alt text:** Illustration showing numeric micromanagement replaced by categorical intent that compiles cleanly

**Description / Prompt:**
Left: a tangled ball of numbers (angles, speeds). Right: clean categorical tags. Bottom: renderer curves from tags.
**Motion cue:** “before/after” with arrows; show jitter smoothing.
**VIEW:** “No more twitchy servos; just clean choreography.”

---

## Part 5: Prompt Engineering

### ILL-05-00 — Blog Header Banner — Prompt Packs & Contracts

**File:** `assets/illustrations/05_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing stacked prompt layers and an injected schema block

**Description / Prompt:**
Banner: layered cards labeled System / Developer / User with a schema block sliding in like a puzzle piece.
**VIEW:** “Cleaner outputs → fewer judge rejections.”

---

### ILL-05-01 — Schema Repair Loop

**File:** `assets/illustrations/05_schema_repair.png`
**Placement:** In the schema repair loop section.
**Alt text:** Loop that repairs malformed JSON into schema-valid output with minimal tokens

**Description / Prompt:**
Loop: LLM output → validator → repair prompt → fixed JSON. Keep it playful.
**Motion cue:** ‘broken’ icon becomes ‘fixed’ icon.
**VIEW:** “Less time fighting formatting, more time designing effects.”

---

### ILL-05-02 — Prompt Engineering System Overview (Illustrated, not Mermaid)

**File:** `assets/illustrations/05_prompt_system.png`
**Placement:** Replace the mermaid diagram in this post.
**Alt text:** Overview of prompt packs, schema injection, validators, and judge feedback

**Description / Prompt:**
A systems view: prompt pack → model → output → heuristic validator → judge → revision prompt.
**Motion cue:** arrows with iteration loop swirl.
**VIEW:** “Iteration gets cheaper and more reliable.”

---

### ILL-05-03 — Schema Injection Contract Test (CI Guardrail)

**File:** `assets/illustrations/05_schema_contract_test.png`
**Placement:** Inside “Schema Injection Contract Test”.
**Alt text:** CI test failing when schema changes until prompt pack is updated

**Description / Prompt:**
Comic: developer changes schema file → CI red X → prompt pack updated → CI green check.
Include a tiny “injected schema” block icon.
**Motion cue:** red→green transition.
**VIEW:** “Prevents silent failures and wasted render cycles.”

---

## Part 6: Rendering & Compilation

### ILL-06-00 — Blog Header Banner — Curves, Not Guesswork

**File:** `assets/illustrations/06_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing moving head pan/tilt/dimmer curves aligned to beat ticks with beams in the background

**Description / Prompt:**
Banner: beat ticks along top; three curve lanes (pan/tilt/dimmer) below; faint roofline with beams behind.
**VIEW:** “Beams glide and pulse exactly on hits.”

---

### ILL-06-01 — Phase Offsets (Chase Motion)

**File:** `assets/illustrations/06_phase_offsets.png`
**Placement:** In “Phase Offsets: Making Lights Chase”.
**Alt text:** Three fixtures following the same pulse pattern with phase offsets, creating a chase

**Description / Prompt:**
Show 3–5 lanes of pulses offset in time, plus a small top view of roofline beams moving left→right.
**Motion cue:** arrow indicating chase direction; ghosted beam positions.
**VIEW:** “A ripple travels across the roof.”

---

### ILL-06-02 — Compilation Pipeline (Already-Rendered Reference)

**File:** `assets/illustrations/06_compilation_pipeline.png`
**Placement:** In “The Compilation Pipeline”.
**Alt text:** Compilation pipeline from template intent to channel curves to export

**Description / Prompt:**
Use the existing pipeline illustration concept but ensure each node is visually distinct and includes a tiny ‘curve’ icon.
**Motion cue:** curve lanes appear progressively as you move right.
**VIEW:** “Intent becomes smooth motion.”

---

### ILL-06-03 — Rendering & Compilation Pipeline (Illustrated, not Mermaid)

**File:** `assets/illustrations/06_rendering_pipeline_overview.png`
**Placement:** Replace the mermaid diagram in this post.
**Alt text:** High-level rendering & compilation overview with curve generation and blending

**Description / Prompt:**
Overview with emphasis on **curves** and **transitions**:
Plan card → resolve targets → generate curves → blend transitions → export.
**Motion cue:** show curve continuity across section boundary (no jumps).
**VIEW:** “No pops; beams move naturally.”

---

### ILL-06-04 — Hero: Template Card → Pan/Tilt/Dimmer Curves → Street View

**File:** `assets/illustrations/06_hero_template_to_curves.png`
**Placement:** In “Hero Walkthrough: One Template → Rendered Curves”.
**Alt text:** A single phrase template becoming rendered curves and the resulting moving-head beam choreography

**Description / Prompt:**
Hero multi-panel (3 panels):
1) **Template card**: `fan_pulse`, PHRASE, MED intensity, motif tag; plus beat span (bar/beat).
2) **Rendered curves**: three lanes (pan, tilt, dimmer) with easing; dimmer hits land on beat ticks; include limits (min/max).
3) **Street view**: roofline with beams showing fan open + pulse. Use 3 ghosted frames or a tiny frame strip to imply motion.

Include a small **VIEW:** callout: “Audience sees: fan opens smoothly, pulses ‘thump’ on beats, then relaxes.”

**Notes:**
If you have a canonical template card layout, mirror it here for consistency.

---

## Part 7: Lessons Learned

### ILL-07-00 — Blog Header Banner — The Twinklr Playbook

**File:** `assets/illustrations/07_banner.png`
**Placement:** Directly under the H1 title.
**Alt text:** Banner showing a toolbox of transferable patterns with a light show in the background

**Description / Prompt:**
Banner: toolbox with 5 labeled tools (vocab, schema, validation, compression, compilation). Background: subtle roofline beams.
**VIEW:** “Steal the tools, build your own show.”

---

### ILL-07-01 — What to Steal Toolbox Infographic

**File:** `assets/illustrations/07_what_to_steal.png`
**Placement:** Inside the “What to Steal” section.
**Alt text:** Infographic of five transferable patterns represented as tools

**Description / Prompt:**
A clean infographic with 5 tools:
- Tile set (categorical vocab)
- Puzzle piece (schema injection)
- Stoplight (two-tier validation)
- Funnel (context compression)
- Ruler/curve (deterministic compiler)

Each tool has a 1-line example label.
**VIEW:** “These prevent the ‘LLM chaos’ feeling.”

---

### ILL-07-02 — Lessons Roadmap (Illustrated, not Mermaid)

**File:** `assets/illustrations/07_roadmap.png`
**Placement:** Replace the mermaid diagram in this post.
**Alt text:** Roadmap-style illustration of the pipeline and next steps

**Description / Prompt:**
A roadmap with milestones (Analysis, Profiling, Planning, Validation, Rendering, Export) and a “Next” branch.
**Motion cue:** path moving forward; optional ‘future’ dotted line.
**VIEW:** “This is the path from song → show.”

---

