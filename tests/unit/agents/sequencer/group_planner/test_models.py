"""Tests for GroupPlanner models."""

from pydantic import ValidationError
import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.group_planner.models import (
    AssetRequest,
    CompilationHints,
    GroupPlan,
    GroupPlanSet,
    LayerPlan,
    SectionGroupPlan,
    SnapRule,
    TemplatePlacement,
    TimeRef,
)
from twinklr.core.agents.taxonomy import (
    BlendMode,
    QuantizeMode,
    SnapMode,
    TimeRefType,
)


class TestTimeRef:
    """Test TimeRef model."""

    def test_marker_based_time_ref(self):
        """Test marker-based time reference."""
        ref = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        assert ref.ref_type == TimeRefType.MARKER
        assert ref.value == 4
        assert ref.marker_type == "bar"

    def test_milliseconds_time_ref(self):
        """Test milliseconds-based time reference."""
        ref = TimeRef(ref_type=TimeRefType.MILLISECONDS, value=5000)
        assert ref.ref_type == TimeRefType.MILLISECONDS
        assert ref.value == 5000


class TestSnapRule:
    """Test SnapRule model."""

    def test_snap_rule_defaults(self):
        """Test snap rule defaults."""
        rule = SnapRule()
        assert rule.snap_mode == SnapMode.NONE
        assert rule.quantize == QuantizeMode.NONE

    def test_snap_rule_custom(self):
        """Test custom snap rule."""
        rule = SnapRule(snap_mode=SnapMode.BOTH, quantize=QuantizeMode.BARS)
        assert rule.snap_mode == SnapMode.BOTH
        assert rule.quantize == QuantizeMode.BARS


class TestTemplatePlacement:
    """Test TemplatePlacement model."""

    def test_valid_template_placement(self):
        """Test valid template placement."""
        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )
        assert placement.placement_id == "p1"
        assert placement.template_id == "gtpl_test"
        assert placement.intensity == 1.0
        assert placement.blend_mode == BlendMode.NORMAL


class TestLayerPlan:
    """Test LayerPlan model."""

    def test_valid_layer_plan(self):
        """Test valid layer plan."""
        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer = LayerPlan(layer_index=0, placements=[placement])
        assert layer.layer_index == 0
        assert len(layer.placements) == 1


class TestSectionGroupPlan:
    """Test SectionGroupPlan model."""

    def test_valid_section_group_plan(self):
        """Test valid section group plan."""
        section = SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=10000)

        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer = LayerPlan(layer_index=0, placements=[placement])
        section_plan = SectionGroupPlan(section=section, layers=[layer])

        assert section_plan.section.section_id == "verse_1"
        assert len(section_plan.layers) == 1

    def test_section_group_plan_duplicate_layers(self):
        """Test that duplicate layer indices are rejected."""
        section = SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=10000)

        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer1 = LayerPlan(layer_index=0, placements=[placement])
        layer2 = LayerPlan(layer_index=0, placements=[placement])  # Duplicate index

        with pytest.raises(ValidationError, match="Layer indices must be unique"):
            SectionGroupPlan(section=section, layers=[layer1, layer2])


class TestAssetRequest:
    """Test AssetRequest model."""

    def test_valid_asset_request(self):
        """Test valid asset request."""
        request = AssetRequest(
            request_id="req_001",
            kind="image_png",
            use_case="matrix_texture",
            style_tags=["holiday", "winter"],
            content_tags=["snowflakes"],
        )
        assert request.request_id == "req_001"
        assert request.kind == "image_png"
        assert request.use_case == "matrix_texture"


class TestCompilationHints:
    """Test CompilationHints model."""

    def test_compilation_hints_defaults(self):
        """Test compilation hints defaults."""
        hints = CompilationHints()
        assert hints.quantize_policy == QuantizeMode.BARS
        assert hints.transition_policy == "crossfade"
        assert hints.layering_policy == "blend"


class TestGroupPlan:
    """Test GroupPlan model."""

    def test_valid_group_plan(self):
        """Test valid group plan."""
        section = SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=10000)

        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer = LayerPlan(layer_index=0, placements=[placement])
        section_plan = SectionGroupPlan(section=section, layers=[layer])

        group_plan = GroupPlan(
            plan_id="plan_001",
            group_id="roofline",
            section_plans=[section_plan],
        )

        assert group_plan.plan_id == "plan_001"
        assert group_plan.group_id == "roofline"
        assert len(group_plan.section_plans) == 1
        assert group_plan.schema_version == "group-plan.v2"


class TestGroupPlanSet:
    """Test GroupPlanSet model."""

    def test_valid_group_plan_set(self):
        """Test valid group plan set."""
        section = SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=10000)

        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer = LayerPlan(layer_index=0, placements=[placement])
        section_plan = SectionGroupPlan(section=section, layers=[layer])

        plan1 = GroupPlan(plan_id="plan_001", group_id="roofline", section_plans=[section_plan])
        plan2 = GroupPlan(plan_id="plan_002", group_id="mega_tree", section_plans=[section_plan])

        plan_set = GroupPlanSet(
            set_id="set_001",
            group_plans=[plan1, plan2],
        )

        assert plan_set.set_id == "set_001"
        assert len(plan_set.group_plans) == 2
        assert plan_set.schema_version == "group-plan-set.v2"

    def test_group_plan_set_duplicate_groups(self):
        """Test that duplicate group IDs are rejected."""
        section = SongSectionRef(section_id="verse_1", name="verse", start_ms=0, end_ms=10000)

        start = TimeRef(ref_type=TimeRefType.MARKER, value=1, marker_type="bar")
        end = TimeRef(ref_type=TimeRefType.MARKER, value=4, marker_type="bar")
        snap = SnapRule()

        placement = TemplatePlacement(
            placement_id="p1",
            start=start,
            end=end,
            snap=snap,
            template_id="gtpl_test",
            preset_id="default",
        )

        layer = LayerPlan(layer_index=0, placements=[placement])
        section_plan = SectionGroupPlan(section=section, layers=[layer])

        plan1 = GroupPlan(plan_id="plan_001", group_id="roofline", section_plans=[section_plan])
        plan2 = GroupPlan(
            plan_id="plan_002", group_id="roofline", section_plans=[section_plan]
        )  # Duplicate

        with pytest.raises(ValidationError, match="Group IDs must be unique"):
            GroupPlanSet(set_id="set_001", group_plans=[plan1, plan2])
