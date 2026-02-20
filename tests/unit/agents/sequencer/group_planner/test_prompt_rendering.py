"""Tests for FE context injection into planner prompts."""

from __future__ import annotations

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
from twinklr.core.agents.sequencer.group_planner.context_shaping import (
    shape_planner_context,
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
    TimeRef,
    TimeRefKind,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.vocabulary import GroupTemplateType, GroupVisualIntent


@pytest.fixture
def section_context_with_fe() -> SectionPlanningContext:
    """SectionPlanningContext with FE enrichment fields populated."""
    choreo_graph = ChoreographyGraph(
        graph_id="test_display",
        groups=[ChoreoGroup(id="HERO_1", role="HERO")],
    )
    template_catalog = TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow_warm",
                version="1.0",
                name="Warm Glow",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
        ]
    )
    timing_context = TimingContext(
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
    return SectionPlanningContext(
        section_id="verse_1",
        section_name="verse",
        start_ms=0,
        end_ms=4000,
        energy_target="MED",
        motion_density="MED",
        choreography_style="HYBRID",
        primary_focus_targets=["HERO"],
        secondary_targets=[],
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        timing_context=timing_context,
        color_arc={
            "palette_id": "pal_icy_blue",
            "shift_timing": "section_start",
            "contrast_target": 0.5,
        },
        propensity_hints={
            "affinities": [
                {"effect_family": "single_strand", "model_type": "megatree", "frequency": 0.8}
            ],
        },
        style_constraints={
            "timing_style": {"beat_alignment_strictness": 0.8, "density_preference": 0.5},
        },
    )


@pytest.fixture
def section_context_without_fe() -> SectionPlanningContext:
    """SectionPlanningContext without FE enrichment fields."""
    choreo_graph = ChoreographyGraph(
        graph_id="test_display",
        groups=[ChoreoGroup(id="HERO_1", role="HERO")],
    )
    template_catalog = TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow_warm",
                version="1.0",
                name="Warm Glow",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
        ]
    )
    timing_context = TimingContext(
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
    return SectionPlanningContext(
        section_id="verse_1",
        section_name="verse",
        start_ms=0,
        end_ms=4000,
        energy_target="MED",
        motion_density="MED",
        choreography_style="HYBRID",
        primary_focus_targets=["HERO"],
        secondary_targets=[],
        choreo_graph=choreo_graph,
        template_catalog=template_catalog,
        timing_context=timing_context,
    )


def test_shape_planner_context_includes_fe_fields(
    section_context_with_fe: SectionPlanningContext,
) -> None:
    """When FE fields are populated, they appear in shaped context."""
    variables = shape_planner_context(section_context_with_fe)
    assert variables["color_arc"] is not None
    assert variables["color_arc"]["palette_id"] == "pal_icy_blue"
    assert variables["propensity_hints"] is not None
    assert variables["style_constraints"] is not None


def test_shape_planner_context_fe_fields_none_when_absent(
    section_context_without_fe: SectionPlanningContext,
) -> None:
    """When FE fields are not set, they are None in shaped context."""
    variables = shape_planner_context(section_context_without_fe)
    assert variables["color_arc"] is None
    assert variables["propensity_hints"] is None
    assert variables["style_constraints"] is None


def test_prompt_renders_fe_blocks_when_populated(
    section_context_with_fe: SectionPlanningContext,
) -> None:
    """FE context blocks render in user prompt when fields are populated."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    prompts_dir = Path(__file__).resolve().parents[5] / (
        "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    )
    env = Environment(loader=FileSystemLoader(str(prompts_dir)))
    template = env.get_template("user.j2")

    variables = shape_planner_context(section_context_with_fe)
    rendered = template.render(**variables)

    assert "Feature Engineering Context" in rendered
    assert "Color Arc" in rendered
    assert "pal_icy_blue" in rendered
    assert "Propensity Hints" in rendered
    assert "Style Constraints" in rendered
    assert "Transition Hints" not in rendered
    assert "Layering Budget" not in rendered


def test_prompt_omits_fe_blocks_when_absent(
    section_context_without_fe: SectionPlanningContext,
) -> None:
    """FE context blocks do NOT render when fields are None."""
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    prompts_dir = Path(__file__).resolve().parents[5] / (
        "packages/twinklr/core/agents/sequencer/group_planner/prompts/planner"
    )
    env = Environment(loader=FileSystemLoader(str(prompts_dir)))
    template = env.get_template("user.j2")

    variables = shape_planner_context(section_context_without_fe)
    rendered = template.render(**variables)

    assert "Feature Engineering Context" not in rendered
    assert "Color Arc" not in rendered
    assert "Propensity Hints" not in rendered
