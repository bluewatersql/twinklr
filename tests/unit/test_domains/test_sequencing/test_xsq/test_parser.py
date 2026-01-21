"""Tests for XSQ Parser.

Following TDD: These tests are written BEFORE implementation.
They should FAIL initially (RED phase).
"""

import pytest

from blinkb0t.core.domains.sequencing.infrastructure.xsq.parser import XSQParser
from blinkb0t.core.domains.sequencing.models.xsq import (
    XSequence,
)


@pytest.fixture
def simple_xsq_content():
    """Minimal valid XSQ content."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <author></author>
        <author-email></author-email>
        <website></website>
        <song></song>
        <artist></artist>
        <album></album>
        <MusicURL></MusicURL>
        <comment></comment>
        <sequenceTiming>50 ms</sequenceTiming>
        <sequenceDuration>10.000</sequenceDuration>
        <imageDir/>
        <MediaFile>test.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements/>
    <ElementEffects/>
</xsequence>
"""


@pytest.fixture
def xsq_with_timing_track():
    """XSQ with a timing track."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>5.000</sequenceDuration>
        <MediaFile>song.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="timing" name="Beats" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="timing" name="Beats">
            <EffectLayer>
                <Effect label="Beat 1" startTime="0" endTime="1000"/>
                <Effect label="Beat 2" startTime="1000" endTime="2000"/>
                <Effect label="Beat 3" startTime="2000" endTime="3000"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""


@pytest.fixture
def xsq_with_effects():
    """XSQ with model effects."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>3.000</sequenceDuration>
        <MediaFile>music.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="model" name="Model1" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="model" name="Model1">
            <EffectLayer>
                <Effect ref="0" name="On" startTime="0" endTime="1000" palette="0"/>
                <Effect ref="1" name="ColorWash" startTime="1000" endTime="2000" palette="1"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""


@pytest.fixture
def xsq_with_multiple_layers():
    """XSQ with multiple effect layers."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>2.000</sequenceDuration>
        <MediaFile>track.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="model" name="Model1" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="model" name="Model1">
            <EffectLayer>
                <Effect name="On" startTime="0" endTime="1000"/>
            </EffectLayer>
            <EffectLayer>
                <Effect name="ColorWash" startTime="500" endTime="1500"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""


def test_parser_initialization():
    """Test XSQParser can be instantiated."""
    parser = XSQParser()
    assert parser is not None
    assert isinstance(parser, XSQParser)


def test_parse_simple_xsq(tmp_path, simple_xsq_content):
    """Test parsing minimal valid XSQ."""
    xsq_file = tmp_path / "simple.xsq"
    xsq_file.write_text(simple_xsq_content)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    assert isinstance(sequence, XSequence)
    assert sequence.version == "2024.10"
    assert sequence.media_file == "test.mp3"
    assert sequence.sequence_duration_ms == 10000  # 10.000 seconds = 10000ms


def test_parse_from_string(simple_xsq_content):
    """Test parsing XSQ from string."""
    parser = XSQParser()
    sequence = parser.parse_string(simple_xsq_content)

    assert isinstance(sequence, XSequence)
    assert sequence.version == "2024.10"


def test_parse_file_not_found():
    """Test parsing non-existent file raises error."""
    parser = XSQParser()

    with pytest.raises(FileNotFoundError):
        parser.parse("nonexistent.xsq")


def test_parse_malformed_xml(tmp_path):
    """Test parsing malformed XML raises error."""
    xsq_file = tmp_path / "malformed.xsq"
    xsq_file.write_text("<xsequence><unclosed>")

    parser = XSQParser()

    with pytest.raises(ValueError, match="Malformed XML"):
        parser.parse(xsq_file)


def test_parse_missing_required_fields(tmp_path):
    """Test parsing XSQ missing required fields."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
    </head>
</xsequence>
"""
    xsq_file = tmp_path / "incomplete.xsq"
    xsq_file.write_text(xsq_content)

    parser = XSQParser()

    with pytest.raises(ValueError, match="Missing required"):
        parser.parse(xsq_file)


def test_parse_timing_track(tmp_path, xsq_with_timing_track):
    """Test parsing timing track."""
    xsq_file = tmp_path / "timing.xsq"
    xsq_file.write_text(xsq_with_timing_track)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    assert len(sequence.timing_tracks) == 1
    track = sequence.timing_tracks[0]
    assert track.name == "Beats"
    assert track.type == "timing"
    assert len(track.markers) == 3

    # Check first marker
    assert track.markers[0].name == "Beat 1"
    assert track.markers[0].time_ms == 0

    # Check last marker
    assert track.markers[2].name == "Beat 3"
    assert track.markers[2].time_ms == 2000


def test_parse_model_effects(tmp_path, xsq_with_effects):
    """Test parsing model with effects."""
    xsq_file = tmp_path / "effects.xsq"
    xsq_file.write_text(xsq_with_effects)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    assert len(sequence.element_effects) == 1
    element = sequence.element_effects[0]
    assert element.element_name == "Model1"
    assert element.element_type == "model"
    assert len(element.layers) == 1

    layer = element.layers[0]
    assert len(layer.effects) == 2

    # Check first effect
    effect1 = layer.effects[0]
    assert effect1.effect_type == "On"
    assert effect1.start_time_ms == 0
    assert effect1.end_time_ms == 1000
    assert effect1.duration_ms == 1000


def test_parse_multiple_layers(tmp_path, xsq_with_multiple_layers):
    """Test parsing element with multiple effect layers."""
    xsq_file = tmp_path / "layers.xsq"
    xsq_file.write_text(xsq_with_multiple_layers)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    element = sequence.element_effects[0]
    assert len(element.layers) == 2

    assert element.layers[0].index == 0
    assert element.layers[1].index == 1


def test_parse_converts_seconds_to_milliseconds(tmp_path):
    """Test that parser converts duration from seconds to milliseconds."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>30.500</sequenceDuration>
        <MediaFile>test.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements/>
    <ElementEffects/>
