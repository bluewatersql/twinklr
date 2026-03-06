"""Tests for TransitionEvaluator."""

from __future__ import annotations

from twinklr.core.feature_engineering.models.transitions import (
    TransitionEdge,
    TransitionGraph,
    TransitionType,
)
from twinklr.core.feature_engineering.transitions_v2.evaluator import TransitionEvaluator
from twinklr.core.feature_engineering.transitions_v2.markov import MarkovTransitionModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_edge(src: str, tgt: str, count: int) -> TransitionEdge:
    """Build a minimal TransitionEdge fixture."""
    return TransitionEdge(
        source_template_id=src,
        target_template_id=tgt,
        edge_count=count,
        confidence=0.9,
        mean_gap_ms=50.0,
        transition_type_distribution={TransitionType.HARD_CUT: count},
    )


def _make_graph(edges: list[TransitionEdge]) -> TransitionGraph:
    """Build a TransitionGraph from a list of edges."""
    unique_srcs: set[str] = set()
    unique_tgts: set[str] = set()
    for e in edges:
        unique_srcs.add(e.source_template_id)
        unique_tgts.add(e.target_template_id)
    nodes = unique_srcs | unique_tgts
    return TransitionGraph(
        schema_version="1.0.0",
        graph_version="1.0.0",
        total_transitions=sum(e.edge_count for e in edges),
        total_nodes=len(nodes),
        total_edges=len(edges),
        edges=tuple(edges),
    )


# Standard fixture edges.
_EDGES: list[TransitionEdge] = [
    _make_edge("T1", "T2", 10),
    _make_edge("T1", "T3", 5),
    _make_edge("T2", "T3", 8),
    _make_edge("T2", "T1", 3),
]


def _fitted_model(edges: list[TransitionEdge]) -> MarkovTransitionModel:
    model = MarkovTransitionModel()
    model.fit(edges, [])
    return model


# ---------------------------------------------------------------------------
# Test 1: Perfect model — top_k_recall approaches 1.0
# ---------------------------------------------------------------------------


def test_top_k_recall_perfect_model() -> None:
    """When model is trained on the same edges as the graph, recall is 1.0 at k=2.

    _EDGES has at most 2 targets per source (T1→{T2,T3}, T2→{T3,T1}).
    With k=2, graph top-2 and model top-2 should fully overlap since the model
    was fit on the same data — giving recall = overlap/k = 2/2 = 1.0.
    """
    graph = _make_graph(_EDGES)
    model = _fitted_model(_EDGES)
    evaluator = TransitionEvaluator(k=2)

    report = evaluator.evaluate(model, graph, held_out_transitions=())

    assert report.top_k_recall == 1.0, f"Expected perfect recall, got {report.top_k_recall}"
    assert 0.0 <= report.top_k_recall <= 1.0


# ---------------------------------------------------------------------------
# Test 2: Hit rate computed correctly for held-out data
# ---------------------------------------------------------------------------


def test_hit_rate_with_held_out_transitions() -> None:
    """Hit rate reflects actual hits on held-out transitions."""
    # Training edges: T1→T2 (heavy), T1→T3 (light)
    training_edges = [
        _make_edge("T1", "T2", 20),
        _make_edge("T1", "T3", 2),
        _make_edge("T2", "T1", 10),
    ]
    model = _fitted_model(training_edges)
    graph = _make_graph(training_edges)

    # Held-out: T1→T2 should be in top-5 predictions (model was trained heavily on it)
    held_out: tuple[TransitionEdge, ...] = (
        _make_edge("T1", "T2", 1),
        _make_edge("T2", "T1", 1),
    )

    evaluator = TransitionEvaluator(k=5)
    report = evaluator.evaluate(model, graph, held_out_transitions=held_out)

    assert report.held_out_count == 2
    # Both T1→T2 and T2→T1 are well-represented in training; should be hits.
    assert report.hit_rate > 0.0, f"Expected hits > 0, got hit_rate={report.hit_rate}"
    assert 0.0 <= report.hit_rate <= 1.0


def test_hit_rate_zero_when_no_held_out() -> None:
    """Hit rate is 0.0 when held_out_transitions is empty."""
    graph = _make_graph(_EDGES)
    model = _fitted_model(_EDGES)
    evaluator = TransitionEvaluator(k=5)

    report = evaluator.evaluate(model, graph, held_out_transitions=())

    assert report.hit_rate == 0.0
    assert report.held_out_count == 0


# ---------------------------------------------------------------------------
# Test 3: Coverage computed correctly
# ---------------------------------------------------------------------------


def test_coverage_all_templates_have_predictions() -> None:
    """Coverage is 1.0 when all graph-source templates are known to the model."""
    graph = _make_graph(_EDGES)
    model = _fitted_model(_EDGES)
    evaluator = TransitionEvaluator(k=5)

    report = evaluator.evaluate(model, graph, held_out_transitions=())

    # Model was trained on same edges; every source in the graph is in model index.
    assert report.coverage == 1.0
    assert report.templates_with_predictions == report.total_templates


def test_coverage_partial_when_model_missing_templates() -> None:
    """Coverage < 1.0 when the graph has a source template absent from the model's index.

    The graph contains T1, T2 and T3 as sources. The partial model is trained
    only on T1→T2, so T3 is completely unknown to it. predict("T3") returns ()
    and templates_with_predictions < total_templates.
    """
    # Graph sources: T1, T2, T3
    graph_edges = [
        _make_edge("T1", "T2", 10),
        _make_edge("T2", "T1", 5),
        _make_edge("T3", "T1", 8),  # T3 is a source; model won't know it
    ]
    graph = _make_graph(graph_edges)
    # Partial model only sees T1 and T2.
    partial_model = _fitted_model([_make_edge("T1", "T2", 10), _make_edge("T2", "T1", 5)])

    evaluator = TransitionEvaluator(k=5)
    report = evaluator.evaluate(partial_model, graph, held_out_transitions=())

    # T3 is a source in the graph but absent from partial_model's index → coverage < 1.0
    assert report.total_templates == 3
    assert report.coverage < 1.0
    assert report.templates_with_predictions < report.total_templates
