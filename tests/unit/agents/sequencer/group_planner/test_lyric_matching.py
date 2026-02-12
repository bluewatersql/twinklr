"""Tests for lyric context matching in GroupPlannerStage.

Verifies the two-pass matching strategy:
1. Primary: exact section_id match
2. Fallback: timestamp overlap
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from twinklr.core.agents.sequencer.group_planner.stage import GroupPlannerStage


def _make_beat(
    section_id: str,
    timestamp_range: tuple[int, int],
    beat_type: str = "setup",
    description: str = "Test beat description here",
    visual_opportunity: str = "Test visual opportunity here",
) -> SimpleNamespace:
    """Create a mock StoryBeat."""
    return SimpleNamespace(
        section_id=section_id,
        timestamp_range=timestamp_range,
        beat_type=beat_type,
        description=description,
        visual_opportunity=visual_opportunity,
    )


def _make_phrase(
    section_id: str,
    timestamp_ms: int,
    text: str = "test phrase",
    visual_hint: str = "flash on beat",
    emphasis: str = "MED",
) -> SimpleNamespace:
    """Create a mock KeyPhrase."""
    return SimpleNamespace(
        section_id=section_id,
        timestamp_ms=timestamp_ms,
        text=text,
        visual_hint=visual_hint,
        emphasis=emphasis,
    )


def _make_lyric_context(
    story_beats: list[Any] | None = None,
    key_phrases: list[Any] | None = None,
    has_lyrics: bool = True,
    has_narrative: bool = True,
    characters: list[str] | None = None,
    themes: list[str] | None = None,
    mood_arc: str = "test mood arc",
) -> SimpleNamespace:
    """Create a mock LyricContextModel."""
    return SimpleNamespace(
        has_lyrics=has_lyrics,
        has_narrative=has_narrative,
        characters=characters or ["Rudolph"],
        themes=themes or ["underdog"],
        mood_arc=mood_arc,
        story_beats=story_beats,
        key_phrases=key_phrases,
    )


class TestBeatMatchesSection:
    """Tests for GroupPlannerStage._beat_matches_section."""

    def test_exact_section_id_match(self) -> None:
        """Beat with matching section_id is always included."""
        beat = _make_beat("chorus_1", (10000, 20000))
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_1", 10000, 20000) is True

    def test_exact_match_different_timestamps(self) -> None:
        """Section ID match takes precedence even if timestamps don't overlap."""
        beat = _make_beat("chorus_1", (90000, 95000))
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_1", 10000, 20000) is True

    def test_timestamp_fallback_overlap(self) -> None:
        """Beat overlapping the section by timestamp matches as fallback."""
        beat = _make_beat("chorus_3", (15000, 25000))  # Wrong ID but overlaps
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_2", 10000, 30000) is True

    def test_timestamp_fallback_contained(self) -> None:
        """Beat fully contained within section matches by timestamp."""
        beat = _make_beat("verse_6", (12000, 18000))  # Wrong ID
        assert GroupPlannerStage._beat_matches_section(beat, "verse_1", 10000, 20000) is True

    def test_no_match_wrong_id_no_overlap(self) -> None:
        """Beat with wrong ID and no timestamp overlap is excluded."""
        beat = _make_beat("outro_10", (180000, 190000))
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_1", 10000, 30000) is False

    def test_timestamp_boundary_exact_start(self) -> None:
        """Beat starting exactly at section start matches."""
        beat = _make_beat("wrong_id", (10000, 15000))
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_1", 10000, 30000) is True

    def test_timestamp_boundary_at_end_excluded(self) -> None:
        """Beat starting exactly at section end is excluded (half-open interval)."""
        beat = _make_beat("wrong_id", (30000, 35000))
        assert GroupPlannerStage._beat_matches_section(beat, "chorus_1", 10000, 30000) is False


