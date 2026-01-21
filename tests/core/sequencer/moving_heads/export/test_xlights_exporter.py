"""Tests for xLights Exporter.

Tests for converting IR segments to xLights sequence format.
"""

from pathlib import Path

from blinkb0t.core.curves.models import CurvePoint, PointsCurve
from blinkb0t.core.sequencer.moving_heads.compile.template_compiler import (
    TemplateCompileResult,
)
from blinkb0t.core.sequencer.moving_heads.export.xlights_exporter import (
    XLightsExporter,
    compile_result_to_sequence,
    segment_to_effect,
    segments_to_element,
)
from blinkb0t.core.sequencer.moving_heads.export.xlights_models import (
    Effect,
    SequenceHead,
    XLightsSequence,
)
from blinkb0t.core.sequencer.moving_heads.models.channel import ChannelName
from blinkb0t.core.sequencer.moving_heads.models.ir import ChannelSegment

# =============================================================================
# Helper Fixtures
# =============================================================================


def make_dimmer_segment(
    fixture_id: str = "fixture_1",
    t0_ms: int = 0,
    t1_ms: int = 1000,
) -> ChannelSegment:
    """Create a dimmer segment for testing."""
    points = [
        CurvePoint(t=0.0, v=0.0),
        CurvePoint(t=0.5, v=1.0),
        CurvePoint(t=1.0, v=0.0),
    ]
    return ChannelSegment(
        fixture_id=fixture_id,
        channel=ChannelName.DIMMER,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        curve=PointsCurve(points=points),
        offset_centered=False,
    )


def make_pan_segment(
    fixture_id: str = "fixture_1",
    t0_ms: int = 0,
    t1_ms: int = 1000,
) -> ChannelSegment:
    """Create a pan segment for testing."""
    points = [
        CurvePoint(t=0.0, v=0.5),
        CurvePoint(t=0.5, v=1.0),
        CurvePoint(t=1.0, v=0.5),
    ]
    return ChannelSegment(
        fixture_id=fixture_id,
        channel=ChannelName.PAN,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        curve=PointsCurve(points=points),
        offset_centered=True,
        base_dmx=128,
        amplitude_dmx=64,
    )


def make_static_segment(
    fixture_id: str = "fixture_1",
    t0_ms: int = 0,
    t1_ms: int = 1000,
    dmx_value: int = 200,
) -> ChannelSegment:
    """Create a static DMX segment for testing."""
    return ChannelSegment(
        fixture_id=fixture_id,
        channel=ChannelName.DIMMER,
        t0_ms=t0_ms,
        t1_ms=t1_ms,
        static_dmx=dmx_value,
    )


# =============================================================================
# Tests for segment_to_effect
# =============================================================================


class TestSegmentToEffect:
    """Tests for converting a segment to an xLights Effect."""

    def test_dimmer_segment_creates_effect(self) -> None:
        """Test that dimmer segment creates valid effect."""
        segment = make_dimmer_segment()
        effect = segment_to_effect(segment, channel_num=12)

        assert effect.effect_type == "DMX"
        assert effect.start_time_ms == 0
        assert effect.end_time_ms == 1000

    def test_effect_has_value_curve(self) -> None:
        """Test that effect has value curve for channel."""
        segment = make_dimmer_segment()
        effect = segment_to_effect(segment, channel_num=12)

        assert "DMX12" in effect.value_curves
        curve_str = effect.value_curves["DMX12"]
        assert "Type=Custom" in curve_str
        assert "Active=TRUE" in curve_str

    def test_pan_segment_creates_offset_centered_curve(self) -> None:
        """Test that pan segment uses offset-centered conversion."""
        segment = make_pan_segment()
        effect = segment_to_effect(segment, channel_num=11)

        assert "DMX11" in effect.value_curves

    def test_static_segment_creates_flat_curve(self) -> None:
        """Test that static segment creates flat curve."""
        segment = make_static_segment(dmx_value=200)
        effect = segment_to_effect(segment, channel_num=12)

        # Static segment should have a value curve
        assert "DMX12" in effect.value_curves


# =============================================================================
# Tests for segments_to_element
# =============================================================================


class TestSegmentsToElement:
    """Tests for converting segments to an xLights ElementEffects."""

    def test_single_segment(self) -> None:
        """Test converting single segment to element."""
        segments = [make_dimmer_segment(fixture_id="MH_1")]
        channel_map = {ChannelName.DIMMER: 12}

        element = segments_to_element("MH_1", segments, channel_map)

        assert element.element_name == "MH_1"
        assert len(element.layers) >= 1

    def test_multiple_segments_same_time(self) -> None:
        """Test converting multiple segments at same time."""
        segments = [
            make_dimmer_segment(fixture_id="MH_1", t0_ms=0, t1_ms=1000),
            make_pan_segment(fixture_id="MH_1", t0_ms=0, t1_ms=1000),
        ]
        channel_map = {
            ChannelName.DIMMER: 12,
            ChannelName.PAN: 11,
        }

        element = segments_to_element("MH_1", segments, channel_map)

        assert element.element_name == "MH_1"
        # Should have effects for both channels
        total_effects = sum(len(layer.effects) for layer in element.layers)
        assert total_effects == 2

    def test_sequential_segments(self) -> None:
        """Test converting sequential segments."""
        segments = [
            make_dimmer_segment(fixture_id="MH_1", t0_ms=0, t1_ms=1000),
            make_dimmer_segment(fixture_id="MH_1", t0_ms=1000, t1_ms=2000),
        ]
        channel_map = {ChannelName.DIMMER: 12}

        element = segments_to_element("MH_1", segments, channel_map)

        total_effects = sum(len(layer.effects) for layer in element.layers)
        assert total_effects == 2


