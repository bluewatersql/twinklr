"""NumPy-based similarity index over sequence embeddings."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from twinklr.core.feature_engineering.embeddings.models import (
    SequenceEmbedding,
    SimilarityLink,
)


class SimilarityIndex:
    """NumPy-based similarity index over sequence embeddings.

    Args:
        metric: Distance metric ("cosine").
        n_neighbors: Default number of neighbors to return.
    """

    def __init__(self, metric: str = "cosine", n_neighbors: int = 5) -> None:
        self._metric = metric
        self._n_neighbors = n_neighbors
        self._embeddings: tuple[SequenceEmbedding, ...] = ()
        self._matrix: np.ndarray | None = None  # (N, dim) matrix

    def build(self, embeddings: tuple[SequenceEmbedding, ...]) -> None:
        """Build the index from embeddings.

        Args:
            embeddings: Sequence embeddings to index.
        """
        self._embeddings = embeddings
        if not embeddings:
            self._matrix = None
            return
        self._matrix = np.array([e.embedding for e in embeddings], dtype=np.float64)

    def query(
        self,
        embedding: SequenceEmbedding,
        k: int | None = None,
    ) -> tuple[SimilarityLink, ...]:
        """Find k nearest neighbors for a query embedding.

        Args:
            embedding: Query embedding.
            k: Number of neighbors to return. Defaults to n_neighbors.

        Returns:
            Tuple of SimilarityLink instances ranked by similarity descending.
        """
        if self._matrix is None or len(self._embeddings) == 0:
            return ()
        k = k or self._n_neighbors
        query_vec = np.array(embedding.embedding, dtype=np.float64)
        sims = self._cosine_similarity(query_vec, self._matrix)
        indices = np.argsort(sims)[::-1]
        links: list[SimilarityLink] = []
        rank = 1
        for idx_val in indices:
            idx = int(idx_val)
            target = self._embeddings[idx]
            # Skip self
            if (
                target.package_id == embedding.package_id
                and target.sequence_file_id == embedding.sequence_file_id
            ):
                continue
            if rank > k:
                break
            links.append(
                SimilarityLink(
                    source_package_id=embedding.package_id,
                    source_sequence_id=embedding.sequence_file_id,
                    target_package_id=target.package_id,
                    target_sequence_id=target.sequence_file_id,
                    similarity=max(0.0, min(1.0, float(sims[idx]))),
                    rank=rank,
                )
            )
            rank += 1
        return tuple(links)

    def build_cross_package_links(
        self,
        embeddings: tuple[SequenceEmbedding, ...],
        min_similarity: float = 0.7,
    ) -> tuple[SimilarityLink, ...]:
        """Build cross-package similarity links above threshold.

        Args:
            embeddings: All embeddings to compare.
            min_similarity: Minimum similarity score to include a link.

        Returns:
            Tuple of SimilarityLink instances for cross-package pairs.
        """
        self.build(embeddings)
        links: list[SimilarityLink] = []
        for emb in embeddings:
            for link in self.query(emb, k=self._n_neighbors):
                if link.source_package_id != link.target_package_id:
                    if link.similarity >= min_similarity:
                        links.append(link)
        return tuple(links)

    def save(self, path: Path) -> None:
        """Save index state to JSON.

        Args:
            path: File path to write JSON to.
        """
        data = {
            "metric": self._metric,
            "n_neighbors": self._n_neighbors,
            "embeddings": [e.model_dump(mode="json") for e in self._embeddings],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SimilarityIndex:
        """Load index from JSON.

        Args:
            path: File path to read JSON from.

        Returns:
            Reconstructed SimilarityIndex with embeddings built.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        idx = cls(metric=data["metric"], n_neighbors=data["n_neighbors"])
        embeddings = tuple(SequenceEmbedding.model_validate(e) for e in data["embeddings"])
        idx.build(embeddings)
        return idx

    @staticmethod
    def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and all rows in matrix.

        Args:
            query: 1-D query vector.
            matrix: 2-D matrix of shape (N, dim).

        Returns:
            1-D array of similarity scores of length N.
        """
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return np.zeros(len(matrix))
        row_norms = np.linalg.norm(matrix, axis=1)
        row_norms = np.where(row_norms == 0, 1.0, row_norms)
        dots = matrix @ query
        result: np.ndarray = dots / (row_norms * query_norm)
        return result
