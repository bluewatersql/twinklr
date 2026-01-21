"""Tests for XlightsProvider.

Tests the xLights integration layer that converts RenderedEffect objects
to xLights XSQ file format.
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead, XSequence
from blinkb0t.core.domains.sequencing.rendering.models import (
    RenderedChannels,
    RenderedEffect,
)
from blinkb0t.core.domains.sequencing.rendering.xlights_provider import (
    XlightsProvider,
)


def test_xlights_provider_init():
    """Test XlightsProvider initialization."""
    provider = XlightsProvider()

    assert provider.adapter is not None
    assert provider.parser is not None
    assert provider.exporter is not None


def test_convert_to_placements_native_curve(mock_fixture_defs, mock_xsq):
    """Test conversion with Native curve (ValueCurveSpec)."""
    provider = XlightsProvider()

    # Effect with Native curve
    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=RenderedChannels(
            pan=ValueCurveSpec(type=NativeCurveType.RAMP, p2=200.0),  # Native!
            tilt=[CurvePoint(time=0.0, value=127.0), CurvePoint(time=1.0, value=127.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
        ),
    )

    placements = provider._convert_to_placements([effect], mock_fixture_defs, mock_xsq)

    # Should have 1 placement (one effect per fixture)
    assert len(placements) == 1

    placement = placements[0]
    assert placement.element_name == "Dmx MH1"
    assert placement.effect_name == "DMX"
    assert placement.ref >= 0  # Should have EffectDB entry (0-indexed)

    # Check that settings string was added to EffectDB
    settings = mock_xsq.effect_db.entries[placement.ref]
    assert "E_VALUECURVE_DMX11=" in settings  # Pan channel
    assert "Type=Ramp" in settings  # Native curve


def test_convert_to_placements_custom_curve(mock_fixture_defs, mock_xsq):
    """Test conversion with Custom curve (point array)."""
    provider = XlightsProvider()

    # Effect with Custom curves
    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=RenderedChannels(
            pan=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)],  # Custom!
            tilt=[CurvePoint(time=0.0, value=127.0), CurvePoint(time=1.0, value=127.0)],
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
        ),
    )

    placements = provider._convert_to_placements([effect], mock_fixture_defs, mock_xsq)

    # Should have 1 placement
    assert len(placements) == 1

    placement = placements[0]
    settings = mock_xsq.effect_db.entries[placement.ref]

    # Pan should use custom format (points)
    assert "E_VALUECURVE_DMX11=" in settings
    assert "Type=Custom" in settings or "Values=" in settings


def test_convert_to_placements_mixed_curves(mock_fixture_defs, mock_xsq):
    """Test conversion with mixed Native and Custom curves."""
    provider = XlightsProvider()

    # Effect with BOTH types
    effect = RenderedEffect(
        fixture_id="MH1",
        start_ms=0,
        end_ms=1000,
        rendered_channels=RenderedChannels(
            pan=ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0),  # Native
            tilt=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)],  # Custom
            dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],  # Custom
        ),
    )

    placements = provider._convert_to_placements([effect], mock_fixture_defs, mock_xsq)

    assert len(placements) == 1

    settings = mock_xsq.effect_db.entries[placements[0].ref]

    assert "E_VALUECURVE_DMX11=" in settings
    assert "Type=Sine" in settings

    # Tilt is Custom
    assert "E_VALUECURVE_DMX13=" in settings
    assert "Type=Custom" in settings or "Values=" in settings


def test_convert_to_placements_public_api(mock_fixture_defs, mock_xsq):
    """Test public API wrapper."""
    provider = XlightsProvider()

    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=[CurvePoint(time=0.0, value=0.0), CurvePoint(time=1.0, value=255.0)],
                tilt=[CurvePoint(time=0.0, value=127.0), CurvePoint(time=1.0, value=127.0)],
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    placements = provider.convert_to_placements(effects, mock_fixture_defs, mock_xsq)

    assert len(placements) == 1
    # Verify they're EffectPlacement objects
    assert all(hasattr(p, "element_name") for p in placements)
    assert all(hasattr(p, "effect_name") for p in placements)
    assert all(hasattr(p, "ref") for p in placements)


@pytest.fixture
def mock_fixture_defs():
    """Mock fixture definitions."""
    return {
        "MH1": {
            "pan": 11,
            "tilt": 13,
            "dimmer": 15,
            "shutter": 17,
        }
    }


@pytest.fixture
def mock_xsq():
    """Mock XSequence object."""
    head = SequenceHead(
        version="2024.10",
        media_file="test.mp3",
        sequence_duration_ms=30000,
    )
    return XSequence(head=head)
