"""Context shaping for GroupPlanner agents.

Similar to audio profile's shape_context(), these functions transform
full context into minimal, agent-specific context for efficient LLM consumption.

Each agent gets its own shaping function based on what it actually needs
in its prompt. This allows independent tuning per agent.
"""

import json
import logging
from typing import TYPE_CHECKING, Any

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.taxonomy_utils import get_theming_catalog_dict, get_theming_ids
from twinklr.core.sequencer.planning import GroupPlanSet
from twinklr.core.sequencer.templates.group.affinity import AffinityScorer
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.theming import get_theme
from twinklr.core.sequencer.vocabulary import LaneKind

if TYPE_CHECKING:
    from twinklr.core.agents.sequencer.group_planner.holistic import (
        HolisticEvaluation,
    )

logger = logging.getLogger(__name__)


# Template name/tag patterns for intent-based filtering
# Maps energy levels to patterns that match in template name, ID, or tags
# Includes both descriptive keywords and common template tags (ambient, drive, hit, etc.)
ENERGY_TEMPLATE_PATTERNS: dict[str, list[str]] = {
    "LOW": ["glow", "soft", "warm", "gentle", "shimmer", "breathe", "slow", "ambient"],
    "MODERATE": ["pulse", "sweep", "wave", "flow", "ripple", "drive"],
    "HIGH": ["chase", "strobe", "burst", "flash", "rapid", "drive", "hit"],
    "PEAK": ["burst", "strobe", "hit", "flash", "slam", "big", "emphasis"],
    "BUILD": ["pulse", "swell", "grow", "shimmer", "wave", "drive"],
    "SUSTAIN": ["glow", "shimmer", "pulse", "steady", "ambient"],
    "RELEASE": ["soft", "fade", "gentle", "warm", "ambient"],
}

# Minimum templates per lane — ensures enough variety per lane so the LLM
# doesn't resort to picking templates from other lanes.
MIN_TEMPLATES_PER_LANE = 5


def filter_templates_by_intent(
    catalog: TemplateCatalog,
    energy_target: str,
    motion_density: str,
    motif_ids: list[str] | None = None,
) -> list[TemplateInfo]:
    """Filter templates based on section intent and motif requirements.

    Reduces template count to relevant options, saving tokens and improving
    planner focus. Falls back to full catalog if filtering is too aggressive.

    IMPORTANT: Templates with affinity_tags matching declared motif_ids are
    always included to ensure motif-aligned options are available.

    Args:
        catalog: Full template catalog
        energy_target: Section energy target (LOW, MODERATE, HIGH, PEAK, BUILD, etc.)
        motion_density: Motion density (SPARSE, MODERATE, BUSY)
        motif_ids: Optional list of motif IDs from the section plan

    Returns:
        Filtered list of template entries (empty list if catalog is empty)
    """
    if not catalog.entries:
        logger.debug("Template catalog is empty, returning empty list")
        return []

    motif_list = motif_ids or []

    # Get patterns for this energy target
    patterns = ENERGY_TEMPLATE_PATTERNS.get(energy_target.upper(), [])

    # If no patterns for this energy and no motifs, use all templates
    if not patterns and not motif_list:
        logger.debug(f"No filter patterns for energy '{energy_target}', using full catalog")
        return list(catalog.entries)

    # Filter templates by energy patterns OR motif affinity
    # Using OR ensures sufficient variety per lane; AND was too aggressive
    # and could leave lanes with only the safety minimum (3 templates).
    filtered = []
    filtered_ids = set()
    for entry in catalog.entries:
        name_lower = entry.name.lower()
        template_id_lower = entry.template_id.lower()
        tags_lower = [str(tag).lower() for tag in (entry.tags or [])]

        energy_match = patterns and any(
            pattern in name_lower
            or pattern in template_id_lower
            or any(pattern in tag for tag in tags_lower)
            for pattern in patterns
        )

        motif_match = bool(motif_list) and AffinityScorer.has_motif_affinity(
            entry, motif_ids=motif_list
        )

        include = energy_match or motif_match

        if include and entry.template_id not in filtered_ids:
            filtered.append(entry)
            filtered_ids.add(entry.template_id)

    # Safety check: ensure minimum per lane
    for lane in LaneKind:
        lane_entries = [e for e in filtered if lane in e.compatible_lanes]
        if len(lane_entries) < MIN_TEMPLATES_PER_LANE:
            # Add more templates from full catalog for this lane
            full_lane_entries = [e for e in catalog.entries if lane in e.compatible_lanes]
            # Add entries we don't already have
            existing_ids = {e.template_id for e in filtered}
            for entry in full_lane_entries:
                if entry.template_id not in existing_ids:
                    filtered.append(entry)
                    existing_ids.add(entry.template_id)
                    if (
                        len([e for e in filtered if lane in e.compatible_lanes])
                        >= MIN_TEMPLATES_PER_LANE
                    ):
                        break

    # Final safety: if still empty, return full catalog
    if not filtered:
        logger.warning(
            f"Template filtering for energy={energy_target} resulted in 0 templates, "
            "falling back to full catalog"
        )
        return list(catalog.entries)

    logger.debug(
        f"Template filtering: {len(catalog.entries)} → {len(filtered)} templates "
        f"(energy={energy_target}, density={motion_density})"
    )

    return filtered


