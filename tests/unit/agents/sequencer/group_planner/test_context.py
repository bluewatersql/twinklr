"""Tests for GroupPlanner context models."""

from __future__ import annotations

import pytest

from twinklr.core.agents.sequencer.group_planner.context import (
    SectionPlanningContext,
)
from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.sequencer.templates.group.catalog import (
    TemplateCatalog,
    TemplateInfo,
)
from twinklr.core.sequencer.templates.group.models import (
    LaneKind,
    TimeRef,
    TimeRefKind,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent


@pytest.fixture
def sample_choreo_graph() -> ChoreographyGraph:
    """Sample choreography graph."""
    return ChoreographyGraph(
        graph_id="test_display",
        groups=[
            ChoreoGroup(id="HERO_1", role="HERO"),
            ChoreoGroup(id="ARCHES_1", role="ARCHES"),
        ],
    )


@pytest.fixture
def sample_template_catalog() -> TemplateCatalog:
    """Sample template catalog."""
    return TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow_warm",
                version="1.0",
                name="Warm BG",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
            TemplateInfo(
                template_id="gtpl_accent_flash",
                version="1.0",
                name="Flash",
                template_type=GroupTemplateType.ACCENT,
                visual_intent=GroupVisualIntent.TEXTURE,
                tags=(),
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
        "lead_targets": ["HERO"],
        "support_targets": ["ARCHES"],
        "choreography_style": "HYBRID",
        "motion_density": "MED",
        "notes": "Standard verse section",
    }


class TestSectionPlanningContext:
    """Tests for SectionPlanningContext."""

    def test_create_from_macro_section(
        self,
        sample_macro_section: dict,
        sample_choreo_graph: ChoreographyGraph,
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
            lead_targets=["HERO"],
            support_targets=["ARCHES"],
            notes="Standard verse section",
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        assert ctx.section_id == "verse_1"
        assert ctx.energy_target == "MED"
        assert ctx.lead_targets == ["HERO"]

    def test_get_target_groups(
        self,
        sample_macro_section: dict,
        sample_choreo_graph: ChoreographyGraph,
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
            lead_targets=["HERO"],
            support_targets=["ARCHES"],
            notes=None,
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        primary_groups = ctx.get_target_groups(ctx.lead_targets)
        assert "HERO_1" in primary_groups

        secondary_groups = ctx.get_target_groups(ctx.support_targets)
        assert "ARCHES_1" in secondary_groups

    def test_templates_for_lane(
        self,
        sample_choreo_graph: ChoreographyGraph,
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
            lead_targets=["HERO"],
            support_targets=[],
            notes=None,
            choreo_graph=sample_choreo_graph,
            template_catalog=sample_template_catalog,
            timing_context=sample_timing_context,
        )

        base_templates = ctx.templates_for_lane(LaneKind.BASE)
        assert len(base_templates) == 1
        assert base_templates[0].template_id == "gtpl_base_glow_warm"

        accent_templates = ctx.templates_for_lane(LaneKind.ACCENT)
        assert len(accent_templates) == 1
        assert accent_templates[0].template_id == "gtpl_accent_flash"
