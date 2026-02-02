"""Tests for group template models."""

from pydantic import ValidationError
import pytest

from twinklr.core.sequencer.templates.group.enums import (
    AssetSlotType,
    ColorMode,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRole,
    MotionVerb,
    ProjectionIntent,
    WarpHint,
)
from twinklr.core.sequencer.templates.group.models import (
    AssetSlot,
    AssetSlotDefaults,
    GroupConstraints,
    GroupPlanTemplate,
    LayerRecipe,
    ProjectionParams,
    ProjectionSpec,
    TimingHints,
)


class TestTimingHints:
    """Test TimingHints model."""

    def test_create_with_defaults(self):
        """Test creating TimingHints with default values."""
        hints = TimingHints()
        assert hints.bars_min is None
        assert hints.bars_max is None
        assert hints.emphasize_downbeats is True

    def test_create_with_values(self):
        """Test creating TimingHints with explicit values."""
        hints = TimingHints(bars_min=4, bars_max=16, beats_per_bar=4)
        assert hints.bars_min == 4
        assert hints.bars_max == 16
        assert hints.beats_per_bar == 4

    def test_bars_min_max_validation(self):
        """Test bars_min must be <= bars_max."""
        with pytest.raises(ValidationError, match="bars_min.*must be.*bars_max"):
            TimingHints(bars_min=16, bars_max=4)

    def test_bars_range_constraints(self):
        """Test bars must be between 1 and 256."""
        with pytest.raises(ValidationError):
            TimingHints(bars_min=0)
        with pytest.raises(ValidationError):
            TimingHints(bars_max=257)

    def test_frozen(self):
        """Test TimingHints is frozen."""
        hints = TimingHints(bars_min=4)
        with pytest.raises(ValidationError):
            hints.bars_min = 8


class TestGroupConstraints:
    """Test GroupConstraints model."""

    def test_create_with_defaults(self):
        """Test creating GroupConstraints with default values."""
        constraints = GroupConstraints()
        assert constraints.no_text is True
        assert constraints.low_detail is True
        assert constraints.max_layers == 3

    def test_create_with_values(self):
        """Test creating GroupConstraints with explicit values."""
        constraints = GroupConstraints(
            seam_safe_required=True, max_layers=5, avoid_edges_for_subject=True
        )
        assert constraints.seam_safe_required is True
        assert constraints.max_layers == 5
        assert constraints.avoid_edges_for_subject is True

    def test_max_layers_bounds(self):
        """Test max_layers must be between 1 and 6."""
        with pytest.raises(ValidationError):
            GroupConstraints(max_layers=0)
        with pytest.raises(ValidationError):
            GroupConstraints(max_layers=7)

    def test_frozen(self):
        """Test GroupConstraints is frozen."""
        constraints = GroupConstraints()
        with pytest.raises(ValidationError):
            constraints.no_text = False


