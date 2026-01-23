"""Tests for token estimator."""

from blinkb0t.core.agents.context.token_estimator import TokenEstimator


def test_estimate_empty_dict():
    """Test estimating empty dict."""
    tokens = TokenEstimator.estimate({})

    # Empty dict "{}" = 2 chars = ~0.6 tokens
    assert tokens >= 0
    assert tokens < 10


def test_estimate_simple_dict():
    """Test estimating simple dict."""
    data = {"key": "value", "number": 42}

    tokens = TokenEstimator.estimate(data)

    # Should be reasonable (not 0, not thousands)
    assert tokens > 0
    assert tokens < 100


def test_estimate_large_dict():
    """Test estimating large dict."""
    data = {"items": [{"id": i, "name": f"item_{i}"} for i in range(100)]}

    tokens = TokenEstimator.estimate(data)

    # Should be in the hundreds
    assert tokens > 100
    assert tokens < 1000


def test_estimate_text_empty():
    """Test estimating empty text."""
    tokens = TokenEstimator.estimate_text("")

    assert tokens == 0


def test_estimate_text_simple():
    """Test estimating simple text."""
    text = "Hello, world!"  # 13 chars

    tokens = TokenEstimator.estimate_text(text)

    # 13 / 4 = ~3 tokens
    assert tokens == 3


def test_estimate_text_long():
    """Test estimating long text."""
    text = "a" * 1000  # 1000 chars

    tokens = TokenEstimator.estimate_text(text)

    # 1000 / 4 = 250 tokens
    assert tokens == 250


def test_estimate_list_empty():
    """Test estimating empty list."""
    tokens = TokenEstimator.estimate_list([])

    assert tokens >= 0
    assert tokens < 10


def test_estimate_list_simple():
    """Test estimating simple list."""
    items = [1, 2, 3, 4, 5]

    tokens = TokenEstimator.estimate_list(items)

    assert tokens > 0
    assert tokens < 50


def test_estimate_list_complex():
    """Test estimating complex list."""
    items = [{"id": i, "data": "x" * 100} for i in range(10)]

    tokens = TokenEstimator.estimate_list(items)

    # Should be in the hundreds
    assert tokens > 100
    assert tokens < 1000


def test_estimate_nested_structure():
    """Test estimating nested data structure."""
    data = {
        "songs": [
            {
                "title": "Song 1",
                "features": {"tempo": 120, "energy": [0.5, 0.6, 0.7]},
            },
            {
                "title": "Song 2",
                "features": {"tempo": 140, "energy": [0.8, 0.9, 1.0]},
            },
        ]
    }

    tokens = TokenEstimator.estimate(data)

    # Should be reasonable (relaxed range - estimates are approximate)
    assert tokens > 40
    assert tokens < 500
