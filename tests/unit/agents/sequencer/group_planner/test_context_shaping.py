"""Unit tests for GroupPlanner context shaping functions.

Tests context transformation logic that filters and simplifies context
for efficient LLM consumption.
"""

from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.context_shaping import (
    filter_templates_by_intent,
    shape_holistic_judge_context,
    shape_planner_context,
    shape_section_judge_context,
)
from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.sequencer.planning import GroupPlanSet, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.templates.group.models import DisplayGraph, DisplayGroup
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent, LaneKind

from .conftest import DEFAULT_THEME

# Rebuild TemplateInfo after LaneKind is imported
TemplateInfo.model_rebuild()


# ============================================================================
# Test Models & Fixtures
# ============================================================================


# Layer intents are dicts, not Pydantic models


def make_display_group(group_id: str, role: str) -> DisplayGroup:
    """Helper to create DisplayGroup for testing."""
    return DisplayGroup(
        group_id=group_id,
        role=role,
        display_name=f"{role}_{group_id}",
    )


def make_template_entry(
    template_id: str, name: str, lanes: list[str], description: str = "Test description"
) -> TemplateInfo:
    """Helper to create TemplateInfo for testing."""
    from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent

    # Map lane strings to template types
    lane_to_type = {
        "BASE": GroupTemplateType.BASE,
        "RHYTHM": GroupTemplateType.RHYTHM,
        "ACCENT": GroupTemplateType.ACCENT,
    }
    lane_to_visual = {
        "BASE": GroupVisualIntent.ABSTRACT,
        "RHYTHM": GroupVisualIntent.GEOMETRIC,
        "ACCENT": GroupVisualIntent.TEXTURE,
    }

    # Use first lane for type determination
    first_lane = lanes[0] if lanes else "BASE"
    template_type = lane_to_type.get(first_lane, GroupTemplateType.BASE)
    visual_intent = lane_to_visual.get(first_lane, GroupVisualIntent.ABSTRACT)

    return TemplateInfo(
        template_id=template_id,
        version="1.0",
        name=name,
        template_type=template_type,
        visual_intent=visual_intent,
        tags=(),
        description=description,
    )


@pytest.fixture
def section_context() -> SectionPlanningContext:
    """Create mock section planning context."""
    # Create display groups with various roles
    # Note: group_id must match pattern ^[A-Z][A-Z0-9_]*$
    groups = [
        make_display_group("MEGA_TREE_01", "MEGA_TREE"),
        make_display_group("HERO_01", "HERO"),
        make_display_group("ARCHES_01", "ARCHES"),
        make_display_group("TREES_01", "TREES"),
        make_display_group("PROPS_01", "PROPS"),
    ]

    # DisplayGraph computes groups_by_role automatically from groups
    display_graph = DisplayGraph(
        schema_version="display-graph.v1",
        display_id="test_display",
        display_name="Test Display",
        groups=groups,
    )

    # Create template catalog
    template_entries = [
        make_template_entry("sweep_basic", "Basic Sweep", ["BASE"], "A basic sweep pattern"),
        make_template_entry("pulse_rhythm", "Rhythm Pulse", ["RHYTHM"], "Rhythmic pulse"),
        make_template_entry("hit_accent", "Accent Hit", ["ACCENT"], "Sharp accent hit"),
    ]

    template_catalog = TemplateCatalog(
        schema_version="template-catalog.v1", entries=template_entries
    )

    # Create timing context (required field)
    timing_context = TimingContext(
        song_duration_ms=120000,
        beats_per_bar=4,
    )

    # Create layer intents (some targeting section roles, some not)
    # layer_intents are dicts with target_selector containing roles
    layer_intents: list[dict[str, Any]] = [
        {
            "layer_index": 0,
            "target_selector": {"roles": ["MEGA_TREE", "HERO"]},  # ← Relevant
        },
        {
            "layer_index": 1,
            "target_selector": {"roles": ["ARCHES"]},  # ← Relevant
        },
        {
            "layer_index": 2,
            "target_selector": {"roles": ["FLOODS"]},  # ← NOT relevant
        },
    ]

    # Build section context
    return SectionPlanningContext(
        section_id="chorus_1",
        section_name="Chorus 1",
        start_ms=10000,
        end_ms=25000,
        energy_target="HIGH",
        motion_density="BUSY",
        choreography_style="ABSTRACT",
        primary_focus_targets=["MEGA_TREE", "HERO"],
        secondary_targets=["ARCHES"],
        notes="Big chorus moment",
        display_graph=display_graph,
        template_catalog=template_catalog,
        timing_context=timing_context,
        layer_intents=layer_intents,  # type: ignore[arg-type]
    )


