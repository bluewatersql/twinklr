"""Section descriptors for energy, repetition, and confidence scoring."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from twinklr.core.audio.utils import cosine_similarity


class RobustNormResult(BaseModel):
    """Result of robust normalization with discrimination power metric."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    values_0_1: np.ndarray  # Normalized values in [0, 1]
    discrim_power: float  # Discrimination power (0..1), how much variance exists


def robust_sigmoid_norm(x: np.ndarray, eps: float = 1e-8) -> RobustNormResult:
    """Variance-aware normalization via robust z-score and sigmoid mapping.

    Uses MAD (Median Absolute Deviation) for robust standardization,
    then sigmoid to map to [0, 1]. Also returns discrimination power
    metric indicating how much signal variation exists.

    Args:
        x: Input array
        eps: Small constant for numerical stability

    Returns:
        RobustNormResult with normalized values and discrimination power
    """
    x = np.asarray(x, dtype=np.float32)
    if x.size == 0:
        return RobustNormResult(values_0_1=np.array([], dtype=np.float32), discrim_power=0.0)

    # Compute discrimination power (spread relative to scale)
    p10 = float(np.percentile(x, 10))
    p90 = float(np.percentile(x, 90))
    spread = p90 - p10
    scale = max(abs(p90), abs(p10), 1.0)
    discrim = float(np.clip(spread / (scale + eps), 0.0, 1.0))

    # Robust z-score via MAD
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))

    if mad < eps or spread < eps:
        # No variation - return flat 0.5
        return RobustNormResult(
            values_0_1=np.full_like(x, 0.5, dtype=np.float32),
            discrim_power=0.0,
        )

    z = (x - med) / (1.4826 * mad + eps)  # 1.4826 is scaling factor for MAD
    y = 1.0 / (1.0 + np.exp(-z))  # Sigmoid

    return RobustNormResult(values_0_1=y.astype(np.float32), discrim_power=discrim)


def compute_section_centroids(
    features: np.ndarray, beat_times: np.ndarray, boundaries: list[float]
) -> list[np.ndarray]:
    """Compute mean feature vector (centroid) for each section.

    Args:
        features: Normalized feature matrix (features × beats)
        beat_times: Beat times in seconds
        boundaries: Section boundary times

    Returns:
        List of section centroids
    """
    centroids: list[np.ndarray] = []
    num_beats = features.shape[1]

    def _beat_idx_for_time(t: float) -> int:
        """Find nearest beat index for time."""
        if beat_times.size == 0:
            return 0
        return int(np.argmin(np.abs(beat_times - float(t))))

    for i in range(len(boundaries) - 1):
        start_t = float(boundaries[i])
        end_t = float(boundaries[i + 1])

        sb = _beat_idx_for_time(start_t)
        eb = _beat_idx_for_time(end_t)
        if eb <= sb:
            eb = min(sb + 1, num_beats)

        seg = features[:, sb:eb] if eb > sb else features[:, sb : sb + 1]
        centroids.append(np.mean(seg, axis=1))

    return centroids


def compute_similarity_matrix(centroids: list[np.ndarray]) -> np.ndarray:
    """Compute pairwise cosine similarity between section centroids.

    Args:
        centroids: List of section centroid vectors

    Returns:
        Similarity matrix (n_sections × n_sections)
    """
    n = len(centroids)
    sim_mat = np.zeros((n, n), dtype=np.float32)

    for i in range(n):
        for j in range(n):
            if i != j:
                sim_mat[i, j] = float(cosine_similarity(centroids[i], centroids[j]))

    return sim_mat


def topk_mean_similarity(sim_row: np.ndarray, k: int = 3) -> float:
    """Compute mean of top-k similarities (excluding self-similarity).

    Args:
        sim_row: Row of similarity matrix
        k: Number of top similarities to average

    Returns:
        Mean of top-k similarities
    """
    x = np.asarray(sim_row, dtype=np.float32)
    if x.size == 0:
        return 0.0

    # Exclude self/near-self
    x = x[x < 0.999999]
    if x.size == 0:
        return 0.0

    k = int(max(1, min(k, x.size)))
    part = np.partition(x, -k)[-k:]
    return float(np.mean(part))


def compute_repetition_strength(similarity_matrix: np.ndarray) -> np.ndarray:
    """Compute repetition strength for each section via top-k similarity.

    Args:
        similarity_matrix: Pairwise section similarity matrix

    Returns:
        Repetition strength per section (raw values, not normalized)
    """
    n = similarity_matrix.shape[0]
    if n == 0:
        return np.array([], dtype=np.float32)

    rep_strength = np.array(
        [topk_mean_similarity(similarity_matrix[i], k=3) for i in range(n)],
        dtype=np.float32,
    )
    return rep_strength


def compute_repeat_counts(similarity_matrix: np.ndarray, threshold: float) -> np.ndarray:
    """Count how many sections each section is similar to (above threshold).

    Args:
        similarity_matrix: Pairwise section similarity matrix
        threshold: Similarity threshold for counting

    Returns:
        Repeat count per section
    """
    n = similarity_matrix.shape[0]
    if n == 0:
        return np.array([], dtype=int)

    repeat_counts = (similarity_matrix >= threshold).sum(axis=1).astype(int)
    return repeat_counts  # type: ignore[no-any-return]


def derive_repeat_threshold(similarity_matrix: np.ndarray) -> float:
    """Derive adaptive repeat threshold from similarity distribution.

    Uses 90th percentile of non-zero similarities, clamped to [0.75, 0.97].

    Args:
        similarity_matrix: Pairwise section similarity matrix

    Returns:
        Threshold for counting repeats
    """
    n = similarity_matrix.shape[0]
    if n <= 1:
        return 0.9

    all_sims = similarity_matrix[similarity_matrix > 0.0]
    if all_sims.size == 0:
        return 0.9

    threshold = float(np.percentile(all_sims, 90))
    return float(np.clip(threshold, 0.75, 0.97))


def compute_section_confidence(
    boundary_evidence: float,
    repetition_val: float,
    energy_rank: float,
    discrimination: float,
) -> float:
    """Compute section confidence score from multiple signals.

    Confidence = weighted combination of:
    - Boundary evidence (prominence)
    - Repetition strength
    - Energy rank
    All scaled by discrimination power (how much signal variance exists).

    Args:
        boundary_evidence: Boundary prominence (0-1)
        repetition_val: Repetition strength (0-1)
        energy_rank: Energy rank (0-1)
        discrimination: Discrimination power (0-1)

    Returns:
        Confidence score in [0, 1]
    """
    conf = (0.55 * boundary_evidence + 0.25 * repetition_val + 0.20 * energy_rank) * (
        0.35 + 0.65 * discrimination
    )
    return float(np.clip(conf, 0.0, 1.0))
