#!/usr/bin/env python3
"""Demo script for the FE-to-Recipes pipeline.

Exercises each phase of the recipe pipeline, printing human-readable
summaries at each stage. By default uses synthetic data; pass
``--load-fe-data`` to load real artifacts from a feature engineering run.

Usage:
    uv run python scripts/demo_recipe_pipeline.py --phase all
    uv run python scripts/demo_recipe_pipeline.py --phase 1
    uv run python scripts/demo_recipe_pipeline.py --phase 2a
    uv run python scripts/demo_recipe_pipeline.py --phase 2b
    uv run python scripts/demo_recipe_pipeline.py --phase 2c

    # Load real FE data (default path):
    uv run python scripts/demo_recipe_pipeline.py --load-fe-data --phase all

    # Load real FE data (custom path):
    uv run python scripts/demo_recipe_pipeline.py --load-fe-data data/features/my_run --phase 2a
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

from twinklr.core.feature_engineering.models.clustering import TemplateClusterCatalog

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
from twinklr.core.feature_engineering.models.motifs import MotifCatalog
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
from twinklr.core.feature_engineering.models.templates import (
    TemplateCatalog as FETemplateCatalog,
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


def _scope_clusters_to_candidates(
    cluster_catalog: TemplateClusterCatalog | None,
    candidates: list[MinedTemplate],
) -> list[dict[str, Any]] | None:
    """Build same-family cluster dedup specs scoped to *candidates*.

    The raw cluster catalog merges templates across effect families
    (the vectorization hashes family names into float buckets that
    can collide).  For recipe promotion we only want to deduplicate
    within the same ``effect_family`` — e.g. two ``single_strand``
    variants are genuine duplicates, but ``spirals`` and ``bars``
    are not.

    Algorithm:
      1. Scope each cluster's members to only IDs in *candidates*.
      2. Sub-partition the scoped members by ``effect_family``.
      3. Emit one dedup spec per sub-group with 2+ members,
         keeping the highest-support member as representative.
    """
    if cluster_catalog is None:
        return None

    candidate_by_id = {t.template_id: t for t in candidates}
    scoped: list[dict[str, Any]] = []

    for c in cluster_catalog.clusters:
        members_in_scope = [
            candidate_by_id[mid] for mid in c.member_template_ids if mid in candidate_by_id
        ]
        if len(members_in_scope) < 2:
            continue

        by_family: dict[str, list[MinedTemplate]] = {}
        for t in members_in_scope:
            by_family.setdefault(t.effect_family, []).append(t)

        for family, group in by_family.items():
            if len(group) < 2:
                continue
            ranked = sorted(group, key=lambda t: -t.support_count)
            scoped.append(
                {
                    "cluster_id": f"{c.cluster_id}:{family}",
                    "member_ids": [t.template_id for t in ranked],
                    "keep_id": ranked[0].template_id,
                }
            )

    return scoped if scoped else None


# ===================================================================
# FE data loader
# ===================================================================

_DEFAULT_FE_DIR = Path("data/features/feature_engineering")

_FE_FILES = {
    "color_arc": "color_arc.json",
    "propensity": "propensity_index.json",
    "style": "style_fingerprint.json",
    "content_templates": "content_templates.json",
}

_FE_OPTIONAL_FILES = {
    "motif_catalog": "motif_catalog.json",
    "cluster_candidates": "cluster_candidates.json",
}


@dataclass
class FEData:
    """Container for loaded (or synthetic) feature engineering artifacts."""

    color_arc: SongColorArc
    propensity: PropensityIndex
    style: StyleFingerprint
    mined_templates: list[MinedTemplate]
    motif_catalog: MotifCatalog | None
    cluster_catalog: TemplateClusterCatalog | None
    source: str  # "synthetic" or the directory path


def load_fe_data(fe_dir: Path) -> FEData:
    """Load real FE artifacts from *fe_dir*.

    Reads color_arc.json, propensity_index.json, style_fingerprint.json,
    and content_templates.json, deserialising each via Pydantic
    ``model_validate_json``.

    Args:
        fe_dir: Root directory of a feature engineering run.

    Returns:
        Populated FEData with real artifacts.

    Raises:
        SystemExit: If any required file is missing.
    """
    missing = [name for name, fname in _FE_FILES.items() if not (fe_dir / fname).exists()]
    if missing:
        print(f"ERROR: Missing FE artifacts in {fe_dir}:")
        for name in missing:
            print(f"  - {_FE_FILES[name]}")
        sys.exit(1)

    _header(f"Loading FE data from {fe_dir}")

    color_arc = SongColorArc.model_validate_json(
        (fe_dir / _FE_FILES["color_arc"]).read_text(encoding="utf-8")
    )
    _kv("Color Arc palettes", len(color_arc.palette_library))
    _kv("Color Arc sections", len(color_arc.section_assignments))

    propensity = PropensityIndex.model_validate_json(
        (fe_dir / _FE_FILES["propensity"]).read_text(encoding="utf-8")
    )
    _kv("Propensity affinities", len(propensity.affinities))

    style = StyleFingerprint.model_validate_json(
        (fe_dir / _FE_FILES["style"]).read_text(encoding="utf-8")
    )
    _kv("Style creator", style.creator_id)
    _kv("Style corpus sequences", style.corpus_sequence_count)

    catalog = FETemplateCatalog.model_validate_json(
        (fe_dir / _FE_FILES["content_templates"]).read_text(encoding="utf-8")
    )
    _kv("Content templates", len(catalog.templates))
    _kv("Assignment coverage", f"{catalog.assignment_coverage:.1%}")

    motif_catalog: MotifCatalog | None = None
    motif_path = fe_dir / _FE_OPTIONAL_FILES["motif_catalog"]
    if motif_path.exists():
        motif_catalog = MotifCatalog.model_validate_json(motif_path.read_text(encoding="utf-8"))
        _kv("Motif catalog", f"{motif_catalog.total_motifs} motifs")
    else:
        _kv("Motif catalog", "not found (motif annotation will be skipped)")

    cluster_catalog: TemplateClusterCatalog | None = None
    cluster_path = fe_dir / _FE_OPTIONAL_FILES["cluster_candidates"]
    if cluster_path.exists():
        cluster_catalog = TemplateClusterCatalog.model_validate_json(
            cluster_path.read_text(encoding="utf-8")
        )
        _kv(
            "Cluster catalog",
            f"{cluster_catalog.total_clusters} clusters "
            f"({cluster_catalog.total_templates} templates, "
            f"threshold={cluster_catalog.similarity_threshold})",
        )
    else:
        _kv("Cluster catalog", "not found (cluster dedup will be skipped)")

    print()
    return FEData(
        color_arc=color_arc,
        propensity=propensity,
        style=style,
        mined_templates=list(catalog.templates),
        motif_catalog=motif_catalog,
        cluster_catalog=cluster_catalog,
        source=str(fe_dir),
    )


def _make_synthetic_data() -> FEData:
    """Build the default synthetic FEData for demo purposes."""
    return FEData(
        color_arc=_make_color_arc(),
        propensity=_make_propensity_index(),
        style=_make_style_fingerprint(),
        mined_templates=_make_mined_templates(),
        motif_catalog=None,
        cluster_catalog=None,
        source="synthetic",
    )


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
            EffectModelAffinity(
                effect_family="shimmer",
                model_type="MegaTree",
                frequency=0.85,
                exclusivity=0.6,
                corpus_support=25,
            ),
            EffectModelAffinity(
                effect_family="color_wash",
                model_type="Arch",
                frequency=0.62,
                exclusivity=0.4,
                corpus_support=18,
            ),
            EffectModelAffinity(
                effect_family="fire",
                model_type="Matrix",
                frequency=0.78,
                exclusivity=0.7,
                corpus_support=22,
            ),
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
        # Multi-layer stack template (discovered from xLights sequence analysis)
        MinedTemplate(
            template_id="tpl_candy_cane_stack_004",
            template_kind=TemplateKind.CONTENT,
            template_signature="color_wash@normal+bars@add+sparkle@screen|sweep|palette|high|sustained|multi_target|",
            support_count=15,
            distinct_pack_count=4,
            support_ratio=0.30,
            cross_pack_stability=0.60,
            effect_family="color_wash",
            motion_class="sweep",
            color_class="palette",
            energy_class="high",
            continuity_class="sustained",
            spatial_class="multi_target",
            layer_count=3,
            stack_composition=("color_wash", "bars", "sparkle"),
            layer_blend_modes=("NORMAL", "ADD", "SCREEN"),
            layer_mixes=(1.0, 0.7, 0.45),
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
            style_markers=StyleMarkers(complexity=0.2, energy_affinity=EnergyTarget.LOW),
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


def demo_phase1(fe: FEData) -> None:
    """Phase 1: Context Enrichment artifacts."""
    _header(f"Phase 1: Context Enrichment  [source: {fe.source}]")

    # Color Arc
    _subheader("Color Arc Engine")
    arc = fe.color_arc
    _kv("Palettes", len(arc.palette_library))
    for p in arc.palette_library:
        _kv(f"  {p.name}", f"{p.colors} ({p.temperature})")
    _kv("Section assignments", len(arc.section_assignments))
    for a in arc.section_assignments:
        _kv(
            f"  [{a.section_index}] {a.section_label}",
            f"palette={a.palette_id}, contrast={a.contrast_target}",
        )
    _kv("Arc keyframes", len(arc.arc_curve))
    for k in arc.arc_curve:
        _kv(
            f"  {k.position_pct:.0%}",
            f"temp={k.temperature}, sat={k.saturation}, contrast={k.contrast}",
        )
    _kv("Transition rules", len(arc.transition_rules))
    for r in arc.transition_rules:
        _kv(
            f"  {r.from_palette_id} -> {r.to_palette_id}",
            f"{r.transition_style} ({r.duration_bars} bars)",
        )

    # Propensity
    _subheader("Propensity Miner")
    prop = fe.propensity
    _kv("Model affinities", len(prop.affinities))
    for a in prop.affinities:
        _kv(
            f"  {a.model_type}",
            f"family={a.effect_family}, freq={a.frequency:.2f}, excl={a.exclusivity:.2f}",
        )

    # Style Fingerprint
    _subheader("Style Fingerprint")
    style = fe.style
    _kv("Creator", style.creator_id)
    _kv("Corpus sequences", style.corpus_sequence_count)
    _kv("Recipe preferences", dict(style.recipe_preferences))
    _kv(
        "Layering",
        f"mean={style.layering_style.mean_layers}, max={style.layering_style.max_layers}",
    )
    _kv("Timing density", f"{style.timing_style.density_preference:.2f}")
    _kv("Color contrast pref", f"{style.color_tendencies.contrast_preference:.2f}")

    print("\nPhase 1 complete.")


def demo_phase2a(fe: FEData) -> RecipeCatalog:
    """Phase 2a: Recipe Foundation (promotion pipeline)."""
    _header(f"Phase 2a: Recipe Foundation  [source: {fe.source}]")

    mined = fe.mined_templates
    _subheader(f"Input: Mined Templates ({len(mined)} total)")
    for t in mined[:10]:
        _kv(
            f"  {t.template_id}",
            f"family={t.effect_family}, support={t.support_count}, stability={t.cross_pack_stability:.2f}",
        )
    if len(mined) > 10:
        _kv("  ...", f"({len(mined) - 10} more)")

    clusters = _scope_clusters_to_candidates(fe.cluster_catalog, mined)
    if clusters is not None:
        dedup_removals = sum(len(c["member_ids"]) - 1 for c in clusters)
        _subheader(f"Cluster Dedup ({len(clusters)} clusters scoped to {len(mined)} candidates)")
        _kv("Effective clusters", len(clusters))
        _kv("Duplicate members to remove", dedup_removals)
    else:
        _subheader("Cluster Dedup (skipped — no cluster catalog)")

    _subheader("Promotion Pipeline (stack-aware)")
    has_stacks = any(t.stack_composition for t in mined)
    result = PromotionPipeline().run(
        candidates=mined,
        min_support=5,
        min_stability=0.3,
        clusters=clusters,
        motif_catalog=fe.motif_catalog,
        propensity_index=fe.propensity,
        use_stack_synthesis=has_stacks,
    )
    _kv("Total candidates", result.report["total_candidates"])
    _kv("Filtered (excluded families)", result.report.get("filtered_families", 0))
    _kv("Rejected (quality gate)", result.report["rejected_count"])
    _kv("Cluster deduped", f"yes ({len(clusters)} clusters)" if clusters else "no")
    _kv("Promoted", result.report["promoted_count"])
    _kv("Affinities enriched", result.report.get("affinities_enriched", 0))
    _kv("Motif-annotated", result.report.get("motifs_annotated", 0))
    _kv("Stack-aware synthesis", "yes" if has_stacks else "no (legacy)")

    _subheader("Promoted Recipes")
    for r in result.promoted_recipes[:15]:
        _kv(
            f"  {r.recipe_id}",
            f"type={r.template_type.value}, layers={len(r.layers)}, source={r.provenance.source}",
        )
        for layer in r.layers:
            _kv(
                f"    L{layer.layer_index} {layer.layer_name}",
                f"{layer.effect_type} ({layer.blend_mode.value}, mix={layer.mix})",
            )
    if len(result.promoted_recipes) > 15:
        _kv("  ...", f"({len(result.promoted_recipes) - 15} more)")

    _subheader("Recipe Catalog (merge builtins + promoted)")
    builtins = _make_builtin_recipes()
    catalog = RecipeCatalog.merge(builtins=builtins, promoted=result.promoted_recipes)
    _kv("Total recipes", len(catalog.recipes))
    _kv("BASE lane", len(catalog.list_by_lane(LaneKind.BASE)))
    _kv("RHYTHM lane", len(catalog.list_by_lane(LaneKind.RHYTHM)))
    _kv("ACCENT lane", len(catalog.list_by_lane(LaneKind.ACCENT)))
    for r in catalog.recipes[:20]:
        _kv(f"  {r.recipe_id}", f"{r.name} ({r.provenance.source})")
    if len(catalog.recipes) > 20:
        _kv("  ...", f"({len(catalog.recipes) - 20} more)")

    print("\nPhase 2a complete.")
    return catalog


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


def demo_phase2c(fe: FEData, catalog: RecipeCatalog | None = None) -> None:
    """Phase 2c: Style Transfer & Extensions."""
    _header(f"Phase 2c: Style Transfer & Extensions  [source: {fe.source}]")

    if catalog is None:
        builtins = _make_builtin_recipes()
        catalog = RecipeCatalog(recipes=builtins)

    style = fe.style

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
        _kv(
            f"  {direction} (0.5)",
            f"temp={evolved.color_tendencies.temperature_preference:.2f}, complexity-proxy=layering_mean={evolved.layering_style.mean_layers:.2f}",
        )

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
    parser.add_argument(
        "--load-fe-data",
        nargs="?",
        const=str(_DEFAULT_FE_DIR),
        default=None,
        metavar="DIR",
        help=(
            "Load real FE artifacts instead of synthetic data. "
            f"Optional DIR argument (default: {_DEFAULT_FE_DIR})."
        ),
    )
    args = parser.parse_args()

    if args.load_fe_data is not None:
        fe = load_fe_data(Path(args.load_fe_data))
    else:
        fe = _make_synthetic_data()

    catalog = None

    if args.phase in ("1", "all"):
        demo_phase1(fe)

    if args.phase in ("2a", "all"):
        catalog = demo_phase2a(fe)

    if args.phase in ("2b", "all"):
        demo_phase2b(catalog)

    if args.phase in ("2c", "all"):
        demo_phase2c(fe, catalog)

    if args.phase == "all":
        _header("ALL PHASES COMPLETE")
        source_label = fe.source
        print(f"  Data source: {source_label}")
        print("  The FE-to-Recipes pipeline is working end-to-end.")
        print("  Run individual phases with --phase 1/2a/2b/2c for detailed inspection.")


if __name__ == "__main__":
    main()
