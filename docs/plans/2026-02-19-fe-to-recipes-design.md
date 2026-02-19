# Feature Engineering to Recipes — Design Document

**Date:** 2026-02-19
**Status:** Approved
**Approach:** A+B Hybrid (Context Enrichment → Recipe Engine)

## Problem Statement

The feature engineering pipeline produces rich semantic data (85K+ phrases, 3,202 mined templates, 78 motifs, 19K-edge transition graph, color narratives, layering metrics) that the planner and renderer do not consume. The planner selects from ~60 hand-authored builtin templates with no awareness of FE intelligence. Ten critical gaps exist between FE outputs and planner/renderer consumption.

## Goals

1. **Enrich planner context** with FE data so the LLM makes better template selections (Phase 1)
2. **Introduce EffectRecipe** as a multi-layer composite effect model inspired by xLights presets (Phase 2)
3. **Build a promotion pipeline** from FE-mined templates to curated EffectRecipes (Phase 2)
4. **Enable style transfer** — learn creator fingerprints and apply/evolve them on new songs (Phase 2)
5. **AI asset generation** on demand for imagery/video layers (Phase 2)
6. **Mine effect→model propensity** from corpus data (Phase 1)
7. **Full color intelligence** — palettes, song-level arcs, timing-aware shifts, spatial application (Phase 1)

## Non-Goals

- Changing the macro planner architecture
- Real-time rendering or preview
- User-facing UI for recipe editing (future)
- Collaborative/multi-user template sharing (future)

---

## Phase 1: Smarter Planner (Context Enrichment)

Activate FE data in the planner without changing the template model or renderer. Three new FE stages plus adapter activation.

### 1a. Color Arc Engine

**Module:** `feature_engineering/color_arc.py`

The current `ColorNarrativeRow` captures per-section color class (mono/palette/multi) and contrast shifts. The Color Arc Engine extends this to a song-level color plan.

**Output Model: `SongColorArc`**

```
SongColorArc
├── palette_library: list[NamedPalette]
│   └── NamedPalette:
│       ├── palette_id: str
│       ├── name: str
│       ├── colors: list[HexColor]
│       ├── mood_tags: list[str]
│       └── temperature: "warm" | "cool" | "neutral"
├── section_assignments: list[SectionColorAssignment]
│   └── SectionColorAssignment:
│       ├── section_label: str
│       ├── section_index: int
│       ├── palette_id: str
│       ├── spatial_mapping: dict[target_group_id, PaletteRole]
│       ├── shift_timing: ShiftTiming  # beat-aligned or section-boundary
│       └── contrast_target: float (0.0-1.0)
├── arc_curve: list[ArcKeyframe]
│   └── ArcKeyframe:
│       ├── position_pct: float (0-1)
│       ├── temperature: float
│       ├── saturation: float
│       └── contrast: float
└── transition_rules: list[ColorTransitionRule]
    └── ColorTransitionRule:
        ├── from_palette_id: str
        ├── to_palette_id: str
        ├── transition_style: "crossfade" | "cut" | "ripple"
        └── duration_bars: int
```

**Sources:** Existing `color_narrative.jsonl`, audio energy/structure analysis, holiday color theory heuristics (Christmas red/green/gold, winter blues, warm amber for ballads).

**Key capabilities:**
- Concrete hex palettes per section (not just "palette" or "mono" labels)
- Spatial color assignment (which groups get primary vs accent colors)
- Timing-aware palette shifts (beat-aligned transitions between palettes)
- Song-level arc curve for coherent color narrative

### 1b. Model/Group Propensity Miner

**Module:** `feature_engineering/propensity.py`

Mines effect→display-element affinity from corpus. Correlates which effect families appear on which model types.

**Output Model: `PropensityIndex`**

