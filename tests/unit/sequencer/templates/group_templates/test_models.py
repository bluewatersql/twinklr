"""Tests for group template models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.taxonomy import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
)
from twinklr.core.sequencer.templates.group_templates.models import (
    AssetSlot,
    AssetSlotDefaults,
    BackgroundMode,
    GroupConstraints,
    GroupPlanTemplate,
    GroupTemplatePack,
    LayerRecipe,
    MatrixAspect,
    ProjectionParams,
    ProjectionSpec,
    TimingHints,
)


class TestTimingHints:
    """Test TimingHints model."""

    def test_valid_timing_hints(self):
        """Test valid timing hints."""
        hints = TimingHints(bars_min=4, bars_max=8, beats_per_bar=4)
        assert hints.bars_min == 4
        assert hints.bars_max == 8
        assert hints.beats_per_bar == 4
        assert hints.emphasize_downbeats is True

    def test_timing_hints_defaults(self):
        """Test timing hints with defaults."""
        hints = TimingHints()
        assert hints.bars_min is None
        assert hints.bars_max is None
        assert hints.beats_per_bar is None
        assert hints.loop_len_ms is None
        assert hints.emphasize_downbeats is True


class TestGroupConstraints:
    """Test GroupConstraints model."""

    def test_valid_constraints(self):
        """Test valid constraints."""
        constraints = GroupConstraints()
        assert constraints.no_text is True
        assert constraints.low_detail is True
        assert constraints.high_contrast is True
        assert constraints.clean_edges is True
        assert constraints.seam_safe_required is False
        assert constraints.max_layers == 3

    def test_constraints_custom_max_layers(self):
        """Test custom max_layers."""
        constraints = GroupConstraints(max_layers=5)
        assert constraints.max_layers == 5


class TestProjectionParams:
    """Test ProjectionParams model."""

    def test_valid_projection_params(self):
        """Test valid projection params."""
        params = ProjectionParams(center_x=0.3, center_y=0.7, seam_safe=True)
        assert params.center_x == 0.3
        assert params.center_y == 0.7
        assert params.seam_safe is True

    def test_projection_params_defaults(self):
        """Test projection params defaults."""
        params = ProjectionParams()
        assert params.center_x == 0.5
        assert params.center_y == 0.5
        assert params.angle_offset_deg == 0.0
        assert params.radius_bias == 0.5
        assert params.seam_safe is False


class TestProjectionSpec:
    """Test ProjectionSpec model."""

    def test_valid_projection_spec(self):
        """Test valid projection spec."""
        spec = ProjectionSpec(intent=ProjectionIntent.TREE_POLAR)
        assert spec.intent == ProjectionIntent.TREE_POLAR
        assert spec.params is None
        assert spec.warp_hints == []

    def test_projection_spec_with_params(self):
        """Test projection spec with params."""
        params = ProjectionParams(seam_safe=True)
        spec = ProjectionSpec(intent=ProjectionIntent.TREE_POLAR, params=params)
        assert spec.intent == ProjectionIntent.TREE_POLAR
        assert spec.params.seam_safe is True


class TestLayerRecipe:
    """Test LayerRecipe model."""

    def test_valid_layer_recipe(self):
        """Test valid layer recipe."""
        recipe = LayerRecipe(
            layer=LayerRole.BASE,
            motifs=["snowflakes", "stars"],
            visual_intent=GroupVisualIntent.PATTERN,
            motion=[MotionVerb.DRIFT, MotionVerb.TWINKLE],
            density=0.6,
            contrast=0.9,
            color_mode=ColorMode.COOL,
        )
        assert recipe.layer == LayerRole.BASE
        assert recipe.motifs == ["snowflakes", "stars"]
        assert recipe.density == 0.6
        assert recipe.contrast == 0.9

    def test_layer_recipe_defaults(self):
        """Test layer recipe defaults."""
        recipe = LayerRecipe(layer=LayerRole.RHYTHM)
        assert recipe.motifs == []
        assert recipe.visual_intent == GroupVisualIntent.ABSTRACT
        assert recipe.motion == [MotionVerb.NONE]
        assert recipe.density == 0.5
        assert recipe.contrast == 0.8


class TestAssetSlotDefaults:
    """Test AssetSlotDefaults model."""

    def test_valid_asset_slot_defaults(self):
        """Test valid asset slot defaults."""
        defaults = AssetSlotDefaults()
        assert defaults.background == BackgroundMode.OPAQUE
        assert defaults.aspect == MatrixAspect.SQUARE_1_1
        assert defaults.base_size == 256
        assert defaults.even_dimensions is True
        assert defaults.seam_safe is False


class TestAssetSlot:
    """Test AssetSlot model."""

    def test_valid_asset_slot(self):
        """Test valid asset slot."""
        slot = AssetSlot(
            slot_id="bg_plate",
            slot_type=AssetSlotType.BACKGROUND_PLATE,
            required=True,
            preferred_tags=["holiday", "winter"],
        )
        assert slot.slot_id == "bg_plate"
        assert slot.slot_type == AssetSlotType.BACKGROUND_PLATE
        assert slot.required is True
        assert slot.preferred_tags == ["holiday", "winter"]

    def test_asset_slot_invalid_id(self):
        """Test asset slot with invalid ID."""
        with pytest.raises(ValidationError):
            AssetSlot(slot_id="Invalid ID!", slot_type=AssetSlotType.ICON_CUTOUT)


class TestGroupPlanTemplate:
    """Test GroupPlanTemplate model."""

    def test_valid_group_plan_template(self):
        """Test valid group plan template."""
        template = GroupPlanTemplate(
            template_id="gtpl_test_template",
            name="Test Template",
            description="A test template",
            template_type=GroupTemplateType.SECTION_BACKGROUND,
            visual_intent=GroupVisualIntent.SCENE,
            tags=["test", "winter"],
        )
        assert template.template_id == "gtpl_test_template"
        assert template.name == "Test Template"
        assert template.template_type == GroupTemplateType.SECTION_BACKGROUND
        assert template.schema_version == "group_plan_template.v1"

    def test_group_plan_template_with_layer_recipe(self):
        """Test template with layer recipe."""
        recipe = LayerRecipe(layer=LayerRole.BASE, motifs=["snowfall"])
        template = GroupPlanTemplate(
            template_id="gtpl_test",
            name="Test",
            template_type=GroupTemplateType.ACCENT,
            visual_intent=GroupVisualIntent.ABSTRACT,
            layer_recipe=[recipe],
        )
        assert len(template.layer_recipe) == 1
        assert template.layer_recipe[0].layer == LayerRole.BASE

    def test_group_plan_template_with_asset_slots(self):
        """Test template with asset slots."""
        slot = AssetSlot(slot_id="test_slot", slot_type=AssetSlotType.PATTERN_TILE)
        template = GroupPlanTemplate(
            template_id="gtpl_test",
            name="Test",
            template_type=GroupTemplateType.PATTERN_LOOP,
            visual_intent=GroupVisualIntent.PATTERN,
            asset_slots=[slot],
        )
        assert len(template.asset_slots) == 1
        assert template.asset_slots[0].slot_id == "test_slot"


class TestGroupTemplatePack:
    """Test GroupTemplatePack model."""

    def test_valid_group_template_pack(self):
        """Test valid group template pack."""
        template = GroupPlanTemplate(
            template_id="gtpl_test",
            name="Test",
            template_type=GroupTemplateType.ACCENT,
            visual_intent=GroupVisualIntent.ABSTRACT,
        )
        pack = GroupTemplatePack(
            pack_id="pack_test",
            name="Test Pack",
            version="1.0.0",
            templates=[template],
        )
        assert pack.pack_id == "pack_test"
        assert pack.name == "Test Pack"
        assert len(pack.templates) == 1
        assert pack.templates[0].template_id == "gtpl_test"

    def test_group_template_pack_empty_templates(self):
        """Test pack with empty templates list."""
        pack = GroupTemplatePack(
            pack_id="pack_empty",
            name="Empty Pack",
            templates=[],
        )
        assert len(pack.templates) == 0
