"""Tests for Color Arc output models."""

from twinklr.core.feature_engineering.models.color_arc import (
    ArcKeyframe,
    ColorTransitionRule,
    NamedPalette,
    SectionColorAssignment,
    SongColorArc,
)


def test_named_palette_creation() -> None:
    p = NamedPalette(
        palette_id="pal_icy_blue",
        name="Icy Blue",
        colors=("#A8D8EA", "#E0F7FA", "#FFFFFF"),
        mood_tags=("calm", "winter"),
        temperature="cool",
    )
    assert p.palette_id == "pal_icy_blue"
    assert len(p.colors) == 3
    assert p.temperature == "cool"


def test_section_color_assignment_creation() -> None:
    a = SectionColorAssignment(
        schema_version="v1.0.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label="chorus",
        section_index=1,
        palette_id="pal_icy_blue",
        spatial_mapping={"group_megatree": "primary", "group_arch": "accent"},
        shift_timing="section_boundary",
        contrast_target=0.7,
    )
    assert a.section_label == "chorus"
    assert a.spatial_mapping["group_megatree"] == "primary"


def test_arc_keyframe_bounds() -> None:
    k = ArcKeyframe(position_pct=0.5, temperature=0.3, saturation=0.8, contrast=0.6)
    assert 0.0 <= k.position_pct <= 1.0


def test_song_color_arc_assembly() -> None:
    palette = NamedPalette(
        palette_id="pal_1",
        name="Test",
        colors=("#FF0000",),
        mood_tags=(),
        temperature="warm",
    )
    assignment = SectionColorAssignment(
        schema_version="v1.0.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label="intro",
        section_index=0,
        palette_id="pal_1",
        spatial_mapping={},
        shift_timing="section_boundary",
        contrast_target=0.5,
    )
    rule = ColorTransitionRule(
        from_palette_id="pal_1",
        to_palette_id="pal_1",
        transition_style="crossfade",
        duration_bars=2,
    )
    arc = SongColorArc(
        schema_version="v1.0.0",
        palette_library=(palette,),
        section_assignments=(assignment,),
        arc_curve=(ArcKeyframe(position_pct=0.0, temperature=0.5, saturation=0.7, contrast=0.5),),
        transition_rules=(rule,),
    )
    assert len(arc.palette_library) == 1
    assert len(arc.section_assignments) == 1