def shape_planner_context(section_context: SectionPlanningContext) -> dict[str, Any]:
    """Shape context for GroupPlanner agent (per-section coordination planning).

    **SECTION-FOCUSED + TOKEN-OPTIMIZED**:
    - Groups: Full display graph (ensures sufficient targets for all lanes)
    - Templates: Simplified to {ID, name, lanes} (descriptions dropped, saves ~40% tokens)
    - Layer intents: Filtered to only layers targeting these roles

    Token savings example (chorus section):
    - Before: ~75K tokens (full templates + full layer intents)
    - After: ~45K-55K tokens (minimal templates + filtered layer intents)

    Analyzed from planner/user.j2:
    - Uses: section_id, section_name, start_ms, end_ms
    - Uses: energy_target, motion_density, choreography_style
    - Uses: primary_focus_targets, secondary_targets, notes
    - Uses: choreo_graph.groups (full graph)
    - Uses: choreo_graph.groups_by_role (full graph)
    - Uses: template_catalog.entries (SIMPLIFIED to ID/name/lanes)
    - Uses: layer_intents (FILTERED to relevant layers)
    - Does NOT use: timing_context (not referenced in prompt)

    Args:
        section_context: Complete section planning context

    Returns:
        Shaped context dict for planner prompt
    """
    # Priority roles from MacroPlan intent (used for emphasis guidance in prompts)
    # Keep this list explicit even though the full display graph is provided.
    all_target_roles = section_context.primary_focus_targets + section_context.secondary_targets

    # Keep full display graph for planning so the model has sufficient targets
    # for all lanes without artificial scarcity.
    planner_groups = list(section_context.choreo_graph.groups)
    planner_groups_by_role = dict(section_context.choreo_graph.groups_by_role)

    # Log filtering results
    logger.debug(
        f"Context shaping for {section_context.section_id}: "
        f"{len(section_context.choreo_graph.groups)} groups (full graph), "
        f"{len(section_context.template_catalog.entries)} templates (simplified)"
    )

    # Filter layer_intents to only layers targeting these roles
    # layer_intents can be either dicts or objects with target_selector
    filtered_layer_intents: list[Any] = []
    if section_context.layer_intents:
        for layer in section_context.layer_intents:
            # Handle both dict and object access patterns
            if isinstance(layer, dict):
                target_selector = layer.get("target_selector", {})
                layer_target_roles = target_selector.get("roles", [])
            elif hasattr(layer, "target_selector") and hasattr(layer.target_selector, "roles"):
                layer_target_roles = layer.target_selector.roles
            else:
                continue

            if any(role in all_target_roles for role in layer_target_roles):
                filtered_layer_intents.append(layer)

    # Filter and simplify template catalog
    # 1. Filter by section intent (energy, density, motifs) to reduce options
    # 2. Simplify entries (drop descriptions to save tokens)
    # NOTE: motif_ids ensures templates matching declared motifs are always included
    filtered_entries = filter_templates_by_intent(
        section_context.template_catalog,
        section_context.energy_target,
        section_context.motion_density,
        motif_ids=section_context.motif_ids,
    )

    def _simplify_entries(entries: list[TemplateInfo]) -> list[dict[str, Any]]:
        return [
            {
                "template_id": entry.template_id,
                "name": entry.name,
                "compatible_lanes": entry.compatible_lanes,
                "affinity_tags": AffinityScorer.derive_affinity_tags(entry),
                "tags": entry.tags,
            }
            for entry in entries
        ]

    simplified_catalog = {
        "schema_version": section_context.template_catalog.schema_version,
        "entries": _simplify_entries(filtered_entries),
    }

    # Store the full catalog in simplified form for the section judge.
    # The judge evaluates against the same filtered set the planner sees,
    # plus the full catalog for ID-existence validation.
    full_catalog_simplified = {
        "schema_version": section_context.template_catalog.schema_version,
        "entries": _simplify_entries(list(section_context.template_catalog.entries)),
    }

    logger.debug(
        f"Template catalog for {section_context.section_id}: "
        f"{len(section_context.template_catalog.entries)} → {len(filtered_entries)} "
        f"(energy={section_context.energy_target})"
    )

    # Create section-scoped choreography graph summary
    section_choreo_graph = {
        "schema_version": "choreography-graph.v1",
        "graph_id": section_context.choreo_graph.graph_id,
        "groups": [g.model_dump() for g in planner_groups],
        "groups_by_role": planner_groups_by_role,
    }

    # Prepare theme context if theme is available
    theme_ref_json: str = "{}"
    theme_definition_dict: dict[str, Any] = {
        "default_tags": [],
        "style_tags": [],
        "avoid_tags": [],
        "default_palette_id": None,
    }
    if section_context.theme:
        # Serialize ThemeRef to JSON for prompt
        theme_ref_json = json.dumps(section_context.theme.model_dump(), indent=2)

        # Resolve theme definition from registry
        try:
            theme_def = get_theme(section_context.theme.theme_id)
            theme_definition_dict = {
                "default_tags": theme_def.default_tags,
                "style_tags": theme_def.style_tags,
                "avoid_tags": theme_def.avoid_tags,
                "default_palette_id": theme_def.default_palette_id,
            }
        except Exception as e:
            logger.warning(f"Failed to resolve theme '{section_context.theme.theme_id}': {e}")

    # Prepare palette context.
    # Priority:
    # 1) Section explicit palette override from MacroSectionPlan
    # 2) Section ThemeRef palette_id (if explicitly set)
    # 3) Macro global primary palette
    # Do NOT auto-fallback to theme default palette here; that can introduce
    # unintended palette churn not explicitly requested by MacroPlan.
    palette_ref_json: str = "{}"
    if section_context.palette:
        # Section has explicit palette override
        palette_ref_json = json.dumps(section_context.palette, indent=2)
    elif section_context.theme and section_context.theme.palette_id:
        # Use theme's palette override
        palette_ref_json = json.dumps({"palette_id": section_context.theme.palette_id}, indent=2)
    elif section_context.global_palette_id:
        # Use macro global primary palette as default
        palette_ref_json = json.dumps({"palette_id": section_context.global_palette_id}, indent=2)

    # Get tag catalog and motif catalog for validation
    theming_catalog = get_theming_catalog_dict()
    tag_catalog = theming_catalog["tags"]
    motif_catalog = theming_catalog.get("motifs", [])

    # Build motif catalog summary (compact for prompt)
    motif_catalog_summary = ""
    if motif_catalog:
        motif_lines = []
        for motif in motif_catalog[:15]:  # Limit to avoid token bloat
            motif_id = motif.get("id", "")
            desc = motif.get("description", "")
            energy = motif.get("energy", "")
            line = f"  - {motif_id}: {desc[:60]}{'...' if len(desc) > 60 else ''}"
            if energy:
                line += f" (energy: {energy})"
            motif_lines.append(line)
        motif_catalog_summary = "\n".join(motif_lines)

    # Calculate section duration in bars/beats
    # This tells the LLM how much space it has to work with
    section_duration_ms = section_context.end_ms - section_context.start_ms
    timing_ctx = section_context.timing_context
    if timing_ctx.bar_map:
        # Get bar duration from first bar in map
        first_bar = next(iter(timing_ctx.bar_map.values()))
        bar_duration_ms = first_bar.duration_ms
        beat_duration_ms = bar_duration_ms / timing_ctx.beats_per_bar
        section_bars = section_duration_ms / bar_duration_ms
        section_beats = section_duration_ms / beat_duration_ms
        # Hard bar limit: last bar whose start_ms is within section bounds.
        # The bar_map may include bars past section end due to rounding;
        # using those would cause PLACEMENT_OUTSIDE_SECTION errors.
        valid_bars = [
            bar
            for bar, info in timing_ctx.bar_map.items()
            if info.start_ms < section_context.end_ms
        ]
        section_max_bar = max(valid_bars) if valid_bars else max(timing_ctx.bar_map.keys())
        available_bars = section_max_bar
    else:
        # Fallback estimate
        available_bars = 4
        section_max_bar = available_bars
        section_bars = 4.0
        section_beats = 16.0

    # Build spatial map data for prompt
    display_graph_zones = _build_zone_summary(planner_groups)
    display_graph_spatial = _build_spatial_layout(planner_groups)
    display_graph_splits = _build_split_summary(planner_groups)

    return {
        # Section identity
        "section_id": section_context.section_id,
        "section_name": section_context.section_name,
        # Timing
        "start_ms": section_context.start_ms,
        "end_ms": section_context.end_ms,
        # Section duration in musical terms (CRITICAL for LLM to know constraints)
        "section_duration_bars": round(section_bars, 1),
        "section_duration_beats": round(section_beats, 1),
        "available_bars": available_bars,
        "section_max_bar": section_max_bar,
        # Intent from MacroPlan
        "energy_target": section_context.energy_target,
        "motion_density": section_context.motion_density,
        "choreography_style": section_context.choreography_style,
        "primary_focus_targets": section_context.primary_focus_targets,
        "primary_focus_targets_typed": section_context.primary_focus_targets_typed,
        "secondary_targets": section_context.secondary_targets,
        "secondary_targets_typed": section_context.secondary_targets_typed,
        "priority_roles": all_target_roles,
        "notes": section_context.notes,
        # Section-scoped shared context (FILTERED + SIMPLIFIED)
        "display_graph": section_choreo_graph,
        "template_catalog": simplified_catalog,  # Filtered catalog (planner + judge)
        "template_catalog_full": full_catalog_simplified,  # Full catalog for ID validation
        "layer_intents": filtered_layer_intents,  # Only relevant layers
        # Spatial planning context
        "display_graph_zones": display_graph_zones,
        "display_graph_spatial": display_graph_spatial,
        "display_graph_splits": display_graph_splits,
        # Theme context from MacroPlan
        "theme_ref": section_context.theme,  # ThemeRef object for refinement prompt
        "theme_ref_json": theme_ref_json,
        "theme_definition": theme_definition_dict,
        "palette_ref_json": palette_ref_json,  # Palette for this section
        "motif_ids": section_context.motif_ids,  # Motifs for this section
        "motif_catalog_summary": motif_catalog_summary,  # Motif reference guide
        "tag_catalog": tag_catalog,  # For tag validation
        # Lyric/narrative context (section-scoped) for narrative asset directives
        "lyric_context": section_context.lyric_context,
        # Feature Engineering enrichment (Phase 1 context, all optional)
        "color_arc": section_context.color_arc,
        "propensity_hints": section_context.propensity_hints,
        "style_constraints": section_context.style_constraints,
        # Recipe catalog (Phase 2, optional)
        "recipe_catalog": _shape_recipe_catalog(section_context),
        # Historical learning context (populated by StandardIterationController
        # when IssueRepository is available; defaults to empty so templates
        # using {% if learning_context %} render without error)
        "learning_context": "",
    }


