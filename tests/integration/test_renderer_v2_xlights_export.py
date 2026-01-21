"""Integration tests for xLights export pipeline.

Tests the complete flow: RenderedEffect → XlightsProvider → XSQ file
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.curves.enums import NativeCurveType
from blinkb0t.core.domains.sequencing.infrastructure.xsq import XSQParser
from blinkb0t.core.domains.sequencing.models.curves import CurvePoint, ValueCurveSpec
from blinkb0t.core.domains.sequencing.rendering.models import RenderedChannels, RenderedEffect
from blinkb0t.core.domains.sequencing.rendering.xlights_provider import XlightsProvider


@pytest.fixture
def xlights_provider():
    """Create XlightsProvider instance."""
    return XlightsProvider()


@pytest.fixture
def fixture_defs():
    """Mock fixture definitions for testing."""
    return {
        "MH1": {"pan": 11, "tilt": 13, "dimmer": 15},
        "MH2": {"pan": 21, "tilt": 23, "dimmer": 25},
    }


def test_xlights_export_native_curves(xlights_provider, fixture_defs, tmp_path):
    """Test exporting effects with Native curves to XSQ."""
    # Create rendered effects with Native curves
    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=2000,
            rendered_channels=RenderedChannels(
                pan=ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0),
                tilt=ValueCurveSpec(type=NativeCurveType.RAMP, p2=180.0),
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    # Export to XSQ
    output_path = tmp_path / "test_native.xsq"
    xlights_provider.write_to_xsq(
        rendered_effects=effects,
        output_path=output_path,
        fixture_definitions=fixture_defs,
    )

    # Verify file was created
    assert output_path.exists()

    # Parse back and verify
    parser = XSQParser()
    sequence = parser.parse(output_path)

    assert sequence is not None
    # Should have at least one effect in EffectDB
    assert len(sequence.effect_db.entries) > 0

    # Verify the effect contains Native curve strings
    settings = sequence.effect_db.entries[0]
    assert "E_VALUECURVE_DMX11=" in settings  # Pan
    assert "Type=Sine" in settings
    assert "E_VALUECURVE_DMX13=" in settings  # Tilt
    assert "Type=Ramp" in settings


def test_xlights_export_custom_curves(xlights_provider, fixture_defs, tmp_path):
    """Test exporting effects with Custom curves to XSQ."""
    # Create rendered effects with Custom curves (point arrays)
    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=[
                    CurvePoint(time=0.0, value=0.0),
                    CurvePoint(time=0.5, value=127.5),
                    CurvePoint(time=1.0, value=255.0),
                ],
                tilt=[
                    CurvePoint(time=0.0, value=100.0),
                    CurvePoint(time=1.0, value=200.0),
                ],
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    # Export to XSQ
    output_path = tmp_path / "test_custom.xsq"
    xlights_provider.write_to_xsq(
        rendered_effects=effects,
        output_path=output_path,
        fixture_definitions=fixture_defs,
    )

    # Verify file was created
    assert output_path.exists()

    # Parse back and verify
    parser = XSQParser()
    sequence = parser.parse(output_path)

    assert sequence is not None
    assert len(sequence.effect_db.entries) > 0

    # Verify the effect contains Custom curve strings
    settings = sequence.effect_db.entries[0]
    assert "E_VALUECURVE_DMX11=" in settings  # Pan
    assert "Type=Custom" in settings or "Values=" in settings


def test_xlights_export_multiple_fixtures(xlights_provider, fixture_defs, tmp_path):
    """Test exporting effects for multiple fixtures."""
    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                tilt=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        ),
        RenderedEffect(
            fixture_id="MH2",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=[CurvePoint(time=0.0, value=150.0), CurvePoint(time=1.0, value=150.0)],
                tilt=[CurvePoint(time=0.0, value=150.0), CurvePoint(time=1.0, value=150.0)],
                dimmer=[CurvePoint(time=0.0, value=200.0), CurvePoint(time=1.0, value=200.0)],
            ),
        ),
    ]

    # Export to XSQ
    output_path = tmp_path / "test_multiple.xsq"
    xlights_provider.write_to_xsq(
        rendered_effects=effects,
        output_path=output_path,
        fixture_definitions=fixture_defs,
    )

    # Verify file was created
    assert output_path.exists()

    # Parse back and verify
    parser = XSQParser()
    sequence = parser.parse(output_path)

    # Should have 2 effects (one per fixture)
    assert len(sequence.effect_db.entries) >= 2


def test_xlights_export_mixed_native_custom(xlights_provider, fixture_defs, tmp_path):
    """Test exporting effects with mixed Native and Custom curves."""
    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=ValueCurveSpec(type=NativeCurveType.SINE, p2=100.0),  # Native
                tilt=[
                    CurvePoint(time=0.0, value=100.0),
                    CurvePoint(time=1.0, value=200.0),
                ],  # Custom
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    # Export to XSQ
    output_path = tmp_path / "test_mixed.xsq"
    xlights_provider.write_to_xsq(
        rendered_effects=effects,
        output_path=output_path,
        fixture_definitions=fixture_defs,
    )

    # Verify file was created
    assert output_path.exists()

    # Parse back and verify
    parser = XSQParser()
    sequence = parser.parse(output_path)

    assert len(sequence.effect_db.entries) > 0

    # Verify both Native and Custom curves in same effect
    settings = sequence.effect_db.entries[0]
    assert "Type=Sine" in settings  # Native (pan)
    assert "Type=Custom" in settings or "Values=" in settings  # Custom (tilt)


def test_xlights_export_empty_raises_error(xlights_provider, fixture_defs, tmp_path):
    """Test that exporting empty effects list raises an error."""
    output_path = tmp_path / "test_empty.xsq"

    with pytest.raises(ValueError, match="Cannot write XSQ with empty rendered_effects list"):
        xlights_provider.write_to_xsq(
            rendered_effects=[],
            output_path=output_path,
            fixture_definitions=fixture_defs,
        )


def test_xlights_export_preserves_timing(xlights_provider, fixture_defs, tmp_path):
    """Test that effect timing is preserved in XSQ export."""
    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=1000,
            end_ms=3500,
            rendered_channels=RenderedChannels(
                pan=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                tilt=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    # Export to XSQ
    output_path = tmp_path / "test_timing.xsq"
    xlights_provider.write_to_xsq(
        rendered_effects=effects,
        output_path=output_path,
        fixture_definitions=fixture_defs,
    )

    # Parse back and verify timing
    parser = XSQParser()
    sequence = parser.parse(output_path)

    # Find the effect (it's in element_effects)
    assert len(sequence.element_effects) > 0
    element = sequence.element_effects[0]
    assert len(element.layers) > 0
    layer = element.layers[0]
    assert len(layer.effects) > 0

    effect = layer.effects[0]
    assert effect.start_time_ms == 1000
    assert effect.end_time_ms == 3500


def test_xlights_convert_to_placements_public_api(xlights_provider, fixture_defs):
    """Test the public convert_to_placements API."""
    from blinkb0t.core.domains.sequencing.models.xsq import SequenceHead, XSequence

    effects = [
        RenderedEffect(
            fixture_id="MH1",
            start_ms=0,
            end_ms=1000,
            rendered_channels=RenderedChannels(
                pan=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                tilt=[CurvePoint(time=0.0, value=100.0), CurvePoint(time=1.0, value=100.0)],
                dimmer=[CurvePoint(time=0.0, value=255.0), CurvePoint(time=1.0, value=255.0)],
            ),
        )
    ]

    # Create minimal XSequence
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=10000)
    xsq = XSequence(head=head)

    # Convert to placements
    placements = xlights_provider.convert_to_placements(effects, fixture_defs, xsq)

    # Verify
    assert len(placements) == 1
    assert placements[0].element_name == "Dmx MH1"
    assert placements[0].effect_name == "DMX"
    assert placements[0].start_ms == 0
    assert placements[0].end_ms == 1000
