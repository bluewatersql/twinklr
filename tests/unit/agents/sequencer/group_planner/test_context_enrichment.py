"""Tests for FE context enrichment in SectionPlanningContext."""

from __future__ import annotations

from typing import Any

import pytest

from twinklr.core.agents.sequencer.group_planner.context import SectionPlanningContext
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
def _minimal_context_kwargs() -> dict[str, Any]:
    """Minimal required fields for SectionPlanningContext."""
    choreo_graph = ChoreographyGraph(
        graph_id="test_display",
        groups=[ChoreoGroup(id="HERO_1", role="HERO")],
    )
    template_catalog = TemplateCatalog(
        entries=[
            TemplateInfo(
                template_id="gtpl_base_glow",
                version="1.0",
                name="Glow",
                template_type=GroupTemplateType.BASE,
                visual_intent=GroupVisualIntent.ABSTRACT,
                tags=(),
            ),
        ]
    )
    timing_context = TimingContext(
        song_duration_ms=8000,
        beats_per_bar=4,
        bar_map={1: BarInfo(bar=1, start_ms=0, duration_ms=2000)},
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=2, beat=1),
            ),
        },
    )
    return {
        "section_id": "verse_1",
        "section_name": "verse",
        "start_ms": 0,
        "end_ms": 2000,
        "energy_target": "MED",
        "motion_density": "MED",
        "choreography_style": "HYBRID",
        "primary_focus_targets": ["HERO"],
        "secondary_targets": [],
        "choreo_graph": choreo_graph,
        "template_catalog": template_catalog,
        "timing_context": timing_context,
    }


def test_fe_fields_default_to_none(
    _minimal_context_kwargs: dict[str, Any],
) -> None:
    """FE enrichment fields default to None (backward compat)."""
    ctx = SectionPlanningContext(**_minimal_context_kwargs)
    assert ctx.color_arc is None
    assert ctx.propensity_hints is None
    assert ctx.style_constraints is None


def test_fe_fields_accept_dict_values(
    _minimal_context_kwargs: dict[str, Any],
) -> None:
    """FE enrichment fields accept dict values when populated."""
    fe_kwargs = {
        **_minimal_context_kwargs,
        "color_arc": {
            "palette_id": "pal_icy_blue",
            "shift_timing": "section_start",
            "contrast_target": 0.5,
        },
        "propensity_hints": {
            "affinities": [
                {"effect_family": "single_strand", "model_type": "megatree", "frequency": 0.8}
            ],
        },
        "style_constraints": {
            "timing_style": {"beat_alignment_strictness": 0.8, "density_preference": 0.5},
        },
    }
    ctx = SectionPlanningContext(**fe_kwargs)
    assert ctx.color_arc is not None
    assert ctx.color_arc["palette_id"] == "pal_icy_blue"
    assert ctx.propensity_hints is not None
    assert ctx.style_constraints is not None


def test_existing_fields_unaffected(
    _minimal_context_kwargs: dict[str, Any],
) -> None:
    """Existing fields continue to work with FE fields added."""
    ctx = SectionPlanningContext(
        **_minimal_context_kwargs,
        color_arc={"palette_id": "test"},
    )
    assert ctx.section_id == "verse_1"
    assert ctx.energy_target == "MED"
    assert ctx.duration_ms == 2000
