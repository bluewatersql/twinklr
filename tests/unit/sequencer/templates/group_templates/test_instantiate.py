"""Tests for template instantiation functionality."""

from __future__ import annotations

from twinklr.core.sequencer.templates.group_templates.instantiate import (
    AssetRequest,
    GroupPlanLayer,
    GroupPlanSkeleton,
    instantiate_group_template,
)
from twinklr.core.sequencer.templates.group_templates.models import (
    AssetSlot,
    AssetSlotDefaults,
    AssetSlotType,
    BackgroundMode,
    ColorMode,
    GroupConstraints,
    GroupPlanTemplate,
    GroupTemplateType,
    GroupVisualIntent,
    LayerRecipe,
    LayerRole,
    MatrixAspect,
    MotionVerb,
    ProjectionIntent,
    ProjectionParams,
    ProjectionSpec,
)


def test_instantiate_basic_template():
    """Test basic template instantiation without asset slots."""
    template = GroupPlanTemplate(
        template_id="test_basic",
        name="Test Basic",
        template_type=GroupTemplateType.SECTION_BACKGROUND,
        visual_intent=GroupVisualIntent.SCENE,
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["snowflakes", "winter"],
                visual_intent=GroupVisualIntent.PATTERN,
                motion=[MotionVerb.DRIFT],
                density=0.5,
                contrast=0.8,
                color_mode=ColorMode.COOL,
                notes="Gentle background",
            )
        ],
    )

    skeleton = instantiate_group_template(template, "matrix_1")

    assert skeleton.schema_version == "group_plan_skeleton.v1"
    assert skeleton.template_id == "test_basic"
    assert skeleton.group_id == "matrix_1"
    assert len(skeleton.layers) == 1
    assert len(skeleton.asset_requests) == 0

    # Check layer conversion
    layer = skeleton.layers[0]
    assert layer.layer == LayerRole.BASE
    assert layer.motifs == ["snowflakes", "winter"]
    assert layer.motions == ["drift"]
    assert layer.notes == "Gentle background"


def test_instantiate_template_with_multiple_layers():
    """Test template instantiation with multiple layer recipes."""
    template = GroupPlanTemplate(
        template_id="test_multi_layer",
        name="Test Multi Layer",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        layer_recipe=[
            LayerRecipe(
                layer=LayerRole.BASE,
                motifs=["background"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.NONE],
            ),
            LayerRecipe(
                layer=LayerRole.RHYTHM,
                motifs=["pulse", "beat"],
                visual_intent=GroupVisualIntent.ABSTRACT,
                motion=[MotionVerb.PULSE, MotionVerb.TWINKLE],
            ),
            LayerRecipe(
                layer=LayerRole.HIGHLIGHT,
                motifs=["accent"],
                visual_intent=GroupVisualIntent.ICON,
                motion=[MotionVerb.NONE],
            ),
        ],
    )

    skeleton = instantiate_group_template(template, "matrix_1")

    assert len(skeleton.layers) == 3
    assert skeleton.layers[0].layer == LayerRole.BASE
    assert skeleton.layers[1].layer == LayerRole.RHYTHM
    assert skeleton.layers[2].layer == LayerRole.HIGHLIGHT
    assert skeleton.layers[1].motions == ["pulse", "twinkle"]


def test_instantiate_template_with_asset_slots():
    """Test template instantiation with asset slot generation."""
    template = GroupPlanTemplate(
        template_id="test_with_assets",
        name="Test With Assets",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        asset_slots=[
            AssetSlot(
                slot_id="bg_plate",
                slot_type=AssetSlotType.BACKGROUND_PLATE,
                required=True,
                preferred_tags=["christmas", "background"],
                prompt_hint="Cozy village scene",
                defaults=AssetSlotDefaults(
                    background=BackgroundMode.OPAQUE,
                    aspect=MatrixAspect.WIDE_2_1,
                    base_size=256,
                ),
            ),
            AssetSlot(
                slot_id="icon_cutout",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=False,
                preferred_tags=["santa", "character"],
            ),
        ],
    )

    skeleton = instantiate_group_template(template, "matrix_main")

    assert len(skeleton.asset_requests) == 2

    # Check first asset request
    req1 = skeleton.asset_requests[0]
    assert req1.request_id == "matrix_main:test_with_assets:bg_plate:0"
    assert req1.slot_id == "bg_plate"
    assert req1.slot_type == "background_plate"
    assert req1.preferred_tags == ["christmas", "background"]
    assert req1.prompt_hint == "Cozy village scene"
    assert req1.defaults["background"] == "opaque"
    assert req1.defaults["aspect"] == "2:1"
    assert req1.defaults["base_size"] == 256

    # Check second asset request
    req2 = skeleton.asset_requests[1]
    assert req2.request_id == "matrix_main:test_with_assets:icon_cutout:1"
    assert req2.slot_id == "icon_cutout"
    assert req2.slot_type == "icon_cutout"
    assert req2.preferred_tags == ["santa", "character"]
    assert req2.prompt_hint is None


