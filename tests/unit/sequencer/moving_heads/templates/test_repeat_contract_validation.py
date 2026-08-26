"""Registration rejects repeat contracts the scheduler cannot honor.

This is the linter the P4-F5 / P4-F6 review asked for: both defects were data
errors that no code path checked, so they shipped in the catalog and were only
found by reading it. Every shipped template must pass, and both defect shapes must
be rejected, or the same class of error can land again.
"""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from twinklr.core.config.poses import TiltPose
from twinklr.core.sequencer.models.enum import (
    Intensity,
    TemplateCategory,
    TimingMode,
)
from twinklr.core.sequencer.models.template import (
    BaseTiming,
    Dimmer,
    Geometry,
    Movement,
    RemainderPolicy,
    RepeatContract,
    RepeatMode,
    StepTiming,
    Template,
    TemplateDoc,
    TemplateMetadata,
    TemplateStep,
)
from twinklr.core.sequencer.moving_heads.libraries.dimmer import DimmerType
from twinklr.core.sequencer.moving_heads.libraries.geometry import GeometryType
from twinklr.core.sequencer.moving_heads.libraries.movement import MovementType
from twinklr.core.sequencer.moving_heads.templates import (
    list_templates,
    load_builtin_templates,
)
from twinklr.core.sequencer.moving_heads.templates.library import (
    InvalidTemplateError,
    TemplateRegistry,
    get_template,
    validate_repeat_contract,
)


def _step(step_id: str, *, offset_bars: float, duration_bars: float) -> TemplateStep:
    return TemplateStep(
        step_id=step_id,
        timing=StepTiming(
            base_timing=BaseTiming(
                mode=TimingMode.MUSICAL,
                start_offset_bars=offset_bars,
                duration_bars=duration_bars,
            )
        ),
        geometry=Geometry(geometry_type=GeometryType.ROLE_POSE, tilt_pose=TiltPose.HORIZON),
        movement=Movement(movement_type=MovementType.SWEEP_LR, intensity=Intensity.SMOOTH),
        dimmer=Dimmer(dimmer_type=DimmerType.PULSE, intensity=Intensity.SMOOTH),
    )


def _doc(*, cycle_bars: float, loop_step_ids: list[str], steps: list[TemplateStep]) -> TemplateDoc:
    return TemplateDoc(
        template=Template(
            template_id="fixture_under_test",
            version=1,
            name="Fixture Under Test",
            category=TemplateCategory.MEDIUM_ENERGY,
            repeat=RepeatContract(
                mode=RepeatMode.JOINER,
                cycle_bars=cycle_bars,
                loop_step_ids=loop_step_ids,
                remainder_policy=RemainderPolicy.HOLD_LAST_POSE,
            ),
            defaults={"dimmer_floor_dmx": 60, "dimmer_ceiling_dmx": 255},
            steps=steps,
            metadata=TemplateMetadata(
                tags=["test"],
                recommended_sections=["verse"],
                energy_range=(20, 80),
                description="Repeat contract fixture.",
            ),
        )
    )


def test_registration_rejects_step_duration_mismatch() -> None:
    """P4-F6's shape: the loop occupies more bars than the cycle claims.

    `split_lr_sweep_counter` shipped as two 4-bar steps under a 4-bar cycle. Read as
    a sequence that is an 8-bar loop, and a 16-bar section scheduled 32 bars of
    segments with nothing clipping them.
    """
    doc = _doc(
        cycle_bars=4.0,
        loop_step_ids=["left", "right"],
        steps=[
            _step("left", offset_bars=0.0, duration_bars=4.0),
            _step("right", offset_bars=4.0, duration_bars=4.0),
        ],
    )

    with pytest.raises(InvalidTemplateError, match=r"span 8\.0 bars"):
        TemplateRegistry().register(lambda: doc)


def test_registration_rejects_unreachable_step() -> None:
    """P4-F5's shape: a step is defined but never named in the loop.

    `build_drop_recover` declared build/drop/recover and looped only "drop", so two
    thirds of the template — including the only FADE_IN and FADE_OUT in the library
    — were dead data behind a description promising the whole arc.
    """
    doc = _doc(
        cycle_bars=2.0,
        loop_step_ids=["drop"],
        steps=[
            _step("build", offset_bars=0.0, duration_bars=2.0),
            _step("drop", offset_bars=2.0, duration_bars=2.0),
        ],
    )

    with pytest.raises(InvalidTemplateError, match=r"\['build'\]"):
        TemplateRegistry().register(lambda: doc)


def test_loop_step_that_does_not_exist_is_rejected_by_the_model() -> None:
    """The other direction is already the `Template` model's job — named here so the
    validator is not extended to duplicate it."""
    with pytest.raises(ValidationError, match="not found in template steps"):
        _doc(
            cycle_bars=4.0,
            loop_step_ids=["main", "ghost"],
            steps=[_step("main", offset_bars=0.0, duration_bars=4.0)],
        )


def test_parallel_steps_are_accepted() -> None:
    """Steps that overlap deliberately are valid: the span is the cycle, not the sum."""
    doc = _doc(
        cycle_bars=4.0,
        loop_step_ids=["left", "right"],
        steps=[
            _step("left", offset_bars=0.0, duration_bars=4.0),
            _step("right", offset_bars=0.0, duration_bars=4.0),
        ],
    )

    TemplateRegistry().register(lambda: doc)


def test_every_shipped_template_passes_the_validator() -> None:
    load_builtin_templates()
    template_ids = [info.template_id for info in list_templates()]
    assert len(template_ids) == 37

    for template_id in template_ids:
        validate_repeat_contract(get_template(template_id).template)


def test_every_shipped_template_schedules_all_of_its_steps() -> None:
    """The consequence the validator exists to guarantee, stated directly."""
    load_builtin_templates()

    for info in list_templates():
        template = get_template(info.template_id).template
        declared = {step.step_id for step in template.steps}
        assert declared == set(template.repeat.loop_step_ids), (
            f"{info.template_id} declares steps it never schedules: "
            f"{sorted(declared - set(template.repeat.loop_step_ids))}"
        )
