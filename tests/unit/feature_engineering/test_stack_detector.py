"""Tests for EffectStackDetector — groups co-occurring effects into stacks."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.stack_detector import (
    EffectStackDetector,
    EffectStackDetectorOptions,
)
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole


def _make_phrase(
    *,
    phrase_id: str = "p1",
    package_id: str = "pkg",
    sequence_file_id: str = "seq",
    target_name: str = "MegaTree",
    layer_index: int = 0,
    effect_type: str = "ColorWash",
    effect_family: str = "color_wash",
    start_ms: int = 0,
    end_ms: int = 8000,
    section_label: str | None = "chorus",
    blend_mode: str | None = None,
    mix: float | None = None,
    motion_class: MotionClass = MotionClass.STATIC,
    energy_class: EnergyClass = EnergyClass.LOW,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt_{phrase_id}",
        effect_type=effect_type,
        effect_family=effect_family,
        motion_class=motion_class,
        color_class=ColorClass.PALETTE,
        energy_class=energy_class,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target_name,
        layer_index=layer_index,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        section_label=section_label,
        param_signature="abc123",
        blend_mode=blend_mode,
        mix=mix,
    )


class TestEffectStackDetectorSingleLayer:
    """A single effect on a target produces a 1-layer stack."""

    def test_single_phrase_yields_one_stack(self) -> None:
        phrase = _make_phrase()
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=(phrase,))

        assert len(stacks) == 1
        stack = stacks[0]
        assert stack.layer_count == 1
        assert stack.target_name == "MegaTree"
        assert stack.start_ms == 0
        assert stack.end_ms == 8000
        assert stack.layers[0].phrase.phrase_id == "p1"

    def test_single_layer_stack_signature(self) -> None:
        phrase = _make_phrase(effect_family="color_wash")
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=(phrase,))

        assert "color_wash" in stacks[0].stack_signature

    def test_single_layer_role_is_base(self) -> None:
        phrase = _make_phrase(effect_family="color_wash")
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=(phrase,))

        assert stacks[0].layers[0].layer_role == LayerRole.BASE


class TestEffectStackDetectorMultiLayer:
    """Co-occurring effects on the same target become a multi-layer stack."""

    def test_three_overlapping_layers_become_one_stack(self) -> None:
        phrases = (
            _make_phrase(
                phrase_id="wash",
                layer_index=0,
                effect_type="ColorWash",
                effect_family="color_wash",
                blend_mode="NORMAL",
                mix=1.0,
            ),
            _make_phrase(
                phrase_id="bars",
                layer_index=1,
                effect_type="Bars",
                effect_family="bars",
                blend_mode="ADD",
                mix=0.7,
                motion_class=MotionClass.SWEEP,
                energy_class=EnergyClass.HIGH,
            ),
            _make_phrase(
                phrase_id="sparkle",
                layer_index=2,
                effect_type="Sparkle",
                effect_family="sparkle",
                blend_mode="SCREEN",
                mix=0.45,
                motion_class=MotionClass.SPARKLE,
                energy_class=EnergyClass.MID,
            ),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 1
        stack = stacks[0]
        assert stack.layer_count == 3
        assert stack.layers[0].phrase.effect_family == "color_wash"
        assert stack.layers[1].phrase.effect_family == "bars"
        assert stack.layers[2].phrase.effect_family == "sparkle"

    def test_multi_layer_preserves_blend_modes(self) -> None:
        phrases = (
            _make_phrase(phrase_id="wash", layer_index=0, blend_mode="NORMAL", mix=1.0),
            _make_phrase(
                phrase_id="bars",
                layer_index=1,
                effect_family="bars",
                blend_mode="ADD",
                mix=0.7,
            ),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert stacks[0].layers[0].blend_mode == BlendMode.NORMAL
        assert stacks[0].layers[0].mix == 1.0
        assert stacks[0].layers[1].blend_mode == BlendMode.ADD
        assert stacks[0].layers[1].mix == 0.7

    def test_multi_layer_stack_signature_contains_all_families(self) -> None:
        phrases = (
            _make_phrase(
                phrase_id="wash",
                layer_index=0,
                effect_family="color_wash",
                blend_mode="NORMAL",
            ),
            _make_phrase(
                phrase_id="bars",
                layer_index=1,
                effect_family="bars",
                blend_mode="ADD",
            ),
            _make_phrase(
                phrase_id="sparkle",
                layer_index=2,
                effect_family="sparkle",
                blend_mode="SCREEN",
            ),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)
        sig = stacks[0].stack_signature

        assert "color_wash" in sig
        assert "bars" in sig
        assert "sparkle" in sig

    def test_layer_roles_assigned_by_position(self) -> None:
        phrases = (
            _make_phrase(phrase_id="wash", layer_index=0, effect_family="color_wash"),
            _make_phrase(phrase_id="bars", layer_index=1, effect_family="bars"),
            _make_phrase(phrase_id="sparkle", layer_index=2, effect_family="sparkle"),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert stacks[0].layers[0].layer_role == LayerRole.BASE
        assert stacks[0].layers[1].layer_role == LayerRole.RHYTHM
        assert stacks[0].layers[2].layer_role == LayerRole.ACCENT


class TestEffectStackDetectorBoundaries:
    """Stack boundaries are defined by when the active layer set changes."""

    def test_different_targets_produce_separate_stacks(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", target_name="MegaTree"),
            _make_phrase(phrase_id="p2", target_name="Arch"),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 2
        targets = {s.target_name for s in stacks}
        assert targets == {"MegaTree", "Arch"}

    def test_non_overlapping_effects_on_same_target_produce_separate_stacks(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", start_ms=0, end_ms=4000),
            _make_phrase(phrase_id="p2", start_ms=4000, end_ms=8000),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 2

    def test_partially_overlapping_below_threshold_separate(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", layer_index=0, start_ms=0, end_ms=10000),
            _make_phrase(phrase_id="p2", layer_index=1, start_ms=9000, end_ms=20000),
        )
        detector = EffectStackDetector(options=EffectStackDetectorOptions(overlap_threshold=0.8))
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 2

    def test_partially_overlapping_above_threshold_merge(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", layer_index=0, start_ms=0, end_ms=10000),
            _make_phrase(phrase_id="p2", layer_index=1, start_ms=500, end_ms=10000),
        )
        detector = EffectStackDetector(options=EffectStackDetectorOptions(overlap_threshold=0.8))
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 1
        assert stacks[0].layer_count == 2


class TestEffectStackDetectorPackageIsolation:
    """Stacks are scoped to (package_id, sequence_file_id, target_name)."""

    def test_same_target_different_sequences_separate(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", sequence_file_id="seq1"),
            _make_phrase(phrase_id="p2", sequence_file_id="seq2"),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert len(stacks) == 2


class TestEffectStackDetectorMetadata:
    """Stack metadata propagation."""

    def test_section_label_from_first_layer(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", layer_index=0, section_label="chorus"),
            _make_phrase(phrase_id="p2", layer_index=1, section_label="chorus"),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert stacks[0].section_label == "chorus"

    def test_stack_timing_is_intersection(self) -> None:
        phrases = (
            _make_phrase(phrase_id="p1", layer_index=0, start_ms=100, end_ms=9000),
            _make_phrase(phrase_id="p2", layer_index=1, start_ms=200, end_ms=8500),
        )
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        stack = stacks[0]
        assert stack.start_ms == 200
        assert stack.end_ms == 8500

    def test_package_and_sequence_propagated(self) -> None:
        phrases = (_make_phrase(phrase_id="p1", package_id="my_pkg", sequence_file_id="my_seq"),)
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=phrases)

        assert stacks[0].package_id == "my_pkg"
        assert stacks[0].sequence_file_id == "my_seq"


class TestEffectStackDetectorEmpty:
    """Edge cases with empty input."""

    def test_no_phrases_yields_no_stacks(self) -> None:
        detector = EffectStackDetector()
        stacks = detector.detect(phrases=())
        assert len(stacks) == 0
