"""Tests for Style Fingerprint output models."""

from twinklr.core.feature_engineering.models.style import (
    ColorStyleProfile,
    LayeringStyleProfile,
    StyleBlend,
    StyleEvolution,
    StyleFingerprint,
    TimingStyleProfile,
    TransitionStyleProfile,
)


def test_transition_style_profile() -> None:
    p = TransitionStyleProfile(
        preferred_gap_ms=50.0,
        overlap_tendency=0.3,
        variety_score=0.7,
    )
    assert p.preferred_gap_ms == 50.0
    assert 0.0 <= p.overlap_tendency <= 1.0


def test_color_style_profile() -> None:
    p = ColorStyleProfile(
        palette_complexity=0.6,
        contrast_preference=0.5,
        temperature_preference=0.7,
    )
    assert p.palette_complexity == 0.6


def test_timing_style_profile() -> None:
    p = TimingStyleProfile(
        beat_alignment_strictness=0.8,
        density_preference=0.5,
        section_change_aggression=0.6,
    )
    assert p.beat_alignment_strictness == 0.8


def test_layering_style_profile() -> None:
    p = LayeringStyleProfile(
        mean_layers=2.5,
        max_layers=4,
        blend_mode_preference="screen",
    )
    assert p.mean_layers == 2.5
    assert p.max_layers == 4


def test_style_fingerprint_assembly() -> None:
    fp = StyleFingerprint(
        creator_id="creator-1",
        recipe_preferences={"single_strand": 0.8, "bars": 0.5},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=50.0,
            overlap_tendency=0.3,
            variety_score=0.7,
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.6,
            contrast_preference=0.5,
            temperature_preference=0.7,
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.8,
            density_preference=0.5,
            section_change_aggression=0.6,
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=2.5,
            max_layers=4,
            blend_mode_preference="screen",
        ),
        corpus_sequence_count=10,
    )
    assert fp.creator_id == "creator-1"
    assert fp.recipe_preferences["single_strand"] == 0.8
    assert fp.corpus_sequence_count == 10


def test_style_blend() -> None:
    fp = StyleFingerprint(
        creator_id="c1",
        recipe_preferences={},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=0.0, overlap_tendency=0.5, variety_score=0.5
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.5, contrast_preference=0.5, temperature_preference=0.5
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.5, density_preference=0.5, section_change_aggression=0.5
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=1.0, max_layers=1, blend_mode_preference="normal"
        ),
        corpus_sequence_count=1,
    )
    blend = StyleBlend(
        base_style=fp,
        accent_style=None,
        blend_ratio=0.0,
        evolution_params=None,
    )
    assert blend.base_style.creator_id == "c1"
    assert blend.accent_style is None


def test_style_evolution() -> None:
    evo = StyleEvolution(
        direction="more_complex",
        intensity=0.5,
    )
    assert evo.direction == "more_complex"
    assert evo.intensity == 0.5


def test_style_blend_with_evolution() -> None:
    fp1 = StyleFingerprint(
        creator_id="c1",
        recipe_preferences={"bars": 0.9},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=10.0, overlap_tendency=0.2, variety_score=0.8
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.7, contrast_preference=0.6, temperature_preference=0.4
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.9, density_preference=0.6, section_change_aggression=0.7
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=3.0, max_layers=5, blend_mode_preference="add"
        ),
        corpus_sequence_count=20,
    )
    fp2 = StyleFingerprint(
        creator_id="c2",
        recipe_preferences={"sparkle": 0.7},
        transition_style=TransitionStyleProfile(
            preferred_gap_ms=100.0, overlap_tendency=0.8, variety_score=0.3
        ),
        color_tendencies=ColorStyleProfile(
            palette_complexity=0.3, contrast_preference=0.8, temperature_preference=0.9
        ),
        timing_style=TimingStyleProfile(
            beat_alignment_strictness=0.4, density_preference=0.3, section_change_aggression=0.2
        ),
        layering_style=LayeringStyleProfile(
            mean_layers=1.5, max_layers=2, blend_mode_preference="screen"
        ),
        corpus_sequence_count=5,
    )
    blend = StyleBlend(
        base_style=fp1,
        accent_style=fp2,
        blend_ratio=0.3,
        evolution_params=StyleEvolution(direction="warmer", intensity=0.4),
    )
    assert blend.blend_ratio == 0.3
    assert blend.evolution_params is not None
    assert blend.evolution_params.direction == "warmer"
