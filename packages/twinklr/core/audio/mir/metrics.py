"""Deterministic metrics for the pre-committed P2P-T8 adoption gate."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EventScore:
    """One-to-one event matching score."""

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def _finite_sorted(values: list[float]) -> list[float]:
    return sorted(float(value) for value in values if math.isfinite(float(value)))


def event_f1(
    reference_s: list[float], estimated_s: list[float], *, tolerance_s: float
) -> EventScore:
    """Score event times with ordered, one-to-one matching inside a fixed window."""
    if tolerance_s < 0:
        raise ValueError("tolerance_s must be non-negative")

    reference = _finite_sorted(reference_s)
    estimated = _finite_sorted(estimated_s)
    reference_index = 0
    estimated_index = 0
    matches = 0

    while reference_index < len(reference) and estimated_index < len(estimated):
        delta = estimated[estimated_index] - reference[reference_index]
        if abs(delta) <= tolerance_s:
            matches += 1
            reference_index += 1
            estimated_index += 1
        elif delta < -tolerance_s:
            estimated_index += 1
        else:
            reference_index += 1

    false_positives = len(estimated) - matches
    false_negatives = len(reference) - matches
    precision = matches / len(estimated) if estimated else (1.0 if not reference else 0.0)
    recall = matches / len(reference) if reference else (1.0 if not estimated else 0.0)
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall > 0.0 else 0.0
    return EventScore(
        true_positives=matches,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def section_boundary_hit_rate(
    reference_s: list[float], estimated_s: list[float], *, tolerance_s: float
) -> float:
    """Return the fraction of annotated boundaries hit within ``tolerance_s``."""
    if not reference_s:
        return 1.0 if not estimated_s else 0.0
    score = event_f1(reference_s, estimated_s, tolerance_s=tolerance_s)
    return score.true_positives / len(reference_s)
