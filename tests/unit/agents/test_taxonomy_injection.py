"""Tests for Phase 03: Taxonomy & Vocabulary Injection.

Verifies that FE-discovered compound motion/energy terms from VocabularyExtensions
are injected into the planner's taxonomy dict via shape_planner_context(), and
that the developer.j2 template renders the compound vocabulary section correctly.
"""

from __future__ import annotations

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.context_shaping import shape_planner_context
from twinklr.core.agents.sequencer.group_planner.timing import TimingContext
from twinklr.core.feature_engineering.models.vocabulary import (
    CompoundEnergyTerm,
    CompoundMotionTerm,
    VocabularyExtensions,
)
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent

# Rebuild after imports settle
TemplateInfo.model_rebuild()


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------


def _make_minimal_section_context(
    vocabulary_extensions: VocabularyExtensions | None = None,
) -> SectionPlanningContext:
    """Build a minimal SectionPlanningContext suitable for unit tests.

    Args:
        vocabulary_extensions: Optional VocabularyExtensions to attach.

    Returns:
        SectionPlanningContext with minimal valid data.
    """
    group = ChoreoGroup(id="MEGA_TREE_01", role="MEGA_TREE")
    choreo_graph = ChoreographyGraph(graph_id="test_display", groups=[group])

    entry = TemplateInfo(
        template_id="gtpl_base_glow",
        version="1.0",
        name="Glow",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=(),
        description="Glow effect",
    )
    template_catalog = TemplateCatalog(schema_version="template-catalog.v1", entries=[entry])
    timing_context = TimingContext(song_duration_ms=120000, beats_per_bar=4)

    return SectionPlanningContext(
        section_id="verse_1",
        section_name="Verse 1",
        start_ms=0,
        end_ms=15000,
        energy_target="LOW",
        motion_density="SPARSE",
        choreography_style="ABSTRACT",
        primary_focus_targets=["MEGA_TREE_01"],
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        timing_context=timing_context,
        vocabulary_extensions=vocabulary_extensions,
    )


def _make_motion_term(term: str) -> CompoundMotionTerm:
    return CompoundMotionTerm(
        term=term,
        description=f"Test motion term: {term}",
        component_families=("Chase", "Sweep"),
        component_roles=("base", "accent"),
        motion_axis="horizontal",
        corpus_support=5,
        canonical_signature=f"{term}_sig",
    )


def _make_energy_term(term: str) -> CompoundEnergyTerm:
    return CompoundEnergyTerm(
        term=term,
        description=f"Test energy term: {term}",
        base_energy="LOW",
        accent_energy="HIGH",
        combined_energy="MED",
        corpus_support=3,
        canonical_signature=f"{term}_sig",
    )


# ---------------------------------------------------------------------------
# Test 1: taxonomy contains CompoundMotionTerm when vocabulary_extensions present
# ---------------------------------------------------------------------------


def test_taxonomy_contains_compound_motion_when_vocabulary_extensions_present() -> None:
    """shape_planner_context() adds CompoundMotionTerm key when vocabulary_extensions set."""
    vx = VocabularyExtensions(
        compound_motion_terms=(_make_motion_term("dual_chase"), _make_motion_term("sweep_strobe")),
        compound_energy_terms=(_make_energy_term("wash_burst"),),
    )
    ctx = _make_minimal_section_context(vocabulary_extensions=vx)
    result = shape_planner_context(ctx)

    taxonomy = result.get("taxonomy")
    assert taxonomy is not None, "taxonomy key must be present in shaped context"
    assert "CompoundMotionTerm" in taxonomy, (
        "taxonomy must contain CompoundMotionTerm when vocabulary_extensions present"
    )


# ---------------------------------------------------------------------------
# Test 2: compound terms match vocabulary_extensions content exactly
# ---------------------------------------------------------------------------


def test_compound_terms_match_vocabulary_extensions_content() -> None:
    """Taxonomy CompoundMotionTerm and CompoundEnergyTerm values match VocabularyExtensions."""
    vx = VocabularyExtensions(
        compound_motion_terms=(_make_motion_term("dual_chase"), _make_motion_term("sweep_strobe")),
        compound_energy_terms=(_make_energy_term("wash_burst"),),
    )
    ctx = _make_minimal_section_context(vocabulary_extensions=vx)
    result = shape_planner_context(ctx)

    taxonomy = result["taxonomy"]
    assert set(taxonomy["CompoundMotionTerm"]) == {"dual_chase", "sweep_strobe"}
    assert set(taxonomy["CompoundEnergyTerm"]) == {"wash_burst"}


