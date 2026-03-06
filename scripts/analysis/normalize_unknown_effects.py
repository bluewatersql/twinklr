#!/usr/bin/env python3
"""Run unknown effect normalization pipeline.

Reads unknown_diagnostics.json from a feature engineering output directory,
builds an unknown effect corpus, optionally embeds and clusters effect names,
and generates alias candidates and taxonomy rule patches.

Usage:
    python scripts/analysis/normalize_unknown_effects.py \
        --diagnostics data/features/feature_engineering/unknown_diagnostics.json \
        --output-dir data/features/normalization
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run unknown effect normalization pipeline.")
    parser.add_argument(
        "--diagnostics",
        type=Path,
        required=True,
        help="Path to unknown_diagnostics.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/features/normalization"),
        help="Output directory for normalization artifacts",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="Skip embedding and clustering (corpus-only mode)",
    )
    parser.add_argument(
        "--skip-llm-review",
        action="store_true",
        help="Skip LLM review pass (use clustering output directly)",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.75,
        help="Minimum cosine similarity for clustering",
    )
    parser.add_argument(
        "--min-cluster-size",
        type=int,
        default=2,
        help="Minimum cluster size",
    )
    return parser.parse_args()


def main() -> int:
    """Run normalization pipeline."""
    args = parse_args()

    if not args.diagnostics.exists():
        logger.error("Diagnostics file not found: %s", args.diagnostics)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Build corpus
    from twinklr.core.feature_engineering.normalization.corpus import (
        UnknownEffectCorpusBuilder,
    )

    builder = UnknownEffectCorpusBuilder()
    corpus = builder.build(args.diagnostics)
    logger.info(
        "Corpus: %d entries, unknown_effect_ratio=%.4f, unknown_motion_ratio=%.4f",
        len(corpus.entries),
        corpus.unknown_effect_family_ratio,
        corpus.unknown_motion_ratio,
    )

    corpus_path = args.output_dir / "unknown_effect_corpus.json"
    corpus_path.write_text(corpus.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Wrote corpus: %s", corpus_path)

    if args.skip_embedding or len(corpus.entries) == 0:
        logger.info("Skipping embedding/clustering (--skip-embedding or empty corpus)")
        return 0

    # Step 2: Embed
    from twinklr.core.feature_engineering.normalization.embedder import (
        SentenceTransformerEmbedder,
    )

    embedder = SentenceTransformerEmbedder()
    texts = tuple(e.context_text for e in corpus.entries)
    embeddings = embedder.embed(texts)
    logger.info("Embedded %d entries", len(embeddings))

    # Step 3: Cluster
    from twinklr.core.feature_engineering.normalization.clustering import (
        AliasClustering,
    )
    from twinklr.core.feature_engineering.normalization.models import (
        AliasClusteringOptions,
    )

    options = AliasClusteringOptions(
        min_cluster_size=args.min_cluster_size,
        min_similarity=args.min_similarity,
    )
    clusterer = AliasClustering(options=options)
    clusters = clusterer.cluster(corpus.entries, embeddings)
    logger.info("Found %d alias clusters", len(clusters))

    clusters_path = args.output_dir / "alias_clusters.json"
    clusters_path.write_text(
        json.dumps([c.model_dump(mode="json") for c in clusters], indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote clusters: %s", clusters_path)

    if args.skip_llm_review or len(clusters) == 0:
        logger.info("Skipping LLM review (--skip-llm-review or no clusters)")
        return 0

    # Step 4: LLM review
    from twinklr.core.api.llm.openai.client import OpenAIClient
    from twinklr.core.feature_engineering.normalization.llm_review import (
        LLMReviewPass,
    )

    llm_client = OpenAIClient()
    reviewer = LLMReviewPass(llm_client=llm_client)
    results = reviewer.review(clusters)
    approved = [r for r in results if r.approved]
    logger.info("LLM review: %d/%d clusters approved", len(approved), len(results))

    results_path = args.output_dir / "alias_review_results.json"
    results_path.write_text(
        json.dumps([r.model_dump(mode="json") for r in results], indent=2),
        encoding="utf-8",
    )

    # Step 5: Build resolver and generate patches
    from twinklr.core.feature_engineering.normalization.resolver import (
        EffectAliasResolver,
    )

    resolver = EffectAliasResolver.from_review_results(tuple(results))
    resolver.to_json(args.output_dir / "effect_alias_candidates.json")
    logger.info("Wrote resolver: %s", args.output_dir / "effect_alias_candidates.json")

    patches = EffectAliasResolver.generate_taxonomy_patches(tuple(results))
    patches_path = args.output_dir / "taxonomy_rule_patches.json"
    patches_path.write_text(
        json.dumps([p.model_dump(mode="json") for p in patches], indent=2),
        encoding="utf-8",
    )
    logger.info("Wrote %d taxonomy patches: %s", len(patches), patches_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
