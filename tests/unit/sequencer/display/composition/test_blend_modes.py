"""P3-T2 contract tests for lane blend-mode propagation."""

from __future__ import annotations

from types import SimpleNamespace

from twinklr.core.sequencer.display.composition.models import CompiledEffect
from twinklr.core.sequencer.display.composition.template_compiler import TemplateCompileContext
from twinklr.core.sequencer.display.export.writer import XSQWriter
from twinklr.core.sequencer.display.models.render_event import RenderEvent, RenderEventSource
from twinklr.core.sequencer.planning.group_plan import (
    GroupPlanSet,
    LanePlan,
    SectionCoordinationPlan,
)
from twinklr.core.sequencer.templates.group.models.coordination import (
    CoordinationPlan,
    GroupPlacement,
    PlanTarget,
)
from twinklr.core.sequencer.theming import ThemeRef
from twinklr.core.sequencer.theming.enums import ThemeScope
from twinklr.core.sequencer.vocabulary import (
    CoordinationMode,
    EffectDuration,
    GPBlendMode,
    LaneKind,
    PlanningTimeRef,
    TargetType,
    VisualDepth,
)

from .p3_t1_fixtures import make_engine


class _BlendCompiler:
    """Emit predictable depths and deliberately conflicting recipe blend modes."""

    def compile(
        self,
        placement: GroupPlacement,
        context: TemplateCompileContext,
    ) -> list[CompiledEffect]:
        depths = (
            [VisualDepth.BACKGROUND, VisualDepth.FOREGROUND]
            if placement.template_id == "two_depths"
            else [VisualDepth.FOREGROUND]
            if placement.template_id == "foreground"
            else [VisualDepth.BACKGROUND]
        )
        effects: list[CompiledEffect] = []
        for index, depth in enumerate(depths):
            event = RenderEvent(
                event_id=f"{placement.placement_id}_{index}",
                start_ms=context.start_ms,
                end_ms=context.end_ms,
                effect_type="On",
                palette=context.palette,
                source=RenderEventSource(
                    section_id=context.section_id,
                    lane=context.lane,
                    group_id=placement.target.id,
                    template_id=placement.template_id,
                    placement_id=placement.placement_id,
                    placement_index=context.placement_index,
                ),
            )
            effects.append(
                CompiledEffect(
                    event=event,
                    visual_depth=depth,
                    layer_blend_mode="Normal" if index == 0 else "1 reveals 2",
                )
            )
        return effects


def _placement(
    placement_id: str,
    lane: LaneKind,
    *,
    template_id: str = "background",
    bar: int = 1,
) -> tuple[LaneKind, GroupPlacement]:
    return lane, GroupPlacement(
        placement_id=placement_id,
        target=PlanTarget(type=TargetType.GROUP, id="G0"),
        template_id=template_id,
        start=PlanningTimeRef(bar=bar, beat=1),
        duration=EffectDuration.HIT,
    )


