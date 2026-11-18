"""Variation variants fitted to a slow rig (`fitting`): the gate admits the strongest
reduced strength that passes, the render plays it, the trace, the offer and repair say so,
and no frame goes over the head's limits. Every rig here narrows its allowed ranges
(`allowed_rig`)."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest

from tests.support import moving_heads as m
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.fitting import (
    MIN_RATE,
    MIN_REACH,
    Fit,
    fits_for,
    fitted_preset,
)
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    admit_templates,
)
from twinklr.core.sequencer.moving_heads.song_intent import offer_for_prompt
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid

HEADS = ("MH1", "MH2", "MH3", "MH4")
CASCADES = ("fly_out_cascade", "fly_in_cascade")


@pytest.fixture(autouse=True)
def _catalog() -> Iterator[None]:
    with m.family_catalog():
        yield


def slow_rig(speed: float) -> FixtureGroup:
    """`allowed_rig(family_rig)` whose pan and tilt travel at `speed` degrees a second."""
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return m.allowed_rig(FixtureGroup.model_validate(payload))


def grid(bpm: float) -> BeatGrid:
    return m.bars_grid(*([60_000 / bpm] * 16))


def gate(fg: FixtureGroup, beat_grid: BeatGrid) -> TemplateAdmission:
    job = m.family_job(HEADS)
    return admit_templates(
        list(m.FAMILY_IDS),
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(m.FAMILY_IDS),
    )


def render(
    sections: list, fg: FixtureGroup, beat_grid: BeatGrid, admission: TemplateAdmission
) -> RenderingPipeline:
    pipeline = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        admission=admission,
    )
    pipeline.render()
    return pipeline


def pan_degrees(
    pipeline: RenderingPipeline, fixture_id: str, window: tuple[float, float] = (0, 1e12)
) -> list[float]:
    profile = pipeline.fixture_group.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    axis = profile.axes["pan"]
    out = []
    for frame in sorted(pipeline.frames, key=lambda f: f.time_ms):
        if frame.fixture_id != fixture_id or not window[0] <= frame.time_ms < window[1]:
            continue
        channels = dict(frame.channels)
        word = channels[axis.coarse_offset]
        if axis.fine_offset is not None:
            word = word << 8 | channels[axis.fine_offset]
        out.append(axis.word_center(word))
    return out


# --- the ladder ------------------------------------------------------------------------


def test_the_fits_tried_are_strongest_first_and_stop_at_a_visible_step() -> None:
    cascade = get_template("fly_out_cascade")
    presets = {p.preset_id: p for p in cascade.presets}

    assert fits_for(cascade, presets["wide"]) == [
        Fit(reach=1.4),
        Fit(reach=1.3),
        Fit(reach=1.25),
        Fit(reach=1.2),
    ]
    assert fits_for(cascade, presets["fast"]) == [Fit(period_beats=3.0)]  # 4 beats: 2, 3
    assert fits_for(cascade, presets["narrow+fast"]) == [Fit(period_beats=3.0)]
    pair = fits_for(cascade, presets["wide+fast"])
    assert pair[:3] == [Fit(period_beats=3.0), Fit(reach=1.4), Fit(reach=1.4, period_beats=3.0)]
    assert pair[-1] == Fit(reach=MIN_REACH, period_beats=3.0)
    assert fits_for(cascade, presets["narrow"]) == [] and fits_for(cascade, presets["slow"]) == []
    snap = get_template("finite_snap_hold")
    fast_snap = next(p for p in snap.presets if p.preset_id == "fast")
    assert fits_for(snap, fast_snap) == []  # 1 beat: only the catalog's half beat
    assert MIN_RATE == 0.75


def test_a_fitted_patch_is_derived_from_the_base_and_the_catalog_target() -> None:
    wings = get_template("mirror_wings")
    wide_fast = next(p for p in wings.presets if p.preset_id == "wide+fast")

    fitted = fitted_preset(wings, wide_fast, Fit(reach=1.3, period_beats=3.0))

    # base 35 x 15 degrees; the catalog's wide 52.5 x 22.5
    assert fitted.step_patches["wings"].movement == {
        "pan_extent_deg": 45.5,
        "tilt_extent_deg": 19.5,
        "period_beats": 3.0,
    }


# --- the gate and the render on a slow rig ----------------------------------------------


def test_a_slow_rig_plays_the_cascades_wide_and_fast_at_fitted_strengths() -> None:
    """140 degree/s heads at 79.5 BPM (narrowed ranges): the cascades' catalog `wide` and
    `fast` are over the heads' speed; the gate admits `wide` at x1.4 and `fast` on a 3-beat
    period, the strongest that pass. The render plays them, visibly unlike the base, never
    faster than the heads go, and the trace, the offer and repair say so."""
    fg = slow_rig(140.0)
    beat_grid = grid(79.5)
    admission = gate(fg, beat_grid)

    for cascade in CASCADES:
        offered = admission.offer.templates[cascade]
        assert offered.fitted["wide"] == {"reach": 1.4}
        assert offered.fitted["fast"] == {"period_beats": 3.0}
        assert {"wide", "fast"} <= set(offered.variants)
    shown = offer_for_prompt(admission.offer, {}, ["a", "b"])
    assert "`fly_out_cascade` wide at x1.4 of the base's reach" in shown["fitted_variants"]

    base = render([m.plan_section("a", 1, 8, "fly_out_cascade")], fg, beat_grid, admission)
    plan = ChoreographyPlan(
        sections=[
            m.plan_section("a", 1, 4, "fly_out_cascade", motif_id="m"),
            m.plan_section("b", 5, 8, "fly_out_cascade", motif_id="m", variation="WIDEN"),
        ],
        overall_strategy="",
    )
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    wide = render(list(repaired.sections), fg, beat_grid, admission)
    looks = {look["section_id"]: look for look in wide.render_record["section_looks"]}
    assert looks["b"]["arrangement"]["variation"]["plays"] == "wide"
    assert looks["b"]["fitted"].startswith("wide fitted to this rig: x1.4 of the base's reach")
    assert any(
        r.section_id == "b" and "x1.4 of the base's reach" in r.reason for r in repaired.repairs
    )
    bars = beat_grid.bar_boundaries
    second = (bars[4], bars[8])  # section b
    for head in HEADS:
        plain, widened = pan_degrees(base, head, second), pan_degrees(wide, head, second)
        assert max(widened) - min(widened) > (max(plain) - min(plain)) * 1.2, head

    fast = render(
        [
            m.plan_section("a", 1, 4, "fly_out_cascade"),
            m.plan_section("b", 5, 8, "fly_out_cascade", "fast"),
        ],
        fg,
        beat_grid,
        admission,
    )
    assert fast.frames != base.frames
    assert (
        "fitted" in {look["section_id"]: look for look in fast.render_record["section_looks"]}["b"]
    )

    profile = fg.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    pan = profile.axes["pan"]
    assert pan.travel_speed_per_s is not None
    word = (pan.physical_max - pan.physical_min) / (65535 if pan.fine_offset else 255)
    allowed = pan.travel_speed_per_s * 0.020 + word + 1e-6
    for pipeline in (wide, fast):
        for head in HEADS:
            degrees = pan_degrees(pipeline, head)
            steps = [abs(b - a) for a, b in pairwise(degrees)]
            assert max(steps) <= allowed, (head, max(steps), allowed)


def test_a_fitted_strength_is_render_identity() -> None:
    fg = slow_rig(140.0)
    beat_grid = grid(79.5)
    admission = gate(fg, beat_grid)
    sections = [m.plan_section("a", 1, 8, "fly_out_cascade", "wide")]
    fitted = render(sections, fg, beat_grid, admission)
    offer = admission.offer
    unfitted = offer.model_copy(
        update={
            "templates": {
                t: o.model_copy(update={"fitted": {}}) for t, o in offer.templates.items()
            }
        }
    )
    from dataclasses import replace

    plain = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        admission=replace(admission, offer=unfitted),
    )
    assert fitted.fingerprint() != plain.fingerprint()


@pytest.mark.parametrize("bpm", [79.5, 120, 170])
def test_a_rig_fast_enough_for_the_catalog_fits_nothing(bpm: float) -> None:
    """On heads fast enough for the catalog's strengths nothing is fitted: such a rig
    renders as before (the byte matrix holds every frame)."""
    admission = gate(m.allowed_rig(m.family_rig(HEADS)), grid(bpm))

    assert all(not offered.fitted for offered in admission.offer.templates.values())
