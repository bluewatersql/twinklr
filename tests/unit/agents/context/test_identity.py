"""Tests for identity context shaper."""

from unittest.mock import MagicMock

from twinklr.core.agents.context.identity import IdentityContextShaper


def test_identity_shaper_returns_unchanged():
    """Test identity shaper returns unchanged data."""
    shaper = IdentityContextShaper()

    context = {"test": "data", "more": {"nested": "values"}}
    agent = MagicMock()

    shaped = shaper.shape(agent, context)

    # Data should be unchanged
    assert shaped.data == context
    assert shaped.data is not context  # But should be a copy


def test_identity_shaper_zero_reduction():
    """Test identity shaper has zero reduction."""
    shaper = IdentityContextShaper()

    context = {"test": "data"}
    agent = MagicMock()

    shaped = shaper.shape(agent, context)

    assert shaped.stats["reduction_pct"] == 0.0
    assert shaped.stats["original_estimate"] == shaped.stats["shaped_estimate"]


def test_identity_shaper_includes_note():
    """Test identity shaper includes note about no reduction."""
    shaper = IdentityContextShaper()

    context = {"test": "data"}
    agent = MagicMock()

    shaped = shaper.shape(agent, context)

    assert "Identity shaper" in shaped.stats["notes"][0]
    assert "no reduction" in shaped.stats["notes"][0]


def test_identity_shaper_with_large_context():
    """Test identity shaper with large context."""
    shaper = IdentityContextShaper()

    context = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}
    agent = MagicMock()

    shaped = shaper.shape(agent, context)

    # Should return all data
    assert len(shaped.data["items"]) == 100
    assert shaped.stats["reduction_pct"] == 0.0