def test_instantiate_template_projection_preservation():
    """Test that projection settings are preserved in skeleton."""
    template = GroupPlanTemplate(
        template_id="test_projection",
        name="Test Projection",
        template_type=GroupTemplateType.PATTERN_LOOP,
        visual_intent=GroupVisualIntent.PATTERN,
        projection=ProjectionSpec(
            intent=ProjectionIntent.TREE_POLAR,
            params=ProjectionParams(
                seam_safe=True, center_x=0.5, center_y=0.5, angle_offset_deg=45.0
            ),
        ),
    )

    skeleton = instantiate_group_template(template, "tree_mega")

    assert skeleton.projection["intent"] == "proj_tree_polar"
    assert skeleton.projection["params"]["seam_safe"] is True
    assert skeleton.projection["params"]["center_x"] == 0.5
    assert skeleton.projection["params"]["angle_offset_deg"] == 45.0


def test_instantiate_template_constraints_preservation():
    """Test that constraints are preserved in skeleton."""
    template = GroupPlanTemplate(
        template_id="test_constraints",
        name="Test Constraints",
        template_type=GroupTemplateType.SECTION_BACKGROUND,
        visual_intent=GroupVisualIntent.SCENE,
        constraints=GroupConstraints(
            no_text=True,
            low_detail=True,
            high_contrast=True,
            clean_edges=True,
            seam_safe_required=True,
            avoid_edges_for_subject=True,
            max_layers=5,
        ),
    )

    skeleton = instantiate_group_template(template, "matrix_1")

    assert skeleton.constraints["no_text"] is True
    assert skeleton.constraints["low_detail"] is True
    assert skeleton.constraints["high_contrast"] is True
    assert skeleton.constraints["seam_safe_required"] is True
    assert skeleton.constraints["max_layers"] == 5


def test_instantiate_template_empty_layer_recipe():
    """Test template instantiation with no layer recipes."""
    template = GroupPlanTemplate(
        template_id="test_empty",
        name="Test Empty",
        template_type=GroupTemplateType.ACCENT,
        visual_intent=GroupVisualIntent.ABSTRACT,
        layer_recipe=[],
    )

    skeleton = instantiate_group_template(template, "matrix_1")

    assert len(skeleton.layers) == 0
    assert skeleton.template_id == "test_empty"
    assert skeleton.group_id == "matrix_1"


def test_instantiate_template_group_id_variations():
    """Test that different group IDs produce unique asset request IDs."""
    template = GroupPlanTemplate(
        template_id="test_template",
        name="Test",
        template_type=GroupTemplateType.SECTION_FEATURE,
        visual_intent=GroupVisualIntent.ICON,
        asset_slots=[
            AssetSlot(
                slot_id="test_slot",
                slot_type=AssetSlotType.ICON_CUTOUT,
                required=True,
            )
        ],
    )

    skeleton1 = instantiate_group_template(template, "group_a")
    skeleton2 = instantiate_group_template(template, "group_b")

    assert skeleton1.asset_requests[0].request_id.startswith("group_a:")
    assert skeleton2.asset_requests[0].request_id.startswith("group_b:")
    assert skeleton1.asset_requests[0].request_id != skeleton2.asset_requests[0].request_id


def test_group_plan_skeleton_schema():
    """Test GroupPlanSkeleton model validation."""
    skeleton = GroupPlanSkeleton(
        template_id="test",
        group_id="group1",
        projection={"intent": "proj_flat"},
        constraints={"no_text": True},
        layers=[GroupPlanLayer(layer=LayerRole.BASE, motifs=["test"], motions=["none"])],
        asset_requests=[
            AssetRequest(
                request_id="req1",
                slot_id="slot1",
                slot_type="background_plate",
                preferred_tags=["tag1"],
            )
        ],
    )

    assert skeleton.schema_version == "group_plan_skeleton.v1"
    assert skeleton.template_id == "test"
    assert skeleton.group_id == "group1"
    assert len(skeleton.layers) == 1
    assert len(skeleton.asset_requests) == 1


def test_asset_request_model():
    """Test AssetRequest model directly."""
    request = AssetRequest(
        request_id="test:template:slot:0",
        slot_id="test_slot",
        slot_type="icon_cutout",
        preferred_tags=["christmas", "santa"],
        prompt_hint="Santa waving",
        defaults={"background": "transparent", "size": 256},
    )

    assert request.request_id == "test:template:slot:0"
    assert request.slot_id == "test_slot"
    assert request.slot_type == "icon_cutout"
    assert len(request.preferred_tags) == 2
    assert request.prompt_hint == "Santa waving"
    assert request.defaults["background"] == "transparent"


def test_group_plan_layer_model():
    """Test GroupPlanLayer model directly."""
    layer = GroupPlanLayer(
        layer=LayerRole.RHYTHM,
        motifs=["pulse", "beat"],
        motions=["pulse", "twinkle"],
        notes="Sync to music",
    )

    assert layer.layer == LayerRole.RHYTHM
    assert len(layer.motifs) == 2
    assert len(layer.motions) == 2
    assert layer.notes == "Sync to music"
