#!/usr/bin/env python3
"""Render an owner-facing quality-gate report from a staged mining run.

This command is read-only with respect to the live catalog.  It reads staged
artifacts beneath ``--run-dir`` and writes review material there, ready for an
owner session; it never promotes candidates or changes threshold defaults.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.evidence import (
    NUMERIC_VALUE_NAMES,
    EvidenceArtifact,
    MiningRunManifest,
    OwnerDecisionRecord,
    P2KEvidenceManifest,
    QualityGateReviewBundle,
    sha256_file,
    verify_evidence_artifacts,
    verify_staged_artifacts,
)
from twinklr.core.feature_engineering.models.clustering import TemplateClusterCatalog
from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateCatalog
from twinklr.core.feature_engineering.propensity import uncensored_pair_supports
from twinklr.core.feature_engineering.quality_gate_distributions import (
    build_quality_gate_distribution_report,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


def _load_candidates(run_dir: Path) -> tuple[MinedTemplate, ...]:
    candidates: list[MinedTemplate] = []
    for name in ("content_templates.json", "orchestration_templates.json"):
        path = run_dir / name
        if path.exists():
            candidates.extend(TemplateCatalog.model_validate(_read_json(path)).templates)
    if not candidates:
        raise FileNotFoundError(
            "No staged template catalogs found; expected content_templates.json and/or "
            f"orchestration_templates.json under {run_dir}"
        )
    return tuple(candidates)


def _load_target_role_scores(run_dir: Path) -> tuple[float, ...]:
    """Load pre-cutoff role scores written by current mining runs only."""
    scores: list[float] = []
    rows: list[object] = []
    for path in sorted(run_dir.rglob("target_roles.jsonl")):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    parquet_paths = sorted(run_dir.rglob("target_roles.parquet"))
    if parquet_paths:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                "target_roles.parquet is present but pyarrow is unavailable; install the FE extras "
                "or retain target_roles.jsonl for threshold review."
            ) from exc
        for path in parquet_paths:
            rows.extend(pq.read_table(path).to_pylist())
    for row in rows:
        if not isinstance(row, dict):
            continue
        score = row.get("top_role_score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
    return tuple(scores)


def _load_dataset_rows(run_dir: Path, stem: str) -> tuple[dict[str, Any], ...]:
    """Load all emitted rows for a dataset stem from JSONL or Parquet artifacts."""
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob(f"{stem}.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object row in {path}")
            rows.append(payload)
    parquet_paths = sorted(run_dir.rglob(f"{stem}.parquet"))
    if parquet_paths:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError(
                f"{stem}.parquet is present but pyarrow is unavailable; install FE extras "
                "or retain the JSONL artifact for threshold review."
            ) from exc
        for path in parquet_paths:
            rows.extend(dict(row) for row in pq.read_table(path).to_pylist())
    return tuple(rows)


def _load_propensity_pair_supports(run_dir: Path) -> tuple[int, ...]:
    rows = _load_dataset_rows(run_dir, "effect_phrases")
    if not rows:
        raise FileNotFoundError(
            f"No uncensored effect_phrases JSONL/Parquet evidence found under {run_dir}"
        )
    phrases = tuple(EffectPhrase.model_validate(row) for row in rows)
    return uncensored_pair_supports(phrases)


def _load_cluster_memberships(run_dir: Path) -> tuple[tuple[str, ...], ...]:
    path = run_dir / "cluster_candidates.json"
    if not path.exists():
        raise FileNotFoundError(f"Cluster-cap review requires {path}")
    catalog = TemplateClusterCatalog.model_validate(_read_json(path))
    return tuple(cluster.member_template_ids for cluster in catalog.clusters)


def _mining_run_provenance(manifest: MiningRunManifest) -> dict[str, object]:
    """Retain source identity fields without copying owner-local paths."""
    return {
        "source": manifest.provenance.source.model_dump(mode="json"),
        "corpus": {
            "input_fingerprint_sha256": manifest.provenance.corpus.input_fingerprint_sha256,
            "tree_sha256": manifest.provenance.corpus.tree_sha256,
            "sequence_index_sha256": manifest.corpus.sequence_index_sha256,
        },
    }


def _require_verified_mining_manifest(manifest: MiningRunManifest) -> None:
    """Reject threshold review until the unchanged-corpus rerun is proven."""
    if manifest.content_hash_identity.verification.verified_unchanged_rerun is not True:
        raise ValueError(
            "Threshold review requires mining_run_manifest.json with verified_unchanged_rerun=true"
        )
    if manifest.live_catalog_immutability.unchanged is not True:
        raise ValueError("Threshold review requires measured live-catalog immutability")


def _artifact(run_dir: Path, role: str, relative: str) -> EvidenceArtifact:
    path = run_dir / relative
    return EvidenceArtifact.model_validate(
        {
            "role": role,
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    )


def _review_input_paths(run_dir: Path) -> tuple[str, ...]:
    fixed = ["promotion_report.json", "cluster_candidates.json"]
    fixed.extend(
        name
        for name in ("content_templates.json", "orchestration_templates.json")
        if (run_dir / name).is_file()
    )
    for stem in ("effect_phrases", "target_roles"):
        fixed.extend(
            path.relative_to(run_dir).as_posix()
            for suffix in ("jsonl", "parquet")
            for path in sorted(run_dir.rglob(f"{stem}.{suffix}"))
        )
    return tuple(fixed)


def _write_review_bundle(
    run_dir: Path, manifest: MiningRunManifest, report: Mapping[str, object]
) -> tuple[Path, QualityGateReviewBundle]:
    artifacts = [
        _artifact(run_dir, "mining_manifest", "mining_run_manifest.json"),
        *(
            [_artifact(run_dir, "content_candidates", "content_templates.json")]
            if (run_dir / "content_templates.json").is_file()
            else []
        ),
        *(
            [_artifact(run_dir, "orchestration_candidates", "orchestration_templates.json")]
            if (run_dir / "orchestration_templates.json").is_file()
            else []
        ),
        _artifact(run_dir, "promotion_report", "promotion_report.json"),
        _artifact(run_dir, "distribution_report_json", "quality_gate_distribution_report.json"),
        _artifact(run_dir, "distribution_report_markdown", "quality_gate_distribution_report.md"),
    ]
    bundle = QualityGateReviewBundle(
        schema_version="twinklr.quality-gate-review-bundle.v1",
        created_at_utc=manifest.created_at_utc,
        mining_manifest_schema_version=manifest.schema_version,
        mining_manifest_sha256=sha256_file(run_dir / "mining_run_manifest.json"),
        report_schema_version="quality_gate_distribution_report_v2",
        report_sha256=sha256_file(run_dir / "quality_gate_distribution_report.json"),
        artifacts=artifacts,
    )
    if report.get("schema_version") != bundle.report_schema_version:
        raise ValueError("distribution report schema does not match review bundle")
    path = run_dir / "quality_gate_review_bundle.json"
    path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path, bundle


def _decision_template(
    report: Mapping[str, object], bundle: QualityGateReviewBundle, bundle_sha256: str
) -> str:
    numeric_values = _mapping(_mapping(report["threshold_review"])["numeric_values"])
    return (
        json.dumps(
            {
                "schema_version": "twinklr.owner-threshold-decisions.v1",
                "report_schema_version": bundle.report_schema_version,
                "report_sha256": bundle.report_sha256,
                "review_bundle_schema_version": bundle.schema_version,
                "review_bundle_sha256": bundle_sha256,
                "decisions": [
                    {
                        "name": name,
                        "current_value": _mapping(numeric_values[name])["configured"],
                        "decision": "<keep|change|defer>",
                        "changed_value": None,
                        "decided_on": "<YYYY-MM-DD>",
                        "rationale": "<owner rationale>",
                    }
                    for name in NUMERIC_VALUE_NAMES
                ],
            },
            indent=2,
        )
        + "\n"
    )


def _bind_owner_decisions(
    run_dir: Path,
    report: Mapping[str, object],
    bundle: QualityGateReviewBundle,
    *,
    accepted_on: date,
) -> Path:
    bundle_path = run_dir / "quality_gate_review_bundle.json"
    decision_path = run_dir / "OWNER_DECISIONS.json"
    decisions = OwnerDecisionRecord.model_validate_json(decision_path.read_text(encoding="utf-8"))
    verify_evidence_artifacts(bundle.artifacts, run_dir)
    if bundle.report_schema_version != report.get("schema_version"):
        raise ValueError("review bundle binds a stale distribution report version")
    if decisions.report_sha256 != sha256_file(run_dir / "quality_gate_distribution_report.json"):
        raise ValueError("owner decisions bind a stale distribution report hash")
    if decisions.report_schema_version != report.get("schema_version"):
        raise ValueError("owner decisions bind a stale distribution report version")
    if decisions.review_bundle_sha256 != sha256_file(bundle_path):
        raise ValueError("owner decisions bind a stale review-bundle hash")
    if decisions.review_bundle_schema_version != bundle.schema_version:
        raise ValueError("owner decisions bind a stale review-bundle version")
    numeric_values = _mapping(_mapping(report["threshold_review"])["numeric_values"])
    for decision in decisions.decisions:
        if decision.current_value != _mapping(numeric_values[decision.name])["configured"]:
            raise ValueError(f"owner decision current value is stale: {decision.name}")
    evidence = P2KEvidenceManifest(
        schema_version="twinklr.p2k-evidence.v2",
        created_at_utc=datetime.now(UTC),
        review_bundle_schema_version=bundle.schema_version,
        review_bundle_sha256=sha256_file(bundle_path),
        decision_schema_version=decisions.schema_version,
        decision_sha256=sha256_file(decision_path),
        accepted=True,
        accepted_on=accepted_on,
    )
    output = run_dir / "quality_gate_evidence_manifest.json"
    output.write_text(evidence.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output


def _load_report_options(manifest: MiningRunManifest) -> FeatureEngineeringPipelineOptions:
    """Recover the promotion options actually recorded by the mining command."""
    effective = manifest.invocation.effective_options

    def _number(name: str) -> int | float:
        value = effective.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        raise ValueError(f"mining manifest effective option is missing or non-numeric: {name}")

    adaptive = effective.get("recipe_promotion_adaptive_stability")
    if type(adaptive) is not bool:
        raise ValueError("mining manifest adaptive-stability option must be a strict boolean")

    return FeatureEngineeringPipelineOptions(
        recipe_promotion_min_support=int(_number("recipe_promotion_min_support")),
        recipe_promotion_min_stability=float(_number("recipe_promotion_min_stability")),
        recipe_promotion_adaptive_stability=adaptive,
        recipe_promotion_max_per_family=int(_number("recipe_promotion_max_per_family")),
        recipe_promotion_multi_layer_min_support=int(
            _number("recipe_promotion_multi_layer_min_support")
        ),
        recipe_promotion_multi_layer_min_stability=float(
            _number("recipe_promotion_multi_layer_min_stability")
        ),
        recipe_promotion_max_per_cluster=int(_number("recipe_promotion_max_per_cluster")),
    )


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    """Render a compact Markdown table."""
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(str(value) for value in row) + " |" for row in rows),
    ]


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected report mapping, got {type(value).__name__}")
    return value


def _row_mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise TypeError(f"Expected report rows, got {type(value).__name__}")
    return tuple(_mapping(row) for row in value)


def _render_markdown(report: dict[str, object]) -> str:
    population = _mapping(report["candidate_population"])
    histograms = _mapping(report["histograms"])
    promotion = _mapping(report["recipe_promotion"])
    static = _mapping(promotion["static_configured"])
    effective = _mapping(promotion["effective_applied"])
    breakdown = _mapping(promotion["exact_gate_breakdown"])
    review = _mapping(report["threshold_review"])
    numeric_values = _mapping(review["numeric_values"])
    propensity = _mapping(review["propensity"])
    propensity_support = _mapping(propensity["min_support"])
    role = _mapping(review["target_role_score_cutoff"])
    caps = _mapping(review["recipe_promotion_caps"])
    cluster_cap = _mapping(caps["max_per_cluster"])
    discrepancy = _mapping(report["promotion_default_discrepancy"])
    risk = _mapping(report["low_pack_ratio_risk"])

    lines = [
        "# Quality-gate distribution review",
        "",
        "Owner-session evidence only. This report does not change thresholds or promote recipes.",
        "",
        "## Candidate population and exact quality gate",
        "",
        *_markdown_table(("population", "count"), tuple(population.items())),
        "",
        f"Static configured thresholds: `{dict(static)}`",
        "",
        f"Effective applied thresholds: `{dict(effective)}`",
        "",
        *_markdown_table(("gate result", "count or note"), tuple(breakdown.items())),
        "",
        "## Numeric review contract",
        "",
        *_markdown_table(
            ("numeric value", "configured", "status", "configured + nearby sensitivity"),
            tuple(
                (
                    name,
                    _mapping(row)["configured"],
                    _mapping(row)["status"],
                    json.dumps(_mapping(row)["sensitivity"], separators=(",", ":")),
                )
                for name, row in numeric_values.items()
            ),
        ),
        "",
        "## Full candidate distributions",
        "",
    ]
    for name in ("support_count", "cross_pack_stability", "distinct_pack_count"):
        histogram = _mapping(histograms[name])
        lines.extend(
            (
                f"### {name}",
                "",
                *_markdown_table(("bucket", "candidate count"), tuple(histogram.items())),
                "",
            )
        )

    lines.extend(("## Single-layer promotion sensitivity", ""))
    lines.append(str(promotion["sensitivity_population"]))
    lines.extend(
        (
            "",
            "### Minimum support",
            "",
            *_markdown_table(
                ("threshold", "pass", "fail"),
                tuple(
                    (row["threshold"], row["pass_count"], row["fail_count"])
                    for row in _row_mappings(promotion["support_sensitivity"])
                ),
            ),
            "",
            "### Minimum stability",
            "",
            *_markdown_table(
                ("threshold", "pass", "fail"),
                tuple(
                    (row["threshold"], row["pass_count"], row["fail_count"])
                    for row in _row_mappings(promotion["stability_sensitivity"])
                ),
            ),
            "",
            "## Pack-count risk among exact gate passes",
            "",
            *_markdown_table(("measure", "count"), tuple(risk.items())),
            "",
            "## Target-role score sensitivity",
            "",
            f"Status: `{role['status']}`; source: {role['source']}",
            "",
            *_markdown_table(
                ("threshold", "pass", "fail"),
                tuple(
                    (row["threshold"], row["pass_count"], row["fail_count"])
                    for row in _row_mappings(role["sensitivity"])
                ),
            ),
            "",
            "## Promotion caps",
            "",
            str(caps["max_per_family_equivalence"]),
            "",
            *_markdown_table(
                ("family cap", "would keep", "would cap"),
                tuple(
                    (row["cap"], row["would_keep"], row["would_cap"])
                    for row in _row_mappings(caps["max_per_family_sensitivity"])
                ),
            ),
            "",
            f"Cluster-cap sensitivity: `{cluster_cap['status']}`",
            "",
            *_markdown_table(
                ("cluster cap", "would keep", "would cap"),
                tuple(
                    (row["cap"], row["would_keep"], row["would_cap"])
                    for row in _row_mappings(cluster_cap["sensitivity"])
                ),
            ),
            "",
            "## Evidence limitations and discrepancies",
            "",
            f"- Propensity min-support sensitivity: `{propensity_support['status']}` from {propensity_support['source']}.",
            "- The former anti-affinity threshold was removed: it was dead code; anti-affinities remain defined by zero co-occurrence with supported marginals.",
            f"- `PromotionPipeline.run()` defaults: `{discrepancy['pipeline_run_defaults']}`",
            f"- Configured FE pipeline values: `{discrepancy['configured_pipeline_values']}`",
            f"- Required owner action: {discrepancy['owner_action_required']}",
            "",
        )
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report staged mining-candidate quality distributions."
    )
    parser.add_argument(
        "--run-dir", required=True, type=Path, help="Staged FE mining output directory."
    )
    parser.add_argument(
        "--bind-owner-decisions",
        action="store_true",
        help=(
            "Require a completed owner decision record and emit the final hash-binding "
            "evidence manifest."
        ),
    )
    parser.add_argument(
        "--accepted-on",
        type=date.fromisoformat,
        help="Owner acceptance date (YYYY-MM-DD); required with --bind-owner-decisions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bind_owner_decisions != (args.accepted_on is not None):
        raise ValueError("--bind-owner-decisions and --accepted-on must be supplied together")
    run_dir = args.run_dir.resolve()
    mining_manifest_path = run_dir / "mining_run_manifest.json"
    if not mining_manifest_path.exists():
        raise FileNotFoundError(f"Evidence binding requires {mining_manifest_path}")
    mining_manifest = MiningRunManifest.model_validate_json(
        mining_manifest_path.read_text(encoding="utf-8")
    )
    _require_verified_mining_manifest(mining_manifest)
    review_inputs = _review_input_paths(run_dir)
    verify_staged_artifacts(
        mining_manifest.candidate_staging.recursive_artifacts,
        run_dir,
        required_paths=review_inputs,
    )
    if args.bind_owner_decisions:
        report_path = run_dir / "quality_gate_distribution_report.json"
        bundle_path = run_dir / "quality_gate_review_bundle.json"
        report = _read_json(report_path)
        bundle = QualityGateReviewBundle.model_validate_json(
            bundle_path.read_text(encoding="utf-8")
        )
        if bundle.report_sha256 != sha256_file(report_path):
            raise ValueError("review bundle does not match current distribution report")
        evidence_path = _bind_owner_decisions(run_dir, report, bundle, accepted_on=args.accepted_on)
        print(f"Evidence manifest: {evidence_path}")
        return 0

    candidates = _load_candidates(run_dir)
    promotion_path = run_dir / "promotion_report.json"
    if not promotion_path.exists():
        raise FileNotFoundError(f"Applied-threshold review requires {promotion_path}")
    promotion_report = _read_json(promotion_path)
    provenance = _mining_run_provenance(mining_manifest)
    role_scores = _load_target_role_scores(run_dir)
    if not role_scores:
        raise FileNotFoundError(
            f"Target-role cutoff review requires top_role_score evidence under {run_dir}"
        )
    report = build_quality_gate_distribution_report(
        candidates,
        options=_load_report_options(mining_manifest),
        promotion_report=promotion_report,
        role_scores=role_scores,
        propensity_pair_supports=_load_propensity_pair_supports(run_dir),
        cluster_memberships=_load_cluster_memberships(run_dir),
        mining_run_provenance=provenance,
    )
    json_path = run_dir / "quality_gate_distribution_report.json"
    markdown_path = run_dir / "quality_gate_distribution_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    bundle_path, bundle = _write_review_bundle(run_dir, mining_manifest, report)
    template_path = run_dir / "OWNER_DECISIONS.json"
    if not template_path.exists():
        template_path.write_text(
            _decision_template(report, bundle, sha256_file(bundle_path)), encoding="utf-8"
        )
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"Owner decision template: {template_path}")
    print(f"Review bundle: {bundle_path}")
    print(
        "Final evidence manifest deferred: complete OWNER_DECISIONS.json and rerun "
        "with --bind-owner-decisions --accepted-on YYYY-MM-DD."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
