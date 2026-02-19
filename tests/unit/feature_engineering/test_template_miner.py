from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
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
from twinklr.core.feature_engineering.models.templates import TemplateKind
from twinklr.core.feature_engineering.templates import TemplateMiner, TemplateMinerOptions


def _phrase(
    phrase_id: str,
    *,
    package_id: str,
    sequence_file_id: str,
    target_name: str,
    effect_event_id: str,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=effect_event_id,
        effect_type="Bars",
        effect_family="pattern_bars",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.HIGH,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name=target_name,
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        onset_sync_score=0.9,
        param_signature="sig-1",
    )


def _taxonomy(phrase_id: str, effect_event_id: str) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="effect_function_v1",
        phrase_id=phrase_id,
        package_id="pkg",
        sequence_file_id="seq",
        effect_event_id=effect_event_id,
        labels=(TaxonomyLabel.RHYTHM_DRIVER,),
        label_confidences=(0.9,),
        rule_hit_keys=("rhythm_continuity_rhythmic",),
        label_scores=(
            TaxonomyLabelScore(
                label=TaxonomyLabel.RHYTHM_DRIVER,
                confidence=0.9,
                rule_hits=("rhythm_continuity_rhythmic",),
            ),
        ),
    )


def _role(package_id: str, sequence_file_id: str, target_name: str) -> TargetRoleAssignment:
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
        target_layout_group=None,
        target_category=None,
        target_semantic_tags=("tree",),
        role_binding_key=f"lead:model:{target_name}",
    )


def test_template_miner_builds_content_and_orchestration_catalogs() -> None:
    miner = TemplateMiner(
        TemplateMinerOptions(min_instance_count=2, min_distinct_pack_count=2)
    )
    phrases = (
        _phrase(
            "phrase-1",
            package_id="pkg-1",
            sequence_file_id="seq-1",
            target_name="MegaTree",
            effect_event_id="evt-1",
        ),
        _phrase(
            "phrase-2",
            package_id="pkg-2",
            sequence_file_id="seq-2",
            target_name="MegaTree",
            effect_event_id="evt-2",
        ),
    )
    taxonomy = (
        _taxonomy("phrase-1", "evt-1"),
        _taxonomy("phrase-2", "evt-2"),
    )
    roles = (
        _role("pkg-1", "seq-1", "MegaTree"),
        _role("pkg-2", "seq-2", "MegaTree"),
    )

    content, orchestration = miner.mine(
        phrases=phrases,
        taxonomy_rows=taxonomy,
        target_roles=roles,
    )

    assert content.template_kind is TemplateKind.CONTENT
    assert orchestration.template_kind is TemplateKind.ORCHESTRATION
    assert len(content.templates) == 1
    assert len(orchestration.templates) == 1
    assert content.assignment_coverage == 1.0
    assert orchestration.assignment_coverage == 1.0
    assert content.templates[0].provenance
    assert orchestration.templates[0].role == "lead"


def test_template_miner_deterministic_output() -> None:
    miner = TemplateMiner(
        TemplateMinerOptions(min_instance_count=2, min_distinct_pack_count=1)
    )
    phrases = (
        _phrase(
            "phrase-a",
            package_id="pkg-1",
            sequence_file_id="seq-1",
            target_name="Tree",
            effect_event_id="evt-a",
        ),
        _phrase(
            "phrase-b",
            package_id="pkg-1",
            sequence_file_id="seq-1",
            target_name="Tree",
            effect_event_id="evt-b",
        ),
    )
    taxonomy = (
        _taxonomy("phrase-a", "evt-a"),
        _taxonomy("phrase-b", "evt-b"),
    )
    roles = (_role("pkg-1", "seq-1", "Tree"),)

    left = miner.mine(phrases=phrases, taxonomy_rows=taxonomy, target_roles=roles)
    right = miner.mine(phrases=phrases, taxonomy_rows=taxonomy, target_roles=roles)

    assert left[0].model_dump(mode="json") == right[0].model_dump(mode="json")
    assert left[1].model_dump(mode="json") == right[1].model_dump(mode="json")

