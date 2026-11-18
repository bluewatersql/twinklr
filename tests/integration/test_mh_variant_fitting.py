"""Variation variants fitted to a slow or range-limited rig (`fitting`): only the reach is
reduced, never the period, so every reveal stays where the catalog variant puts it. The
gate admits the strongest reduced reach that passes, the render plays it, the trace, the
offer and repair say so (with what the catalog strength broke), no two offered variants
play alike, and no frame goes over the head's limits. Every rig here narrows its allowed
ranges (`allowed_rig`)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from itertools import pairwise
from typing import Any

import pytest

from tests.support import moving_heads as m
from tests.unit.sequencer.moving_heads.test_events_render import Frames
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.agents.sequencer.moving_heads.rig_repair import repair_rig_intent
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.sequencer.moving_heads.arrangement import (
    BASE,
    VARIATION_PRESETS,
    VariantOptions,
    resolve_arrangement,
)
from twinklr.core.sequencer.moving_heads.fitting import MIN_REACH, fits_for, fitted_preset
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


def slow_rig(speed: float, group: FixtureGroup | None = None) -> FixtureGroup:
    """`group` (the family rig) whose pan and tilt travel at `speed` degrees a second."""
    payload = (group or m.family_rig(HEADS)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = speed
    return FixtureGroup.model_validate(payload)


def grid(bpm: float, *, per_bar: int = 4) -> BeatGrid:
    return m.pickup_grid(60_000 / bpm, 16, pickup=0, beats_per_bar=per_bar)


def gate(
    fg: FixtureGroup, beat_grid: BeatGrid, ids: tuple[str, ...] = m.FAMILY_IDS, job: Any = None
) -> TemplateAdmission:
    job = job or m.family_job(HEADS)
    return admit_templates(
        list(ids),
        beat_grid=beat_grid,
        fixture_group=fg,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(ids),
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


def degrees(pipeline: RenderingPipeline, fixture_id: str, axis_name: str) -> list[float]:
    profile = pipeline.fixture_group.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    axis = profile.axes[axis_name]
    out = []
    for frame in sorted(pipeline.frames, key=lambda f: f.time_ms):
        if frame.fixture_id != fixture_id:
            continue
        channels = dict(frame.channels)
        word = channels[axis.coarse_offset]
        if axis.fine_offset is not None:
            word = word << 8 | channels[axis.fine_offset]
        out.append(axis.word_center(word))
    return out


def reveals(pipeline: RenderingPipeline) -> dict[str, list[int]]:
    """Each head's reveal frames: a lit frame after a dark one."""
    frames = Frames(pipeline)
    out = {}
    for head in HEADS:
        dark = frames.dark(head)
        out[head] = [i * 20 for i in range(1, len(dark)) if dark[i - 1] and not dark[i]]
    return out


# --- the ladder ------------------------------------------------------------------------


def test_only_the_reach_is_fitted_strongest_first() -> None:
    cascade = get_template("fly_out_cascade")
    presets = {p.preset_id: p for p in cascade.presets}

    assert [f.reach for f in fits_for(cascade, presets["wide"])] == [1.4, 1.3, 1.25, MIN_REACH]
    assert [f.reach for f in fits_for(cascade, presets["wide+slow"])] == [1.4, 1.3, 1.25, 1.2]
    assert [f.reach for f in fits_for(cascade, presets["wide+fast"])] == [1.4, 1.3, 1.25, 1.2]
    # base 45 degrees, narrow 30: a quarter, a half, three quarters of the way to narrow
    assert [(f.toward, f.reach) for f in fits_for(cascade, presets["fast"])] == [
        ("narrow", 0.917),
        ("narrow", 0.833),
        ("narrow", 0.75),
    ]
    for never in ("narrow", "slow", "narrow+slow", "narrow+fast"):
        assert fits_for(cascade, presets[never]) == [], never
    snap = get_template("finite_snap_hold")
    snaps = {p.preset_id: p for p in snap.presets}
    assert [f.reach for f in fits_for(snap, snaps["wide"])] == [1.4, 1.3, 1.25, 1.2]
    for once in ("fast", "wide+fast", "narrow+fast"):  # a ONCE family's rate does not show
        assert fits_for(snap, snaps[once]) == [], once


