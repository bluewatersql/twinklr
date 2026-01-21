"""Tests for XSQ Pydantic models.

Following TDD: These tests are written BEFORE implementation.
They should FAIL initially (RED phase).
"""

from pydantic import ValidationError
import pytest

from blinkb0t.core.domains.sequencing.models.xsq import (
    Effect,
    EffectLayer,
    ElementEffects,
    SequenceHead,
    TimeMarker,
    TimingTrack,
    XSequence,
)


def test_time_marker_creation():
    """Test TimeMarker model creation."""
    marker = TimeMarker(name="Beat 1", time_ms=1000, position=1.0)
    assert marker.name == "Beat 1"
    assert marker.time_ms == 1000
    assert marker.position == 1.0


def test_time_marker_validation_negative_time():
    """Test TimeMarker rejects negative time."""
    with pytest.raises(ValidationError):
        TimeMarker(name="Invalid", time_ms=-100, position=0.0)


def test_time_marker_with_zero_time():
    """Test TimeMarker accepts zero time (sequence start)."""
    marker = TimeMarker(name="Start", time_ms=0, position=0.0)
    assert marker.time_ms == 0


def test_timing_track_creation():
    """Test TimingTrack model creation."""
    markers = [
        TimeMarker(name="M1", time_ms=0, position=0.0),
        TimeMarker(name="M2", time_ms=1000, position=1.0),
    ]
    track = TimingTrack(name="Beats", type="timing", markers=markers)
    assert track.name == "Beats"
    assert track.type == "timing"
    assert len(track.markers) == 2


def test_timing_track_default_type():
    """Test TimingTrack has default type."""
    track = TimingTrack(name="Test", markers=[])
    assert track.type == "timing"


def test_timing_track_empty_markers():
    """Test TimingTrack can have empty markers list."""
    track = TimingTrack(name="Empty", markers=[])
    assert len(track.markers) == 0


def test_effect_creation():
    """Test Effect model creation."""
    effect = Effect(
        effect_type="On",
        start_time_ms=0,
        end_time_ms=1000,
        palette="",
        protected=False,
        parameters={"intensity": "100"},
    )
    assert effect.effect_type == "On"
    assert effect.start_time_ms == 0
    assert effect.end_time_ms == 1000
    assert effect.duration_ms == 1000


def test_effect_validation_end_before_start():
    """Test Effect rejects end_time < start_time."""
    with pytest.raises(ValidationError):
        Effect(
            effect_type="On",
            start_time_ms=1000,
            end_time_ms=500,
            palette="",
            protected=False,
            parameters={},
        )


def test_effect_validation_equal_times():
    """Test Effect accepts equal start and end times (zero duration)."""
    effect = Effect(
        effect_type="On",
        start_time_ms=1000,
        end_time_ms=1000,
        palette="",
        protected=False,
        parameters={},
    )
    assert effect.duration_ms == 0


def test_effect_default_values():
    """Test Effect has sensible defaults."""
    effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)
    assert effect.palette == ""
    assert effect.protected is False
    assert effect.parameters == {}


def test_effect_duration_property():
    """Test Effect duration property calculates correctly."""
    effect = Effect(effect_type="ColorWash", start_time_ms=500, end_time_ms=2500)
    assert effect.duration_ms == 2000


def test_effect_layer_creation():
    """Test EffectLayer model creation."""
    effects = [
        Effect(effect_type="On", start_time_ms=0, end_time_ms=500),
        Effect(effect_type="Off", start_time_ms=500, end_time_ms=1000),
    ]
    layer = EffectLayer(index=0, name="Layer 1", effects=effects)
    assert layer.index == 0
    assert layer.name == "Layer 1"
    assert len(layer.effects) == 2


def test_effect_layer_validation_negative_index():
    """Test EffectLayer rejects negative index."""
    with pytest.raises(ValidationError):
        EffectLayer(index=-1, name="Invalid", effects=[])


def test_effect_layer_empty_effects():
    """Test EffectLayer can have empty effects list."""
    layer = EffectLayer(index=0, name="Empty", effects=[])
    assert len(layer.effects) == 0


def test_effect_layer_default_name():
    """Test EffectLayer has default name."""
    layer = EffectLayer(index=0, effects=[])
    assert layer.name == ""


def test_element_effects_creation():
    """Test ElementEffects model creation."""
    layer = EffectLayer(index=0, name="Layer 1", effects=[])
    element_effects = ElementEffects(element_name="Model1", element_type="model", layers=[layer])
    assert element_effects.element_name == "Model1"
    assert element_effects.element_type == "model"
    assert len(element_effects.layers) == 1


def test_element_effects_default_type():
    """Test ElementEffects has default type."""
    element = ElementEffects(element_name="Test", layers=[])
    assert element.element_type == "model"


