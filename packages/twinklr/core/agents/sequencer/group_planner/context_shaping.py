"""Context shaping for GroupPlanner agents.

Similar to audio profile's shape_context(), these functions transform
full context into minimal, agent-specific context for efficient LLM consumption.

Each agent gets its own shaping function based on what it actually needs
in its prompt. This allows independent tuning per agent.
"""

from typing import Any

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.models import (
    DisplayGraph,
    GroupPlanSet,
)
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog


def shape_planner_context(section_context: SectionPlanningContext) -> dict[str, Any]:
    """Shape context for GroupPlanner agent (per-section coordination planning).

    **SECTION-FOCUSED + TOKEN-OPTIMIZED**:
    - Groups: Filtered to primary_focus + secondary target roles only
    - Templates: Simplified to {ID, name, lanes} (descriptions dropped, saves ~40% tokens)
    - Layer intents: Filtered to only layers targeting these roles

    Token savings example (chorus section):
    - Before: ~75K tokens (9 groups + 61 full templates + 3 layers)
    - After: ~45K tokens (9 groups + 61 minimal templates + 2 layers) = 40% reduction

    Analyzed from planner/user.j2:
    - Uses: section_id, section_name, start_ms, end_ms
    - Uses: energy_target, motion_density, choreography_style
    - Uses: primary_focus_targets, secondary_targets, notes
    - Uses: display_graph.groups (FILTERED to section targets)
    - Uses: display_graph.groups_by_role (FILTERED)
    - Uses: template_catalog.entries (SIMPLIFIED to ID/name/lanes)
    - Uses: layer_intents (FILTERED to relevant layers)
    - Does NOT use: timing_context (not referenced in prompt)

    Args:
        section_context: Complete section planning context

    Returns:
        Shaped context dict for planner prompt
    """
    # Filter display graph to only relevant groups for this section
    # Keep ALL roles assigned by MacroPlanner (both primary and secondary)
    all_target_roles = section_context.primary_focus_targets + section_context.secondary_targets

    # Filter groups to only those in target roles
    filtered_groups = [
        g for g in section_context.display_graph.groups if g.role in all_target_roles
    ]

    # Filter groups_by_role to only target roles
    filtered_groups_by_role = {
        role: groups
        for role, groups in section_context.display_graph.groups_by_role.items()
        if role in all_target_roles
    }

    # Filter layer_intents to only layers targeting these roles
    filtered_layer_intents = []
    if section_context.layer_intents:
        for layer in section_context.layer_intents:
            # Check if this layer targets any of our target roles
            if hasattr(layer, "target_selector") and hasattr(layer.target_selector, "roles"):
                layer_target_roles = layer.target_selector.roles
                if any(role in all_target_roles for role in layer_target_roles):
                    filtered_layer_intents.append(layer)

    # Simplify template catalog (drop descriptions to save tokens)
    # Planner needs IDs, names, and lane compatibility - descriptions are nice-to-have
    simplified_catalog = {
        "schema_version": section_context.template_catalog.schema_version,
        "entries": [
            {
                "template_id": entry.template_id,
                "name": entry.name,
                "compatible_lanes": entry.compatible_lanes,
                # Drop: description, presets, category (save ~40% tokens)
            }
            for entry in section_context.template_catalog.entries
        ],
    }

    # Create section-scoped display graph
    section_display_graph = {
        "schema_version": section_context.display_graph.schema_version,
        "display_id": section_context.display_graph.display_id,
        "groups": [g.model_dump() for g in filtered_groups],
        "groups_by_role": filtered_groups_by_role,
    }

    return {
        # Section identity
        "section_id": section_context.section_id,
        "section_name": section_context.section_name,
        # Timing
        "start_ms": section_context.start_ms,
        "end_ms": section_context.end_ms,
        # Intent from MacroPlan
        "energy_target": section_context.energy_target,
        "motion_density": section_context.motion_density,
        "choreography_style": section_context.choreography_style,
        "primary_focus_targets": section_context.primary_focus_targets,
        "secondary_targets": section_context.secondary_targets,
        "notes": section_context.notes,
        # Section-scoped shared context (FILTERED + SIMPLIFIED)
        "display_graph": section_display_graph,
        "template_catalog": simplified_catalog,  # Stripped to essentials
        "layer_intents": filtered_layer_intents,  # Only relevant layers
        # timing_context excluded (not used in prompt)
    }


def shape_section_judge_context(
    section_context: SectionPlanningContext,
) -> dict[str, Any]:
    """Shape context for SectionJudge agent (per-section evaluation).

    **SECTION-FOCUSED**: Only includes groups relevant to this section.
    Templates kept minimal (IDs only for validation).

    Analyzed from section_judge/user.j2:
    - Uses: start_ms, end_ms (for bounds checking)
    - Uses: energy_target, motion_density, choreography_style
    - Uses: primary_focus_targets, secondary_targets
    - Uses: display_graph.groups_by_role (FILTERED to section targets)
    - Uses: template_catalog (simplified to IDs only)
    - Does NOT use: timing_context, layer_intents

    Note: The plan itself is added by the controller.

    Args:
        section_context: Complete section planning context

    Returns:
        Shaped context dict for section judge (excluding plan)
    """
    # Filter to only relevant roles for this section
    all_target_roles = section_context.primary_focus_targets + section_context.secondary_targets

    # Filter groups_by_role to only target roles
    filtered_groups_by_role = {
        role: groups
        for role, groups in section_context.display_graph.groups_by_role.items()
        if role in all_target_roles
    }

    # Simplify template catalog to just IDs and names (judge only needs to validate existence)
    simplified_catalog = {
        "schema_version": section_context.template_catalog.schema_version,
        "entries": [
            {
                "template_id": entry.template_id,
                "name": entry.name,
                "compatible_lanes": entry.compatible_lanes,
            }
            for entry in section_context.template_catalog.entries
        ],
    }

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
        "secondary_targets": section_context.secondary_targets,
        # Section-scoped shared context
        "display_graph": {"groups_by_role": filtered_groups_by_role},
        "template_catalog": simplified_catalog,
        # Excluded: timing_context, layer_intents, notes
    }


def shape_holistic_judge_context(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
    macro_plan_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Shape context for HolisticJudge agent (cross-section evaluation).

    Analyzed from holistic_judge/user.j2:
    - Uses: group_plan_set (serialized to JSON)
    - Uses: section_count, section_ids (computed from plan set)
    - Uses: display_graph.groups_by_role (NOT full groups)
    - Uses: macro_plan_summary.global_story (theme, motifs, pacing_notes)
    - Does NOT use: template_catalog, timing_context

    TODO: As we tune the holistic judge, we may want to:
    - Add aggregate statistics (template variety, energy arc summary)
    - Add cross-section transition analysis

    Args:
        group_plan_set: Complete set of section plans
        display_graph: Display configuration
        template_catalog: Available templates
        macro_plan_summary: Optional MacroPlan summary

    Returns:
        Shaped context dict for holistic judge
    """
    # Serialize for Jinja2 tojson filter
    group_plan_set_dict = group_plan_set.model_dump()
    display_graph_dict = display_graph.model_dump()

    return {
        "group_plan_set": group_plan_set_dict,
        # Only groups_by_role used in prompt
        "display_graph": {"groups_by_role": display_graph_dict.get("groups_by_role", {})},
        "section_count": len(group_plan_set.section_plans),
        "section_ids": [sp.section_id for sp in group_plan_set.section_plans],
        "macro_plan_summary": macro_plan_summary or {},
        # template_catalog excluded (not used in prompt)
    }
