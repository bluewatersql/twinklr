"""Tests for GlobalStory model."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.sequencer.macro_planner.models import GlobalStory


def test_global_story_valid():
    """Valid GlobalStory passes validation."""
    story = GlobalStory(
        theme="Christmas magic with family warmth",
        motifs=["sparkle cascade", "warm glow", "synchronized pulses"],
        pacing_notes="Build from calm intro to energetic peak, release at end",
        color_story="Warm white → red/green accents → full spectrum peak",
    )
    assert story.theme is not None
    assert story.theme == "Christmas magic with family warmth"
    assert len(story.motifs) == 3
    assert story.pacing_notes is not None
    assert story.color_story is not None


def test_too_few_motifs():
    """Less than 3 motifs rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme="Test theme",
            motifs=["one", "two"],
            pacing_notes="Test pacing notes that are long enough",
            color_story="Test color story",
        )

    # Check that validation error mentions motifs
    assert "motifs" in str(exc_info.value).lower()


def test_extra_fields_forbidden():
    """Extra fields rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme="Test theme",
            motifs=["one", "two", "three"],
            pacing_notes="Test pacing notes that are long enough",
            color_story="Test color story",
            extra_field="invalid",
        )

    assert "extra" in str(exc_info.value).lower()


def test_theme_too_short():
    """Theme < 10 characters rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme="Short",
            motifs=["one", "two", "three"],
            pacing_notes="Test pacing notes that are long enough",
            color_story="Test color story",
        )

    assert "theme" in str(exc_info.value).lower()


def test_pacing_notes_too_short():
    """Pacing notes < 20 characters rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme="Test theme",
            motifs=["one", "two", "three"],
            pacing_notes="Short",
            color_story="Test color story",
        )

    assert "pacing_notes" in str(exc_info.value).lower()


def test_color_story_too_short():
    """Color story < 10 characters rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme="Test theme",
            motifs=["one", "two", "three"],
            pacing_notes="Test pacing notes that are long enough",
            color_story="Short",
        )

    assert "color_story" in str(exc_info.value).lower()


def test_global_story_serialization():
    """GlobalStory serializes to/from JSON."""
    story = GlobalStory(
        theme="Christmas magic with family warmth",
        motifs=["sparkle cascade", "warm glow", "synchronized pulses"],
        pacing_notes="Build from calm intro to energetic peak, release at end",
        color_story="Warm white → red/green accents → full spectrum peak",
    )

    # Export to JSON
    json_str = story.model_dump_json(indent=2)
    assert "Christmas magic" in json_str

    # Import from JSON
    story2 = GlobalStory.model_validate_json(json_str)
    assert story == story2