def _section(
    section_id: str,
    entries: list[tuple[LaneKind, GroupPlacement, GPBlendMode]],
) -> SectionCoordinationPlan:
    return SectionCoordinationPlan(
        section_id=section_id,
        theme=ThemeRef(theme_id="theme.test", scope=ThemeScope.SECTION),
        palette=None,
        lane_plans=[
            LanePlan(
                lane=lane,
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
            for lane, placement, blend_mode in entries
        ],
    )


def _compose(
    sections: list[SectionCoordinationPlan],
    *,
    catalog_index: dict[str, object] | None = None,
):
    engine = make_engine()
    engine._template_compiler = _BlendCompiler()
    engine._catalog_index = catalog_index or {}
    return engine.compose(GroupPlanSet(plan_set_id="blend-test", section_plans=sections))


def _emitted_layer_settings(plan, lane: LaneKind) -> str:
    group = plan.groups[0]
    for compact_index, layer in enumerate(group.layers):
        if layer.layer_role == lane:
            return XSQWriter._augment_settings(
                "",
                event=layer.events[0],
                layer_index=compact_index,
                blend_mode=layer.blend_mode,
            )
    raise AssertionError(f"No layer for {lane}")


def test_rhythm_lane_blend_mode_reaches_output() -> None:
    base_lane, base = _placement("base", LaneKind.BASE)
    rhythm_lane, rhythm = _placement("rhythm", LaneKind.RHYTHM)
    plan = _compose(
        [
            _section(
                "s1", [(base_lane, base, GPBlendMode.ADD), (rhythm_lane, rhythm, GPBlendMode.MAX)]
            )
        ]
    )

    assert "T_CHOICE_LayerMethod=Max" in _emitted_layer_settings(plan, LaneKind.RHYTHM)


def test_accent_lane_blend_mode_reaches_output() -> None:
    base_lane, base = _placement("base", LaneKind.BASE)
    accent_lane, accent = _placement("accent", LaneKind.ACCENT)
    plan = _compose(
        [
            _section(
                "s1",
                [(base_lane, base, GPBlendMode.ADD), (accent_lane, accent, GPBlendMode.ALPHA_OVER)],
            )
        ]
    )

    assert "T_CHOICE_LayerMethod=1 reveals 2" in _emitted_layer_settings(plan, LaneKind.ACCENT)


def test_lane_wins_precedence_is_uniform_across_lanes() -> None:
    """Lane blend wins over every recipe blend, independent of lane/depth/order."""
    _, base = _placement("base", LaneKind.BASE, template_id="two_depths")
    _, rhythm = _placement("rhythm", LaneKind.RHYTHM)
    _, accent = _placement("accent", LaneKind.ACCENT)
    plan = _compose(
        [
            _section(
                "s1",
                [
                    (LaneKind.ACCENT, accent, GPBlendMode.ALPHA_OVER),
                    (LaneKind.BASE, base, GPBlendMode.MAX),
                    (LaneKind.RHYTHM, rhythm, GPBlendMode.MAX),
                ],
            )
        ]
    )

    modes_by_lane = {
        lane: {layer.blend_mode for layer in plan.groups[0].layers if layer.layer_role == lane}
        for lane in LaneKind
    }
    assert modes_by_lane == {
        LaneKind.BASE: {"Max"},
        LaneKind.RHYTHM: {"Max"},
        LaneKind.ACCENT: {"1 reveals 2"},
    }


def test_no_cross_section_blend_contamination() -> None:
    _, rhythm = _placement("rhythm", LaneKind.RHYTHM)
    _, base_foreground = _placement("base-fg", LaneKind.BASE, template_id="foreground", bar=2)
    plan = _compose(
        [
            _section("s1", [(LaneKind.RHYTHM, rhythm, GPBlendMode.ALPHA_OVER)]),
            _section("s2", [(LaneKind.BASE, base_foreground, GPBlendMode.MAX)]),
        ]
    )

    base_layer = next(
        layer
        for layer in plan.groups[0].layers
        if layer.layer_role == LaneKind.BASE and layer.layer_index == 2
    )
    assert base_layer.blend_mode == "Max"


def test_unhonoured_lane_blend_mode_emits_diagnostic() -> None:
    _, rhythm = _placement("rhythm", LaneKind.RHYTHM)
    plan = _compose([_section("s1", [(LaneKind.RHYTHM, rhythm, GPBlendMode.MAX)])])

    assert any(
        diagnostic.level == "warning"
        and "cannot be honoured" in diagnostic.message
        and "emitted base layer" in diagnostic.message
        for diagnostic in plan.diagnostics
    )


def test_lane_wins_precedence_includes_asset_overlay() -> None:
    _, base = _placement("base", LaneKind.BASE)
    _, rhythm = _placement("rhythm", LaneKind.RHYTHM)
    rhythm = rhythm.model_copy(update={"resolved_asset_ids": ["asset-1"]})
    plan = _compose(
        [
            _section(
                "s1",
                [
                    (LaneKind.BASE, base, GPBlendMode.ADD),
                    (LaneKind.RHYTHM, rhythm, GPBlendMode.MAX),
                ],
            )
        ],
        catalog_index={"asset-1": SimpleNamespace(file_path="images/asset.png")},
    )

    rhythm_modes = {
        layer.blend_mode for layer in plan.groups[0].layers if layer.layer_role == LaneKind.RHYTHM
    }
    assert rhythm_modes == {"Max"}
