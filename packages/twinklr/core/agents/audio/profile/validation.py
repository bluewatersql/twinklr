"""Heuristic validation for AudioProfileModel.

Provides deterministic, rule-based validation of LLM-generated AudioProfileModel
instances. These are fail-fast checks that catch logical errors and inconsistencies.

This is separate from Pydantic schema validation:
- Pydantic: Type correctness, field presence, basic constraints
- Heuristic: Logical consistency, cross-field rules, domain constraints
"""

from twinklr.core.agents.audio.profile.models import AudioProfileModel


def validate_audio_profile(profile: AudioProfileModel) -> list[str]:
    """Validate AudioProfileModel using heuristic rules.

    Args:
        profile: The AudioProfileModel to validate.

    Returns:
        List of validation error messages. Empty list if valid.

    Validation Rules:
        Section Validation:
        - Sections must be monotonically increasing (start_ms)
        - Sections must not overlap
        - Sections must be within song duration
        - At least one section must be present

        Energy Validation:
        - Energy curve timestamps must be monotonic
        - Energy peaks must be within song duration

        Cross-Field Consistency:
        - has_timed_words=True requires has_plain_lyrics=True
        - has_phonemes=True requires has_timed_words=True
    """
    errors: list[str] = []

    # Section validation
    errors.extend(_validate_sections(profile))

    # Energy validation
    errors.extend(_validate_energy(profile))

    # Lyric consistency
    errors.extend(_validate_lyric_consistency(profile))

    return errors


def _validate_sections(profile: AudioProfileModel) -> list[str]:
    """Validate section structure and ordering."""
    errors: list[str] = []
    sections = profile.structure.sections
    duration_ms = profile.song_identity.duration_ms

    if len(sections) == 0:
        errors.append("Structure must contain at least one section")
        return errors

    # Check monotonicity (start_ms increasing)
    for i in range(1, len(sections)):
        if sections[i].start_ms < sections[i - 1].start_ms:
            errors.append(
                f"Sections not in monotonic order: {sections[i - 1].section_id} "
                f"starts at {sections[i - 1].start_ms}ms, but {sections[i].section_id} "
                f"starts at {sections[i].start_ms}ms"
            )

    # Check for overlaps
    for i in range(len(sections) - 1):
        if sections[i].end_ms > sections[i + 1].start_ms:
            errors.append(
                f"Section overlap detected: {sections[i].section_id} "
                f"[{sections[i].start_ms}-{sections[i].end_ms}ms] overlaps "
                f"{sections[i + 1].section_id} [{sections[i + 1].start_ms}-{sections[i + 1].end_ms}ms]"
            )

    # Check sections within duration
    for section in sections:
        if section.end_ms > duration_ms:
            errors.append(
                f"Section {section.section_id} ends at {section.end_ms}ms, "
                f"exceeds song duration ({duration_ms}ms)"
            )

    return errors


def _validate_energy(profile: AudioProfileModel) -> list[str]:
    """Validate energy profile consistency."""
    errors: list[str] = []
    energy = profile.energy_profile
    duration_ms = profile.song_identity.duration_ms

    # Validate energy curve timestamps are monotonic within each section
    for section_profile in energy.section_profiles:
        timestamps = [point.t_ms for point in section_profile.energy_curve]
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                errors.append(
                    f"Energy curve timestamps not monotonic in section "
                    f"{section_profile.section_id}: {timestamps[i - 1]}ms -> {timestamps[i]}ms"
                )
                break  # Only report once per section

    # Validate energy peaks within duration
    for peak in energy.peaks:
        if peak.end_ms > duration_ms:
            errors.append(
                f"Energy peak [{peak.start_ms}-{peak.end_ms}ms] exceeds "
                f"song duration ({duration_ms}ms)"
            )

    return errors


def _validate_lyric_consistency(profile: AudioProfileModel) -> list[str]:
    """Validate lyric field consistency."""
    errors: list[str] = []
    lyrics = profile.lyric_profile

    # has_timed_words requires has_plain_lyrics
    if lyrics.has_timed_words and not lyrics.has_plain_lyrics:
        errors.append("Lyric inconsistency: has_timed_words=True requires has_plain_lyrics=True")

    # has_phonemes requires has_timed_words
    if lyrics.has_phonemes and not lyrics.has_timed_words:
        errors.append("Lyric inconsistency: has_phonemes=True requires has_timed_words=True")

    return errors