# ---------------------------------------------------------------------------
# Recipe catalog shaping
# ---------------------------------------------------------------------------


def _shape_recipe_catalog(section_context: SectionPlanningContext) -> dict[str, Any] | None:
    """Shape recipe entries for the planner prompt.

    Recipes are multi-layer composite templates from feature engineering.
    Their IDs are valid ``template_id`` values — the renderer handles
    multi-layer composition transparently.

    Args:
        section_context: Section planning context with optional recipe_catalog.

    Returns:
        Shaped recipe catalog dict, or None if no recipes available.
    """
    if section_context.recipe_catalog is None:
        return None

    entries = []
    for recipe in section_context.recipe_catalog.recipes:
        # Collect unique effect types across layers
        effect_types = list(dict.fromkeys(layer.effect_type for layer in recipe.layers))

        entry: dict[str, Any] = {
            "recipe_id": recipe.recipe_id,
            "name": recipe.name,
            "template_type": recipe.template_type.value,
            "visual_intent": recipe.visual_intent.value,
            "layer_count": len(recipe.layers),
            "effect_types": effect_types,
            "tags": recipe.tags,
            "model_affinities": [
                {"model_type": a.model_type, "score": a.score} for a in recipe.model_affinities
            ],
        }
        entries.append(entry)

    return {"entries": entries}