def test_a_fitted_patch_keeps_the_catalog_period() -> None:
    wings = get_template("mirror_wings")
    presets = {p.preset_id: p for p in wings.presets}

    # base 35 x 15, catalog wide 52.5 x 22.5, narrow 20 x 10
    (wider,) = [f for f in fits_for(wings, presets["wide+fast"]) if f.reach == 1.3]
    assert fitted_preset(wings, presets["wide+fast"], wider).step_patches["wings"].movement == {
        "pan_extent_deg": 45.5,
        "tilt_extent_deg": 19.5,
        "period_beats": 2.0,
    }
    (narrower,) = [f for f in fits_for(wings, presets["fast"]) if f.share == 0.5]
    assert fitted_preset(wings, presets["fast"], narrower).step_patches["wings"].movement == {
        "period_beats": 2.0,
        "pan_extent_deg": 27.5,
        "tilt_extent_deg": 12.5,
    }


# --- slow and limited rigs ----------------------------------------------------------------


@pytest.mark.parametrize("per_bar", [4, 3], ids=["4/4", "3/4"])
def test_a_fitted_fast_reveals_on_the_beats_the_catalog_fast_does(per_bar: int) -> None:
    """On 150 degree/s heads at 79.5 BPM the cascades' catalog `fast` is over the heads'
    speed; the gate fits it at a reach toward `narrow`'s, at the catalog's halved period.
    Every head reveals on the same frames as the catalog `fast` does on heads fast enough
    for it, and no frame steps faster than the head goes."""
    beat_grid = grid(79.5, per_bar=per_bar)
    slow = m.allowed_rig(slow_rig(150.0))
    fast = m.allowed_rig(m.family_rig(HEADS))
    fitted, catalog = gate(slow, beat_grid), gate(fast, beat_grid)
    section = [m.plan_section("a", 1, 8, "fly_out_cascade", "fast")]

    for cascade in CASCADES:
        fit = fitted.offer.templates[cascade].fitted["fast"]
        assert fit["toward"] == "narrow" and fit["reach"] < 1
        assert "above the configured speed" in fit["because"]
        assert "fast" not in catalog.offer.templates[cascade].fitted
    reduced = render(section, slow, beat_grid, fitted)
    authored = render(section, fast, beat_grid, catalog)

    assert reveals(reduced) == reveals(authored)
    look = reduced.render_record["section_looks"][0]
    assert look["fitted"].startswith("fast fitted to this rig: half the period at x")
    pan = slow.expand_fixtures()[0].config.physical_profile.axes["pan"]  # type: ignore[union-attr]
    word = 540 / (65535 if pan.fine_offset else 255)
    for head in HEADS:
        swing = degrees(reduced, head, "pan")
        assert max(abs(b - a) for a, b in pairwise(swing)) <= 150.0 * 0.020 + word + 1e-6


def test_a_slow_rig_names_the_fit_and_its_cause_in_offer_trace_and_repair() -> None:
    fg = m.allowed_rig(slow_rig(140.0))
    beat_grid = grid(79.5)
    admission = gate(fg, beat_grid)

    for cascade in CASCADES:
        assert admission.offer.templates[cascade].fitted["wide"]["reach"] == 1.4
    shown = offer_for_prompt(admission.offer, {}, ["a", "b"])
    assert "`fly_out_cascade` wide at x1.4 of the base's reach" in shown["fitted_variants"]
    plan = ChoreographyPlan(
        sections=[
            m.plan_section("a", 1, 4, "fly_out_cascade", motif_id="m"),
            m.plan_section("b", 5, 8, "fly_out_cascade", motif_id="m", variation="WIDEN"),
        ],
        overall_strategy="",
    )
    repaired = repair_rig_intent(plan, admission.offer, {}, beat_grid)
    pipeline = render(list(repaired.sections), fg, beat_grid, admission)
    looks = {look["section_id"]: look for look in pipeline.render_record["section_looks"]}

    assert looks["b"]["arrangement"]["variation"]["plays"] == "wide"
    assert looks["b"]["fitted"].startswith("wide fitted to this rig: x1.4 of the base's reach")
    assert "above the configured speed" in looks["b"]["fitted"]
    (said,) = [r.reason for r in repaired.repairs if r.section_id == "b" and "fitted" in r.reason]
    assert said == looks["b"]["fitted"]


