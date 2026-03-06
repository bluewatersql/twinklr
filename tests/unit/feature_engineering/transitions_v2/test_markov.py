"""Tests for MarkovTransitionModel."""

from __future__ import annotations

from pathlib import Path
import tempfile

from twinklr.core.feature_engineering.models.phrases import (
    ColorClass,
    ContinuityClass,
    EffectPhrase,
    EnergyClass,
    MotionClass,
    PhraseSource,
    SpatialClass,
)
from twinklr.core.feature_engineering.models.transitions import (
    TransitionEdge,
    TransitionType,
)
from twinklr.core.feature_engineering.transitions_v2.markov import MarkovTransitionModel

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_edge(src: str, tgt: str, count: int = 10) -> TransitionEdge:
    return TransitionEdge(
        source_template_id=src,
        target_template_id=tgt,
        edge_count=count,
        confidence=0.8,
        mean_gap_ms=100.0,
        transition_type_distribution={TransitionType.HARD_CUT: count},
    )


def _make_phrase(phrase_id: str, duration_ms: int, param_sig: str = "sig") -> EffectPhrase:
    return EffectPhrase(
        schema_version="1.0",
        phrase_id=phrase_id,
        package_id="pkg",
        sequence_file_id="seq",
        effect_event_id="evt",
        effect_type="strobe",
        effect_family="flash",
        motion_class=MotionClass.SWEEP,
        color_class=ColorClass.MONO,
        energy_class=EnergyClass.HIGH,
        continuity_class=ContinuityClass.RHYTHMIC,
        spatial_class=SpatialClass.GROUP,
        source=PhraseSource.EFFECT_TYPE_MAP,
        map_confidence=0.9,
        target_name="head1",
        layer_index=0,
        start_ms=0,
        end_ms=duration_ms,
        duration_ms=duration_ms,
        param_signature=param_sig,
    )


# ---------------------------------------------------------------------------
# Test 1: Row probabilities sum to ~1.0
# ---------------------------------------------------------------------------


def test_probabilities_sum_to_one() -> None:
    """After fitting, each row of the probability matrix sums to ~1.0."""
    edges = [
        _make_edge("T1", "T2", 10),
        _make_edge("T1", "T3", 5),
        _make_edge("T2", "T1", 8),
        _make_edge("T2", "T3", 2),
    ]
    model = MarkovTransitionModel()
    model.fit(edges, [])

    predictions_t1 = model.predict("T1", k=10)
    total = sum(p.probability for p in predictions_t1)
    assert abs(total - 1.0) < 1e-9, f"row sum = {total}"

    predictions_t2 = model.predict("T2", k=10)
    total2 = sum(p.probability for p in predictions_t2)
    assert abs(total2 - 1.0) < 1e-9, f"row sum = {total2}"


# ---------------------------------------------------------------------------
# Test 2: Top-k predictions are monotonically decreasing in probability
# ---------------------------------------------------------------------------


def test_top_k_monotonic_decreasing() -> None:
    """Top-k predictions are sorted by probability descending."""
    edges = [
        _make_edge("T1", "T2", 50),
        _make_edge("T1", "T3", 20),
        _make_edge("T1", "T4", 5),
    ]
    model = MarkovTransitionModel()
    model.fit(edges, [])

    preds = model.predict("T1", k=3)
    assert len(preds) == 3
    probs = [p.probability for p in preds]
    for i in range(len(probs) - 1):
        assert probs[i] >= probs[i + 1], f"Not monotonic at index {i}: {probs}"


# ---------------------------------------------------------------------------
# Test 3: Duration conditioning changes predictions (short vs long bucket)
# ---------------------------------------------------------------------------


def test_duration_conditioning_changes_predictions() -> None:
    """Short and long bucket predictions differ when phrase data is available."""
    # T1 has short phrases mapping to T2 heavily
    # T3 has long phrases mapping to T4 heavily
    # We use param_signature == source_template_id to exercise the bucket path.
    edges = [
        _make_edge("T1", "T2", 40),
        _make_edge("T1", "T3", 2),
        _make_edge("T1", "T4", 2),
    ]
    # Short phrases with param_signature="T1" → bucket "short"
    short_phrases = [_make_phrase(f"p{i}", 500, param_sig="T1") for i in range(5)]
    # Long phrases with param_signature="T1" → bucket "long" (override by adding long phrases)
    # We need a separate model to compare buckets.
    edges_long = [
        _make_edge("T1", "T4", 40),
        _make_edge("T1", "T2", 2),
        _make_edge("T1", "T3", 2),
    ]
    long_phrases = [_make_phrase(f"q{i}", 8000, param_sig="T1") for i in range(5)]

    model_short = MarkovTransitionModel()
    model_short.fit(edges, short_phrases)

    model_long = MarkovTransitionModel()
    model_long.fit(edges_long, long_phrases)

    pred_short = model_short.predict("T1", duration_ms=500, k=1)
    pred_long = model_long.predict("T1", duration_ms=8000, k=1)

    assert pred_short[0].template_id == "T2", f"Expected T2, got {pred_short[0].template_id}"
    assert pred_long[0].template_id == "T4", f"Expected T4, got {pred_long[0].template_id}"
    assert pred_short[0].duration_bucket == "short"
    assert pred_long[0].duration_bucket == "long"


# ---------------------------------------------------------------------------
# Test 4: Unknown template returns empty predictions
# ---------------------------------------------------------------------------


def test_unknown_template_returns_empty() -> None:
    """Requesting predictions for an unknown template returns an empty tuple."""
    edges = [_make_edge("T1", "T2", 10)]
    model = MarkovTransitionModel()
    model.fit(edges, [])

    result = model.predict("UNKNOWN_TEMPLATE", k=5)
    assert result == ()


def test_unfitted_model_returns_empty() -> None:
    """An unfitted model returns empty predictions and 0.0 probability."""
    model = MarkovTransitionModel()
    assert model.predict("T1", k=5) == ()
    assert model.probability("T1", "T2") == 0.0


# ---------------------------------------------------------------------------
# Test 5: Save + load round trip produces identical predictions
# ---------------------------------------------------------------------------


def test_save_load_round_trip() -> None:
    """Saved and reloaded model returns identical predictions."""
    edges = [
        _make_edge("A", "B", 30),
        _make_edge("A", "C", 10),
        _make_edge("B", "A", 20),
    ]
    model = MarkovTransitionModel()
    model.fit(edges, [])

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "model.json"
        model.save(path)
        loaded = MarkovTransitionModel.load(path)

    original_preds = model.predict("A", k=3)
    loaded_preds = loaded.predict("A", k=3)

    assert len(original_preds) == len(loaded_preds)
    for orig, load in zip(original_preds, loaded_preds, strict=True):
        assert orig.template_id == load.template_id
        assert abs(orig.probability - load.probability) < 1e-12
        assert orig.rank == load.rank