```
PropensityIndex
├── affinities: list[EffectModelAffinity]
│   └── EffectModelAffinity:
│       ├── effect_family: str
│       ├── model_type: str  # megatree, arch, matrix, candy_cane, etc.
│       ├── frequency: float
│       ├── exclusivity: float
│       └── corpus_support: int
├── anti_affinities: list[EffectModelAntiAffinity]
│   └── EffectModelAntiAffinity:
│       ├── effect_family: str
│       ├── model_type: str
│       └── corpus_support: int
└── model_type_vocabulary: list[str]
```

**Source:** Cross-reference `target_roles.jsonl` (target IDs) with xLights model definitions in sequence files to discover model types, then correlate with `effect_phrases.jsonl`.

### 1c. Style Fingerprint Extractor

**Module:** `feature_engineering/style.py`

Learns the signature of a sequence creator's work across their sequences.

**Output Model: `StyleFingerprint`**

```
StyleFingerprint
├── creator_id: str
├── recipe_preferences: dict[effect_family, float]
├── transition_style: TransitionStyleProfile
│   ├── preferred_gap_ms: float
│   ├── overlap_tendency: float (0=sharp cuts, 1=heavy overlaps)
│   └── variety_score: float (0=repetitive, 1=highly varied)
├── color_tendencies: ColorStyleProfile
│   ├── palette_complexity: float (mono→spectrum)
│   ├── contrast_preference: float
│   └── temperature_preference: float (cool→warm)
├── timing_style: TimingStyleProfile
│   ├── beat_alignment_strictness: float
│   ├── density_preference: float (sparse→busy)
│   └── section_change_aggression: float (subtle→dramatic)
├── layering_style: LayeringStyleProfile
│   ├── mean_layers: float
│   ├── max_layers: int
│   └── collision_tolerance: float
└── motif_preferences: dict[motif_signature, float]
```

**Source:** Aggregate existing FE artifacts (`layering_features.jsonl`, `color_narrative.jsonl`, `transition_graph.json`, `motif_catalog.json`) per creator/package.

### 1d. Adapter Activation

The existing `GroupPlannerAdapterPayload` gets consumed by the planner. Inject into the planner's developer prompt:

- Top-N template recommendations (from `template_retrieval_index.json`) with scores
- Transition compatibility hints (from `transition_graph.json`)
- Role bindings per target (from adapter payload)
- Color arc for current section (from Color Arc Engine)
- Propensity hints for target groups (from Propensity Miner)
- Style profile constraints (from Style Fingerprint, when user selects a reference style)

New template variables in planner prompts (`system.j2`, `developer.j2`):
- `{{ color_arc }}` — SectionColorAssignment for current section
- `{{ propensity_hints }}` — per-target recommended effect families
- `{{ style_constraints }}` — active style profile (if any)
- `{{ template_recommendations }}` — pre-ranked recipe list with scores
- `{{ transition_hints }}` — recommended transitions from previous section
- `{{ motif_context }}` — active motifs + compatibility scores
- `{{ layering_budget }}` — max concurrent layers, collision tolerance

---

## Phase 2: Recipe Engine (Structural Evolution)

### 2a. EffectRecipe Data Model

The central new abstraction — a multi-layer composite effect specification modeled on xLights presets. An EffectRecipe is directly renderable by the pipeline.

**Inspiration:** xLights `.xpreset` files (e.g., "Candy Cane Stack" = ColorWash base + Bars pattern + Sparkle accents, each with blend mode and mix level).

