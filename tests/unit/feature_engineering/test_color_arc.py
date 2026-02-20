"""Tests for ColorArcExtractor."""

from twinklr.core.feature_engineering.color_arc import ColorArcExtractor
from twinklr.core.feature_engineering.models.color_arc import SongColorArc
from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)


def _make_phrase(
    *,
    section_label: str,
    section_index: int = 0,
    color_class: ColorClass = ColorClass.PALETTE,
    energy_class: EnergyClass = EnergyClass.MID,
    target_name: str = "MegaTree",
    start_ms: int = 0,
    duration_ms: int = 4000,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{section_label}_{section_index}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{section_label}_{section_index}",
        effect_type="Bars",
        effect_family="single_strand",
        motion_class=MotionClass.SWEEP,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name=target_name,
        layer_index=0,
        start_ms=start_ms,
        end_ms=start_ms + duration_ms,
        duration_ms=duration_ms,
        section_label=section_label,
        param_signature="bars|sweep|palette",
    )


def _make_color_row(
    *,
    section_label: str,
    section_index: int,
    dominant_color_class: str = "palette",
    contrast_shift_from_prev: float = 0.0,
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
        hue_family_movement="section_start" if section_index == 0 else "hold",
    )


def _make_phrases_with_sections(sections: list[str]) -> tuple[EffectPhrase, ...]:
    return tuple(
        _make_phrase(section_label=s, section_index=i, start_ms=i * 4000)
        for i, s in enumerate(sections)
    )


def _make_color_narrative_rows(
    sections: list[str],
    dominant_color_class: str = "palette",
) -> tuple[ColorNarrativeRow, ...]:
    return tuple(
        _make_color_row(
            section_label=s,
            section_index=i,
            dominant_color_class=dominant_color_class,
        )
        for i, s in enumerate(sections)
    )


def test_extract_produces_song_color_arc() -> None:
    phrases = _make_phrases_with_sections(["intro", "verse", "chorus"])
    color_rows = _make_color_narrative_rows(["intro", "verse", "chorus"])
    result = ColorArcExtractor().extract(phrases=phrases, color_narrative=color_rows)
    assert isinstance(result, SongColorArc)
    assert len(result.palette_library) >= 1
    assert len(result.section_assignments) == 3


def test_contrast_shift_generates_transition_rule() -> None:
    color_rows = (
        _make_color_row(
            section_label="verse",
            section_index=0,
            dominant_color_class="mono",
            contrast_shift_from_prev=0.0,
        ),
        _make_color_row(
            section_label="chorus",
            section_index=1,
            dominant_color_class="multi",
            contrast_shift_from_prev=0.65,
        ),
    )
    result = ColorArcExtractor().extract(
        phrases=_make_phrases_with_sections(["verse", "chorus"]),
        color_narrative=color_rows,
    )
    assert len(result.transition_rules) >= 1
    assert result.transition_rules[0].from_palette_id != result.transition_rules[0].to_palette_id


def test_mono_section_gets_monochrome_palette() -> None:
    color_rows = _make_color_narrative_rows(["chorus"], dominant_color_class="mono")
    result = ColorArcExtractor().extract(
        phrases=_make_phrases_with_sections(["chorus"]),
        color_narrative=color_rows,
    )
    palette = next(
        p
        for p in result.palette_library
        if p.palette_id == result.section_assignments[0].palette_id
    )
    assert palette.temperature in ("warm", "cool", "neutral")
    assert len(palette.colors) <= 2


def test_arc_curve_matches_section_count() -> None:
    phrases = _make_phrases_with_sections(["intro", "verse", "chorus", "outro"])
    color_rows = _make_color_narrative_rows(["intro", "verse", "chorus", "outro"])
    result = ColorArcExtractor().extract(phrases=phrases, color_narrative=color_rows)
    assert len(result.arc_curve) >= 2
    assert result.arc_curve[0].position_pct == 0.0
    assert result.arc_curve[-1].position_pct == 1.0


def test_empty_inputs_produce_empty_arc() -> None:
    result = ColorArcExtractor().extract(phrases=(), color_narrative=())
    assert isinstance(result, SongColorArc)
    assert len(result.palette_library) == 0
    assert len(result.section_assignments) == 0


# --- Bug fixes: per-sequence energy, palette rotation, cross-row contrast ---


def _make_phrase_for_seq(
    *,
    package_id: str,
    sequence_file_id: str,
    energy_class: EnergyClass = EnergyClass.MID,
) -> EffectPhrase:
    """Helper that creates a phrase with a specific sequence identity."""
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{package_id}_{sequence_file_id}",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt_{package_id}",
        effect_type="Bars",
        effect_family="single_strand",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=energy_class,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="MegaTree",
        layer_index=0,
        start_ms=0,
        end_ms=4000,
        duration_ms=4000,
        section_label="__none__",
        param_signature="bars|sweep|palette",
    )


def _make_color_row_for_seq(
    *,
    package_id: str,
    sequence_file_id: str,
    dominant_color_class: str = "palette",
) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        section_label="__none__",
        section_index=0,
        phrase_count=5,
        dominant_color_class=dominant_color_class,
        contrast_shift_from_prev=0.0,
        hue_family_movement="section_start",
    )


def test_different_energy_per_sequence_produces_different_arc_values() -> None:
    """Two sequences with same section_label but different energy must produce
    different arc keyframe temperatures."""
    phrases = (
        _make_phrase_for_seq(
            package_id="pkgA", sequence_file_id="seqA",
            energy_class=EnergyClass.LOW,
        ),
        _make_phrase_for_seq(
            package_id="pkgB", sequence_file_id="seqB",
            energy_class=EnergyClass.BURST,
        ),
    )
    rows = (
        _make_color_row_for_seq(package_id="pkgA", sequence_file_id="seqA"),
        _make_color_row_for_seq(package_id="pkgB", sequence_file_id="seqB"),
    )
    result = ColorArcExtractor().extract(phrases=phrases, color_narrative=rows)
    assert len(result.arc_curve) == 2
    assert result.arc_curve[0].temperature != result.arc_curve[1].temperature


def test_palette_rotation_across_same_section_index() -> None:
    """Three rows all with section_index=0 should still get different palettes
    via rotation by global row position."""
    rows = tuple(
        _make_color_row_for_seq(
            package_id=f"pkg{i}", sequence_file_id=f"seq{i}",
        )
        for i in range(3)
    )
    phrases = tuple(
        _make_phrase_for_seq(package_id=f"pkg{i}", sequence_file_id=f"seq{i}")
        for i in range(3)
    )
    result = ColorArcExtractor().extract(phrases=phrases, color_narrative=rows)
    palette_ids = [a.palette_id for a in result.section_assignments]
    assert len(set(palette_ids)) > 1, (
        f"Expected palette variety but got {palette_ids}"
    )
