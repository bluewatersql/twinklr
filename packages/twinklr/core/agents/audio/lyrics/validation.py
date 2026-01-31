"""Heuristic validation for LyricContextModel.

Provides deterministic, rule-based validation of LLM-generated LyricContextModel
instances. These are fail-fast checks that catch logical errors and inconsistencies.

This is separate from Pydantic schema validation:
- Pydantic: Type correctness, field presence, basic constraints
- Heuristic: Logical consistency, cross-field rules, domain constraints
"""

from twinklr.core.agents.audio.lyrics.models import Issue, LyricContextModel, Severity
from twinklr.core.audio.models import SongBundle


def validate_lyrics(lyric_context: LyricContextModel, song_bundle: SongBundle) -> list[Issue]:
    """Validate LyricContextModel using heuristic rules.

    Args:
        lyric_context: The LyricContextModel to validate
        song_bundle: Original SongBundle for cross-validation

    Returns:
        List of validation issues. Empty list if valid.

    Validation Rules:
        Timestamp Validation:
        - All timestamps must be within song duration
        - Story beats must not overlap
        - Silent sections must not overlap

        Cross-Field Consistency:
        - has_narrative=True requires story_beats is not None
        - has_narrative=True requires characters is not None
        - has_lyrics=False should have minimal populated fields

        Thematic Consistency:
        - If has_lyrics=True, themes should not be empty
        - If has_lyrics=True, key_phrases should not be empty
        - If has_lyrics=True, recommended_visual_themes should not be empty
    """
    issues: list[Issue] = []
    duration_ms = song_bundle.timing.duration_ms

    # Timestamp validation
    issues.extend(_validate_timestamps(lyric_context, duration_ms))

    # Cross-field consistency
    issues.extend(_validate_cross_field_consistency(lyric_context))

    # Thematic consistency
    issues.extend(_validate_thematic_consistency(lyric_context))

    return issues


def _validate_timestamps(lyric_context: LyricContextModel, duration_ms: int) -> list[Issue]:
    """Validate all timestamps are within song duration and non-overlapping."""
    issues: list[Issue] = []

    # Validate key phrase timestamps
    for phrase in lyric_context.key_phrases:
        if phrase.timestamp_ms > duration_ms:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TIMESTAMP_OUT_OF_BOUNDS",
                    message=f"Key phrase '{phrase.text[:30]}...' timestamp {phrase.timestamp_ms}ms "
                    f"exceeds song duration ({duration_ms}ms)",
                    path=f"$.key_phrases[?(@.text=='{phrase.text}')].timestamp_ms",
                )
            )

    # Validate story beat timestamps
    if lyric_context.story_beats:
        for beat in lyric_context.story_beats:
            start_ms, end_ms = beat.timestamp_range
            if end_ms > duration_ms:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        code="TIMESTAMP_OUT_OF_BOUNDS",
                        message=f"Story beat in {beat.section_id} ends at {end_ms}ms, "
                        f"exceeds song duration ({duration_ms}ms)",
                        path=f"$.story_beats[?(@.section_id=='{beat.section_id}')].timestamp_range",
                    )
                )

        # Check for overlapping story beats
        sorted_beats = sorted(lyric_context.story_beats, key=lambda b: b.timestamp_range[0])
        for i in range(len(sorted_beats) - 1):
            if sorted_beats[i].timestamp_range[1] > sorted_beats[i + 1].timestamp_range[0]:
                issues.append(
                    Issue(
                        severity=Severity.WARN,
                        code="OVERLAPPING_STORY_BEATS",
                        message=f"Story beats overlap: {sorted_beats[i].section_id} "
                        f"[{sorted_beats[i].timestamp_range[0]}-{sorted_beats[i].timestamp_range[1]}ms] "
                        f"overlaps {sorted_beats[i + 1].section_id} "
                        f"[{sorted_beats[i + 1].timestamp_range[0]}-{sorted_beats[i + 1].timestamp_range[1]}ms]",
                        path="$.story_beats",
                    )
                )

    # Validate silent section timestamps
    for section in lyric_context.silent_sections:
        if section.end_ms > duration_ms:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="TIMESTAMP_OUT_OF_BOUNDS",
                    message=f"Silent section ends at {section.end_ms}ms, "
                    f"exceeds song duration ({duration_ms}ms)",
                    path="$.silent_sections",
                )
            )

    # Check for overlapping silent sections
    sorted_sections = sorted(lyric_context.silent_sections, key=lambda s: s.start_ms)
    for i in range(len(sorted_sections) - 1):
        if sorted_sections[i].end_ms > sorted_sections[i + 1].start_ms:
            issues.append(
                Issue(
                    severity=Severity.WARN,
                    code="OVERLAPPING_SILENT_SECTIONS",
                    message=f"Silent sections overlap: [{sorted_sections[i].start_ms}-{sorted_sections[i].end_ms}ms] "
                    f"overlaps [{sorted_sections[i + 1].start_ms}-{sorted_sections[i + 1].end_ms}ms]",
                    path="$.silent_sections",
                )
            )

    return issues