```
EffectRecipe
├── recipe_id: str                          # human-readable ("candy_cane_stack_v1")
├── name: str                               # display name
├── description: str
├── recipe_version: str                     # semver
├── schema_version: str                     # "effect_recipe.v1"
│
├── # Classification
├── template_type: GroupTemplateType         # BASE, RHYTHM, ACCENT, TRANSITION, SPECIAL
├── visual_intent: GroupVisualIntent         # ABSTRACT, IMAGERY, HYBRID, etc.
├── tags: list[str]
├── affinity_tags: list[str]
├── avoid_tags: list[str]
│
├── # Timing
├── timing: TimingHints                      # bars_min, bars_max, emphasize_downbeats
├── beat_alignment: BeatAlignmentHint        # STRICT, LOOSE, FREEFORM
│
├── # Color
├── palette_spec: PaletteSpec
│   ├── mode: ColorMode                      # MONOCHROME, DICHROME, TRIAD, etc.
│   ├── palette_roles: list[PaletteRole]     # which roles needed (PRIMARY, ACCENT, etc.)
│   ├── default_palette: NamedPalette | None # fallback
│   └── temperature_affinity: float | None   # warm/cool preference (-1 to 1)
│
├── # Layers (core composite structure)
├── layers: list[RecipeLayer]
│   └── RecipeLayer:
│       ├── layer_index: int                 # render order (0 = bottom)
│       ├── layer_name: str                  # "Base", "Pattern", "Accents"
│       ├── layer_depth: VisualDepth         # BACKGROUND, MIDGROUND, FOREGROUND, etc.
│       ├── effect_type: str                 # xLights effect name ("ColorWash", "Bars", etc.)
│       ├── blend_mode: BlendMode            # NORMAL, ADD, SCREEN, MULTIPLY
│       ├── mix: float                       # 0.0-1.0
│       ├── params: dict[str, ParamValue]    # effect-specific parameters
│       │   ├── Static: {"value": 25}
│       │   └── Dynamic: {"expr": "energy * 0.8", "min": 10, "max": 90}
│       ├── motion: list[MotionVerb]
│       ├── density: float                   # 0.0-1.0
│       ├── color_source: ColorSource        # PALETTE_PRIMARY, PALETTE_ACCENT, EXPLICIT, WHITE_ONLY
│       └── timing_offset: TimingOffset | None
│           └── TimingOffset: offset_beats, offset_ms
│
├── # Assets
├── asset_slots: list[AssetSlot]
│   └── AssetSlot:
│       ├── slot_id, slot_type, required
│       ├── preferred_tags: list[str]
│       ├── generation_prompt: str | None    # AI generation prompt hint
│       └── target_layer_index: int          # which RecipeLayer this feeds
│
├── # Propensity
├── model_affinities: list[ModelAffinity]
│   └── ModelAffinity: model_type, score
│
├── # Provenance
├── provenance: RecipeProvenance
│   ├── source: "builtin" | "mined" | "curated" | "generated"
│   ├── mined_template_ids: list[str]        # FE template UUIDs
│   ├── corpus_support: int
│   ├── cross_pack_stability: float
│   └── curation_decision: str | None
│
└── # Style metadata
    └── style_markers: StyleMarkers
        ├── complexity: float                # 0=simple, 1=complex
        ├── energy_affinity: EnergyTarget    # LOW, MED, HIGH, BUILD, CLIMAX, RELEASE
        └── genre_tags: list[str]            # ["upbeat", "ballad", "epic", "playful"]
```

**Key design decisions:**

- **Dynamic params:** `RecipeLayer.params` supports static values AND dynamic expressions tied to audio features (energy, tempo). Recipes adapt to different songs.
- **Palette references:** `color_source` references palette roles, not hardcoded colors. The Color Arc Engine assigns palettes; recipes consume them.
- **Asset linkage:** `asset_slots` link to specific layers via `target_layer_index`. AI-generated images go into specific composite layers.
- **Provenance tracking:** Full lineage from FE mining through curation to final recipe.
- **Backward compatibility:** Existing builtins are wrapped as single-layer EffectRecipes automatically.

### 2b. Promotion Pipeline

Implements the phased path from `fe_to_templates.md`, outputting EffectRecipes.

```
FE MinedTemplates
    ↓
[1. Quality Gate] → filter by quality_report thresholds
    ↓
[2. Candidate Builder] → normalize, assign deterministic IDs, attach metadata
    ↓
[3. Cluster Dedup] → use cluster_candidates to merge near-duplicates
    ↓
[4. Human Review Queue] → present candidates with keep/merge/reject decisions
    ↓
[5. Recipe Synthesizer] → convert approved candidates to EffectRecipe
    ↓
[6. Catalog Merge] → merge into EffectRecipe catalog alongside builtins
    ↓
[7. Retrieval Index Rebuild] → update retrieval index with new recipes
    ↓
curated_recipe_catalog.json + promotion_report.json
```

