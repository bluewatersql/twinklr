"""First-order Markov transition model with duration conditioning.

Uses sparse count dicts throughout — the transition graph typically has O(edges)
non-zero cells out of O(n²) possible, and for corpora with thousands of templates
the dense-matrix approach allocates hundreds of millions of floats and writes
multi-gigabyte JSON files.  Sparse storage keeps memory proportional to observed
edges and serialized size proportional to observed counts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from twinklr.core.feature_engineering.models.phrases import EffectPhrase
from twinklr.core.feature_engineering.models.transitions import TransitionEdge
from twinklr.core.feature_engineering.transitions_v2.models import TransitionPrediction

# Duration bucket boundaries in milliseconds.
_SHORT_MS = 2000
_LONG_MS = 5000

# Wilson score z-value for 95% confidence interval.
_Z = 1.96

# Laplace smoothing alpha — applied lazily only over observed transitions per row,
# not over every possible (n × n) cell.
_ALPHA = 1.0


def _duration_bucket(duration_ms: int | float) -> str:
    """Return the duration bucket label for a phrase duration.

    Args:
        duration_ms: Duration of the phrase in milliseconds.

    Returns:
        One of ``"short"``, ``"medium"``, or ``"long"``.
    """
    if duration_ms < _SHORT_MS:
        return "short"
    if duration_ms <= _LONG_MS:
        return "medium"
    return "long"


def _wilson_ci(p: float, n: int, z: float = _Z) -> tuple[float, float]:
    """Compute Wilson score confidence interval.

    Args:
        p: Observed probability estimate.
        n: Total observation count for this row.
        z: Z-score for desired confidence level (default 1.96 for 95%).

    Returns:
        Tuple ``(lower, upper)`` both clamped to ``[0.0, 1.0]``.
    """
    if n == 0:
        return (0.0, 1.0)
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denominator
    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return (lower, upper)


def _normalise_row(counts: dict[str, int], alpha: float = _ALPHA) -> dict[str, float]:
    """Apply Laplace smoothing and row-normalise a sparse count dict.

    Smoothing is applied only over *observed* targets, not the full template
    vocabulary, so the result sums to 1 over observed transitions.

    Args:
        counts: Mapping from target_template_id to raw observation count.
        alpha: Laplace smoothing pseudo-count added to each observed entry.

    Returns:
        Mapping from target_template_id to smoothed probability.
    """
    if not counts:
        return {}
    smoothed = {tid: c + alpha for tid, c in counts.items()}
    total = sum(smoothed.values())
    return {tid: v / total for tid, v in smoothed.items()}


class MarkovTransitionModel:
    """Probabilistic transition model using first-order Markov chains.

    Supports:
    - First-order: P(next | current)
    - Duration-conditioned: P(next | current, duration_bucket)
    - Confidence intervals via Laplace smoothing / Wilson score CI

    Stores only *observed* transitions in nested dicts, keeping memory and
    serialized size proportional to observed edges rather than O(n²) in the
    number of templates.
    """

    _BUCKETS: tuple[str, ...] = ("short", "medium", "long")

    def __init__(self) -> None:
        """Initialise an empty (unfitted) model."""
        # Sparse unconditional counts: source_id → {target_id: count}
        self._counts: dict[str, dict[str, int]] = {}
        # Sparse per-bucket counts: bucket → source_id → {target_id: count}
        self._bucket_counts: dict[str, dict[str, dict[str, int]]] = {b: {} for b in self._BUCKETS}
        # Raw row sums for Wilson CI (unconditional).
        self._row_counts: dict[str, int] = {}
        # Raw row sums per bucket for Wilson CI.
        self._bucket_row_counts: dict[str, dict[str, int]] = {b: {} for b in self._BUCKETS}
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        transitions: list[TransitionEdge] | tuple[TransitionEdge, ...],
        phrases: list[EffectPhrase] | tuple[EffectPhrase, ...],
    ) -> None:
        """Build sparse transition counts from observed edges and phrases.

        Constructs both an unconditional first-order Markov model and three
        duration-conditioned models (``"short"``, ``"medium"``, ``"long"``).
        Only observed (source, target) pairs are stored.

        Args:
            transitions: Aggregated ``TransitionEdge`` objects; ``edge_count``
                is used as the observation weight.
            phrases: ``EffectPhrase`` objects providing ``duration_ms`` values
                for duration conditioning, keyed by ``param_signature``.
        """
        # Build template_id → median duration from phrases via param_signature.
        template_phrase_durations: dict[str, list[int]] = {}
        for phrase in phrases:
            tid = phrase.param_signature
            template_phrase_durations.setdefault(tid, []).append(phrase.duration_ms)

        counts: dict[str, dict[str, int]] = {}
        bucket_counts: dict[str, dict[str, dict[str, int]]] = {b: {} for b in self._BUCKETS}

        for edge in transitions:
            src = edge.source_template_id
            tgt = edge.target_template_id
            w = edge.edge_count

            # Unconditional.
            counts.setdefault(src, {})[tgt] = counts.get(src, {}).get(tgt, 0) + w

            # Duration-conditioned.
            durations = template_phrase_durations.get(src, [])
            if durations:
                median_dur = sorted(durations)[len(durations) // 2]
                bucket = _duration_bucket(median_dur)
                row = bucket_counts[bucket].setdefault(src, {})
                row[tgt] = row.get(tgt, 0) + w
            else:
                for b in self._BUCKETS:
                    row = bucket_counts[b].setdefault(src, {})
                    row[tgt] = row.get(tgt, 0) + w

        self._counts = counts
        self._bucket_counts = bucket_counts
        self._row_counts = {src: sum(tgts.values()) for src, tgts in counts.items()}
        self._bucket_row_counts = {
            b: {src: sum(tgts.values()) for src, tgts in rows.items()}
            for b, rows in bucket_counts.items()
        }
        self._fitted = True

    def predict(
        self,
        current_template_id: str,
        duration_ms: int | float | None = None,
        k: int = 5,
    ) -> tuple[TransitionPrediction, ...]:
        """Return the top-k predicted next templates.

        Args:
            current_template_id: The template the chain is currently in.
            duration_ms: Optional phrase duration in ms; selects the
                duration-conditioned counts when provided.
            k: Maximum number of predictions to return.

        Returns:
            Tuple of up to ``k`` ``TransitionPrediction`` objects sorted by
            probability descending.  Returns an empty tuple for unknown templates.
        """
        if not self._fitted:
            return ()

        bucket: str | None = None
        if duration_ms is not None:
            bucket = _duration_bucket(duration_ms)
            raw_counts = self._bucket_counts[bucket].get(current_template_id)
            n_obs = self._bucket_row_counts[bucket].get(current_template_id, 0)
        else:
            raw_counts = self._counts.get(current_template_id)
            n_obs = self._row_counts.get(current_template_id, 0)

        if not raw_counts:
            return ()

        probs = _normalise_row(raw_counts)
        ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)

        results: list[TransitionPrediction] = []
        for rank, (tid, prob) in enumerate(ranked[:k], start=1):
            ci = _wilson_ci(prob, n_obs)
            results.append(
                TransitionPrediction(
                    template_id=tid,
                    probability=prob,
                    confidence_interval=ci,
                    duration_bucket=bucket,
                    rank=rank,
                )
            )
        return tuple(results)

    def probability(
        self,
        from_template_id: str,
        to_template_id: str,
        duration_ms: int | float | None = None,
    ) -> float:
        """Return the transition probability between two templates.

        Args:
            from_template_id: Source template id.
            to_template_id: Target template id.
            duration_ms: Optional duration in ms for conditioned lookup.

        Returns:
            Smoothed transition probability, or ``0.0`` if either template
            is unknown or the model is unfitted.
        """
        if not self._fitted:
            return 0.0

        if duration_ms is not None:
            bucket = _duration_bucket(duration_ms)
            raw_counts = self._bucket_counts[bucket].get(from_template_id)
        else:
            raw_counts = self._counts.get(from_template_id)

        if not raw_counts or to_template_id not in raw_counts:
            return 0.0

        probs = _normalise_row(raw_counts)
        return probs.get(to_template_id, 0.0)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Serialise the sparse model to a JSON file.

        Args:
            path: Destination file path.
        """
        state: dict[str, Any] = {
            "schema_version": "v2.0.0",
            "counts": self._counts,
            "bucket_counts": self._bucket_counts,
            "row_counts": self._row_counts,
            "bucket_row_counts": self._bucket_row_counts,
            "fitted": self._fitted,
        }
        Path(path).write_text(json.dumps(state))

    @classmethod
    def load(cls, path: str | Path) -> MarkovTransitionModel:
        """Deserialise a model from a JSON file.

        Supports both the current sparse format (``schema_version`` present)
        and the legacy dense-matrix format for backwards compatibility.

        Args:
            path: Source file path produced by :meth:`save`.

        Returns:
            A fully restored ``MarkovTransitionModel`` instance.
        """
        state: dict[str, Any] = json.loads(Path(path).read_text())
        model = cls()
        if "schema_version" in state:
            # Current sparse format.
            model._counts = state["counts"]
            model._bucket_counts = state["bucket_counts"]
            model._row_counts = state["row_counts"]
            model._bucket_row_counts = state["bucket_row_counts"]
            model._fitted = state["fitted"]
        else:
            # Legacy dense-matrix format — reconstruct sparse counts from index + matrix.
            index: dict[str, int] = state.get("index", {})
            idx_to_tid = {v: k for k, v in index.items()}
            matrix: list[list[float]] = state.get("matrix", [])
            row_counts_list: list[int] = state.get("row_counts", [])
            bucket_matrices: dict[str, list[list[float]]] = state.get("bucket_matrices", {})
            bucket_row_counts_list: dict[str, list[int]] = state.get("bucket_row_counts", {})

            for i, row in enumerate(matrix):
                src = idx_to_tid.get(i, str(i))
                for j, val in enumerate(row):
                    if val > 0:
                        tgt = idx_to_tid.get(j, str(j))
                        # Convert probability back to pseudo-count for sparse storage.
                        model._counts.setdefault(src, {})[tgt] = int(round(val * 1000))
                model._row_counts[src] = row_counts_list[i] if i < len(row_counts_list) else 0

            for b, bmat in bucket_matrices.items():
                brc = bucket_row_counts_list.get(b, [])
                for i, row in enumerate(bmat):
                    src = idx_to_tid.get(i, str(i))
                    for j, val in enumerate(row):
                        if val > 0:
                            tgt = idx_to_tid.get(j, str(j))
                            model._bucket_counts[b].setdefault(src, {})[tgt] = int(
                                round(val * 1000)
                            )
                    model._bucket_row_counts[b][src] = brc[i] if i < len(brc) else 0

            model._fitted = state.get("fitted", False)
        return model
