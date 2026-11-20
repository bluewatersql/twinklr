"""Historical arrangements retain their selection, formation and musical structure."""

import json
from pathlib import Path

import numpy as np
import pytest

from tests.support import moving_heads as m
from twinklr.core.config.fixtures.presets import PoseDegrees
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.topology import (
    PhaseDistribution,
    resolve_distribution,
)
from twinklr.core.sequencer.moving_heads.compile.scheduler import schedule_repeats
from twinklr.core.sequencer.moving_heads.compile.step import evaluate_path
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline
from twinklr.core.sequencer.moving_heads.templates import get_template

HEADS = ("MH1", "MH2", "MH3", "MH4")
CONTRACTS = json.loads(
    (Path(__file__).parents[1] / "fixtures/moving_heads/historical_arrangements.json").read_text()
)


def render(template_id, *, document=None):
    grid = m.bars_grid(*([500.0] * 18))
    pipe = RenderingPipeline(
        choreography_plan=m.sections_plan((template_id, 2, 17)),
        beat_grid=grid,
        fixture_group=m.movement_rig(HEADS),
        job_config=m.zoom_job(HEADS, on_unplayable="error"),
        media_file="silence.wav",
    )
    pipe.render()
    return pipe


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c["template_id"])
def test_historical_arrangement_contract_and_production_frames(contract):
    with m.family_catalog():
        template = get_template(contract["template_id"]).template
        assert template.repeat.mode.value == contract["repeat_mode"]
        assert template.repeat.cycle_bars == contract["cycle_bars"]
        assert len(template.steps) == len(contract["steps"])
        for step, original in zip(template.steps, contract["steps"], strict=True):
            assert step.step_id == original["step_id"]
            assert step.target.value == original["target"]
            assert step.timing.base_timing.start_offset_bars == original["start_bars"]
            assert step.timing.base_timing.duration_bars == original["duration_bars"]
            assert step.component_refs.position_id == original["position_id"]
            assert step.shutter_state == original["shutter_state"]
            assert step.color == original["color"]
            assert step.gobo == original["gobo"]
            phase = original["phase_order"]
            if phase:
                pan = next(d for d in step.distribution if ChannelName.PAN in d.domains)
                assert pan.direction == (
                    "reverse" if phase in ("RIGHT_TO_LEFT", "INSIDE_OUT") else "forward"
                )
                if phase in ("INSIDE_OUT", "OUTSIDE_IN"):
                    assert pan.wings == 2 and not pan.mirror_pan
                if phase == "ODD_EVEN":
                    assert pan.group_count == 2
            if original["dimmer_type"] == "BLACKOUT":
                assert step.dimmer.high == step.dimmer.low == 0
            elif original["dimmer_type"].startswith("FADE_"):
                assert step.dimmer.fade == original["dimmer_type"][5:].lower()
        pipe = render(contract["template_id"])
    assert pipe.frames
    assert pipe.unplayable_warning is None
    if contract["template_id"] in ("pop_lock_spotlight_blackout", "spiral_xross_blackout"):
        assert all(dict(f.channels)[5] == 0 for f in pipe.frames)
    else:
        assert any(dict(f.channels)[5] > 0 for f in pipe.frames)


def test_inner_pendulum_lights_and_moves_only_inner_heads():
    with m.family_catalog():
        pipe = render("inner_pendulum_breathe")
    for head in HEADS:
        frames = [dict(f.channels) for f in pipe.frames if f.fixture_id == head]
        if head in ("MH1", "MH4"):
            assert all(c[5] == 0 for c in frames)
        else:
            lit_pan = [c[1] * 256 + c[2] for c in frames if c[5] > 0]
            assert len(lit_pan) > 100 and np.ptp(lit_pan) > 1000


def test_scattered_wave_preserves_sine_pan_and_independent_noise_tilt():
    with m.family_catalog():
        spec = get_template("wave_scattered_fade_in").template.steps[0].movement
    assert spec.shape == "scattered_wave"
    points = np.array(
        [evaluate_path(spec, PoseDegrees(pan_deg=0, tilt_deg=0), i, 128) for i in range(129)]
    )
    assert points[:, 0] == pytest.approx(
        np.sin(np.arange(129) / 128 * 2 * np.pi) * spec.pan_extent_deg
    )
    assert np.ptp(points[:, 1]) > 5
    assert points[0] == pytest.approx(points[-1])
    turns = np.diff(np.sign(np.diff(points[:, 1])))
    assert np.count_nonzero(turns) > 4
    with m.family_catalog():
        pipe = render("wave_scattered_fade_in")
    for head in HEADS:
        lit = [
            dict(f.channels)
            for f in pipe.frames
            if f.fixture_id == head and dict(f.channels)[5] > 0
        ]
        assert np.ptp([c[3] * 256 + c[4] for c in lit]) > 500


@pytest.mark.parametrize(
    "template_id, expected",
    [
        ("build_drop_recover", [("build", 0, 2), ("drop", 2, 4), ("recover", 4, 6)]),
        ("intro_main_outro_phrase", [("intro", 0, 2), ("main", 2, 6), ("outro", 6, 8)]),
        ("crossfade_between_steps", [("a", 0, 2), ("b", 2, 4), ("b", 4, 6), ("a", 6, 8)]),
    ],
)
def test_complete_arc_and_ping_pong_order(template_id, expected):
    with m.family_catalog():
        t = get_template(template_id).template
    scheduled = schedule_repeats(
        t.repeat,
        expected[-1][2],
        {s.step_id: s.timing.base_timing.duration_bars for s in t.steps},
        {s.step_id: s.timing.base_timing.start_offset_bars for s in t.steps},
    )
    assert [(i.step_id, i.start_bars, i.end_bars) for i in scheduled.instances] == expected


