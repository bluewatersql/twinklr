"""Tests for GroupPlanner context models."""

from __future__ import annotations

import pytest

from twinklr.core.agents.sequencer.group_planner.context import (
    GroupPlanningContext,
    SectionPlanningContext,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateCatalogEntry,
)
from twinklr.core.sequencer.templates.group.models import (
    DisplayGraph,
    DisplayGroup,
    LaneKind,
    TimeRef,
    TimeRefKind,
)


@pytest.fixture
def sample_display_graph() -> DisplayGraph:
    """Sample display graph."""
    return DisplayGraph(
        display_id="test_display",
        display_name="Test Display",
        groups=[
            DisplayGroup(group_id="HERO_1", role="HERO", display_name="Hero 1"),
            DisplayGroup(group_id="ARCHES_1", role="ARCHES", display_name="Arches"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog."""
    return TemplateCatalog(
        entries=[
            TemplateCatalogEntry(
                template_id="gtpl_base_glow_warm",
                name="Warm BG",
                compatible_lanes=[LaneKind.BASE],
            ),
            TemplateCatalogEntry(
                template_id="gtpl_accent_flash",
                name="Flash",
                compatible_lanes=[LaneKind.ACCENT],
            ),
        ]
    )


@pytest.fixture
def sample_timing_context() -> TimingContext:
    """Sample timing context."""
    return TimingContext(
        song_duration_ms=8000,
        beats_per_bar=4,
        bar_map={
            1: BarInfo(bar=1, start_ms=0, duration_ms=2000),
            2: BarInfo(bar=2, start_ms=2000, duration_ms=2000),
        },
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
            ),
        },
    )


@pytest.fixture
def sample_macro_section() -> dict:
    """Sample MacroPlan section_plan dict."""
    return {
        "section": {
            "section_id": "verse_1",
            "name": "verse",
            "start_ms": 0,
            "end_ms": 2000,
        },
        "energy_target": "MED",
        "primary_focus_targets": ["HERO"],
        "secondary_targets": ["ARCHES"],
        "choreography_style": "HYBRID",
        "motion_density": "MED",
        "notes": "Standard verse section",
    }


class TestSectionPlanningContext:
    """Tests for SectionPlanningContext."""

    def test_create_from_macro_section(
        self,
        sample_macro_section: dict,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """Create SectionPlanningContext from macro section."""
        ctx = SectionPlanningContext(
            section_id="verse_1",
            section_name="verse",
            start_ms=0,
            end_ms=2000,
            energy_target="MED",
            motion_density="MED",
            choreography_style="HYBRID",
            primary_focus_targets=["HERO"],
            secondary_targets=["ARCHES"],
            notes="Standard verse section",
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        assert ctx.section_id == "verse_1"
        assert ctx.energy_target == "MED"
        assert ctx.primary_focus_targets == ["HERO"]

    def test_get_target_groups(
        self,
        sample_macro_section: dict,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """get_target_groups expands roles to group_ids."""
        ctx = SectionPlanningContext(
            section_id="verse_1",
            section_name="verse",
            start_ms=0,
            end_ms=2000,
            energy_target="MED",
            motion_density="MED",
            choreography_style="HYBRID",
            primary_focus_targets=["HERO"],
            secondary_targets=["ARCHES"],
            notes=None,
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        primary_groups = ctx.get_target_groups(ctx.primary_focus_targets)
        assert "HERO_1" in primary_groups

        secondary_groups = ctx.get_target_groups(ctx.secondary_targets)
        assert "ARCHES_1" in secondary_groups

    def test_templates_for_lane(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """templates_for_lane filters catalog by lane."""
        ctx = SectionPlanningContext(
            section_id="verse_1",
            section_name="verse",
            start_ms=0,
            end_ms=2000,
            energy_target="MED",
            motion_density="MED",
            choreography_style="HYBRID",
            primary_focus_targets=["HERO"],
            secondary_targets=[],
            notes=None,
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        base_templates = ctx.templates_for_lane(LaneKind.BASE)
        assert len(base_templates) == 1
        assert base_templates[0].template_id == "gtpl_base_glow_warm"

        accent_templates = ctx.templates_for_lane(LaneKind.ACCENT)
        assert len(accent_templates) == 1
        assert accent_templates[0].template_id == "gtpl_accent_flash"


class TestGroupPlanningContext:
    """Tests for GroupPlanningContext (aggregate)."""

    def test_build_section_contexts(
        self,
        sample_display_graph: DisplayGraph,
        sample_template_catalog: TemplateCatalog,
        sample_timing_context: TimingContext,
    ) -> None:
        """build_section_contexts creates list of SectionPlanningContext."""
        # Mock MacroPlan section_plans structure
        section_plans = [
            {
                "section": {
                    "section_id": "verse_1",
                    "name": "verse",
                    "start_ms": 0,
                    "end_ms": 2000,
                },
                "energy_target": "MED",
                "primary_focus_targets": ["HERO"],
                "secondary_targets": ["ARCHES"],
                "choreography_style": "HYBRID",
                "motion_density": "MED",
                "notes": "Verse section",
            },
            {
                "section": {
                    "section_id": "chorus_1",
                    "name": "chorus",
                    "start_ms": 2000,
                    "end_ms": 4000,
                },
                "energy_target": "HIGH",
                "primary_focus_targets": ["HERO", "ARCHES"],
                "secondary_targets": [],
                "choreography_style": "ABSTRACT",
                "motion_density": "BUSY",
                "notes": "Chorus section",
            },
        ]

        ctx = GroupPlanningContext(
            display_graph=sample_display_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        section_contexts = ctx.build_section_contexts(section_plans)

        assert len(section_contexts) == 2
        assert section_contexts[0].section_id == "verse_1"
        assert section_contexts[1].section_id == "chorus_1"
        assert section_contexts[1].energy_target == "HIGH"
