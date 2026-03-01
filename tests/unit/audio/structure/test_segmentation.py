"""Tests for segmentation algorithms (structure/segmentation.py).

Covers PERF-06: Foote novelty vectorization equivalence and edge cases.
"""

from __future__ import annotations

import numpy as np

from twinklr.core.audio.structure.segmentation import (
    compute_foote_novelty,
)


def _foote_novelty_reference(ssm: np.ndarray, kernel_size: int) -> np.ndarray:
    """Reference (original loop-based) Foote novelty implementation for comparison."""
    n = int(ssm.shape[0])
    L = int(max(2, kernel_size))

    if n < (2 * L + 1):
        return np.zeros(n, dtype=np.float32)

    # Checkerboard kernel
    kernel = np.zeros((2 * L, 2 * L), dtype=np.float32)
    kernel[:L, :L] = 1.0
    kernel[L:, L:] = 1.0
    kernel[:L, L:] = -1.0
    kernel[L:, :L] = -1.0

    # Original Python loop
    novelty = np.zeros(n, dtype=np.float32)
    for t in range(L, n - L):
        patch = ssm[t - L : t + L, t - L : t + L]
        novelty[t] = float(np.sum(patch * kernel))

    # Normalize to [0, 1]
    if float(np.max(novelty)) > float(np.min(novelty)):
        novelty = (novelty - float(np.min(novelty))) / (
            float(np.max(novelty)) - float(np.min(novelty)) + 1e-8
        )

    return novelty.astype(np.float32)


class TestComputeFooteNovelty:
    """Tests for compute_foote_novelty function."""

    def test_output_equivalence_with_reference(self) -> None:
        """PERF-06: Vectorized output matches original loop-based implementation."""
        rng = np.random.default_rng(42)
        n = 50
        # Create a realistic SSM from random features
        features = rng.standard_normal((10, n)).astype(np.float32)
        norms = np.linalg.norm(features, axis=0, keepdims=True)
        norms = np.where(norms < 1e-8, 1.0, norms)
        features_norm = features / norms
        ssm = (features_norm.T @ features_norm).astype(np.float32)

        kernel_size = 4

        reference = _foote_novelty_reference(ssm, kernel_size)
        vectorized = compute_foote_novelty(ssm, kernel_size)

        np.testing.assert_allclose(
            vectorized,
            reference,
            atol=1e-5,
            err_msg="Vectorized Foote novelty does not match reference implementation",
        )

    def test_output_equivalence_large_kernel(self) -> None:
        """PERF-06: Equivalence holds with larger kernel size."""
        rng = np.random.default_rng(123)
        n = 80
        features = rng.standard_normal((10, n)).astype(np.float32)
        norms = np.linalg.norm(features, axis=0, keepdims=True)
        norms = np.where(norms < 1e-8, 1.0, norms)
        features_norm = features / norms
        ssm = (features_norm.T @ features_norm).astype(np.float32)

        kernel_size = 8

        reference = _foote_novelty_reference(ssm, kernel_size)
        vectorized = compute_foote_novelty(ssm, kernel_size)

        np.testing.assert_allclose(
            vectorized,
            reference,
            atol=1e-5,
            err_msg="Vectorized Foote novelty does not match with larger kernel",
        )

    def test_short_signal_returns_zeros(self) -> None:
        """PERF-06: Very short SSM returns zero novelty without crash."""
        ssm = np.ones((3, 3), dtype=np.float32)
        result = compute_foote_novelty(ssm, kernel_size=4)
        assert result.shape == (3,)
        assert np.all(result == 0.0)

    def test_output_normalized_0_1(self) -> None:
        """PERF-06: Output is normalized to [0, 1] range."""
        rng = np.random.default_rng(99)
        n = 40
        features = rng.standard_normal((8, n)).astype(np.float32)
        norms = np.linalg.norm(features, axis=0, keepdims=True)
        norms = np.where(norms < 1e-8, 1.0, norms)
        features_norm = features / norms
        ssm = (features_norm.T @ features_norm).astype(np.float32)

        result = compute_foote_novelty(ssm, kernel_size=4)

        assert result.dtype == np.float32
        assert float(np.min(result)) >= -1e-6
        assert float(np.max(result)) <= 1.0 + 1e-6

    def test_edges_are_zero(self) -> None:
        """PERF-06: Edge values (outside kernel range) are zero."""
        rng = np.random.default_rng(77)
        n = 30
        features = rng.standard_normal((6, n)).astype(np.float32)
        norms = np.linalg.norm(features, axis=0, keepdims=True)
        norms = np.where(norms < 1e-8, 1.0, norms)
        features_norm = features / norms
        ssm = (features_norm.T @ features_norm).astype(np.float32)

        kernel_size = 4
        L = max(2, kernel_size)

        result = compute_foote_novelty(ssm, kernel_size)

        # First L and last L values should be zero (not computed by kernel)
        assert np.all(result[:L] == 0.0)
        assert np.all(result[n - L :] == 0.0)

    def test_identity_ssm(self) -> None:
        """PERF-06: Identity SSM produces valid output."""
        n = 20
        ssm = np.eye(n, dtype=np.float32)
        result = compute_foote_novelty(ssm, kernel_size=3)
        assert result.shape == (n,)
        assert result.dtype == np.float32
