"""Tests for the motif-primary effect resolver."""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.display.composition.effect_resolver import (
    ResolvedEffect,
    resolve_effect,
)
from twinklr.core.sequencer.vocabulary.motion import MotionVerb
from twinklr.core.sequencer.vocabulary.visual import VisualDepth

# ------------------------------------------------------------------
# Tier 1: motif → effect type
# ------------------------------------------------------------------


class TestMotifResolution:
    """Motifs select the primary xLights effect type."""

    def test_radial_rays_to_fan(self) -> None:
        result = resolve_effect(
            motifs=["radial_rays"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        assert result.effect_type == "Fan"

    def test_snowflakes_to_snowflakes(self) -> None:
        result = resolve_effect(
            motifs=["snowflakes"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.effect_type == "Snowflakes"

    def test_sparkles_to_twinkle(self) -> None:
        result = resolve_effect(
            motifs=["sparkles", "hit"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        assert result.effect_type == "Twinkle"

    def test_fire_to_fire(self) -> None:
        result = resolve_effect(
            motifs=["fire"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.effect_type == "Fire"

    def test_light_trails_to_meteors(self) -> None:
        result = resolve_effect(
            motifs=["light_trails"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.effect_type == "Meteors"

    def test_first_recognised_motif_wins(self) -> None:
        """When multiple motifs, first match determines effect type."""
        result = resolve_effect(
            motifs=["spiral", "wash", "abstract"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.effect_type == "Spirals"

    def test_unrecognised_motifs_raises(self) -> None:
        """No fallback — unrecognised motifs raise ValueError."""
        with pytest.raises(ValueError, match="No recognised motif"):
            resolve_effect(
                motifs=["disco_ball", "laser_beam"],
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.5,
                visual_depth=VisualDepth.BACKGROUND,
            )

    def test_empty_motifs_raises(self) -> None:
        """Empty motif list raises."""
        with pytest.raises(ValueError, match="No recognised motif"):
            resolve_effect(
                motifs=[],
                motion=[MotionVerb.NONE],
                density=0.5,
                contrast=0.5,
                visual_depth=VisualDepth.BACKGROUND,
            )

    def test_wash_motif_to_color_wash(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.effect_type == "Color Wash"

    def test_chevrons_to_marquee(self) -> None:
        result = resolve_effect(
            motifs=["chevrons"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.effect_type == "Marquee"

    def test_chase_motif_to_singlestrand(self) -> None:
        result = resolve_effect(
            motifs=["chase"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.effect_type == "SingleStrand"


# ------------------------------------------------------------------
# Tier 2: motion verb → behaviour curves
# ------------------------------------------------------------------


class TestMotionBehavior:
    """Motion verbs modulate effect behavior via curves and params."""

    def test_pulse_generates_brightness_curve(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[MotionVerb.PULSE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert "Brightness" in result.value_curves
        assert "Active=TRUE" in result.value_curves["Brightness"]

    def test_shimmer_generates_speed_curve(self) -> None:
        result = resolve_effect(
            motifs=["sparkles"],
            motion=[MotionVerb.SHIMMER],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert "Speed" in result.value_curves

    def test_none_produces_no_curves(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.value_curves == {}

    def test_strobe_sets_param_override(self) -> None:
        result = resolve_effect(
            motifs=["sparkles"],
            motion=[MotionVerb.STROBE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.ACCENT,
        )
        assert result.parameters.get("strobe") is True

    def test_flip_sets_reverse(self) -> None:
        result = resolve_effect(
            motifs=["spiral"],
            motion=[MotionVerb.FLIP],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.parameters.get("reverse") is True

    def test_empty_motion_treated_as_none(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.value_curves == {}


# ------------------------------------------------------------------
# Tier 3: density/contrast scaling
# ------------------------------------------------------------------


class TestDensityContrast:
    """Density and contrast scale quantity and intensity parameters."""

    def test_high_density_twinkle_high_count(self) -> None:
        result = resolve_effect(
            motifs=["sparkles"],
            motion=[MotionVerb.NONE],
            density=1.0,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        assert result.parameters["count"] == 25  # max for Twinkle

    def test_low_density_twinkle_low_count(self) -> None:
        result = resolve_effect(
            motifs=["sparkles"],
            motion=[MotionVerb.NONE],
            density=0.0,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        assert result.parameters["count"] == 3  # min for Twinkle

    def test_high_contrast_color_wash_high_speed(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=1.0,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.parameters["speed"] == 100  # max for Color Wash

    def test_mid_density_fan_mid_blades(self) -> None:
        result = resolve_effect(
            motifs=["radial_rays"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        # density=0.5 → (4 + 16*0.5) = 12 blades
        assert result.parameters["num_blades"] == 12


# ------------------------------------------------------------------
# Buffer style
# ------------------------------------------------------------------


class TestBufferStyle:
    """Centered effects get overlay buffer style."""

    def test_fan_gets_centered(self) -> None:
        result = resolve_effect(
            motifs=["radial_rays"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.FOREGROUND,
        )
        assert result.buffer_style == "Overlay - Centered"

    def test_ripple_gets_centered(self) -> None:
        result = resolve_effect(
            motifs=["ripple"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.MIDGROUND,
        )
        assert result.buffer_style == "Overlay - Centered"

    def test_wash_gets_default(self) -> None:
        result = resolve_effect(
            motifs=["wash"],
            motion=[MotionVerb.NONE],
            density=0.5,
            contrast=0.5,
            visual_depth=VisualDepth.BACKGROUND,
        )
        assert result.buffer_style == "Per Model Default"


# ------------------------------------------------------------------
# Output model
# ------------------------------------------------------------------


class TestResolvedEffect:
    """ResolvedEffect is a frozen dataclass."""

    def test_is_frozen(self) -> None:
        r = ResolvedEffect(effect_type="On")
        with pytest.raises(AttributeError):
            r.effect_type = "Off"  # type: ignore[misc]
