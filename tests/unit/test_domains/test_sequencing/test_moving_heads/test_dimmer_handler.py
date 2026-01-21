"""Tests for DimmerHandler.

Tests the dimmer handler interface used by SegmentRenderer.
"""

from blinkb0t.core.config.fixtures import FixtureInstance
from blinkb0t.core.domains.sequencing.moving_heads.dimmer_handler import DimmerHandler

# ============================================================================
# DimmerHandler Tests
# ============================================================================


def test_dimmer_handler_creation():
    """Test DimmerHandler can be instantiated."""
    handler = DimmerHandler()
    assert handler is not None


def test_resolve_dimmer_full():
    """Test DimmerHandler resolves 'full' pattern to static value."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    result = handler.resolve_dimmer(
        pattern_id="full",
        params={},
        fixture=fixture,
    )

    # Full should return static 255
    assert isinstance(result, int)
    assert result == 255


def test_resolve_dimmer_off():
    """Test DimmerHandler resolves 'off' pattern to static value."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    result = handler.resolve_dimmer(
        pattern_id="off",
        params={},
        fixture=fixture,
    )

    # Off should return static 0
    assert isinstance(result, int)
    assert result == 0


def test_resolve_dimmer_with_base_pct():
    """Test DimmerHandler resolves static dimmer with base_pct param."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    result = handler.resolve_dimmer(
        pattern_id="full",
        params={"base_pct": 50},
        fixture=fixture,
    )

    # 50% = 127.5 ≈ 128
    assert isinstance(result, int)
    assert result == 128  # 50% of 255


def test_resolve_dimmer_dynamic_pattern_breathe():
    """Test DimmerHandler resolves dynamic 'breathe' pattern to average intensity."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    result = handler.resolve_dimmer(
        pattern_id="breathe",
        params={"intensity": "SMOOTH"},
        fixture=fixture,
    )

    # For Phase 3, dynamic patterns return average intensity
    # SMOOTH breathe: min=0, max=128 → average=64
    assert isinstance(result, int)
    assert result == 64  # Average of 0 and 128


def test_resolve_dimmer_dynamic_pattern_pulse():
    """Test DimmerHandler resolves dynamic 'pulse' pattern to average intensity."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    result = handler.resolve_dimmer(
        pattern_id="pulse",
        params={"intensity": "DRAMATIC"},
        fixture=fixture,
    )

    # For Phase 3, dynamic patterns return average intensity
    # DRAMATIC pulse defaults to 0-255 range when not found → average=127
    assert isinstance(result, int)
    assert result == 127  # Average intensity


def test_resolve_dimmer_invalid_pattern():
    """Test DimmerHandler handles invalid pattern gracefully."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    # Should fall back to full (255) for unknown patterns
    result = handler.resolve_dimmer(
        pattern_id="invalid_pattern_xyz",
        params={},
        fixture=fixture,
    )

    # Fallback to full
    assert isinstance(result, int)
    assert result == 255


def test_resolve_dimmer_with_fixture_specific_params():
    """Test DimmerHandler can use fixture-specific parameters."""
    handler = DimmerHandler()
    fixture = _create_test_fixture()

    # Handler should work with any fixture
    result = handler.resolve_dimmer(
        pattern_id="full",
        params={"base_pct": 75},
        fixture=fixture,
    )

    # 75% of 255 = 191.25 ≈ 191
    assert isinstance(result, int)
    assert result == 191


# ============================================================================
# Helper Functions
# ============================================================================


def _create_test_fixture() -> FixtureInstance:
    """Create a minimal test fixture for testing."""
    from unittest.mock import Mock

    # Create a mock fixture - dimmer handler doesn't actually use fixture properties
    # in Phase 3 (simplified implementation)
    fixture = Mock(spec=FixtureInstance)
    fixture.fixture_id = "MH_1"
    return fixture
