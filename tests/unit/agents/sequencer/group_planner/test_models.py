"""Tests for GroupPlanner models.

Tests focus on model contracts and validation rules, not basic Pydantic behavior.
"""

from __future__ import annotations

import pytest

from twinklr.core.sequencer.planning import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models import (
    CoordinationConfig,
    CoordinationPlan,
    DisplayGraph,
    DisplayGroup,
    GroupPlacement,
    PlacementWindow,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    SpillPolicy,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME


class TestTimeRef:
    """Tests for TimeRef model validation contracts."""

    def test_bar_beat_requires_bar_and_beat(self) -> None:
        """BAR_BEAT kind requires bar and beat fields."""
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1)
        assert ref.bar == 1
        assert ref.beat == 1
        assert ref.offset_ms is None

    def test_bar_beat_with_optional_offset(self) -> None:
        """BAR_BEAT can have optional offset_ms for fine nudge."""
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=4, beat=2, offset_ms=50)
        assert ref.bar == 4
        assert ref.beat == 2
        assert ref.offset_ms == 50

    def test_bar_beat_with_beat_frac(self) -> None:
        """BAR_BEAT supports beat_frac for sub-beat timing."""
        ref = TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1, beat_frac=0.5)
        assert ref.beat_frac == 0.5

    def test_ms_requires_offset_ms(self) -> None:
        """MS kind requires offset_ms field."""
        ref = TimeRef(kind=TimeRefKind.MS, offset_ms=5000)
        assert ref.offset_ms == 5000
        assert ref.bar is None
        assert ref.beat is None

    def test_bar_beat_missing_bar_raises(self) -> None:
        """BAR_BEAT without bar should raise validation error."""
        with pytest.raises(ValueError, match=r"bar.*required"):
            TimeRef(kind=TimeRefKind.BAR_BEAT, beat=1)

    def test_bar_beat_missing_beat_raises(self) -> None:
        """BAR_BEAT without beat should raise validation error."""
        with pytest.raises(ValueError, match=r"beat.*required"):
            TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1)

    def test_ms_missing_offset_raises(self) -> None:
        """MS without offset_ms should raise validation error."""
        with pytest.raises(ValueError, match=r"offset_ms.*required"):
            TimeRef(kind=TimeRefKind.MS)

    def test_ms_with_bar_raises(self) -> None:
        """MS kind with bar field should raise validation error."""
        with pytest.raises(ValueError, match=r"bar.*None"):
            TimeRef(kind=TimeRefKind.MS, offset_ms=5000, bar=1)


class TestDisplayGraph:
    """Tests for DisplayGraph model."""

    def test_groups_by_role_computed(self) -> None:
        """groups_by_role returns mapping of role -> group_ids."""
        graph = DisplayGraph(
            display_id="test_display",
            display_name="Test Display",
            groups=[
                DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
                DisplayGroup(group_id="HERO_2", role="HERO", display_name="Hero 2"),
                DisplayGroup(group_id="ARCHES_1", role="ARCHES", display_name="Arches"),
            ],
        )
        by_role = graph.groups_by_role
        assert by_role["HERO"] == ["HERO_1", "HERO_2"]
        assert by_role["ARCHES"] == ["ARCHES_1"]

    def test_get_group_by_id(self) -> None:
        """get_group returns group by ID or None."""
        graph = DisplayGraph(
            display_id="test_display",
            display_name="Test Display",
            groups=[
                DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
            ],
        )
        assert graph.get_group("HERO_1") is not None
        assert graph.get_group("HERO_1").display_name == "Hero 1"
        assert graph.get_group("NONEXISTENT") is None

    def test_requires_at_least_one_group(self) -> None:
        """DisplayGraph must have at least one group."""
        with pytest.raises(ValueError):
            DisplayGraph(
                display_id="empty",
                display_name="Empty",
                groups=[],
            )


class TestTemplateCatalog:
    """Tests for lightweight TemplateCatalog."""

    def test_has_template(self) -> None:
        """has_template checks if template_id exists."""
        catalog = TemplateCatalog(
            entries=[
                TemplateInfo(
                    template_id="gtpl_bg_starfield",
                    version="1.0",
                    name="Starfield Background",
                    template_type=GroupTemplateType.BASE,
                    visual_intent=GroupVisualIntent.ABSTRACT,
                    tags=(),
                ),
            ]
        )
        assert catalog.has_template("gtpl_bg_starfield") is True
        assert catalog.has_template("nonexistent") is False

    def test_get_entry(self) -> None:
        """get_entry returns entry or None."""
        catalog = TemplateCatalog(
            entries=[
                TemplateInfo(
                    template_id="gtpl_accent_bell",
                    version="1.0",
                    name="Bell Accent",
                    template_type=GroupTemplateType.ACCENT,
                    visual_intent=GroupVisualIntent.TEXTURE,
                    tags=(),
                ),
            ]
        )
        entry = catalog.get_entry("gtpl_accent_bell")
        assert entry is not None
        assert entry.name == "Bell Accent"
        assert catalog.get_entry("nonexistent") is None

    def test_list_by_lane(self) -> None:
        """list_by_lane filters entries by lane compatibility."""
        catalog = TemplateCatalog(
            entries=[
                TemplateInfo(
                    template_id="gtpl_bg_1",
                    version="1.0",
                    name="BG 1",
                    template_type=GroupTemplateType.BASE,
                    visual_intent=GroupVisualIntent.ABSTRACT,
                    tags=(),
                ),
                TemplateInfo(
                    template_id="gtpl_rhythm_1",
                    version="1.0",
                    name="Rhythm 1",
                    template_type=GroupTemplateType.RHYTHM,
                    visual_intent=GroupVisualIntent.GEOMETRIC,
                    tags=(),
                ),
                TemplateInfo(
                    template_id="gtpl_multi",
                    version="1.0",
                    name="Multi",
                    template_type=GroupTemplateType.BASE,
                    visual_intent=GroupVisualIntent.ABSTRACT,
                    tags=(),
                ),
            ]
        )
        base_templates = catalog.list_by_lane(LaneKind.BASE)
        assert len(base_templates) == 2
        template_ids = [e.template_id for e in base_templates]
        assert "gtpl_bg_1" in template_ids
        assert "gtpl_multi" in template_ids


