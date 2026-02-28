"""Tests for EffectMetadataProfileBuilder.

Covers all 7 test cases from the spec:
1. Duration distribution (10 phrases -> correct p10, p50, p90)
2. Classification distribution (5 phrases -> correct modal + distribution)
3. Parameter profiles (preserved_params top values)
4. Layering behavior (stack role distribution, common partners)
5. Section placement (section frequencies, preferred sections)
6. Model affinities (from PropensityIndex, sorted by frequency)
7. Edge cases (0 stacks -> solo_ratio=1.0, no section_label, no preserved_params)
"""

from __future__ import annotations

from typing import Any

from twinklr.core.feature_engineering.metadata_profiles import (
    EffectMetadataProfileBuilder,
)
from twinklr.core.feature_engineering.models.metadata import (
    DurationDistribution,
    EffectMetadataProfile,
    EffectMetadataProfiles,
    LayeringBehavior,
    ParamFrequency,
    ParamProfile,
    SectionPlacement,
)
from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.propensity import (
    EffectModelAffinity,
    PropensityIndex,
)
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackCatalog,
    EffectStackLayer,
)
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole


def _make_phrase(
    *,
    effect_family: str = "bars",
    motion_class: MotionClass = MotionClass.SWEEP,
    color_class: ColorClass = ColorClass.PALETTE,
    energy_class: EnergyClass = EnergyClass.MID,
    continuity_class: ContinuityClass = ContinuityClass.SUSTAINED,
    spatial_class: SpatialClass = SpatialClass.MULTI_TARGET,
    duration_ms: int = 1000,
    section_label: str | None = "verse",
    target_name: str = "MegaTree",
    sequence_file_id: str = "seq-1",
    idx: int = 0,
) -> EffectPhrase:
    """Build a test phrase with sensible defaults."""
    return EffectPhrase(
        schema_version="v1.0.0",
        phrase_id=f"ph_{effect_family}_{idx}",
        package_id="pkg-1",
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt_{effect_family}_{idx}",
        effect_type=effect_family.title(),
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=color_class,
        energy_class=energy_class,
        continuity_class=continuity_class,
        spatial_class=spatial_class,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target_name,
        layer_index=0,
        start_ms=idx * duration_ms,
        end_ms=(idx + 1) * duration_ms,
        duration_ms=duration_ms,
        section_label=section_label,
        param_signature=f"sig_{effect_family}_{idx}",
    )


def _make_stack(
    *,
    layers: tuple[tuple[EffectPhrase, LayerRole, dict[str, Any]], ...],
    stack_idx: int = 0,
) -> EffectStack:
    """Build a test stack from (phrase, role, preserved_params) tuples."""
    stack_layers = tuple(
        EffectStackLayer(
            phrase=phrase,
            layer_role=role,
            blend_mode=BlendMode.NORMAL,
            mix=1.0,
            preserved_params=params,
        )
        for phrase, role, params in layers
    )
    first = layers[0][0]
    return EffectStack(
        stack_id=f"stack_{stack_idx}",
        package_id=first.package_id,
        sequence_file_id=first.sequence_file_id,
        target_name=first.target_name,
        model_type=None,
        start_ms=first.start_ms,
        end_ms=first.end_ms,
        duration_ms=first.duration_ms,
        section_label=first.section_label,
        layers=stack_layers,
        layer_count=len(stack_layers),
        stack_signature="|".join(l[0].effect_family for l in layers),
    )


def _get_profile(
    profiles: EffectMetadataProfiles, family: str
) -> EffectMetadataProfile:
    """Extract a single family profile from the collection."""
    for p in profiles.profiles:
        if p.effect_family == family:
            return p
    msg = f"No profile found for family '{family}'"
    raise ValueError(msg)