class TestProjectionParams:
    """Test ProjectionParams model."""

    def test_create_with_defaults(self):
        """Test creating ProjectionParams with default values."""
        params = ProjectionParams()
        assert params.center_x == 0.5
        assert params.center_y == 0.5
        assert params.angle_offset_deg == 0.0
        assert params.seam_safe is False

    def test_create_with_values(self):
        """Test creating ProjectionParams with explicit values."""
        params = ProjectionParams(center_x=0.3, center_y=0.7, angle_offset_deg=45.0, seam_safe=True)
        assert params.center_x == 0.3
        assert params.center_y == 0.7
        assert params.angle_offset_deg == 45.0
        assert params.seam_safe is True

    def test_center_bounds(self):
        """Test center coordinates must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            ProjectionParams(center_x=-0.1)
        with pytest.raises(ValidationError):
            ProjectionParams(center_y=1.1)

    def test_angle_bounds(self):
        """Test angle must be between -180 and 180."""
        with pytest.raises(ValidationError):
            ProjectionParams(angle_offset_deg=-181.0)
        with pytest.raises(ValidationError):
            ProjectionParams(angle_offset_deg=181.0)


class TestProjectionSpec:
    """Test ProjectionSpec model."""

    def test_create_minimal(self):
        """Test creating ProjectionSpec with minimal data."""
        spec = ProjectionSpec(intent=ProjectionIntent.FLAT)
        assert spec.intent == ProjectionIntent.FLAT
        assert spec.params is None
        assert spec.warp_hints == []

    def test_create_with_params(self):
        """Test creating ProjectionSpec with params."""
        params = ProjectionParams(seam_safe=True)
        spec = ProjectionSpec(intent=ProjectionIntent.POLAR, params=params)
        assert spec.intent == ProjectionIntent.POLAR
        assert spec.params is not None
        assert spec.params.seam_safe is True

    def test_create_with_warp_hints(self):
        """Test creating ProjectionSpec with warp hints."""
        spec = ProjectionSpec(
            intent=ProjectionIntent.FLAT, warp_hints=[WarpHint.SEAM_SAFE, WarpHint.TILE_XY]
        )
        assert len(spec.warp_hints) == 2
        assert WarpHint.SEAM_SAFE in spec.warp_hints


class TestLayerRecipe:
    """Test LayerRecipe model."""

    def test_create_minimal(self):
        """Test creating LayerRecipe with minimal required fields."""
        recipe = LayerRecipe(
            layer=LayerRole.BACKGROUND,
            visual_intent=GroupVisualIntent.ABSTRACT,
            density=0.5,
            contrast=0.7,
            color_mode=ColorMode.MONOCHROME,
        )
        assert recipe.layer == LayerRole.BACKGROUND
        assert recipe.motion == [MotionVerb.NONE]
        assert recipe.motifs == []

    def test_create_with_motion(self):
        """Test creating LayerRecipe with motion verbs."""
        recipe = LayerRecipe(
            layer=LayerRole.FOREGROUND,
            visual_intent=GroupVisualIntent.GEOMETRIC,
            motion=[MotionVerb.PULSE, MotionVerb.FADE],
            density=0.8,
            contrast=0.9,
            color_mode=ColorMode.DICHROME,
        )
        assert len(recipe.motion) == 2
        assert MotionVerb.PULSE in recipe.motion

    def test_density_bounds(self):
        """Test density must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            LayerRecipe(
                layer=LayerRole.BACKGROUND,
                visual_intent=GroupVisualIntent.ABSTRACT,
                density=-0.1,
                contrast=0.5,
                color_mode=ColorMode.MONOCHROME,
            )

    def test_frozen(self):
        """Test LayerRecipe is frozen."""
        recipe = LayerRecipe(
            layer=LayerRole.BACKGROUND,
            visual_intent=GroupVisualIntent.ABSTRACT,
            density=0.5,
            contrast=0.5,
            color_mode=ColorMode.MONOCHROME,
        )
        with pytest.raises(ValidationError):
            recipe.density = 0.8


class TestAssetSlotDefaults:
    """Test AssetSlotDefaults model."""

    def test_create_with_defaults(self):
        """Test creating AssetSlotDefaults with default values."""
        defaults = AssetSlotDefaults()
        assert defaults.background == "transparent"
        assert defaults.aspect == "1:1"
        assert defaults.base_size == 256

    def test_create_with_values(self):
        """Test creating AssetSlotDefaults with explicit values."""
        defaults = AssetSlotDefaults(
            background="opaque", aspect="16:9", base_size=512, seam_safe=True
        )
        assert defaults.background == "opaque"
        assert defaults.aspect == "16:9"
        assert defaults.base_size == 512
        assert defaults.seam_safe is True

    def test_base_size_positive(self):
        """Test base_size must be positive."""
        with pytest.raises(ValidationError):
            AssetSlotDefaults(base_size=0)


class TestAssetSlot:
    """Test AssetSlot model."""

    def test_create_minimal(self):
        """Test creating AssetSlot with minimal required fields."""
        slot = AssetSlot(slot_id="background_01", slot_type=AssetSlotType.PNG_OPAQUE)
        assert slot.slot_id == "background_01"
        assert slot.slot_type == AssetSlotType.PNG_OPAQUE
        assert slot.required is True
        assert slot.preferred_tags == []

    def test_create_with_tags(self):
        """Test creating AssetSlot with preferred tags."""
        slot = AssetSlot(
            slot_id="bg_night_sky",
            slot_type=AssetSlotType.PNG_OPAQUE,
            preferred_tags=["night", "sky", "stars"],
            prompt_hint="Night sky with scattered stars",
        )
        assert len(slot.preferred_tags) == 3
        assert "night" in slot.preferred_tags
        assert slot.prompt_hint is not None

    def test_slot_id_pattern(self):
        """Test slot_id must match pattern."""
        # Valid IDs
        AssetSlot(slot_id="bg_01", slot_type=AssetSlotType.PNG_OPAQUE)
        AssetSlot(slot_id="texture-tile.1", slot_type=AssetSlotType.PNG_TILE)

        # Invalid IDs
        with pytest.raises(ValidationError):
            AssetSlot(slot_id="BG_01", slot_type=AssetSlotType.PNG_OPAQUE)  # uppercase
        with pytest.raises(ValidationError):
            AssetSlot(slot_id="bg 01", slot_type=AssetSlotType.PNG_OPAQUE)  # space

    def test_frozen(self):
        """Test AssetSlot is frozen."""
        slot = AssetSlot(slot_id="test", slot_type=AssetSlotType.PNG_OPAQUE)
        with pytest.raises(ValidationError):
            slot.required = False


