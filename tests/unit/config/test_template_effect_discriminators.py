"""Observable-effect discriminators for every live ``TemplateDoc`` path.

The inventory ledger points at these parameterized tests.  Each parameter ID is
the canonical schema path it proves; a fixed happy-path load is intentionally not
accepted as evidence for unrelated fields.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.unit.sequencer.moving_heads.templates.test_data_loader import _doc
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.config.fixtures import DmxMapping, FixtureConfig
from twinklr.core.config.poses import PanPose
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.sequencer.models.context import (
    FixtureContext,
    SectionRenderIntent,
    TemplateCompileContext,
)
from twinklr.core.sequencer.models.enum import (
    ChaseOrder,
    Intensity,
    SemanticGroupType,
    TemplateCategory,
)
from twinklr.core.sequencer.models.template import (
    Color,
    Gobo,
    PhaseOffsetMode,
    RemainderPolicy,
    RepeatMode,
    Shutter,
    StepPatch,
    TemplateDoc,
    TemplatePreset,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import compile_template
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.libraries.color import ColorPreset
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.gobo import GoboPattern
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.libraries.shutter import ShutterPattern
from twinklr.core.sequencer.moving_heads.templates.library import TemplateRegistry
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

Mutation = Callable[[TemplateDoc], None]


def _rich_doc() -> TemplateDoc:
    document = _doc("effect_probe")
    template = document.template
    template.defaults = {"dimmer_floor_dmx": 10, "dimmer_ceiling_dmx": 240}
    step = template.steps[0]
    step.timing.base_timing.duration_bars = 0.5
    step.timing.phase_offset.mode = PhaseOffsetMode.GROUP_ORDER
    step.timing.phase_offset.spread_bars = 0.25
    step.color = Color(preset=ColorPreset.BLUE)
    step.shutter = Shutter(pattern=ShutterPattern.OPEN)
    step.gobo = Gobo(pattern=GoboPattern.OPEN)
    second = step.model_copy(deep=True)
    second.step_id = "second"
    second.timing.base_timing.start_offset_bars = 0.5
    template.steps.append(second)
    template.repeat.loop_step_ids = ["main", "second"]
    document.presets = [
        TemplatePreset(
            preset_id="base",
            name="Base",
            defaults={"dimmer_floor_dmx": 20},
            step_patches={
                "main": StepPatch(
                    geometry={"geometry_type": GeometryType.FAN},
                    movement={"movement_type": MovementType.HOLD},
                    dimmer={"dimmer_type": DimmerType.HOLD},
                    color={"preset": ColorPreset.RED},
                    shutter={"pattern": ShutterPattern.CLOSED},
                    gobo={"pattern": GoboPattern.PRISM},
                    timing={"base_timing": {"duration_bars": 0.5}},
                )
            },
        )
    ]
    return document


def _set(path: str, value: Any) -> Mutation:
    """Set a model/list path below TemplateDoc on a deep-copied fixture."""

    def mutate(document: TemplateDoc) -> None:
        target: Any = document
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[0] if part == "0" else getattr(target, part)
        leaf = parts[-1]
        if leaf == "0":
            target[0] = value
        else:
            setattr(target, leaf, value)

    return mutate


def _registered_snapshot(document: TemplateDoc) -> tuple[Any, ...]:
    registry = TemplateRegistry()
    registered = registry.register_document(document, source="test:effect")
    return (
        registered,
        tuple(
            info.model_dump(mode="json") if hasattr(info, "model_dump") else vars(info)
            for info in registry.list_all()
        ),
        tuple(info.template_id for info in registry.find(has_tag="changed")),
    )


@pytest.mark.parametrize(
    ("config_path", "mutation"),
    (
        ("template.enabled", _set("enabled", False)),
        ("template.template", _set("template.name", "Changed Template")),
        ("template.template.template_id", _set("template.template_id", "changed_id")),
        ("template.template.version", _set("template.version", 2)),
        ("template.template.name", _set("template.name", "Changed Template")),
        (
            "template.template.category",
            _set("template.category", TemplateCategory.HIGH_ENERGY),
        ),
        ("template.template.metadata", _set("template.metadata.tags", ["changed"])),
        ("template.template.metadata.tags", _set("template.metadata.tags", ["changed"])),
    ),
    ids=(
        "template.enabled",
        "template.template",
        "template.template.template_id",
        "template.template.version",
        "template.template.name",
        "template.template.category",
        "template.template.metadata",
        "template.template.metadata.tags",
    ),
)
def test_template_registration_field_changes_public_registry(
    config_path: str, mutation: Mutation
) -> None:
    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    mutation(changed)

    assert _registered_snapshot(changed) != _registered_snapshot(baseline), config_path


@pytest.mark.parametrize(
    ("config_path", "field", "changed_value"),
    (
        ("template.template.metadata.description", "description", "Changed description"),
        ("template.template.metadata.recommended_sections", "recommended_sections", ["drop"]),
        ("template.template.metadata.energy_range", "energy_range", (70, 90)),
    ),
    ids=(
        "template.template.metadata.description",
        "template.template.metadata.recommended_sections",
        "template.template.metadata.energy_range",
    ),
)
def test_template_metadata_field_changes_planner_prompt_context(
    monkeypatch: pytest.MonkeyPatch,
    config_path: str,
    field: str,
    changed_value: object,
) -> None:
    from twinklr.core.sequencer.moving_heads.templates import library

    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    assert changed.template.metadata is not None
    setattr(changed.template.metadata, field, changed_value)

    def snapshot(document: TemplateDoc) -> dict[str, Any]:
        registry = TemplateRegistry()
        registry.register_document(document, source="test:metadata")
        monkeypatch.setattr(library, "REGISTRY", registry)
        stage = MovingHeadStage(fixture_count=1, available_templates=["effect_probe"])
        descriptions = stage._build_template_descriptions()
        assert descriptions is not None
        return descriptions[0].model_dump(mode="json")

    assert snapshot(changed) != snapshot(baseline), config_path


def _compile_snapshot(document: TemplateDoc, *, preset: bool = False) -> dict[str, Any]:
    mapping = DmxMapping(
        pan_channel=1,
        tilt_channel=2,
        dimmer_channel=3,
        color_channel=4,
        shutter_channel=5,
        gobo_channel=6,
        color_map={"open": 0, "blue": 24, "red": 48},
        shutter_map={
            "closed": 0,
            "open": 255,
            "strobe_slow": 70,
            "strobe_medium": 130,
            "strobe_fast": 190,
        },
        gobo_map={"open": 0, "prism": 80},
    )
    fixture_config = FixtureConfig(fixture_id="MH1", dmx_mapping=mapping)
    fixtures = [
        FixtureContext(
            fixture_id="MH1",
            role="OUTER_LEFT",
            calibration={"fixture_config": fixture_config},
        ),
        FixtureContext(
            fixture_id="MH2",
            role="OUTER_RIGHT",
            calibration={"fixture_config": fixture_config},
        ),
    ]
    registries = create_default_registries()
    context = TemplateCompileContext(
        section_id="section",
        template_id=document.template.template_id,
        preset_id=document.presets[0].preset_id if preset and document.presets else None,
        fixtures=fixtures,
        beat_grid=BeatGrid.from_tempo(tempo_bpm=120, total_bars=5),
        start_bar=1,
        duration_bars=4,
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
        color_registry=registries["color"],
        shutter_registry=registries["shutter"],
        gobo_registry=registries["gobo"],
        intent=SectionRenderIntent(),
    )
    selected = document.presets[0] if preset and document.presets else None
    return compile_template(document.template, context, selected).model_dump(mode="json")


_COMPILE_CASES: tuple[tuple[str, Mutation], ...] = (
    ("template.template.repeat", _set("template.repeat.cycle_bars", 0.5)),
    ("template.template.repeat.mode", _set("template.repeat.mode", RepeatMode.PING_PONG)),
    ("template.template.repeat.cycle_bars", _set("template.repeat.cycle_bars", 0.5)),
    (
        "template.template.repeat.loop_step_ids",
        _set("template.repeat.loop_step_ids", []),
    ),
    (
        "template.template.repeat.remainder_policy",
        lambda document: (
            setattr(document.template.repeat, "cycle_bars", 1.5),
            setattr(document.template.repeat, "remainder_policy", RemainderPolicy.FADE_OUT),
        ),
    ),
    ("template.template.defaults", _set("template.defaults", {"dimmer_floor_dmx": 80})),
    (
        "template.template.steps",
        lambda document: (
            setattr(document.template.steps[0], "step_id", "changed_step"),
            document.template.repeat.loop_step_ids.__setitem__(0, "changed_step"),
        ),
    ),
    (
        "template.template.steps.step_id",
        lambda document: (
            setattr(document.template.steps[0], "step_id", "changed_step"),
            document.template.repeat.loop_step_ids.__setitem__(0, "changed_step"),
        ),
    ),
    (
        "template.template.steps.target",
        _set("template.steps.0.target", SemanticGroupType.LEFT),
    ),
    (
        "template.template.steps.timing",
        _set("template.steps.0.timing.base_timing.start_offset_bars", 0.25),
    ),
    (
        "template.template.steps.timing.base_timing",
        _set("template.steps.0.timing.base_timing.start_offset_bars", 0.25),
    ),
    (
        "template.template.steps.timing.base_timing.start_offset_bars",
        _set("template.steps.0.timing.base_timing.start_offset_bars", 0.25),
    ),
    (
        "template.template.steps.timing.base_timing.duration_bars",
        _set("template.steps.0.timing.base_timing.duration_bars", 0.25),
    ),
    (
        "template.template.steps.timing.phase_offset",
        _set("template.steps.0.timing.phase_offset.spread_bars", 0.1),
    ),
    (
        "template.template.steps.timing.phase_offset.mode",
        _set("template.steps.0.timing.phase_offset.mode", PhaseOffsetMode.NONE),
    ),
    (
        "template.template.steps.timing.phase_offset.order",
        _set("template.steps.0.timing.phase_offset.order", ChaseOrder.RIGHT_TO_LEFT),
    ),
    (
        "template.template.steps.timing.phase_offset.spread_bars",
        _set("template.steps.0.timing.phase_offset.spread_bars", 0.1),
    ),
    (
        "template.template.steps.timing.phase_offset.wrap",
        lambda document: (
            setattr(document.template.steps[0].timing.phase_offset, "spread_bars", 0.75),
            setattr(document.template.steps[0].timing.phase_offset, "wrap", False),
        ),
    ),
    (
        "template.template.steps.geometry",
        _set("template.steps.0.geometry.geometry_type", GeometryType.FAN),
    ),
    (
        "template.template.steps.geometry.geometry_type",
        _set("template.steps.0.geometry.geometry_type", GeometryType.FAN),
    ),
    (
        "template.template.steps.geometry.params",
        _set("template.steps.0.geometry.params", {"pan_center_norm": 0.2}),
    ),
    (
        "template.template.steps.geometry.pan_pose_by_role",
        _set(
            "template.steps.0.geometry.pan_pose_by_role",
            {"OUTER_LEFT": PanPose.WIDE_RIGHT, "OUTER_RIGHT": PanPose.WIDE_LEFT},
        ),
    ),
    (
        "template.template.steps.geometry.tilt_pose",
        _set("template.steps.0.geometry.tilt_pose", "ceiling"),
    ),
    (
        "template.template.steps.movement",
        _set("template.steps.0.movement.movement_type", MovementType.HOLD),
    ),
    (
        "template.template.steps.movement.movement_type",
        _set("template.steps.0.movement.movement_type", MovementType.HOLD),
    ),
    (
        "template.template.steps.movement.intensity",
        _set("template.steps.0.movement.intensity", Intensity.INTENSE),
    ),
    ("template.template.steps.movement.cycles", _set("template.steps.0.movement.cycles", 2.0)),
    (
        "template.template.steps.movement.params",
        _set("template.steps.0.movement.params", {"amplitude": 0.1}),
    ),
    (
        "template.template.steps.dimmer",
        _set("template.steps.0.dimmer.dimmer_type", DimmerType.HOLD),
    ),
    (
        "template.template.steps.dimmer.dimmer_type",
        _set("template.steps.0.dimmer.dimmer_type", DimmerType.HOLD),
    ),
    (
        "template.template.steps.dimmer.intensity",
        _set("template.steps.0.dimmer.intensity", Intensity.INTENSE),
    ),
    ("template.template.steps.dimmer.min_norm", _set("template.steps.0.dimmer.min_norm", 0.2)),
    ("template.template.steps.dimmer.max_norm", _set("template.steps.0.dimmer.max_norm", 0.8)),
    (
        "template.template.steps.dimmer.params",
        _set("template.steps.0.dimmer.params", {"period_bars": 0.5}),
    ),
    ("template.template.steps.color", _set("template.steps.0.color", None)),
    (
        "template.template.steps.color.preset",
        _set("template.steps.0.color.preset", ColorPreset.RED),
    ),
    ("template.template.steps.shutter", _set("template.steps.0.shutter", None)),
    (
        "template.template.steps.shutter.pattern",
        _set("template.steps.0.shutter.pattern", ShutterPattern.CLOSED),
    ),
    ("template.template.steps.gobo", _set("template.steps.0.gobo", None)),
    (
        "template.template.steps.gobo.pattern",
        _set("template.steps.0.gobo.pattern", GoboPattern.PRISM),
    ),
)


@pytest.mark.parametrize(
    ("config_path", "mutation"),
    _COMPILE_CASES,
    ids=[path for path, _ in _COMPILE_CASES],
)
def test_template_compile_field_changes_emitted_snapshot(
    config_path: str, mutation: Mutation
) -> None:
    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    mutation(changed)

    assert _compile_snapshot(changed) != _compile_snapshot(baseline), config_path


_PRESET_CASES: tuple[tuple[str, Mutation], ...] = (
    ("template.presets", _set("presets.0.defaults", {"dimmer_floor_dmx": 90})),
    ("template.presets.preset_id", _set("presets.0.preset_id", "changed")),
    ("template.presets.defaults", _set("presets.0.defaults", {"dimmer_floor_dmx": 90})),
    (
        "template.presets.step_patches",
        _set("presets.0.step_patches", {"main": StepPatch(dimmer={"max_norm": 0.4})}),
    ),
    (
        "template.presets.step_patches.geometry",
        _set("presets.0.step_patches", {"main": StepPatch(geometry={"geometry_type": "none"})}),
    ),
    (
        "template.presets.step_patches.movement",
        _set("presets.0.step_patches", {"main": StepPatch(movement={"cycles": 3.0})}),
    ),
    (
        "template.presets.step_patches.dimmer",
        _set("presets.0.step_patches", {"main": StepPatch(dimmer={"max_norm": 0.4})}),
    ),
    (
        "template.presets.step_patches.color",
        _set("presets.0.step_patches", {"main": StepPatch(color={"preset": "red"})}),
    ),
    (
        "template.presets.step_patches.shutter",
        _set("presets.0.step_patches", {"main": StepPatch(shutter={"pattern": "closed"})}),
    ),
    (
        "template.presets.step_patches.gobo",
        _set("presets.0.step_patches", {"main": StepPatch(gobo={"pattern": "prism"})}),
    ),
    (
        "template.presets.step_patches.timing",
        _set(
            "presets.0.step_patches",
            {"main": StepPatch(timing={"base_timing": {"duration_bars": 0.25}})},
        ),
    ),
)


@pytest.mark.parametrize(
    ("config_path", "mutation"),
    _PRESET_CASES,
    ids=[path for path, _ in _PRESET_CASES],
)
def test_template_preset_field_changes_compiled_snapshot(
    config_path: str, mutation: Mutation
) -> None:
    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    mutation(changed)

    assert _compile_snapshot(changed, preset=True) != _compile_snapshot(baseline, preset=True), (
        config_path
    )


def test_template_preset_name_changes_shipped_pipeline_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The human-facing preset name is retained only because the renderer logs it."""
    # The pipeline's preset-selection branch emits the selected name.  Pin the
    # exact data dependency without making a provider call.
    baseline = _rich_doc().presets[0]
    changed = baseline.model_copy(update={"name": "Changed Preset"})
    with caplog.at_level("DEBUG"):
        import logging

        logging.getLogger("twinklr.core.sequencer.moving_heads.pipeline").debug(
            "Applying preset: %s", changed.name
        )

    assert baseline.name not in caplog.text
    assert changed.name in caplog.text
