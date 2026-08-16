"""Behavioral tests for the typed macro coordination sink (P3-T5)."""

from __future__ import annotations

import re

import pytest

from twinklr.core.agents.audio.profile.models import SongSectionRef
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan, PlanSection
from twinklr.core.sequencer.display.models.palette import ResolvedPalette
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.display.models.render_plan import (
    RenderGroupPlan,
    RenderLayerPlan,
    RenderPlan,
)
from twinklr.core.sequencer.models.enum import ChannelName, Intensity
from twinklr.core.sequencer.moving_heads.channels.state import ChannelValue, FixtureSegment
from twinklr.core.sequencer.planning.models import (
    CallResponsePair,
    FocalAssignment,
    FocalRole,
    FocalRoleKind,
    MacroPlan,
    MacroSection,
    PaletteRef,
    PaletteRoleRef,
    PaletteStop,
    PaletteTransition,
)
from twinklr.core.sequencer.show_coordination import (
    coordinate_display_render_plan,
    coordinate_moving_head_plan,
    coordinate_moving_head_segments,
    coordination_schedule,
    validate_macro_coordination,
)
from twinklr.core.sequencer.templates.group.models.choreography import (
    ChoreographyGraph,
    ChoreoGroup,
)
from twinklr.core.sequencer.templates.group.models.coordination import PlanTarget
from twinklr.core.sequencer.theming import ThemeRef, ThemeScope
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.vocabulary import (
    ChoreographyStyle,
    CoordinationMode,
    EnergyTarget,
    LaneKind,
    MotionDensity,
    StepUnit,
)
from twinklr.core.sequencer.vocabulary.choreography import ChoreoTag, TargetType


def _grid() -> BeatGrid:
    beats = [0.0, 500.0, 1_100.0, 1_600.0, 2_200.0, 2_700.0, 3_300.0, 3_800.0, 4_400.0]
    return BeatGrid(
        bar_boundaries=[0.0, 2_200.0, 4_400.0],
        beat_boundaries=beats,
        eighth_boundaries=beats,
        sixteenth_boundaries=beats,
        tempo_bpm=109.0,
        beats_per_bar=4,
        duration_ms=4_400.0,
    )


def _graph() -> ChoreographyGraph:
    return ChoreographyGraph(
        graph_id="combined",
        groups=[
            ChoreoGroup(id="MOVING_HEADS", role="MOVING_HEADS", tags=[ChoreoTag.YARD]),
            ChoreoGroup(id="MEGA_TREE", role="MEGA_TREE", tags=[ChoreoTag.YARD]),
            ChoreoGroup(id="ARCH_LEFT", role="ARCH", tags=[ChoreoTag.HOUSE]),
            ChoreoGroup(id="ARCH_RIGHT", role="ARCH", tags=[ChoreoTag.HOUSE]),
            ChoreoGroup(id="WINDOWS", role="WINDOW", tags=[ChoreoTag.HOUSE]),
        ],
    )


def _macro(
    *,
    mode: CoordinationMode = CoordinationMode.UNIFIED,
    roles: list[FocalRole] | None = None,
    pairs: list[CallResponsePair] | None = None,
) -> MacroPlan:
    lead = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    section_roles = roles or [
        FocalRole(target=lead, role=FocalRoleKind.LEAD),
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="ARCH_LEFT"),
            role=FocalRoleKind.SUPPORT,
        ),
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="ARCH_RIGHT"),
            role=FocalRoleKind.REST,
        ),
    ]
    lead = next(role.target for role in section_roles if role.role == FocalRoleKind.LEAD)
    section = MacroSection(
        section=SongSectionRef(section_id="drop", name="Drop", start_ms=0, end_ms=4_400),
        energy_target=EnergyTarget.HIGH,
        motion_density=MotionDensity.BUSY,
        choreography_style=ChoreographyStyle.HYBRID,
        palette_role=PaletteRoleRef(stop_id="drop_palette", override=None),
        theme=ThemeRef(theme_id="theme.holiday.traditional", scope=ThemeScope.SECTION),
        motif_ids=[],
        focal_roles=section_roles,
        call_response_pairs=pairs or [],
        coordination_intent=mode,
        notes="Coordinate every emitted part of this drop.",
    )
    return MacroPlan(
        sections=[section],
        palette_arc=[
            PaletteStop(
                stop_id="drop_palette",
                palette=PaletteRef(palette_id="core.christmas_traditional"),
                applies_from_section_id="drop",
                transition=PaletteTransition.CUT,
            )
        ],
        motif_continuity=[],
        focal_arc=[FocalAssignment(section_id="drop", lead_target=lead)],
    )


