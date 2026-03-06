"""NumPy-only agglomerative clustering for effect alias discovery."""

from __future__ import annotations

import numpy as np

from twinklr.core.feature_engineering.normalization.models import (
    AliasClusterGroup,
    AliasClusteringOptions,
    UnknownEffectEntry,
)


class AliasClustering:
    """Cluster effect name embeddings to discover alias groups.

    Uses NumPy-only agglomerative (single-linkage) clustering — no sklearn
    or scipy required.

    Args:
        options: Clustering configuration.  Defaults to ``AliasClusteringOptions()``.
    """

    def __init__(self, options: AliasClusteringOptions | None = None) -> None:
        self._options = options or AliasClusteringOptions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cluster(
        self,
        entries: tuple[UnknownEffectEntry, ...],
        embeddings: tuple[tuple[float, ...], ...],
    ) -> tuple[AliasClusterGroup, ...]:
        """Cluster entries by embedding similarity.

        Algorithm (agglomerative, NumPy-only):

        1. Compute pairwise cosine similarity matrix.
        2. Use single-linkage: merge pairs above ``min_similarity`` threshold
           via union-find.
        3. Filter clusters below ``min_cluster_size``.
        4. For each cluster: ``suggested_canonical`` = member with highest
           ``count``.
        5. ``centroid_similarity`` = mean of pairwise similarities within
           the cluster.

        Args:
            entries: Unknown effect entries to cluster.
            embeddings: Pre-computed embedding vectors, one per entry.

        Returns:
            Tuple of ``AliasClusterGroup`` objects (one per qualifying cluster).
        """
        if not entries or not embeddings:
            return ()

        n = len(entries)
        if n != len(embeddings):
            raise ValueError(
                f"entries and embeddings must have equal length, got {n} vs {len(embeddings)}"
            )

        # Build (n, dim) float64 matrix and compute pairwise cosine similarity.
        mat = np.array(embeddings, dtype=np.float64)
        sim = self._cosine_similarity_matrix(mat)

        # Union-find clustering with single-linkage at min_similarity threshold.
        parent = list(range(n))

        def _find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def _union(a: int, b: int) -> None:
            parent[_find(a)] = _find(b)

        for i in range(n):
            for j in range(i + 1, n):
                if sim[i, j] >= self._options.min_similarity:
                    _union(i, j)

        # Group indices by root.
        clusters: dict[int, list[int]] = {}
        for idx in range(n):
            root = _find(idx)
            clusters.setdefault(root, []).append(idx)

        # Build output groups, filtering by min_cluster_size.
        groups: list[AliasClusterGroup] = []
        for cluster_idx, (_root, members) in enumerate(sorted(clusters.items())):
            if len(members) < self._options.min_cluster_size:
                continue

            member_entries = [entries[i] for i in members]
            member_names = tuple(e.effect_type for e in member_entries)
            member_counts = tuple(e.count for e in member_entries)

            # Suggested canonical = member with highest count.
            best_idx = int(np.argmax(np.array(member_counts, dtype=np.int64)))
            canonical = member_names[best_idx]

            # Centroid similarity = mean of pairwise sims within cluster.
            centroid_sim = self._mean_pairwise_similarity(sim, members)

            groups.append(
                AliasClusterGroup(
                    cluster_id=f"cluster_{cluster_idx:04d}",
                    members=member_names,
                    member_counts=member_counts,
                    centroid_similarity=float(centroid_sim),
                    suggested_canonical=canonical,
                )
            )

        return tuple(groups)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity_matrix(mat: np.ndarray) -> np.ndarray:
        """Return (n, n) cosine similarity matrix for row vectors in *mat*.

        Args:
            mat: Shape ``(n, dim)`` float64 array.

        Returns:
            Shape ``(n, n)`` float64 similarity matrix with values in [0, 1].
        """
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        # Avoid division by zero for zero-norm vectors.
        norms = np.where(norms == 0.0, 1.0, norms)
        normed = mat / norms
        sim = normed @ normed.T
        # Numerical clamp to [0, 1].
        result: np.ndarray = np.clip(sim, 0.0, 1.0)
        return result

    @staticmethod
    def _mean_pairwise_similarity(sim: np.ndarray, members: list[int]) -> float:
        """Compute mean pairwise cosine similarity for a cluster.

        Args:
            sim: Full (n, n) similarity matrix.
            members: Row/column indices belonging to this cluster.

        Returns:
            Mean of upper-triangle pairwise similarities (1.0 for singletons).
        """
        if len(members) < 2:
            return 1.0
        sub = sim[np.ix_(members, members)]
        n = len(members)
        # Extract upper triangle (excluding diagonal).
        upper_vals = sub[np.triu_indices(n, k=1)]
        if upper_vals.size == 0:
            return 1.0
        return float(np.mean(upper_vals))
