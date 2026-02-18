"""Tests for GroupPlanner deterministic validators."""

from __future__ import annotations

import pytest

from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.agents.sequencer.group_planner.validators import (
    SectionPlanValidator,
)
from twinklr.core.sequencer.planning import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models import (
    CoordinationPlan,
    GroupPlacement,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
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
)
from twinklr.core.sequencer.vocabulary.choreography import TargetType
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME

# Rebuild TemplateInfo after LaneKind is imported (forward ref resolution)
TemplateInfo.model_rebuild()


@pytest.fixture
def sample_choreo_graph() -> ChoreographyGraph:
    """Sample choreography graph with multiple groups."""
    return ChoreographyGraph(
        graph_id="test_display",
        groups=[
            ChoreoGroup(id="HERO_1", role="HERO"),
            ChoreoGroup(id="HERO_2", role="HERO"),
            ChoreoGroup(id="ARCHES_1", role="ARCHES"),
            ChoreoGroup(id="OUTLINE_1", role="OUTLINE"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog with valid templates."""
    return TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_bg_starfield",
                version="1.0",
                name="Starfield Background",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
            TemplateInfo(
                template_id="gtpl_accent_bell",
                version="1.0",
                name="Bell Accent",
                template_type=GroupTemplateType.ACCENT,
                visual_intent=GroupVisualIntent.TEXTURE,
                tags=(),
            ),
            TemplateInfo(
                template_id="gtpl_rhythm_bounce",
                version="1.0",
                name="Rhythm Bounce",
                template_type=GroupTemplateType.RHYTHM,
                visual_intent=GroupVisualIntent.GEOMETRIC,
                tags=(),
            ),
        ]
    )


@pytest.fixture
def sample_timing_context() -> TimingContext:
    """Sample timing context (4 bars at 120 BPM)."""
    return TimingContext(
        song_duration_ms=8000,
        beats_per_bar=4,
        bar_map={
            1: BarInfo(bar=1, start_ms=0, duration_ms=2000),
            2: BarInfo(bar=2, start_ms=2000, duration_ms=2000),
            3: BarInfo(bar=3, start_ms=4000, duration_ms=2000),
            4: BarInfo(bar=4, start_ms=6000, duration_ms=2000),
        },
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=3, beat=1),
            ),
        },
    )


class TestSectionPlanValidator:
    """Tests for SectionPlanValidator."""

    def test_valid_plan_passes(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Valid plan passes validation."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_unknown_template_fails(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Unknown template_id causes validation error."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="NONEXISTENT_TEMPLATE",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("NONEXISTENT_TEMPLATE" in e.message for e in result.errors)

    def test_unknown_group_id_fails(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Unknown group_id causes validation error."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="NONEXISTENT_GROUP")],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    target=PlanTarget(
                                        type=TargetType.GROUP, id="NONEXISTENT_GROUP"
                                    ),
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("NONEXISTENT_GROUP" in e.message for e in result.errors)

    def test_placement_outside_section_fails(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Placement outside section bounds causes validation error."""
        # Section verse_1 is bar 1-3, placement starts at bar 4
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=4, beat=1),
                                    duration=EffectDuration.HIT,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("outside section" in e.message.lower() for e in result.errors)

    def test_within_lane_overlap_fails(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Overlapping placements on same group within same lane fails."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,  # 4 beats
                                ),
                                GroupPlacement(
                                    placement_id="p2",
                                    target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=3),
                                    duration=EffectDuration.BURST,  # 4 beats, overlaps p1
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("overlap" in e.message.lower() for e in result.errors)

    def test_different_groups_can_overlap(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Different groups CAN have overlapping placements."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.ACCENT,
                    target_roles=["HERO"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[
                                PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                                PlanTarget(type=TargetType.GROUP, id="HERO_2"),
                            ],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                                GroupPlacement(
                                    placement_id="p2",
                                    target=PlanTarget(type=TargetType.GROUP, id="HERO_2"),
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid

    def test_valid_intensity_levels(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """All valid IntensityLevel enum values should pass validation."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                    intensity=IntensityLevel.PEAK,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_effect_durations(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """All valid EffectDuration enum values should pass validation."""
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
                    lane=LaneKind.RHYTHM,
                    target_roles=["ARCHES"],
                    coordination_plans=[
                        CoordinationPlan(
                            coordination_mode=CoordinationMode.UNIFIED,
                            targets=[PlanTarget(type=TargetType.GROUP, id="ARCHES_1")],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    target=PlanTarget(type=TargetType.GROUP, id="ARCHES_1"),
                                    template_id="gtpl_rhythm_bounce",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.PHRASE,
                                    intensity=IntensityLevel.MED,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_all_intensity_levels_with_accent_lane(
        self,
        sample_choreo_graph: ChoreographyGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """All IntensityLevel values should work with ACCENT lane."""
        # Create placements with each intensity level
        placements = []
        for i, level in enumerate(IntensityLevel):
            placements.append(
                GroupPlacement(
                    placement_id=f"p{i}",
                    target=PlanTarget(type=TargetType.GROUP, id="HERO_1"),
                    template_id="gtpl_accent_bell",
                    start=PlanningTimeRef(bar=1 + i, beat=1)
                    if i < 2
                    else PlanningTimeRef(bar=2, beat=1 + i - 2),
                    duration=EffectDuration.HIT,
                    intensity=level,
                )
            )

        # Just test one placement with PEAK intensity
        plan = SectionCoordinationPlan(
            section_id="verse_1",
            theme=DEFAULT_THEME,
            lane_plans=[
                LanePlan(
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
                                    template_id="gtpl_accent_bell",
                                    start=PlanningTimeRef(bar=1, beat=1),
                                    duration=EffectDuration.BURST,
                                    intensity=IntensityLevel.PEAK,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