# ============================================================================
# Test: shape_planner_context()
# ============================================================================


def test_shape_planner_context_basic_fields(section_context: SectionPlanningContext) -> None:
    """Test basic field passthrough."""
    result = shape_planner_context(section_context)

    # Section identity
    assert result["section_id"] == "chorus_1"
    assert result["section_name"] == "Chorus 1"

    # Timing
    assert result["start_ms"] == 10000
    assert result["end_ms"] == 25000

    # Intent
    assert result["energy_target"] == "HIGH"
    assert result["motion_density"] == "BUSY"
    assert result["choreography_style"] == "ABSTRACT"
    assert result["primary_focus_targets"] == ["MEGA_TREE", "HERO"]
    assert result["secondary_targets"] == ["ARCHES"]
    assert result["notes"] == "Big chorus moment"


def test_shape_planner_context_filters_groups_by_role(
    section_context: SectionPlanningContext,
) -> None:
    """Test display graph filtering to only target roles."""
    result = shape_planner_context(section_context)

    display_graph = result["display_graph"]
    groups = display_graph["groups"]

    # Should only include MEGA_TREE, HERO, ARCHES (not TREES, PROPS)
    assert len(groups) == 3
    group_roles = [g["role"] for g in groups]
    assert "MEGA_TREE" in group_roles
    assert "HERO" in group_roles
    assert "ARCHES" in group_roles
    assert "TREES" not in group_roles
    assert "PROPS" not in group_roles


def test_shape_planner_context_filters_groups_by_role_dict(
    section_context: SectionPlanningContext,
) -> None:
    """Test groups_by_role filtering."""
    result = shape_planner_context(section_context)

    groups_by_role = result["display_graph"]["groups_by_role"]

    # Should only include target roles
    assert "MEGA_TREE" in groups_by_role
    assert "HERO" in groups_by_role
    assert "ARCHES" in groups_by_role
    assert "TREES" not in groups_by_role
    assert "PROPS" not in groups_by_role


def test_shape_planner_context_simplifies_template_catalog(
    section_context: SectionPlanningContext,
) -> None:
    """Test template catalog simplification (drops descriptions)."""
    result = shape_planner_context(section_context)

    catalog = result["template_catalog"]
    entries = catalog["entries"]

    # Should have all templates (order may vary due to intent filtering)
    assert len(entries) == 3

    # Find sweep_basic entry regardless of order
    entry_map = {e["template_id"]: e for e in entries}
    sweep = entry_map["sweep_basic"]
    assert sweep["name"] == "Basic Sweep"
    assert sweep["compatible_lanes"] == ["BASE"]

    # CRITICAL: Description should be DROPPED (token savings)
    assert "description" not in sweep
    assert "presets" not in sweep
    assert "category" not in sweep


def test_shape_planner_context_filters_layer_intents(
    section_context: SectionPlanningContext,
) -> None:
    """Test layer intent filtering to only relevant layers."""
    result = shape_planner_context(section_context)

    layer_intents = result["layer_intents"]

    # Should include layers 0 and 1 (target MEGA_TREE/HERO/ARCHES)
    # Should exclude layer 2 (targets FLOODS which is not in section)
    assert len(layer_intents) == 2

    # layer_intents are dicts returned from shape_planner_context
    # Verify layer indices (access as dict keys)
    assert layer_intents[0]["layer_index"] == 0  # Targets MEGA_TREE, HERO
    assert layer_intents[1]["layer_index"] == 1  # Targets ARCHES


def test_shape_planner_context_excludes_timing_context(
    section_context: SectionPlanningContext,
) -> None:
    """Test timing_context is excluded (not used in prompt)."""
    result = shape_planner_context(section_context)

    assert "timing_context" not in result


