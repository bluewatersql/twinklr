"""Tests for Phase 04: StyleFingerprint Completion.

Verifies that all 4 previously-dropped StyleFingerprint fields
(transition_style, layering_style, recipe_preferences, color_tendencies)
are now exposed in style_constraints via _extract_fe_fields(), and that
user.j2 renders all style sections correctly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent

TemplateInfo.model_rebuild()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_full_fingerprint() -> StyleFingerprint:
    """Build a StyleFingerprint with all fields populated."""
    return StyleFingerprint(
        creator_id="test_creator",
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.8,
            density_preference=0.5,
            section_change_aggression=0.3,
        ),
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=250.0,
            overlap_tendency=0.4,
            variety_score=0.7,
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=2.5,
            max_layers=4,
            blend_mode_preference="add",
        ),
        recipe_preferences={"chase": 0.9, "strobe": 0.2, "wash": 0.6},
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.6,
            contrast_preference=0.75,
            temperature_preference=0.4,
        ),
        corpus_sequence_count=42,
    )


def _make_stage(fp: StyleFingerprint | None) -> GroupPlannerStage:
    """Build a minimal GroupPlannerStage with a real or absent StyleFingerprint."""
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

    # Use a real FEArtifactBundle with only style_fingerprint set
    fe_bundle = FEArtifactBundle(style_fingerprint=fp)

    return GroupPlannerStage(
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        fe_bundle=fe_bundle,
    )


# ---------------------------------------------------------------------------
# Test 1: style_constraints contains all four new keys
# ---------------------------------------------------------------------------


def test_style_constraints_contains_all_new_keys() -> None:
    """_extract_fe_fields() exposes transition_style, layering_style, recipe_preferences,
    and color_tendencies in style_constraints when StyleFingerprint has all fields.
    """
    stage = _make_stage(_make_full_fingerprint())
    result = stage._extract_fe_fields(section_id="test_section")

    assert "style_constraints" in result, "style_constraints must be present"
    sc = result["style_constraints"]
    assert "transition_style" in sc, "transition_style must be in style_constraints"
    assert "layering_style" in sc, "layering_style must be in style_constraints"
    assert "recipe_preferences" in sc, "recipe_preferences must be in style_constraints"
    assert "color_tendencies" in sc, "color_tendencies must be in style_constraints"


# ---------------------------------------------------------------------------
# Test 2: transition_style has expected keys
# ---------------------------------------------------------------------------


def test_transition_style_has_expected_keys() -> None:
    """transition_style dict contains preferred_gap_ms, overlap_tendency, variety_score."""
    stage = _make_stage(_make_full_fingerprint())
    result = stage._extract_fe_fields(section_id="test_section")

    ts = result["style_constraints"]["transition_style"]
    assert "preferred_gap_ms" in ts, "transition_style must have preferred_gap_ms"
    assert "overlap_tendency" in ts, "transition_style must have overlap_tendency"
    assert "variety_score" in ts, "transition_style must have variety_score"
    assert ts["preferred_gap_ms"] == 250.0
    assert ts["overlap_tendency"] == 0.4
    assert ts["variety_score"] == 0.7


# ---------------------------------------------------------------------------
# Test 3: layering_style has expected keys
# ---------------------------------------------------------------------------


def test_layering_style_has_expected_keys() -> None:
    """layering_style dict contains mean_layers, max_layers, blend_mode_preference."""
    stage = _make_stage(_make_full_fingerprint())
    result = stage._extract_fe_fields(section_id="test_section")

    ls = result["style_constraints"]["layering_style"]
    assert "mean_layers" in ls, "layering_style must have mean_layers"
    assert "max_layers" in ls, "layering_style must have max_layers"
    assert "blend_mode_preference" in ls, "layering_style must have blend_mode_preference"
    assert ls["mean_layers"] == 2.5
    assert ls["max_layers"] == 4
    assert ls["blend_mode_preference"] == "add"


# ---------------------------------------------------------------------------
# Test 4: recipe_preferences is a dict with string keys and float values
# ---------------------------------------------------------------------------


def test_recipe_preferences_dict_structure() -> None:
    """recipe_preferences is a plain dict with string keys and float values."""
    stage = _make_stage(_make_full_fingerprint())
    result = stage._extract_fe_fields(section_id="test_section")

    rp = result["style_constraints"]["recipe_preferences"]
    assert isinstance(rp, dict), "recipe_preferences must be a dict"
    for k, v in rp.items():
        assert isinstance(k, str), f"key {k!r} must be a string"
        assert isinstance(v, float), f"value {v!r} for key {k!r} must be a float"
    assert rp == {"chase": 0.9, "strobe": 0.2, "wash": 0.6}


# ---------------------------------------------------------------------------
# Test 5: color_tendencies has expected keys
# ---------------------------------------------------------------------------


def test_color_tendencies_has_expected_keys() -> None:
    """color_tendencies dict contains palette_complexity, contrast_preference,
    temperature_preference.
    """
    stage = _make_stage(_make_full_fingerprint())
    result = stage._extract_fe_fields(section_id="test_section")

    ct = result["style_constraints"]["color_tendencies"]
    assert "palette_complexity" in ct, "color_tendencies must have palette_complexity"
    assert "contrast_preference" in ct, "color_tendencies must have contrast_preference"
    assert "temperature_preference" in ct, "color_tendencies must have temperature_preference"
    assert ct["palette_complexity"] == 0.6
    assert ct["contrast_preference"] == 0.75
    assert ct["temperature_preference"] == 0.4


# ---------------------------------------------------------------------------
# Test 6: style_fingerprint=None → style_constraints absent
# ---------------------------------------------------------------------------


def test_style_fingerprint_none_graceful() -> None:
    """When style_fingerprint is None, style_constraints is absent from result."""
    stage = _make_stage(None)
    result = stage._extract_fe_fields(section_id="test_section")

    assert "style_constraints" not in result, (
        "style_constraints must be absent when style_fingerprint is None"
    )


# ---------------------------------------------------------------------------
# Test 7: user.j2 renders transition_style section
# ---------------------------------------------------------------------------


def test_user_j2_renders_transition_style() -> None:
    """user.j2 renders 'Transitions:' line when style_constraints has transition_style."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("user.j2")

    output = template.render(
        section_id="verse_1",
        section_name="Verse 1",
        start_ms=0,
        end_ms=15000,
        section_duration_bars=8,
        section_duration_beats=32,
        available_bars=8,
        section_max_bar=8,
        energy_target="MED",
        motion_density="MODERATE",
        choreography_style="ABSTRACT",
        primary_focus_targets=["MEGA_TREE_01"],
        secondary_targets=[],
        notes=None,
        theme_ref_json='{"theme": "test"}',
        palette_ref_json='{"palette": "test"}',
        motif_ids=["motif_1"],
        motif_catalog_summary=None,
        display_graph=MagicMock(groups=[], groups_by_role={}),
        display_graph_zones=[],
        display_graph_splits={},
        display_graph_spatial=None,
        template_catalog=MagicMock(entries=[]),
        layer_intents=[],
        lyric_context=None,
        color_arc=None,
        propensity_hints=None,
        style_constraints={
            "timing_style": {
                "beat_alignment_strictness": 0.8,
                "density_preference": 0.5,
                "section_change_aggression": 0.3,
            },
            "transition_style": {
                "preferred_gap_ms": 250.0,
                "overlap_tendency": 0.4,
                "variety_score": 0.7,
            },
        },
    )

    assert "Transitions:" in output, "user.j2 must render 'Transitions:' when transition_style set"