# ---------------------------------------------------------------------------
# Spatial map helpers (for prompt injection)
# ---------------------------------------------------------------------------


def _build_zone_summary(groups: list[ChoreoGroup]) -> list[dict[str, Any]]:
    """Build zone → group_ids summary for prompt.

    Args:
        groups: Filtered list of ChoreoGroup instances.

    Returns:
        List of dicts with ``zone`` and ``group_ids`` keys.
    """
    zone_map: dict[str, list[str]] = {}
    for g in groups:
        for tag in g.tags:
            zone_map.setdefault(tag.value, []).append(g.id)
    return [{"zone": zone, "group_ids": gids} for zone, gids in zone_map.items()]


def _build_spatial_layout(groups: list[ChoreoGroup]) -> dict[str, list[dict[str, str | None]]]:
    """Build horizontal layout summary for prompt.

    Args:
        groups: Filtered list of ChoreoGroup instances.

    Returns:
        Dict with ``horizontal`` key mapping to sorted group list.
    """
    horizontal: list[dict[str, str | None]] = []
    sorted_groups = sorted(
        [g for g in groups if g.position],
        key=lambda g: g.position.horizontal.sort_key() if g.position else 999,
    )
    for g in sorted_groups:
        horizontal.append(
            {
                "position": g.position.horizontal.value if g.position else "UNKNOWN",
                "id": g.id,
                "role": g.role,
                "detail": g.detail_capability.value,
            }
        )
    return {"horizontal": horizontal}


