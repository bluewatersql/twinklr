"""Tests for StyleFingerprintExtractor."""

from twinklr.core.feature_engineering.models.color_narrative import ColorNarrativeRow
from twinklr.core.feature_engineering.models.layering import LayeringFeatureRow
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.style import StyleFingerprint
from twinklr.core.feature_engineering.models.transitions import (
    TransitionGraph,
    TransitionRecord,
    TransitionType,
)
from twinklr.core.feature_engineering.style import StyleFingerprintExtractor


def _make_phrase(
    *,
    effect_family: str = "single_strand",
    color_class: ColorClass = ColorClass.PALETTE,
    energy_class: EnergyClass = EnergyClass.MID,
    section_label: str = "verse",
    idx: int = 0,
    onset_sync_score: float | None = 0.8,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{idx}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt_{idx}",
        effect_type="Bars",
        effect_family=effect_family,
        motion_class=MotionClass.SWEEP,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="MegaTree",
        layer_index=0,
        start_ms=idx * 1000,
        end_ms=(idx + 1) * 1000,
        duration_ms=1000,
        section_label=section_label,
        onset_sync_score=onset_sync_score,
        param_signature="bars|sweep|palette",
    )


def _make_layering_row(
    mean_layers: float = 2.0, max_layers: int = 3
) -> LayeringFeatureRow:
    return LayeringFeatureRow(
        schema_version="v1.7.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        phrase_count=10,
        max_concurrent_layers=max_layers,
        mean_concurrent_layers=mean_layers,
        hierarchy_transitions=5,
        overlap_pairs=3,
        same_target_overlap_pairs=1,
        collision_score=0.2,
    )


def _make_color_row(
    section_label: str,
    section_index: int,
    dominant_color_class: str = "palette",
    contrast_shift: float = 0.0,
) -> ColorNarrativeRow:
    return ColorNarrativeRow(
        schema_version="v1.8.0",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        section_label=section_label,
        section_index=section_index,
        phrase_count=5,
        dominant_color_class=dominant_color_class,
        contrast_shift_from_prev=contrast_shift,
        hue_family_movement="section_start" if section_index == 0 else "hold",
    )


def _make_transition_graph(gap_ms: int = 50) -> TransitionGraph:
    return TransitionGraph(
        schema_version="v1.6.0",
        graph_version="v1",
        total_transitions=2,
        total_nodes=2,
        total_edges=1,
        transitions=(
            TransitionRecord(
                sequence_file_id="seq-1",
                package_id="pkg-1",
                from_phrase_id="ph_0",
                to_phrase_id="ph_1",
                from_template_id="tpl_a",
                to_template_id="tpl_b",
                from_end_ms=1000,
                to_start_ms=1000 + gap_ms,
                gap_ms=gap_ms,
                transition_type=TransitionType.CROSSFADE,
            ),
            TransitionRecord(
                sequence_file_id="seq-1",
                package_id="pkg-1",
                from_phrase_id="ph_1",
                to_phrase_id="ph_2",
                from_template_id="tpl_b",
                to_template_id="tpl_a",
                from_end_ms=2000,
                to_start_ms=2000 + gap_ms,
                gap_ms=gap_ms,
                transition_type=TransitionType.HARD_CUT,
            ),
        ),
    )


def test_extract_produces_style_fingerprint() -> None:
    phrases = tuple(_make_phrase(idx=i) for i in range(10))
    layering = (_make_layering_row(),)
    color_rows = (
        _make_color_row("intro", 0),
        _make_color_row("verse", 1),
    )
    transition_graph = _make_transition_graph()

    result = StyleFingerprintExtractor().extract(
        creator_id="creator-1",
        phrases=phrases,
        layering_rows=layering,
        color_rows=color_rows,
        transition_graph=transition_graph,
    )
    assert isinstance(result, StyleFingerprint)
    assert result.creator_id == "creator-1"
    assert result.corpus_sequence_count >= 1


def test_recipe_preferences_from_effect_families() -> None:
    phrases = tuple(
        _make_phrase(effect_family="single_strand", idx=i) for i in range(8)
    ) + tuple(
        _make_phrase(effect_family="bars", idx=i + 8) for i in range(2)
    )
    result = StyleFingerprintExtractor().extract(
        creator_id="c1",
        phrases=phrases,
        layering_rows=(_make_layering_row(),),
        color_rows=(),
        transition_graph=None,
    )
    assert result.recipe_preferences["single_strand"] > result.recipe_preferences["bars"]


def test_layering_style_from_rows() -> None:
    layering = (_make_layering_row(mean_layers=3.5, max_layers=6),)
    result = StyleFingerprintExtractor().extract(
        creator_id="c1",
        phrases=tuple(_make_phrase(idx=i) for i in range(5)),
        layering_rows=layering,
        color_rows=(),
        transition_graph=None,
    )
    assert result.layering_style.mean_layers == 3.5
    assert result.layering_style.max_layers == 6


def test_color_tendencies_from_narrative() -> None:
    color_rows = (
        _make_color_row("intro", 0, "mono", 0.0),
        _make_color_row("verse", 1, "palette", 0.5),
        _make_color_row("chorus", 2, "multi", 0.8),
    )
    result = StyleFingerprintExtractor().extract(
        creator_id="c1",
        phrases=tuple(_make_phrase(idx=i) for i in range(5)),
        layering_rows=(),
        color_rows=color_rows,
        transition_graph=None,
    )
    assert result.color_tendencies.contrast_preference > 0.0


def test_empty_inputs() -> None:
    result = StyleFingerprintExtractor().extract(
        creator_id="c1",
        phrases=(),
        layering_rows=(),
        color_rows=(),
        transition_graph=None,
    )
    assert isinstance(result, StyleFingerprint)
    assert result.corpus_sequence_count == 0