def test_a_range_limit_is_named_as_the_cause() -> None:
    """Heads fast enough for everything, whose pan is allowed only -62..62: the catalog's
    `wide` reaches 67.5 degrees; it is fitted for the range, and says so."""
    payload = m.family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"]["axes"]["pan"].update(
            allowed_min=-62.0, allowed_max=62.0
        )
    fg = FixtureGroup.model_validate(payload)
    beat_grid = grid(120)
    admission = gate(fg, beat_grid)

    fit = admission.offer.templates["fly_out_cascade"].fitted["wide"]
    assert fit["toward"] == "wide" and "outside the operable range" in fit["because"]
    repaired = repair_rig_intent(
        ChoreographyPlan(
            sections=[m.plan_section("a", 1, 4, "fly_out_cascade", "wide")], overall_strategy=""
        ),
        admission.offer,
        {},
        beat_grid,
    )
    assert any("outside the operable range" in r.reason for r in repaired.repairs)
    assert not any("speed allows" in r.reason for r in repaired.repairs)


def test_a_failure_that_is_not_a_physical_limit_is_not_fitted() -> None:
    """At 170 BPM on 150 degree/s heads `masked_wheel_flick`'s `wide` fails on a dark
    repositioning it cannot plan: no reduced reach is tried, and the reason stands."""
    admission = gate(m.allowed_rig(slow_rig(150.0)), grid(170))
    flick = admission.offer.templates["masked_wheel_flick"]

    assert "wide" not in flick.variants and "wide" not in flick.fitted
    (refused,) = [
        e
        for e in admission.preset_exclusions
        if (e["template_id"], e["preset_id"]) == ("masked_wheel_flick", "wide")
    ]
    assert "dark repositioning" in str(refused["reason"])
    assert "reduced reach" not in str(refused["reason"])


@pytest.mark.parametrize("bpm", [79.5, 120, 170])
def test_no_two_offered_variants_play_alike(bpm: float) -> None:
    """`fast` fitted toward `narrow` stays short of `narrow+fast`, and the snap, whose rate
    does not show, offers none of its fast variants."""
    for fg in (m.allowed_rig(slow_rig(150.0)), m.allowed_rig(m.family_rig(HEADS))):
        admission = gate(fg, grid(bpm))
        for template_id, offered in admission.offer.templates.items():
            fast = offered.fitted.get("fast")
            if fast is not None:
                assert fast["toward"] == "narrow" and fast["share"] < 1
            if template_id == "finite_snap_hold":
                assert not {"fast", "narrow+fast", "wide+fast"} & set(offered.variants)


def test_faster_needs_a_narrower_reach_where_fast_is_not_offered() -> None:
    def no_fast(_: str) -> VariantOptions:
        everything = frozenset({BASE, "narrow", "slow", *VARIATION_PRESETS})
        return VariantOptions(effective=BASE, admitted=everything - {"fast", "wide+fast"})

    resolved = resolve_arrangement(
        ChoreographyPlan(
            sections=[
                m.plan_section("a", 1, 2, "fly_out_cascade", "wide", motif_id="m"),
                m.plan_section("b", 3, 4, "fly_out_cascade", motif_id="m", variation="FASTER"),
                m.plan_section("c", 5, 6, "target_orbit", variation="FASTER"),
            ],
            overall_strategy="",
        ),
        no_fast,
    )

    b, c = resolved["b"].parts[0], resolved["c"].parts[0]
    assert b is not None and c is not None
    # From `wide`: `wide+fast` and, one reach step narrower, `fast` are not offered; two
    # steps narrower would read as NARROW, so the variation does not play.
    assert b.plays == "wide" and b.reason is not None and "'fast' of" in b.reason
    # From base: `fast` is not offered; one step narrower, `narrow+fast` plays.
    assert c.plays == "narrow+fast"
    assert c.note is not None and "faster here needs a narrower reach" in c.note


