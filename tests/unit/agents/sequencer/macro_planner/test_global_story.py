"""Tests for GlobalStory model."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.planning import GlobalStory
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.vocabulary import EnergyTarget

from .conftest import make_motif_spec, make_palette_plan


def _make_global_theme() -> ThemeRef:
    """Create a valid global ThemeRef (SONG scope)."""
    return ThemeRef(
        theme_id="theme.abstract.neon",
        scope=ThemeScope.SONG,
        tags=["motif.geometric"],
    )


def test_global_story_valid():
    """Valid GlobalStory passes validation."""
    story = GlobalStory(
        theme=_make_global_theme(),
        story_notes="Christmas magic with family warmth and holiday cheer",
        motifs=[
            make_motif_spec("sparkle_cascade", "Cascading sparkle effects", [EnergyTarget.HIGH]),
            make_motif_spec("warm_glow", "Warm glowing ambiance", [EnergyTarget.LOW]),
            make_motif_spec("synchronized_pulses", "Synchronized pulsing", [EnergyTarget.MED]),
        ],
        pacing_notes="Build from calm intro to energetic peak, release at end",
        palette_plan=make_palette_plan(),
    )
    assert story.theme is not None
    assert story.theme.theme_id == "theme.abstract.neon"
    assert story.story_notes == "Christmas magic with family warmth and holiday cheer"
    assert len(story.motifs) == 3
    assert story.pacing_notes is not None
    assert story.palette_plan is not None
    assert story.palette_plan.primary.palette_id == "core.christmas_traditional"


def test_too_few_motifs():
    """Less than 3 motifs rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme=_make_global_theme(),
            story_notes="Test story notes that are long enough for validation",
            motifs=[
                make_motif_spec("one"),
                make_motif_spec("two"),
            ],
            pacing_notes="Test pacing notes that are long enough",
            palette_plan=make_palette_plan(),
        )

    # Check that validation error mentions motifs
    assert "motifs" in str(exc_info.value).lower()


def test_extra_fields_forbidden():
    """Extra fields rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme=_make_global_theme(),
            story_notes="Test story notes that are long enough for validation",
            motifs=[
                make_motif_spec("one"),
                make_motif_spec("two"),
                make_motif_spec("three"),
            ],
            pacing_notes="Test pacing notes that are long enough",
            palette_plan=make_palette_plan(),
            extra_field="invalid",
        )

    assert "extra" in str(exc_info.value).lower()


def test_story_notes_too_short():
    """story_notes < 10 characters rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme=_make_global_theme(),
            story_notes="Short",
            motifs=[
                make_motif_spec("one"),
                make_motif_spec("two"),
                make_motif_spec("three"),
            ],
            pacing_notes="Test pacing notes that are long enough",
            palette_plan=make_palette_plan(),
        )

    assert "story_notes" in str(exc_info.value).lower()


def test_pacing_notes_too_short():
    """Pacing notes < 20 characters rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme=_make_global_theme(),
            story_notes="Test story notes that are long enough for validation",
            motifs=[
                make_motif_spec("one"),
                make_motif_spec("two"),
                make_motif_spec("three"),
            ],
            pacing_notes="Short",
            palette_plan=make_palette_plan(),
        )

    assert "pacing_notes" in str(exc_info.value).lower()


def test_palette_plan_required():
    """palette_plan is required."""
    with pytest.raises(ValidationError) as exc_info:
        GlobalStory(
            theme=_make_global_theme(),
            story_notes="Test story notes that are long enough for validation",
            motifs=[
                make_motif_spec("one"),
                make_motif_spec("two"),
                make_motif_spec("three"),
            ],
            pacing_notes="Test pacing notes that are long enough",
            # Missing palette_plan
        )

    assert "palette_plan" in str(exc_info.value).lower()


def test_global_story_serialization():
    """GlobalStory serializes to/from JSON."""
    story = GlobalStory(
        theme=_make_global_theme(),
        story_notes="Christmas magic with family warmth and holiday cheer",
        motifs=[
            make_motif_spec("sparkle_cascade", "Cascading sparkle effects", [EnergyTarget.HIGH]),
            make_motif_spec("warm_glow", "Warm glowing ambiance", [EnergyTarget.LOW]),
            make_motif_spec("synchronized_pulses", "Synchronized pulsing", [EnergyTarget.MED]),
        ],
        pacing_notes="Build from calm intro to energetic peak, release at end",
        palette_plan=make_palette_plan(),
    )

    # Export to JSON
    json_str = story.model_dump_json(indent=2)
    assert "Christmas magic" in json_str
    assert "palette_plan" in json_str

    # Import from JSON
    story2 = GlobalStory.model_validate_json(json_str)
    assert story == story2