def _event(group_id: str) -> RenderEvent:
    return RenderEvent(
        event_id=f"event-{group_id}",
        start_ms=0,
        end_ms=4_400,
        effect_type="On",
        palette=ResolvedPalette(colors=["#E53935", "#43A047", "#F5F1E8"], active_slots=[1, 2, 3]),
        intensity=0.7,
        source=RenderEventSource(
            section_id="drop",
            lane=LaneKind.BASE,
            group_id=group_id,
            template_id="recipe",
        ),
    )


def _render_plan(*group_ids: str) -> RenderPlan:
    return RenderPlan(
        render_id="render",
        duration_ms=4_400,
        groups=[
            RenderGroupPlan(
                element_name=group_id,
                layers=[
                    RenderLayerPlan(
                        layer_index=0,
                        layer_role=LaneKind.BASE,
                        events=[_event(group_id)],
                    )
                ],
            )
            for group_id in group_ids
        ],
    )


def _render_plan_with_counts(counts: dict[str, int]) -> RenderPlan:
    plan = _render_plan(*counts)
    groups = []
    for group in plan.groups:
        count = counts[group.element_name]
        event = group.layers[0].events[0]
        events = [
            event.model_copy(update={"event_id": f"{event.event_id}-{index}"}, deep=True)
            for index in range(count)
        ]
        groups.append(
            group.model_copy(
                update={
                    "layers": [group.layers[0].model_copy(update={"events": events}, deep=True)]
                },
                deep=True,
            )
        )
    return plan.model_copy(update={"groups": groups}, deep=True)


def _two_section_macro() -> MacroPlan:
    first = _macro()
    lead = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    chorus = first.sections[0].model_copy(
        update={
            "section": SongSectionRef(
                section_id="chorus", name="Chorus", start_ms=4_400, end_ms=8_800
            )
        },
        deep=True,
    )
    return first.model_copy(
        update={
            "sections": [first.sections[0], chorus],
            "focal_arc": [
                first.focal_arc[0],
                FocalAssignment(section_id="chorus", lead_target=lead),
            ],
        },
        deep=True,
    )


def _mh_plan(template_id: str = "sweep_lr_fan_hold") -> ChoreographyPlan:
    return ChoreographyPlan(
        sections=[
            PlanSection(
                section_name="drop",
                start_bar=1,
                end_bar=2,
                template_id=template_id,
                intensity=Intensity.SMOOTH,
            )
        ],
        overall_strategy="fixture",
    )


def _mh_segment() -> FixtureSegment:
    return FixtureSegment(
        section_id="drop",
        segment_id="mh",
        step_id="sweep",
        template_id="sweep_lr_fan_hold",
        fixture_id="MH1",
        t0_ms=0,
        t1_ms=4_400,
        channels={ChannelName.DIMMER: ChannelValue(channel=ChannelName.DIMMER, static_dmx=200)},
    )


def _ranges(plan: RenderPlan, group_id: str) -> list[tuple[int, int]]:
    group = next(item for item in plan.groups if item.element_name == group_id)
    return [(event.start_ms, event.end_ms) for layer in group.layers for event in layer.events]