def test_element_effects_multiple_layers():
    """Test ElementEffects can have multiple layers."""
    layers = [
        EffectLayer(index=0, name="Layer 1", effects=[]),
        EffectLayer(index=1, name="Layer 2", effects=[]),
        EffectLayer(index=2, name="Layer 3", effects=[]),
    ]
    element = ElementEffects(element_name="Model1", layers=layers)
    assert len(element.layers) == 3


def test_xsequence_creation():
    """Test XSequence model creation."""
    head = SequenceHead(
        version="2024.10",
        media_file="audio.mp3",
        sequence_duration_ms=30000,
    )
    sequence = XSequence(
        head=head,
        timing_tracks=[],
        element_effects=[],
    )
    assert sequence.version == "2024.10"
    assert sequence.media_file == "audio.mp3"
    assert sequence.sequence_duration_ms == 30000
    assert len(sequence.timing_tracks) == 0
    assert len(sequence.element_effects) == 0


def test_xsequence_validation_negative_duration():
    """Test XSequence rejects negative duration."""
    with pytest.raises(ValidationError):
        head = SequenceHead(
            version="2024.10",
            media_file="audio.mp3",
            sequence_duration_ms=-1000,
        )
        XSequence(head=head, timing_tracks=[], element_effects=[])


def test_xsequence_zero_duration():
    """Test XSequence accepts zero duration (empty sequence)."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=0)
    sequence = XSequence(head=head)
    assert sequence.sequence_duration_ms == 0


def test_xsequence_get_element_by_name():
    """Test finding element by name."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    element = ElementEffects(element_name="Model1", element_type="model", layers=[])
    sequence = XSequence(head=head, timing_tracks=[], element_effects=[element])

    found = sequence.get_element("Model1")
    assert found is not None
    assert found.element_name == "Model1"


def test_xsequence_get_nonexistent_element():
    """Test get_element returns None for non-existent element."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)

    not_found = sequence.get_element("NonExistent")
    assert not_found is None


def test_xsequence_add_effect_to_element():
    """Test adding effect to an element's layer."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    layer = EffectLayer(index=0, name="Layer 1", effects=[])
    element = ElementEffects(element_name="Model1", element_type="model", layers=[layer])
    sequence = XSequence(head=head, timing_tracks=[], element_effects=[element])

    new_effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)

    sequence.add_effect("Model1", new_effect, layer_index=0)

    found = sequence.get_element("Model1")
    assert len(found.layers[0].effects) == 1
    assert found.layers[0].effects[0].effect_type == "On"


def test_xsequence_add_effect_nonexistent_element():
    """Test adding effect to non-existent element creates element."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)

    effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)

    # ensure_element creates element if it doesn't exist
    sequence.add_effect("NonExistent", effect, layer_index=0)
    assert sequence.has_element("NonExistent")


def test_xsequence_add_effect_invalid_layer():
    """Test adding effect to invalid layer creates layer."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    element = ElementEffects(
        element_name="Model1", layers=[EffectLayer(index=0, name="Layer 1", effects=[])]
    )
    sequence = XSequence(head=head, element_effects=[element])

    effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)

    # add_effect creates layers if needed
    sequence.add_effect("Model1", effect, layer_index=5)
    assert len(sequence.get_element("Model1").layers) == 6


def test_xsequence_with_timing_tracks():
    """Test XSequence with timing tracks."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    marker1 = TimeMarker(name="M1", time_ms=0, position=0.0)
    marker2 = TimeMarker(name="M2", time_ms=1000, position=0.5)
    track = TimingTrack(name="Beats", markers=[marker1, marker2])

    sequence = XSequence(head=head, timing_tracks=[track])

    assert len(sequence.timing_tracks) == 1
    assert sequence.timing_tracks[0].name == "Beats"
    assert len(sequence.timing_tracks[0].markers) == 2


def test_xsequence_complex_structure():
    """Test XSequence with complex nested structure."""
    # Create timing markers
    markers = [TimeMarker(name=f"M{i}", time_ms=i * 1000, position=float(i)) for i in range(5)]
    track = TimingTrack(name="Beats", markers=markers)

    # Create effects
    effects = [
        Effect(effect_type="On", start_time_ms=i * 1000, end_time_ms=(i + 1) * 1000)
        for i in range(5)
    ]

    # Create layers
    layer1 = EffectLayer(index=0, name="Layer 1", effects=effects[:3])
    layer2 = EffectLayer(index=1, name="Layer 2", effects=effects[3:])

    # Create elements
    element1 = ElementEffects(element_name="Model1", layers=[layer1])
    element2 = ElementEffects(element_name="Model2", layers=[layer2])

    # Create sequence
    head = SequenceHead(version="2024.10", media_file="song.mp3", sequence_duration_ms=30000)
    sequence = XSequence(
        head=head,
        timing_tracks=[track],
        element_effects=[element1, element2],
    )

    assert len(sequence.timing_tracks) == 1
    assert len(sequence.element_effects) == 2
    assert len(sequence.get_element("Model1").layers[0].effects) == 3
    assert len(sequence.get_element("Model2").layers[0].effects) == 2