def test_a_fitted_strength_is_render_identity() -> None:
    fg = m.allowed_rig(slow_rig(140.0))
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
    plain = RenderingPipeline(
        choreography_plan=ChoreographyPlan(sections=sections, overall_strategy=""),
        beat_grid=beat_grid,
        fixture_group=fg,
        job_config=m.family_job(HEADS),
        media_file="silence.wav",
        admission=replace(admission, offer=unfitted),
    )
    assert fitted.fingerprint() != plain.fingerprint()


@pytest.mark.parametrize(("speed", "fitted"), [(140.55, False), (140.40, True)])
def test_a_variant_over_the_limit_by_a_hair_is_fitted(speed: float, fitted: bool) -> None:
    """The cascades' `wide` at 79.5 BPM passes at the catalog's strength from about 140.48
    degree/s: just above it plays unfitted, just under it at x1.4."""
    admission = gate(m.allowed_rig(slow_rig(speed)), grid(79.5), ("fly_out_cascade",))
    offered = admission.offer.templates["fly_out_cascade"]

    assert "wide" in offered.variants
    assert ("wide" in offered.fitted) is fitted
    if fitted:
        assert offered.fitted["wide"]["reach"] == 1.4


def test_zoom_wave_on_a_narrowed_zoom_rig_it_can_play() -> None:
    """A zoom rig narrowed to a zoom range `zoom_wave` plays in (10..38): admitted, and on
    slow heads its `wide` fitted like any family's pan (zoom itself is never fitted: no
    variant patches it)."""
    job = m.zoom_job(HEADS)
    fg = m.allowed_rig(slow_rig(60.0, m.zoom_rig(HEADS)), zoom=(10.0, 38.0))
    admission = gate(fg, grid(120), (m.ZOOM_FAMILY_ID,), job)

    assert admission.admitted == (m.ZOOM_FAMILY_ID,)
    offered = admission.offer.templates[m.ZOOM_FAMILY_ID]
    assert {"base", "wide"} <= set(offered.variants)
    assert offered.fitted["wide"]["reach"] == 1.25
    assert "above the configured speed" in offered.fitted["wide"]["because"]


@pytest.mark.parametrize("bpm", [79.5, 120, 170])
def test_a_rig_fast_enough_for_the_catalog_fits_nothing(bpm: float) -> None:
    admission = gate(m.allowed_rig(m.family_rig(HEADS)), grid(bpm))

    assert all(not offered.fitted for offered in admission.offer.templates.values())


def test_variants_whose_aim_differs_by_under_three_degrees_play_alike() -> None:
    """`_alike`: the same darkness, level and wheels with every aim within `TWIN_POSE_DEG`
    plays alike; a 3-degree aim difference, or any other channel, does not."""
    from twinklr.core.sequencer.moving_heads.export.frame_encoder import EncodedFixtureFrame
    from twinklr.core.sequencer.moving_heads.pipeline import TWIN_POSE_DEG, _alike

    fg = m.allowed_rig(m.family_rig(HEADS))
    profile = fg.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    pan = profile.axes["pan"]

    def frame(degrees: float, dimmer: int = 255) -> EncodedFixtureFrame:
        word = pan.dmx_word(degrees)
        channels = dict.fromkeys(range(1, profile.footprint + 1), 0)
        if pan.fine_offset is not None:
            channels[pan.coarse_offset], channels[pan.fine_offset] = word >> 8, word & 0xFF
        else:
            channels[pan.coarse_offset] = word
        tilt = profile.axes["tilt"]
        tilt_word = tilt.dmx_word(30.0)
        if tilt.fine_offset is not None:
            channels[tilt.coarse_offset], channels[tilt.fine_offset] = (
                tilt_word >> 8,
                tilt_word & 0xFF,
            )
        else:
            channels[tilt.coarse_offset] = tilt_word
        channels[profile.axes["dimmer"].coarse_offset] = dimmer
        return EncodedFixtureFrame(
            time_ms=0, fixture_id="MH1", channels=tuple(sorted(channels.items()))
        )

    profiles = {"MH1": profile}
    assert _alike([frame(10.0)], [frame(10.0 + TWIN_POSE_DEG - 0.5)], profiles)
    assert not _alike([frame(10.0)], [frame(10.0 + TWIN_POSE_DEG + 0.5)], profiles)
    assert not _alike([frame(10.0)], [frame(10.0, dimmer=128)], profiles)