def _build_split_summary(groups: list[ChoreoGroup]) -> dict[str, list[str]]:
    """Build split → group_ids summary for prompt.

    Args:
        groups: Filtered list of ChoreoGroup instances.

    Returns:
        Dict mapping split value strings to lists of group IDs.
    """
    split_map: dict[str, list[str]] = {}
    for g in groups:
        for split in g.split_membership:
            split_map.setdefault(split.value, []).append(g.id)
    return split_map


def shape_section_judge_context(
    section_context: SectionPlanningContext,
    *,
    planner_template_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape context for SectionJudge agent (per-section evaluation).

    **SECTION-FOCUSED**: Includes full display graph validity context and section intent.
    The judge receives two template catalogs:
    - ``template_catalog``: The same filtered catalog the planner was shown (for fair
      quality evaluation — don't penalize for not using templates that weren't available).
    - ``template_catalog_full``: The full catalog for ID-existence validation (a template_id
      is valid if it exists in either catalog).

    Note: The plan itself is added by the controller.

    Args:
        section_context: Complete section planning context
        planner_template_catalog: Optional pre-built filtered catalog from planner context.
            If None, falls back to the full catalog simplified.

    Returns:
        Shaped context dict for section judge (excluding plan)
    """
    all_target_roles = section_context.primary_focus_targets + section_context.secondary_targets
    groups_by_role = dict(section_context.choreo_graph.groups_by_role)

    # Full catalog simplified for ID validation
    full_catalog_simplified = {
        "schema_version": section_context.template_catalog.schema_version,
        "entries": [
            {
                "template_id": entry.template_id,
                "name": entry.name,
                "compatible_lanes": entry.compatible_lanes,
                "affinity_tags": AffinityScorer.derive_affinity_tags(entry),
                "tags": entry.tags,
            }
            for entry in section_context.template_catalog.entries
        ],
    }

    # Use the same filtered catalog the planner saw if available
    judge_template_catalog = planner_template_catalog or full_catalog_simplified

    # Prepare theme context for validation
    theme_definition_dict: dict[str, Any] | None = None
    if section_context.theme:
        try:
            theme_def = get_theme(section_context.theme.theme_id)
            theme_definition_dict = {
                "theme_id": section_context.theme.theme_id,
                "default_tags": theme_def.default_tags,
                "style_tags": theme_def.style_tags,
                "avoid_tags": theme_def.avoid_tags,
                "default_palette_id": theme_def.default_palette_id,
            }
        except Exception:
            pass

    # Get theming IDs for validation
    theming_ids = get_theming_ids()

    # Get motif catalog for validation and template support checking
    from twinklr.core.agents.taxonomy_utils import get_theming_catalog_dict

    theming_catalog = get_theming_catalog_dict()

    return {
        # Section identity
        "section_id": section_context.section_id,
        "section_name": section_context.section_name,
        # Timing (for bounds validation)
        "start_ms": section_context.start_ms,
        "end_ms": section_context.end_ms,
        # Intent (for quality assessment)
        "energy_target": section_context.energy_target,
        "motion_density": section_context.motion_density,
        "choreography_style": section_context.choreography_style,
        "primary_focus_targets": section_context.primary_focus_targets,
        "primary_focus_targets_typed": section_context.primary_focus_targets_typed,
        "secondary_targets": section_context.secondary_targets,
        "secondary_targets_typed": section_context.secondary_targets_typed,
        "priority_roles": all_target_roles,
        # Section-scoped shared context
        "display_graph": {
            "groups_by_role": groups_by_role,
            "groups_by_tag": {
                tag.value: ids for tag, ids in section_context.choreo_graph.groups_by_tag.items()
            },
            "groups_by_split": {
                split.value: ids
                for split, ids in section_context.choreo_graph.groups_by_split.items()
            },
        },
        "template_catalog": judge_template_catalog,  # Same filtered catalog planner saw
        "template_catalog_full": full_catalog_simplified,  # Full catalog for ID validation
        # Theme context for validation
        "theme_definition": theme_definition_dict,
        "theming_ids": theming_ids,  # For validating theme_id, tags, palette_id
        "motif_catalog": theming_catalog[
            "motifs"
        ],  # For validating motif_ids and checking template support
        # Excluded: timing_context, layer_intents, notes
    }


def _shape_lyric_context_summary(lyric_context: Any | None) -> dict[str, Any] | None:
    """Extract a compact narrative summary from LyricContextModel for holistic judge.

    Args:
        lyric_context: LyricContextModel instance (or None)

    Returns:
        Compact dict with narrative fields, or None if no lyrics/narrative context.
    """
    if lyric_context is None:
        return None

    has_lyrics = getattr(lyric_context, "has_lyrics", False)
    if not has_lyrics:
        return None

    return {
        "has_narrative": getattr(lyric_context, "has_narrative", False),
        "characters": getattr(lyric_context, "characters", None) or [],
        "themes": getattr(lyric_context, "themes", None) or [],
        "mood_arc": getattr(lyric_context, "mood_arc", ""),
        "genre_markers": getattr(lyric_context, "genre_markers", None) or [],
        "recommended_visual_themes": getattr(lyric_context, "recommended_visual_themes", None)
        or [],
    }


def _compute_completeness_check(
    section_ids: list[str],
    expected_section_ids: list[str],
) -> dict[str, Any]:
    """Deterministic completeness check for holistic judge.

    Compares actual section IDs against expected IDs from the MacroPlan.
    This prevents LLM hallucination when counting sections in large JSON payloads.

    Args:
        section_ids: Section IDs present in the GroupPlanSet.
        expected_section_ids: Section IDs expected by the MacroPlan.

    Returns:
        Dict with status, counts, and any missing/extra section IDs.
    """
    if not expected_section_ids:
        return {
            "status": "SKIPPED",
            "reason": "No expected section list provided by MacroPlan",
        }

    present_set = set(section_ids)
    expected_set = set(expected_section_ids)

    missing = sorted(expected_set - present_set)
    extra = sorted(present_set - expected_set)

    if not missing and not extra:
        return {
            "status": "PASSED",
            "present_count": len(section_ids),
            "expected_count": len(expected_section_ids),
            "missing": [],
            "extra": [],
        }

    return {
        "status": "FAILED",
        "present_count": len(section_ids),
        "expected_count": len(expected_section_ids),
        "missing": missing,
        "extra": extra,
    }


def shape_holistic_judge_context(
    group_plan_set: GroupPlanSet,
    choreo_graph: ChoreographyGraph,
    template_catalog: TemplateCatalog,
    macro_plan_summary: dict[str, Any] | None,
    lyric_context: Any | None = None,
) -> dict[str, Any]:
    """Shape context for HolisticJudge agent (cross-section evaluation).

    Provides theme/palette data for cross-section continuity evaluation:
    - Global theme ID and palette from macro_plan_summary.global_story
    - Per-section theme IDs and palette overrides
    - Color story narrative (if provided)
    - Lyric/narrative context for calibrating variety + utilization scores

    Analyzed from holistic_judge/user.j2:
    - Uses: group_plan_set (serialized to JSON)
    - Uses: section_count, section_ids (computed from plan set)
    - Uses: choreo_graph.groups_by_role (NOT full groups)
    - Uses: macro_plan_summary.global_story (theme, motifs, pacing_notes)
    - Uses: lyric_context (narrative summary for score calibration)
    - Does NOT use: template_catalog, timing_context

    Args:
        group_plan_set: Complete set of section plans
        choreo_graph: Choreography graph configuration
        template_catalog: Available templates
        macro_plan_summary: Optional MacroPlan summary
        lyric_context: Optional LyricContextModel for narrative calibration

    Returns:
        Shaped context dict for holistic judge
    """
    # Serialize for Jinja2 tojson filter
    group_plan_set_dict = group_plan_set.model_dump()

    # Extract global theme context for explicit display
    # Handle both dict and string formats for global_story
    global_story = (macro_plan_summary or {}).get("global_story", {})
    if isinstance(global_story, str):
        # Legacy format: global_story is a string
        global_story = {}
    global_theme = global_story.get("theme", {}) if isinstance(global_story, dict) else {}
    global_theme_id = global_theme.get("theme_id") if isinstance(global_theme, dict) else None
    global_palette_id = global_theme.get("palette_id") if isinstance(global_theme, dict) else None
    global_theme_tags = global_theme.get("tags", []) if isinstance(global_theme, dict) else []
    story_notes = global_story.get("story_notes", "") if isinstance(global_story, dict) else ""

    # Extract palette_plan if available
    palette_plan = global_story.get("palette_plan", {}) if isinstance(global_story, dict) else {}
    global_palette_primary = (
        palette_plan.get("primary", {}).get("palette_id")
        if isinstance(palette_plan, dict)
        else None
    )
    global_palette_alternates = (
        [
            alt.get("palette_id")
            for alt in palette_plan.get("alternates", [])
            if isinstance(alt, dict)
        ]
        if isinstance(palette_plan, dict)
        else []
    )

    # Extract section theme summaries for cross-section analysis
    section_theme_summary = []
    for sp in group_plan_set.section_plans:
        theme_dict = sp.theme.model_dump() if sp.theme else {}
        section_theme_summary.append(
            {
                "section_id": sp.section_id,
                "theme_id": theme_dict.get("theme_id"),
                "scope": theme_dict.get("scope"),
                "tags": theme_dict.get("tags", []),
                "palette_id": theme_dict.get("palette_id"),
                "motif_ids": sp.motif_ids,
            }
        )

    # Extract expected section IDs from macro_plan_summary (if provided)
    expected_section_ids: list[str] = []
    if macro_plan_summary:
        expected_section_ids = list(macro_plan_summary.get("expected_section_ids", []))

    # Deterministic completeness check (prevents LLM hallucination on large JSON)
    section_ids = [sp.section_id for sp in group_plan_set.section_plans]
    completeness_check = _compute_completeness_check(section_ids, expected_section_ids)

    # ChoreographyGraph has no hierarchy (ChoreoGroup has no parent_group_id)
    group_hierarchy: dict[str, list[str]] = {}

    return {
        "group_plan_set": group_plan_set_dict,
        "display_graph": {
            "groups_by_role": choreo_graph.groups_by_role,
            "groups_by_tag": {tag.value: ids for tag, ids in choreo_graph.groups_by_tag.items()},
            "groups_by_split": {
                split.value: ids for split, ids in choreo_graph.groups_by_split.items()
            },
        },
        "group_hierarchy": group_hierarchy,
        "section_count": len(group_plan_set.section_plans),
        "section_ids": section_ids,
        "expected_section_ids": expected_section_ids,
        "completeness_check": completeness_check,
        "macro_plan_summary": macro_plan_summary or {},
        # Explicitly extracted theme/palette context for holistic evaluation
        "global_theme_id": global_theme_id,
        "global_palette_id": global_palette_id,
        "global_theme_tags": global_theme_tags,
        "global_palette_primary": global_palette_primary,
        "global_palette_alternates": global_palette_alternates,
        "story_notes": story_notes,
        "section_theme_summary": section_theme_summary,
        # Lyric/narrative context — used to calibrate variety + utilization scoring
        "lyric_context": _shape_lyric_context_summary(lyric_context),
        # template_catalog excluded (not used in prompt)
    }


def shape_holistic_corrector_context(
    group_plan_set: GroupPlanSet,
    holistic_evaluation: "HolisticEvaluation",
    choreo_graph: ChoreographyGraph | None = None,
    template_catalog: TemplateCatalog | None = None,
) -> dict[str, Any]:
    """Build variables for holistic corrector prompt.

    Scopes context to keep token usage feasible:
    - Affected sections (referenced by targeted actions) at full detail
    - Non-affected sections as compact summaries for cross-section awareness
    - Template catalog filtered to referenced templates only

    Args:
        group_plan_set: Complete plan set to correct
        holistic_evaluation: Evaluation with issues and targeted actions
        choreo_graph: Optional display graph for target validation
        template_catalog: Optional template catalog for template validation

    Returns:
        Variables dict for corrector prompt
    """
    from twinklr.core.agents.issues import IssueSeverity

    actionable_issues = [
        issue
        for issue in holistic_evaluation.cross_section_issues
        if issue.severity in (IssueSeverity.ERROR, IssueSeverity.WARN) and issue.targeted_actions
    ]

    # Deduplicate affected section IDs from all targeted actions
    affected_section_ids: set[str] = set()
    for issue in actionable_issues:
        affected_section_ids.update(issue.affected_sections)
        for action in issue.targeted_actions:
            affected_section_ids.add(action.section_id)

    # Partition sections: affected get full detail, others get summary
    affected_sections_data: list[dict[str, Any]] = []
    section_summaries: list[dict[str, Any]] = []

    for section in group_plan_set.section_plans:
        if section.section_id in affected_section_ids:
            affected_sections_data.append(
                section.model_dump(exclude={"start_ms", "end_ms", "narrative_assets"})
            )
        else:
            template_ids_by_lane: dict[str, list[str]] = {}
            for lp in section.lane_plans:
                tids = []
                for cp in lp.coordination_plans:
                    for p in cp.placements:
                        if p.template_id not in tids:
                            tids.append(p.template_id)
                    if cp.window and cp.window.template_id not in tids:
                        tids.append(cp.window.template_id)
                template_ids_by_lane[lp.lane.value] = tids

            section_summaries.append({
                "section_id": section.section_id,
                "theme": section.theme.model_dump() if section.theme else None,
                "palette": section.palette.model_dump() if section.palette else None,
                "motif_ids": section.motif_ids,
                "template_ids_by_lane": template_ids_by_lane,
            })

    variables: dict[str, Any] = {
        "affected_sections_json": json.dumps(affected_sections_data, indent=2, default=str),
        "affected_section_ids": sorted(affected_section_ids),
        "section_summaries": section_summaries,
        "holistic_evaluation": holistic_evaluation.model_dump(),
        "actionable_issues": [issue.model_dump() for issue in actionable_issues],
        "strengths": holistic_evaluation.strengths,
    }

    if choreo_graph is not None:
        variables["choreo_graph"] = choreo_graph.model_dump()

    if template_catalog is not None:
        referenced_template_ids: set[str] = set()
        for issue in actionable_issues:
            for action in issue.targeted_actions:
                if action.template_id:
                    referenced_template_ids.add(action.template_id)
                if action.replacement_template_id:
                    referenced_template_ids.add(action.replacement_template_id)

        if referenced_template_ids:
            catalog_data = template_catalog.model_dump()
            filtered_entries = [
                e
                for e in catalog_data.get("entries", [])
                if e.get("template_id") in referenced_template_ids
            ]
            variables["template_catalog"] = {"entries": filtered_entries}

    return variables