**Recipe Synthesizer mapping rules:**

| FE Field | Recipe Field | Mapping Logic |
|----------|-------------|---------------|
| `effect_family` | `layers[].effect_type` | Direct map: `color_wash`→`ColorWash`, `single_strand`→`SingleStrand`, `bars`→`Bars` |
| `effect_family` complexity | `layers` count | Simple families (on, color_wash) → 1 layer. Complex (butterfly, pinwheel) → 2-3 layers |
| `motion_class` | `layers[].motion` | `sweep`→SWEEP, `pulse`→PULSE, `static`→NONE, `sparkle`→SPARKLE |
| `color_class` | `palette_spec.mode` | `mono`→MONOCHROME, `palette`→DICHROME/TRIAD, `multi`→FULL_SPECTRUM |
| `energy_class` | `style_markers.energy_affinity` | `low`→LOW, `mid`→MED, `high`→HIGH |
| `taxonomy_labels` | `template_type` | `accent_hit`→ACCENT, `rhythm_driver`→RHYTHM, `texture_bed`/`sustainer`→BASE, `transition`→TRANSITION |
| `spatial_class` | `model_affinities` | `single_target`→higher specificity, `multi_target`→broader affinity |
| Transition graph | `affinity_tags`/`avoid_tags` | High-confidence successors → affinity; never-seen → avoid |

### 2c. Recipe-Aware Planner

- `SectionCoordinationPlan.placements[].template_id` references `recipe_id` (EffectRecipe) instead of `gtpl_*` builtin IDs
- `TemplateCatalog` merges builtins (auto-converted to EffectRecipe) + promoted FE recipes
- Backward compatible: existing builtins wrapped as single-layer EffectRecipes

### 2d. Recipe-Aware Renderer

The rendering pipeline reads `EffectRecipe.layers` and emits multi-layer xLights effects:

```
EffectRecipe → for each RecipeLayer:
    ├── resolve effect_type → xLights effect class
    ├── resolve color_source → concrete colors from SectionColorAssignment
    ├── evaluate dynamic params (substitute audio features)
    ├── apply timing (beat grid alignment + timing_offset)
    └── emit xLights effect element with blend_mode + mix
```

Replaces current single-effect-per-template rendering with composite output.

---

## Phase 2 Extensions

### 3a. Style Transfer & Blending

Uses the StyleFingerprint (Phase 1) to apply and evolve creator aesthetics.

**Style-Weighted Retrieval:**

```
Normal retrieval score × style_weight = final_score

style_weight =
  recipe_preference[effect_family] ×
  color_tendency_match ×
  timing_style_match ×
  layering_match
```

**Style Blending & Evolution:**

```
StyleBlend
├── base_style: StyleFingerprint           # primary style
├── accent_style: StyleFingerprint | None  # secondary style to mix in
├── blend_ratio: float                     # 0.0=pure base, 1.0=pure accent
├── evolution_params: StyleEvolution | None
│   └── StyleEvolution:
│       ├── direction: "more_complex" | "simpler" | "warmer" | "cooler" |
│       │              "higher_energy" | "calmer"
│       ├── intensity: float (0.0-1.0)
│       └── preserve: list[str]            # aspects to keep ["color", "timing", "transitions"]
```

**Capabilities:**
- "Like Creator A but with more energy"
- "Blend Creator A's colors with Creator B's timing"
- "My style but simpler"
- "Evolve this style toward warmer tones"

### 3b. AI Asset Generation Pipeline

For templates with imagery/video layers, assets generated on demand:

