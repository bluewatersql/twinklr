"""Dense embedding producer for sequence feature vectors."""

from __future__ import annotations

import numpy as np

from twinklr.core.feature_engineering.embeddings.models import (
    SequenceEmbedding,
    SequenceFeatureVector,
)


class SequenceEmbedder:
    """Produces dense embeddings from sequence feature vectors.

    Supports multiple reduction strategies:
    - "passthrough": Use raw feature vector as embedding (baseline)
    - "pca": PCA dimensionality reduction (NumPy-only, no sklearn)

    Args:
        strategy: Embedding strategy ("passthrough" or "pca").
        target_dim: Target embedding dimensionality (for PCA).
    """

    def __init__(self, strategy: str = "passthrough", target_dim: int = 32) -> None:
        self._strategy = strategy
        self._target_dim = target_dim
        self._components: np.ndarray | None = None  # PCA components
        self._mean: np.ndarray | None = None  # PCA mean

    def fit(self, vectors: tuple[SequenceFeatureVector, ...]) -> None:
        """Fit the embedding model (only needed for PCA).

        For PCA: compute mean-centered covariance, eigendecompose,
        keep top target_dim components. NumPy-only, no sklearn.

        Args:
            vectors: Feature vectors to fit on.
        """
        if self._strategy != "pca" or not vectors:
            return
        mat = np.array([v.values for v in vectors], dtype=np.float64)
        self._mean = mat.mean(axis=0)
        centered = mat - self._mean
        # Covariance matrix
        cov = (centered.T @ centered) / max(len(vectors) - 1, 1)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        # Sort by descending eigenvalue
        idx = np.argsort(eigenvalues)[::-1]
        dim = min(self._target_dim, len(idx))
        self._components = eigenvectors[:, idx[:dim]].T  # (dim, features)

    def embed(self, vectors: tuple[SequenceFeatureVector, ...]) -> tuple[SequenceEmbedding, ...]:
        """Produce embeddings from feature vectors.

        Args:
            vectors: Feature vectors to embed.

        Returns:
            Tuple of SequenceEmbedding instances, one per input vector.
        """
        results: list[SequenceEmbedding] = []
        for v in vectors:
            if self._strategy == "pca" and self._components is not None and self._mean is not None:
                centered = np.array(v.values) - self._mean
                projected = self._components @ centered
                emb = tuple(float(x) for x in projected)
            else:
                emb = v.values
            results.append(
                SequenceEmbedding(
                    package_id=v.package_id,
                    sequence_file_id=v.sequence_file_id,
                    embedding=emb,
                    dimensionality=len(emb),
                    strategy=self._strategy,
                )
            )
        return tuple(results)
