#!/usr/bin/env python3
"""Render an owner-facing quality-gate report from a staged mining run.

This command is read-only with respect to the live catalog.  It reads staged
artifacts beneath ``--run-dir`` and writes review material there, ready for an
owner session; it never promotes candidates or changes threshold defaults.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
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


def _mining_run_provenance(manifest: Mapping[str, object] | None) -> dict[str, object]:
    """Retain source identity fields without copying owner-local paths."""
    if manifest is None:
        return {}
    selected: dict[str, object] = {}
    provenance = manifest.get("provenance")
    if isinstance(provenance, Mapping):
        source = provenance.get("source")
        if isinstance(source, Mapping):
            selected["source"] = {
                key: source[key]
                for key in ("git_commit", "git_tree", "tracked_diff_sha256")
                if key in source
            }
        provenance_corpus = provenance.get("corpus")
        if isinstance(provenance_corpus, Mapping):
            selected["corpus"] = {
                key: provenance_corpus[key]
                for key in (
                    "input_fingerprint_sha256",
                    "tree_sha256",
                    "sequence_index_sha256",
                )
                if key in provenance_corpus
            }
    for key in ("source_git_sha", "git_sha", "input_fingerprint"):
        if key in manifest:
            selected[key] = manifest[key]
    corpus = manifest.get("corpus")
    if isinstance(corpus, Mapping):
        corpus_identity = {
            key: corpus[key]
            for key in ("input_fingerprint_sha256", "sequence_index_sha256")
            if key in corpus
        }
        if corpus_identity:
            selected.setdefault("corpus", corpus_identity)
    return selected


def _require_verified_mining_manifest(manifest: Mapping[str, object]) -> None:
    """Reject threshold review until the unchanged-corpus rerun is proven."""
    identity = manifest.get("content_hash_identity")
    verification = identity.get("verification") if isinstance(identity, Mapping) else None
    if not isinstance(verification, Mapping) or not verification.get("verified_unchanged_rerun"):
        raise ValueError(
            "Threshold review requires mining_run_manifest.json with verified_unchanged_rerun=true"
        )
    catalog = manifest.get("live_catalog_immutability")
    if not isinstance(catalog, Mapping) or catalog.get("unchanged") is not True:
        raise ValueError("Threshold review requires measured live-catalog immutability")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_evidence_manifest(run_dir: Path, *, mining_run_provenance: Mapping[str, object]) -> Path:
    """Bind source and generated evidence without a circular self-hash."""
    required = (
        "mining_run_manifest.json",
        "promotion_report.json",
        "quality_gate_distribution_report.json",
        "quality_gate_distribution_report.md",
        "OWNER_DECISION_LOG_TEMPLATE.md",
    )
    missing = [name for name in required if not (run_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("Evidence binding requires: " + ", ".join(missing))
    candidate_names = (
        "content_templates.json",
        "orchestration_templates.json",
    )
    if not any((run_dir / name).is_file() for name in candidate_names):
        raise FileNotFoundError("Evidence binding requires at least one staged candidate catalog")
    names = (
        *required[:1],
        "content_templates.json",
        "orchestration_templates.json",
        *required[1:],
    )
    artifacts = [
        {"path": name, "sha256": _sha256_file(run_dir / name)}
        for name in names
        if (run_dir / name).exists()
    ]
    output = run_dir / "quality_gate_evidence_manifest.json"
    payload = {
        "schema_version": "quality_gate_evidence_manifest_v1",
        "mining_run_provenance": dict(mining_run_provenance),
        "artifacts": artifacts,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _load_report_options(run_dir: Path) -> FeatureEngineeringPipelineOptions:
    """Recover the promotion options actually recorded by the mining command."""
    manifest_path = run_dir / "mining_run_manifest.json"
    if not manifest_path.exists():
        return FeatureEngineeringPipelineOptions()
    manifest = _read_json(manifest_path)
    invocation = manifest.get("invocation")
    if not isinstance(invocation, dict):
        return FeatureEngineeringPipelineOptions()
    effective = invocation.get("effective_options")
    if not isinstance(effective, dict):
        return FeatureEngineeringPipelineOptions()
    defaults = FeatureEngineeringPipelineOptions()

    def _number(name: str, fallback: int | float) -> int | float:
        value = effective.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        return fallback

    return FeatureEngineeringPipelineOptions(
        recipe_promotion_min_support=int(
            _number("recipe_promotion_min_support", defaults.recipe_promotion_min_support)
        ),
        recipe_promotion_min_stability=float(
            _number("recipe_promotion_min_stability", defaults.recipe_promotion_min_stability)
        ),
        recipe_promotion_adaptive_stability=bool(
            effective.get(
                "recipe_promotion_adaptive_stability",
                defaults.recipe_promotion_adaptive_stability,
            )
        ),
        recipe_promotion_max_per_family=int(
            _number("recipe_promotion_max_per_family", defaults.recipe_promotion_max_per_family)
        ),
        recipe_promotion_multi_layer_min_support=int(
            _number(
                "recipe_promotion_multi_layer_min_support",
                defaults.recipe_promotion_multi_layer_min_support,
            )
        ),
        recipe_promotion_multi_layer_min_stability=float(
            _number(
                "recipe_promotion_multi_layer_min_stability",
                defaults.recipe_promotion_multi_layer_min_stability,
            )
        ),
        recipe_promotion_max_per_cluster=int(
            _number("recipe_promotion_max_per_cluster", defaults.recipe_promotion_max_per_cluster)
        ),
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


def _decision_log_template(report: Mapping[str, object]) -> str:
    """Render one owner entry from the report's single numeric contract."""
    review = _mapping(report["threshold_review"])
    numeric_values = _mapping(review["numeric_values"])
    lines = [
        "# Owner quality-gate decision log",
        "",
        "Complete every entry after reviewing quality_gate_distribution_report.json.",
        "This template is not a decision record until the owner supplies all dates, decisions, and rationales.",
        "",
    ]
    for name, raw_row in numeric_values.items():
        row = _mapping(raw_row)
        lines.extend(
            (
                f"## {name}",
                "",
                f"- Current value: {row['configured']}",
                "- Evidence: quality_gate_distribution_report.json",
                "- Date (YYYY-MM-DD):",
                "- Owner decision: keep / change to … / defer",
                "- Rationale:",
                "",
            )
        )
    return "\n".join(lines)


