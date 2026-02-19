#!/usr/bin/env python3
"""Run a feature-engineering demo with human-readable summaries."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "features" / "demo_feature_engineering"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run feature-engineering demo with reporting.")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/profiles_corpus/v0_effectdb_structured_1"),
        help="Unified profile corpus dir (required unless --skip-build).",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip pipeline run and report from existing artifacts in output-dir.",
    )
    parser.add_argument(
        "--run-audio-analysis",
        action="store_true",
        help="Run audio analysis during build (off by default for faster demo).",
    )
    parser.add_argument(
        "--template-min-instance-count",
        type=int,
        default=2,
        help="Minimum phrase instances per mined template.",
    )
    parser.add_argument(
        "--template-min-distinct-pack-count",
        type=int,
        default=1,
        help="Minimum distinct packs per mined template.",
    )
    parser.add_argument(
        "--quality-max-unknown-effect-family-ratio",
        type=float,
        default=0.85,
        help="Maximum unknown effect-family ratio quality threshold.",
    )
    parser.add_argument(
        "--quality-max-unknown-motion-ratio",
        type=float,
        default=0.85,
        help="Maximum unknown motion-class ratio quality threshold.",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Top-N rows to show in summaries.")
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _read_dataset_rows(sequence_dir: Path, stem: str) -> list[dict[str, Any]]:
    parquet_path = sequence_dir / f"{stem}.parquet"
    jsonl_path = sequence_dir / f"{stem}.jsonl"

    if parquet_path.exists():
        try:
            import pyarrow.parquet as pq
        except Exception:
            pass
        else:
            table = pq.read_table(parquet_path)
            return [row for row in table.to_pylist() if isinstance(row, dict)]

    if jsonl_path.exists():
        return _read_jsonl(jsonl_path)

    return []


def _render_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    divider = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    body = [" | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) for row in rows]
    return "\n".join([header_line, divider, *body])


def _render_markdown_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([head, sep, *body])


def _collect_sequence_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    dirs: list[Path] = []
    for package_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        for sequence_dir in sorted(path for path in package_dir.iterdir() if path.is_dir()):
            if (sequence_dir / "feature_bundle.json").exists():
                dirs.append(sequence_dir)
    return dirs


def _sequence_summary(
    sequence_dirs: list[Path],
) -> tuple[
    list[tuple[str, ...]], Counter[str], Counter[str], int, dict[str, list[tuple[str, str, str]]]
]:
    rows: list[tuple[str, ...]] = []
    taxonomy_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    total_phrases = 0
    by_sha: dict[str, list[tuple[str, str, str]]] = {}

    for sequence_dir in sequence_dirs:
        feature_bundle = _read_json(sequence_dir / "feature_bundle.json")
        phrases = _read_dataset_rows(sequence_dir, "effect_phrases")
        taxonomy = _read_dataset_rows(sequence_dir, "phrase_taxonomy")
        roles = _read_dataset_rows(sequence_dir, "target_roles")

        total_phrases += len(phrases)
        package_id = str(feature_bundle.get("package_id", "-"))
        sequence_file_id = str(feature_bundle.get("sequence_file_id", "-"))
        sequence_name = str(feature_bundle.get("song", "") or sequence_file_id)
        sequence_sha = str(feature_bundle.get("sequence_sha256", ""))
        if sequence_sha:
            by_sha.setdefault(sequence_sha, []).append(
                (package_id, sequence_file_id, sequence_name)
            )

        for row in taxonomy:
            labels = row.get("labels", [])
            if isinstance(labels, list):
                taxonomy_counts.update(str(label) for label in labels)

        for row in roles:
            role = row.get("role")
            if isinstance(role, str):
                role_counts.update([role])

        rows.append(
            (
                package_id,
                sequence_name,
                sequence_file_id,
                str(len(phrases)),
                str(len(taxonomy)),
                str(len(roles)),
                str(feature_bundle.get("audio", {}).get("audio_status", "-")),
                sequence_sha[:12] if sequence_sha else "-",
            )
        )

    return rows, taxonomy_counts, role_counts, total_phrases, by_sha


def _top_rows(counter: Counter[str], top_n: int) -> list[tuple[str, str]]:
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    return [(label, str(count)) for label, count in ordered]


def _template_rows(path: Path, top_n: int) -> list[tuple[str, ...]]:
    if not path.exists():
        return []
    payload = _read_json(path)
    templates = payload.get("templates", [])
    if not isinstance(templates, list):
        return []

    rows: list[tuple[str, ...]] = []
    ranked = sorted(
        [row for row in templates if isinstance(row, dict)],
        key=lambda row: (-int(row.get("support_count", 0)), str(row.get("template_id", ""))),
    )
    for row in ranked[:top_n]:
        rows.append(
            (
                str(row.get("template_id", "")),
                str(row.get("support_count", 0)),
                str(row.get("distinct_pack_count", 0)),
                str(row.get("effect_family", "")),
            )
        )
    return rows


def _write_markdown(
    output_dir: Path,
    sequence_rows: list[tuple[str, ...]],
    taxonomy_rows: list[tuple[str, str]],
    role_rows: list[tuple[str, str]],
    content_template_rows: list[tuple[str, ...]],
    orchestration_template_rows: list[tuple[str, ...]],
    transition_graph: dict[str, Any] | None,
    quality_report: dict[str, Any] | None,
    total_phrases: int,
    duplicate_groups: list[tuple[str, list[tuple[str, str, str]]]],
) -> Path:
    lines: list[str] = []
    lines.append("# Feature Engineering Demo Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total sequences: {len(sequence_rows)}")
    lines.append(f"- Total phrases: {total_phrases}")
    lines.append("")

    if sequence_rows:
        lines.append("## Sequence Coverage")
        lines.append("")
        lines.append(
            _render_markdown_table(
                (
                    "package_id",
                    "sequence_name",
                    "sequence_file_id",
                    "phrases",
                    "taxonomy",
                    "target_roles",
                    "audio_status",
                    "sequence_sha12",
                ),
                sequence_rows,
            )
        )
        lines.append("")

    if duplicate_groups:
        lines.append("## Duplicate Sequence Warning")
        lines.append("")
        lines.append(
            "Detected sequences sharing the same `sequence_sha256` (likely duplicated source sequence content)."
        )
        lines.append("")
        for sha, items in duplicate_groups:
            lines.append(f"- SHA `{sha}`")
            for package_id, sequence_file_id, sequence_name in items:
                lines.append(f"  - `{package_id}` / `{sequence_file_id}` / `{sequence_name}`")
        lines.append("")

    if taxonomy_rows:
        lines.append("## Top Taxonomy Labels")
        lines.append("")
        lines.append(_render_markdown_table(("label", "count"), taxonomy_rows))
        lines.append("")

    if role_rows:
        lines.append("## Target Role Distribution")
        lines.append("")
        lines.append(_render_markdown_table(("role", "count"), role_rows))
        lines.append("")

    if content_template_rows:
        lines.append("## Content Templates")
        lines.append("")
        lines.append(
            _render_markdown_table(
                ("template_id", "support", "packs", "effect_family"), content_template_rows
            )
        )
        lines.append("")

    if orchestration_template_rows:
        lines.append("## Orchestration Templates")
        lines.append("")
        lines.append(
            _render_markdown_table(
                ("template_id", "support", "packs", "effect_family"),
                orchestration_template_rows,
            )
        )
        lines.append("")

    if transition_graph:
        lines.append("## Transition Graph")
        lines.append("")
        lines.append(f"- Transitions: {transition_graph.get('total_transitions', 0)}")
        lines.append(f"- Nodes: {transition_graph.get('total_nodes', 0)}")
        lines.append(f"- Edges: {transition_graph.get('total_edges', 0)}")
        anomalies = transition_graph.get("anomalies", [])
        lines.append(f"- Anomalies: {len(anomalies) if isinstance(anomalies, list) else 0}")
        lines.append("")

    if quality_report:
        lines.append("## Quality Gates")
        lines.append("")
        lines.append(f"- Passed: {quality_report.get('passed', False)}")
        checks = quality_report.get("checks", [])
        check_rows: list[tuple[str, str, str, str]] = []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_rows.append(
                    (
                        str(check.get("check_id", "")),
                        str(check.get("passed", False)),
                        str(check.get("value", "")),
                        str(check.get("threshold", "")),
                    )
                )
        if check_rows:
            lines.append("")
            lines.append(
                _render_markdown_table(("check", "passed", "value", "threshold"), check_rows)
            )
            lines.append("")

    report_path = output_dir / "feature_engineering_demo.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()

    if not args.skip_build:
        if args.corpus_dir is None:
            print("ERROR: --corpus-dir is required unless --skip-build is set.")
            return 2
        analyzer = None
        if args.run_audio_analysis:
            from twinklr.core.audio.analyzer import AudioAnalyzer

            analyzer = AudioAnalyzer(AppConfig(), JobConfig())

        pipeline = FeatureEngineeringPipeline(
            options=FeatureEngineeringPipelineOptions(
                template_min_instance_count=args.template_min_instance_count,
                template_min_distinct_pack_count=args.template_min_distinct_pack_count,
                quality_max_unknown_effect_family_ratio=args.quality_max_unknown_effect_family_ratio,
                quality_max_unknown_motion_ratio=args.quality_max_unknown_motion_ratio,
            ),
            analyzer=analyzer,
        )
        bundles = pipeline.run_corpus(args.corpus_dir.resolve(), output_dir)
        print(f"Built feature-engineering artifacts for {len(bundles)} sequences.")

    sequence_dirs = _collect_sequence_dirs(output_dir)
    if not sequence_dirs:
        print("No feature-engineering sequence outputs found.")
        return 1

    sequence_rows, taxonomy_counts, role_counts, total_phrases, by_sha = _sequence_summary(
        sequence_dirs
    )
    duplicate_groups = [
        (sha, items)
        for sha, items in sorted(by_sha.items(), key=lambda item: item[0])
        if len(items) > 1
    ]

    taxonomy_rows = _top_rows(taxonomy_counts, args.top_n)
    role_rows = _top_rows(role_counts, args.top_n)
    content_template_rows = _template_rows(output_dir / "content_templates.json", args.top_n)
    orchestration_template_rows = _template_rows(
        output_dir / "orchestration_templates.json", args.top_n
    )

    transition_graph = None
    transition_graph_path = output_dir / "transition_graph.json"
    if transition_graph_path.exists():
        transition_graph = _read_json(transition_graph_path)

    quality_report = None
    quality_report_path = output_dir / "quality_report.json"
    if quality_report_path.exists():
        quality_report = _read_json(quality_report_path)

    print("\nFeature Engineering Summary")
    print("===========================")
    print(f"Output directory : {output_dir}")
    print(f"Sequences        : {len(sequence_rows)}")
    print(f"Total phrases    : {total_phrases}")

    print("\nPer-Sequence Coverage")
    print(
        _render_table(
            (
                "package_id",
                "sequence_name",
                "sequence_file_id",
                "phrases",
                "taxonomy",
                "target_roles",
                "audio_status",
                "sequence_sha12",
            ),
            sequence_rows,
        )
    )

    if duplicate_groups:
        print("\nDuplicate Sequence Warning")
        print(
            "Detected sequences sharing identical sequence_sha256 (likely duplicated source sequence content):"
        )
        for sha, items in duplicate_groups:
            print(f"- {sha}")
            for package_id, sequence_file_id, sequence_name in items:
                print(f"  - {package_id} | {sequence_file_id} | {sequence_name}")

    if taxonomy_rows:
        print("\nTop Taxonomy Labels")
        print(_render_table(("label", "count"), taxonomy_rows))

    if role_rows:
        print("\nTarget Role Distribution")
        print(_render_table(("role", "count"), role_rows))

    if content_template_rows:
        print("\nTop Content Templates")
        print(
            _render_table(
                ("template_id", "support", "packs", "effect_family"), content_template_rows
            )
        )

    if orchestration_template_rows:
        print("\nTop Orchestration Templates")
        print(
            _render_table(
                ("template_id", "support", "packs", "effect_family"),
                orchestration_template_rows,
            )
        )

    if transition_graph is not None:
        print("\nTransition Graph")
        print(f"Transitions : {transition_graph.get('total_transitions', 0)}")
        print(f"Nodes       : {transition_graph.get('total_nodes', 0)}")
        print(f"Edges       : {transition_graph.get('total_edges', 0)}")
        anomalies = transition_graph.get("anomalies", [])
        anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
        print(f"Anomalies   : {anomaly_count}")

    if quality_report is not None:
        print("\nQuality Gates")
        print(f"Passed: {quality_report.get('passed', False)}")
        checks = quality_report.get("checks", [])
        check_rows: list[tuple[str, str, str, str]] = []
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                check_rows.append(
                    (
                        str(check.get("check_id", "")),
                        str(check.get("passed", False)),
                        str(check.get("value", "")),
                        str(check.get("threshold", "")),
                    )
                )
        if check_rows:
            print(_render_table(("check", "passed", "value", "threshold"), check_rows))

    report_path = _write_markdown(
        output_dir=output_dir,
        sequence_rows=sequence_rows,
        taxonomy_rows=taxonomy_rows,
        role_rows=role_rows,
        content_template_rows=content_template_rows,
        orchestration_template_rows=orchestration_template_rows,
        transition_graph=transition_graph,
        quality_report=quality_report,
        total_phrases=total_phrases,
        duplicate_groups=duplicate_groups,
    )
    print(f"\nMarkdown report written: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
