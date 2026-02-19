#!/usr/bin/env python3
"""Query template retrieval recommendations from a feature-engineering run."""

from __future__ import annotations

import argparse
from pathlib import Path

from twinklr.core.feature_engineering.models.templates import TemplateKind
from twinklr.core.feature_engineering.retrieval import (
    TemplateQuery,
    TemplateRetrievalQueryEngine,
)


def _render_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))
    header_line = " | ".join(header.ljust(widths[idx]) for idx, header in enumerate(headers))
    divider = "-+-".join("-" * widths[idx] for idx in range(len(headers)))
    body = [" | ".join(value.ljust(widths[idx]) for idx, value in enumerate(row)) for row in rows]
    return "\n".join([header_line, divider, *body])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query template retrieval baseline output.")
    parser.add_argument(
        "--feature-dir",
        type=Path,
        default=Path("data/features/feature_engineering"),
        help="Feature-engineering run output root containing template_retrieval_index.json",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Maximum recommendations to return")
    parser.add_argument(
        "--template-kind",
        choices=("all", "content", "orchestration"),
        default="all",
        help="Optional template kind filter",
    )
    parser.add_argument("--role", type=str, default=None, help="Optional role filter (e.g., lead)")
    parser.add_argument("--effect-family", type=str, default=None, help="Optional effect-family filter")
    parser.add_argument("--motion-class", type=str, default=None, help="Optional motion-class filter")
    parser.add_argument("--energy-class", type=str, default=None, help="Optional energy-class filter")
    parser.add_argument("--min-base-score", type=float, default=0.0, help="Minimum base retrieval score")
    parser.add_argument(
        "--min-transition-flow",
        type=float,
        default=0.0,
        help="Minimum transition-flow normalized score",
    )
    parser.add_argument(
        "--min-taxonomy-label-count",
        type=int,
        default=0,
        help="Minimum taxonomy-label count",
    )
    return parser.parse_args()


def _kind_from_arg(value: str) -> TemplateKind | None:
    if value == "content":
        return TemplateKind.CONTENT
    if value == "orchestration":
        return TemplateKind.ORCHESTRATION
    return None


def main() -> int:
    args = parse_args()
    index_path = args.feature_dir.resolve() / "template_retrieval_index.json"
    if not index_path.exists():
        print(f"ERROR: missing retrieval index: {index_path}")
        return 1

    engine = TemplateRetrievalQueryEngine()
    index = engine.load_index(index_path)
    query = TemplateQuery(
        template_kind=_kind_from_arg(args.template_kind),
        role=args.role,
        effect_family=args.effect_family,
        motion_class=args.motion_class,
        energy_class=args.energy_class,
        min_base_score=args.min_base_score,
        min_transition_flow=args.min_transition_flow,
        min_taxonomy_label_count=args.min_taxonomy_label_count,
        top_n=args.top_n,
    )
    rows = engine.query(index=index, query=query)
    if not rows:
        print("No templates matched query.")
        return 0

    print(f"Index: {index_path}")
    print(f"Matched: {len(rows)} templates")
    table_rows = [
        (
            str(row.rank),
            row.template_kind.value,
            f"{row.retrieval_score:.6f}",
            f"{row.transition_flow_norm:.6f}",
            row.effect_family,
            row.role or "-",
            row.template_id,
        )
        for row in rows
    ]
    print(
        _render_table(
            ("rank", "kind", "score", "flow", "effect_family", "role", "template_id"),
            table_rows,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

