"""Tests for Structure and SongSectionRef models."""

from pydantic import ValidationError
import pytest


def test_song_section_ref_valid():
    """Test SongSectionRef with valid data."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    section = SongSectionRef(
        section_id="verse_1",
        name="verse",
        start_ms=0,
        end_ms=30000,
    )

    assert section.section_id == "verse_1"
    assert section.name == "verse"
    assert section.start_ms == 0
    assert section.end_ms == 30000


def test_song_section_ref_section_id_required():
    """Test SongSectionRef requires section_id."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    # Missing section_id should fail
    with pytest.raises(ValidationError):
        SongSectionRef(name="verse", start_ms=0, end_ms=1000)


def test_song_section_ref_timing_validation():
    """Test SongSectionRef timing constraints."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    # start_ms must be >= 0
    with pytest.raises(ValidationError):
        SongSectionRef(section_id="v1", name="verse", start_ms=-1, end_ms=1000)

    # end_ms must be > 0
    with pytest.raises(ValidationError):
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=0)

    with pytest.raises(ValidationError):
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=-100)


def test_song_section_ref_end_after_start():
    """Test SongSectionRef end_ms must be > start_ms."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    # Valid: end > start
    SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=1000)
    SongSectionRef(section_id="v2", name="verse", start_ms=5000, end_ms=10000)

    # Invalid: end <= start
    with pytest.raises(ValidationError) as exc_info:
        SongSectionRef(section_id="v1", name="verse", start_ms=1000, end_ms=1000)
    assert "end_ms must be greater than start_ms" in str(exc_info.value).lower()

    with pytest.raises(ValidationError) as exc_info:
        SongSectionRef(section_id="v1", name="verse", start_ms=2000, end_ms=1000)
    assert "end_ms must be greater than start_ms" in str(exc_info.value).lower()


def test_song_section_ref_frozen():
    """Test SongSectionRef is frozen (immutable)."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    section = SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=1000)

    with pytest.raises(ValidationError):
        section.name = "chorus"


def test_song_section_ref_extra_forbid():
    """Test SongSectionRef forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef

    with pytest.raises(ValidationError) as exc_info:
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=1000, extra="not allowed")

    assert "extra" in str(exc_info.value).lower()


def test_structure_valid():
    """Test Structure with valid data."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    sections = [
        SongSectionRef(section_id="intro_1", name="intro", start_ms=0, end_ms=10000),
        SongSectionRef(section_id="verse_1", name="verse", start_ms=10000, end_ms=40000),
        SongSectionRef(section_id="chorus_1", name="chorus", start_ms=40000, end_ms=70000),
    ]

    structure = Structure(
        sections=sections,
        structure_confidence=0.93,
    )

    assert len(structure.sections) == 3
    assert structure.sections[0].name == "intro"
    assert structure.sections[1].name == "verse"
    assert structure.sections[2].name == "chorus"
    assert structure.structure_confidence == 0.93


def test_structure_confidence_validation():
    """Test Structure structure_confidence must be in [0, 1]."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    sections = [
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=10000),
    ]

    # Valid confidence values
    Structure(sections=sections, structure_confidence=0.0)
    Structure(sections=sections, structure_confidence=0.5)
    Structure(sections=sections, structure_confidence=1.0)

    # Invalid: < 0
    with pytest.raises(ValidationError):
        Structure(sections=sections, structure_confidence=-0.1)

    # Invalid: > 1
    with pytest.raises(ValidationError):
        Structure(sections=sections, structure_confidence=1.1)


def test_structure_minimum_sections():
    """Test Structure requires at least one section."""
    from twinklr.core.agents.audio.profile.models import Structure

    # Empty sections should fail (min_length=1 in spec)
    with pytest.raises(ValidationError):
        Structure(sections=[], structure_confidence=0.0)


def test_structure_not_frozen():
    """Test Structure is mutable (not frozen)."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    sections = [
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=10000),
    ]

    structure = Structure(sections=sections, structure_confidence=0.9)

    # Should be able to modify
    structure.structure_confidence = 0.8
    assert structure.structure_confidence == 0.8


def test_structure_extra_forbid():
    """Test Structure forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    sections = [
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=10000),
    ]

    with pytest.raises(ValidationError) as exc_info:
        Structure(sections=sections, structure_confidence=0.9, extra="not allowed")

    assert "extra" in str(exc_info.value).lower()


def test_structure_common_section_names():
    """Test Structure with common section names."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    common_names = [
        "intro",
        "verse",
        "chorus",
        "bridge",
        "outro",
        "pre-chorus",
        "interlude",
        "solo",
        "breakdown",
    ]

    sections = [
        SongSectionRef(
            section_id=f"{name}_{i}",
            name=name,
            start_ms=i * 10000,
            end_ms=(i + 1) * 10000,
        )
        for i, name in enumerate(common_names)
    ]

    structure = Structure(sections=sections, structure_confidence=0.9)
    assert len(structure.sections) == len(common_names)
    assert [s.name for s in structure.sections] == common_names


def test_structure_notes_optional():
    """Test Structure notes field is optional."""
    from twinklr.core.agents.audio.profile.models import SongSectionRef, Structure

    sections = [
        SongSectionRef(section_id="v1", name="verse", start_ms=0, end_ms=10000),
    ]

    # Without notes
    structure1 = Structure(sections=sections, structure_confidence=0.9)
    assert structure1.notes == []

    # With notes
    structure2 = Structure(
        sections=sections,
        structure_confidence=0.9,
        notes=["Unusual structure", "Multiple false starts"],
    )
    assert len(structure2.notes) == 2
    assert "Unusual structure" in structure2.notes
