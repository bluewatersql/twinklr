"""Tests for canonical section ID generation.

Verifies generate_section_ids produces per-type counter IDs that are
consistent across the pipeline (audio profile, lyrics, macro, group planner).
"""

from __future__ import annotations

from twinklr.core.audio.sections import generate_section_ids


class TestGenerateSectionIds:
    """Tests for generate_section_ids utility."""

    def test_empty_sections(self) -> None:
        """Empty input produces empty output."""
        assert generate_section_ids([]) == []

    def test_single_section_no_suffix(self) -> None:
        """A single section type gets no counter suffix."""
        sections = [{"label": "intro"}]
        assert generate_section_ids(sections) == ["intro"]

    def test_singleton_types_no_suffix(self) -> None:
        """Section types that appear only once get no suffix."""
        sections = [
            {"label": "intro"},
            {"label": "chorus"},
            {"label": "bridge"},
            {"label": "outro"},
        ]
        result = generate_section_ids(sections)
        assert result == ["intro", "chorus", "bridge", "outro"]

    def test_multi_occurrence_types_get_counters(self) -> None:
        """Section types that appear multiple times get 1-based counter suffix."""
        sections = [
            {"label": "verse"},
            {"label": "chorus"},
            {"label": "verse"},
            {"label": "chorus"},
        ]
        result = generate_section_ids(sections)
        assert result == ["verse_1", "chorus_1", "verse_2", "chorus_2"]

    def test_mixed_singleton_and_multi(self) -> None:
        """Mix of singleton and multi-occurrence types."""
        sections = [
            {"label": "intro"},
            {"label": "chorus"},
            {"label": "verse"},
            {"label": "chorus"},
            {"label": "verse"},
            {"label": "outro"},
        ]
        result = generate_section_ids(sections)
        assert result == ["intro", "chorus_1", "verse_1", "chorus_2", "verse_2", "outro"]

    def test_rudolph_song_structure(self) -> None:
        """Matches the expected IDs for the Rudolph song structure."""
        sections = [
            {"label": "intro"},
            {"label": "chorus"},
            {"label": "break"},
            {"label": "chorus"},
            {"label": "break"},
            {"label": "verse"},
            {"label": "verse"},
            {"label": "verse"},
            {"label": "verse"},
            {"label": "instrumental"},
            {"label": "outro"},
        ]
        result = generate_section_ids(sections)
        assert result == [
            "intro",
            "chorus_1",
            "break_1",
            "chorus_2",
            "break_2",
            "verse_1",
            "verse_2",
            "verse_3",
            "verse_4",
            "instrumental",
            "outro",
        ]

    def test_type_key_fallback(self) -> None:
        """Falls back to 'type' key if 'label' is not present."""
        sections = [
            {"type": "verse"},
            {"type": "chorus"},
            {"type": "verse"},
        ]
        result = generate_section_ids(sections)
        assert result == ["verse_1", "chorus", "verse_2"]

    def test_unknown_fallback(self) -> None:
        """Falls back to 'unknown' if neither label nor type is present."""
        sections = [{"start_s": 0}, {"start_s": 10}]
        result = generate_section_ids(sections)
        assert result == ["unknown_1", "unknown_2"]

    def test_preserves_order(self) -> None:
        """Output order matches input order."""
        sections = [
            {"label": "outro"},
            {"label": "intro"},
            {"label": "chorus"},
        ]
        result = generate_section_ids(sections)
        assert result == ["outro", "intro", "chorus"]

    def test_many_repeated_sections(self) -> None:
        """Handles many occurrences of the same type."""
        sections = [{"label": "verse"} for _ in range(10)]
        result = generate_section_ids(sections)
        expected = [f"verse_{i}" for i in range(1, 11)]
        assert result == expected
