"""Restored choreography renders through the single production path."""

from collections import defaultdict

import numpy as np
import pytest

from tests.support import moving_heads as m
from twinklr.core.sequencer.models.moving_heads.physical import PhysicalChannelError
from twinklr.core.sequencer.moving_heads.compile.step import CompileError
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

HEADS = ("MH1", "MH2", "MH3", "MH4")


def render(template_id, preset=None, rig=None):
    plan = m.sections_plan((template_id, 2, 9))
    if preset is not None:
        plan = plan.model_copy(
            update={"sections": [m.with_preset(s, preset) for s in plan.sections]}
        )
    pipe = RenderingPipeline(
        choreography_plan=plan,
        beat_grid=m.bars_grid(*([500.0] * 10)),
        fixture_group=rig or m.movement_rig(HEADS),
        job_config=m.zoom_job(HEADS, on_unplayable="error"),
        media_file="silence.wav",
    )
    pipe.render()
    return pipe


def lit_poses(pipe):
    result = defaultdict(list)
    for f in pipe.frames:
        c = dict(f.channels)
        if c[5] > 0:
            result[f.fixture_id].append((c[1] * 256 + c[2], c[3] * 256 + c[4]))
    return result


@pytest.mark.parametrize("template_id", m.RESTORED_MOVEMENT_IDS)
def test_restored_family_renders_motion_and_preserves_neutral_light(template_id):
    with m.family_catalog():
        pipe = render(template_id)
    poses = lit_poses(pipe)
    assert set(poses) == set(HEADS)
    for values in poses.values():
        span = np.ptp(values, axis=0).max()
        assert span == 0 if template_id.startswith("static_") else span > 500
    for f in pipe.frames:
        c = dict(f.channels)
        assert c[7] == 0  # white; no color disguising motion
    # The authored arrangement must not collapse all heads onto identical aims/phase.
    if template_id in {
        "bounce_fan",
        "zigzag_alternating",
        "fan_iris",
        "horizontal_wave",
        "radial_fan",
    }:
        assert len({tuple(poses[h]) for h in HEADS}) >= 3


def test_angular_speed_and_pose_dwell_survive_production_rendering():
    with m.family_catalog():
        angular = np.array(lit_poses(render("angular_pan"))["MH1"])[:, 0]
        pulse = np.array(lit_poses(render("pose_pop_lock"))["MH1"])[:, 0]
    angular_changes = np.abs(np.diff(angular))
    pulse_changes = np.abs(np.diff(pulse))
    assert np.mean(angular_changes == 0) < 0.02
    assert np.mean(pulse_changes == 0) > 0.6
    assert np.mean(pulse_changes > 0) > 0.15


def test_required_geometry_is_not_silently_replaced_by_centered_heads():
    with m.family_catalog(), pytest.raises(CompileError, match="movement_fan"):
        render("bounce_fan", rig=m.zoom_rig(HEADS))


def test_too_fast_pose_switch_is_rejected_by_physical_rate_checks():
    with m.family_catalog():
        rig = m.movement_rig(HEADS)
        payload = rig.model_dump(mode="json")
        for f in payload["fixtures"]:
            if f.get("config") and f["config"].get("physical_profile"):
                for axis in ("pan", "tilt"):
                    f["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 5
        slow = type(rig).model_validate(payload)
        with pytest.raises(PhysicalChannelError, match=r"speed|rate|travel"):
            render("pose_pop_lock", rig=slow)


@pytest.mark.parametrize(
    "path",
    [
        "template.template.steps.movement.path_knots",
        "template.template.steps.movement.path_knots.phase",
        "template.template.steps.movement.path_knots.x",
        "template.template.steps.movement.path_knots.y",
    ],
)
def test_path_knot_field_changes_emitted_frames(path):
    from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind

    assert CONFIG_EFFECTS[path].kind is ConfigDispositionKind.EFFECT_TEST
    step = m.hold_step("path", 0, tilt=30, duration=4)
    step["movement"].update(
        shape="polyline",
        mode="periodic",
        period_beats=4,
        pan_extent_deg=30,
        tilt_extent_deg=20,
        path_knots=[
            {"phase": 0, "x": -1, "y": -1},
            {"phase": 0.5, "x": 1, "y": 1},
            {"phase": 1, "x": -1, "y": -1},
        ],
    )
    original = m.loop_template_doc("knots_probe", [step], cycle_bars=4)
    with m.registered_templates(original):
        before = render("knots_probe").frames
    knots = step["movement"]["path_knots"]
    field = path.rsplit(".", 1)[-1]
    if field == "path_knots":
        knots.insert(1, {"phase": 0.25, "x": -0.8, "y": 0.6})
    elif field == "phase":
        knots[1]["phase"] = 0.375
    else:
        knots[1][field] = 0.25
    changed = m.loop_template_doc("knots_probe", [step], cycle_bars=4)
    with m.registered_templates(changed):
        after = render("knots_probe").frames
    assert before != after
    assert any(a.channels != b.channels for a, b in zip(before, after, strict=True))