class TestDurationDistribution:
    """Test 1: Duration distribution with 10 phrases -> correct percentiles."""

    def test_duration_percentiles_computed_correctly(self) -> None:
        """10 phrases with known durations produce correct p10, p50, p90."""
        # Durations: 100, 200, 300, ..., 1000
        phrases = tuple(
            _make_phrase(effect_family="bars", duration_ms=(i + 1) * 100, idx=i)
            for i in range(10)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        dur = profile.duration

        assert dur.sample_count == 10
        assert dur.min_ms == 100
        assert dur.max_ms == 1000
        # p10 of [100..1000]: np.percentile(..., 10) = 190
        assert dur.p10_ms == 190
        # p50 = median = 550
        assert dur.p50_ms == 550
        # p90 = 910
        assert dur.p90_ms == 910
        assert dur.p25_ms == 325
        assert dur.p75_ms == 775
        # Mean = 550.0
        assert dur.mean_ms == 550.0


class TestClassificationDistribution:
    """Test 2: Classification distribution with 5 phrases."""

    def test_modal_and_distribution_correct(self) -> None:
        """3 sweep + 2 pulse -> motion_class modal = sweep, correct dist."""
        phrases = tuple(
            _make_phrase(
                effect_family="bars",
                motion_class=MotionClass.SWEEP,
                idx=i,
            )
            for i in range(3)
        ) + tuple(
            _make_phrase(
                effect_family="bars",
                motion_class=MotionClass.PULSE,
                idx=i + 3,
            )
            for i in range(2)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        assert profile.classification["motion_class"] == "sweep"
        motion_dist = profile.classification_distribution["motion_class"]
        assert motion_dist["sweep"] == 0.6
        assert motion_dist["pulse"] == 0.4


class TestParameterProfiles:
    """Test 3: Parameter profiles from preserved_params in stacks."""

    def test_top_param_values_extracted(self) -> None:
        """4x Left-Right + 1x Bounce -> top value Left-Right freq 0.8."""
        phrases_lr = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(4)
        )
        phrase_bounce = _make_phrase(effect_family="bars", idx=4)

        stacks_lr = tuple(
            _make_stack(
                layers=(
                    (p, LayerRole.BASE, {"chase_type1": "Left-Right"}),
                ),
                stack_idx=i,
            )
            for i, p in enumerate(phrases_lr)
        )
        stack_bounce = _make_stack(
            layers=(
                (phrase_bounce, LayerRole.BASE, {"chase_type1": "Bounce"}),
            ),
            stack_idx=4,
        )

        all_phrases = phrases_lr + (phrase_bounce,)
        catalog = EffectStackCatalog(
            schema_version="v1.0.0",
            total_phrase_count=5,
            total_stack_count=5,
            single_layer_count=5,
            multi_layer_count=0,
            max_layer_count=1,
            stacks=stacks_lr + (stack_bounce,),
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=all_phrases, stacks=catalog)

        profile = _get_profile(result, "bars")
        assert len(profile.top_params) >= 1
        chase_param = next(
            p for p in profile.top_params if p.param_name == "chase_type1"
        )
        assert chase_param.distinct_value_count == 2
        top = chase_param.top_values[0]
        assert top.value == "Left-Right"
        assert top.frequency == 0.8
        assert top.corpus_count == 4


class TestLayeringBehavior:
    """Test 4: Layering behavior from stacks."""

    def test_role_distribution_and_partners(self) -> None:
        """7 BASE + 3 ACCENT stacks, with color_wash partner in 6."""
        bars_phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(10)
        )
        wash_phrases = tuple(
            _make_phrase(effect_family="color_wash", idx=100 + i)
            for i in range(6)
        )

        # 7 stacks where bars is BASE (single layer)
        base_stacks = tuple(
            _make_stack(
                layers=((bars_phrases[i], LayerRole.BASE, {}),),
                stack_idx=i,
            )
            for i in range(7)
        )
        # 3 stacks where bars is ACCENT alongside color_wash
        accent_stacks = tuple(
            _make_stack(
                layers=(
                    (wash_phrases[i], LayerRole.BASE, {}),
                    (bars_phrases[7 + i], LayerRole.ACCENT, {}),
                ),
                stack_idx=7 + i,
            )
            for i in range(3)
        )
        # 3 extra stacks where color_wash partners with bars as BASE
        partner_stacks = tuple(
            _make_stack(
                layers=(
                    (bars_phrases[i], LayerRole.BASE, {}),
                    (wash_phrases[3 + i], LayerRole.ACCENT, {}),
                ),
                stack_idx=10 + i,
            )
            for i in range(3)
        )

        all_stacks = base_stacks + accent_stacks + partner_stacks
        catalog = EffectStackCatalog(
            schema_version="v1.0.0",
            total_phrase_count=16,
            total_stack_count=len(all_stacks),
            single_layer_count=7,
            multi_layer_count=6,
            max_layer_count=2,
            stacks=all_stacks,
        )
        all_phrases = bars_phrases + wash_phrases
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=all_phrases, stacks=catalog)

        bars_profile = _get_profile(result, "bars")
        layering = bars_profile.layering

        # bars appears in 13 stacks total: 10 as BASE + 3 as ACCENT
        assert layering.typical_layer_role == "BASE"
        assert layering.role_distribution["BASE"] > layering.role_distribution.get(
            "ACCENT", 0.0
        )
        # common_partners should include color_wash
        assert "color_wash" in layering.common_partners

    def test_solo_ratio_correct(self) -> None:
        """7 single-layer stacks + 3 multi-layer -> solo_ratio = 0.7."""
        bars_phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(10)
        )
        wash_phrases = tuple(
            _make_phrase(effect_family="color_wash", idx=100 + i)
            for i in range(3)
        )

        single_stacks = tuple(
            _make_stack(
                layers=((bars_phrases[i], LayerRole.BASE, {}),),
                stack_idx=i,
            )
            for i in range(7)
        )
        multi_stacks = tuple(
            _make_stack(
                layers=(
                    (bars_phrases[7 + i], LayerRole.BASE, {}),
                    (wash_phrases[i], LayerRole.ACCENT, {}),
                ),
                stack_idx=7 + i,
            )
            for i in range(3)
        )

        catalog = EffectStackCatalog(
            schema_version="v1.0.0",
            total_phrase_count=13,
            total_stack_count=10,
            single_layer_count=7,
            multi_layer_count=3,
            max_layer_count=2,
            stacks=single_stacks + multi_stacks,
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(
            phrases=bars_phrases + wash_phrases, stacks=catalog
        )
        bars_profile = _get_profile(result, "bars")
        # 7 solo out of 10 stacks containing bars = 0.7
        assert bars_profile.layering.solo_ratio == 0.7


class TestSectionPlacement:
    """Test 5: Section placement distribution."""

    def test_section_frequencies_and_preferred(self) -> None:
        """chorus(5) + verse(3) + intro(2) -> correct preferred sections."""
        phrases: list[EffectPhrase] = []
        idx = 0
        for label, count in [("chorus", 5), ("verse", 3), ("intro", 2)]:
            for _ in range(count):
                phrases.append(
                    _make_phrase(
                        effect_family="bars",
                        section_label=label,
                        idx=idx,
                    )
                )
                idx += 1

        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=tuple(phrases))

        profile = _get_profile(result, "bars")
        sp = profile.section_placement
        assert sp.section_distribution["chorus"] == 0.5
        assert sp.section_distribution["verse"] == 0.3
        assert sp.section_distribution["intro"] == 0.2
        assert sp.preferred_sections == ("chorus", "verse", "intro")


