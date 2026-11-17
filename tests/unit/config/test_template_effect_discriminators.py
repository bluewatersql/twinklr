"""Observable-effect discriminators for every live ``TemplateDoc`` path.

The inventory ledger points at these parameterized tests.  Each parameter ID is
the canonical schema path it proves; a fixed happy-path load is intentionally not
accepted as evidence for unrelated fields.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.support.moving_heads import (
    bars_grid,
    hold_step,
    loop_template_doc,
    p1_rig,
    sweep_step,
)
from twinklr.core.agents.sequencer.moving_heads.stage import MovingHeadStage
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import SemanticGroupType, TemplateCategory
from twinklr.core.sequencer.models.moving_heads.physical import PhysicalChannelError
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.template import (
    DimmerPulse,
    RemainderPolicy,
    RepeatMode,
    StepPatch,
    TemplateDoc,
    TemplatePreset,
)
from twinklr.core.sequencer.moving_heads.compile.step import CompileError
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_template,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import cue_limits
from twinklr.core.sequencer.moving_heads.templates.library import TemplateRegistry
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

Mutation = Callable[[TemplateDoc], None]


def _rich_doc() -> TemplateDoc:
    """Two steps over a one-bar cycle, and a preset patching the first."""
    document = loop_template_doc(
        "effect_probe",
        [
            sweep_step("main", -20.0, 40.0, duration=0.5, period_beats=2.0),
            hold_step("second", 20.0, start=0.5, duration=0.5),
        ],
    )
    document.presets = [
        TemplatePreset(
            preset_id="base",
            step_patches={"main": StepPatch(timing={"base_timing": {"duration_bars": 0.5}})},
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
    """The compile of `document` over four bars on the two-head rig, or the
    type of the refusal."""
    rig = p1_rig()
    grid = bars_grid(*([500.0] * 4))
    phase_map = build_musical_phase_map(grid)
    start_limit, end_limit = cue_limits(phase_map, int(grid.duration_ms))
    selected = document.presets[0] if preset and document.presets else None
    context = TemplateCompileContext(
        section_id="section",
        template_id=document.template.template_id,
        preset_id=selected.preset_id if selected else None,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=1,
        duration_bars=4,
        presets=rig.presets,
    )
    try:
        result = compile_template(
            document.template,
            context,
            selected,
            phase_map=phase_map,
            start_limit_ms=start_limit,
            end_limit_ms=end_limit,
        )
    except (CompileError, PhysicalChannelError, ValueError) as error:
        return {"rejected": type(error).__name__}
    return result.model_dump(mode="json")


_COMPILE_CASES: tuple[tuple[str, Mutation], ...] = (
    ("template.template.repeat", _set("template.repeat.cycle_bars", 2.0)),
    ("template.template.repeat.mode", _set("template.repeat.mode", RepeatMode.PING_PONG)),
    ("template.template.repeat.cycle_bars", _set("template.repeat.cycle_bars", 2.0)),
    (
        "template.template.repeat.loop_step_ids",
        _set("template.repeat.loop_step_ids", ["main"]),
    ),
    (
        "template.template.repeat.remainder_policy",
        _set("template.repeat.remainder_policy", RemainderPolicy.FADE_OUT),
    ),
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
        "template.template.steps.movement",
        lambda document: setattr(
            document.template.steps[0],
            "movement",
            document.template.steps[0].movement.model_copy(update={"start_pan_deg": 10.0}),
        ),
    ),
    (
        "template.template.steps.dimmer",
        _set(
            "template.steps.0.dimmer",
            DimmerPulse(period_beats=1.0, duty_cycle=0.5, low=0.0, high=1.0),
        ),
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
    """Each path changes the compile, or makes it refuse the template."""
    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    mutation(changed)

    assert "rejected" not in _compile_snapshot(baseline)
    assert _compile_snapshot(changed) != _compile_snapshot(baseline), config_path


_PRESET_CASES: tuple[tuple[str, Mutation], ...] = (
    (
        "template.presets",
        _set(
            "presets.0.step_patches",
            {"main": StepPatch(timing={"base_timing": {"duration_bars": 0.25}})},
        ),
    ),
    ("template.presets.preset_id", _set("presets.0.preset_id", "changed")),
    (
        "template.presets.step_patches",
        _set(
            "presets.0.step_patches",
            {"main": StepPatch(timing={"base_timing": {"duration_bars": 0.25}})},
        ),
    ),
    (
        "template.presets.step_patches.movement",
        _set(
            "presets.0.step_patches",
            {"main": StepPatch(movement={"start_pan_deg": 10.0})},
        ),
    ),
    (
        "template.presets.step_patches.dimmer",
        _set(
            "presets.0.step_patches",
            {"main": StepPatch(dimmer={"duty_cycle": 0.5, "period_beats": 1.0})},
        ),
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
    """Each path changes the compile under the preset, or makes it refuse."""
    baseline = _rich_doc()
    changed = baseline.model_copy(deep=True)
    mutation(changed)

    assert "rejected" not in _compile_snapshot(baseline, preset=True)
    assert _compile_snapshot(changed, preset=True) != _compile_snapshot(baseline, preset=True), (
        config_path
    )
