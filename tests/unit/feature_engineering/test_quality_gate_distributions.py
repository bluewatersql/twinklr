"""Tests for the owner-facing mined-candidate quality-gate report."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateCatalog,
    TemplateKind,
)
from twinklr.core.feature_engineering.quality_gate_distributions import (
    build_quality_gate_distribution_report,
)


def _candidate(
    template_id: str,
    *,
    support: int,
    packs: int,
    stability: float,
    family: str = "bars",
    layer_count: int = 1,
) -> MinedTemplate:
    return MinedTemplate(
        template_id=template_id,
        template_kind=TemplateKind.CONTENT,
        template_signature=f"{family}|sweep|palette|mid|rhythmic|single_target",
        support_count=support,
        distinct_pack_count=packs,
        support_ratio=0.5,
        cross_pack_stability=stability,
        effect_family=family,
        motion_class="sweep",
        color_class="palette",
        energy_class="mid",
        continuity_class="rhythmic",
        spatial_class="single_target",
        layer_count=layer_count,
    )


def test_distribution_report_has_hand_computed_histograms_and_sensitivity() -> None:
    """All candidates contribute to readable distributions and gate sensitivity."""
    candidates = [
        _candidate("a", support=1, packs=1, stability=0.01),
        _candidate("b", support=2, packs=1, stability=0.02),
        _candidate("c", support=3, packs=2, stability=0.05),
        _candidate("d", support=5, packs=3, stability=0.30),
    ]

    report = build_quality_gate_distribution_report(
        candidates,
        options=FeatureEngineeringPipelineOptions(),
        promotion_report={"effective_min_support": 2, "effective_min_stability": 0.05},
    )

    assert report["candidate_count"] == 4
    assert report["histograms"]["support_count"] == {
        "1": 1,
        "2": 1,
        "3-4": 1,
        "5-9": 1,
        "10+": 0,
    }
    assert report["histograms"]["distinct_pack_count"] == {
        "1": 2,
        "2": 1,
        "3-4": 1,
        "5-9": 0,
        "10+": 0,
    }

    promotion = report["threshold_review"]["recipe_promotion"]
    assert promotion["static_configured"]["min_support"] == 2
    assert promotion["effective_applied"] == {
        "min_support": 2,
        "min_stability": 0.05,
        "source": "promotion_report",
    }
    assert promotion["support_sensitivity"] == [
        {"threshold": 2, "pass_count": 2, "fail_count": 2},
        {"threshold": 3, "pass_count": 2, "fail_count": 2},
        {"threshold": 5, "pass_count": 1, "fail_count": 3},
    ]
    assert promotion["stability_sensitivity"] == [
        {"threshold": 0.015, "pass_count": 3, "fail_count": 1},
        {"threshold": 0.05, "pass_count": 2, "fail_count": 2},
        {"threshold": 0.3, "pass_count": 1, "fail_count": 3},
    ]
    assert report["promotion_default_discrepancy"]["pipeline_run_defaults"] == {
        "min_support": 5,
        "min_stability": 0.3,
    }


def test_distribution_report_exposes_low_pack_ratio_risk_and_cap_impact() -> None:
    """Ratio-only passes are split out by pack count and cap sensitivity is visible."""
    candidates = [
        _candidate("low-pack", support=2, packs=1, stability=0.10, family="bars"),
        _candidate("high-pack", support=2, packs=5, stability=0.10, family="bars"),
        _candidate("other", support=2, packs=2, stability=0.10, family="shimmer"),
    ]

    report = build_quality_gate_distribution_report(
        candidates,
        options=FeatureEngineeringPipelineOptions(),
        promotion_report={"effective_min_support": 2, "effective_min_stability": 0.05},
        role_scores=(0.2, 0.35, 1.05),
    )

    risk = report["low_pack_ratio_risk"]
    assert risk == {
        "exact_gate_pass_count": 3,
        "exact_gate_passes_with_one_pack": 1,
        "exact_gate_passes_with_two_or_fewer_packs": 2,
    }
    caps = report["threshold_review"]["recipe_promotion_caps"]
    assert caps["max_per_family_sensitivity"] == [
        {"cap": 5, "would_keep": 3, "would_cap": 0},
        {"cap": 10, "would_keep": 3, "would_cap": 0},
        {"cap": 15, "would_keep": 3, "would_cap": 0},
    ]
    assert caps["max_per_cluster"] == {
        "configured": 2,
        "status": "unavailable_without_cluster_catalog",
        "sensitivity": [],
        "limitation": "Nearby cap values cannot be evaluated from templates alone because cluster membership and multi-layer minimum retention affect survivors.",
    }
    assert report["threshold_review"]["target_role_score_cutoff"] == {
        "configured": 0.35,
        "source": "unclamped pre-assignment target-role scores",
        "status": "available",
        "sensitivity": [
            {"threshold": 0.25, "pass_count": 2, "fail_count": 1},
            {"threshold": 0.35, "pass_count": 2, "fail_count": 1},
            {"threshold": 0.45, "pass_count": 1, "fail_count": 2},
        ],
    }
    assert (
        report["threshold_review"]["propensity"]["anti_affinity_threshold"]["status"]
        == "unwired_constant"
    )
    propensity_support = report["threshold_review"]["propensity"]["min_support"]
    assert propensity_support["status"] == "unavailable_from_emitted_index"
    assert propensity_support["sensitivity"] == []


def test_exact_gate_accounts_for_excluded_families_and_multi_layer_rules() -> None:
    """Reported exact quality-gate counts mirror promotion stages zero and one."""
    candidates = [
        _candidate("excluded", support=20, packs=5, stability=0.9, family="dmx"),
        _candidate("single-fail", support=5, packs=3, stability=0.1),
        _candidate("single-pass", support=5, packs=3, stability=0.4),
        _candidate("multi-pass", support=2, packs=1, stability=0.02, layer_count=2),
    ]

    report = build_quality_gate_distribution_report(
        candidates,
        options=FeatureEngineeringPipelineOptions(),
        promotion_report={"effective_min_support": 2, "effective_min_stability": 0.3},
    )

    assert report["candidate_population"] == {
        "all": 4,
        "excluded_family": 1,
        "eligible_single_layer": 2,
        "eligible_multi_layer": 1,
        "exact_quality_gate_pass": 2,
        "exact_quality_gate_fail_or_excluded": 2,
    }
    assert report["recipe_promotion"]["exact_gate_breakdown"] == {
        "excluded_family_count": 1,
        "single_layer_pass_count": 1,
        "single_layer_fail_count": 1,
        "multi_layer_pass_count": 1,
        "multi_layer_fail_count": 0,
        "equivalence": "Matches PromotionPipeline stage 0 and stage 1; cluster dedup and caps occur later.",
    }


def test_report_command_writes_staged_review_material(tmp_path: Path) -> None:
    """The report command reads staged candidates and creates no live catalog output."""
    catalog = TemplateCatalog(
        schema_version="v1",
        miner_version="test",
        template_kind=TemplateKind.CONTENT,
        total_phrase_count=2,
        assigned_phrase_count=2,
        assignment_coverage=1.0,
        min_instance_count=1,
        min_distinct_pack_count=1,
        templates=(
            _candidate("one", support=2, packs=1, stability=0.02),
            _candidate("two", support=5, packs=3, stability=0.3),
        ),
    )
    (tmp_path / "content_templates.json").write_text(
        json.dumps(catalog.model_dump(mode="json")), encoding="utf-8"
    )
    (tmp_path / "promotion_report.json").write_text(
        json.dumps({"effective_min_support": 2, "effective_min_stability": 0.05}),
        encoding="utf-8",
    )
    root = Path(__file__).parents[3]

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/report_quality_gate_distributions.py",
            "--run-dir",
            str(tmp_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "quality_gate_distribution_report.json" in completed.stdout
    report = json.loads((tmp_path / "quality_gate_distribution_report.json").read_text())
    assert report["candidate_count"] == 2
    markdown = (tmp_path / "quality_gate_distribution_report.md").read_text()
    assert "## Full candidate distributions" in markdown
    assert "## Single-layer promotion sensitivity" in markdown
    assert "## Target-role score sensitivity" in markdown
    assert "## Promotion caps" in markdown
    assert "0.015-0.049" in markdown
    assert "| threshold | pass | fail |" in markdown
    assert "unavailable_from_emitted_index" in markdown
    assert "Upper bound before cluster dedup" in markdown
    template = tmp_path / "OWNER_DECISION_LOG_TEMPLATE.md"
    assert "Owner decision" in template.read_text(encoding="utf-8")
    assert not (tmp_path / "recipe_catalog.json").exists()
