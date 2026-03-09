"""Catalog analysis and opportunity identification for recipe_builder.

Loads the existing recipe catalog, analyzes distributions across every
dimension, and identifies specific creative opportunities where new
recipes would add the most value.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from twinklr.core.recipe_builder.models import (
    CatalogAnalysis,
    DistributionEntry,
    Opportunity,
)
from twinklr.core.sequencer.templates.group.recipe import EffectRecipe
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.templates.group.store import TemplateStore
from twinklr.core.sequencer.vocabulary import (
    EnergyTarget,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
)

logger = logging.getLogger(__name__)

# All xLights effect types used in existing templates
ALL_EFFECT_TYPES = frozenset(
    {
        "Color Wash",
        "Twinkle",
        "Fire",
        "Spirals",
        "Meteors",
        "Fan",
        "Shockwave",
        "Strobe",
        "Snowflakes",
        "Marquee",
        "SingleStrand",
        "Ripple",
        "Pinwheel",
        "On",
        "Morph",
        "Butterfly",
        "Galaxy",
        "Plasma",
        "Lightning",
        "Wave",
        "Bars",
    }
)

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "data" / "templates"


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


def load_catalog(templates_dir: Path | None = None) -> list[EffectRecipe]:
    """Load all recipes from the template store.

    Args:
        templates_dir: Path to templates directory with index.json.
            Defaults to data/templates/ in the repo root.

    Returns:
        List of all EffectRecipe instances from the catalog.
    """
    directory = templates_dir or DEFAULT_TEMPLATES_DIR
    if not directory.exists():
        logger.warning("Templates directory not found: %s", directory)
        return []

    store = TemplateStore.from_directory(directory)
    catalog = RecipeCatalog.from_store(store)
    recipes = catalog.recipes
    logger.info("Loaded %d recipes from %s", len(recipes), directory)
    return recipes


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------


def _distribution(counts: Counter[str], total: int) -> list[DistributionEntry]:
    """Build sorted DistributionEntry list from a Counter."""
    return sorted(
        [
            DistributionEntry(
                name=name,
                count=count,
                percentage=round(100.0 * count / total, 1) if total > 0 else 0.0,
            )
            for name, count in counts.items()
        ],
        key=lambda e: (-e.count, e.name),
    )


def _all_enum_distribution(
    counts: Counter[str],
    all_values: list[str],
    total: int,
) -> list[DistributionEntry]:
    """Distribution including zero-count entries for all known values."""
    for val in all_values:
        if val not in counts:
            counts[val] = 0
    return _distribution(counts, total)


# ---------------------------------------------------------------------------
# Catalog analysis
# ---------------------------------------------------------------------------


def analyze_catalog(recipes: list[EffectRecipe]) -> CatalogAnalysis:
    """Analyze the recipe catalog across all dimensions.

    Computes distributions for effect types, energies, template types,
    motion verbs, visual intents, color modes, layer counts, and effect
    families. Identifies underutilized primitives and missing combinations.

    Args:
        recipes: All recipes in the catalog.

    Returns:
        CatalogAnalysis with full distribution data and gap identification.
    """
    now = datetime.now(UTC)
    total = len(recipes)

    if total == 0:
        return CatalogAnalysis(
            generated_at=now,
            total_recipes=0,
            summary="Empty catalog — every recipe type is an opportunity.",
        )

    # Gather counts
    effect_types: Counter[str] = Counter()
    energies: Counter[str] = Counter()
    template_types: Counter[str] = Counter()
    motion_verbs: Counter[str] = Counter()
    visual_intents: Counter[str] = Counter()
    color_modes: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    effect_families: Counter[str] = Counter()

    # Track effect_type × energy combinations
    effect_energy_combos: set[tuple[str, str]] = set()

    for recipe in recipes:
        energies[recipe.style_markers.energy_affinity.value] += 1
        template_types[recipe.template_type.value] += 1
        visual_intents[recipe.visual_intent.value] += 1
        color_modes[recipe.palette_spec.mode.value] += 1
        layer_counts[str(len(recipe.layers))] += 1
        effect_families[recipe.effect_family] += 1

        for layer in recipe.layers:
            effect_types[layer.effect_type] += 1
            for mv in layer.motion:
                motion_verbs[mv.value] += 1
            effect_energy_combos.add(
                (layer.effect_type, recipe.style_markers.energy_affinity.value),
            )

    # Identify underutilized
    all_motions = [mv.value for mv in MotionVerb if mv != MotionVerb.NONE]
    underutilized_motions = [
        m for m in all_motions if motion_verbs.get(m, 0) <= 2
    ]

    underutilized_effects = [
        e for e in ALL_EFFECT_TYPES if effect_types.get(e, 0) <= 1
    ]

    # Missing effect × energy combos (for effects that exist in catalog)
    all_energy_vals = [e.value for e in EnergyTarget if e in (EnergyTarget.LOW, EnergyTarget.MED, EnergyTarget.HIGH)]
    used_effects = {et for et in effect_types if effect_types[et] >= 2}
    missing_combos: list[str] = []
    for effect in sorted(used_effects):
        for energy in all_energy_vals:
            if (effect, energy) not in effect_energy_combos:
                missing_combos.append(f"{effect} × {energy}")

    # Build distributions
    effect_type_dist = _distribution(effect_types, total)
    energy_dist = _all_enum_distribution(
        energies,
        [e.value for e in EnergyTarget],
        total,
    )
    template_type_dist = _all_enum_distribution(
        template_types,
        [t.value for t in GroupTemplateType],
        total,
    )
    motion_dist = _all_enum_distribution(
        motion_verbs,
        all_motions,
        total,
    )
    visual_intent_dist = _all_enum_distribution(
        visual_intents,
        [vi.value for vi in GroupVisualIntent],
        total,
    )

    # Summary text
    top_effects = ", ".join(f"{e.name}({e.count})" for e in effect_type_dist[:3])
    top_energies = ", ".join(f"{e.name}({e.count})" for e in energy_dist[:3])
    summary_lines = [
        f"{total} recipes in catalog.",
        f"Top effects: {top_effects}.",
        f"Energy distribution: {top_energies}.",
        f"{len(underutilized_effects)} underutilized effects: {', '.join(sorted(underutilized_effects)[:5])}.",
        f"{len(underutilized_motions)} underutilized motions: {', '.join(sorted(underutilized_motions)[:5])}.",
        f"{len(missing_combos)} missing effect×energy combinations.",
    ]

    return CatalogAnalysis(
        generated_at=now,
        total_recipes=total,
        effect_type_distribution=effect_type_dist,
        energy_distribution=energy_dist,
        template_type_distribution=template_type_dist,
        motion_verb_usage=motion_dist,
        visual_intent_distribution=visual_intent_dist,
        color_mode_distribution=_distribution(color_modes, total),
        layer_count_distribution=_distribution(layer_counts, total),
        effect_family_distribution=_distribution(effect_families, total),
        underutilized_effects=sorted(underutilized_effects),
        underutilized_motions=sorted(underutilized_motions),
        missing_energy_combos=missing_combos,
        summary="\n".join(summary_lines),
    )


# ---------------------------------------------------------------------------
# Opportunity identification
# ---------------------------------------------------------------------------


def _opp_id() -> str:
    return f"opp_{uuid.uuid4().hex[:10]}"


def identify_opportunities(
    analysis: CatalogAnalysis,
    max_opportunities: int = 10,
) -> list[Opportunity]:
    """Identify creative opportunities from catalog analysis.

    Scans distributions and gaps to produce ranked opportunities
    for new recipe generation. Each opportunity describes a specific
    creative direction the LLM should explore.

    Args:
        analysis: Completed catalog analysis.
        max_opportunities: Maximum number of opportunities to return.

    Returns:
        Sorted list of Opportunity instances (highest priority first).
    """
    opportunities: list[Opportunity] = []

    # 1. Missing or underutilized effect types
    for effect in analysis.underutilized_effects:
        count = next(
            (e.count for e in analysis.effect_type_distribution if e.name == effect),
            0,
        )
        priority = 0.9 if count == 0 else 0.7
        opportunities.append(
            Opportunity(
                opportunity_id=_opp_id(),
                category="missing_effect_type",
                description=(
                    f"Effect type '{effect}' has only {count} recipe(s). "
                    f"Create a recipe showcasing {effect} as the primary visual."
                ),
                priority=priority,
                target_effect_type=effect,
                context=f"This effect is {'completely absent' if count == 0 else 'rarely used'} in the catalog.",
            ),
        )

    # 2. Missing effect × energy combinations
    for combo in analysis.missing_energy_combos[:8]:
        parts = combo.split(" × ")
        if len(parts) == 2:
            effect, energy = parts
            opportunities.append(
                Opportunity(
                    opportunity_id=_opp_id(),
                    category="missing_energy_variant",
                    description=(
                        f"No recipe combines {effect} with {energy} energy. "
                        f"Create a {energy.lower()}-energy {effect} recipe."
                    ),
                    priority=0.75,
                    target_effect_type=effect,
                    target_energy=energy,
                    context=f"Existing {effect} recipes cover other energy levels but not {energy}.",
                ),
            )

    # 3. Underutilized motion verbs
    for motion in analysis.underutilized_motions[:4]:
        count = next(
            (e.count for e in analysis.motion_verb_usage if e.name == motion),
            0,
        )
        opportunities.append(
            Opportunity(
                opportunity_id=_opp_id(),
                category="underutilized_motion",
                description=(
                    f"Motion verb '{motion}' is used in only {count} recipe(s). "
                    f"Create a recipe that prominently features {motion} motion."
                ),
                priority=0.65,
                target_motions=[motion],
                context=f"Explore how {motion} motion creates visual interest.",
            ),
        )

    # 4. Template type gaps (under-represented types)
    for entry in analysis.template_type_distribution:
        if entry.percentage < 10.0 and entry.name not in ("SPECIAL",):
            opportunities.append(
                Opportunity(
                    opportunity_id=_opp_id(),
                    category="missing_template_type",
                    description=(
                        f"Template type '{entry.name}' is underrepresented "
                        f"({entry.count} recipes, {entry.percentage}%). "
                        f"Create a {entry.name} recipe."
                    ),
                    priority=0.6,
                    target_template_type=entry.name,
                    context=f"The catalog needs more {entry.name} templates for balanced sequencing.",
                ),
            )

    # 5. Visual intent diversity
    for entry in analysis.visual_intent_distribution:
        if entry.count == 0:
            opportunities.append(
                Opportunity(
                    opportunity_id=_opp_id(),
                    category="missing_visual_intent",
                    description=(
                        f"No recipes with visual intent '{entry.name}'. "
                        f"Create a recipe with {entry.name} visual character."
                    ),
                    priority=0.55,
                    context=f"Visual intent {entry.name} is completely unrepresented.",
                ),
            )

    # 6. Layer composition diversity
    multi_layer_count = sum(
        e.count
        for e in analysis.layer_count_distribution
        if e.name not in ("0", "1")
    )
    single_layer_count = next(
        (e.count for e in analysis.layer_count_distribution if e.name == "1"),
        0,
    )
    if analysis.total_recipes > 0 and multi_layer_count < analysis.total_recipes * 0.3:
        opportunities.append(
            Opportunity(
                opportunity_id=_opp_id(),
                category="low_layer_diversity",
                description=(
                    f"Only {multi_layer_count} of {analysis.total_recipes} recipes "
                    f"use multiple layers ({single_layer_count} are single-layer). "
                    f"Create a multi-layer recipe with 2-3 layers for visual depth."
                ),
                priority=0.7,
                context=(
                    "Multi-layer recipes create richer visuals by combining "
                    "background, midground, and foreground effects with different "
                    "blend modes and densities."
                ),
            ),
        )

    # 7. General diversity — if catalog is small, encourage variety
    if analysis.total_recipes < 20:
        opportunities.append(
            Opportunity(
                opportunity_id=_opp_id(),
                category="general_diversity",
                description=(
                    f"Small catalog ({analysis.total_recipes} recipes). "
                    f"Create a visually unique recipe using an uncommon effect "
                    f"and motion combination."
                ),
                priority=0.5,
                context="With a small catalog, any creative addition adds value.",
            ),
        )

    # Sort by priority and cap
    opportunities.sort(key=lambda o: (-o.priority, o.opportunity_id))
    return opportunities[:max_opportunities]


def format_analysis_for_prompt(analysis: CatalogAnalysis) -> str:
    """Format catalog analysis as a concise text summary for LLM prompts.

    Args:
        analysis: Completed catalog analysis.

    Returns:
        Human-readable summary suitable for inclusion in an LLM prompt.
    """
    lines: list[str] = [
        f"Catalog: {analysis.total_recipes} recipes total",
        "",
        "Effect type usage (layer count across all recipes):",
    ]
    for entry in analysis.effect_type_distribution:
        bar = "█" * max(1, int(entry.percentage / 5))
        lines.append(f"  {entry.name:<16} {entry.count:>3}  {bar}")

    lines.append("")
    lines.append("Energy distribution:")
    for entry in analysis.energy_distribution:
        if entry.count > 0:
            lines.append(f"  {entry.name:<10} {entry.count:>3} ({entry.percentage:.0f}%)")

    lines.append("")
    lines.append("Template types:")
    for entry in analysis.template_type_distribution:
        lines.append(f"  {entry.name:<12} {entry.count:>3} ({entry.percentage:.0f}%)")

    if analysis.underutilized_effects:
        lines.append("")
        lines.append(f"Underutilized effects (≤1 recipe): {', '.join(analysis.underutilized_effects)}")

    if analysis.underutilized_motions:
        lines.append("")
        lines.append(f"Underutilized motions (≤2 uses): {', '.join(analysis.underutilized_motions)}")

    if analysis.missing_energy_combos:
        lines.append("")
        lines.append(f"Missing effect×energy combos: {', '.join(analysis.missing_energy_combos[:8])}")

    return "\n".join(lines)
