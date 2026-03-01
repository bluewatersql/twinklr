#!/usr/bin/env python3
"""Run sequence pack profiling demos over vendor example archives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from twinklr.core.feature_store.backends.null import NullFeatureStore
from twinklr.core.feature_store.factory import create_feature_store
from twinklr.core.feature_store.models import FeatureStoreConfig
from twinklr.core.profiling.profiler import SequencePackProfiler
from twinklr.core.profiling.report import generate_layout_report_md

if TYPE_CHECKING:
    from twinklr.core.feature_store.protocols import FeatureStoreProviderSync

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "data" / "vendor_packages"
TEST_DIR = ROOT / "data" / "profiles"


def _find_default_inputs() -> list[Path]:
    inputs: list[Path] = []
    for index in range(1, 15):
        zip_path = VENDOR_DIR / f"example{index}.zip"
        xsqz_path = VENDOR_DIR / f"example{index}.xsqz"
        if zip_path.exists():
            inputs.append(zip_path)
        elif xsqz_path.exists():
            inputs.append(xsqz_path)
    return inputs


def _default_output_dir(input_path: Path) -> Path:
    stem = input_path.stem
    if stem.startswith("example"):
        return TEST_DIR / stem
    return TEST_DIR / f"profile_{stem}"


def _print_summary(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("No inputs processed.")
        return

    headers = (
        "status",
        "source",
        "song",
        "duration_ms",
        "events",
        "models",
        "groups",
        "source_ext",
    )
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(row.get(header, "")))

    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    sep_line = "-+-".join("-" * widths[header] for header in headers)
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(row.get(header, "").ljust(widths[header]) for header in headers))


def _profile_layout_only(
    profiler: SequencePackProfiler, input_path: Path, output_dir: Path
) -> dict[str, str]:
    layout = profiler.profile_layout(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rgbeffects_profile.json").write_text(
        json.dumps(layout.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (output_dir / "profile_rgbeffects.md").write_text(
        generate_layout_report_md(layout), encoding="utf-8"
    )
    return {
        "status": "NEW",
        "source": input_path.name,
        "song": "-",
        "duration_ms": "-",
        "events": "-",
        "models": str(layout.statistics.total_models),
        "groups": str(len(layout.groups)),
        "source_ext": input_path.suffix.lower(),
    }


def _profile_archive(
    profiler: SequencePackProfiler,
    input_path: Path,
    output_dir: Path,
    *,
    force: bool = False,
    prev_profile_count: int = 0,
    store,
) -> dict[str, str]:
    profile = profiler.profile(input_path, output_dir, force=force)
    source_ext = sorted(profile.manifest.source_extensions)

    # Detect skip vs. new by comparing store profile count
    new_count = len(store.query_profiles()) if not isinstance(store, NullFeatureStore) else None
    if new_count is not None:
        status = "NEW" if new_count > prev_profile_count else "SKIP"
    else:
        # NullFeatureStore: check if sequence_metadata.json existed before profiling
        metadata_path = output_dir / "sequence_metadata.json"
        status = "SKIP" if metadata_path.exists() and not force else "NEW"

    return {
        "status": status,
        "source": input_path.name,
        "song": profile.sequence_metadata.song,
        "duration_ms": str(profile.sequence_metadata.sequence_duration_ms),
        "events": str(profile.effect_statistics.total_events),
        "models": str(
            profile.layout_profile.statistics.total_models if profile.layout_profile else 0
        ),
        "groups": str(len(profile.layout_profile.groups) if profile.layout_profile else 0),
        "source_ext": ",".join(source_ext),
    }


def _error_row(input_path: Path, error: Exception) -> dict[str, str]:
    return {
        "status": "ERROR",
        "source": input_path.name,
        "song": f"ERROR: {type(error).__name__}",
        "duration_ms": "-",
        "events": "-",
        "models": "-",
        "groups": "-",
        "source_ext": input_path.suffix.lower(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run twinklr sequence pack profiling demo.")
    parser.add_argument(
        "--input", type=Path, help="Input .zip/.xsqz package or xlights_rgbeffects.xml file."
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory for profiling artifacts.")
    parser.add_argument(
        "--feature-store-db",
        type=Path,
        default=None,
        help="Path to SQLite feature store DB. If omitted, uses in-memory null store.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force full profiling even if a cached result exists.",
    )
    args = parser.parse_args()

    # Build store
    store: FeatureStoreProviderSync = NullFeatureStore()
    if args.feature_store_db is not None:
        cfg = FeatureStoreConfig(backend="sqlite", db_path=Path(args.feature_store_db))
        store = create_feature_store(cfg)
    store.initialize()

    rows: list[dict[str, str]] = []

    try:
        profiler = SequencePackProfiler(store=store)

        if args.input is not None:
            input_path = args.input.resolve()
            output_dir = (
                args.output_dir.resolve() if args.output_dir else _default_output_dir(input_path)
            )
            if input_path.suffix.lower() == ".xml":
                rows.append(_profile_layout_only(profiler, input_path, output_dir))
            else:
                prev_count = len(store.query_profiles())
                rows.append(
                    _profile_archive(
                        profiler,
                        input_path,
                        output_dir,
                        force=args.force,
                        prev_profile_count=prev_count,
                        store=store,
                    )
                )
            _print_summary(rows)
            return 0

        for input_path in _find_default_inputs():
            output_dir = _default_output_dir(input_path)
            try:
                prev_count = len(store.query_profiles())
                rows.append(
                    _profile_archive(
                        profiler,
                        input_path,
                        output_dir,
                        force=args.force,
                        prev_profile_count=prev_count,
                        store=store,
                    )
                )
            except Exception as exc:
                print(f"Failed to profile {input_path.name}: {exc}", file=sys.stderr)
                rows.append(_error_row(input_path, exc))
    finally:
        store.close()

    _print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
