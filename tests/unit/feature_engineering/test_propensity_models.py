"""Tests for Propensity Miner output models."""

from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    EffectModelAntiAffinity,
    PropensityIndex,
)


def test_effect_model_affinity_creation() -> None:
    a = EffectModelAffinity(
        effect_family="single_strand",
        model_type="megatree",
        frequency=0.85,
        exclusivity=0.3,
        corpus_support=42,
    )
    assert a.effect_family == "single_strand"
    assert a.model_type == "megatree"
    assert a.frequency == 0.85
    assert a.corpus_support == 42


def test_effect_model_anti_affinity_creation() -> None:
    aa = EffectModelAntiAffinity(
        effect_family="matrix",
        model_type="candy_cane",
        corpus_support=5,
    )
    assert aa.effect_family == "matrix"
    assert aa.model_type == "candy_cane"


def test_propensity_index_assembly() -> None:
    affinity = EffectModelAffinity(
        effect_family="single_strand",
        model_type="megatree",
        frequency=0.85,
        exclusivity=0.3,
        corpus_support=42,
    )
    anti = EffectModelAntiAffinity(
        effect_family="matrix",
        model_type="candy_cane",
        corpus_support=5,
    )
    index = PropensityIndex(
        schema_version="v1.0.0",
        affinities=(affinity,),
        anti_affinities=(anti,),
    )
    assert len(index.affinities) == 1
    assert len(index.anti_affinities) == 1
    assert index.schema_version == "v1.0.0"


def test_propensity_index_empty() -> None:
    index = PropensityIndex(
        schema_version="v1.0.0",
        affinities=(),
        anti_affinities=(),
    )
    assert len(index.affinities) == 0
    assert len(index.anti_affinities) == 0


def test_affinity_frequency_bounds() -> None:
    a = EffectModelAffinity(
        effect_family="bars",
        model_type="arch",
        frequency=0.0,
        exclusivity=1.0,
        corpus_support=1,
    )
    assert 0.0 <= a.frequency <= 1.0
    assert 0.0 <= a.exclusivity <= 1.0