# ---------------------------------------------------------------------------
# Test 3: static fallback when vocabulary_extensions is None
# ---------------------------------------------------------------------------


def test_static_fallback_when_vocabulary_extensions_none() -> None:
    """taxonomy must NOT have CompoundMotionTerm/CompoundEnergyTerm when extensions absent."""
    ctx = _make_minimal_section_context(vocabulary_extensions=None)
    result = shape_planner_context(ctx)

    taxonomy = result.get("taxonomy")
    assert taxonomy is not None, "taxonomy key must still be present"
    assert "CompoundMotionTerm" not in taxonomy, (
        "CompoundMotionTerm must not appear without vocabulary_extensions"
    )
    assert "CompoundEnergyTerm" not in taxonomy, (
        "CompoundEnergyTerm must not appear without vocabulary_extensions"
    )


# ---------------------------------------------------------------------------
# Test 4: inject_taxonomy skips when taxonomy already pre-populated
# ---------------------------------------------------------------------------


def test_inject_taxonomy_skips_when_prepopulated() -> None:
    """inject_taxonomy() does not overwrite an existing 'taxonomy' key."""
    from twinklr.core.agents.taxonomy_utils import inject_taxonomy

    sentinel = {"MyCustomKey": ["A", "B"]}
    variables: dict = {"taxonomy": sentinel}
    result = inject_taxonomy(variables)

    assert result["taxonomy"] is sentinel, (
        "inject_taxonomy must not overwrite pre-populated taxonomy"
    )


# ---------------------------------------------------------------------------
# Test 5: developer.j2 renders compound vocabulary section
# ---------------------------------------------------------------------------


def test_developer_j2_renders_compound_section() -> None:
    """developer.j2 renders 'Compound Motion Vocabulary' when taxonomy has CompoundMotionTerm."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("developer.j2")

    output = template.render(
        taxonomy={
            "CompoundMotionTerm": ["dual_chase", "sweep_strobe"],
            "CompoundEnergyTerm": ["wash_burst"],
            "LaneKind": ["BASE", "RHYTHM", "ACCENT"],
            "CoordinationMode": ["UNIFIED", "COMPLEMENTARY"],
            "IntensityLevel": ["SOFT", "MED", "STRONG"],
            "EffectDuration": ["HIT", "BURST", "PHRASE", "EXTENDED", "SECTION"],
            "StepUnit": ["BEATS", "BARS"],
            "TargetType": ["group", "zone", "split"],
            "SplitDimension": ["HALVES_LEFT", "HALVES_RIGHT"],
            "DetailCapability": ["LOW", "MEDIUM", "HIGH"],
        },
        learning_context="",
        response_schema="{}",
        recipe_catalog=None,
    )

    assert "Compound Motion Vocabulary" in output, (
        "developer.j2 must render 'Compound Motion Vocabulary' section"
    )


# ---------------------------------------------------------------------------
# Test 6: _extract_fe_fields includes vocabulary_extensions
# ---------------------------------------------------------------------------


def test_extract_fe_fields_includes_vocabulary_extensions() -> None:
    """GroupPlannerStage._extract_fe_fields() includes vocabulary_extensions when set."""
    from unittest.mock import MagicMock

    from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
    from twinklr.core.sequencer.templates.group.models.choreography import ChoreographyGraph

    vx = VocabularyExtensions(
        compound_motion_terms=(_make_motion_term("dual_chase"),),
        compound_energy_terms=(_make_energy_term("wash_burst"),),
    )

    # Minimal stub fe_bundle with only vocabulary_extensions set
    fe_bundle = MagicMock()
    fe_bundle.color_arc = None
    fe_bundle.propensity_index = None
    fe_bundle.style_fingerprint = None
    fe_bundle.vocabulary_extensions = vx

    group = ChoreoGroup(id="MEGA_TREE_01", role="MEGA_TREE")
    choreo_graph = ChoreographyGraph(graph_id="test_display", groups=[group])

    entry = TemplateInfo(
        template_id="gtpl_base_glow",
        version="1.0",
        name="Glow",
        template_type=GroupTemplateType.BASE,
        visual_intent=GroupVisualIntent.ABSTRACT,
        tags=(),
        description="Glow effect",
    )
    template_catalog = TemplateCatalog(schema_version="template-catalog.v1", entries=[entry])

    stage = GroupPlannerStage(
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        fe_bundle=fe_bundle,
    )

    result = stage._extract_fe_fields(section_id="verse_1")

    assert "vocabulary_extensions" in result, (
        "_extract_fe_fields must include 'vocabulary_extensions' key when fe_bundle has it"
    )
    assert result["vocabulary_extensions"] is vx
