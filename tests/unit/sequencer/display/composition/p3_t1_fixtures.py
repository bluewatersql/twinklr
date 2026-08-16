"""Corpus-independent fixtures for the P3-T1 composition timing contract."""

from __future__ import annotations

from collections.abc import Iterable

from twinklr.core.sequencer.display.composition.engine import CompositionEngine
from twinklr.core.sequencer.display.composition.models import CompiledEffect
from twinklr.core.sequencer.display.composition.palette_resolver import PaletteResolver
from twinklr.core.sequencer.display.composition.template_compiler import TemplateCompileContext
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.display.models.render_plan import RenderPlan
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.planning.models import PaletteRef
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationConfig,
    CoordinationPlan,
    GroupPlacement,
    PlacementWindow,
    PlanTarget,
)
from twinklr.core.sequencer.theming import PALETTE_REGISTRY, ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GPBlendMode,
    IntensityLevel,
    LaneKind,
    PlanningTimeRef,
    StepUnit,
    TargetType,
    VisualDepth,
)

GROUP_IDS = ("G0", "G1", "G2", "G3")


class RecordingCompiler:
    """Minimal compiler that preserves the engine's resolved timing verbatim."""

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        event = RenderEvent(
            event_id=placement.placement_id,
            start_ms=context.start_ms,
            end_ms=context.end_ms,
            effect_type="On",
            palette=context.palette,
            intensity=context.intensity,
            source=RenderEventSource(
                section_id=context.section_id,
                lane=context.lane,
                group_id=placement.target.id,
                template_id=placement.template_id,
                placement_id=placement.placement_id,
                placement_index=context.placement_index,
            ),
        )
        return [CompiledEffect(event=event, visual_depth=VisualDepth.BACKGROUND)]


def make_grid(
    beat_boundaries: list[float] | None = None,
    *,
    tempo_bpm: float = 120.0,
    beats_per_bar: int = 4,
) -> BeatGrid:
    beats = beat_boundaries or [137.0 + 500.0 * index for index in range(33)]
    bars = [beats[index] for index in range(0, len(beats), beats_per_bar)]
    if bars[-1] != beats[-1]:
        bars.append(beats[-1])
    return BeatGrid(
        bar_boundaries=bars,
        beat_boundaries=beats,
        eighth_boundaries=[],
        sixteenth_boundaries=[],
        tempo_bpm=tempo_bpm,
        beats_per_bar=beats_per_bar,
        duration_ms=beats[-1] + 1000.0,
    )


def make_engine(
    beat_grid: BeatGrid | None = None,
    *,
    section_boundaries: list[tuple[str, int, int]] | None = None,
) -> CompositionEngine:
    graph = ChoreographyGraph(
        graph_id="p3-t1",
        groups=[ChoreoGroup(id=group_id, role="ARCHES") for group_id in GROUP_IDS],
    )
    palette = ResolvedPalette(colors=["#FFFFFF"], active_slots=[1])
    return CompositionEngine(
        beat_grid=beat_grid or make_grid(),
        choreo_graph=graph,
        palette_resolver=PaletteResolver(catalog=PALETTE_REGISTRY, default=palette),
        template_compiler=RecordingCompiler(),
        section_boundaries=section_boundaries,
    )


def make_window_plan(
    mode: CoordinationMode,
    *,
    group_ids: Iterable[str] = GROUP_IDS[:3],
    start: PlanningTimeRef | None = None,
    end: PlanningTimeRef | None = None,
    step_duration: int = 1,
    phase_offset: float = 0.0,
    section_id: str = "section",
    blend_mode: GPBlendMode = GPBlendMode.ADD,
) -> GroupPlanSet:
    ids = list(group_ids)
    section = SectionCoordinationPlan(
        section_id=section_id,
        theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
        palette=PaletteRef(palette_id="missing.test.palette"),
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                blend_mode=blend_mode,
                target_roles=["ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=mode,
                        targets=[PlanTarget(type=TargetType.GROUP, id=value) for value in ids],
                        window=PlacementWindow(
                            start=start or PlanningTimeRef(bar=1, beat=1),
                            end=end or PlanningTimeRef(bar=3, beat=1),
                            template_id="fixture",
                            intensity=IntensityLevel.MED,
                        ),
                        config=CoordinationConfig(
                            group_order=ids,
                            step_unit=StepUnit.BEAT,
                            step_duration=step_duration,
                            phase_offset=phase_offset,
                        ),
                    )
                ],
            )
        ],
    )
    return GroupPlanSet(plan_set_id=f"{mode.value}-plan", section_plans=[section])


def make_authored_plan(
    *,
    placement_id: str = "authored",
    blend_mode: GPBlendMode = GPBlendMode.ADD,
) -> GroupPlanSet:
    placement = GroupPlacement(
        placement_id=placement_id,
        target=PlanTarget(type=TargetType.GROUP, id="G0"),
        template_id="fixture",
        start=PlanningTimeRef(bar=1, beat=2),
        duration=EffectDuration.HIT,
    )
    section = SectionCoordinationPlan(
        section_id="section",
        theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
        palette=None,
        lane_plans=[
            LanePlan(
                lane=LaneKind.BASE,
                blend_mode=blend_mode,
                target_roles=["ARCHES"],
                coordination_plans=[
                    CoordinationPlan(
                        coordination_mode=CoordinationMode.UNIFIED,
                        targets=[placement.target],
                        placements=[placement],
                    )
                ],
            )
        ],
    )
    return GroupPlanSet(plan_set_id=f"{placement_id}-plan", section_plans=[section])


def events_by_start(plan: RenderPlan) -> list[tuple[str, RenderEvent]]:
    groups = plan.groups
    result = [
        (group.element_name, event)
        for group in groups
        for layer in group.layers
        for event in layer.events
    ]
    return sorted(result, key=lambda item: (item[1].start_ms, item[0], item[1].event_id))
