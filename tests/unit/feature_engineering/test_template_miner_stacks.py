"""Tests for TemplateMiner.mine_stacks — stack-aware template mining."""

from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EffectStack,
    EffectStackLayer,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
    TargetRole,
    TargetRoleAssignment,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
    TaxonomyLabelScore,
)
from twinklr.core.feature_engineering.templates import TemplateMiner, TemplateMinerOptions
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole


def _phrase(
    phrase_id: str,
    *,
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    target_name: str = "MegaTree",
    effect_family: str = "color_wash",
    effect_type: str = "ColorWash",
    layer_index: int = 0,
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
        start_ms=0,
        end_ms=8000,
        duration_ms=8000,
        onset_sync_score=0.85,
        param_signature="sig",
    )


def _stack(
    stack_id: str,
    layers: tuple[EffectStackLayer, ...],
    *,
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    target_name: str = "MegaTree",
    section_label: str = "chorus",
) -> EffectStack:
    return EffectStack(
        stack_id=stack_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        target_name=target_name,
        start_ms=0,
        end_ms=8000,
        duration_ms=8000,
        section_label=section_label,
        layers=layers,
        layer_count=len(layers),
        stack_signature=f"sig_{stack_id}",
    )


def _taxonomy(
    phrase_id: str,
    *,
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="effect_function_v1",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt_{phrase_id}",
        labels=(TaxonomyLabel.TEXTURE_BED,),
        label_confidences=(0.9,),
        rule_hit_keys=("texture_static",),
        label_scores=(
            TaxonomyLabelScore(
                label=TaxonomyLabel.TEXTURE_BED,
                confidence=0.9,
                rule_hits=("texture_static",),
            ),
        ),
    )


def _target_role(
    package_id: str = "pkg1",
    sequence_file_id: str = "seq1",
    target_name: str = "MegaTree",
) -> TargetRoleAssignment:
    return TargetRoleAssignment(
        schema_version="v1.4.0",
        role_engine_version="target_roles_v1",
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        target_id=f"{package_id}-{sequence_file_id}-{target_name}",
        target_name=target_name,
        target_kind="model",
        role=TargetRole.LEAD,
        role_confidence=0.9,
        reason_keys=("high_activity",),
        event_count=5,
        active_duration_ms=2000,
        pixel_count=600,
        target_semantic_tags=("tree",),
        role_binding_key=f"lead:model:{target_name}",
    )


class TestMineStacksSingleLayer:
    """Single-layer stacks produce templates with layer_count=1."""

    def test_single_layer_stack_mines_template(self) -> None:
        p = _phrase("p1")
        layer = EffectStackLayer(
            phrase=p, layer_role=LayerRole.BASE, blend_mode=BlendMode.NORMAL, mix=1.0
        )
        # Need 2 instances for min_instance_count
        p2 = _phrase("p2", package_id="pkg2")
        layer2 = EffectStackLayer(
            phrase=p2, layer_role=LayerRole.BASE, blend_mode=BlendMode.NORMAL, mix=1.0
        )

        stacks = (
            _stack("s1", (layer,)),
            _stack("s2", (layer2,), package_id="pkg2"),
        )
        miner = TemplateMiner(options=TemplateMinerOptions(min_instance_count=2))
        content, orch = miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=(_taxonomy("p1"), _taxonomy("p2")),
            target_roles=(_target_role(), _target_role(package_id="pkg2")),
        )

        assert len(content.templates) >= 1
        t = content.templates[0]
        assert t.layer_count == 1
        assert t.stack_composition == ("color_wash",)