class TestGroupPlanTemplate:
    """Test GroupPlanTemplate model."""

    def test_create_minimal(self):
        """Test creating GroupPlanTemplate with minimal required fields."""
        template = GroupPlanTemplate(
            template_id="test_template",
            name="Test Template",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        )
        assert template.template_id == "test_template"
        assert template.name == "Test Template"
        assert template.template_type == GroupTemplateType.BASE
        assert template.schema_version == "group_plan_template.v1"
        assert template.layer_recipe == []
        assert template.asset_slots == []

    def test_create_complete(self):
        """Test creating complete GroupPlanTemplate."""
        template = GroupPlanTemplate(
            template_id="gtpl_base_starfield_slow",
            name="Starfield - Slow",
            description="Slow random twinkling stars",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            tags=["starfield", "twinkle", "calm"],
            projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            timing=TimingHints(bars_min=4, bars_max=32),
            constraints=GroupConstraints(max_layers=2),
            layer_recipe=[
                LayerRecipe(
                    layer=LayerRole.BACKGROUND,
                    motifs=["stars", "dots"],
                    visual_intent=GroupVisualIntent.ABSTRACT,
                    motion=[MotionVerb.TWINKLE],
                    density=0.3,
                    contrast=0.6,
                    color_mode=ColorMode.MONOCHROME,
                )
            ],
            template_version="1.0.0",
            author="twinklr",
        )
        assert template.template_id == "gtpl_base_starfield_slow"
        assert len(template.layer_recipe) == 1
        assert len(template.tags) == 3

    def test_template_id_pattern(self):
        """Test template_id must match pattern."""
        # Valid IDs
        GroupPlanTemplate(
            template_id="test123",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
        )

        # Invalid IDs
        with pytest.raises(ValidationError):
            GroupPlanTemplate(
                template_id="Test_123",  # uppercase
                name="Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            )

    def test_layer_recipe_exceeds_max_layers(self):
        """Test validation fails if layer_recipe exceeds max_layers."""
        with pytest.raises(ValidationError, match="layer_recipe count.*exceeds.*max_layers"):
            GroupPlanTemplate(
                template_id="test",
                name="Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                constraints=GroupConstraints(max_layers=1),
                layer_recipe=[
                    LayerRecipe(
                        layer=LayerRole.BACKGROUND,
                        visual_intent=GroupVisualIntent.ABSTRACT,
                        density=0.5,
                        contrast=0.5,
                        color_mode=ColorMode.MONOCHROME,
                    ),
                    LayerRecipe(
                        layer=LayerRole.FOREGROUND,
                        visual_intent=GroupVisualIntent.ABSTRACT,
                        density=0.5,
                        contrast=0.5,
                        color_mode=ColorMode.MONOCHROME,
                    ),
                ],
            )

    def test_seam_safe_validation(self):
        """Test seam_safe_required requires seam-safe hints."""
        with pytest.raises(ValidationError, match="seam_safe_required.*lacks seam-safe hints"):
            GroupPlanTemplate(
                template_id="test",
                name="Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                constraints=GroupConstraints(seam_safe_required=True),
            )

        # Should pass with seam-safe hint
        GroupPlanTemplate(
            template_id="test",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            projection=ProjectionSpec(
                intent=ProjectionIntent.FLAT, warp_hints=[WarpHint.SEAM_SAFE]
            ),
            constraints=GroupConstraints(seam_safe_required=True),
        )

    def test_duplicate_slot_ids(self):
        """Test validation fails with duplicate slot_ids."""
        with pytest.raises(ValidationError, match="Duplicate slot_id"):
            GroupPlanTemplate(
                template_id="test",
                name="Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                asset_slots=[
                    AssetSlot(slot_id="bg_01", slot_type=AssetSlotType.PNG_OPAQUE),
                    AssetSlot(slot_id="bg_01", slot_type=AssetSlotType.PNG_TILE),
                ],
            )

    def test_tags_normalized(self):
        """Test tags are normalized and deduped."""
        template = GroupPlanTemplate(
            template_id="test",
            name="Test",
            template_type=GroupTemplateType.BASE,
            visual_intent=GroupVisualIntent.ABSTRACT,
            projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
            tags=["Starfield", "TWINKLE", "starfield", "  calm  "],
        )
        # Should be lowercase, sorted, deduped
        assert template.tags == ["calm", "starfield", "twinkle"]

    def test_extra_forbid(self):
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError):
            GroupPlanTemplate(
                template_id="test",
                name="Test",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                projection=ProjectionSpec(intent=ProjectionIntent.FLAT),
                unknown_field="value",  # type: ignore
            )
