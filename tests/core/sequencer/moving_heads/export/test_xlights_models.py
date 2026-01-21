"""Tests for xLights Data Models.

Tests for Pydantic models that represent xLights sequence structure
including effects, layers, elements, and the complete sequence.
"""

import re

import pytest

from blinkb0t.core.sequencer.moving_heads.export.xlights_models import (
    ColorPalette,
    Effect,
    EffectDB,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    TimingMarker,
    TimingTrack,
    XLightsSequence,
)

# =============================================================================
# Tests for TimingMarker
# =============================================================================


class TestTimingMarker:
    """Tests for TimingMarker model."""

    def test_minimal_valid_marker(self) -> None:
        """Test creating marker with minimal fields."""
        marker = TimingMarker(
            label="Beat 1",
            time_ms=0,
        )
        assert marker.label == "Beat 1"
        assert marker.time_ms == 0
        assert marker.end_time_ms is None

    def test_marker_with_end_time(self) -> None:
        """Test creating marker with end time."""
        marker = TimingMarker(
            label="Section",
            time_ms=1000,
            end_time_ms=2000,
        )
        assert marker.time_ms == 1000
        assert marker.end_time_ms == 2000

    def test_marker_negative_time_rejected(self) -> None:
        """Test that negative time is rejected."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            TimingMarker(label="Bad", time_ms=-100)

    def test_marker_end_before_start_rejected(self) -> None:
        """Test that end_time before start_time is rejected."""
        with pytest.raises(ValueError, match="end_time_ms.*must be >= time_ms"):  # noqa: RUF043
            TimingMarker(label="Bad", time_ms=1000, end_time_ms=500)


# =============================================================================
# Tests for TimingTrack
# =============================================================================


class TestTimingTrack:
    """Tests for TimingTrack model."""

    def test_empty_track(self) -> None:
        """Test creating empty timing track."""
        track = TimingTrack(name="Beats")
        assert track.name == "Beats"
        assert track.markers == []

    def test_track_with_markers(self) -> None:
        """Test creating track with markers."""
        markers = [
            TimingMarker(label="1", time_ms=0),
            TimingMarker(label="2", time_ms=500),
        ]
        track = TimingTrack(name="Beats", markers=markers)
        assert len(track.markers) == 2


# =============================================================================
# Tests for Effect
# =============================================================================


class TestEffect:
    """Tests for Effect model."""

    def test_minimal_effect(self) -> None:
        """Test creating effect with minimal fields."""
        effect = Effect(
            effect_type="On",
            start_time_ms=0,
            end_time_ms=1000,
        )
        assert effect.effect_type == "On"
        assert effect.start_time_ms == 0
        assert effect.end_time_ms == 1000
        assert effect.duration_ms == 1000

    def test_effect_with_settings(self) -> None:
        """Test effect with settings string."""
        effect = Effect(
            effect_type="DMX",
            start_time_ms=0,
            end_time_ms=500,
            settings="E_TEXTCTRL_DMX1=128",
        )
        assert effect.settings == "E_TEXTCTRL_DMX1=128"

    def test_effect_with_value_curves(self) -> None:
        """Test effect with value curve strings."""
        effect = Effect(
            effect_type="DMX",
            start_time_ms=0,
            end_time_ms=1000,
            value_curves={"DMX1": "Active=TRUE|Type=Ramp|Min=0|Max=255|"},
        )
        assert "DMX1" in effect.value_curves

    def test_effect_end_before_start_rejected(self) -> None:
        """Test that end_time before start_time is rejected."""
        with pytest.raises(ValueError, match=re.escape("end_time_ms.*must be >= start_time_ms")):
            Effect(effect_type="On", start_time_ms=1000, end_time_ms=500)

    def test_effect_zero_duration_allowed(self) -> None:
        """Test that zero duration is allowed."""
        effect = Effect(effect_type="On", start_time_ms=1000, end_time_ms=1000)
        assert effect.duration_ms == 0


# =============================================================================
# Tests for EffectLayer
# =============================================================================


class TestEffectLayer:
    """Tests for EffectLayer model."""

    def test_empty_layer(self) -> None:
        """Test creating empty layer."""
        layer = EffectLayer(index=0)
        assert layer.index == 0
        assert layer.effects == []

    def test_layer_with_effects(self) -> None:
        """Test layer with effects."""
        effects = [
            Effect(effect_type="On", start_time_ms=0, end_time_ms=500),
            Effect(effect_type="On", start_time_ms=500, end_time_ms=1000),
        ]
        layer = EffectLayer(index=0, effects=effects)
        assert len(layer.effects) == 2


# =============================================================================
# Tests for ElementEffects
# =============================================================================


class TestElementEffects:
    """Tests for ElementEffects model."""

    def test_minimal_element(self) -> None:
        """Test creating element with minimal fields."""
        element = ElementEffects(element_name="MH_1")
        assert element.element_name == "MH_1"
        assert element.layers == []

    def test_element_with_layers(self) -> None:
        """Test element with layers."""
        layers = [
            EffectLayer(index=0),
            EffectLayer(index=1),
        ]
        element = ElementEffects(element_name="MH_1", layers=layers)
        assert len(element.layers) == 2

    def test_element_add_effect(self) -> None:
        """Test adding effect to element."""
        element = ElementEffects(element_name="MH_1")
        effect = Effect(effect_type="DMX", start_time_ms=0, end_time_ms=1000)

        element.add_effect(effect, layer_index=0)

        assert len(element.layers) == 1
        assert len(element.layers[0].effects) == 1

    def test_element_add_effect_creates_layer(self) -> None:
        """Test adding effect creates layer if needed."""
        element = ElementEffects(element_name="MH_1")
        effect = Effect(effect_type="DMX", start_time_ms=0, end_time_ms=1000)

        element.add_effect(effect, layer_index=2)

        # Should have created layers 0, 1, 2
        assert len(element.layers) == 3
        assert element.layers[2].effects[0] == effect


# =============================================================================
# Tests for EffectDB
# =============================================================================


class TestEffectDB:
    """Tests for EffectDB model."""

    def test_empty_db(self) -> None:
        """Test creating empty effect database."""
        db = EffectDB()
        assert len(db.entries) == 0

    def test_append_entry(self) -> None:
        """Test appending entry to database."""
        db = EffectDB()
        idx = db.append("E_TEXTCTRL_DMX1=128")
        assert idx == 0
        assert db.get(0) == "E_TEXTCTRL_DMX1=128"

    def test_get_invalid_index(self) -> None:
        """Test getting invalid index returns None."""
        db = EffectDB()
        assert db.get(99) is None


# =============================================================================
# Tests for ColorPalette
# =============================================================================


class TestColorPalette:
    """Tests for ColorPalette model."""

    def test_palette_creation(self) -> None:
        """Test creating color palette."""
        palette = ColorPalette(settings="C_BUTTON_Palette1=#FF0000")
        assert palette.settings == "C_BUTTON_Palette1=#FF0000"


# =============================================================================
# Tests for SequenceHead
# =============================================================================


class TestSequenceHead:
    """Tests for SequenceHead model."""

    def test_minimal_head(self) -> None:
        """Test creating sequence head with required fields."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        assert head.version == "2024.1"
        assert head.media_file == "song.mp3"
        assert head.sequence_duration_ms == 180000

    def test_head_with_metadata(self) -> None:
        """Test head with optional metadata."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
            author="BlinkB0t",
            song="Test Song",
            artist="Test Artist",
        )
        assert head.author == "BlinkB0t"
        assert head.song == "Test Song"

    def test_head_negative_duration_rejected(self) -> None:
        """Test that negative duration is rejected."""
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            SequenceHead(
                version="2024.1",
                media_file="song.mp3",
                sequence_duration_ms=-1000,
            )


# =============================================================================
# Tests for XLightsSequence
# =============================================================================


class TestXLightsSequence:
    """Tests for XLightsSequence model."""

    def test_minimal_sequence(self) -> None:
        """Test creating sequence with minimal fields."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)

        assert seq.head == head
        assert seq.elements == []
        assert seq.timing_tracks == []

    def test_sequence_ensure_element(self) -> None:
        """Test ensuring element exists."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)

        # First call creates element
        elem1 = seq.ensure_element("MH_1")
        assert elem1.element_name == "MH_1"

        # Second call returns same element
        elem2 = seq.ensure_element("MH_1")
        assert elem1 is elem2

    def test_sequence_add_effect(self) -> None:
        """Test adding effect to sequence."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)
        effect = Effect(effect_type="DMX", start_time_ms=0, end_time_ms=1000)

        seq.add_effect("MH_1", effect)

        assert len(seq.elements) == 1
        assert seq.elements[0].element_name == "MH_1"
        assert len(seq.elements[0].layers[0].effects) == 1

    def test_sequence_get_element(self) -> None:
        """Test getting element by name."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)
        seq.ensure_element("MH_1")
        seq.ensure_element("MH_2")

        elem = seq.get_element("MH_1")
        assert elem is not None
        assert elem.element_name == "MH_1"

        missing = seq.get_element("MH_99")
        assert missing is None

    def test_sequence_properties(self) -> None:
        """Test sequence property accessors."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)

        assert seq.version == "2024.1"
        assert seq.media_file == "song.mp3"
        assert seq.duration_ms == 180000