# =============================================================================
# Tests for compile_result_to_sequence
# =============================================================================


class TestCompileResultToSequence:
    """Tests for converting TemplateCompileResult to XLightsSequence."""

    def test_basic_conversion(self) -> None:
        """Test basic conversion from compile result."""
        segments = [
            make_dimmer_segment(fixture_id="fixture_1"),
            make_pan_segment(fixture_id="fixture_1"),
        ]
        result = TemplateCompileResult(
            template_id="test_template",
            segments=segments,
            num_complete_cycles=1,
            provenance=["template:test_template"],
        )
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        channel_map = {
            "fixture_1": {
                ChannelName.PAN: 11,
                ChannelName.TILT: 12,
                ChannelName.DIMMER: 13,
            }
        }

        sequence = compile_result_to_sequence(result, head, channel_map)

        assert sequence.version == "2024.1"
        assert len(sequence.elements) == 1
        assert sequence.elements[0].element_name == "fixture_1"

    def test_multiple_fixtures(self) -> None:
        """Test conversion with multiple fixtures."""
        segments = [
            make_dimmer_segment(fixture_id="fixture_1"),
            make_dimmer_segment(fixture_id="fixture_2"),
        ]
        result = TemplateCompileResult(
            template_id="test_template",
            segments=segments,
            num_complete_cycles=1,
            provenance=[],
        )
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        channel_map = {
            "fixture_1": {ChannelName.DIMMER: 13},
            "fixture_2": {ChannelName.DIMMER: 16},
        }

        sequence = compile_result_to_sequence(result, head, channel_map)

        assert len(sequence.elements) == 2
        fixture_names = {e.element_name for e in sequence.elements}
        assert "fixture_1" in fixture_names
        assert "fixture_2" in fixture_names


# =============================================================================
# Tests for XLightsExporter
# =============================================================================


class TestXLightsExporter:
    """Tests for XLightsExporter class."""

    def test_export_to_xml(self, tmp_path: Path) -> None:
        """Test exporting to XML file."""
        # Create a simple sequence
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        sequence = XLightsSequence(head=head)
        sequence.add_effect(
            "MH_1",
            Effect(
                effect_type="DMX",
                start_time_ms=0,
                end_time_ms=1000,
            ),
        )

        # Export
        exporter = XLightsExporter()
        output_path = tmp_path / "test_sequence.xsq"
        exporter.export(sequence, output_path)

        # Verify file exists and has content
        assert output_path.exists()
        content = output_path.read_text()
        assert "xsequence" in content
        assert "2024.1" in content

    def test_export_with_effects(self, tmp_path: Path) -> None:
        """Test exporting sequence with effects."""
        # Create compile result
        segments = [
            make_dimmer_segment(fixture_id="MH_1"),
            make_pan_segment(fixture_id="MH_1"),
        ]
        result = TemplateCompileResult(
            template_id="test_template",
            segments=segments,
            num_complete_cycles=1,
            provenance=[],
        )
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        channel_map = {
            "MH_1": {
                ChannelName.PAN: 11,
                ChannelName.TILT: 12,
                ChannelName.DIMMER: 13,
            }
        }

        # Convert and export
        sequence = compile_result_to_sequence(result, head, channel_map)

        exporter = XLightsExporter()
        output_path = tmp_path / "test_with_effects.xsq"
        exporter.export(sequence, output_path)

        # Verify file content
        content = output_path.read_text()
        assert "MH_1" in content
        assert "DMX" in content


# =============================================================================
# Tests for Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in export."""

    def test_empty_segments(self) -> None:
        """Test conversion with no segments."""
        result = TemplateCompileResult(
            template_id="empty",
            segments=[],
            num_complete_cycles=0,
            provenance=[],
        )
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        channel_map: dict[str, dict[ChannelName, int]] = {}

        sequence = compile_result_to_sequence(result, head, channel_map)

        assert len(sequence.elements) == 0

    def test_missing_channel_in_map(self) -> None:
        """Test handling of missing channel in channel map."""
        segments = [make_dimmer_segment(fixture_id="MH_1")]
        result = TemplateCompileResult(
            template_id="test",
            segments=segments,
            num_complete_cycles=1,
            provenance=[],
        )
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=10000,
        )
        # Empty channel map for fixture - should use default channel number
        channel_map = {"MH_1": {}}

        sequence = compile_result_to_sequence(result, head, channel_map)

        # Should still create element with default channel
        assert len(sequence.elements) == 1