class TestPhraseMatchesSection:
    """Tests for GroupPlannerStage._phrase_matches_section."""

    def test_exact_section_id_match(self) -> None:
        """Phrase with matching section_id is always included."""
        phrase = _make_phrase("verse_1", 50000)
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is True

    def test_exact_match_different_timestamp(self) -> None:
        """Section ID match takes precedence even if timestamp is outside."""
        phrase = _make_phrase("verse_1", 90000)  # Timestamp outside section
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is True

    def test_timestamp_fallback(self) -> None:
        """Phrase within section time range matches by timestamp fallback."""
        phrase = _make_phrase("verse_6", 50000)  # Wrong ID
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is True

    def test_no_match_wrong_id_outside_range(self) -> None:
        """Phrase with wrong ID and outside time range is excluded."""
        phrase = _make_phrase("outro_10", 180000)
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is False

    def test_timestamp_at_start_included(self) -> None:
        """Phrase at exact section start is included."""
        phrase = _make_phrase("wrong", 40000)
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is True

    def test_timestamp_at_end_excluded(self) -> None:
        """Phrase at exact section end is excluded (half-open interval)."""
        phrase = _make_phrase("wrong", 70000)
        assert GroupPlannerStage._phrase_matches_section(phrase, "verse_1", 40000, 70000) is False


class TestBuildSectionLyricContext:
    """Integration tests for _build_section_lyric_context."""

    def _build(
        self,
        lyric_context: Any,
        section_id: str,
        start_ms: int,
        end_ms: int,
    ) -> dict[str, Any] | None:
        """Helper to call _build_section_lyric_context on a fresh stage instance."""
        stage = GroupPlannerStage.__new__(GroupPlannerStage)
        return stage._build_section_lyric_context(
            lyric_context,
            section_id=section_id,
            start_ms=start_ms,
            end_ms=end_ms,
        )

    def test_none_lyric_context_returns_none(self) -> None:
        """No lyric context returns None."""
        assert self._build(None, "verse_1", 0, 10000) is None

    def test_no_lyrics_returns_none(self) -> None:
        """has_lyrics=False returns None."""
        ctx = _make_lyric_context(has_lyrics=False)
        assert self._build(ctx, "verse_1", 0, 10000) is None

    def test_exact_match_returns_content(self) -> None:
        """Beats and phrases matching by section_id are returned."""
        ctx = _make_lyric_context(
            story_beats=[_make_beat("verse_1", (1000, 5000))],
            key_phrases=[_make_phrase("verse_1", 2000)],
        )
        result = self._build(ctx, "verse_1", 0, 10000)
        assert result is not None
        assert len(result["story_beats"]) == 1
        assert len(result["key_phrases"]) == 1

    def test_timestamp_fallback_returns_content(self) -> None:
        """Beats and phrases matching by timestamp (not section_id) are returned."""
        ctx = _make_lyric_context(
            story_beats=[_make_beat("chorus_3", (5000, 15000))],  # Wrong ID
            key_phrases=[_make_phrase("verse_6", 8000)],  # Wrong ID
        )
        result = self._build(ctx, "verse_1", 0, 20000)
        assert result is not None
        assert len(result["story_beats"]) == 1
        assert len(result["key_phrases"]) == 1

    def test_no_matches_returns_none(self) -> None:
        """No matching beats or phrases returns None."""
        ctx = _make_lyric_context(
            story_beats=[_make_beat("outro", (180000, 190000))],
            key_phrases=[_make_phrase("outro", 185000)],
        )
        assert self._build(ctx, "verse_1", 0, 20000) is None

    def test_includes_global_context(self) -> None:
        """Result includes characters, themes, mood_arc from the model."""
        ctx = _make_lyric_context(
            story_beats=[_make_beat("v1", (1000, 5000))],
            characters=["Rudolph", "Santa"],
            themes=["underdog", "redemption"],
        )
        result = self._build(ctx, "v1", 0, 10000)
        assert result is not None
        assert result["characters"] == ["Rudolph", "Santa"]
        assert result["themes"] == ["underdog", "redemption"]
        assert result["has_narrative"] is True