class TestModelAffinities:
    """Test 6: Model affinities from PropensityIndex."""

    def test_affinities_sorted_by_frequency(self) -> None:
        """PropensityIndex affinities are sorted by frequency in profile."""
        phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(5)
        )
        propensity = PropensityIndex(
            schema_version="v1.0.0",
            affinities=(
                EffectModelAffinity(
                    effect_family="bars",
                    model_type="megatree",
                    frequency=0.6,
                    exclusivity=0.3,
                    corpus_support=100,
                ),
                EffectModelAffinity(
                    effect_family="bars",
                    model_type="arch",
                    frequency=0.8,
                    exclusivity=0.2,
                    corpus_support=80,
                ),
                EffectModelAffinity(
                    effect_family="bars",
                    model_type="matrix",
                    frequency=0.3,
                    exclusivity=0.1,
                    corpus_support=50,
                ),
                # Unrelated family
                EffectModelAffinity(
                    effect_family="twinkle",
                    model_type="megatree",
                    frequency=0.9,
                    exclusivity=0.5,
                    corpus_support=200,
                ),
            ),
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases, propensity=propensity)

        profile = _get_profile(result, "bars")
        # Sorted by frequency descending: arch(0.8), megatree(0.6), matrix(0.3)
        assert profile.model_affinities == ("arch", "megatree", "matrix")