class TestGroupPlacement:
    """Tests for GroupPlacement model."""

    def test_valid_placement(self) -> None:
        """Valid placement with PlanningTimeRef start and EffectDuration."""
        placement = GroupPlacement(
            placement_id="p1",
            target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
            template_id="gtpl_accent_bell",
            start=PlanningTimeRef(bar=1, beat=1),
            duration=EffectDuration.PHRASE,
            intensity=IntensityLevel.STRONG,
        )
        assert placement.target.id == "HERO_1"
        assert placement.template_id == "gtpl_accent_bell"
        assert placement.duration == EffectDuration.PHRASE
        assert placement.intensity == IntensityLevel.STRONG


class TestCoordinationPlan:
    """Tests for CoordinationPlan model."""

    def test_unified_mode_requires_placements(self) -> None:
        """UNIFIED mode should have placements, no config."""
        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.UNIFIED,
            targets=[
                PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                PlanTarget(type=TargetType.GROUP, id="HERO_2"),
            ],
            placements=[
                GroupPlacement(
                    placement_id="p1",
                    target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                    template_id="gtpl_accent",
                    start=PlanningTimeRef(bar=1, beat=1),
                    duration=EffectDuration.BURST,
                    intensity=IntensityLevel.STRONG,
                ),
            ],
        )
        assert plan.coordination_mode == CoordinationMode.UNIFIED
        assert plan.config is None

    def test_sequenced_mode_requires_config(self) -> None:
        """SEQUENCED mode should have window + config, no pre-expanded placements."""
        plan = CoordinationPlan(
            coordination_mode=CoordinationMode.SEQUENCED,
            targets=[
                PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                PlanTarget(type=TargetType.GROUP, id="HERO_2"),
                PlanTarget(type=TargetType.GROUP, id="HERO_3"),
            ],
            window=PlacementWindow(
                start=PlanningTimeRef(bar=1, beat=1),
                end=PlanningTimeRef(bar=4, beat=1),
                template_id="gtpl_accent",
                intensity=IntensityLevel.STRONG,
            ),
            config=CoordinationConfig(
                group_order=["HERO_1", "HERO_2", "HERO_3"],
                step_unit=StepUnit.BEAT,
                step_duration=1,
                spill_policy=SpillPolicy.TRUNCATE,
            ),
        )
        assert plan.coordination_mode == CoordinationMode.SEQUENCED
        assert plan.config is not None
        assert plan.config.group_order == ["HERO_1", "HERO_2", "HERO_3"]


class TestLanePlan:
    """Tests for LanePlan model."""

    def test_lane_plan_with_coordination(self) -> None:
        """LanePlan contains coordination plans for a lane."""
        lane_plan = LanePlan(
            lane=LaneKind.ACCENT,
            target_roles=["HERO"],
            coordination_plans=[
                CoordinationPlan(
                    coordination_mode=CoordinationMode.UNIFIED,
                    targets=[PlanTarget(type=TargetType.GROUP, id="HERO_1")],
                    placements=[
                        GroupPlacement(
                            placement_id="p1",
                            target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                            template_id="gtpl_accent",
                            start=PlanningTimeRef(bar=1, beat=1),
                            duration=EffectDuration.BURST,
                            intensity=IntensityLevel.PEAK,
                        ),
                    ],
                ),
            ],
        )
        assert lane_plan.lane == LaneKind.ACCENT
        assert len(lane_plan.coordination_plans) == 1


class TestSectionCoordinationPlan:
    """Tests for SectionCoordinationPlan model."""

    def test_section_plan_structure(self) -> None:
        """SectionCoordinationPlan contains lane plans for a section."""
        section_plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.BASE,
                    target_roles=["OUTLINE"],
                    coordination_plans=[],
                ),
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[],
                ),
            ],
        )
        assert section_plan.section_id == "verse_1"
        assert len(section_plan.lane_plans) == 2
