#!/usr/bin/env python3
"""Build consolidated profiling corpora for feature engineering."""

from __future__ import annotations

import argparse
from pathlib import Path

from twinklr.core.profiling.unify import CorpusBuildOptions, ProfileCorpusBuilder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified profile corpus artifacts.")
    parser.add_argument("--include-glob", type=str, default=None, help="Include glob pattern")
    parser.add_argument("--exclude-glob", type=str, default=None, help="Exclude glob pattern")
    parser.add_argument("--schema-version", type=str, default=None, help="Optional schema version")
    parser.add_argument(
        "--write-extent-mb",
        type=int,
        default=256,
        help="Approximate write extent target (MB), default 256",
    )
    parser.add_argument(
        "--min-parse-success-ratio",
        type=float,
        default=0.95,
        help="Minimum parse success ratio quality gate",
    )
    parser.add_argument(
        "--fail-on-quality-gate",
        action="store_true",
        help="Exit non-zero when parse success ratio is below minimum",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    builder = ProfileCorpusBuilder(
        CorpusBuildOptions(
            write_extent_mb=args.write_extent_mb,
            min_parse_success_ratio=args.min_parse_success_ratio,
            fail_on_quality_gate=args.fail_on_quality_gate,
        )
    )

    output_dir = Path("data/profiles_corpus")
    profiles_root = Path("data/profiles")

    try:
        results = builder.build(
            profiles_root=profiles_root,
            output_root=output_dir,
            include_glob=args.include_glob,
            exclude_glob=args.exclude_glob,
            schema_version_filter=args.schema_version,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("schema_version | profiles | sequences | output_dir")
    print("---------------+----------+-----------+-------------------------------")
    for result in results:
        print(
            f"{result.schema_version:14} | {result.profile_count:8d} | "
            f"{result.sequence_count:9d} | {result.output_dir}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