def _validate_cross_field_consistency(lyric_context: LyricContextModel) -> list[Issue]:
    """Validate cross-field consistency rules."""
    issues: list[Issue] = []

    # has_narrative=True requires story_beats
    if lyric_context.has_narrative and (
        lyric_context.story_beats is None or len(lyric_context.story_beats) == 0
    ):
        issues.append(
            Issue(
                severity=Severity.ERROR,
                code="NARRATIVE_MISSING_STORY_BEATS",
                message="has_narrative=True but story_beats is empty or None",
                path="$.story_beats",
                hint="Populate story_beats with narrative moments",
            )
        )

    # has_narrative=True requires characters
    if lyric_context.has_narrative and (
        lyric_context.characters is None or len(lyric_context.characters) == 0
    ):
        issues.append(
            Issue(
                severity=Severity.WARN,
                code="NARRATIVE_MISSING_CHARACTERS",
                message="has_narrative=True but characters is empty or None",
                path="$.characters",
                hint="Populate characters with named personas from lyrics",
            )
        )

    # has_lyrics=False should have minimal populated fields
    if not lyric_context.has_lyrics:
        if lyric_context.themes:
            issues.append(
                Issue(
                    severity=Severity.WARN,
                    code="NO_LYRICS_BUT_THEMES",
                    message="has_lyrics=False but themes is populated",
                    path="$.themes",
                )
            )
        if lyric_context.key_phrases:
            issues.append(
                Issue(
                    severity=Severity.ERROR,
                    code="NO_LYRICS_BUT_KEY_PHRASES",
                    message="has_lyrics=False but key_phrases is populated",
                    path="$.key_phrases",
                )
            )

    return issues


def _validate_thematic_consistency(lyric_context: LyricContextModel) -> list[Issue]:
    """Validate thematic consistency."""
    issues: list[Issue] = []

    if lyric_context.has_lyrics:
        # Themes should not be empty if lyrics available
        if not lyric_context.themes:
            issues.append(
                Issue(
                    severity=Severity.WARN,
                    code="MISSING_THEMES",
                    message="has_lyrics=True but themes is empty",
                    path="$.themes",
                    hint="Populate themes with 2-5 major thematic elements",
                )
            )

        # Key phrases should not be empty if lyrics available
        if not lyric_context.key_phrases:
            issues.append(
                Issue(
                    severity=Severity.WARN,
                    code="MISSING_KEY_PHRASES",
                    message="has_lyrics=True but key_phrases is empty",
                    path="$.key_phrases",
                    hint="Populate key_phrases with 5-10 memorable moments",
                )
            )

        # Visual themes should not be empty if lyrics available
        if not lyric_context.recommended_visual_themes:
            issues.append(
                Issue(
                    severity=Severity.WARN,
                    code="MISSING_VISUAL_THEMES",
                    message="has_lyrics=True but recommended_visual_themes is empty",
                    path="$.recommended_visual_themes",
                    hint="Populate recommended_visual_themes with 3-5 visual design recommendations",
                )
            )

    return issues
