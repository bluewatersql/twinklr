"""Tests for base context shaper."""

from unittest.mock import MagicMock

import pytest

from blinkb0t.core.agents.context.base import BaseContextShaper, ShapedContext


def test_shaped_context_model():
    """Test ShapedContext model."""
    shaped = ShapedContext(
        data={"test": "data"},
        stats={
            "original_estimate": 1000,
            "shaped_estimate": 200,
            "reduction_pct": 80.0,
            "notes": ["Test note"],
        },
    )

    assert shaped.data == {"test": "data"}
    assert shaped.stats["original_estimate"] == 1000
    assert shaped.stats["shaped_estimate"] == 200
    assert shaped.stats["reduction_pct"] == 80.0


def test_shaped_context_default_stats():
    """Test ShapedContext with default stats."""
    shaped = ShapedContext(data={"test": "data"})

    assert shaped.data == {"test": "data"}
    assert shaped.stats["original_estimate"] == 0
    assert shaped.stats["shaped_estimate"] == 0
    assert shaped.stats["reduction_pct"] == 0.0
    assert shaped.stats["notes"] == []


def test_base_context_shaper_init():
    """Test base shaper initialization."""
    shaper = BaseContextShaper()

    assert shaper.estimator is not None


def test_base_context_shaper_shape_not_implemented():
    """Test base shaper shape() must be implemented."""
    shaper = BaseContextShaper()

    with pytest.raises(NotImplementedError):
        shaper.shape(agent=MagicMock(), context={})


def test_calculate_reduction():
    """Test reduction calculation."""
    shaper = BaseContextShaper()

    original = {"data": ["item" * 100 for _ in range(100)]}  # Large
    shaped = {"data": ["item" for _ in range(10)]}  # Small

    original_tokens, shaped_tokens, reduction_pct = shaper._calculate_reduction(original, shaped)

    assert original_tokens > shaped_tokens
    assert reduction_pct > 0
    assert reduction_pct < 100


def test_calculate_reduction_no_reduction():
    """Test reduction calculation with no reduction."""
    shaper = BaseContextShaper()

    data = {"test": "data"}

    original_tokens, shaped_tokens, reduction_pct = shaper._calculate_reduction(data, data)

    assert original_tokens == shaped_tokens
    assert reduction_pct == 0.0


def test_calculate_reduction_empty():
    """Test reduction calculation with empty data."""
    shaper = BaseContextShaper()

    original_tokens, shaped_tokens, reduction_pct = shaper._calculate_reduction({}, {})

    assert original_tokens == 0
    assert shaped_tokens == 0
    assert reduction_pct == 0.0


def test_log_shaping(caplog):
    """Test logging of shaping stats."""
    shaper = BaseContextShaper()

    with caplog.at_level("INFO"):
        shaper._log_shaping("test_agent", 1000, 200, 80.0)

    assert "test_agent" in caplog.text
    assert "1000 → 200 tokens" in caplog.text
    assert "reduced 80.0%" in caplog.text