class TestEdgeCases:
    """Test 7: Edge cases."""

    def test_zero_stacks_solo_ratio_one(self) -> None:
        """Family with 0 stacks -> solo_ratio = 1.0."""
        phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(3)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        assert profile.layering.solo_ratio == 1.0
        assert profile.layering.typical_layer_role == "UNKNOWN"
        assert profile.layering.role_distribution == {}
        assert profile.layering.common_partners == ()

    def test_no_section_label_empty_distribution(self) -> None:
        """Phrases with no section_label -> empty section_distribution."""
        phrases = tuple(
            _make_phrase(
                effect_family="bars", section_label=None, idx=i
            )
            for i in range(3)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        assert profile.section_placement.section_distribution == {}
        assert profile.section_placement.preferred_sections == ()

    def test_no_preserved_params_empty_top_params(self) -> None:
        """Stacks with no preserved_params -> empty top_params."""
        phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(3)
        )
        stacks = tuple(
            _make_stack(
                layers=((p, LayerRole.BASE, {}),),
                stack_idx=i,
            )
            for i, p in enumerate(phrases)
        )
        catalog = EffectStackCatalog(
            schema_version="v1.0.0",
            total_phrase_count=3,
            total_stack_count=3,
            single_layer_count=3,
            multi_layer_count=0,
            max_layer_count=1,
            stacks=stacks,
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases, stacks=catalog)

        profile = _get_profile(result, "bars")
        assert profile.top_params == ()

    def test_corpus_counts_correct(self) -> None:
        """Profile tracks correct corpus_phrase_count and corpus_sequence_count."""
        phrases = tuple(
            _make_phrase(
                effect_family="bars",
                sequence_file_id=f"seq-{i % 2}",
                idx=i,
            )
            for i in range(5)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        assert profile.corpus_phrase_count == 5
        assert profile.corpus_sequence_count == 2

    def test_multiple_families_independent(self) -> None:
        """Multiple families produce independent profiles."""
        bars = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(3)
        )
        twinkle = tuple(
            _make_phrase(
                effect_family="twinkle",
                motion_class=MotionClass.SPARKLE,
                idx=i + 10,
            )
            for i in range(2)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=bars + twinkle)

        assert result.profile_count == 2
        assert result.total_phrase_count == 5
        bars_profile = _get_profile(result, "bars")
        twinkle_profile = _get_profile(result, "twinkle")
        assert bars_profile.corpus_phrase_count == 3
        assert twinkle_profile.corpus_phrase_count == 2

    def test_no_propensity_empty_affinities(self) -> None:
        """No PropensityIndex provided -> empty model_affinities."""
        phrases = tuple(
            _make_phrase(effect_family="bars", idx=i) for i in range(3)
        )
        builder = EffectMetadataProfileBuilder()
        result = builder.build(phrases=phrases)

        profile = _get_profile(result, "bars")
        assert profile.model_affinities == ()
