from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TargetRole,
    TaxonomyLabel,
    TaxonomyLabelScore,
)
from twinklr.core.feature_engineering.taxonomy.target_roles import TargetRoleAssigner


def _phrase(event_id: str, *, energy: EnergyClass, continuity: ContinuityClass) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=f"phrase-{event_id}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=event_id,
        effect_type="Bars",
        effect_family="pattern_bars",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=energy,
        continuity_class=continuity,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="MegaTree",
        layer_index=0,
        start_ms=0,
        end_ms=500,
        duration_ms=500,
        onset_sync_score=0.85,
        param_signature="abc",
    )


def _taxonomy(event_id: str, *labels: TaxonomyLabel) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="effect_function_v1",
        phrase_id=f"phrase-{event_id}",
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=event_id,
        labels=tuple(labels),
        label_confidences=tuple(0.9 for _ in labels),
        rule_hit_keys=("hit",),
        label_scores=tuple(
            TaxonomyLabelScore(label=label, confidence=0.9, rule_hits=("hit",))
            for label in labels
        ),
    )


def test_target_roles_assigner_assigns_high_activity_lead() -> None:
    assigner = TargetRoleAssigner()

    enriched_events = [
        {
            "effect_event_id": "evt-1",
            "target_name": "MegaTree",
            "target_kind": "model",
            "target_semantic_tags": ["tree", "main"],
            "target_pixel_count": 800,
            "start_ms": 0,
            "end_ms": 500,
        },
        {
            "effect_event_id": "evt-2",
            "target_name": "MegaTree",
            "target_kind": "model",
            "target_semantic_tags": ["tree", "main"],
            "target_pixel_count": 800,
            "start_ms": 500,
            "end_ms": 1000,
        },
        {
            "effect_event_id": "evt-3",
            "target_name": "Stars",
            "target_kind": "model",
            "target_semantic_tags": ["accent"],
            "target_pixel_count": 50,
            "start_ms": 0,
            "end_ms": 300,
        },
    ]
    phrases = (
        _phrase("evt-1", energy=EnergyClass.HIGH, continuity=ContinuityClass.RHYTHMIC),
        _phrase("evt-2", energy=EnergyClass.HIGH, continuity=ContinuityClass.RHYTHMIC),
        _phrase("evt-3", energy=EnergyClass.MID, continuity=ContinuityClass.SUSTAINED),
    )
    taxonomy_rows = (
        _taxonomy("evt-1", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("evt-2", TaxonomyLabel.ACCENT_HIT),
        _taxonomy("evt-3", TaxonomyLabel.SUSTAINER),
    )

    rows = assigner.assign(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        enriched_events=enriched_events,
        phrases=phrases,
        taxonomy_rows=taxonomy_rows,
    )

    by_target = {row.target_name: row for row in rows}
    assert by_target["MegaTree"].role in {TargetRole.LEAD, TargetRole.IMPACT}
    assert by_target["MegaTree"].role_confidence >= 0.35
    assert by_target["Stars"].event_count == 1


def test_target_roles_assigner_fallback_when_weak_signal() -> None:
    assigner = TargetRoleAssigner()

    rows = assigner.assign(
        package_id="pkg-1",
        sequence_file_id="seq-1",
        enriched_events=[
            {
                "effect_event_id": "evt-1",
                "target_name": "Unknown Target",
                "target_kind": "unknown",
                "start_ms": 0,
                "end_ms": 100,
            }
        ],
        phrases=(),
        taxonomy_rows=(),
    )

    assert len(rows) == 1
    assert rows[0].role is TargetRole.FALLBACK
    assert rows[0].reason_keys == ("fallback_default",)

