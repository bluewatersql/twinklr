"""Asset resolution: map plan placements to catalog asset IDs.

Runs AFTER the asset creation pipeline, BEFORE the renderer.
Resolves each motif placement in the GroupPlanSet to catalog asset_ids
and writes them back into the plan so the renderer consumes resolved
asset paths directly.

This module is NOT part of the renderer. It is a pipeline step that
bridges asset creation and rendering.
"""

from __future__ import annotations

import logging
import re

from twinklr.core.agents.assets.models import (
    AssetCatalog,
    AssetCategory,
    AssetStatus,
    CatalogEntry,
)
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role → preferred AssetCategory
# ---------------------------------------------------------------------------

ROLE_CATEGORY_PREFERENCE: dict[str, AssetCategory] = {
    # Large matrix models — fill with tileable pattern
    "MEGA_TREE": AssetCategory.IMAGE_TEXTURE,
    "MATRIX": AssetCategory.IMAGE_TEXTURE,
    # Linear / small models — overlay transparent cutouts
    "ARCHES": AssetCategory.IMAGE_CUTOUT,
    "OUTLINE": AssetCategory.IMAGE_CUTOUT,
    "WINDOWS": AssetCategory.IMAGE_CUTOUT,
    "HERO": AssetCategory.IMAGE_CUTOUT,
}

# Default when role is unknown
_DEFAULT_CATEGORY = AssetCategory.IMAGE_CUTOUT


# ---------------------------------------------------------------------------
# Motif ID extraction
# ---------------------------------------------------------------------------

# Pattern: gtpl_{lane}_motif_{motif_id}_{energy_suffix}
# where lane ∈ {base, rhythm, accent, transition, special}
# and energy_suffix ∈ {ambient, drive, hit_small, hit_big, signature, ripple, ...}
#
# The motif_id may contain underscores (e.g., "candy_stripes", "light_trails",
# "wave_bands", "radial_rays"). We extract everything between "_motif_" and
# the final underscore-separated energy suffix.
_MOTIF_PATTERN = re.compile(
    r"^gtpl_(?:base|rhythm|accent|transition|special)_motif_(.+)_("
    r"ambient|drive|hit_small|hit_big|signature|ripple|pulse|sweep"
    r")$"
)


def extract_motif_id(template_id: str) -> str | None:
    """Extract motif_id from a template_id.

    Scans for the ``_motif_`` segment in the template ID and extracts
    the motif name between it and the trailing energy suffix.

    Args:
        template_id: Group plan template ID
            (e.g., ``gtpl_rhythm_motif_candy_stripes_drive``).

    Returns:
        The motif_id (e.g., ``candy_stripes``), or None if the
        template is not a motif template.

    Examples:
        >>> extract_motif_id("gtpl_base_motif_sparkles_ambient")
        'sparkles'
        >>> extract_motif_id("gtpl_rhythm_motif_candy_stripes_drive")
        'candy_stripes'
        >>> extract_motif_id("gtpl_base_wash_soft")
        None
    """
    if not template_id:
        return None

    match = _MOTIF_PATTERN.match(template_id)
    if match:
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Catalog search
# ---------------------------------------------------------------------------


def _find_matching_entries(
    motif_id: str,
    catalog: AssetCatalog,
    preferred_category: AssetCategory,
) -> list[str]:
    """Search catalog for matching assets by motif_id with category preference.

    Search strategy:
    1. Find all successful entries for this motif_id.
    2. Prefer entries matching the preferred_category for the group's role.
    3. If no preferred-category match, fall back to any category.

    Args:
        motif_id: Motif identifier to search for.
        catalog: Asset catalog to search.
        preferred_category: Preferred asset category for the target role.

    Returns:
        List of matching asset_ids (may be empty).
    """
    # Find all successful entries for this motif
    motif_entries = [
        e
        for e in catalog.find_by_motif(motif_id)
        if e.status != AssetStatus.FAILED
    ]

    if not motif_entries:
        return []

    # Try preferred category first
    preferred = [
        e for e in motif_entries if e.spec.category == preferred_category
    ]
    if preferred:
        return [e.asset_id for e in preferred]

    # Fall back to any category
    logger.debug(
        "No %s asset for motif '%s', falling back to available: %s",
        preferred_category.value,
        motif_id,
        [e.spec.category.value for e in motif_entries],
    )
    return [e.asset_id for e in motif_entries]


# ---------------------------------------------------------------------------
# Plan resolution
# ---------------------------------------------------------------------------


