"""Tests for new XSQ model features: EffectDB, ColorPalettes, ref/label, etc."""

from blinkb0t.core.domains.sequencing.models.xsq import (
    ColorPalette,
    Effect,
    EffectDB,
    SequenceHead,
    XSequence,
)


def test_effectdb_creation():
    """Test EffectDB model creation."""
    effectdb = EffectDB()
    assert len(effectdb.entries) == 0


def test_effectdb_append():
    """Test appending to EffectDB."""
    effectdb = EffectDB()
    idx1 = effectdb.append("E_TEXTCTRL_DMX1=128")
    idx2 = effectdb.append("E_TEXTCTRL_DMX2=255")
    assert idx1 == 0
    assert idx2 == 1
    assert len(effectdb.entries) == 2
    assert effectdb.entries[0] == "E_TEXTCTRL_DMX1=128"
    assert effectdb.entries[1] == "E_TEXTCTRL_DMX2=255"


def test_effectdb_get():
    """Test getting EffectDB entry by index."""
    effectdb = EffectDB()
    effectdb.append("Entry1")
    effectdb.append("Entry2")
    assert effectdb.get(0) == "Entry1"
    assert effectdb.get(1) == "Entry2"
    assert effectdb.get(2) is None
    assert effectdb.get(-1) is None


def test_color_palette_creation():
    """Test ColorPalette model creation."""
    palette = ColorPalette(settings="C_BUTTON_Palette1=#FFFFFF")
    assert palette.settings == "C_BUTTON_Palette1=#FFFFFF"


def test_effect_with_ref():
    """Test Effect with ref attribute."""
    effect = Effect(
        effect_type="DMX",
        start_time_ms=0,
        end_time_ms=1000,
        ref=5,
    )
    assert effect.ref == 5


def test_effect_with_label():
    """Test Effect with label attribute."""
    effect = Effect(
        effect_type="On",
        start_time_ms=0,
        end_time_ms=1000,
        label="Beat 1",
    )
    assert effect.label == "Beat 1"


def test_effect_with_ref_and_label():
    """Test Effect with both ref and label."""
    effect = Effect(
        effect_type="DMX",
        start_time_ms=0,
        end_time_ms=1000,
        ref=10,
        label="Custom Effect",
    )
    assert effect.ref == 10
    assert effect.label == "Custom Effect"


def test_xsequence_effectdb():
    """Test XSequence EffectDB support."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)
    assert len(sequence.effect_db.entries) == 0

    idx = sequence.append_effectdb("E_TEXTCTRL_DMX1=128")
    assert idx == 0
    assert len(sequence.effect_db.entries) == 1
    assert sequence.get_effectdb()[0] == "E_TEXTCTRL_DMX1=128"


def test_xsequence_color_palettes():
    """Test XSequence ColorPalettes support."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    palettes = [
        ColorPalette(settings="Palette1"),
        ColorPalette(settings="Palette2"),
    ]
    sequence = XSequence(head=head, color_palettes=palettes)
    assert len(sequence.color_palettes) == 2
    assert sequence.color_palettes[0].settings == "Palette1"


def test_xsequence_root_attributes():
    """Test XSequence root attributes."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(
        head=head,
        base_channel=10,
        chan_ctrl_basic=1,
        chan_ctrl_color=2,
        fixed_point_timing=False,
        model_blending=False,
    )
    assert sequence.base_channel == 10
    assert sequence.chan_ctrl_basic == 1
    assert sequence.chan_ctrl_color == 2
    assert sequence.fixed_point_timing is False
    assert sequence.model_blending is False


def test_xsequence_ensure_element():
    """Test ensure_element creates element if missing."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)
    assert not sequence.has_element("NewModel")

    element = sequence.ensure_element("NewModel", element_type="model")
    assert sequence.has_element("NewModel")
    assert element.element_name == "NewModel"
    assert element.element_type == "model"
    assert len(element.layers) == 1  # Default layer created


def test_xsequence_ensure_element_existing():
    """Test ensure_element returns existing element."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)
    element1 = sequence.ensure_element("Model1")
    element2 = sequence.ensure_element("Model1")
    assert element1 is element2


def test_xsequence_drop_element():
    """Test drop_element removes element."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)
    sequence.ensure_element("Model1")
    sequence.ensure_element("Model2")
    assert sequence.has_element("Model1")
    assert sequence.has_element("Model2")

    sequence.drop_element("Model1")
    assert not sequence.has_element("Model1")
    assert sequence.has_element("Model2")


def test_xsequence_reset_element_effects():
    """Test reset_element_effects clears effects but keeps element."""
    head = SequenceHead(version="2024.10", media_file="audio.mp3", sequence_duration_ms=30000)
    sequence = XSequence(head=head)
    element = sequence.ensure_element("Model1")
    effect = Effect(effect_type="On", start_time_ms=0, end_time_ms=1000)
    element.layers[0].effects.append(effect)
    assert len(element.layers[0].effects) == 1

    sequence.reset_element_effects("Model1")
    assert sequence.has_element("Model1")
    assert len(sequence.get_element("Model1").layers[0].effects) == 0


def test_xsequence_head_properties():
    """Test XSequence head property accessors."""
    head = SequenceHead(
        version="2024.10",
        media_file="audio.mp3",
        sequence_duration_ms=30000,
        author="Test Author",
        song="Test Song",
    )
    sequence = XSequence(head=head)
    assert sequence.version == "2024.10"
    assert sequence.media_file == "audio.mp3"
    assert sequence.sequence_duration_ms == 30000
    assert sequence.head.author == "Test Author"
    assert sequence.head.song == "Test Song"


def test_sequence_head_all_fields():
    """Test SequenceHead with all fields."""
    head = SequenceHead(
        version="2024.10",
        media_file="audio.mp3",
        sequence_duration_ms=30000,
        author="Author",
        author_email="author@example.com",
        author_website="https://example.com",
        song="Song",
        artist="Artist",
        album="Album",
        music_url="https://example.com/song.mp3",
        comment="Comment",
        sequence_timing="20 ms",
        sequence_type="Media",
        image_dir="/images",
    )
    assert head.version == "2024.10"
    assert head.author == "Author"
    assert head.author_email == "author@example.com"
    assert head.author_website == "https://example.com"
    assert head.song == "Song"
    assert head.artist == "Artist"
    assert head.album == "Album"
    assert head.music_url == "https://example.com/song.mp3"
    assert head.comment == "Comment"
    assert head.sequence_timing == "20 ms"
    assert head.sequence_type == "Media"
    assert head.image_dir == "/images"