# ---------------------------------------------------------------------------
# Test 8: user.j2 renders all five style sections
# ---------------------------------------------------------------------------


def test_user_j2_renders_all_style_sections() -> None:
    """user.j2 renders all style sections when all style_constraints fields are present."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("user.j2")

    output = template.render(
        section_id="chorus_1",
        section_name="Chorus 1",
        start_ms=15000,
        end_ms=45000,
        section_duration_bars=16,
        section_duration_beats=64,
        available_bars=16,
        section_max_bar=16,
        energy_target="HIGH",
        motion_density="BUSY",
        choreography_style="SYNCHRONIZED",
        primary_focus_targets=["MEGA_TREE_01"],
        secondary_targets=[],
        notes=None,
        theme_ref_json='{"theme": "test"}',
        palette_ref_json='{"palette": "test"}',
        motif_ids=["motif_1"],
        motif_catalog_summary=None,
        display_graph=MagicMock(groups=[], groups_by_role={}),
        display_graph_zones=[],
        display_graph_splits={},
        display_graph_spatial=None,
        template_catalog=MagicMock(entries=[]),
        layer_intents=[],
        lyric_context=None,
        color_arc=None,
        propensity_hints=None,
        style_constraints={
            "timing_style": {
                "beat_alignment_strictness": 0.8,
                "density_preference": 0.5,
                "section_change_aggression": 0.3,
            },
            "transition_style": {
                "preferred_gap_ms": 250.0,
                "overlap_tendency": 0.4,
                "variety_score": 0.7,
            },
            "layering_style": {
                "mean_layers": 2.5,
                "max_layers": 4,
                "blend_mode_preference": "add",
            },
            "recipe_preferences": {"chase": 0.9, "strobe": 0.2},
            "color_tendencies": {
                "palette_complexity": 0.6,
                "contrast_preference": 0.75,
                "temperature_preference": 0.4,
            },
        },
    )

    assert "Transitions:" in output, "user.j2 must render 'Transitions:' section"
    assert "Layering:" in output, "user.j2 must render 'Layering:' section"
    assert "Recipe preferences:" in output, "user.j2 must render 'Recipe preferences:' section"
    assert "Color tendencies:" in output, "user.j2 must render 'Color tendencies:' section"
    assert "Timing:" in output, "user.j2 must render 'Timing:' section"
