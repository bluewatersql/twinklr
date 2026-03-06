"""Tests for Phase 05 COL-03/COL-04: Color context injection into section planning.

Verifies that _extract_fe_fields() exposes color_narrative_row and arc_keyframe,
and that user.j2 renders both Color Narrative and Arc Position sections.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage
from twinklr.core.feature_engineering.loader import FEArtifactBundle
from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    SectionColorAssignment,
    SongColorArc,
)
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog
from twinklr.core.sequencer.templates.group.library import TemplateInfo
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent

TemplateInfo.model_rebuild()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(fe_bundle: FEArtifactBundle | None) -> GroupPlannerStage:
    """Build a minimal GroupPlannerStage with the given FEArtifactBundle."""
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

    return GroupPlannerStage(
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        fe_bundle=fe_bundle,
    )


def _make_color_row(
    *,
    section_label: str,
    section_index: int = 0,
    dominant_color_class: str = "palette",
    contrast_shift_from_prev: float = 0.2,
    hue_family_movement: str = "hold",
) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label=section_label,
        section_index=section_index,
        phrase_count=5,
        dominant_color_class=dominant_color_class,
        contrast_shift_from_prev=contrast_shift_from_prev,
        hue_family_movement=hue_family_movement,
    )


def _make_song_color_arc_with_curve(sections: list[str]) -> SongColorArc:
    """Build a minimal SongColorArc with section_assignments and arc_curve."""
    n = len(sections)
    assignments = tuple(
        SectionColorAssignment(
            package_id="pkg-1",
            sequence_file_id="seq-1",
            section_label=s,
            section_index=i,
            palette_id=f"pal_test_{i}",
            spatial_mapping={},
            shift_timing="section_boundary",
            contrast_target=0.2,
        )
        for i, s in enumerate(sections)
    )
    arc_curve = tuple(
        ArcKeyframe(
            position_pct=round(i / max(n - 1, 1), 4),
            temperature=0.5,
            saturation=0.7,
            contrast=0.2,
        )
        for i in range(n)
    )
    return SongColorArc(
        palette_library=(),
        section_assignments=assignments,
        arc_curve=arc_curve,
        transition_rules=(),
    )


def _base_j2_render_kwargs() -> dict:
    """Minimal valid kwargs for rendering user.j2 without FE color fields."""
    return {
        "section_id": "verse_1",
        "section_name": "Verse 1",
        "start_ms": 0,
        "end_ms": 15000,
        "section_duration_bars": 8,
        "section_duration_beats": 32,
        "available_bars": 8,
        "section_max_bar": 8,
        "energy_target": "MED",
        "motion_density": "MODERATE",
        "choreography_style": "ABSTRACT",
        "primary_focus_targets": ["MEGA_TREE_01"],
        "secondary_targets": [],
        "notes": None,
        "theme_ref_json": '{"theme": "test"}',
        "palette_ref_json": '{"palette": "test"}',
        "motif_ids": ["motif_1"],
        "motif_catalog_summary": None,
        "display_graph": MagicMock(groups=[], groups_by_role={}),
        "display_graph_zones": [],
        "display_graph_splits": {},
        "display_graph_spatial": None,
        "template_catalog": MagicMock(entries=[]),
        "layer_intents": [],
        "lyric_context": None,
        "color_arc": None,
        "propensity_hints": None,
        "style_constraints": None,
        "color_narrative_row": None,
        "arc_keyframe": None,
    }


# ---------------------------------------------------------------------------
# Test 4: _extract_fe_fields() includes color_narrative_row when matching section
# ---------------------------------------------------------------------------


def test_extract_fe_fields_includes_color_narrative_row() -> None:
    """_extract_fe_fields() sets color_narrative_row when color_narrative has a matching row.

    When fe_bundle.color_narrative contains a ColorNarrativeRow whose
    section_label matches section_id, result must include 'color_narrative_row'.
    """
    cnr = _make_color_row(
        section_label="verse_1",
        section_index=0,
        dominant_color_class="palette",
        contrast_shift_from_prev=0.3,
    )
    fe_bundle = FEArtifactBundle(color_narrative=(cnr,))
    stage = _make_stage(fe_bundle)

    result = stage._extract_fe_fields(section_id="verse_1")

    assert "color_narrative_row" in result, (
        "_extract_fe_fields must include 'color_narrative_row' when section matches"
    )
    cnr_dict = result["color_narrative_row"]
    assert isinstance(cnr_dict, dict), "color_narrative_row must be a dict"
    assert cnr_dict.get("section_label") == "verse_1", (
        f"color_narrative_row.section_label must be 'verse_1', got {cnr_dict.get('section_label')}"
    )
    assert cnr_dict.get("dominant_color_class") == "palette", (
        "color_narrative_row.dominant_color_class must be 'palette'"
    )


# ---------------------------------------------------------------------------
# Test 5: _extract_fe_fields() includes arc_keyframe when color_arc has arc_curve
# ---------------------------------------------------------------------------


def test_extract_fe_fields_includes_arc_keyframe() -> None:
    """_extract_fe_fields() sets arc_keyframe when color_arc has arc_curve entries.

    When fe_bundle.color_arc is populated with arc_curve and color_narrative
    has a matching row, result must include 'arc_keyframe' with expected keys.
    """
    sections = ["verse_1", "chorus_1", "outro_1"]
    color_arc = _make_song_color_arc_with_curve(sections)
    color_narrative = tuple(
        _make_color_row(section_label=s, section_index=i) for i, s in enumerate(sections)
    )

    fe_bundle = FEArtifactBundle(color_arc=color_arc, color_narrative=color_narrative)
    stage = _make_stage(fe_bundle)

    result = stage._extract_fe_fields(section_id="chorus_1")

    assert "arc_keyframe" in result, (
        "_extract_fe_fields must include 'arc_keyframe' when color_arc has arc_curve"
    )
    kf = result["arc_keyframe"]
    assert isinstance(kf, dict), "arc_keyframe must be a dict"
    assert "position_pct" in kf, "arc_keyframe must have 'position_pct'"
    assert "temperature" in kf, "arc_keyframe must have 'temperature'"
    assert "saturation" in kf, "arc_keyframe must have 'saturation'"
    assert "contrast" in kf, "arc_keyframe must have 'contrast'"


# ---------------------------------------------------------------------------
# Test 6: _extract_fe_fields() gracefully handles color_arc=None
# ---------------------------------------------------------------------------


def test_extract_fe_fields_graceful_color_arc_none() -> None:
    """_extract_fe_fields() does not set arc_keyframe when color_arc is None.

    When fe_bundle.color_arc is None, result must NOT contain 'arc_keyframe'.
    """
    fe_bundle = FEArtifactBundle(color_arc=None)
    stage = _make_stage(fe_bundle)

    result = stage._extract_fe_fields(section_id="verse_1")

    assert "arc_keyframe" not in result, (
        "'arc_keyframe' must be absent from result when color_arc is None"
    )


# ---------------------------------------------------------------------------
# Test 7: user.j2 renders Color Narrative section when color_narrative_row present
# ---------------------------------------------------------------------------


def test_user_j2_renders_color_narrative() -> None:
    """user.j2 renders 'Color Narrative' section when color_narrative_row is provided."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("user.j2")

    kwargs = _base_j2_render_kwargs()
    kwargs["color_narrative_row"] = {
        "dominant_color_class": "palette",
        "contrast_shift_from_prev": 0.3,
        "hue_family_movement": "rising",
    }

    output = template.render(**kwargs)

    assert "Color Narrative" in output, (
        "user.j2 must render 'Color Narrative' when color_narrative_row is provided"
    )
    assert "palette" in output, "user.j2 must render dominant_color_class value 'palette'"


# ---------------------------------------------------------------------------
# Test 8: user.j2 renders Arc Position section when arc_keyframe present
# ---------------------------------------------------------------------------


def test_user_j2_renders_arc_keyframe() -> None:
    """user.j2 renders 'Arc Position' section when arc_keyframe is provided."""
    from jinja2 import Environment, FileSystemLoader

    template_dir = "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("user.j2")

    kwargs = _base_j2_render_kwargs()
    kwargs["arc_keyframe"] = {
        "position_pct": 0.5,
        "temperature": 0.6,
        "saturation": 0.75,
        "contrast": 0.4,
    }

    output = template.render(**kwargs)

    assert "Arc Position" in output, (
        "user.j2 must render 'Arc Position' when arc_keyframe is provided"
    )
    assert "Temperature" in output or "temperature" in output.lower(), (
        "user.j2 must render temperature field in Arc Position section"
    )