def _require_complete_owner_decisions(path: Path, report: Mapping[str, object]) -> None:
    """Require one dated, reasoned owner decision for every numeric value."""
    text = path.read_text(encoding="utf-8")
    numeric_values = _mapping(_mapping(report["threshold_review"])["numeric_values"])
    sections = dict(
        re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    )
    if set(sections) != set(numeric_values):
        raise ValueError("Owner decision log headings do not match the numeric review contract")
    for name, body in sections.items():
        date = re.search(r"^- Date \(YYYY-MM-DD\):\s*(\S.*?)\s*$", body, re.MULTILINE)
        decision = re.search(r"^- Owner decision:\s*(\S.*?)\s*$", body, re.MULTILINE)
        rationale = re.search(r"^- Rationale:\s*(\S.*?)\s*$", body, re.MULTILINE)
        if date is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", date.group(1)) is None:
            raise ValueError(f"Owner decision {name} requires a YYYY-MM-DD date")
        if decision is None or not (
            decision.group(1) in {"keep", "defer"} or decision.group(1).startswith("change to ")
        ):
            raise ValueError(f"Owner decision {name} must be keep, defer, or change to VALUE")
        if rationale is None:
            raise ValueError(f"Owner decision {name} requires a rationale")


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
            "Require a completed owner decision log and emit the final hash-binding "
            "evidence manifest."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    candidates = _load_candidates(run_dir)
    promotion_path = run_dir / "promotion_report.json"
    if not promotion_path.exists():
        raise FileNotFoundError(f"Applied-threshold review requires {promotion_path}")
    promotion_report = _read_json(promotion_path)
    mining_manifest_path = run_dir / "mining_run_manifest.json"
    if not mining_manifest_path.exists():
        raise FileNotFoundError(f"Evidence binding requires {mining_manifest_path}")
    mining_manifest = _read_json(mining_manifest_path)
    _require_verified_mining_manifest(mining_manifest)
    provenance = _mining_run_provenance(mining_manifest)
    role_scores = _load_target_role_scores(run_dir)
    if not role_scores:
        raise FileNotFoundError(
            f"Target-role cutoff review requires top_role_score evidence under {run_dir}"
        )
    report = build_quality_gate_distribution_report(
        candidates,
        options=_load_report_options(run_dir),
        promotion_report=promotion_report,
        role_scores=role_scores,
        propensity_pair_supports=_load_propensity_pair_supports(run_dir),
        cluster_memberships=_load_cluster_memberships(run_dir),
        mining_run_provenance=provenance,
    )
    json_path = run_dir / "quality_gate_distribution_report.json"
    markdown_path = run_dir / "quality_gate_distribution_report.md"
    template_path = run_dir / "OWNER_DECISION_LOG_TEMPLATE.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    if not template_path.exists():
        template_path.write_text(_decision_log_template(report), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"Owner decision-log template: {template_path}")
    if args.bind_owner_decisions:
        _require_complete_owner_decisions(template_path, report)
        evidence_path = _write_evidence_manifest(run_dir, mining_run_provenance=provenance)
        print(f"Evidence manifest: {evidence_path}")
    else:
        print(
            "Final evidence manifest deferred: complete the owner decision log and rerun "
            "with --bind-owner-decisions."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