</xsequence>
"""
    xsq_file = tmp_path / "duration.xsq"
    xsq_file.write_text(xsq_content)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    assert sequence.sequence_duration_ms == 30500  # 30.5s = 30500ms


def test_parse_empty_elements_list():
    """Test parsing XSQ with no elements."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>10.000</sequenceDuration>
        <MediaFile>test.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements/>
    <ElementEffects/>
</xsequence>
"""
    parser = XSQParser()
    sequence = parser.parse_string(xsq_content)

    assert len(sequence.element_effects) == 0
    assert len(sequence.timing_tracks) == 0


def test_parse_effect_with_parameters():
    """Test parsing effect with custom parameters."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>5.000</sequenceDuration>
        <MediaFile>test.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="model" name="Model1" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="model" name="Model1">
            <EffectLayer>
                <Effect name="ColorWash" startTime="0" endTime="1000"
                        E1_Colors="#FF0000,#00FF00" E1_Speed="2" E1_Direction="Right"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""
    parser = XSQParser()
    sequence = parser.parse_string(xsq_content)

    effect = sequence.element_effects[0].layers[0].effects[0]
    assert effect.parameters["E1_Colors"] == "#FF0000,#00FF00"
    assert effect.parameters["E1_Speed"] == "2"
    assert effect.parameters["E1_Direction"] == "Right"


def test_parse_protected_effect():
    """Test parsing protected (locked) effect."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>5.000</sequenceDuration>
        <MediaFile>test.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="model" name="Model1" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="model" name="Model1">
            <EffectLayer>
                <Effect name="On" startTime="0" endTime="1000" protected="1"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""
    parser = XSQParser()
    sequence = parser.parse_string(xsq_content)

    effect = sequence.element_effects[0].layers[0].effects[0]
    assert effect.protected is True


def test_parse_complex_sequence(tmp_path):
    """Test parsing complex sequence with multiple elements and timing."""
    xsq_content = """<?xml version="1.0"?>
<xsequence>
    <head>
        <version>2024.10</version>
        <sequenceDuration>10.000</sequenceDuration>
        <MediaFile>complex.mp3</MediaFile>
    </head>
    <EffectDB/>
    <DisplayElements>
        <Element type="timing" name="Beats" visible="1" collapsed="0"/>
        <Element type="model" name="Model1" visible="1" collapsed="0"/>
        <Element type="model" name="Model2" visible="1" collapsed="0"/>
    </DisplayElements>
    <ElementEffects>
        <Element type="timing" name="Beats">
            <EffectLayer>
                <Effect label="Beat 1" startTime="0" endTime="1000"/>
                <Effect label="Beat 2" startTime="1000" endTime="2000"/>
            </EffectLayer>
        </Element>
        <Element type="model" name="Model1">
            <EffectLayer>
                <Effect name="On" startTime="0" endTime="2000"/>
            </EffectLayer>
        </Element>
        <Element type="model" name="Model2">
            <EffectLayer>
                <Effect name="ColorWash" startTime="500" endTime="1500"/>
            </EffectLayer>
        </Element>
    </ElementEffects>
</xsequence>
"""
    xsq_file = tmp_path / "complex.xsq"
    xsq_file.write_text(xsq_content)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)

    # Check structure
    assert len(sequence.timing_tracks) == 1
    assert len(sequence.element_effects) == 2  # Model1 and Model2 (timing track separate)

    # Verify specific elements
    assert sequence.get_element("Model1") is not None
    assert sequence.get_element("Model2") is not None
    assert sequence.timing_tracks[0].name == "Beats"


def test_parse_accepts_path_object(tmp_path, simple_xsq_content):
    """Test parser accepts Path objects."""
    xsq_file = tmp_path / "test.xsq"
    xsq_file.write_text(simple_xsq_content)

    parser = XSQParser()
    sequence = parser.parse(xsq_file)  # Pass Path directly

    assert sequence.version == "2024.10"


def test_parse_accepts_string_path(tmp_path, simple_xsq_content):
    """Test parser accepts string paths."""
    xsq_file = tmp_path / "test.xsq"
    xsq_file.write_text(simple_xsq_content)

    parser = XSQParser()
    sequence = parser.parse(str(xsq_file))  # Pass string path

    assert sequence.version == "2024.10"
