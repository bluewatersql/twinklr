"""Tests for GroupPlanner taxonomy enums."""

from twinklr.core.agents.taxonomy import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    MotionVerb,
    ProjectionIntent,
    QuantizeMode,
    SnapMode,
    TimeRefType,
    WarpHint,
)


class TestGroupPlannerEnums:
    """Test GroupPlanner-specific taxonomy enums."""

    def test_group_template_type_values(self):
        """Test GroupTemplateType enum values."""
        assert GroupTemplateType.SECTION_BACKGROUND.value == "section_background"
        assert GroupTemplateType.SECTION_FEATURE.value == "section_feature"
        assert GroupTemplateType.TRANSITION.value == "transition"
        assert GroupTemplateType.ACCENT.value == "accent"
        assert GroupTemplateType.PATTERN_LOOP.value == "pattern_loop"

    def test_group_visual_intent_values(self):
        """Test GroupVisualIntent enum values."""
        assert GroupVisualIntent.SCENE.value == "scene"
        assert GroupVisualIntent.ICON.value == "icon"
        assert GroupVisualIntent.PATTERN.value == "pattern"
        assert GroupVisualIntent.TEXT.value == "text"
        assert GroupVisualIntent.ABSTRACT.value == "abstract"

    def test_projection_intent_values(self):
        """Test ProjectionIntent enum values."""
        assert ProjectionIntent.FLAT.value == "proj_flat"
        assert ProjectionIntent.TREE_POLAR.value == "proj_tree_polar"
        assert ProjectionIntent.TREE_RADIAL_FOCUS.value == "proj_tree_radial_focus"
        assert ProjectionIntent.TREE_SPIRAL_BIAS.value == "proj_tree_spiral_bias"
        assert ProjectionIntent.TREE_BAND_SAFE.value == "proj_tree_band_safe"

    def test_warp_hint_values(self):
        """Test WarpHint enum values."""
        assert WarpHint.SKEW_LR.value == "warp_skew_lr"
        assert WarpHint.SKEW_UD.value == "warp_skew_ud"
        assert WarpHint.RADIAL_WARP_OK.value == "warp_radial_warp_ok"
        assert WarpHint.CENTER_ANCHOR.value == "warp_center_anchor"

    def test_motion_verb_values(self):
        """Test MotionVerb enum values."""
        assert MotionVerb.NONE.value == "none"
        assert MotionVerb.DRIFT.value == "drift"
        assert MotionVerb.FALL.value == "fall"
        assert MotionVerb.TWINKLE.value == "twinkle"
        assert MotionVerb.PULSE.value == "pulse"
        assert MotionVerb.WIPE.value == "wipe"
        assert MotionVerb.SWEEP.value == "sweep"
        assert MotionVerb.ROTATE.value == "rotate"
        assert MotionVerb.SPIRAL.value == "spiral"

    def test_color_mode_values(self):
        """Test ColorMode enum values."""
        assert ColorMode.TRADITIONAL.value == "traditional"
        assert ColorMode.WARM.value == "warm"
        assert ColorMode.COOL.value == "cool"
        assert ColorMode.LIMITED.value == "limited"
        assert ColorMode.MONO.value == "mono"

    def test_asset_slot_type_values(self):
        """Test AssetSlotType enum values."""
        assert AssetSlotType.BACKGROUND_PLATE.value == "background_plate"
        assert AssetSlotType.ICON_CUTOUT.value == "icon_cutout"
        assert AssetSlotType.PATTERN_TILE.value == "pattern_tile"
        assert AssetSlotType.MASK.value == "mask"
        assert AssetSlotType.TEXT_PLATE.value == "text_plate"

    def test_time_ref_type_values(self):
        """Test TimeRefType enum values."""
        assert TimeRefType.MARKER.value == "marker"
        assert TimeRefType.MILLISECONDS.value == "milliseconds"

    def test_snap_mode_values(self):
        """Test SnapMode enum values."""
        assert SnapMode.NONE.value == "none"
        assert SnapMode.START.value == "start"
        assert SnapMode.END.value == "end"
        assert SnapMode.BOTH.value == "both"
        assert SnapMode.STRETCH.value == "stretch"

    def test_quantize_mode_values(self):
        """Test QuantizeMode enum values."""
        assert QuantizeMode.NONE.value == "none"
        assert QuantizeMode.BARS.value == "bars"
        assert QuantizeMode.BEATS.value == "beats"
        assert QuantizeMode.EIGHTHS.value == "eighths"
        assert QuantizeMode.SIXTEENTHS.value == "sixteenths"
