#!/usr/bin/env python3
"""Demo script for the FE-to-Recipes pipeline.

Exercises each phase of the recipe pipeline with synthetic data,
printing human-readable summaries at each stage. Use --phase to
run specific phases or 'all' for the complete pipeline.

Usage:
    uv run python scripts/demo_recipe_pipeline.py --phase all
    uv run python scripts/demo_recipe_pipeline.py --phase 1
    uv run python scripts/demo_recipe_pipeline.py --phase 2a
    uv run python scripts/demo_recipe_pipeline.py --phase 2b
    uv run python scripts/demo_recipe_pipeline.py --phase 2c
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Phase 1 imports
# ---------------------------------------------------------------------------
from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    ColorTransitionRule,
    NamedPalette,
    SectionColorAssignment,
    SongColorArc,
)
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    PropensityIndex,
)
from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleBlend,
    StyleEvolution,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)

# ---------------------------------------------------------------------------
# Phase 2 imports
# ---------------------------------------------------------------------------
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateKind,
)
from twinklr.core.feature_engineering.promotion import PromotionPipeline
from twinklr.core.feature_engineering.style_transfer import (
    StyleBlendEvaluator,
    StyleWeightedRetrieval,
)
from twinklr.core.sequencer.display.recipe_renderer import (
    RecipeRenderer,
    RenderEnvironment,
)
from twinklr.core.sequencer.templates.group.models.template import TimingHints
from twinklr.core.sequencer.templates.group.recipe import (
    ColorSource,
    EffectRecipe,
    MotifCompatibility,
    PaletteSpec,
    ParamValue,
    RecipeLayer,
    RecipeProvenance,
    StyleMarkers,
)
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.vocabulary import (
    BlendMode,
    ColorMode,
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    MotionVerb,
    VisualDepth,
)


# ===================================================================
# Helpers
# ===================================================================

def _header(title: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _subheader(title: str) -> None:
    print(f"\n--- {title} ---")


def _kv(label: str, value: Any) -> None:
    print(f"  {label}: {value}")


# ===================================================================
# Synthetic data factories
# ===================================================================

def _make_palettes() -> tuple[NamedPalette, ...]:
    return (
        NamedPalette(
            palette_id="pal_christmas_classic",
            name="Christmas Classic",
            colors=("#E53935", "#43A047", "#FFFFFF"),
            mood_tags=("festive", "traditional"),
            temperature="warm",
        ),
        NamedPalette(
            palette_id="pal_icy_blue",
            name="Icy Blue",
            colors=("#A8D8EA", "#E0F7FA", "#FFFFFF"),
            mood_tags=("calm", "winter"),
            temperature="cool",
        ),
    )


def _make_color_arc() -> SongColorArc:
    palettes = _make_palettes()
    return SongColorArc(
        schema_version="v1.0.0",
        palette_library=palettes,
        section_assignments=(
            SectionColorAssignment(
                schema_version="v1.0.0",
                package_id="pkg-demo",
                sequence_file_id="seq-demo",
                section_label="intro",
                section_index=0,
                palette_id="pal_icy_blue",
                spatial_mapping={"group_megatree": "primary"},
                shift_timing="section_boundary",
                contrast_target=0.3,
            ),
            SectionColorAssignment(
                schema_version="v1.0.0",
                package_id="pkg-demo",
                sequence_file_id="seq-demo",
                section_label="chorus",
                section_index=1,
                palette_id="pal_christmas_classic",
                spatial_mapping={"group_megatree": "primary", "group_arch": "accent"},
                shift_timing="beat_aligned",
                contrast_target=0.8,
            ),
        ),
        arc_curve=(
            ArcKeyframe(position_pct=0.0, temperature=0.3, saturation=0.5, contrast=0.3),
            ArcKeyframe(position_pct=0.5, temperature=0.7, saturation=0.8, contrast=0.7),
            ArcKeyframe(position_pct=1.0, temperature=0.5, saturation=0.6, contrast=0.5),
        ),
        transition_rules=(
            ColorTransitionRule(
                from_palette_id="pal_icy_blue",
                to_palette_id="pal_christmas_classic",
                transition_style="crossfade",
                duration_bars=2,
            ),
        ),
    )


def _make_propensity_index() -> PropensityIndex:
    return PropensityIndex(
        schema_version="v1.0.0",
        affinities=(
            EffectModelAffinity(effect_family="shimmer", model_type="MegaTree", frequency=0.85, exclusivity=0.6, corpus_support=25),
            EffectModelAffinity(effect_family="color_wash", model_type="Arch", frequency=0.62, exclusivity=0.4, corpus_support=18),
            EffectModelAffinity(effect_family="fire", model_type="Matrix", frequency=0.78, exclusivity=0.7, corpus_support=22),
        ),
    )


def _make_style_fingerprint() -> StyleFingerprint:
    return StyleFingerprint(
        creator_id="demo_creator",
        recipe_preferences={"shimmer": 0.8, "sparkle": 0.6, "color_wash": 0.4},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=100.0,
            overlap_tendency=0.3,
            variety_score=0.6,
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.5,
            contrast_preference=0.7,
            temperature_preference=0.6,
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.7,
            density_preference=0.55,
            section_change_aggression=0.4,
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=2.0,
            max_layers=4,
            blend_mode_preference="add",
        ),
        corpus_sequence_count=15,
    )


def _make_mined_templates() -> list[MinedTemplate]:
    return [
        MinedTemplate(
            template_id="tpl_shimmer_sweep_001",
            template_kind=TemplateKind.CONTENT,
            template_signature="shimmer|sweep|palette|mid|sustained|single_target|rhythm_driver",
            support_count=25,
            distinct_pack_count=5,
            support_ratio=0.45,
            cross_pack_stability=0.72,
            effect_family="shimmer",
            motion_class="sweep",
            color_class="palette",
            energy_class="mid",
            continuity_class="sustained",
            spatial_class="single_target",
        ),
        MinedTemplate(
            template_id="tpl_sparkle_pulse_002",
            template_kind=TemplateKind.CONTENT,
            template_signature="sparkle|pulse|palette|high|sustained|single_target|rhythm_driver",
            support_count=18,
            distinct_pack_count=4,
            support_ratio=0.35,
            cross_pack_stability=0.65,
            effect_family="sparkle",
            motion_class="pulse",
            color_class="palette",
            energy_class="high",
            continuity_class="sustained",
            spatial_class="single_target",
        ),
        MinedTemplate(
            template_id="tpl_weak_003",
            template_kind=TemplateKind.CONTENT,
            template_signature="on|static|mono|low|sustained|single_target|base_ambient",
            support_count=2,
            distinct_pack_count=1,
            support_ratio=0.05,
            cross_pack_stability=0.15,
            effect_family="on",
            motion_class="static",
            color_class="mono",
            energy_class="low",
            continuity_class="sustained",
            spatial_class="single_target",
        ),
    ]


def _make_builtin_recipes() -> list[EffectRecipe]:
    return [
        EffectRecipe(
            recipe_id="builtin_wash_soft_v1",
            name="Soft Wash",
            description="Gentle color wash for ambient base layers",
            recipe_version="1.0.0",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=["wash", "ambient", "base"],
            timing=TimingHints(bars_min=4, bars_max=64),
            palette_spec=PaletteSpec(mode=ColorMode.MONOCHROME, palette_roles=["primary"]),
            layers=(
                RecipeLayer(
                    layer_index=0,
                    layer_name="Wash",
                    layer_depth=VisualDepth.BACKGROUND,
                    effect_type="ColorWash",
                    blend_mode=BlendMode.NORMAL,
                    mix=1.0,
                    params={"Speed": ParamValue(value=0)},
                    motion=[MotionVerb.FADE],
                    density=0.9,
                    color_source=ColorSource.PALETTE_PRIMARY,
                ),
            ),
            provenance=RecipeProvenance(source="builtin"),
        ),
        EffectRecipe(
            recipe_id="builtin_candy_cane_v1",
            name="Candy Cane Stack",
            description="Red/white striped bars with sparkle overlay",
            recipe_version="1.0.0",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=["candy_cane", "christmas", "classic"],
            timing=TimingHints(bars_min=4, bars_max=32),
            palette_spec=PaletteSpec(mode=ColorMode.DICHROME, palette_roles=["primary", "accent"]),
            layers=(
                RecipeLayer(
                    layer_index=0,
                    layer_name="Base Wash",
                    layer_depth=VisualDepth.BACKGROUND,
                    effect_type="ColorWash",
                    blend_mode=BlendMode.NORMAL,
                    mix=1.0,
                    params={"Speed": ParamValue(value=0)},
                    motion=[MotionVerb.FADE],
                    density=0.8,
                    color_source=ColorSource.PALETTE_PRIMARY,
                ),
                RecipeLayer(
                    layer_index=1,
                    layer_name="Bars",
                    layer_depth=VisualDepth.MIDGROUND,
                    effect_type="Bars",
                    blend_mode=BlendMode.ADD,
                    mix=0.7,
                    params={
                        "BarCount": ParamValue(expr="energy * 12", min_val=4, max_val=16),
                        "Direction": ParamValue(value="Diagonal"),
                    },
                    motion=[MotionVerb.SWEEP],
                    density=0.6,
                    color_source=ColorSource.PALETTE_ACCENT,
                ),
                RecipeLayer(
                    layer_index=2,
                    layer_name="Sparkle",
                    layer_depth=VisualDepth.FOREGROUND,
                    effect_type="Sparkle",
                    blend_mode=BlendMode.SCREEN,
                    mix=0.4,
                    params={"Density": ParamValue(value=30)},
                    motion=[MotionVerb.SPARKLE],
                    density=0.3,
                    color_source=ColorSource.WHITE_ONLY,
                ),
            ),
            provenance=RecipeProvenance(source="builtin"),
            style_markers=StyleMarkers(complexity=0.6, energy_affinity=EnergyTarget.MED),
            motif_compatibility=[
                MotifCompatibility(motif_id="candy_cane", score=0.95, reason="Direct match"),
            ],
        ),
    ]


# ===================================================================
# Phase demos
# ===================================================================

def demo_phase1() -> dict[str, Any]:
    """Phase 1: Context Enrichment artifacts."""
    _header("Phase 1: Context Enrichment")

    # Color Arc
    _subheader("Color Arc Engine")
    arc = _make_color_arc()
    _kv("Palettes", len(arc.palette_library))
    for p in arc.palette_library:
        _kv(f"  {p.name}", f"{p.colors} ({p.temperature})")
    _kv("Section assignments", len(arc.section_assignments))
    for a in arc.section_assignments:
        _kv(f"  [{a.section_index}] {a.section_label}", f"palette={a.palette_id}, contrast={a.contrast_target}")
    _kv("Arc keyframes", len(arc.arc_curve))
    for k in arc.arc_curve:
        _kv(f"  {k.position_pct:.0%}", f"temp={k.temperature}, sat={k.saturation}, contrast={k.contrast}")
    _kv("Transition rules", len(arc.transition_rules))
    for r in arc.transition_rules:
        _kv(f"  {r.from_palette_id} -> {r.to_palette_id}", f"{r.transition_style} ({r.duration_bars} bars)")

    # Propensity
    _subheader("Propensity Miner")
    prop = _make_propensity_index()
    _kv("Model affinities", len(prop.affinities))
    for a in prop.affinities:
        _kv(f"  {a.model_type}", f"family={a.effect_family}, freq={a.frequency:.2f}, excl={a.exclusivity:.2f}")

    # Style Fingerprint
    _subheader("Style Fingerprint")
    style = _make_style_fingerprint()
    _kv("Creator", style.creator_id)
    _kv("Corpus sequences", style.corpus_sequence_count)
    _kv("Recipe preferences", dict(style.recipe_preferences))
    _kv("Layering", f"mean={style.layering_style.mean_layers}, max={style.layering_style.max_layers}")
    _kv("Timing density", f"{style.timing_style.density_preference:.2f}")
    _kv("Color contrast pref", f"{style.color_tendencies.contrast_preference:.2f}")

    print("\nPhase 1 complete.")
    return {"color_arc": arc, "propensity": prop, "style": style}


def demo_phase2a() -> dict[str, Any]:
    """Phase 2a: Recipe Foundation (promotion pipeline)."""
    _header("Phase 2a: Recipe Foundation")

    mined = _make_mined_templates()
    _subheader("Input: Mined Templates")
    for t in mined:
        _kv(f"  {t.template_id}", f"family={t.effect_family}, support={t.support_count}, stability={t.cross_pack_stability:.2f}")

    _subheader("Promotion Pipeline")
    result = PromotionPipeline().run(
        candidates=mined,
        min_support=5,
        min_stability=0.3,
    )
    _kv("Total candidates", result.report["total_candidates"])
    _kv("Rejected (quality gate)", result.report["rejected_count"])
    _kv("Promoted", result.report["promoted_count"])

    _subheader("Promoted Recipes")
    for r in result.promoted_recipes:
        _kv(f"  {r.recipe_id}", f"type={r.template_type.value}, layers={len(r.layers)}, source={r.provenance.source}")
        for layer in r.layers:
            _kv(f"    L{layer.layer_index} {layer.layer_name}", f"{layer.effect_type} ({layer.blend_mode.value}, mix={layer.mix})")

    _subheader("Recipe Catalog (merge builtins + promoted)")
    builtins = _make_builtin_recipes()
    catalog = RecipeCatalog.merge(builtins=builtins, promoted=result.promoted_recipes)
    _kv("Total recipes", len(catalog.recipes))
    _kv("BASE lane", len(catalog.list_by_lane(LaneKind.BASE)))
    _kv("RHYTHM lane", len(catalog.list_by_lane(LaneKind.RHYTHM)))
    _kv("ACCENT lane", len(catalog.list_by_lane(LaneKind.ACCENT)))
    for r in catalog.recipes:
        _kv(f"  {r.recipe_id}", f"{r.name} ({r.provenance.source})")

    print("\nPhase 2a complete.")
    return {"promoted": result.promoted_recipes, "catalog": catalog}


def demo_phase2b(catalog: RecipeCatalog | None = None) -> None:
    """Phase 2b: Recipe Rendering."""
    _header("Phase 2b: Recipe Rendering")

    if catalog is None:
        builtins = _make_builtin_recipes()
        catalog = RecipeCatalog(recipes=builtins)

    renderer = RecipeRenderer()

    for recipe in catalog.recipes:
        _subheader(f"Rendering: {recipe.name} ({recipe.recipe_id})")
        _kv("Layers", len(recipe.layers))

        env = RenderEnvironment(
            energy=0.75,
            density=0.6,
            palette_colors={"primary": "#E53935", "accent": "#43A047"},
        )
        _kv("Environment", f"energy={env.energy}, density={env.density}")
        _kv("Palette", dict(env.palette_colors))

        result = renderer.render(recipe, env)
        _kv("Rendered layers", len(result.layers))
        if result.warnings:
            _kv("Warnings", result.warnings)

        for rl in result.layers:
            _kv(
                f"  L{rl.layer_index} {rl.layer_name}",
                f"{rl.effect_type} | color={rl.resolved_color} | blend={rl.blend_mode.value} | mix={rl.mix}",
            )
            if rl.resolved_params:
                for pk, pv in rl.resolved_params.items():
                    _kv(f"    param {pk}", pv)

    print("\nPhase 2b complete.")


def demo_phase2c(catalog: RecipeCatalog | None = None) -> None:
    """Phase 2c: Style Transfer & Extensions."""
    _header("Phase 2c: Style Transfer & Extensions")

    if catalog is None:
        builtins = _make_builtin_recipes()
        catalog = RecipeCatalog(recipes=builtins)

    style = _make_style_fingerprint()

    # Style-weighted retrieval
    _subheader("Style-Weighted Retrieval")
    retrieval = StyleWeightedRetrieval()
    scored = retrieval.rank(catalog, style)
    for i, sr in enumerate(scored):
        _kv(f"  #{i + 1} {sr.recipe.recipe_id}", f"score={sr.score:.3f}")
        for dim, val in sr.breakdown.items():
            _kv(f"    {dim}", f"{val:.3f}")

    _kv("Top-1", scored[0].recipe.name if scored else "N/A")

    # Style blend
    _subheader("Style Blend (base + accent)")
    accent = StyleFingerprint(
        creator_id="accent_creator",
        recipe_preferences={"fire": 0.9, "meteor": 0.7},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=50.0, overlap_tendency=0.6, variety_score=0.8
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.8, contrast_preference=0.9, temperature_preference=0.9
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.9, density_preference=0.8, section_change_aggression=0.7
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=3.0, max_layers=6, blend_mode_preference="screen"
        ),
        corpus_sequence_count=8,
    )

    blend_spec = StyleBlend(
        base_style=style,
        accent_style=accent,
        blend_ratio=0.3,
    )

    evaluator = StyleBlendEvaluator()
    blended = evaluator.evaluate(blend_spec)
    _kv("Base creator", style.creator_id)
    _kv("Accent creator", accent.creator_id)
    _kv("Blend ratio", blend_spec.blend_ratio)
    _kv("Blended layering mean", f"{blended.layering_style.mean_layers:.2f}")
    _kv("Blended density pref", f"{blended.timing_style.density_preference:.2f}")
    _kv("Blended contrast pref", f"{blended.color_tendencies.contrast_preference:.2f}")

    # Style evolution
    _subheader("Style Evolution")
    for direction in ["warmer", "cooler", "more_complex", "simpler"]:
        evolution = StyleEvolution(direction=direction, intensity=0.5)
        evo_blend = StyleBlend(base_style=style, blend_ratio=0.0, evolution_params=evolution)
        evolved = evaluator.evaluate(evo_blend)
        _kv(f"  {direction} (0.5)", f"temp={evolved.color_tendencies.temperature_preference:.2f}, complexity-proxy=layering_mean={evolved.layering_style.mean_layers:.2f}")

    # Motif compatibility
    _subheader("Motif Compatibility")
    for recipe in catalog.recipes:
        if recipe.motif_compatibility:
            _kv(f"  {recipe.recipe_id}", f"{len(recipe.motif_compatibility)} motif scores")
            for mc in recipe.motif_compatibility:
                _kv(f"    {mc.motif_id}", f"score={mc.score:.2f} ({mc.reason})")
        else:
            _kv(f"  {recipe.recipe_id}", "no motif scores")

    print("\nPhase 2c complete.")


# ===================================================================
# Main
# ===================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo the FE-to-Recipes pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--phase",
        choices=["1", "2a", "2b", "2c", "all"],
        default="all",
        help="Which phase to demo (default: all).",
    )
    args = parser.parse_args()

    catalog = None

    if args.phase in ("1", "all"):
        demo_phase1()

    if args.phase in ("2a", "all"):
        result = demo_phase2a()
        catalog = result["catalog"]

    if args.phase in ("2b", "all"):
        demo_phase2b(catalog)

    if args.phase in ("2c", "all"):
        demo_phase2c(catalog)

    if args.phase == "all":
        _header("ALL PHASES COMPLETE")
        print("  The FE-to-Recipes pipeline is working end-to-end.")
        print("  Run individual phases with --phase 1/2a/2b/2c for detailed inspection.")


if __name__ == "__main__":
    main()
