"""Utilities for extracting taxonomy enum values for prompt injection.

Ensures prompts always use the source-of-truth enum values from vocabulary,
theming catalogs, and issues modules.
"""

from typing import Any


def get_taxonomy_dict() -> dict[str, list[str]]:
    """Get dictionary of taxonomy enum names to value lists.

    Extracts all enum values from the vocabulary and issues modules for dynamic
    injection into prompts, preventing hardcoded enum drift.

    Returns:
        Dict mapping enum class names to lists of their string values.
        Example: {"LayerRole": ["BASE", "RHYTHM", ...],
                  "IssueCategory": ["SCHEMA", "TIMING", ...], ...}
    """
    from enum import Enum

    from twinklr.core.agents.issues import (
        IssueCategory,
        IssueEffort,
        IssueScope,
        IssueSeverity,
        SuggestedAction,
    )
    from twinklr.core.sequencer.vocabulary import (
        AssetSlotType,
        BlendMode,
        ChoreographyStyle,
        CoordinationMode,
        EffectDuration,
        EnergyTarget,
        GroupTemplateType,
        GroupVisualIntent,
        IntensityLevel,
        LaneKind,
        LayerRole,
        MotionDensity,
        QuantizeMode,
        SnapMode,
        SpillPolicy,
        StepUnit,
        TargetRole,
        TimingDriver,
        TimingHint,
    )
    from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

    taxonomy: dict[str, list[str]] = {}

    # Extract choreography taxonomy enums
    choreography_enums: list[type[Enum]] = [
        LayerRole,
        BlendMode,
        TimingDriver,
        TargetRole,
        EnergyTarget,
        ChoreographyStyle,
        MotionDensity,
        TimeRefKind,
        SnapMode,
        QuantizeMode,
        GroupTemplateType,
        GroupVisualIntent,
        AssetSlotType,
    ]

    # Group planner enums
    group_planner_enums: list[type[Enum]] = [
        LaneKind,
        CoordinationMode,
        StepUnit,
        SpillPolicy,
        # Categorical planning enums (v2)
        IntensityLevel,
        EffectDuration,
        TimingHint,
    ]

    # Extract issue taxonomy enums (for judge agents)
    issue_enums: list[type[Enum]] = [
        IssueCategory,
        IssueSeverity,
        IssueEffort,
        IssueScope,
        SuggestedAction,
    ]

    all_enums = choreography_enums + group_planner_enums + issue_enums
    for enum_class in all_enums:
        taxonomy[enum_class.__name__] = [e.value for e in enum_class]  # type: ignore[misc]

    return taxonomy


def get_supported_motif_ids() -> set[str]:
    """Get set of motif IDs that have at least one template with corresponding affinity_tag.

    Returns:
        Set of motif IDs (without 'motif.' prefix) that are supported by templates.
        Example: {"sparkles", "dots", "wave_bands", "radial_rays"}
    """
    # Import templates (ensures builtins are loaded)
    import twinklr.core.sequencer.templates.group.builtins  # noqa: F401
    from twinklr.core.sequencer.templates.group.library import list_group_templates

    # Get all unique motif.* tags from template affinity_tags
    motif_tags = set()
    for template in list_group_templates():
        for tag in template.affinity_tags:
            if isinstance(tag, str) and tag.startswith("motif."):
                # Extract motif ID (e.g., "motif.sparkles" -> "sparkles")
                motif_id = tag[6:]  # Remove "motif." prefix
                motif_tags.add(motif_id)

    return motif_tags


