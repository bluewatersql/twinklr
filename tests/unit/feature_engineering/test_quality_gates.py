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
from twinklr.core.feature_engineering.models.quality import QualityCheckResult
from twinklr.core.feature_engineering.models.template_diagnostics import (
    TemplateDiagnosticsReport,
    TemplateDiagnosticThresholds,
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


def test_quality_gate_fails_when_single_unknown_type_is_dominant() -> None:
    known = tuple(_phrase(f"p-known-{idx}") for idx in range(10))
    unknown_1 = _phrase("p-unknown-1").model_copy(
        update={
            "effect_type": "SketchFX",
            "effect_family": "unknown",
            "motion_class": MotionClass.UNKNOWN,
        }
    )
    unknown_2 = _phrase("p-unknown-2").model_copy(
        update={
            "effect_type": "SketchFX",
            "effect_family": "unknown",
            "motion_class": MotionClass.UNKNOWN,
        }
    )
    phrases = (*known, unknown_1, unknown_2)
    report = FeatureQualityGates(
        QualityGateOptions(
            max_unknown_effect_family_ratio=1.0,
            max_unknown_motion_ratio=1.0,
            max_single_unknown_effect_type_ratio=0.10,
        )
    ).evaluate(
        phrases=phrases,
        taxonomy_rows=tuple(_taxonomy(f"p-{idx}") for idx in range(len(phrases))),
        orchestration_catalog=TemplateCatalog(
            schema_version="v1.5.0",
            miner_version="template_miner_v1",
            template_kind=TemplateKind.ORCHESTRATION,
            total_phrase_count=len(phrases),
            assigned_phrase_count=len(phrases),
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
    check = next(row for row in report.checks if row.check_id == "single_unknown_effect_type_ratio")
    assert check.passed is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_transition_graph() -> TransitionGraph:
    return TransitionGraph(
        schema_version="v1.6.0",
        graph_version="transition_graph_v1",
        total_transitions=0,
        total_nodes=0,
        total_edges=0,
        edges=(),
        transitions=(),
        anomalies=(),
    )


def _minimal_orchestration_catalog(phrase_count: int = 1) -> TemplateCatalog:
    return TemplateCatalog(
        schema_version="v1.5.0",
        miner_version="template_miner_v1",
        template_kind=TemplateKind.ORCHESTRATION,
        total_phrase_count=phrase_count,
        assigned_phrase_count=phrase_count,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(),
        assignments=(),
    )


def _clean_diagnostics() -> TemplateDiagnosticsReport:
    """Diagnostics report with all ratios at zero (all templates clean)."""
    return TemplateDiagnosticsReport(
        schema_version="v1.0.0",
        diagnostics_version="template_diagnostics_v1",
        thresholds=TemplateDiagnosticThresholds(
            low_support_max_count=5,
            high_concentration_min_ratio=0.8,
            high_variance_min_score=0.65,
            over_generic_min_support_count=50,
            over_generic_max_dominant_taxonomy_ratio=0.35,
        ),
        total_templates=10,
        flagged_template_count=0,
        low_support_templates=(),
        high_concentration_templates=(),
        high_variance_templates=(),
        over_generic_templates=(),
        rows=(),
    )


def _dirty_diagnostics() -> TemplateDiagnosticsReport:
    """Diagnostics report with 5/10 templates flagged in each category."""
    flagged = tuple(f"tpl-{i}" for i in range(5))
    return TemplateDiagnosticsReport(
        schema_version="v1.0.0",
        diagnostics_version="template_diagnostics_v1",
        thresholds=TemplateDiagnosticThresholds(
            low_support_max_count=5,
            high_concentration_min_ratio=0.8,
            high_variance_min_score=0.65,
            over_generic_min_support_count=50,
            over_generic_max_dominant_taxonomy_ratio=0.35,
        ),
        total_templates=10,
        flagged_template_count=5,
        low_support_templates=flagged,
        high_concentration_templates=flagged,
        high_variance_templates=flagged,
        over_generic_templates=flagged,
        rows=(),
    )


# ---------------------------------------------------------------------------
# QualityCheckResult.mode tests
# ---------------------------------------------------------------------------


def test_quality_check_result_mode_enforce_default() -> None:
    """mode defaults to 'enforce'."""
    check = QualityCheckResult(
        check_id="test_check",
        passed=False,
        message="test",
    )
    assert check.mode == "enforce"


def test_quality_check_result_mode_enforce_affects_report_passed() -> None:
    """An enforce-mode failed check causes report.passed to be False."""
    report = FeatureQualityGates().evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_dirty_diagnostics(),
    )
    # With dirty diagnostics and thresholds set to enforce mode at 0.0 → fails
    gates = FeatureQualityGates(
        QualityGateOptions(
            max_low_support_template_ratio=0.0,
            diagnostics_gate_mode="enforce",
        )
    )
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_dirty_diagnostics(),
    )
    # The diagnostics check should fail and because mode=enforce, report.passed is False
    diag_check = next(
        (row for row in report.checks if row.check_id == "low_support_template_ratio"), None
    )
    assert diag_check is not None
    assert diag_check.passed is False
    assert diag_check.mode == "enforce"
    assert report.passed is False


def test_quality_check_result_mode_warn_does_not_affect_report_passed() -> None:
    """A warn-mode failed check does NOT cause report.passed to be False."""
    gates = FeatureQualityGates(
        QualityGateOptions(
            max_low_support_template_ratio=0.0,
            diagnostics_gate_mode="warn",
        )
    )
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_dirty_diagnostics(),
    )
    diag_check = next(
        (row for row in report.checks if row.check_id == "low_support_template_ratio"), None
    )
    assert diag_check is not None
    assert diag_check.passed is False
    assert diag_check.mode == "warn"
    # report.passed must not be False due to warn-mode check
    assert report.passed is True


