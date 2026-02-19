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
from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
)
from twinklr.core.feature_engineering.models.templates import (
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.motifs import MotifMiner


def _phrase(
    phrase_id: str,
    package_id: str,
    sequence_file_id: str,
    start_ms: int,
    beat: int,
    effect_family: str,
) -> EffectPhrase:
    return EffectPhrase(
        schema_version="v1.2.0",
        phrase_id=phrase_id,
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        effect_event_id=f"evt-{phrase_id}",
        effect_type=effect_family,
        effect_family=effect_family,
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.PALETTE,
        energy_class=EnergyClass.MID,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.GROUP,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=1.0,
        target_name="Tree",
        layer_index=0,
        start_ms=start_ms,
        end_ms=start_ms + 500,
        duration_ms=500,
        start_beat_index=beat,
        end_beat_index=beat + 1,
        section_label="verse",
        onset_sync_score=0.8,
        param_signature="sig",
    )


def _taxonomy(phrase_id: str, label: TaxonomyLabel) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="test",
        phrase_id=phrase_id,
        package_id="pkg",
        sequence_file_id="seq",
        effect_event_id=f"evt-{phrase_id}",
        labels=(label,),
        label_confidences=(0.8,),
        rule_hit_keys=("r1",),
        label_scores=(),
    )


def test_motif_miner_finds_recurrent_windows() -> None:
    phrases = (
        _phrase("p1", "pkg-a", "seq-1", 0, 0, "on"),
        _phrase("p2", "pkg-a", "seq-1", 600, 1, "bars"),
        _phrase("p3", "pkg-b", "seq-2", 0, 0, "on"),
        _phrase("p4", "pkg-b", "seq-2", 650, 1, "bars"),
    )
    taxonomy_rows = (
        _taxonomy("p1", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("p2", TaxonomyLabel.MOTION_DRIVER),
        _taxonomy("p3", TaxonomyLabel.RHYTHM_DRIVER),
        _taxonomy("p4", TaxonomyLabel.MOTION_DRIVER),
    )
    content_catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.CONTENT,
        total_phrase_count=4,
        assigned_phrase_count=4,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=(
            TemplateAssignment(
                package_id="pkg-a",
                sequence_file_id="seq-1",
                phrase_id="p1",
                effect_event_id="evt-p1",
                template_id="t-on",
            ),
            TemplateAssignment(
                package_id="pkg-a",
                sequence_file_id="seq-1",
                phrase_id="p2",
                effect_event_id="evt-p2",
                template_id="t-bars",
            ),
            TemplateAssignment(
                package_id="pkg-b",
                sequence_file_id="seq-2",
                phrase_id="p3",
                effect_event_id="evt-p3",
                template_id="t-on",
            ),
            TemplateAssignment(
                package_id="pkg-b",
                sequence_file_id="seq-2",
                phrase_id="p4",
                effect_event_id="evt-p4",
                template_id="t-bars",
            ),
        ),
    )
    orchestration_catalog = content_catalog.model_copy(
        update={
            "template_kind": TemplateKind.ORCHESTRATION,
            "assignments": (),
            "assigned_phrase_count": 0,
            "assignment_coverage": 0.0,
        }
    )

    catalog = MotifMiner().mine(
        phrases=phrases,
        taxonomy_rows=taxonomy_rows,
        content_catalog=content_catalog,
        orchestration_catalog=orchestration_catalog,
    )

    assert catalog.total_motifs >= 1
    motif = catalog.motifs[0]
    assert motif.support_count >= 2
    assert "t-on" in motif.template_ids