def get_theming_catalog_dict() -> dict[str, list[dict[str, str]]]:
    """Get dictionary of theming catalog items for prompt injection.

    Extracts palette, tag, theme, and motif IDs with descriptions from the
    theming catalogs for dynamic injection into prompts.

    Returns:
        Dict with keys 'palettes', 'tags', 'themes', 'motifs', each containing
        a list of dicts with id and description.
        Example: {
            "palettes": [{"id": "core.uv_party", "title": "UV Party", "hint": "..."}],
            "tags": [{"id": "motif.spiral", "description": "...", "category": "MOTIF"}],
            "themes": [{"id": "theme.abstract.neon", "title": "...", "palette": "..."}],
            "motifs": [{"id": "spiral", "description": "...", "energy": "MED,HIGH"}]
        }
    """
    from twinklr.core.sequencer.theming import (
        list_motifs,
        list_palettes,
        list_tags,
        list_themes,
    )

    catalog: dict[str, list[dict[str, str]]] = {}

    # Extract palettes
    catalog["palettes"] = [
        {
            "id": info.palette_id,
            "title": info.title,
            "description": info.description or "",
        }
        for info in list_palettes()
    ]

    # Extract tags with category
    catalog["tags"] = [
        {
            "id": info.tag,
            "description": info.description or "",
            "category": info.category.value if info.category else "",
        }
        for info in list_tags()
    ]

    # Extract themes
    catalog["themes"] = [
        {
            "id": info.theme_id,
            "title": info.title,
            "description": info.description or "",
            "palette": info.default_palette_id or "",
        }
        for info in list_themes()
    ]

    # Extract motifs (filtered to only those with template support)
    supported_motifs = get_supported_motif_ids()
    catalog["motifs"] = [
        {
            "id": info.motif_id,
            "description": info.description or "",
            "energy": ",".join(info.preferred_energy),
        }
        for info in list_motifs()
        if info.motif_id in supported_motifs
    ]

    return catalog


def get_theming_ids() -> dict[str, list[str]]:
    """Get simple lists of theming catalog IDs for prompt injection.

    Motif IDs are filtered to only those with template support.

    Returns:
        Dict with keys 'palette_ids', 'tag_ids', 'theme_ids', 'motif_ids',
        each containing a sorted list of valid IDs.
    """
    from twinklr.core.sequencer.theming import (
        MOTIF_REGISTRY,
        PALETTE_REGISTRY,
        TAG_REGISTRY,
        THEME_REGISTRY,
    )

    # Filter motifs to only those with template support
    supported_motifs = get_supported_motif_ids()
    all_motif_ids = set(MOTIF_REGISTRY.list_ids())
    filtered_motif_ids = sorted(all_motif_ids & supported_motifs)

    return {
        "palette_ids": PALETTE_REGISTRY.list_ids(),
        "tag_ids": TAG_REGISTRY.list_ids(),
        "theme_ids": THEME_REGISTRY.list_ids(),
        "motif_ids": filtered_motif_ids,
    }


def inject_taxonomy(variables: dict[str, Any]) -> dict[str, Any]:
    """Inject taxonomy enum values into prompt variables.

    Args:
        variables: Existing prompt variables

    Returns:
        Variables dict with 'taxonomy' key added containing enum values
    """
    if "taxonomy" not in variables:
        variables = {**variables, "taxonomy": get_taxonomy_dict()}
    return variables


def inject_theming(variables: dict[str, Any]) -> dict[str, Any]:
    """Inject theming catalog data into prompt variables.

    Adds 'theming' (full catalog with descriptions) and 'theming_ids'
    (simple ID lists) to prompt variables for validation and selection.

    Args:
        variables: Existing prompt variables

    Returns:
        Variables dict with 'theming' and 'theming_ids' keys added
    """
    if "theming" not in variables:
        variables = {**variables, "theming": get_theming_catalog_dict()}
    if "theming_ids" not in variables:
        variables = {**variables, "theming_ids": get_theming_ids()}
    return variables


def inject_all(variables: dict[str, Any]) -> dict[str, Any]:
    """Inject all taxonomy and theming data into prompt variables.

    Convenience function that injects both taxonomy enums and theming catalogs
    (palettes, tags, themes, motifs).

    Args:
        variables: Existing prompt variables

    Returns:
        Variables dict with 'taxonomy', 'theming', and 'theming_ids' keys added
    """
    variables = inject_taxonomy(variables)
    variables = inject_theming(variables)
    return variables
