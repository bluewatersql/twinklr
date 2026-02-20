from __future__ import annotations

from twinklr.core.feature_engineering.models.taxonomy import (
    PhraseTaxonomyRecord,
    TaxonomyLabel,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateAssignment,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.template_diagnostics import (
    TemplateDiagnosticsBuilder,
    TemplateDiagnosticsOptions,
)


def _template(template_id: str, kind: TemplateKind, support_count: int) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=kind,
        template_signature=f"sig-{template_id}",
        support_count=support_count,
        distinct_pack_count=1,
        support_ratio=0.2,
        cross_pack_stability=0.2,
        onset_sync_mean=0.5,
        role=None,
        taxonomy_labels=("sustainer",),
        effect_family="on",
        motion_class="static",
        color_class="solid",
        energy_class="unknown",
        continuity_class="sustained",
        spatial_class="single_target",
        provenance=(),
    )


def _assignment(
    template_id: str, phrase_id: str, *, package_id: str, sequence_file_id: str
) -> TemplateAssignment:
    return TemplateAssignment(
        package_id=package_id,
        sequence_file_id=sequence_file_id,
        phrase_id=phrase_id,
        effect_event_id=f"evt-{phrase_id}",
        template_id=template_id,
    )


def _taxonomy(phrase_id: str, label: TaxonomyLabel) -> PhraseTaxonomyRecord:
    return PhraseTaxonomyRecord(
        schema_version="v1.3.0",
        classifier_version="test",
        phrase_id=phrase_id,
        package_id="pkg-1",
        sequence_file_id="seq-1",
        effect_event_id=f"evt-{phrase_id}",
        labels=(label,),
        label_confidences=(1.0,),
        rule_hit_keys=(),
        label_scores=(),
    )


def test_template_diagnostics_flags_expected_templates() -> None:
    content_catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.CONTENT,
        total_phrase_count=13,
        assigned_phrase_count=13,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(
            _template("t-low", TemplateKind.CONTENT, support_count=2),
            _template("t-conc", TemplateKind.CONTENT, support_count=5),
            _template("t-generic", TemplateKind.CONTENT, support_count=6),
        ),
        assignments=(
            _assignment("t-low", "p1", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-low", "p2", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-conc", "p3", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-conc", "p4", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-conc", "p5", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-conc", "p6", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-conc", "p7", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-generic", "p8", package_id="pkg-1", sequence_file_id="seq-1"),
            _assignment("t-generic", "p9", package_id="pkg-1", sequence_file_id="seq-2"),
            _assignment("t-generic", "p10", package_id="pkg-1", sequence_file_id="seq-3"),
            _assignment("t-generic", "p11", package_id="pkg-1", sequence_file_id="seq-4"),
            _assignment("t-generic", "p12", package_id="pkg-1", sequence_file_id="seq-5"),
            _assignment("t-generic", "p13", package_id="pkg-1", sequence_file_id="seq-6"),
        ),
    )
    orchestration_catalog = TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="test",
        template_kind=TemplateKind.ORCHESTRATION,
        total_phrase_count=0,
        assigned_phrase_count=0,
        assignment_coverage=0.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=(),
    )

    taxonomy_rows = (
        _taxonomy("p1", TaxonomyLabel.SUSTAINER),
        _taxonomy("p2", TaxonomyLabel.SUSTAINER),
        _taxonomy("p3", TaxonomyLabel.SUSTAINER),
        _taxonomy("p4", TaxonomyLabel.SUSTAINER),
        _taxonomy("p5", TaxonomyLabel.SUSTAINER),
        _taxonomy("p6", TaxonomyLabel.SUSTAINER),
        _taxonomy("p7", TaxonomyLabel.SUSTAINER),
        _taxonomy("p8", TaxonomyLabel.SUSTAINER),
        _taxonomy("p9", TaxonomyLabel.MOTION_DRIVER),
        _taxonomy("p10", TaxonomyLabel.TEXTURE_BED),
        _taxonomy("p11", TaxonomyLabel.ACCENT_HIT),
        _taxonomy("p12", TaxonomyLabel.TRANSITION),
        _taxonomy("p13", TaxonomyLabel.RHYTHM_DRIVER),
    )

    builder = TemplateDiagnosticsBuilder(
        TemplateDiagnosticsOptions(
            low_support_max_count=2,
            high_concentration_min_ratio=0.8,
            high_variance_min_score=0.65,
            over_generic_min_support_count=5,
            over_generic_max_dominant_taxonomy_ratio=0.35,
        )
    )
    report = builder.build(
        content_catalog=content_catalog,
        orchestration_catalog=orchestration_catalog,
        taxonomy_rows=taxonomy_rows,
    )

    assert report.total_templates == 3
    assert report.low_support_templates == ("t-low",)
    assert "t-conc" in report.high_concentration_templates
    assert "t-generic" in report.high_variance_templates
    assert "t-generic" in report.over_generic_templates
