"""Tests for the owner-facing mined-candidate quality-gate report."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.report_quality_gate_distributions import _require_verified_mining_manifest
from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.evidence import MiningRunManifest, snapshot_tree
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


def test_threshold_review_rejects_unverified_mining() -> None:
    manifest = _mining_manifest(Path("/tmp/run"), verified=False)
    with pytest.raises(ValueError, match="verified_unchanged_rerun=true"):
        _require_verified_mining_manifest(manifest)


def _mining_manifest(run_dir: Path, *, verified: bool = True) -> MiningRunManifest:
    zero = "0" * 64
    tree = (
        snapshot_tree(run_dir)
        if run_dir.exists()
        else {"root": str(run_dir), "exists": False, "file_count": 0, "sha256": None, "files": []}
    )
    options = FeatureEngineeringPipelineOptions()
    effective = {
        name: getattr(options, name)
        for name in (
            "recipe_promotion_min_support",
            "recipe_promotion_min_stability",
            "recipe_promotion_adaptive_stability",
            "recipe_promotion_max_per_family",
            "recipe_promotion_multi_layer_min_support",
            "recipe_promotion_multi_layer_min_stability",
            "recipe_promotion_max_per_cluster",
        )
    }
    return MiningRunManifest.model_validate(
        {
            "schema_version": "twinklr.owner-mining-run.v2",
            "created_at_utc": datetime(2026, 8, 26, tzinfo=UTC),
            "invocation": {
                "exact_command": "mine",
                "exact_rerun_command": "mine",
                "effective_options": effective,
            },
            "corpus": {"path": "/private/corpus", "sequence_index_sha256": zero},
            "output_dir": str(run_dir),
            "sequence_count": 1,
            "provenance": {
                "source": {
                    "git_commit": "a" * 40,
                    "git_tree": "b" * 40,
                    "tracked_diff_sha256": zero,
                },
                "tools": {},
                "corpus": {
                    "path": "/private/corpus",
                    "tree_sha256": zero,
                    "files": {},
                    "input_fingerprint_sha256": zero,
                },
                "profiles": [],
                "music_library_index": {
                    "path": None,
                    "exists": False,
                    "size_bytes": None,
                    "sha256": None,
                    "explicitly_disabled": True,
                },
            },
            "candidate_staging": {"recursive_artifacts": tree, "note": "staged review inputs"},
            "content_hash_identity": {
                "required": True,
                "implementation": "content digest",
                "verification": {
                    "previous_run_after_stats": {},
                    "current_run_before_stats": {},
                    "current_run_after_stats": {},
                    "before_matches_previous_after": verified,
                    "after_matches_before": verified,
                    "input_fingerprint_matches_previous": verified,
                    "source_provenance_matches_previous": verified,
                    "entity_key_digests_match": verified,
                    "entity_content_digests_match": verified,
                    "duplicate_identity_count": 0,
                    "verified_unchanged_rerun": verified,
                    "status": "verified" if verified else "changed",
                },
            },
            "feature_store": {"backend": "sqlite", "path": str(run_dir / "features.db")},
            "feature_store_snapshots": {"before": {}, "after": {}},
            "live_catalog_immutability": {"before": tree, "after": tree, "unchanged": True},
        }
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


def test_family_cap_sensitivity_uses_runtime_recipe_effect_type_grouping() -> None:
    """Deprecated and canonical family names collapse to one runtime effect type."""
    candidates = [
        _candidate("legacy", support=5, packs=3, stability=0.3, family="spiral"),
        _candidate("canonical", support=5, packs=3, stability=0.3, family="spirals"),
    ]

    report = build_quality_gate_distribution_report(
        candidates,
        options=FeatureEngineeringPipelineOptions(recipe_promotion_max_per_family=1),
        promotion_report={"effective_min_support": 2, "effective_min_stability": 0.05},
        role_scores=(0.5,),
        propensity_pair_supports=(3,),
        cluster_memberships=(),
    )

    sensitivity = report["threshold_review"]["recipe_promotion_caps"]["max_per_family_sensitivity"]
    configured = next(row for row in sensitivity if row["cap"] == 1)
    assert configured == {"cap": 1, "would_keep": 1, "would_cap": 1}


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
    mining_manifest = _mining_manifest(tmp_path)
    (tmp_path / "mining_run_manifest.json").write_text(
        mining_manifest.model_dump_json(indent=2), encoding="utf-8"
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
    expected_provenance = {
        "source": mining_manifest.provenance.source.model_dump(mode="json"),
        "corpus": {
            "input_fingerprint_sha256": mining_manifest.provenance.corpus.input_fingerprint_sha256,
            "tree_sha256": mining_manifest.provenance.corpus.tree_sha256,
            "sequence_index_sha256": mining_manifest.corpus.sequence_index_sha256,
        },
    }
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
    template = tmp_path / "OWNER_DECISIONS.json"
    decisions = json.loads(template.read_text(encoding="utf-8"))
    assert len(decisions["decisions"]) == 8
    assert not (tmp_path / "quality_gate_evidence_manifest.json").exists()
    for decision in decisions["decisions"]:
        decision.update(
            decision="defer", decided_on="2026-08-26", rationale="Awaiting private corpus."
        )
    template.write_text(json.dumps(decisions), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/report_quality_gate_distributions.py",
            "--run-dir",
            str(tmp_path),
            "--bind-owner-decisions",
            "--accepted-on",
            "2026-08-26",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    evidence_manifest = json.loads(
        (tmp_path / "quality_gate_evidence_manifest.json").read_text(encoding="utf-8")
    )
    assert evidence_manifest["schema_version"] == "twinklr.p2k-evidence.v2"
    bundle = json.loads((tmp_path / "quality_gate_review_bundle.json").read_text())
    bound_names = {row["path"] for row in bundle["artifacts"]}
    assert bound_names == {
        "mining_run_manifest.json",
        "content_templates.json",
        "promotion_report.json",
        "quality_gate_distribution_report.json",
        "quality_gate_distribution_report.md",
    }
    assert all(len(row["sha256"]) == 64 for row in bundle["artifacts"])
    assert "quality_gate_evidence_manifest.json" not in bound_names
    assert not (tmp_path / "recipe_catalog.json").exists()

    (tmp_path / "quality_gate_distribution_report.md").write_text(
        "tampered after owner review\n", encoding="utf-8"
    )
    stale = subprocess.run(
        [
            sys.executable,
            "scripts/report_quality_gate_distributions.py",
            "--run-dir",
            str(tmp_path),
            "--bind-owner-decisions",
            "--accepted-on",
            "2026-08-26",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert stale.returncode != 0
    assert "bound evidence artifact digest mismatch" in stale.stderr
