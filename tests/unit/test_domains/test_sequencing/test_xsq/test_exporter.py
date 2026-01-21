"""Tests for XSQ Exporter.

Following TDD: These tests are written BEFORE implementation.
They should FAIL initially (RED phase).
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.xsq.exporter import XSQExporter
from blinkb0t.core.domains.sequencing.infrastructure.xsq.parser import XSQParser
from blinkb0t.core.domains.sequencing.models.xsq import (
    Effect,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)


@pytest.fixture
def simple_sequence():
    """Create a simple XSequence for testing."""
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=10000)
    return XSequence(head=head, timing_tracks=[], element_effects=[])


@pytest.fixture
def sequence_with_timing():
    """Create XSequence with timing track."""
    head = SequenceHead(version="2024.10", media_file="song.mp3", sequence_duration_ms=5000)
    markers = [
        TimeMarker(name="Beat 1", time_ms=0, position=0.0),
        TimeMarker(name="Beat 2", time_ms=1000, position=0.1),
        TimeMarker(name="Beat 3", time_ms=2000, position=0.2),
    ]
    track = TimingTrack(name="Beats", type="timing", markers=markers)

    return XSequence(head=head, timing_tracks=[track], element_effects=[])


@pytest.fixture
def sequence_with_effects():
    """Create XSequence with effects."""
    head = SequenceHead(version="2024.10", media_file="music.mp3", sequence_duration_ms=3000)
    effects = [
        Effect(effect_type="On", start_time_ms=0, end_time_ms=1000),
        Effect(effect_type="ColorWash", start_time_ms=1000, end_time_ms=2000),
    ]
    layer = EffectLayer(index=0, name="Layer 1", effects=effects)
    element = ElementEffects(element_name="Model1", element_type="model", layers=[layer])

    return XSequence(head=head, timing_tracks=[], element_effects=[element])


def test_exporter_initialization():
    """Test XSQExporter can be instantiated."""
    exporter = XSQExporter()
    assert exporter is not None
    assert isinstance(exporter, XSQExporter)


def test_export_simple_sequence(tmp_path, simple_sequence):
    """Test exporting simple sequence."""
    output_file = tmp_path / "output.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file)

    # Verify file was created
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_export_creates_valid_xml(tmp_path, simple_sequence):
    """Test exported file is valid XML."""
    output_file = tmp_path / "output.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file)

    # Should be parseable as XML
    parser = XSQParser()
    parsed = parser.parse(output_file)

    assert parsed.version == simple_sequence.version
    assert parsed.media_file == simple_sequence.media_file


def test_export_accepts_string_path(tmp_path, simple_sequence):
    """Test exporter accepts string paths."""
    output_file = tmp_path / "output.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, str(output_file))

    assert output_file.exists()


def test_export_accepts_path_object(tmp_path, simple_sequence):
    """Test exporter accepts Path objects."""
    output_file = tmp_path / "output.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file)

    assert output_file.exists()


def test_export_creates_parent_directories(tmp_path, simple_sequence):
    """Test exporter creates parent directories if needed."""
    output_file = tmp_path / "subdir" / "nested" / "output.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file)

    assert output_file.exists()
    assert output_file.parent.exists()


def test_roundtrip_simple_sequence(tmp_path, simple_sequence):
    """Test parse → export → parse preserves data."""
    output_file = tmp_path / "roundtrip.xsq"

    # Export
    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file)

    # Re-parse
    parser = XSQParser()
    parsed = parser.parse(output_file)

    # Verify all fields match
    assert parsed.version == simple_sequence.version
    assert parsed.media_file == simple_sequence.media_file
    assert parsed.sequence_duration_ms == simple_sequence.sequence_duration_ms
    assert len(parsed.timing_tracks) == len(simple_sequence.timing_tracks)
    assert len(parsed.element_effects) == len(simple_sequence.element_effects)


def test_roundtrip_with_timing_track(tmp_path, sequence_with_timing):
    """Test roundtrip with timing tracks."""
    output_file = tmp_path / "timing.xsq"

    exporter = XSQExporter()
    exporter.export(sequence_with_timing, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    # Verify timing track
    assert len(parsed.timing_tracks) == 1
    track = parsed.timing_tracks[0]
    assert track.name == "Beats"
    assert len(track.markers) == 3

    # Verify marker details
    assert track.markers[0].name == "Beat 1"
    assert track.markers[0].time_ms == 0
    assert track.markers[2].name == "Beat 3"
    assert track.markers[2].time_ms == 2000


def test_roundtrip_with_effects(tmp_path, sequence_with_effects):
    """Test roundtrip with effects."""
    output_file = tmp_path / "effects.xsq"

    exporter = XSQExporter()
    exporter.export(sequence_with_effects, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    # Verify element
    assert len(parsed.element_effects) == 1
    element = parsed.element_effects[0]
    assert element.element_name == "Model1"
    assert element.element_type == "model"

    # Verify effects
    assert len(element.layers[0].effects) == 2
    assert element.layers[0].effects[0].effect_type == "On"
    assert element.layers[0].effects[1].effect_type == "ColorWash"


def test_export_with_effect_parameters(tmp_path):
    """Test exporting effects with custom parameters."""
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=2000)
    effect = Effect(
        effect_type="ColorWash",
        start_time_ms=0,
        end_time_ms=1000,
        parameters={"E1_Colors": "#FF0000,#00FF00", "E1_Speed": "2", "E1_Direction": "Right"},
    )
    layer = EffectLayer(index=0, effects=[effect])
    element = ElementEffects(element_name="Model1", layers=[layer])
    sequence = XSequence(head=head, element_effects=[element])

    output_file = tmp_path / "params.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    parsed_effect = parsed.element_effects[0].layers[0].effects[0]
    assert parsed_effect.parameters["E1_Colors"] == "#FF0000,#00FF00"
    assert parsed_effect.parameters["E1_Speed"] == "2"
    assert parsed_effect.parameters["E1_Direction"] == "Right"


def test_export_protected_effect(tmp_path):
    """Test exporting protected (locked) effect."""
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=2000)
    effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000, protected=True)
    layer = EffectLayer(index=0, effects=[effect])
    element = ElementEffects(element_name="Model1", layers=[layer])
    sequence = XSequence(head=head, element_effects=[element])

    output_file = tmp_path / "protected.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    parsed_effect = parsed.element_effects[0].layers[0].effects[0]
    assert parsed_effect.protected is True


def test_export_multiple_layers(tmp_path):
    """Test exporting element with multiple layers."""
    layer1 = EffectLayer(
        index=0,
        name="Layer 1",
        effects=[Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)],
    )
    layer2 = EffectLayer(
        index=1,
        name="Layer 2",
        effects=[Effect(effect_type="ColorWash", start_time_ms=500, end_time_ms=1500)],
    )
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=2000)
    element = ElementEffects(element_name="Model1", layers=[layer1, layer2])
    sequence = XSequence(head=head, element_effects=[element])

    output_file = tmp_path / "layers.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    assert len(parsed.element_effects[0].layers) == 2
    assert parsed.element_effects[0].layers[0].name == "Layer 1"
    assert parsed.element_effects[0].layers[1].name == "Layer 2"


def test_export_complex_sequence(tmp_path):
    """Test exporting complex sequence with timing and multiple elements."""
    # Timing track
    markers = [TimeMarker(name=f"M{i}", time_ms=i * 1000, position=float(i)) for i in range(3)]
    timing = TimingTrack(name="Beats", markers=markers)

    # Elements with effects
    element1 = ElementEffects(
        element_name="Model1",
        layers=[
            EffectLayer(
                index=0, effects=[Effect(effect_type="On", start_time_ms=0, end_time_ms=2000)]
            )
        ],
    )
    element2 = ElementEffects(
        element_name="Model2",
        layers=[
            EffectLayer(
                index=0,
                effects=[Effect(effect_type="ColorWash", start_time_ms=500, end_time_ms=1500)],
            )
        ],
    )

    head = SequenceHead(version="2024.10", media_file="complex.mp3", sequence_duration_ms=10000)
    sequence = XSequence(head=head, timing_tracks=[timing], element_effects=[element1, element2])

    output_file = tmp_path / "complex.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    # Verify structure
    assert len(parsed.timing_tracks) == 1
    assert len(parsed.element_effects) == 2
    assert parsed.get_element("Model1") is not None
    assert parsed.get_element("Model2") is not None


def test_export_converts_milliseconds_to_seconds(tmp_path):
    """Test that exporter converts duration from milliseconds to seconds."""
    head = SequenceHead(version="2024.10", media_file="test.mp3", sequence_duration_ms=30500)
    sequence = XSequence(head=head)

    output_file = tmp_path / "duration.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    # Read the raw XML to check format
    content = output_file.read_text()
    assert (
        "<sequenceDuration>30.500</sequenceDuration>" in content
        or "<sequenceDuration>30.5</sequenceDuration>" in content
    )


def test_export_with_pretty_formatting(tmp_path, simple_sequence):
    """Test export with pretty formatting (indentation)."""
    output_file = tmp_path / "pretty.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file, pretty=True)

    content = output_file.read_text()

    # Should have indentation (multiple spaces or tabs)
    assert "  <" in content or "\t<" in content


def test_export_without_pretty_formatting(tmp_path, simple_sequence):
    """Test export without pretty formatting."""
    output_file = tmp_path / "compact.xsq"

    exporter = XSQExporter()
    exporter.export(simple_sequence, output_file, pretty=False)

    # File should still be valid
    parser = XSQParser()
    parsed = parser.parse(output_file)
    assert parsed.version == simple_sequence.version


def test_export_empty_sequence(tmp_path):
    """Test exporting sequence with no timing tracks or effects."""
    head = SequenceHead(version="2024.10", media_file="empty.mp3", sequence_duration_ms=1000)
    sequence = XSequence(head=head, timing_tracks=[], element_effects=[])

    output_file = tmp_path / "empty.xsq"

    exporter = XSQExporter()
    exporter.export(sequence, output_file)

    parser = XSQParser()
    parsed = parser.parse(output_file)

    assert len(parsed.timing_tracks) == 0
    assert len(parsed.element_effects) == 0
