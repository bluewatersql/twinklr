#!/usr/bin/env python3
"""Validate FE pipeline output after remediation phases.

Checks all DB tables, artifact files, quality metrics, and enrichment
outputs against the acceptance criteria from the FE Evaluation
Remediation spec.

Usage::

    uv run python scripts/validate_fe_output.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

DB_PATH = Path("data/features/twinklr.db")
FE_ROOT = Path("data/features/feature_engineering")
REF_ROOT = Path("data/reference")

checks: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    """Record a check result and print status."""
    checks.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))


def validate_db() -> None:
    """Validate DB tables and row counts."""
    print("\n== Database Validation ==")

    if not DB_PATH.exists():
        check("DB exists", False, f"{DB_PATH} not found")
        return

    check("DB exists", True, str(DB_PATH))
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # fe_status distribution
    try:
        rows = conn.execute(
            "SELECT fe_status, COUNT(*) as cnt FROM profiles GROUP BY fe_status"
        ).fetchall()
        status_dist = {r["fe_status"]: r["cnt"] for r in rows}
        total_profiles = sum(status_dist.values())
        complete_count = status_dist.get("complete", 0)
        check(
            "Profiles total",
            total_profiles >= 59,
            f"{total_profiles} profiles (need >= 59)",
        )
        check(
            "fe_status=complete profiles",
            complete_count >= 59,
            f"{complete_count} complete (need >= 59)",
        )
        check(
            "fe_status distribution",
            True,
            ", ".join(f"{k}={v}" for k, v in sorted(status_dist.items())),
        )
    except sqlite3.OperationalError as exc:
        check("Profiles table", False, str(exc))

    # Table row counts
    table_minimums = {
        "phrases": 100_000,
        "taxonomy": 100_000,
        "templates": 5_000,
        "stacks": 50_000,
        "recipes": 50,
    }
    for table, minimum in table_minimums.items():
        try:
            (count,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            check(
                f"{table} rows",
                count >= minimum,
                f"{count:,} (need >= {minimum:,})",
            )
        except sqlite3.OperationalError as exc:
            check(f"{table} table", False, str(exc))

    # corpus_metadata non-null
    try:
        row = conn.execute("SELECT metadata_json FROM corpus_metadata LIMIT 1").fetchone()
        has_metadata = row is not None and row["metadata_json"] is not None
        check("corpus_metadata non-null", has_metadata)
    except sqlite3.OperationalError as exc:
        check("corpus_metadata table", False, str(exc))

    conn.close()


def validate_recipe_catalog() -> None:
    """Validate recipe_catalog.json metrics."""
    print("\n== Recipe Catalog Validation ==")

    catalog_path = FE_ROOT / "recipe_catalog.json"
    if not catalog_path.exists():
        check("recipe_catalog.json exists", False)
        return

    check("recipe_catalog.json exists", True)
    data = json.loads(catalog_path.read_text())
    recipes = data if isinstance(data, list) else data.get("recipes", [])
    total = len(recipes)

    check("Total recipes >= 50", total >= 50, f"{total} recipes")

    # Family coverage
    families = {
        r.get("effect_family", r.get("layers", [{}])[0].get("effect_type", "unknown")).lower()
        for r in recipes
        if r
    }
    check(
        "Family coverage >= 15",
        len(families) >= 15,
        f"{len(families)} families",
    )

    # Multi-layer counts
    multi_layer = [r for r in recipes if len(r.get("layers", [])) >= 2]
    three_plus = [r for r in recipes if len(r.get("layers", [])) >= 3]
    check(
        "Multi-layer recipes >= 20",
        len(multi_layer) >= 20,
        f"{len(multi_layer)} with 2+ layers",
    )
    check(
        "Recipes with 3+ layers >= 5",
        len(three_plus) >= 5,
        f"{len(three_plus)} with 3+ layers",
    )

    if recipes:
        avg_layers = sum(len(r.get("layers", [])) for r in recipes) / len(recipes)
        max_layers = max(len(r.get("layers", [])) for r in recipes)
        check(
            "Avg layers >= 2.0",
            avg_layers >= 2.0,
            f"{avg_layers:.2f}",
        )
        check(
            "Max layers >= 4",
            max_layers >= 4,
            f"{max_layers}",
        )


def validate_promotion_report() -> None:
    """Validate promotion_report.json."""
    print("\n== Promotion Report Validation ==")

    report_path = FE_ROOT / "promotion_report.json"
    if not report_path.exists():
        check("promotion_report.json exists", False)
        return

    check("promotion_report.json exists", True)
    report = json.loads(report_path.read_text())

    promoted = report.get("promoted_count", 0)
    check("promoted_count >= 50", promoted >= 50, f"{promoted}")

    ml_promoted = report.get("multi_layer_promoted", 0)
    check("multi_layer_promoted >= 20", ml_promoted >= 20, f"{ml_promoted}")

    # Lane distribution
    lane_dist = report.get("lane_distribution", {})
    for lane in ("BASE", "RHYTHM", "ACCENT"):
        count = lane_dist.get(lane, lane_dist.get(lane.lower(), 0))
        check(f"{lane} lane >= 5", count >= 5, f"{count}")


def validate_quality_report() -> None:
    """Validate quality_report.json."""
    print("\n== Quality Report Validation ==")

    report_path = FE_ROOT / "quality_report.json"
    if not report_path.exists():
        check("quality_report.json exists", False)
        return

    check("quality_report.json exists", True)
    report = json.loads(report_path.read_text())
    passed = report.get("passed", report.get("all_passed", False))
    check("Quality gate passed", passed is True, str(passed))

    # Extract template coverage from checks array
    coverage = None
    for chk in report.get("checks", []):
        if chk.get("check_id") == "template_assignment_coverage":
            coverage = chk.get("value")
            break
    if coverage is None:
        coverage = report.get("template_assignment_coverage", report.get("coverage", 0))
    if isinstance(coverage, (int, float)):
        check(
            "Template coverage >= 70%",
            coverage >= 0.70,
            f"{coverage:.1%}" if coverage <= 1.0 else f"{coverage}%",
        )


def validate_enrichment_artifacts() -> None:
    """Validate enrichment and reference data files."""
    print("\n== Enrichment Artifacts Validation ==")

    artifact_checks = [
        (FE_ROOT / "color_arc.json", "color_arc.json"),
        (FE_ROOT / "temporal_motif_catalog.json", "temporal_motif_catalog.json"),
    ]
    for path, name in artifact_checks:
        check(f"{name} exists", path.exists())

    enrichment_files = [
        "effect_metadata.json",
        "vocabulary_extensions.json",
    ]
    for fname in enrichment_files:
        path = FE_ROOT / fname
        check(f"{fname} exists", path.exists())


def main() -> int:
    """Run all validation checks."""
    print("=" * 60)
    print("FE Pipeline Output Validation")
    print("=" * 60)

    validate_db()
    validate_recipe_catalog()
    validate_promotion_report()
    validate_quality_report()
    validate_enrichment_artifacts()

    # Summary
    passed_count = sum(1 for _, p, _ in checks if p)
    failed_count = sum(1 for _, p, _ in checks if not p)
    total = len(checks)

    print("\n" + "=" * 60)
    if failed_count:
        print(f"RESULT: {failed_count}/{total} checks FAILED")
        print("=" * 60)
        print("\nFailed checks:")
        for name, passed, detail in checks:
            if not passed:
                print(f"  - {name}" + (f": {detail}" if detail else ""))
        return 1
    else:
        print(f"RESULT: All {total} checks PASSED")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
