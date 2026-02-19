from __future__ import annotations

from twinklr.core.feature_engineering.models import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.transitions import TransitionModeler


def _phrase(phrase_id: str, template_event_id: str, start_ms: int, end_ms: int) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=template_event_id,
        effect_type="Bars",
        effect_family="pattern_bars",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.MULTI_TARGET,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        param_signature="sig",
    )


def test_transition_modeler_builds_edges() -> None:
    phrases = (
        _phrase("p1", "e1", 0, 1000),
        _phrase("p2", "e2", 1000, 1400),
        _phrase("p3", "e3", 1500, 2200),
    )
    catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="template_miner_v1",
        template_kind=TemplateKind.ORCHESTRATION,
        total_phrase_count=3,
        assigned_phrase_count=3,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=(
            TemplateAssignment(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                phrase_id="p1",
                effect_event_id="e1",
                template_id="t1",
            ),
            TemplateAssignment(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                phrase_id="p2",
                effect_event_id="e2",
                template_id="t2",
            ),
            TemplateAssignment(
                package_id="pkg-1",
                sequence_file_id="seq-1",
                phrase_id="p3",
                effect_event_id="e3",
                template_id="t3",
            ),
        ),
    )

    graph = TransitionModeler().build_graph(phrases=phrases, orchestration_catalog=catalog)

    assert graph.total_transitions == 2
    assert graph.total_edges == 2
    assert len(graph.edges) == 2

