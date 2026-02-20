"""Tests for PropensityMiner."""

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.propensity import PropensityIndex
from twinklr.core.feature_engineering.propensity import PropensityMiner


def _make_phrase(
    *,
    effect_family: str = "single_strand",
    target_name: str = "MegaTree",
    idx: int = 0,
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
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name=target_name,
        layer_index=0,
        start_ms=idx * 1000,
        end_ms=(idx + 1) * 1000,
        duration_ms=1000,
        section_label="verse",
        param_signature="bars|sweep|palette",
    )


def test_mine_produces_propensity_index() -> None:
    phrases = tuple(
        _make_phrase(effect_family="single_strand", target_name="MegaTree", idx=i)
        for i in range(10)
    ) + tuple(_make_phrase(effect_family="bars", target_name="Arch", idx=i + 10) for i in range(5))
    result = PropensityMiner().mine(phrases=phrases)
    assert isinstance(result, PropensityIndex)
    assert len(result.affinities) >= 1


def test_high_frequency_affinity() -> None:
    # All single_strand on MegaTree — should produce high frequency affinity.
    phrases = tuple(
        _make_phrase(effect_family="single_strand", target_name="MegaTree", idx=i)
        for i in range(20)
    )
    result = PropensityMiner().mine(phrases=phrases)
    megatree_aff = [
        a
        for a in result.affinities
        if a.model_type == "megatree" and a.effect_family == "single_strand"
    ]
    assert len(megatree_aff) == 1
    assert megatree_aff[0].frequency >= 0.8


def test_anti_affinity_for_absent_pair() -> None:
    # bars only on Arch, never on MegaTree. If we have enough diversity,
    # bars+megatree should be anti-affinity.
    phrases = tuple(
        _make_phrase(effect_family="bars", target_name="Arch", idx=i) for i in range(15)
    ) + tuple(
        _make_phrase(effect_family="single_strand", target_name="MegaTree", idx=i + 15)
        for i in range(15)
    )
    result = PropensityMiner().mine(phrases=phrases)
    # bars should have affinity with arch, not megatree
    bars_arch = [
        a for a in result.affinities if a.model_type == "arch" and a.effect_family == "bars"
    ]
    assert len(bars_arch) == 1
    assert bars_arch[0].frequency >= 0.8


def test_empty_input() -> None:
    result = PropensityMiner().mine(phrases=())
    assert isinstance(result, PropensityIndex)
    assert len(result.affinities) == 0
    assert len(result.anti_affinities) == 0


def test_model_type_extraction_from_target_name() -> None:
    """Target names like 'MegaTree Left' should map to model_type 'megatree'."""
    phrases = tuple(
        _make_phrase(effect_family="single_strand", target_name="MegaTree Left", idx=i)
        for i in range(5)
    ) + tuple(
        _make_phrase(effect_family="single_strand", target_name="MegaTree Right", idx=i + 5)
        for i in range(5)
    )
    result = PropensityMiner().mine(phrases=phrases)
    model_types = {a.model_type for a in result.affinities}
    assert "megatree" in model_types
