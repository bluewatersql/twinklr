"""Tests for relaxed stack signature mode in template mining.

Validates that _relaxed_stack_content_signature() produces broader groups
by dropping blend modes, sorting families, and keeping only motion+energy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.stacks import (
    EffectStack,
    EffectStackLayer,
)
from twinklr.core.feature_engineering.templates.miner import (
    TemplateMiner,
    TemplateMinerOptions,
)
from twinklr.core.sequencer.vocabulary import BlendMode, LayerRole

if TYPE_CHECKING:
    from twinklr.core.feature_engineering.models.taxonomy import (
        PhraseTaxonomyRecord,
        TargetRoleAssignment,
    )


def _make_phrase(
    effect_family: str = "bars",
    motion: MotionClass = MotionClass.SWEEP,
    energy: EnergyClass = EnergyClass.HIGH,
    phrase_id: str = "ph-001",
    package_id: str = "pack-001",
) -> EffectPhrase:
    """Create a minimal EffectPhrase for testing."""
    return EffectPhrase(
        schema_version="v1.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id="seq-001",
        effect_event_id="ev-001",
        effect_type=effect_family,
        effect_family=effect_family,
        motion_class=motion,
        color_class=ColorClass.PALETTE,
        energy_class=energy,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.95,
        target_name="MegaTree",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature="sig",
    )


def _make_stack(
    layers: list[tuple[str, BlendMode]],
    primary_motion: MotionClass = MotionClass.SWEEP,
    primary_energy: EnergyClass = EnergyClass.HIGH,
    package_id: str = "pack-001",
    stack_id: str | None = None,
) -> EffectStack:
    """Create an EffectStack from (family, blend_mode) layer specs."""
    stack_layers: list[EffectStackLayer] = []
    for i, (family, blend) in enumerate(layers):
        phrase = _make_phrase(
            effect_family=family,
            motion=primary_motion if i == 0 else MotionClass.STATIC,
            energy=primary_energy if i == 0 else EnergyClass.LOW,
            phrase_id=f"ph-{i:03d}",
            package_id=package_id,
        )
        stack_layers.append(
            EffectStackLayer(
                phrase=phrase,
                layer_role=LayerRole.BASE if i == 0 else LayerRole.ACCENT,
                blend_mode=blend,
            )
        )
    return EffectStack(
        stack_id=stack_id or f"stk-{uuid.uuid4().hex[:8]}",
        package_id=package_id,
        sequence_file_id="seq-001",
        target_name="MegaTree",
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        layers=tuple(stack_layers),
        layer_count=len(stack_layers),
        stack_signature="+".join(f for f, _ in layers),
    )


class TestRelaxedSignatures:
    """Verify relaxed stack signature format and behavior."""

    def test_relaxed_signature_format(self) -> None:
        """Relaxed sig = sorted families + motion + energy only."""
        stack = _make_stack(
            [
                ("color_wash", BlendMode.NORMAL),
                ("bars", BlendMode.ADD),
                ("sparkle", BlendMode.SCREEN),
            ],
            primary_motion=MotionClass.SWEEP,
            primary_energy=EnergyClass.HIGH,
        )
        sig = TemplateMiner._relaxed_stack_content_signature(stack, {})
        assert sig == "bars+color_wash+sparkle|sweep|high"

    def test_relaxed_signature_order_independent(self) -> None:
        """Two stacks with same families in different order produce same sig."""
        stack_a = _make_stack(
            [
                ("sparkle", BlendMode.NORMAL),
                ("bars", BlendMode.NORMAL),
                ("color_wash", BlendMode.NORMAL),
            ]
        )
        stack_b = _make_stack(
            [
                ("color_wash", BlendMode.NORMAL),
                ("sparkle", BlendMode.NORMAL),
                ("bars", BlendMode.NORMAL),
            ]
        )
        sig_a = TemplateMiner._relaxed_stack_content_signature(stack_a, {})
        sig_b = TemplateMiner._relaxed_stack_content_signature(stack_b, {})
        assert sig_a == sig_b

    def test_relaxed_signature_ignores_blend_mode(self) -> None:
        """Two stacks differing only in blend produce identical relaxed sigs."""
        stack_normal = _make_stack(
            [
                ("bars", BlendMode.NORMAL),
                ("sparkle", BlendMode.NORMAL),
            ]
        )
        stack_screen = _make_stack(
            [
                ("bars", BlendMode.SCREEN),
                ("sparkle", BlendMode.ADD),
            ]
        )
        sig_normal = TemplateMiner._relaxed_stack_content_signature(stack_normal, {})
        sig_screen = TemplateMiner._relaxed_stack_content_signature(stack_screen, {})
        assert sig_normal == sig_screen

    def test_strict_signature_preserves_blend(self) -> None:
        """Strict sigs differ when blend modes differ."""
        stack_normal = _make_stack(
            [
                ("bars", BlendMode.NORMAL),
                ("sparkle", BlendMode.NORMAL),
            ]
        )
        stack_screen = _make_stack(
            [
                ("bars", BlendMode.SCREEN),
                ("sparkle", BlendMode.ADD),
            ]
        )
        sig_normal = TemplateMiner._stack_content_signature(stack_normal, {})
        sig_screen = TemplateMiner._stack_content_signature(stack_screen, {})
        assert sig_normal != sig_screen

    def test_mine_stacks_uses_relaxed_mode(self) -> None:
        """Relaxed mode produces fewer groups (broader) than strict."""
        stacks = tuple(
            _make_stack(
                [("bars", blend), ("sparkle", BlendMode.NORMAL)],
                package_id=f"pack-{i:03d}",
                stack_id=f"stk-{i:03d}",
            )
            for i, blend in enumerate([BlendMode.NORMAL, BlendMode.ADD, BlendMode.SCREEN])
        )
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...] = ()
        target_roles: tuple[TargetRoleAssignment, ...] = ()

        relaxed_miner = TemplateMiner(
            TemplateMinerOptions(
                min_instance_count=1,
                min_distinct_pack_count=1,
                min_distinct_sequence_count=1,
                stack_signature_mode="relaxed",
            )
        )
        strict_miner = TemplateMiner(
            TemplateMinerOptions(
                min_instance_count=1,
                min_distinct_pack_count=1,
                min_distinct_sequence_count=1,
                stack_signature_mode="strict",
            )
        )

        relaxed_content, _ = relaxed_miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
        )
        strict_content, _ = strict_miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
        )
        # Relaxed produces fewer groups (same families, different blends → 1 group)
        assert len(relaxed_content.templates) < len(strict_content.templates)

    def test_mine_stacks_strict_mode_backward_compatible(self) -> None:
        """Strict mode preserves original signature behavior."""
        stacks = (
            _make_stack(
                [("bars", BlendMode.NORMAL), ("sparkle", BlendMode.SCREEN)],
                package_id="pack-001",
                stack_id="stk-001",
            ),
            _make_stack(
                [("bars", BlendMode.NORMAL), ("sparkle", BlendMode.SCREEN)],
                package_id="pack-002",
                stack_id="stk-002",
            ),
        )
        taxonomy_rows: tuple[PhraseTaxonomyRecord, ...] = ()
        target_roles: tuple[TargetRoleAssignment, ...] = ()

        strict_miner = TemplateMiner(
            TemplateMinerOptions(
                min_instance_count=1,
                min_distinct_pack_count=1,
                stack_signature_mode="strict",
            )
        )
        content, _ = strict_miner.mine_stacks(
            stacks=stacks,
            taxonomy_rows=taxonomy_rows,
            target_roles=target_roles,
        )
        # Both stacks have identical composition → 1 content template
        assert len(content.templates) == 1
