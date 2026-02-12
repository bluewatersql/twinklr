"""Deterministic asset request extraction from GroupPlanSet.

Dual-source extraction:
1. Effect assets — walks motif_ids to produce abstract pattern assets.
2. Narrative assets — converts NarrativeAssetDirective[] to figurative/story assets.
3. Text assets — song title banner.

No LLM involved — purely deterministic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from twinklr.core.agents.assets.models import AssetCategory, AssetSpec
from twinklr.core.agents.audio.lyrics.models import LyricContextModel
from twinklr.core.sequencer.planning.group_plan import GroupPlanSet
from twinklr.core.sequencer.theming.catalog import PALETTE_REGISTRY
from twinklr.core.sequencer.vocabulary import BackgroundMode

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role → Category mapping
# ---------------------------------------------------------------------------

# Roles that map to IMAGE_TEXTURE (tileable, opaque, for LED matrix projection)
_TEXTURE_ROLES = {"MEGA_TREE", "MATRIX"}

# Roles that map to IMAGE_CUTOUT (transparent overlays)
_CUTOUT_ROLES = {"HERO", "WINDOWS"}

# Mapping from role to category for quick lookup
ROLE_CATEGORY_MAP: dict[str, AssetCategory] = {}
for _role in _TEXTURE_ROLES:
    ROLE_CATEGORY_MAP[_role] = AssetCategory.IMAGE_TEXTURE
for _role in _CUTOUT_ROLES:
    ROLE_CATEGORY_MAP[_role] = AssetCategory.IMAGE_CUTOUT


# ---------------------------------------------------------------------------
# Intermediate data
# ---------------------------------------------------------------------------


@dataclass
class MotifContext:
    """Accumulated context for a single motif across sections.

    Attributes:
        motif_id: The motif identifier.
        theme_ids: All themes that reference this motif.
        palette_ids: All palettes associated with this motif.
        section_ids: Which sections reference this motif.
        target_roles: Which display roles the motif appears on.
        scene_context: Planning notes from sections (mood/intent context).
    """

    motif_id: str
    theme_ids: set[str] = field(default_factory=set)
    palette_ids: set[str] = field(default_factory=set)
    section_ids: set[str] = field(default_factory=set)
    target_roles: set[str] = field(default_factory=set)
    scene_context: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 1: Collect motif contexts
# ---------------------------------------------------------------------------


def _collect_motif_contexts(
    plan_set: GroupPlanSet,
    lyric_context: LyricContextModel | None = None,
) -> dict[str, MotifContext]:
    """Walk the plan and collect context for each unique motif.

    Args:
        plan_set: The complete aggregated plan.
        lyric_context: Optional lyric context for narrative enrichment.

    Returns:
        Dict mapping motif_id → MotifContext.
    """
    contexts: dict[str, MotifContext] = {}

    for section in plan_set.section_plans:
        theme_id = section.theme.theme_id
        palette_id = section.palette.palette_id if section.palette else None
        section_id = section.section_id

        # Collect target roles from all lane plans
        section_roles: set[str] = set()
        for lane_plan in section.lane_plans:
            section_roles.update(lane_plan.target_roles)

        # Collect motif_hints from param_overrides in placements
        override_motifs: set[str] = set()
        for lane_plan in section.lane_plans:
            for coord_plan in lane_plan.coordination_plans:
                for placement in coord_plan.placements:
                    hints = placement.param_overrides.get("motif_hint", [])
                    if isinstance(hints, list):
                        override_motifs.update(hints)

        # Union declared motifs with override motifs
        all_motifs = set(section.motif_ids) | override_motifs

        for motif_id in all_motifs:
            if motif_id not in contexts:
                contexts[motif_id] = MotifContext(motif_id=motif_id)

            ctx = contexts[motif_id]
            ctx.theme_ids.add(theme_id)
            if palette_id:
                ctx.palette_ids.add(palette_id)
            ctx.section_ids.add(section_id)
            ctx.target_roles.update(section_roles)

            # Add planning notes as scene context
            if section.planning_notes:
                ctx.scene_context.append(section.planning_notes)

    # Enrich with lyric context if available
    if lyric_context and lyric_context.has_lyrics:
        _enrich_with_lyric_context(contexts, lyric_context, plan_set)

    return contexts


def _enrich_with_lyric_context(
    contexts: dict[str, MotifContext],
    lyric_context: LyricContextModel,
    plan_set: GroupPlanSet,
) -> None:
    """Enrich motif contexts with lyric narrative information.

    Appends key phrases and story beats aligned to each motif's sections
    into the scene_context for richer prompt enrichment.

    Args:
        contexts: Motif contexts to enrich (mutated in place).
        lyric_context: Lyric analysis results.
        plan_set: Plan for section time-range lookups.
    """
    # Build section_id set per motif for quick lookup
    for _motif_id, ctx in contexts.items():
        # Add relevant key phrases
        if lyric_context.key_phrases:
            for phrase in lyric_context.key_phrases:
                if phrase.section_id in ctx.section_ids:
                    hint = f'Lyric: "{phrase.text}" [{phrase.emphasis}] — {phrase.visual_hint}'
                    ctx.scene_context.append(hint)

        # Add relevant story beats
        if lyric_context.story_beats:
            for beat in lyric_context.story_beats:
                if beat.section_id in ctx.section_ids:
                    hint = f"Story: [{beat.beat_type}] {beat.description}"
                    if beat.visual_opportunity:
                        hint += f" — visual: {beat.visual_opportunity}"
                    ctx.scene_context.append(hint)


# ---------------------------------------------------------------------------
# Step 2: Determine categories from roles
# ---------------------------------------------------------------------------


def _determine_categories(target_roles: set[str]) -> set[AssetCategory]:
    """Determine which asset categories are needed for a set of target roles.

    When roles span multiple categories (e.g., MEGA_TREE + HERO), produce
    separate categories for each.

    Args:
        target_roles: Display roles that use this motif.

    Returns:
        Set of AssetCategory values.
    """
    categories: set[AssetCategory] = set()

    for role in target_roles:
        cat = ROLE_CATEGORY_MAP.get(role)
        if cat:
            categories.add(cat)

    # Default to IMAGE_CUTOUT if no specific mapping
    if not categories:
        categories.add(AssetCategory.IMAGE_CUTOUT)

    return categories


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_spec_id(motif_id: str, category: AssetCategory) -> str:
    """Build a deterministic spec ID.

    Args:
        motif_id: Motif or asset identifier.
        category: Asset category.

    Returns:
        Spec ID string (e.g., 'asset_image_texture_sparkles').
    """
    return f"asset_{category.value}_{motif_id}"


def _derive_style_tags(theme_id: str) -> list[str]:
    """Derive style tags from a theme ID.

    Args:
        theme_id: Theme identifier (e.g., 'theme.holiday.traditional').

    Returns:
        List of style tags.
    """
    theme_lower = theme_id.lower()

    if "playful" in theme_lower:
        return ["holiday_christmas_playful", "cartoon", "bold_colors"]
    elif "elegant" in theme_lower:
        return ["holiday_christmas_elegant", "silhouette", "soft_pastels"]
    else:
        # Traditional or any unknown theme
        return ["holiday_christmas_traditional", "flat_illustration", "high_contrast"]


def _background_for_category(category: AssetCategory) -> BackgroundMode:
    """Determine background mode for a category.

    Args:
        category: Asset category.

    Returns:
        BackgroundMode (OPAQUE for textures/plates, TRANSPARENT for cutouts/text).
    """
    if category in {AssetCategory.IMAGE_TEXTURE, AssetCategory.IMAGE_PLATE}:
        return BackgroundMode.OPAQUE
    return BackgroundMode.TRANSPARENT


def _roles_for_category(
    category: AssetCategory,
    all_roles: set[str],
) -> list[str]:
    """Filter roles relevant to a specific category.

    Args:
        category: The asset category.
        all_roles: All target roles for this motif.

    Returns:
        Sorted list of roles that map to this category.
    """
    if category == AssetCategory.IMAGE_TEXTURE:
        relevant = all_roles & _TEXTURE_ROLES
    elif category == AssetCategory.IMAGE_CUTOUT:
        relevant = all_roles & _CUTOUT_ROLES
        # Include roles not in any specific mapping
        unmapped = all_roles - _TEXTURE_ROLES - _CUTOUT_ROLES
        relevant = relevant | unmapped
    else:
        relevant = all_roles

    return sorted(relevant) if relevant else sorted(all_roles)


# ---------------------------------------------------------------------------
# Palette resolution
# ---------------------------------------------------------------------------


def _resolve_palette_colors(palette_id: str | None) -> list[dict[str, str]]:
    """Resolve a palette_id to its actual color stops.

    Looks up the palette in the global registry and extracts hex + name
    for each color stop, giving the enricher concrete color targets.

    Args:
        palette_id: Palette identifier (e.g., 'core.christmas_traditional').

    Returns:
        List of color stop dicts: [{"hex": "#E53935", "name": "christmas_red"}, ...].
        Empty list if palette_id is None or not found.
    """
    if not palette_id:
        return []

    try:
        palette_def = PALETTE_REGISTRY.get(palette_id)
        return [
            {"hex": stop.hex, "name": stop.name or "unnamed"}
            for stop in palette_def.stops
        ]
    except Exception:
        logger.debug("Palette '%s' not found in registry", palette_id)
        return []


def _build_song_title(plan_set_id: str) -> str:
    """Derive a human-readable song title from the plan set ID.

    Args:
        plan_set_id: Plan set identifier (e.g., '02_rudolph_the_red_nosed_reindeer').

    Returns:
        Cleaned title string (e.g., 'Rudolph the Red Nosed Reindeer').
    """
    # Strip leading numeric prefix (e.g., "02_")
    cleaned = plan_set_id
    parts = cleaned.split("_", 1)
    if len(parts) > 1 and parts[0].isdigit():
        cleaned = parts[1]
    return cleaned.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Narrative asset extraction
# ---------------------------------------------------------------------------

# Valid narrative directive categories
_NARRATIVE_CATEGORY_MAP: dict[str, AssetCategory] = {
    "image_cutout": AssetCategory.IMAGE_CUTOUT,
    "image_texture": AssetCategory.IMAGE_TEXTURE,
}


def _extract_narrative_specs(
    plan_set: GroupPlanSet,
) -> list[AssetSpec]:
    """Convert aggregated narrative directives into AssetSpecs.

    Each directive maps to one AssetSpec with narrative fields populated.
    The subject and visual_description drive prompt enrichment instead of motif_id.
    Section palette is resolved and attached for color coherence.

    Args:
        plan_set: The complete aggregated plan (provides directives, palettes, song title).

    Returns:
        List of narrative AssetSpec objects.
    """
    directives = plan_set.narrative_assets
    if not directives:
        return []

    # Build section_id → palette lookup for palette cross-referencing
    section_palette_map: dict[str, str | None] = {}
    for section in plan_set.section_plans:
        palette_id = section.palette.palette_id if section.palette else None
        section_palette_map[section.section_id] = palette_id

    song_title = _build_song_title(plan_set.plan_set_id)

    specs: list[AssetSpec] = []
    for directive in directives:
        category = _NARRATIVE_CATEGORY_MAP.get(directive.category)
        if category is None:
            logger.warning(
                "Unknown narrative category '%s' for directive '%s', skipping",
                directive.category,
                directive.directive_id,
            )
            continue

        section_ids = directive.section_ids if directive.section_ids else ["unknown"]

        # Resolve palette from the directive's primary section
        directive_palette: str | None = None
        for sid in section_ids:
            directive_palette = section_palette_map.get(sid)
            if directive_palette:
                break
        palette_colors = _resolve_palette_colors(directive_palette)

        spec = AssetSpec(
            spec_id=f"asset_{directive.category}_{directive.directive_id}",
            category=category,
            motif_id=None,  # Narrative assets are NOT motif-driven
            theme_id="theme.narrative",
            palette_id=directive_palette,
            palette_colors=palette_colors,
            section_ids=section_ids,
            scene_context=[directive.story_context],
            background=_background_for_category(category),
            style_tags=["led_optimized", "bold_silhouette", "high_contrast"],
            content_tags=[directive.directive_id],
            # Narrative-specific fields
            narrative_subject=directive.subject,
            narrative_description=directive.visual_description,
            color_guidance=directive.color_guidance,
            mood=directive.mood,
            # Song context for narrative anchoring
            song_title=song_title,
        )
        specs.append(spec)

    return specs


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------


def extract_asset_specs(
    plan_set: GroupPlanSet,
    lyric_context: LyricContextModel | None = None,
) -> list[AssetSpec]:
    """Extract asset specs from a GroupPlanSet.

    Dual-source extraction:
    1. Effect assets from motif_ids (one per unique motif+category pair).
    2. Narrative assets from narrative_assets directives (figurative/story imagery).
    3. Text assets (song title banner).

    Args:
        plan_set: The complete aggregated plan.
        lyric_context: Optional lyric context for narrative enrichment.

    Returns:
        List of AssetSpec objects ready for enrichment and generation.
    """
    # Path 1: Effect assets from motifs (existing)
    effect_specs = _extract_effect_specs(plan_set, lyric_context)

    # Path 2: Narrative assets from directives (new)
    narrative_specs = _extract_narrative_specs(plan_set)

    # Path 3: Text assets
    text_specs = _extract_text_specs(plan_set)

    all_specs = effect_specs + narrative_specs + text_specs

    logger.debug(
        "Extracted %d total asset specs (%d effect, %d narrative, %d text)",
        len(all_specs),
        len(effect_specs),
        len(narrative_specs),
        len(text_specs),
    )

    return all_specs


def _extract_effect_specs(
    plan_set: GroupPlanSet,
    lyric_context: LyricContextModel | None = None,
) -> list[AssetSpec]:
    """Extract effect (motif-driven) asset specs.

    Args:
        plan_set: The complete aggregated plan.
        lyric_context: Optional lyric context for scene enrichment.

    Returns:
        List of effect AssetSpec objects.
    """
    specs: list[AssetSpec] = []

    contexts = _collect_motif_contexts(plan_set, lyric_context)
    logger.debug("Collected %d motif contexts from plan", len(contexts))

    for motif_id, ctx in contexts.items():
        categories = _determine_categories(ctx.target_roles)
        primary_theme = sorted(ctx.theme_ids)[0] if ctx.theme_ids else "theme.holiday.traditional"
        primary_palette = sorted(ctx.palette_ids)[0] if ctx.palette_ids else None

        # Resolve palette to actual hex colors
        palette_colors = _resolve_palette_colors(primary_palette)

        for category in sorted(categories, key=lambda c: c.value):
            spec = AssetSpec(
                spec_id=_build_spec_id(motif_id, category),
                category=category,
                motif_id=motif_id,
                theme_id=primary_theme,
                palette_id=primary_palette,
                palette_colors=palette_colors,
                target_roles=_roles_for_category(category, ctx.target_roles),
                section_ids=sorted(ctx.section_ids),
                scene_context=list(ctx.scene_context),
                background=_background_for_category(category),
                style_tags=_derive_style_tags(primary_theme),
                content_tags=[motif_id],
            )
            specs.append(spec)

    return specs


def _extract_text_specs(plan_set: GroupPlanSet) -> list[AssetSpec]:
    """Extract text asset specs (song title banner).

    Args:
        plan_set: The complete aggregated plan.

    Returns:
        List of text AssetSpec objects.
    """
    title = plan_set.plan_set_id.replace("_", " ").title()
    primary_theme = "theme.holiday.traditional"
    if plan_set.section_plans:
        primary_theme = plan_set.section_plans[0].theme.theme_id

    banner_spec = AssetSpec(
        spec_id=_build_spec_id("song_title", AssetCategory.TEXT_BANNER),
        category=AssetCategory.TEXT_BANNER,
        motif_id=None,
        theme_id=primary_theme,
        section_ids=[plan_set.section_plans[0].section_id],
        target_roles=[],
        background=BackgroundMode.TRANSPARENT,
        style_tags=_derive_style_tags(primary_theme),
        content_tags=["song_title"],
        text_content=title,
    )

    return [banner_spec]