def test_dimmer_fade_field_changes_emitted_frames():
    with m.family_catalog():
        before = render("wave_scattered_fade_in").frames
        after = render("wave_scattered_fade_out").frames
    assert [dict(f.channels)[5] for f in before] != [dict(f.channels)[5] for f in after]
    assert [tuple(v for c, v in f.channels if c in (1, 2, 3, 4)) for f in before] == [
        tuple(v for c, v in f.channels if c in (1, 2, 3, 4)) for f in after
    ]


def test_phase_fold_can_preserve_pan_orientation_without_mirroring():
    rig = m.movement_rig(HEADS)
    fold = PhaseDistribution(domains=("pan", "tilt"), wings=2, spread_cycles=0.5, mirror_pan=False)
    plain = resolve_distribution(rig.topology, (fold,), HEADS)
    mirrored = resolve_distribution(
        rig.topology, (fold.model_copy(update={"mirror_pan": True}),), HEADS
    )
    assert [p.pan_sign for p in plain.values()] == [1, 1, 1, 1]
    assert [p.phase_by_channel for p in plain.values()] == [
        p.phase_by_channel for p in mirrored.values()
    ]
    assert [p.pan_sign for p in mirrored.values()] == [-1, -1, 1, 1]


def test_compiled_cycles_keep_historical_bar_counts():
    from twinklr.core.sequencer.moving_heads.compile.template_compiler import whole_period_cycle

    with m.family_catalog():
        for contract in CONTRACTS:
            template = get_template(contract["template_id"]).template
            assert whole_period_cycle(template, 4).repeat.cycle_bars == contract["cycle_bars"]


def test_step_edge_darkness_changes_emitted_frames_and_leaves_reposition_time():
    from twinklr.core.sequencer.models.template import TemplateDoc

    step = m.hold_step("held", 0, tilt=30, duration=4)
    plain = m.loop_template_doc("edge_probe", [step], cycle_bars=4)
    with m.family_catalog(), m.registered_templates(plain):
        before = render("edge_probe").frames
    payload = plain.model_dump(mode="json")
    payload["template"]["steps"][0]["dimmer"]["edge_dark_beats"] = 1
    changed = TemplateDoc.model_validate(payload)
    with m.family_catalog(), m.registered_templates(changed):
        after = render("edge_probe").frames
    b = {f.time_ms: dict(f.channels)[5] for f in before if f.fixture_id == "MH1"}
    a = {f.time_ms: dict(f.channels)[5] for f in after if f.fixture_id == "MH1"}
    assert a[9600] == 0 < b[9600]
    assert a[4000] == b[4000] > 0


def test_fold_mirroring_field_changes_emitted_pan_without_changing_target_selection():
    from twinklr.core.sequencer.models.template import TemplateDoc

    with m.family_catalog():
        payload = get_template("ballyhoo_chaos").model_dump(mode="json")
        before = render("ballyhoo_chaos").frames
    payload["template"]["template_id"] = "mirrored_probe"
    payload["template"]["name"] = "Mirrored probe"
    payload["template"]["steps"][0]["distribution"][0]["mirror_pan"] = True
    with m.family_catalog(), m.registered_templates(TemplateDoc.model_validate(payload)):
        after = render("mirrored_probe").frames
    assert [dict(f.channels)[1] for f in before] != [dict(f.channels)[1] for f in after]


def test_reference_formations_are_shipped_and_mirror_spreads_outward():
    from twinklr.core.config.fixtures.presets import RigPresetLibrary

    reference = Path(__file__).parents[2] / "catalog/rigs/movement-reference-positions.json"
    shipped = RigPresetLibrary.model_validate_json(reference.read_text())
    assert shipped == m.movement_rig(HEADS).presets
    aims = shipped.positions["movement_mirror"].fixtures
    assert [aims[h].pan_deg for h in HEADS] == sorted(aims[h].pan_deg for h in HEADS)


def test_clipped_step_shorter_than_dark_edges_stays_dark():
    from tests.unit.sequencer.moving_heads.compile.test_paths import _compile

    step = m.hold_step("short_tail", 0, duration=1)
    step["dimmer"]["edge_dark_beats"] = 0.5
    template = m.loop_template_doc("short_tail", [step], cycle_bars=1).template
    assert _compile(template, duration_bars=1, end_limit_ms=400) == []


@pytest.mark.parametrize(
    "template_id, channel, word",
    [
        ("figure8_mirror_strobe", 6, 48),
        ("accent_snap_tunnel_hit", 8, 36),
        ("ambient_random_wash", 7, 26),
    ],
)
def test_intrinsic_optical_states_survive_production_render(template_id, channel, word):
    with m.family_catalog():
        frames = render(template_id).frames
    lit = [dict(f.channels) for f in frames if dict(f.channels)[5] > 0]
    assert lit and all(c[channel] == word for c in lit)