def test_shape_planner_context_empty_layer_intents(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles None/empty layer_intents gracefully."""
    section_context.layer_intents = None  # type: ignore[assignment]

    result = shape_planner_context(section_context)

    assert "layer_intents" in result
    assert result["layer_intents"] == []


def test_shape_planner_context_layer_without_target_selector(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles layers without target_selector attribute."""
    section_context.layer_intents = [  # type: ignore[assignment]
        {"layer_index": 5}  # No target_selector
    ]

    result = shape_planner_context(section_context)

    # Should not crash, should filter out layer without target_selector
    assert result["layer_intents"] == []


def test_shape_planner_context_all_roles_primary_and_secondary(
    section_context: SectionPlanningContext,
) -> None:
    """Test includes both primary_focus_targets and secondary_targets."""
    # Modify context to have distinct primary and secondary
    section_context.primary_focus_targets = ["MEGA_TREE"]
    section_context.secondary_targets = ["HERO", "ARCHES"]

    result = shape_planner_context(section_context)

    display_graph = result["display_graph"]
    group_roles = [g["role"] for g in display_graph["groups"]]

    # Should include ALL target roles (primary + secondary)
    assert "MEGA_TREE" in group_roles  # Primary
    assert "HERO" in group_roles  # Secondary
    assert "ARCHES" in group_roles  # Secondary


# ============================================================================
# Test: shape_section_judge_context()
# ============================================================================


def test_shape_section_judge_context_basic_fields(
    section_context: SectionPlanningContext,
) -> None:
    """Test basic field passthrough."""
    result = shape_section_judge_context(section_context)

    # Section identity
    assert result["section_id"] == "chorus_1"
    assert result["section_name"] == "Chorus 1"

    # Timing
    assert result["start_ms"] == 10000
    assert result["end_ms"] == 25000

    # Intent
    assert result["energy_target"] == "HIGH"
    assert result["motion_density"] == "BUSY"
    assert result["choreography_style"] == "ABSTRACT"
    assert result["primary_focus_targets"] == ["MEGA_TREE", "HERO"]
    assert result["secondary_targets"] == ["ARCHES"]


def test_shape_section_judge_context_filters_groups_by_role(
    section_context: SectionPlanningContext,
) -> None:
    """Test groups_by_role filtering."""
    result = shape_section_judge_context(section_context)

    groups_by_role = result["display_graph"]["groups_by_role"]

    # Should only include target roles
    assert "MEGA_TREE" in groups_by_role
    assert "HERO" in groups_by_role
    assert "ARCHES" in groups_by_role
    assert "TREES" not in groups_by_role
    assert "PROPS" not in groups_by_role


def test_shape_section_judge_context_simplifies_template_catalog(
    section_context: SectionPlanningContext,
) -> None:
    """Test template catalog simplification."""
    result = shape_section_judge_context(section_context)

    catalog = result["template_catalog"]
    entries = catalog["entries"]

    assert len(entries) == 3

    # Check simplification
    entry = entries[0]
    assert entry["template_id"] == "sweep_basic"
    assert entry["name"] == "Basic Sweep"
    assert entry["compatible_lanes"] == ["BASE"]
    assert "description" not in entry  # Dropped


def test_shape_section_judge_context_excludes_unnecessary_fields(
    section_context: SectionPlanningContext,
) -> None:
    """Test unnecessary fields are excluded."""
    result = shape_section_judge_context(section_context)

    # Should exclude
    assert "timing_context" not in result
    assert "layer_intents" not in result
    assert "notes" not in result  # Excluded for judge


def test_shape_section_judge_context_display_graph_structure(
    section_context: SectionPlanningContext,
) -> None:
    """Test display_graph only includes groups_by_role (not full groups list)."""
    result = shape_section_judge_context(section_context)

    display_graph = result["display_graph"]

    # Should ONLY have groups_by_role (not groups, not display_id, not schema_version)
    assert "groups_by_role" in display_graph
    assert "groups" not in display_graph
    assert "display_id" not in display_graph
    assert "schema_version" not in display_graph


# ============================================================================
# Test: shape_holistic_judge_context()
# ============================================================================


@pytest.fixture
def group_plan_set() -> GroupPlanSet:
    """Create mock GroupPlanSet."""
    # Import lane plan and minimal coordination plan
    # Import models
    from twinklr.core.sequencer.planning import LanePlan
    from twinklr.core.sequencer.templates.group.models import (
        CoordinationPlan,
        GroupPlacement,
    )
    from twinklr.core.sequencer.vocabulary import CoordinationMode, EffectDuration, PlanningTimeRef

    # Create minimal placements
    placements = [
        GroupPlacement(
            placement_id="p1",
            group_id="MEGA_TREE_01",
            template_id="sweep_basic",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.BURST,
        )
    ]

    # Create minimal lane plans
    lane_plans = [
        LanePlan(
            lane=LaneKind.BASE,
            target_roles=["MEGA_TREE"],
            coordination_plans=[
                CoordinationPlan(
                    coordination_mode=CoordinationMode.UNIFIED,
                    group_ids=["MEGA_TREE_01"],
                    placements=placements,
                )
            ],
        )
    ]

    section_plans = [
        SectionCoordinationPlan(section_id="intro", theme=DEFAULT_THEME, lane_plans=lane_plans),
        SectionCoordinationPlan(section_id="verse_1", theme=DEFAULT_THEME, lane_plans=lane_plans),
        SectionCoordinationPlan(section_id="chorus_1", theme=DEFAULT_THEME, lane_plans=lane_plans),
    ]

    return GroupPlanSet(
        plan_set_id="test_plan_set",
        section_plans=section_plans,
    )


@pytest.fixture
def display_graph() -> DisplayGraph:
    """Create mock DisplayGraph."""
    groups = [
        make_display_group("MEGA_TREE", "MEGA_TREE"),
        make_display_group("HERO_02", "HERO"),
    ]

    return DisplayGraph(
        schema_version="display-graph.v1",
        display_id="test_display",
        display_name="Test Display",
        groups=groups,
    )


@pytest.fixture
def template_catalog() -> TemplateCatalog:
    """Create mock TemplateCatalog."""
    entries = [
        make_template_entry("sweep_basic", "Basic Sweep", ["BASE"]),
    ]

    return TemplateCatalog(schema_version="template-catalog.v1", entries=entries)


def test_shape_holistic_judge_context_basic_structure(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test basic structure of holistic judge context."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    # Required fields
    assert "group_plan_set" in result
    assert "display_graph" in result
    assert "section_count" in result
    assert "section_ids" in result
    assert "macro_plan_summary" in result


def test_shape_holistic_judge_context_section_count(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test section_count is computed correctly."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    assert result["section_count"] == 3


def test_shape_holistic_judge_context_section_ids(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test section_ids are extracted correctly."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    section_ids = result["section_ids"]
    assert section_ids == ["intro", "verse_1", "chorus_1"]


def test_shape_holistic_judge_context_display_graph_minimal(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test display_graph only includes groups_by_role."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    dg = result["display_graph"]

    # Should ONLY have groups_by_role
    assert "groups_by_role" in dg
    assert len(dg) == 1  # Only one key


def test_shape_holistic_judge_context_excludes_template_catalog(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test template_catalog is excluded (not used in prompt)."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    assert "template_catalog" not in result


def test_shape_holistic_judge_context_macro_plan_summary_none(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test handles None macro_plan_summary."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    assert result["macro_plan_summary"] == {}


def test_shape_holistic_judge_context_macro_plan_summary_provided(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test includes macro_plan_summary when provided."""
    summary = {
        "global_story": "A festive Christmas journey",
        "theme": "Holiday magic",
    }

    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=summary
    )

    assert result["macro_plan_summary"] == summary


def test_shape_holistic_judge_context_serialization(
    group_plan_set: GroupPlanSet,
    display_graph: DisplayGraph,
    template_catalog: TemplateCatalog,
) -> None:
    """Test group_plan_set is properly serialized to dict."""
    result = shape_holistic_judge_context(
        group_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    gps = result["group_plan_set"]

    # Should be a dict (serialized from Pydantic model)
    assert isinstance(gps, dict)
    assert "section_plans" in gps
    assert len(gps["section_plans"]) == 3


# ============================================================================
# Test: Edge Cases & Robustness
# ============================================================================


def test_shape_planner_context_empty_primary_focus(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles empty primary_focus_targets."""
    section_context.primary_focus_targets = []
    section_context.secondary_targets = ["HERO"]

    result = shape_planner_context(section_context)

    # Should still filter to secondary targets only
    display_graph = result["display_graph"]
    group_roles = [g["role"] for g in display_graph["groups"]]
    assert "HERO" in group_roles
    assert len(group_roles) == 1


def test_shape_planner_context_empty_secondary_targets(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles empty secondary_targets."""
    section_context.primary_focus_targets = ["MEGA_TREE"]
    section_context.secondary_targets = []

    result = shape_planner_context(section_context)

    # Should filter to primary targets only
    display_graph = result["display_graph"]
    group_roles = [g["role"] for g in display_graph["groups"]]
    assert "MEGA_TREE" in group_roles
    assert len(group_roles) == 1


def test_shape_planner_context_no_matching_groups(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles case where no groups match target roles."""
    section_context.primary_focus_targets = ["NONEXISTENT_ROLE"]
    section_context.secondary_targets = []

    result = shape_planner_context(section_context)

    # Should return empty groups list
    display_graph = result["display_graph"]
    assert display_graph["groups"] == []
    assert display_graph["groups_by_role"] == {}


def test_shape_planner_context_empty_template_catalog(
    section_context: SectionPlanningContext,
) -> None:
    """Test handles empty template catalog."""
    section_context.template_catalog.entries = []

    result = shape_planner_context(section_context)

    catalog = result["template_catalog"]
    assert catalog["entries"] == []


def test_shape_section_judge_context_no_matching_groups(
    section_context: SectionPlanningContext,
) -> None:
    """Test judge handles no matching groups."""
    section_context.primary_focus_targets = ["NONEXISTENT"]
    section_context.secondary_targets = []

    result = shape_section_judge_context(section_context)

    assert result["display_graph"]["groups_by_role"] == {}


def test_shape_holistic_judge_context_single_section() -> None:
    """Test holistic handles single section plan."""
    from twinklr.core.sequencer.planning import LanePlan
    from twinklr.core.sequencer.templates.group.models import (
        CoordinationPlan,
        GroupPlacement,
    )
    from twinklr.core.sequencer.vocabulary import CoordinationMode, EffectDuration, PlanningTimeRef

    # Create minimal placements
    placements = [
        GroupPlacement(
            placement_id="p1",
            group_id="TEST_01",
            template_id="sweep_basic",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.BURST,
        )
    ]

    # Create minimal valid section plan
    lane_plans = [
        LanePlan(
            lane=LaneKind.BASE,
            target_roles=["HERO_02"],
            coordination_plans=[
                CoordinationPlan(
                    coordination_mode=CoordinationMode.UNIFIED,
                    group_ids=["TEST_01"],
                    placements=placements,
                )
            ],
        )
    ]

    single_plan_set = GroupPlanSet(
        plan_set_id="test_single",
        section_plans=[
            SectionCoordinationPlan(section_id="solo", theme=DEFAULT_THEME, lane_plans=lane_plans)
        ],
    )

    display_graph = DisplayGraph(
        schema_version="display-graph.v1",
        display_id="test",
        display_name="Test Display",
        groups=[make_display_group("TEST_01", "HERO_02")],
    )

    template_catalog = TemplateCatalog(schema_version="template-catalog.v1", entries=[])

    result = shape_holistic_judge_context(
        single_plan_set, display_graph, template_catalog, macro_plan_summary=None
    )

    assert result["section_count"] == 1
    assert result["section_ids"] == ["solo"]


# ============================================================================
# Test: Token Savings Verification
# ============================================================================


def test_template_simplification_drops_expected_fields(
    section_context: SectionPlanningContext,
) -> None:
    """Verify token savings: template descriptions are actually dropped."""
    # Original template has description
    original_entry = section_context.template_catalog.entries[0]
    assert original_entry.description is not None
    assert len(original_entry.description) > 0

    # Shaped context should drop it
    result = shape_planner_context(section_context)
    shaped_entry = result["template_catalog"]["entries"][0]

    # Verify fields that should be present
    assert "template_id" in shaped_entry
    assert "name" in shaped_entry
    assert "compatible_lanes" in shaped_entry

    # Verify fields that should be dropped (token savings)
    assert "description" not in shaped_entry
    assert "presets" not in shaped_entry
    assert "category" not in shaped_entry

    # tags should be INCLUDED (needed for template selection heuristics)
    assert "tags" in shaped_entry


def test_judge_template_simplification_consistent(
    section_context: SectionPlanningContext,
) -> None:
    """Verify judge also drops template descriptions."""
    result = shape_section_judge_context(section_context)
    shaped_entry = result["template_catalog"]["entries"][0]

    # Same simplification as planner
    assert "description" not in shaped_entry
    assert "presets" not in shaped_entry


# ============================================================================
# Test: filter_templates_by_intent()
# ============================================================================


def test_filter_templates_by_intent_empty_catalog() -> None:
    """Empty catalog should return empty list."""
    catalog = TemplateCatalog(schema_version="test", entries=[])
    result = filter_templates_by_intent(catalog, "HIGH", "BUSY")
    assert result == []


def test_filter_templates_by_intent_unknown_energy_returns_all() -> None:
    """Unknown energy target should return full catalog."""
    entries = [
        TemplateInfo(
            template_id="test1",
            version="1.0",
            name="Test 1",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        TemplateInfo(
            template_id="test2",
            version="1.0",
            name="Test 2",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
    ]
    catalog = TemplateCatalog(schema_version="test", entries=entries)

    result = filter_templates_by_intent(catalog, "UNKNOWN_ENERGY", "SPARSE")
    assert len(result) == 2


def test_filter_templates_by_intent_filters_by_energy_pattern() -> None:
    """HIGH energy should prefer burst/strobe/chase patterns."""
    entries = [
        TemplateInfo(
            template_id="soft_glow",
            version="1.0",
            name="Soft Glow",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        TemplateInfo(
            template_id="chase_fast",
            version="1.0",
            name="Fast Chase",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        TemplateInfo(
            template_id="burst_big",
            version="1.0",
            name="Big Burst",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
    ]
    catalog = TemplateCatalog(schema_version="test", entries=entries)

    result = filter_templates_by_intent(catalog, "HIGH", "BUSY")

    # Should include chase and burst, not soft glow
    result_ids = [e.template_id for e in result]
    assert "chase_fast" in result_ids
    assert "burst_big" in result_ids


def test_filter_templates_by_intent_ensures_minimum_per_lane() -> None:
    """Should ensure minimum templates per lane even when filtering is aggressive."""
    entries = [
        # BASE templates (none match HIGH patterns)
        TemplateInfo(
            template_id="base1",
            version="1.0",
            name="Warm Glow",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        TemplateInfo(
            template_id="base2",
            version="1.0",
            name="Gentle Fade",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        TemplateInfo(
            template_id="base3",
            version="1.0",
            name="Slow Pulse",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=(),
        ),
        # RHYTHM templates (some match)
        TemplateInfo(
            template_id="rhythm1",
            version="1.0",
            name="Chase Pattern",
            template_type=GroupTemplateType.RHYTHM,
            visual_intent=GroupVisualIntent.GEOMETRIC,
            tags=(),
        ),
        # ACCENT templates (all match HIGH)
        TemplateInfo(
            template_id="accent1",
            version="1.0",
            name="Burst Hit",
            template_type=GroupTemplateType.ACCENT,
            visual_intent=GroupVisualIntent.TEXTURE,
            tags=(),
        ),
        TemplateInfo(
            template_id="accent2",
            version="1.0",
            name="Strobe Flash",
            template_type=GroupTemplateType.ACCENT,
            visual_intent=GroupVisualIntent.TEXTURE,
            tags=(),
        ),
    ]
    catalog = TemplateCatalog(schema_version="test", entries=entries)

    result = filter_templates_by_intent(catalog, "HIGH", "BUSY")

    # Count templates per lane
    from twinklr.core.sequencer.vocabulary import LaneKind

    base_count = len([e for e in result if LaneKind.BASE in e.compatible_lanes])
    rhythm_count = len([e for e in result if LaneKind.RHYTHM in e.compatible_lanes])
    accent_count = len([e for e in result if LaneKind.ACCENT in e.compatible_lanes])

    # Should have at least 3 per lane (minimum threshold) - but only if enough exist
    # Here we have 3 BASE, 1 RHYTHM, 2 ACCENT so:
    # - BASE: Should get all 3 (none match pattern, but safety adds them)
    # - RHYTHM: Only 1 available
    # - ACCENT: 2 match HIGH patterns
    assert base_count >= 3  # All added via safety
    assert rhythm_count >= 1  # Only 1 available
    assert accent_count >= 2  # Both match HIGH


def test_template_simplification_includes_affinity_and_avoid_tags(section_context):
    """Verify that affinity_tags and avoid_tags are included in simplified catalog."""
    shaped = shape_planner_context(section_context)

    # Check that simplified catalog entries include affinity_tags and avoid_tags
    assert "template_catalog" in shaped
    assert "entries" in shaped["template_catalog"]

    if shaped["template_catalog"]["entries"]:
        # Check first entry has the new fields
        entry = shaped["template_catalog"]["entries"][0]
        assert "template_id" in entry
        assert "name" in entry
        assert "compatible_lanes" in entry
        assert "affinity_tags" in entry  # NEW: Should be present
        assert "avoid_tags" in entry  # NEW: Should be present

        # Verify they are lists (even if empty)
        assert isinstance(entry["affinity_tags"], list)
        assert isinstance(entry["avoid_tags"], list)
