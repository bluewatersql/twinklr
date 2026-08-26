"""Tests for the owner-facing mined-candidate quality-gate report."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.report_quality_gate_distributions import (
    _require_complete_owner_decisions,
    _require_verified_mining_manifest,
)
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.models.clustering import (
    TemplateClusterCandidate,
    TemplateClusterCatalog,
)
from twinklr.core.feature_engineering.models.templates import (
    MinedTemplate,
    TemplateCatalog,
    TemplateKind,
)
import twinklr.core.feature_engineering.propensity as propensity_module
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


def test_threshold_review_rejects_unverified_mining_or_incomplete_decisions(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="verified_unchanged_rerun=true"):
        _require_verified_mining_manifest({})

    decision_path = tmp_path / "OWNER_DECISION_LOG_TEMPLATE.md"
    decision_path.write_text(
        "# Owner quality-gate decision log\n\n## min_support\n\n"
        "- Date (YYYY-MM-DD):\n- Owner decision: keep / change to … / defer\n- Rationale:\n",
        encoding="utf-8",
    )
    report = {"threshold_review": {"numeric_values": {"min_support": {}}}}
    with pytest.raises(ValueError, match="requires a YYYY-MM-DD date"):
        _require_complete_owner_decisions(decision_path, report)


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
        role_scores=(),
        propensity_pair_supports=(1, 2, 3, 5),
        cluster_memberships=(),
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
        propensity_pair_supports=(1, 2, 3, 5),
        cluster_memberships=(("low-pack", "high-pack", "other"),),
    )

    risk = report["low_pack_ratio_risk"]
    assert risk == {
        "exact_gate_pass_count": 3,
        "exact_gate_passes_with_one_pack": 1,
        "exact_gate_passes_with_two_or_fewer_packs": 2,
    }
    caps = report["threshold_review"]["recipe_promotion_caps"]
    assert caps["max_per_family_sensitivity"] == [
        {"cap": 5, "would_keep": 2, "would_cap": 0},
        {"cap": 10, "would_keep": 2, "would_cap": 0},
        {"cap": 15, "would_keep": 2, "would_cap": 0},
    ]
    assert caps["max_per_cluster"] == {
        "configured": 2,
        "status": "available",
        "sensitivity": [
            {"cap": 1, "would_keep": 1, "would_cap": 2},
            {"cap": 2, "would_keep": 2, "would_cap": 1},
            {"cap": 3, "would_keep": 3, "would_cap": 0},
        ],
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
    propensity_support = report["threshold_review"]["propensity"]["min_support"]
    assert propensity_support == {
        "configured": 3,
        "source": "uncensored effect/model pair support from effect phrases",
        "status": "available",
        "sensitivity": [
            {"threshold": 2, "pass_count": 3, "fail_count": 1},
            {"threshold": 3, "pass_count": 2, "fail_count": 2},
            {"threshold": 5, "pass_count": 1, "fail_count": 3},
        ],
    }
    assert "anti_affinity_threshold" not in report["threshold_review"]["propensity"]

    numeric = report["threshold_review"]["numeric_values"]
    assert tuple(numeric) == (
        "recipe_promotion_min_support",
        "recipe_promotion_min_stability",
        "promotion_run_default_min_support",
        "promotion_run_default_min_stability",
        "propensity_min_support",
        "target_role_score_cutoff",
        "recipe_promotion_max_per_family",
        "recipe_promotion_max_per_cluster",
    )
    assert all(row["status"] == "available" for row in numeric.values())
    assert all(len(row["sensitivity"]) == 3 for row in numeric.values())


def test_report_requires_uncensored_evidence_for_every_retained_numeric_value() -> None:
    """No owner-review contract can silently contain an unavailable sensitivity row."""
    candidate = _candidate("one", support=3, packs=2, stability=0.1)

    for kwargs, message in (
        ({"propensity_pair_supports": None, "cluster_memberships": ()}, "propensity"),
        ({"propensity_pair_supports": (3,), "cluster_memberships": None}, "cluster"),
    ):
        try:
            build_quality_gate_distribution_report(
                [candidate],
                options=FeatureEngineeringPipelineOptions(),
                promotion_report=None,
                role_scores=(0.35,),
                **kwargs,
            )
        except ValueError as exc:
            assert message in str(exc).lower()
        else:
            raise AssertionError("missing raw threshold evidence must fail closed")


def test_dead_anti_affinity_threshold_is_not_part_of_runtime_or_review_contract() -> None:
    """Zero co-occurrence behavior must not masquerade as a numeric review knob."""
    assert not hasattr(propensity_module, "_ANTI_AFFINITY_THRESHOLD")


def test_numeric_contract_always_includes_the_actual_configured_value() -> None:
    """Loaded run options, not default literals, own configured review points."""
    options = FeatureEngineeringPipelineOptions(
        recipe_promotion_min_support=4,
        recipe_promotion_min_stability=0.1,
        recipe_promotion_max_per_family=8,
        recipe_promotion_max_per_cluster=4,
    )
    report = build_quality_gate_distribution_report(
        [_candidate("one", support=5, packs=3, stability=0.3)],
        options=options,
        promotion_report={"effective_min_support": 4, "effective_min_stability": 0.1},
        role_scores=(0.35,),
        propensity_pair_supports=(3,),
        cluster_memberships=(),
    )

    numeric = report["threshold_review"]["numeric_values"]
    for name in (
        "recipe_promotion_min_support",
        "recipe_promotion_min_stability",
        "recipe_promotion_max_per_family",
        "recipe_promotion_max_per_cluster",
    ):
        row = numeric[name]
        key = "cap" if "max_per" in name else "threshold"
        assert row["configured"] in {item[key] for item in row["sensitivity"]}


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
        role_scores=(),
        propensity_pair_supports=(3,),
        cluster_memberships=(),
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
    mining_manifest = {
        "provenance": {
            "source": {"git_commit": "abc123", "git_tree": "tree123"},
            "corpus": {"input_fingerprint_sha256": "input-hash"},
        },
        "content_hash_identity": {"verification": {"verified_unchanged_rerun": True}},
        "live_catalog_immutability": {"unchanged": True},
    }
    (tmp_path / "mining_run_manifest.json").write_text(
        json.dumps(mining_manifest), encoding="utf-8"
    )
    (tmp_path / "effect_phrases.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "schema_version": "v1",
                    "phrase_id": f"p-{index}",
                    "package_id": "pack",
                    "sequence_file_id": "sequence",
                    "effect_event_id": f"event-{index}",
                    "effect_type": "Bars",
                    "effect_family": "bars",
                    "motion_class": "sweep",
                    "color_class": "palette",
                    "energy_class": "mid",
                    "continuity_class": "rhythmic",
                    "spatial_class": "single_target",
                    "source": "effect_type_map",
                    "map_confidence": 1.0,
                    "target_name": "MegaTree",
                    "layer_index": 0,
                    "start_ms": index * 100,
                    "end_ms": index * 100 + 100,
                    "duration_ms": 100,
                    "param_signature": "x",
                }
            )
            for index in range(3)
        )
        + "\n",
        encoding="utf-8",
    )
    cluster_catalog = TemplateClusterCatalog(
        schema_version="v1",
        clusterer_version="test",
        min_cluster_size=2,
        similarity_threshold=0.8,
        total_templates=2,
        total_clusters=1,
        clusters=(
            TemplateClusterCandidate(
                cluster_id="cluster-1",
                cluster_size=2,
                mean_similarity=0.9,
                dominant_effect_family="bars",
                member_template_ids=("one", "two"),
            ),
        ),
    )
    (tmp_path / "cluster_candidates.json").write_text(
        json.dumps(cluster_catalog.model_dump(mode="json")), encoding="utf-8"
    )
    (tmp_path / "target_roles.jsonl").write_text(
        json.dumps({"top_role_score": 0.35}) + "\n", encoding="utf-8"
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
    expected_provenance = mining_manifest["provenance"]
    assert report["mining_run_provenance"] == expected_provenance
    markdown = (tmp_path / "quality_gate_distribution_report.md").read_text()
    assert "## Full candidate distributions" in markdown
    assert "## Single-layer promotion sensitivity" in markdown
    assert "## Target-role score sensitivity" in markdown
    assert "## Promotion caps" in markdown
    assert "0.015-0.049" in markdown
    assert "| threshold | pass | fail |" in markdown
    assert "uncensored effect/model pair support" in markdown
    assert "Cluster-cap sensitivity" in markdown
    template = tmp_path / "OWNER_DECISION_LOG_TEMPLATE.md"
    template_text = template.read_text(encoding="utf-8")
    assert template_text.count("- Date (YYYY-MM-DD):") == 8
    assert template_text.count("- Owner decision:") == 8
    assert template_text.count("- Rationale:") == 8
    assert not (tmp_path / "quality_gate_evidence_manifest.json").exists()
    template.write_text(
        template_text.replace("- Date (YYYY-MM-DD):", "- Date (YYYY-MM-DD): 2026-08-26")
        .replace("- Owner decision: keep / change to … / defer", "- Owner decision: defer")
        .replace("- Rationale:", "- Rationale: Awaiting the private owner corpus."),
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            "scripts/report_quality_gate_distributions.py",
            "--run-dir",
            str(tmp_path),
            "--bind-owner-decisions",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    evidence_manifest = json.loads(
        (tmp_path / "quality_gate_evidence_manifest.json").read_text(encoding="utf-8")
    )
    assert evidence_manifest["schema_version"] == "quality_gate_evidence_manifest_v1"
    assert evidence_manifest["mining_run_provenance"] == expected_provenance
    bound_names = {row["path"] for row in evidence_manifest["artifacts"]}
    assert bound_names == {
        "mining_run_manifest.json",
        "content_templates.json",
        "promotion_report.json",
        "quality_gate_distribution_report.json",
        "quality_gate_distribution_report.md",
        "OWNER_DECISION_LOG_TEMPLATE.md",
    }
    assert all(len(row["sha256"]) == 64 for row in evidence_manifest["artifacts"])
    assert "quality_gate_evidence_manifest.json" not in bound_names
    assert not (tmp_path / "recipe_catalog.json").exists()