class TestMineStacksMultiLayer:
    """Multi-layer stacks populate stack_composition and blend modes."""

    def test_three_layer_stack_composition(self) -> None:
        wash = _phrase("wash1", effect_family="color_wash", layer_index=0)
        bars = _phrase(
            "bars1",
            effect_family="bars",
            effect_type="Bars",
            layer_index=1,
            motion_class=MotionClass.SWEEP,
            energy_class=EnergyClass.HIGH,
        )
        sparkle = _phrase(
            "sparkle1",
            effect_family="sparkle",
            effect_type="Sparkle",
            layer_index=2,
            motion_class=MotionClass.SPARKLE,
            energy_class=EnergyClass.MID,
        )

        wash2 = _phrase("wash2", package_id="pkg2", effect_family="color_wash", layer_index=0)
        bars2 = _phrase(
            "bars2",
            package_id="pkg2",
            effect_family="bars",
            effect_type="Bars",
            layer_index=1,
            motion_class=MotionClass.SWEEP,
            energy_class=EnergyClass.HIGH,
        )
        sparkle2 = _phrase(
            "sparkle2",
            package_id="pkg2",
            effect_family="sparkle",
            effect_type="Sparkle",
            layer_index=2,
            motion_class=MotionClass.SPARKLE,
            energy_class=EnergyClass.MID,
        )

        stacks = (
            _stack(
                "s1",
                (
                    EffectStackLayer(
                        phrase=wash, layer_role=LayerRole.BASE, blend_mode=BlendMode.NORMAL, mix=1.0
                    ),
                    EffectStackLayer(
                        phrase=bars, layer_role=LayerRole.RHYTHM, blend_mode=BlendMode.ADD, mix=0.7
                    ),
                    EffectStackLayer(
                        phrase=sparkle,
                        layer_role=LayerRole.ACCENT,
                        blend_mode=BlendMode.SCREEN,
                        mix=0.45,
                    ),
                ),
            ),
            _stack(
                "s2",
                (
                    EffectStackLayer(
                        phrase=wash2,
                        layer_role=LayerRole.BASE,
                        blend_mode=BlendMode.NORMAL,
                        mix=1.0,
                    ),
                    EffectStackLayer(
                        phrase=bars2, layer_role=LayerRole.RHYTHM, blend_mode=BlendMode.ADD, mix=0.7
                    ),
                    EffectStackLayer(
                        phrase=sparkle2,
                        layer_role=LayerRole.ACCENT,
                        blend_mode=BlendMode.SCREEN,
                        mix=0.45,
                    ),
                ),
                package_id="pkg2",
            ),
        )

        miner = TemplateMiner(options=TemplateMinerOptions(min_instance_count=2))
        content, _ = miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=(
                _taxonomy("wash1"),
                _taxonomy("wash2"),
            ),
            target_roles=(_target_role(), _target_role(package_id="pkg2")),
        )

        assert len(content.templates) >= 1
        t = content.templates[0]
        assert t.layer_count == 3
        assert t.stack_composition == ("color_wash", "bars", "sparkle")
        assert t.layer_blend_modes == ("NORMAL", "ADD", "SCREEN")
        assert t.layer_mixes == (1.0, 0.7, 0.45)

    def test_content_signature_groups_identical_stacks(self) -> None:
        """Two identical multi-layer stacks should share the same template."""
        wash = _phrase("wash1", effect_family="color_wash", layer_index=0)
        bars = _phrase("bars1", effect_family="bars", layer_index=1)
        wash2 = _phrase("wash2", package_id="pkg2", effect_family="color_wash", layer_index=0)
        bars2 = _phrase("bars2", package_id="pkg2", effect_family="bars", layer_index=1)

        stacks = (
            _stack(
                "s1",
                (
                    EffectStackLayer(
                        phrase=wash, layer_role=LayerRole.BASE, blend_mode=BlendMode.NORMAL, mix=1.0
                    ),
                    EffectStackLayer(
                        phrase=bars, layer_role=LayerRole.RHYTHM, blend_mode=BlendMode.ADD, mix=0.7
                    ),
                ),
            ),
            _stack(
                "s2",
                (
                    EffectStackLayer(
                        phrase=wash2,
                        layer_role=LayerRole.BASE,
                        blend_mode=BlendMode.NORMAL,
                        mix=1.0,
                    ),
                    EffectStackLayer(
                        phrase=bars2, layer_role=LayerRole.RHYTHM, blend_mode=BlendMode.ADD, mix=0.7
                    ),
                ),
                package_id="pkg2",
            ),
        )

        miner = TemplateMiner(options=TemplateMinerOptions(min_instance_count=2))
        content, _ = miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=(_taxonomy("wash1"), _taxonomy("wash2")),
            target_roles=(_target_role(), _target_role(package_id="pkg2")),
        )

        assert len(content.templates) == 1
        assert content.templates[0].support_count == 2


class TestMineStacksEmpty:
    def test_empty_stacks_produces_empty_catalogs(self) -> None:
        miner = TemplateMiner()
        content, orch = miner.mine_stacks(stacks=(), taxonomy_rows=(), target_roles=())
        assert len(content.templates) == 0
        assert len(orch.templates) == 0
