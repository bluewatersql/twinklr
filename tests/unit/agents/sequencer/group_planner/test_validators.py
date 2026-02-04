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
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateCatalogEntry,
)
from twinklr.core.sequencer.templates.group.models import (
    CoordinationMode,
    CoordinationPlan,
    DisplayGraph,
    DisplayGroup,
    GroupPlacement,
    LaneKind,
    LanePlan,
    SectionCoordinationPlan,
    TimeRef,
    TimeRefKind,
)

from .conftest import DEFAULT_THEME

# Rebuild TemplateCatalogEntry after LaneKind is imported (forward ref resolution)
TemplateCatalogEntry.model_rebuild()


@pytest.fixture
def sample_display_graph() -> DisplayGraph:
    """Sample display graph with multiple groups."""
    return DisplayGraph(
        display_id="test_display",
        display_name="Test Display",
        groups=[
            DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
            DisplayGroup(group_id="HERO_2", role="HERO", display_name="Hero 2"),
            DisplayGroup(group_id="ARCHES_1", role="ARCHES", display_name="Arches"),
            DisplayGroup(group_id="OUTLINE_1", role="OUTLINE", display_name="Outline"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog with valid templates."""
    return TemplateCatalog(
        entries=[
            TemplateCatalogEntry(
                template_id="gtpl_bg_starfield",
                name="Starfield Background",
                compatible_lanes=[LaneKind.BASE],
            ),
            TemplateCatalogEntry(
                template_id="gtpl_accent_bell",
                name="Bell Accent",
                compatible_lanes=[LaneKind.ACCENT],
            ),
            TemplateCatalogEntry(
                template_id="gtpl_rhythm_bounce",
                name="Rhythm Bounce",
                compatible_lanes=[LaneKind.RHYTHM],
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
        sample_display_graph: DisplayGraph,
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_unknown_template_fails(
        self,
        sample_display_graph: DisplayGraph,
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="NONEXISTENT_TEMPLATE",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert len(result.errors) >= 1
        assert any("NONEXISTENT_TEMPLATE" in e.message for e in result.errors)

    def test_unknown_group_id_fails(
        self,
        sample_display_graph: DisplayGraph,
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
                            group_ids=["NONEXISTENT_GROUP"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="NONEXISTENT_GROUP",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("NONEXISTENT_GROUP" in e.message for e in result.errors)

    def test_placement_outside_section_fails(
        self,
        sample_display_graph: DisplayGraph,
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=4, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=4, beat=4),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("outside section" in e.message.lower() for e in result.errors)

    def test_within_lane_overlap_fails(
        self,
        sample_display_graph: DisplayGraph,
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                                GroupPlacement(
                                    placement_id="p2",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=3),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=3),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any("overlap" in e.message.lower() for e in result.errors)

    def test_different_groups_can_overlap(
        self,
        sample_display_graph: DisplayGraph,
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
                            group_ids=["HERO_1", "HERO_2"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                                GroupPlacement(
                                    placement_id="p2",
                                    group_id="HERO_2",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid

    def test_accent_intensity_exceeds_lane_limit(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """ACCENT lane intensity >1.30 should fail validation."""
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                    intensity=1.35,  # Exceeds ACCENT max of 1.30
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any(e.code == "LANE_INTENSITY_EXCEEDED" for e in result.errors)

    def test_rhythm_intensity_exceeds_lane_limit(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """RHYTHM lane intensity >1.20 should fail validation."""
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
                            group_ids=["ARCHES_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="ARCHES_1",
                                    template_id="gtpl_rhythm_bounce",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                    intensity=1.25,  # Exceeds RHYTHM max of 1.20
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert not result.is_valid
        assert any(e.code == "LANE_INTENSITY_EXCEEDED" for e in result.errors)

    def test_intensity_at_lane_limit_passes(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Intensity exactly at lane limit should pass validation."""
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
                            group_ids=["HERO_1"],
                            placements=[
                                GroupPlacement(
                                    placement_id="p1",
                                    group_id="HERO_1",
                                    template_id="gtpl_accent_bell",
                                    start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                                    end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
                                    intensity=1.30,  # Exactly at ACCENT limit
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        validator = SectionPlanValidator(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )
        result = validator.validate(plan)

        assert result.is_valid