# ---------------------------------------------------------------------------
# Diagnostics gate: clean diagnostics pass
# ---------------------------------------------------------------------------


def test_diagnostics_checks_pass_with_clean_diagnostics() -> None:
    """All diagnostics checks pass when ratios are below thresholds."""
    gates = FeatureQualityGates(
        QualityGateOptions(
            max_low_support_template_ratio=0.5,
            max_high_concentration_template_ratio=0.5,
            max_high_variance_template_ratio=0.5,
            max_over_generic_template_ratio=0.5,
        )
    )
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_clean_diagnostics(),
    )
    diag_check_ids = {
        "low_support_template_ratio",
        "high_concentration_template_ratio",
        "high_variance_template_ratio",
        "over_generic_template_ratio",
    }
    for check in report.checks:
        if check.check_id in diag_check_ids:
            assert check.passed is True, f"Expected {check.check_id} to pass with clean diagnostics"


def test_diagnostics_checks_fail_when_ratios_exceed_thresholds() -> None:
    """Each diagnostics check fails when flagged ratio exceeds threshold."""
    gates = FeatureQualityGates(
        QualityGateOptions(
            max_low_support_template_ratio=0.0,
            max_high_concentration_template_ratio=0.0,
            max_high_variance_template_ratio=0.0,
            max_over_generic_template_ratio=0.0,
        )
    )
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_dirty_diagnostics(),
    )
    for check_id in [
        "low_support_template_ratio",
        "high_concentration_template_ratio",
        "high_variance_template_ratio",
        "over_generic_template_ratio",
    ]:
        check = next((row for row in report.checks if row.check_id == check_id), None)
        assert check is not None, f"Missing check: {check_id}"
        assert check.passed is False, f"Expected {check_id} to fail"


# ---------------------------------------------------------------------------
# Backward-compat: None thresholds → no diagnostics checks added
# ---------------------------------------------------------------------------


def test_backward_compat_none_thresholds_no_diagnostics_checks() -> None:
    """When all diagnostics thresholds are None, no diagnostics checks are added."""
    gates = FeatureQualityGates(QualityGateOptions())
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_dirty_diagnostics(),
    )
    diag_check_ids = {
        "low_support_template_ratio",
        "high_concentration_template_ratio",
        "high_variance_template_ratio",
        "over_generic_template_ratio",
    }
    found = {row.check_id for row in report.checks} & diag_check_ids
    assert not found, f"Unexpected diagnostics checks added: {found}"


def test_backward_compat_none_diagnostics_no_checks_added() -> None:
    """When diagnostics=None, no diagnostics checks are added even if thresholds set."""
    gates = FeatureQualityGates(
        QualityGateOptions(
            max_low_support_template_ratio=0.5,
        )
    )
    report = gates.evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=None,
    )
    diag_check_ids = {
        "low_support_template_ratio",
        "high_concentration_template_ratio",
        "high_variance_template_ratio",
        "over_generic_template_ratio",
    }
    found = {row.check_id for row in report.checks} & diag_check_ids
    assert not found, f"Unexpected diagnostics checks added: {found}"


# ---------------------------------------------------------------------------
# Existing checks still work unchanged
# ---------------------------------------------------------------------------


def test_existing_checks_still_work_with_diagnostics_param() -> None:
    """Existing quality checks work unchanged when diagnostics param is provided."""
    report = FeatureQualityGates().evaluate(
        phrases=(_phrase("p1"),),
        taxonomy_rows=(_taxonomy("p1"),),
        orchestration_catalog=_minimal_orchestration_catalog(1),
        transition_graph=_minimal_transition_graph(),
        diagnostics=_clean_diagnostics(),
    )
    assert report.passed is True
    check_ids = {row.check_id for row in report.checks}
    assert "alignment_completeness" in check_ids
    assert "template_assignment_coverage" in check_ids
    assert "taxonomy_confidence_mean" in check_ids
    assert "deterministic_phrase_ids_unique" in check_ids
    assert "unknown_effect_family_ratio" in check_ids
    assert "unknown_motion_ratio" in check_ids
    assert "single_unknown_effect_type_ratio" in check_ids
    assert "transition_graph_integrity" in check_ids