```
1. Planner outputs NarrativeAssetDirective
2. Asset Enrichment:
   - Inject section palette from Color Arc
   - Check target layer's blend_mode/mix for transparency needs
   - Determine resolution/aspect from model affinity
3. Generation Prompt Builder:
   - Combines directive + palette + technical constraints
   - Example: "Crystalline snowflake, colors #A8D8EA and #FFFFFF on
     transparent background, 16:9 aspect, suitable for LED matrix,
     high contrast edges, no fine detail below 4px"
4. Asset Generator (pluggable provider interface):
   - generate(prompt, constraints) → AssetResult
   - Implementations: DALL-E, Midjourney, Stable Diffusion, local model
5. Asset Post-Processing:
   - Resize to target resolution
   - Validate transparency
   - Palette conformance check
   - Content-hash caching for dedup
6. Asset Binding:
   - Stored in artifacts/{run_id}/assets/{asset_id}.png
   - Recipe placement updated with resolved_asset_ids
```

**Caching:** Content-hash dedup within run, directive-fingerprint cache across runs.

### 3c. Enhanced Motif Integration

**Motif-Aware Recipe Selection:**
- Each EffectRecipe gets `motif_compatibility: list[MotifCompatibility]` during promotion
- Recipe retrieval boosts recipes matching section's assigned motifs

**Motif Sequencing Rules:**
- Derive motif transition preferences from transition graph + motif catalog
- Inject into planner: "This section uses motif X. Previous used motif Y. Preferred transition: gradual blend over 2 bars"

---

## Planner Enrichment Summary

| FE Source | Planner Injection Point | Format |
|-----------|------------------------|--------|
| Color Arc | `SectionPlanningContext.color_arc` | SectionColorAssignment |
| Propensity | `SectionPlanningContext.propensity_hints` | Per-target model type + effect families |
| Style Profile | `SectionPlanningContext.style_constraints` | StyleBlend |
| Recipe Retrieval | `TemplateCatalog` (enriched) | Top-N recipes with scores |
| Transition Graph | `SectionPlanningContext.transition_hints` | Recommended transitions |
| Motif Catalog | `SectionPlanningContext.motif_context` | Active motifs + compatibility |
| Adapter Payload | `SectionPlanningContext.template_constraints` | Role bindings, quality-filtered recs |
| Layering Features | `SectionPlanningContext.layering_budget` | Max layers, collision tolerance |

---

## Critical Gaps Addressed

| Gap | Solution | Phase |
|-----|----------|-------|
| FE template IDs ↔ planner template IDs | EffectRecipe with human-readable recipe_id | Phase 2 |
| Taxonomy → GroupVisualIntent mismatch | Recipe Synthesizer mapping rules | Phase 2 |
| MotionClass → MotionVerb partial overlap | Formal conversion in Recipe Synthesizer | Phase 2 |
| ColorClass → ColorMode ambiguity | Color Arc Engine + PaletteSpec | Phase 1+2 |
| Asset slots disconnected | AI Asset Generation Pipeline | Phase 2 |
| Adapter payload not consumed | Adapter Activation in planner prompts | Phase 1 |
| Motif-template affinity unlinked | Motif compatibility scoring | Phase 2 |
| Quality gates not enforced | Quality gate as promotion pipeline entry | Phase 2 |
| Timing precision mismatch | BeatAlignmentHint on EffectRecipe | Phase 2 |
| No effect→model propensity | Propensity Miner | Phase 1 |

---

## Delivery Order

### Phase 1 (Context Enrichment — no model/renderer changes)
1. Color Arc Engine
2. Propensity Miner
3. Style Fingerprint Extractor
4. Adapter Activation (consume payload in planner prompts)

### Phase 2a (Recipe Foundation)
5. EffectRecipe data model (Pydantic models)
6. Builtin template → EffectRecipe auto-converter
7. Recipe Synthesizer (FE MinedTemplate → EffectRecipe)
8. Promotion Pipeline (quality gate → curation → catalog merge)

### Phase 2b (Planner/Renderer Integration)
9. Recipe-aware TemplateCatalog
10. Recipe-aware planner (template_id → recipe_id)
11. Recipe-aware renderer (multi-layer composite output)

### Phase 2c (Extensions)
12. Style Transfer + StyleBlend
13. AI Asset Generation Pipeline
14. Enhanced Motif Integration
15. Motif-aware recipe selection + sequencing rules
