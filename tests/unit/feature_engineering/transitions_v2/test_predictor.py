"""Tests for TransitionPredictor."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.transitions import (
    TransitionEdge,
    TransitionGraph,
    TransitionType,
)
from twinklr.core.feature_engineering.transitions_v2.markov import MarkovTransitionModel
from twinklr.core.feature_engineering.transitions_v2.predictor import TransitionPredictor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_edge(src: str, tgt: str, count: int = 10, confidence: float = 0.8) -> TransitionEdge:
    return TransitionEdge(
        source_template_id=src,
        target_template_id=tgt,
        edge_count=count,
        confidence=confidence,
        mean_gap_ms=100.0,
        transition_type_distribution={TransitionType.HARD_CUT: count},
    )


def _fitted_model(edges: list[TransitionEdge]) -> MarkovTransitionModel:
    model = MarkovTransitionModel()
    model.fit(edges, [])
    return model


# ---------------------------------------------------------------------------
# Test 1: Known template → ranked suggestions with source="markov"
# ---------------------------------------------------------------------------


def test_known_template_returns_markov_suggestions() -> None:
    """Known template produces suggestions attributed to source='markov'."""
    edges = [
        _make_edge("T1", "T2", 50),
        _make_edge("T1", "T3", 20),
    ]
    model = _fitted_model(edges)
    predictor = TransitionPredictor(model)

    suggestions = predictor.suggest_next("T1", section_duration_ms=1000, k=3)

    assert len(suggestions) > 0
    for sug in suggestions:
        assert sug.source == "markov"
    # Must be sorted by probability descending.
    probs = [s.probability for s in suggestions]
    for i in range(len(probs) - 1):
        assert probs[i] >= probs[i + 1], f"Not sorted at index {i}: {probs}"
    # Ranks must be 1-based consecutive.
    for i, sug in enumerate(suggestions, start=1):
        assert sug.rank == i


# ---------------------------------------------------------------------------
# Test 2: Unknown template + fallback graph → source="fallback_graph"
# ---------------------------------------------------------------------------


def test_unknown_template_uses_fallback_graph() -> None:
    """When model has no data, fallback graph edges are returned."""
    model = _fitted_model([_make_edge("T1", "T2", 5)])

    # Graph contains edges for "UNKNOWN" which model doesn't know.
    graph = TransitionGraph(
        schema_version="1.0",
        graph_version="1.0",
        total_transitions=2,
        total_nodes=3,
        total_edges=2,
        edges=(
            _make_edge("UNKNOWN", "T_A", 1, confidence=0.9),
            _make_edge("UNKNOWN", "T_B", 1, confidence=0.5),
        ),
    )

    predictor = TransitionPredictor(model, fallback_graph=graph)
    suggestions = predictor.suggest_next("UNKNOWN", section_duration_ms=1000, k=5)

    assert len(suggestions) == 2
    assert all(s.source == "fallback_graph" for s in suggestions)
    # Sorted by confidence descending.
    assert suggestions[0].template_id == "T_A"
    assert suggestions[1].template_id == "T_B"


def test_unknown_template_no_fallback_returns_empty() -> None:
    """Unknown template without fallback graph returns empty tuple."""
    model = _fitted_model([_make_edge("T1", "T2", 5)])
    predictor = TransitionPredictor(model)
    suggestions = predictor.suggest_next("TOTALLY_UNKNOWN", section_duration_ms=1000)
    assert suggestions == ()


# ---------------------------------------------------------------------------
# Test 3: min_confidence filter removes low-probability suggestions
# ---------------------------------------------------------------------------


def test_min_confidence_filter() -> None:
    """All returned suggestions have probability >= min_confidence."""
    # T1 -> T2 dominant, T1 -> T3 very rare; with Laplace smoothing all have nonzero prob.
    edges = [
        _make_edge("T1", "T2", 1000),
        _make_edge("T1", "T3", 1),
    ]
    model = _fitted_model(edges)
    predictor = TransitionPredictor(model)

    # Use a high threshold to filter out rare transitions.
    min_conf = 0.5
    suggestions = predictor.suggest_next("T1", section_duration_ms=2000, min_confidence=min_conf)

    assert len(suggestions) > 0
    for sug in suggestions:
        assert sug.probability >= min_conf, (
            f"Suggestion {sug.template_id} has probability {sug.probability} < {min_conf}"
        )
