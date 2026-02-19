from __future__ import annotations

from twinklr.core.feature_engineering.datasets.quality import (
    FeatureQualityGates,
    QualityGateOptions,
)
from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    PhraseTaxonomyRecord,
    SpatialClass,
    TaxonomyLabel,
    TaxonomyLabelScore,
    TemplateCatalog,
    TemplateKind,
    TransitionGraph,
)


def _phrase(phrase_id: str) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        effect_type="On",
        effect_family="on",
        motion_class=MotionClass.STATIC,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.SUSTAINED,
        spatial_class=SpatialClass.SINGLE_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=0,
        end_ms=1000,
        duration_ms=1000,
        param_signature="sig",
    )


def _taxonomy(phrase_id: str) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="effect_function_v1",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        labels=(TaxonomyLabel.SUSTAINER,),
        label_confidences=(0.8,),
        rule_hit_keys=("rule",),
        label_scores=(
            TaxonomyLabelScore(
                label=TaxonomyLabel.SUSTAINER,
                confidence=0.8,
                rule_hits=("rule",),
            ),
        ),
    )


def test_quality_gates_pass_on_baseline() -> None:
    report = FeatureQualityGates().evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=TemplateCatalog(
            schema_version="v1.5.0",
            miner_version="template_miner_v1",
            template_kind=TemplateKind.ORCHESTRATION,
            total_phrase_count=1,
            assigned_phrase_count=1,
            assignment_coverage=1.0,
            min_instance_count=1,
            min_distinct_pack_count=1,
            templates=(),
            assignments=(),
        ),
        transition_graph=TransitionGraph(
            schema_version="v1.6.0",
            graph_version="transition_graph_v1",
            total_transitions=0,
            total_nodes=0,
            total_edges=0,
            edges=(),
            transitions=(),
            anomalies=(),
        ),
    )

    assert report.passed


def test_quality_gate_fails_when_unknown_effect_ratio_exceeds_threshold() -> None:
    known = _phrase("p-known")
    unknown_1 = _phrase("p-unknown-1").model_copy(
        update={"effect_family": "unknown", "motion_class": MotionClass.UNKNOWN}
    )
    unknown_2 = _phrase("p-unknown-2").model_copy(
        update={"effect_family": "unknown", "motion_class": MotionClass.UNKNOWN}
    )
    report = FeatureQualityGates(
        QualityGateOptions(
            max_unknown_effect_family_ratio=0.40,
            max_unknown_motion_ratio=0.90,
        )
    ).evaluate(
        phrases=(known, unknown_1, unknown_2),
        taxonomy_rows=(_taxonomy("p-known"), _taxonomy("p-unknown-1"), _taxonomy("p-unknown-2")),
        orchestration_catalog=TemplateCatalog(
            schema_version="v1.5.0",
            miner_version="template_miner_v1",
            template_kind=TemplateKind.ORCHESTRATION,
            total_phrase_count=3,
            assigned_phrase_count=3,
            assignment_coverage=1.0,
            min_instance_count=1,
            min_distinct_pack_count=1,
            templates=(),
            assignments=(),
        ),
        transition_graph=TransitionGraph(
            schema_version="v1.6.0",
            graph_version="transition_graph_v1",
            total_transitions=0,
            total_nodes=0,
            total_edges=0,
            edges=(),
            transitions=(),
            anomalies=(),
        ),
    )
    check = next(row for row in report.checks if row.check_id == "unknown_effect_family_ratio")
    assert check.passed is False


def test_quality_gate_fails_when_unknown_motion_ratio_exceeds_threshold() -> None:
    known = _phrase("p-known")
    unknown_motion_1 = _phrase("p-unknown-motion-1").model_copy(
        update={"motion_class": MotionClass.UNKNOWN}
    )
    unknown_motion_2 = _phrase("p-unknown-motion-2").model_copy(
        update={"motion_class": MotionClass.UNKNOWN}
    )
    report = FeatureQualityGates(
        QualityGateOptions(
            max_unknown_effect_family_ratio=1.0,
            max_unknown_motion_ratio=0.40,
        )
    ).evaluate(
        phrases=(known, unknown_motion_1, unknown_motion_2),
        taxonomy_rows=(
            _taxonomy("p-known"),
            _taxonomy("p-unknown-motion-1"),
            _taxonomy("p-unknown-motion-2"),
        ),
        orchestration_catalog=TemplateCatalog(
            schema_version="v1.5.0",
            miner_version="template_miner_v1",
            template_kind=TemplateKind.ORCHESTRATION,
            total_phrase_count=3,
            assigned_phrase_count=3,
            assignment_coverage=1.0,
            min_instance_count=1,
            min_distinct_pack_count=1,
            templates=(),
            assignments=(),
        ),
        transition_graph=TransitionGraph(
            schema_version="v1.6.0",
            graph_version="transition_graph_v1",
            total_transitions=0,
            total_nodes=0,
            total_edges=0,
            edges=(),
            transitions=(),
            anomalies=(),
        ),
    )
    check = next(row for row in report.checks if row.check_id == "unknown_motion_ratio")
    assert check.passed is False
