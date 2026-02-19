#!/usr/bin/env python3
"""Build feature-engineering artifacts from a unified profile corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import threading
import time

from twinklr.core.audio.analyzer import AudioAnalyzer
from twinklr.core.config.models import AppConfig, JobConfig
from twinklr.core.feature_engineering.pipeline import (
    FeatureEngineeringPipeline,
    FeatureEngineeringPipelineOptions,
)


def _count_sequences(corpus_dir: Path) -> int:
    index_path = corpus_dir / "sequence_index.jsonl"
    if not index_path.exists():
        return 0
    count = 0
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        json.loads(line)
        count += 1
    return count


def _count_completed_sequences(output_dir: Path) -> int:
    if not output_dir.exists():
        return 0
    return sum(1 for _ in output_dir.glob("*/*/feature_bundle.json"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build full V1 feature-engineering artifacts from a unified corpus."
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data/profiles_corpus/v0_effectdb_structured_1"),
        help="Unified profile corpus dir",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/features/feature_engineering"),
        help="Output root for feature-engineering artifacts",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.85,
        help="Minimum confidence score to accept audio candidate",
    )
    parser.add_argument(
        "--music-repo",
        type=Path,
        action="append",
        default=[],
        help="Optional additional music repository root(s)",
    )
    parser.add_argument(
        "--extracted-root",
        type=Path,
        action="append",
        default=[],
        help="Optional additional extracted package root(s)",
    )
    parser.add_argument(
        "--audio-required",
        action="store_true",
        help="Fail run when analyzer cannot execute for accepted audio",
    )
    parser.add_argument(
        "--force-reprocess-audio",
        action="store_true",
        help="Force audio analyzer cache bypass",
    )
    parser.add_argument(
        "--skip-audio-analysis",
        action="store_true",
        help="Run discovery only (do not invoke AudioAnalyzer)",
    )
    parser.add_argument(
        "--taxonomy-rules",
        type=Path,
        default=None,
        help="Optional taxonomy rule config override (effect_function_v1.json format)",
    )
    parser.add_argument(
        "--template-min-instance-count",
        type=int,
        default=2,
        help="Minimum phrase instances required to keep a mined template",
    )
    parser.add_argument(
        "--template-min-distinct-pack-count",
        type=int,
        default=1,
        help="Minimum distinct package count required to keep a mined template",
    )
    parser.add_argument(
        "--quality-min-template-coverage",
        type=float,
        default=0.80,
        help="Minimum orchestration template assignment coverage quality threshold",
    )
    parser.add_argument(
        "--quality-min-taxonomy-confidence-mean",
        type=float,
        default=0.30,
        help="Minimum taxonomy confidence mean quality threshold",
    )
    parser.add_argument(
        "--quality-max-unknown-effect-family-ratio",
        type=float,
        default=0.02,
        help="Maximum unknown effect-family ratio quality threshold",
    )
    parser.add_argument(
        "--quality-max-unknown-motion-ratio",
        type=float,
        default=0.02,
        help="Maximum unknown motion-class ratio quality threshold",
    )
    parser.add_argument(
        "--quality-max-single-unknown-effect-type-ratio",
        type=float,
        default=0.01,
        help="Maximum ratio allowed for any one unknown effect type",
    )
    parser.add_argument(
        "--v2-cluster-similarity-threshold",
        type=float,
        default=0.92,
        help="Minimum pairwise similarity required for V2 clustering membership.",
    )
    parser.add_argument(
        "--v2-cluster-min-size",
        type=int,
        default=2,
        help="Minimum template count per V2 cluster candidate.",
    )
    parser.add_argument(
        "--v2-motif-min-distinct-sequences",
        type=int,
        default=2,
        help="Minimum distinct sequences required for reusable motifs.",
    )
    parser.add_argument(
        "--v2-taxonomy-min-recall-for-promotion",
        type=float,
        default=0.55,
        help="Minimum recall required to mark learned taxonomy model promotable.",
    )
    parser.add_argument(
        "--v2-taxonomy-min-f1-for-promotion",
        type=float,
        default=0.60,
        help="Minimum F1 required to mark learned taxonomy model promotable.",
    )
    parser.add_argument(
        "--v2-retrieval-min-recall-at-5",
        type=float,
        default=0.80,
        help="Minimum same-effect-family recall@5 retrieval gate.",
    )
    parser.add_argument(
        "--v2-retrieval-max-avg-latency-ms",
        type=float,
        default=10.0,
        help="Maximum average retrieval query latency gate in milliseconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus_dir = args.corpus_dir.resolve()
    output_dir = args.output_dir.resolve()

    total_sequences = _count_sequences(corpus_dir)
    print(f"Corpus: {corpus_dir}")
    print(f"Output: {output_dir}")
    print(f"Sequences queued: {total_sequences}")

    music_repo_roots = tuple(args.music_repo) if args.music_repo else (Path("data/music"),)
    extracted_roots = (
        tuple(args.extracted_root) if args.extracted_root else (Path("data/vendor_packages"),)
    )

    analyzer = None
    if not args.skip_audio_analysis:
        analyzer = AudioAnalyzer(AppConfig(), JobConfig())

    pipeline = FeatureEngineeringPipeline(
        options=FeatureEngineeringPipelineOptions(
            audio_required=args.audio_required,
            confidence_threshold=args.confidence_threshold,
            music_repo_roots=music_repo_roots,
            extracted_search_roots=extracted_roots,
            force_reprocess_audio=args.force_reprocess_audio,
            taxonomy_rules_path=args.taxonomy_rules,
            template_min_instance_count=args.template_min_instance_count,
            template_min_distinct_pack_count=args.template_min_distinct_pack_count,
            quality_min_template_coverage=args.quality_min_template_coverage,
            quality_min_taxonomy_confidence_mean=args.quality_min_taxonomy_confidence_mean,
            quality_max_unknown_effect_family_ratio=args.quality_max_unknown_effect_family_ratio,
            quality_max_unknown_motion_ratio=args.quality_max_unknown_motion_ratio,
            quality_max_single_unknown_effect_type_ratio=args.quality_max_single_unknown_effect_type_ratio,
            v2_cluster_similarity_threshold=args.v2_cluster_similarity_threshold,
            v2_cluster_min_size=args.v2_cluster_min_size,
            v2_motif_min_distinct_sequence_count=args.v2_motif_min_distinct_sequences,
            v2_taxonomy_min_recall_for_promotion=args.v2_taxonomy_min_recall_for_promotion,
            v2_taxonomy_min_f1_for_promotion=args.v2_taxonomy_min_f1_for_promotion,
            v2_retrieval_min_recall_at_5=args.v2_retrieval_min_recall_at_5,
            v2_retrieval_max_avg_latency_ms=args.v2_retrieval_max_avg_latency_ms,
        ),
        analyzer=analyzer,
    )

    result: dict[str, object] = {"bundles": None, "error": None}

    def _worker() -> None:
        try:
            result["bundles"] = pipeline.run_corpus(corpus_dir, output_dir)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    started = time.time()

    while thread.is_alive():
        processed = _count_completed_sequences(output_dir)
        elapsed = int(time.time() - started)
        if total_sequences > 0:
            print(
                f"\rRunning feature engineering... {processed}/{total_sequences} sequences complete "
                f"({elapsed}s elapsed)",
                end="",
                flush=True,
            )
        else:
            print(
                f"\rRunning feature engineering... {processed} sequences complete ({elapsed}s elapsed)",
                end="",
                flush=True,
            )
        thread.join(timeout=0.5)

    print()

    error = result["error"]
    if error is not None:
        print(f"ERROR: {error}")
        return 1

    bundles = result["bundles"]
    if not isinstance(bundles, list):
        print("ERROR: pipeline returned invalid result")
        return 1

    print("sequences | output_dir")
    print("----------+-------------------------------")
    print(f"{len(bundles):9d} | {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
