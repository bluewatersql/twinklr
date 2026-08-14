#!/usr/bin/env python3
"""Render an owner-facing quality-gate report from a staged mining run.

This command is read-only with respect to the live catalog.  It reads staged
artifacts beneath ``--run-dir`` and writes review material there, ready for an
owner session; it never promotes candidates or changes threshold defaults.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.config import FeatureEngineeringPipelineOptions
from twinklr.core.feature_engineering.models.templates import MinedTemplate, TemplateCatalog
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
    propensity = _mapping(review["propensity"])
    propensity_support = _mapping(propensity["min_support"])
    anti_affinity = _mapping(propensity["anti_affinity_threshold"])
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
            f"Cluster-cap sensitivity: `{cluster_cap['status']}` — {cluster_cap['limitation']}",
            "",
            "## Evidence limitations and discrepancies",
            "",
            f"- Propensity min-support sensitivity: `{propensity_support['status']}` — {propensity_support['limitation']}",
            f"- Anti-affinity threshold: `{anti_affinity['status']}` — {anti_affinity['current_behavior']}",
            f"- `PromotionPipeline.run()` defaults: `{discrepancy['pipeline_run_defaults']}`",
            f"- Configured FE pipeline values: `{discrepancy['configured_pipeline_values']}`",
            f"- Required owner action: {discrepancy['owner_action_required']}",
            "",
        )
    )
    return "\n".join(lines)


def _decision_log_template() -> str:
    return """# Owner quality-gate decision log\n\n\
Use one dated entry for each item below after reviewing the matching report evidence.\n\
Do not treat this template as a decision record until the owner supplies a decision and rationale.\n\n\
## Recipe promotion support and stability\n\n\
- Date:\n- Current values: min_support=2; min_stability=0.015\n- Evidence: quality_gate_distribution_report.json\n- Owner decision: keep / change to … / defer\n- Rationale:\n\n\
## PromotionPipeline direct-call defaults discrepancy\n\n\
- Date:\n- Current direct-call defaults: min_support=5; min_stability=0.3\n- Configured pipeline values: min_support=2; min_stability=0.015\n- Owner decision: keep discrepancy / align in separately approved change / defer\n- Rationale:\n\n\
## Propensity gates\n\n\
- Date:\n- Current values: min_support=3; anti_affinity_threshold=0.05\n- Owner decision: keep / change to … / defer\n- Rationale:\n\n\
## Target-role score cutoff\n\n\
- Date:\n- Current value: 0.35\n- Owner decision: keep / change to … / defer\n- Rationale:\n\n\
## Promotion caps\n\n\
- Date:\n- Current values: max_per_family=10; max_per_cluster=2\n- Owner decision: keep / change to … / defer\n- Rationale:\n"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report staged mining-candidate quality distributions."
    )
    parser.add_argument(
        "--run-dir", required=True, type=Path, help="Staged FE mining output directory."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    candidates = _load_candidates(run_dir)
    promotion_path = run_dir / "promotion_report.json"
    promotion_report = _read_json(promotion_path) if promotion_path.exists() else None
    report = build_quality_gate_distribution_report(
        candidates,
        options=_load_report_options(run_dir),
        promotion_report=promotion_report,
        role_scores=_load_target_role_scores(run_dir),
    )
    json_path = run_dir / "quality_gate_distribution_report.json"
    markdown_path = run_dir / "quality_gate_distribution_report.md"
    template_path = run_dir / "OWNER_DECISION_LOG_TEMPLATE.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    if not template_path.exists():
        template_path.write_text(_decision_log_template(), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(f"Owner decision-log template: {template_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