def _resolve_placement(
    placement: GroupPlacement,
    catalog: AssetCatalog,
) -> GroupPlacement:
    """Resolve a single placement to catalog asset IDs.

    Args:
        placement: Original placement (frozen).
        catalog: Asset catalog.

    Returns:
        New GroupPlacement with resolved_asset_ids populated,
        or the original if no motif or no match.
    """
    motif_id = extract_motif_id(placement.template_id)
    if motif_id is None:
        return placement

    # Determine preferred category from group role
    preferred = ROLE_CATEGORY_PREFERENCE.get(
        placement.group_id, _DEFAULT_CATEGORY
    )

    asset_ids = _find_matching_entries(motif_id, catalog, preferred)
    if not asset_ids:
        logger.debug(
            "No catalog match for motif '%s' (template=%s, group=%s)",
            motif_id,
            placement.template_id,
            placement.group_id,
        )
        return placement

    logger.debug(
        "Resolved placement %s → %d assets: %s",
        placement.placement_id,
        len(asset_ids),
        asset_ids,
    )

    # Reconstruct frozen model with resolved_asset_ids
    return placement.model_copy(update={"resolved_asset_ids": asset_ids})


def _resolve_coordination_plan(
    coord_plan: CoordinationPlan,
    catalog: AssetCatalog,
) -> CoordinationPlan:
    """Resolve all placements in a coordination plan.

    Args:
        coord_plan: Original coordination plan.
        catalog: Asset catalog.

    Returns:
        New CoordinationPlan with resolved placements.
    """
    if not coord_plan.placements:
        return coord_plan

    resolved_placements = [
        _resolve_placement(p, catalog) for p in coord_plan.placements
    ]

    # Only create a new plan if something changed
    if all(
        r is o for r, o in zip(resolved_placements, coord_plan.placements)
    ):
        return coord_plan

    return coord_plan.model_copy(update={"placements": resolved_placements})


def _resolve_lane_plan(
    lane_plan: LanePlan,
    catalog: AssetCatalog,
) -> LanePlan:
    """Resolve all coordination plans in a lane plan.

    Args:
        lane_plan: Original lane plan.
        catalog: Asset catalog.

    Returns:
        New LanePlan with resolved coordination plans.
    """
    resolved_coords = [
        _resolve_coordination_plan(cp, catalog)
        for cp in lane_plan.coordination_plans
    ]

    if all(
        r is o for r, o in zip(resolved_coords, lane_plan.coordination_plans)
    ):
        return lane_plan

    return lane_plan.model_copy(update={"coordination_plans": resolved_coords})


def _resolve_section(
    section: SectionCoordinationPlan,
    catalog: AssetCatalog,
) -> SectionCoordinationPlan:
    """Resolve all lane plans in a section.

    Args:
        section: Original section plan.
        catalog: Asset catalog.

    Returns:
        New SectionCoordinationPlan with resolved lane plans.
    """
    resolved_lanes = [
        _resolve_lane_plan(lp, catalog) for lp in section.lane_plans
    ]

    if all(
        r is o for r, o in zip(resolved_lanes, section.lane_plans)
    ):
        return section

    return section.model_copy(update={"lane_plans": resolved_lanes})


def resolve_plan_assets(
    plan_set: GroupPlanSet,
    catalog: AssetCatalog,
) -> GroupPlanSet:
    """Resolve each motif placement to catalog asset IDs.

    For each GroupPlacement in the plan_set:
    1. Extract motif_id from template_id.
    2. Determine preferred category from group_id role.
    3. Search catalog for matching assets by (motif_id, category).
    4. Write matched asset_ids into placement.resolved_asset_ids.

    This is a pure function: it returns a new GroupPlanSet with
    resolved_asset_ids populated. The original plan_set is not mutated.

    Args:
        plan_set: Group plan set with unresolved placements.
        catalog: Asset catalog with generated entries.

    Returns:
        New GroupPlanSet with resolved_asset_ids populated on
        placements that match catalog entries.
    """
    resolved_sections = [
        _resolve_section(s, catalog) for s in plan_set.section_plans
    ]

    # Count resolutions for logging
    total_placements = 0
    resolved_count = 0
    for section in resolved_sections:
        for lane in section.lane_plans:
            for coord in lane.coordination_plans:
                for placement in coord.placements:
                    total_placements += 1
                    if placement.resolved_asset_ids:
                        resolved_count += 1

    logger.info(
        "Asset resolution: %d/%d placements resolved to catalog assets",
        resolved_count,
        total_placements,
    )

    if all(
        r is o for r, o in zip(resolved_sections, plan_set.section_plans)
    ):
        return plan_set

    return plan_set.model_copy(update={"section_plans": resolved_sections})


__all__ = [
    "ROLE_CATEGORY_PREFERENCE",
    "extract_motif_id",
    "resolve_plan_assets",
]