# =============================================================================
# Tests for JSON Serialization
# =============================================================================


class TestJsonSerialization:
    """Tests for JSON serialization of xLights models."""

    def test_effect_roundtrip(self) -> None:
        """Test effect JSON roundtrip."""
        effect = Effect(
            effect_type="DMX",
            start_time_ms=0,
            end_time_ms=1000,
            settings="E_TEXTCTRL_DMX1=128",
            value_curves={"DMX1": "Active=TRUE|Type=Ramp|"},
        )
        json_str = effect.model_dump_json()
        restored = Effect.model_validate_json(json_str)

        assert restored.effect_type == effect.effect_type
        assert restored.start_time_ms == effect.start_time_ms
        assert restored.value_curves == effect.value_curves

    def test_sequence_roundtrip(self) -> None:
        """Test sequence JSON roundtrip."""
        head = SequenceHead(
            version="2024.1",
            media_file="song.mp3",
            sequence_duration_ms=180000,
        )
        seq = XLightsSequence(head=head)
        seq.add_effect(
            "MH_1",
            Effect(effect_type="DMX", start_time_ms=0, end_time_ms=1000),
        )

        json_str = seq.model_dump_json()
        restored = XLightsSequence.model_validate_json(json_str)

        assert restored.version == seq.version
        assert len(restored.elements) == 1
