"""Tests for the foundation-coverage rule: a section's BASE lane keeps the display lit."""

from __future__ import annotations

from twinklr.core.agents.sequencer.group_planner.timing import (
    BarInfo,
    SectionBounds,
    TimingContext,
)
from twinklr.core.agents.sequencer.group_planner.validators import SectionPlanValidator
from twinklr.core.sequencer.planning import LanePlan, SectionCoordinationPlan
from twinklr.core.sequencer.templates.group.catalog import TemplateCatalog, TemplateInfo
from twinklr.core.sequencer.templates.group.models import CoordinationPlan, GroupPlacement
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.templates.group.recipe_catalog import RecipeCatalog
from twinklr.core.sequencer.timing import TimeRef
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GroupTemplateType,
    GroupVisualIntent,
    LaneKind,
    PlanningTimeRef,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag, TargetType
from twinklr.core.sequencer.vocabulary.timing import TimeRefKind

from .conftest import DEFAULT_THEME
from .test_recipe_planner import _make_recipe

TemplateInfo.model_rebuild()

_CODE = "FOUNDATION_TOO_NARROW"


def _graph(*, with_fractions: bool = True) -> ChoreographyGraph:
    def fraction(value: float) -> float:
        return value if with_fractions else 0.0

    return ChoreographyGraph(
        graph_id="test_display",
        groups=[
            ChoreoGroup(
                id="ALL_HOUSE", role="HOUSE", pixel_fraction=fraction(0.55), tags=[ChoreoTag.HOUSE]
            ),
            ChoreoGroup(id="SNOWFLAKES", role="SNOWFLAKES", pixel_fraction=fraction(0.17)),
            ChoreoGroup(id="FLOODS", role="FLOODS", pixel_fraction=fraction(0.03)),
        ],
    )


def _catalog() -> TemplateCatalog:
    return TemplateCatalog(
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


def _timing(end_bar: int = 3) -> TimingContext:
    return TimingContext(
        song_duration_ms=8000,
        beats_per_bar=4,
        bar_map={
            bar: BarInfo(bar=bar, start_ms=(bar - 1) * 2000, duration_ms=2000)
            for bar in range(1, 5)
        },
        section_bounds={
            "verse_1": SectionBounds(
                section_id="verse_1",
                start=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=1, beat=1),
                end=TimeRef(kind=TimeRefKind.BAR_BEAT, bar=end_bar, beat=1),
            ),
        },
    )


def _base_plan(
    target: PlanTarget,
    duration: EffectDuration = EffectDuration.SECTION,
    template_id: str = "gtpl_base_glow",
) -> SectionCoordinationPlan:
    return SectionCoordinationPlan(
        section_id="verse_1",
        theme=DEFAULT_THEME,
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                target_roles=["BACKGROUND"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[target],
                        placements=[
                            GroupPlacement(
                                placement_id="p1",
                                target=target,
                                template_id=template_id,
                                start=PlanningTimeRef(bar=1, beat=1),
                                duration=duration,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _codes(
    plan: SectionCoordinationPlan,
    *,
    graph: ChoreographyGraph | None = None,
    timing: TimingContext | None = None,
) -> list[str]:
    validator = SectionPlanValidator(
        choreo_graph=graph or _graph(),
        template_catalog=_catalog(),
        timing_context=timing or _timing(),
    )
    return [issue.code for issue in validator.validate(plan).errors]


def test_wide_section_long_foundation_passes() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="ALL_HOUSE"))
    assert _CODE not in _codes(plan)


def test_foundation_on_small_props_only_is_rejected() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="SNOWFLAKES"))
    assert _CODE in _codes(plan)


def test_wide_target_must_last_the_whole_section() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="ALL_HOUSE"), EffectDuration.PHRASE)
    assert _CODE in _codes(plan)


def test_zone_target_counts_as_its_widest_group() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.ZONE, id="HOUSE"))
    assert _CODE not in _codes(plan)


def test_fix_hint_names_the_wide_groups() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="FLOODS"))
    validator = SectionPlanValidator(
        choreo_graph=_graph(), template_catalog=_catalog(), timing_context=_timing()
    )
    issue = next(i for i in validator.validate(plan).errors if i.code == _CODE)
    assert issue.fix_hint is not None
    assert "ALL_HOUSE" in issue.fix_hint
    assert "SNOWFLAKES" not in issue.fix_hint


def _recipes() -> RecipeCatalog:
    return RecipeCatalog(
        recipes=[
            _make_recipe(
                recipe_id="gtpl_base_glow",
                template_type=GroupTemplateType.BASE,
                effect_type="Color Wash",
            ),
            _make_recipe(
                recipe_id="gtpl_base_shimmer",
                template_type=GroupTemplateType.BASE,
                effect_type="Twinkle",
            ),
        ]
    )


def _codes_with_recipes(plan: SectionCoordinationPlan) -> list[str]:
    validator = SectionPlanValidator(
        choreo_graph=_graph(),
        template_catalog=_catalog(),
        timing_context=_timing(),
        recipe_catalog=_recipes(),
    )
    return [issue.code for issue in validator.validate(plan).errors]


def test_sparse_texture_as_the_only_wide_foundation_is_rejected() -> None:
    plan = _base_plan(
        PlanTarget(type=TargetType.GROUP, id="ALL_HOUSE"), template_id="gtpl_base_shimmer"
    )
    assert "FOUNDATION_TOO_SPARSE" in _codes_with_recipes(plan)


def test_full_coverage_template_on_a_wide_target_passes() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="ALL_HOUSE"))
    codes = _codes_with_recipes(plan)
    assert "FOUNDATION_TOO_SPARSE" not in codes
    assert _CODE not in codes


def test_sparse_fix_hint_names_only_full_coverage_templates() -> None:
    plan = _base_plan(
        PlanTarget(type=TargetType.GROUP, id="ALL_HOUSE"), template_id="gtpl_base_shimmer"
    )
    validator = SectionPlanValidator(
        choreo_graph=_graph(),
        template_catalog=_catalog(),
        timing_context=_timing(),
        recipe_catalog=_recipes(),
    )
    issue = next(i for i in validator.validate(plan).errors if i.code == "FOUNDATION_TOO_SPARSE")
    assert issue.fix_hint is not None
    assert "gtpl_base_glow" in issue.fix_hint
    assert "gtpl_base_shimmer" not in issue.fix_hint


def test_skipped_when_the_layout_reports_no_pixel_fractions() -> None:
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="SNOWFLAKES"))
    assert _CODE not in _codes(plan, graph=_graph(with_fractions=False))


def test_skipped_for_a_section_shorter_than_one_bar() -> None:
    """A sub-bar tail may stay dark: its bounds resolve to the same bar."""
    plan = _base_plan(PlanTarget(type=TargetType.GROUP, id="FLOODS"))
    assert _CODE not in _codes(plan, timing=_timing(end_bar=1))
    assert _CODE in _codes(plan, timing=_timing(end_bar=3))