def test_focal_roles_change_emitted_display_intensity() -> None:
    coordinated = coordinate_display_render_plan(
        _render_plan("MEGA_TREE", "ARCH_LEFT", "ARCH_RIGHT"),
        _macro(),
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    intensity = {
        group.element_name: sum(event.intensity for layer in group.layers for event in layer.events)
        for group in coordinated.groups
    }
    assert intensity["MEGA_TREE"] > intensity["ARCH_LEFT"] > intensity["ARCH_RIGHT"]


def test_focal_role_budgets_dominate_with_unequal_event_counts() -> None:
    coordinated = coordinate_display_render_plan(
        _render_plan_with_counts({"MEGA_TREE": 1, "ARCH_LEFT": 3, "ARCH_RIGHT": 10}),
        _macro(),
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    activation = {
        group.element_name: sum(
            event.intensity * (event.end_ms - event.start_ms)
            for layer in group.layers
            for event in layer.events
        )
        for group in coordinated.groups
    }
    assert activation["MEGA_TREE"] > activation["ARCH_LEFT"] > activation["ARCH_RIGHT"]


@pytest.mark.parametrize("support_event_count", [2, 7, 100])
def test_focal_role_budget_is_per_concrete_target_with_unequal_support_counts(
    support_event_count: int,
) -> None:
    macro = _macro(
        roles=[
            FocalRole(
                target=PlanTarget(type=TargetType.GROUP, id="MEGA_TREE"),
                role=FocalRoleKind.LEAD,
            ),
            FocalRole(
                target=PlanTarget(type=TargetType.GROUP, id="ARCH_LEFT"),
                role=FocalRoleKind.SUPPORT,
            ),
            FocalRole(
                target=PlanTarget(type=TargetType.GROUP, id="WINDOWS"),
                role=FocalRoleKind.SUPPORT,
            ),
            FocalRole(
                target=PlanTarget(type=TargetType.GROUP, id="ARCH_RIGHT"),
                role=FocalRoleKind.REST,
            ),
        ]
    )
    coordinated = coordinate_display_render_plan(
        _render_plan_with_counts(
            {
                "MEGA_TREE": 1,
                "ARCH_LEFT": 1,
                "WINDOWS": support_event_count,
                "ARCH_RIGHT": 10,
            }
        ),
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    activation = {
        group.element_name: sum(
            event.intensity * (event.end_ms - event.start_ms)
            for layer in group.layers
            for event in layer.events
        )
        for group in coordinated.groups
    }

    assert activation["MEGA_TREE"] > activation["ARCH_LEFT"]
    assert activation["MEGA_TREE"] > activation["WINDOWS"]
    assert activation["ARCH_LEFT"] == pytest.approx(activation["WINDOWS"])
    assert activation["ARCH_LEFT"] > activation["ARCH_RIGHT"]
    assert activation["MEGA_TREE"] / activation["ARCH_LEFT"] == pytest.approx(1.0 / 0.65)
    assert activation["ARCH_LEFT"] / activation["ARCH_RIGHT"] == pytest.approx(0.65 / 0.15)
    assert (
        coordinate_display_render_plan(
            coordinated,
            macro,
            _grid(),
            _graph(),
            moving_head_target_ids={"MOVING_HEADS"},
        )
        == coordinated
    )


def test_sparse_focal_roles_preserve_unmentioned_display_and_mh_as_support() -> None:
    lead = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    macro = _macro(roles=[FocalRole(target=lead, role=FocalRoleKind.LEAD)])
    display = coordinate_display_render_plan(
        _render_plan("MEGA_TREE", "ARCH_LEFT", "ARCH_RIGHT"),
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    mh = coordinate_moving_head_segments(
        [_mh_segment()],
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert {group.element_name for group in display.groups} == {
        "MEGA_TREE",
        "ARCH_LEFT",
        "ARCH_RIGHT",
    }
    assert _ranges(display, "ARCH_LEFT") == [(0, 4_400)]
    assert [(segment.t0_ms, segment.t1_ms) for segment in mh] == [(0, 4_400)]


def test_cross_part_call_response_uses_typed_teams_and_irregular_grid() -> None:
    house = PlanTarget(type=TargetType.ZONE, id=ChoreoTag.HOUSE.value)
    moving_heads = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    roles = [
        FocalRole(target=house, role=FocalRoleKind.LEAD),
        FocalRole(target=moving_heads, role=FocalRoleKind.SUPPORT),
    ]
    macro = _macro(
        mode=CoordinationMode.CALL_RESPONSE,
        roles=roles,
        pairs=[
            CallResponsePair(
                call=house,
                response=moving_heads,
                step_unit=StepUnit.BEAT,
                step_duration=1,
            )
        ],
    )

    display = coordinate_display_render_plan(
        _render_plan("ARCH_LEFT", "ARCH_RIGHT"),
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    mh = coordinate_moving_head_segments(
        [_mh_segment()],
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert _ranges(display, "ARCH_LEFT") == _ranges(display, "ARCH_RIGHT")
    assert _ranges(display, "ARCH_LEFT")[:2] == [(0, 500), (1_100, 1_600)]
    assert [(item.t0_ms, item.t1_ms) for item in mh][:2] == [(500, 1_100), (1_600, 2_200)]
    assert all(
        call_end <= response_start or response_end <= call_start
        for call_start, call_end in _ranges(display, "ARCH_LEFT")
        for response_start, response_end in [(item.t0_ms, item.t1_ms) for item in mh]
    )


def test_narrow_pair_preserves_unpaired_display_groups() -> None:
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    mh_target = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    macro = _macro(
        mode=CoordinationMode.CALL_RESPONSE,
        roles=[
            FocalRole(target=tree, role=FocalRoleKind.LEAD),
            FocalRole(target=mh_target, role=FocalRoleKind.SUPPORT),
        ],
        pairs=[
            CallResponsePair(
                call=tree,
                response=mh_target,
                step_unit=StepUnit.BEAT,
                step_duration=1,
            )
        ],
    )
    display = coordinate_display_render_plan(
        _render_plan("MEGA_TREE", "ARCH_LEFT", "ARCH_RIGHT"),
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert _ranges(display, "ARCH_LEFT") == [(0, 4_400)]
    assert _ranges(display, "ARCH_RIGHT") == [(0, 4_400)]


@pytest.mark.parametrize(
    "mode",
    [
        CoordinationMode.UNIFIED,
        CoordinationMode.SEQUENCED,
        CoordinationMode.RIPPLE,
        CoordinationMode.COMPLEMENTARY,
    ],
)
def test_call_response_pairs_are_rejected_outside_call_response_mode(
    mode: CoordinationMode,
) -> None:
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    mh_target = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    macro = _macro(
        mode=mode,
        pairs=[
            CallResponsePair(
                call=tree,
                response=mh_target,
                step_unit=StepUnit.BEAT,
                step_duration=1,
            )
        ],
    )

    with pytest.raises(ValueError, match="only valid with CALL_RESPONSE"):
        coordination_schedule(macro, _grid(), _graph())


def test_call_response_mode_requires_a_typed_pair() -> None:
    macro = _macro(mode=CoordinationMode.CALL_RESPONSE, pairs=[])

    with pytest.raises(ValueError, match="requires at least one typed pair"):
        coordination_schedule(macro, _grid(), _graph())


@pytest.mark.parametrize(
    ("step_unit", "step_duration"),
    [(StepUnit.BEAT, 8), (StepUnit.BAR, 2), (StepUnit.PHRASE, 1)],
)
def test_short_call_response_fails_when_both_phases_do_not_fit(
    step_unit: StepUnit, step_duration: int
) -> None:
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    mh_target = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    macro = _macro(
        mode=CoordinationMode.CALL_RESPONSE,
        pairs=[
            CallResponsePair(
                call=tree,
                response=mh_target,
                step_unit=step_unit,
                step_duration=step_duration,
            )
        ],
    )
    with pytest.raises(ValueError, match="both call and response phases"):
        coordinate_moving_head_segments(
            [_mh_segment()],
            macro,
            _grid(),
            _graph(),
            moving_head_target_ids={"MOVING_HEADS"},
        )


@pytest.mark.parametrize(
    ("step_unit", "bars"),
    [(StepUnit.BEAT, 1), (StepUnit.BAR, 2), (StepUnit.PHRASE, 8)],
)
def test_call_response_units_clip_both_phases_to_section(step_unit: StepUnit, bars: int) -> None:
    end_ms = bars * 2_200
    beats = [float(value) for value in range(0, end_ms + 1, 550)]
    grid = BeatGrid(
        bar_boundaries=[float(value) for value in range(0, end_ms + 1, 2_200)],
        beat_boundaries=beats,
        eighth_boundaries=beats,
        sixteenth_boundaries=beats,
        tempo_bpm=109.0,
        beats_per_bar=4,
        duration_ms=end_ms,
    )
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    mh_target = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    source = _macro(
        mode=CoordinationMode.CALL_RESPONSE,
        pairs=[
            CallResponsePair(
                call=tree,
                response=mh_target,
                step_unit=step_unit,
                step_duration=1,
            )
        ],
    )
    section = source.sections[0].model_copy(
        update={
            "section": SongSectionRef(section_id="drop", name="Drop", start_ms=0, end_ms=end_ms)
        },
        deep=True,
    )
    macro = source.model_copy(update={"sections": [section]}, deep=True)

    paired = [
        window
        for window in coordination_schedule(macro, grid, _graph())
        if window.phase in {"call", "response"}
    ]

    assert {window.phase for window in paired} == {"call", "response"}
    assert paired[0].phase == "call"
    assert all(0 <= window.start_ms < window.end_ms <= end_ms for window in paired)


def test_coordination_mode_changes_emitted_timing_without_reselecting_mh_template() -> None:
    roles = [
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="MEGA_TREE"),
            role=FocalRoleKind.LEAD,
        ),
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="ARCH_LEFT"),
            role=FocalRoleKind.SUPPORT,
        ),
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="ARCH_RIGHT"),
            role=FocalRoleKind.REST,
        ),
        FocalRole(
            target=PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS"),
            role=FocalRoleKind.SUPPORT,
        ),
    ]
    unified_macro = _macro(mode=CoordinationMode.UNIFIED, roles=roles)
    sequenced_macro = _macro(mode=CoordinationMode.SEQUENCED, roles=roles)
    display_source = _render_plan("MEGA_TREE", "ARCH_LEFT", "ARCH_RIGHT")

    unified_display = coordinate_display_render_plan(
        display_source,
        unified_macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    sequenced_display = coordinate_display_render_plan(
        display_source,
        sequenced_macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    unified_mh = coordinate_moving_head_segments(
        [_mh_segment()],
        unified_macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    sequenced_mh = coordinate_moving_head_segments(
        [_mh_segment()],
        sequenced_macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert _ranges(unified_display, "MEGA_TREE") != _ranges(sequenced_display, "MEGA_TREE")
    assert [(item.t0_ms, item.t1_ms) for item in unified_mh] != [
        (item.t0_ms, item.t1_ms) for item in sequenced_mh
    ]
    assert {item.template_id for item in unified_mh + sequenced_mh} == {"sweep_lr_fan_hold"}


def test_shared_palette_stop_resolves_mh_color_from_display_primary() -> None:
    coordinated = coordinate_moving_head_plan(
        _mh_plan(),
        _macro(),
        _grid(),
        {"MOVING_HEADS"},
        ["sweep_lr_fan_hold"],
    )
    section = coordinated.sections[0]
    assert section.color_intent.explicit_color is not None
    assert section.color_intent.explicit_color.value == "red"
    assert not section.legacy_intent_omitted
    assert _event("MEGA_TREE").palette.colors[0] == "#E53935"


def test_flattened_segment_and_generated_transition_ids_map_to_macro_sections() -> None:
    macro = _two_section_macro()
    grid = BeatGrid(
        bar_boundaries=[0.0, 2_200.0, 4_400.0, 6_600.0, 8_800.0],
        beat_boundaries=[float(value) for value in range(0, 8_801, 550)],
        eighth_boundaries=[float(value) for value in range(0, 8_801, 550)],
        sixteenth_boundaries=[float(value) for value in range(0, 8_801, 550)],
        tempo_bpm=109.0,
        beats_per_bar=4,
        duration_ms=8_800,
    )
    flattened = _mh_segment().model_copy(
        update={"section_id": "drop|segment-a", "t1_ms": 4_400}, deep=True
    )
    transition = _mh_segment().model_copy(
        update={
            "section_id": "transition_drop|segment-a_to_chorus",
            "segment_id": "trans_drop|segment-a_to_chorus",
            "t0_ms": 4_200,
            "t1_ms": 4_600,
            "metadata": {
                "is_transition": "true",
                "source_id": "drop|segment-a",
                "target_id": "chorus",
            },
        },
        deep=True,
    )

    coordinated = coordinate_moving_head_segments(
        [flattened, transition],
        macro,
        grid,
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert any(segment.section_id == "drop|segment-a" for segment in coordinated)
    assert any(segment.metadata.get("is_transition") == "true" for segment in coordinated)


def test_repeated_call_response_target_fails_closed() -> None:
    mh = PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS")
    tree = PlanTarget(type=TargetType.GROUP, id="MEGA_TREE")
    arch = PlanTarget(type=TargetType.GROUP, id="ARCH_LEFT")
    macro = _macro(
        mode=CoordinationMode.CALL_RESPONSE,
        pairs=[
            CallResponsePair(call=tree, response=mh, step_unit=StepUnit.BEAT, step_duration=1),
            CallResponsePair(call=arch, response=mh, step_unit=StepUnit.BAR, step_duration=1),
        ],
    )

    try:
        validate_macro_coordination(macro, _graph())
    except ValueError as error:
        assert "more than one call/response pair" in str(error)
    else:  # pragma: no cover - assertion branch
        raise AssertionError("contradictory target reuse must fail closed")


def test_coordination_normalization_is_idempotent_for_cached_branch_outputs() -> None:
    macro = _macro(mode=CoordinationMode.SEQUENCED)
    first_display = coordinate_display_render_plan(
        _render_plan("MEGA_TREE", "ARCH_LEFT", "ARCH_RIGHT"),
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    second_display = coordinate_display_render_plan(
        first_display,
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    first_mh = coordinate_moving_head_segments(
        [_mh_segment()],
        _macro(
            mode=CoordinationMode.SEQUENCED,
            roles=[
                FocalRole(
                    target=PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS"),
                    role=FocalRoleKind.LEAD,
                )
            ],
        ),
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    second_mh = coordinate_moving_head_segments(
        first_mh,
        _macro(
            mode=CoordinationMode.SEQUENCED,
            roles=[
                FocalRole(
                    target=PlanTarget(type=TargetType.GROUP, id="MOVING_HEADS"),
                    role=FocalRoleKind.LEAD,
                )
            ],
        ),
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )

    assert second_display == first_display
    assert second_mh == first_mh


@pytest.mark.parametrize(
    "template_id",
    ["local|coord-7-recipe", "fe-promoted|coord-0", "tracked|coord-123-middle"],
)
def test_raw_recipe_ids_containing_coord_marker_are_still_coordinated(
    template_id: str,
) -> None:
    source = _render_plan("MEGA_TREE")
    raw_event = source.groups[0].layers[0].events[0]
    compiler_style_id = f"recipe_{template_id}_0_{'a' * 64}"
    raw_event = raw_event.model_copy(
        update={
            "event_id": compiler_style_id,
            "source": raw_event.source.model_copy(update={"template_id": template_id}),
        },
        deep=True,
    )
    source = source.model_copy(
        update={
            "groups": [
                source.groups[0].model_copy(
                    update={
                        "layers": [
                            source.groups[0]
                            .layers[0]
                            .model_copy(update={"events": [raw_event]}, deep=True)
                        ]
                    },
                    deep=True,
                )
            ]
        },
        deep=True,
    )
    macro = _macro(mode=CoordinationMode.SEQUENCED)

    first = coordinate_display_render_plan(
        source,
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    second = coordinate_display_render_plan(
        first,
        macro,
        _grid(),
        _graph(),
        moving_head_target_ids={"MOVING_HEADS"},
    )
    emitted = first.groups[0].layers[0].events

    assert emitted
    assert all(event.end_ms - event.start_ms < 4_400 for event in emitted)
    assert all(re.search(r"\|coord-\d+$", event.event_id) for event in emitted)
    assert second == first
