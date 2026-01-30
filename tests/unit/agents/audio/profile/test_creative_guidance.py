"""Tests for CreativeGuidance and PlannerHints models."""

from pydantic import ValidationError
import pytest


def test_contrast_enum():
    """Test Contrast enum values."""
    from twinklr.core.agents.audio.profile.models import Contrast

    assert Contrast.LOW == "LOW"
    assert Contrast.MED == "MED"
    assert Contrast.HIGH == "HIGH"


def test_motion_density_enum():
    """Test MotionDensity enum values."""
    from twinklr.core.agents.audio.profile.models import MotionDensity

    assert MotionDensity.SPARSE == "SPARSE"
    assert MotionDensity.MED == "MED"
    assert MotionDensity.BUSY == "BUSY"


def test_asset_usage_enum():
    """Test AssetUsage enum values."""
    from twinklr.core.agents.audio.profile.models import AssetUsage

    assert AssetUsage.NONE == "NONE"
    assert AssetUsage.SPARSE == "SPARSE"
    assert AssetUsage.HEAVY == "HEAVY"


def test_creative_guidance_valid_full():
    """Test CreativeGuidance with all fields."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        Contrast,
        CreativeGuidance,
        MotionDensity,
    )

    guidance = CreativeGuidance(
        recommended_layer_count=2,
        recommended_contrast=Contrast.HIGH,
        recommended_motion_density=MotionDensity.BUSY,
        recommended_asset_usage=AssetUsage.HEAVY,
        recommended_color_story=["vibrant", "energetic"],
        cautions=["Respect quiet bridge section"],
    )

    assert guidance.recommended_layer_count == 2
    assert guidance.recommended_contrast == Contrast.HIGH
    assert guidance.recommended_motion_density == MotionDensity.BUSY
    assert guidance.recommended_asset_usage == AssetUsage.HEAVY
    assert len(guidance.recommended_color_story) == 2
    assert len(guidance.cautions) == 1


def test_creative_guidance_layer_count_validation():
    """Test CreativeGuidance layer_count must be in [1, 3]."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        Contrast,
        CreativeGuidance,
        MotionDensity,
    )

    # Valid: 1-3
    for count in [1, 2, 3]:
        CreativeGuidance(
            recommended_layer_count=count,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
        )

    # Invalid: < 1
    with pytest.raises(ValidationError):
        CreativeGuidance(
            recommended_layer_count=0,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
        )

    # Invalid: > 3
    with pytest.raises(ValidationError):
        CreativeGuidance(
            recommended_layer_count=4,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
        )


def test_creative_guidance_color_story_max_length():
    """Test CreativeGuidance color_story max 5 items."""
    from twinklr.core.agents.audio.profile.models import (
        AssetUsage,
        Contrast,
        CreativeGuidance,
        MotionDensity,
    )

    # Valid: <= 5
    CreativeGuidance(
        recommended_layer_count=2,
        recommended_contrast=Contrast.MED,
        recommended_motion_density=MotionDensity.MED,
        recommended_asset_usage=AssetUsage.SPARSE,
        recommended_color_story=["warm", "cool", "vibrant", "dark", "light"],
    )

    # Invalid: > 5
    with pytest.raises(ValidationError):
        CreativeGuidance(
            recommended_layer_count=2,
            recommended_contrast=Contrast.MED,
            recommended_motion_density=MotionDensity.MED,
            recommended_asset_usage=AssetUsage.SPARSE,
            recommended_color_story=["a", "b", "c", "d", "e", "f"],
        )


def test_planner_hints_valid():
    """Test PlannerHints with valid data."""
    from twinklr.core.agents.audio.profile.models import PlannerHints

    hints = PlannerHints(
        section_objectives={
            "verse_1": ["Subtle movement"],
            "chorus_1": ["High energy", "Wide sweeps"],
        },
        avoid_patterns=["Repetitive pan/tilt", "Strobing in quiet sections"],
        emphasize_groups=["moving_heads_center"],
    )

    assert len(hints.section_objectives) == 2
    assert "verse_1" in hints.section_objectives
    assert len(hints.avoid_patterns) == 2
    assert len(hints.emphasize_groups) == 1


def test_planner_hints_minimal():
    """Test PlannerHints with minimal/empty fields."""
    from twinklr.core.agents.audio.profile.models import PlannerHints

    hints = PlannerHints()

    assert hints.section_objectives == {}
    assert hints.avoid_patterns == []
    assert hints.emphasize_groups == []


def test_planner_hints_not_frozen():
    """Test PlannerHints is mutable."""
    from twinklr.core.agents.audio.profile.models import PlannerHints

    hints = PlannerHints(avoid_patterns=["Pattern 1"])

    # Should be able to modify
    hints.avoid_patterns.append("Pattern 2")
    assert len(hints.avoid_patterns) == 2


def test_planner_hints_extra_forbid():
    """Test PlannerHints forbids extra fields."""
    from twinklr.core.agents.audio.profile.models import PlannerHints

    with pytest.raises(ValidationError) as exc_info:
        PlannerHints(extra="not allowed")

    assert "extra" in str(exc_info.value).lower()
