"""The pre-planning gate checks every placement a planner section can give a template.

A section can start on any bar (the cycle then meets the song's bars and tempo at another
alignment), end after any number of bars (leaving a remainder under the template's
remainder policy) and, after its entry window, reveal any of its first cycle's cues first
(a `drop_accent` cascade then runs from there). The gate exercises each such placement
class, deduplicating placements identical relative to their start, so a template it
admits renders wherever a plan puts it.
"""

from __future__ import annotations

from collections.abc import Callable
import gc
from typing import Any

import pytest

from tests.support.moving_heads import (
    bars_grid,
    hold_step,
    loop_template_doc,
    overlay,
    p1_job,
    p1_rig,
    referencing_step,
    registered_templates,
    sections_plan,
    sweep_step,
    topology_rig,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.sequencer.models.moving_heads.physical import PhysicalChannelError
from twinklr.core.sequencer.models.template import TemplateDoc
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    RenderRefusedError,
    admit_templates,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid


def _rig(edit: Callable[[dict[str, Any]], None] | None = None) -> FixtureGroup:
    payload = p1_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        if edit is not None:
            edit(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _slow(profile: dict[str, Any]) -> None:
    for name in ("pan", "tilt"):
        profile["axes"][name]["travel_speed_per_s"] = 45.0


def _gate(doc: TemplateDoc, grid: BeatGrid, rig: FixtureGroup, job: JobConfig) -> str:
    """The gate's refusal, or "" when it admits the template."""
    with registered_templates(doc):
        try:
            admit_templates(
                [doc.template.template_id],
                beat_grid=grid,
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode=job.moving_heads.reposition_fallback,
                on_unplayable=job.moving_heads.on_unplayable,
            )
        except UnsupportedRenderModeError as error:
            return str(error)
    return ""


def _render_fails(
    doc: TemplateDoc,
    sections: tuple[tuple[str, int, int], ...],
    grid: BeatGrid,
    rig: FixtureGroup,
    job: JobConfig,
) -> str:
    """Why the render refuses the plan, or "" when it renders."""
    with registered_templates(doc):
        try:
            RenderingPipeline(
                choreography_plan=sections_plan(*sections),
                beat_grid=grid,
                fixture_group=rig,
                job_config=job,
                output_path=None,
            ).render()
        except (RenderRefusedError, PhysicalChannelError) as error:
            return str(error)
    return ""


def _dark(job: JobConfig) -> JobConfig:
    """`job` keeping what cannot play dark: the render's safety net behind the gate."""
    policy = job.moving_heads.model_copy(update={"on_unplayable": "dark"})
    return job.model_copy(update={"moving_heads": policy})


def test_a_cycle_started_on_another_bar_meets_that_bars_tempo() -> None:
    """A 2-bar cycle: a hold bar, then a 45-degree out-and-back over one bar. Bar 3 is
    fast (400 ms beats), the rest slow (600 ms). From bar 1 the move falls on bars 2, 4
    and 6 at 37.5 degrees/s; a section starting on bar 2 puts it on bar 3 at 56 degrees/s,
    over a 45 degrees/s rig. The gate checks every alignment and refuses it."""
    doc = loop_template_doc(
        "gp_align",
        [
            hold_step("a", 0.0),
            sweep_step("b", 0.0, 45.0, period_beats=2.0, start=1.0, duration=0.5),
            sweep_step("c", 45.0, -45.0, period_beats=2.0, start=1.5, duration=0.5),
        ],
        cycle_bars=2.0,
    )
    grid = bars_grid(600.0, 600.0, 400.0, 600.0, 600.0, 600.0)
    rig, job = _rig(_slow), p1_job(on_unplayable="error")

    assert "travels" in _render_fails(doc, (("gp_align", 1, 1), ("gp_align", 2, 5)), grid, rig, job)
    assert _render_fails(doc, (("gp_align", 1, 1), ("gp_align", 2, 5)), grid, rig, _dark(job)) == ""
    assert "travels 56.25" in _gate(doc, grid, rig, job)


def test_a_remainder_replaying_the_last_step_is_checked() -> None:
    """Two linear sweeps per 2-bar cycle, out then back. A 3-bar section leaves a 1-bar
    `HOLD_LAST_POSE` remainder that replays the back sweep from its start: the pose jumps
    30 degrees at the remainder (review M1). The gate compiles every remainder length."""
    doc = loop_template_doc(
        "gp_remainder",
        [sweep_step("a", 0.0, 30.0), sweep_step("b", 30.0, -30.0, start=1.0)],
        cycle_bars=2.0,
    )
    grid = bars_grid(*[500.0] * 4)
    rig, job = p1_rig(), p1_job(on_unplayable="error")

    assert "jumps" in _render_fails(
        doc, (("gp_remainder", 1, 3), ("gp_remainder", 4, 4)), grid, rig, job
    )
    assert "jumps" in _gate(doc, grid, rig, job)
    # Under `dark` the gate leaves section ends to the render, which keeps the jump dark.
    assert _gate(doc, grid, rig, _dark(job)) == ""
    plan = (("gp_remainder", 1, 3), ("gp_remainder", 4, 4))
    assert _render_fails(doc, plan, grid, rig, _dark(job)) == ""


def test_a_remainder_wheel_turn_under_an_overlay_is_checked() -> None:
    """Review M1 for wheels: the end mask of a colour overlay turns the wheel into the
    next cycle's red (120 ms settle) in every full cycle, but into the remainder's replay
    of blue (140 ms) after a 3-bar section."""
    doc = loop_template_doc(
        "gp_remainder_color",
        [
            hold_step("a", 0.0, color="red"),
            hold_step("b", 0.0, start=1.0, color="blue"),
        ],
        cycle_bars=2.0,
        overlays=[
            overlay("color", 2.0, 6.0, 0.5, "white"),
            overlay("color", 6.0, 8.0, 0.24, "white"),
        ],
    )
    grid = bars_grid(*[500.0] * 4)
    rig, job = p1_rig(), p1_job(on_unplayable="error")

    assert _render_fails(
        doc, (("gp_remainder_color", 1, 3), ("gp_remainder_color", 4, 4)), grid, rig, job
    )
    assert "infeasible_transition" in _gate(doc, grid, rig, job)
    assert _gate(doc, grid, rig, _dark(job)) == ""
    plan = (("gp_remainder_color", 1, 3), ("gp_remainder_color", 4, 4))
    assert _render_fails(doc, plan, grid, rig, _dark(job)) == ""


def test_a_drop_cascade_entered_at_another_cue_is_checked() -> None:
    """Under `drop_accent`, a hold at 0 degrees then a hold at 60 (red) that alone declares
    the fallback: from a cycle's start the 60-degree cue can never follow the first and is
    always dropped, so the gate saw a clean template. A section whose entry window drops
    its first cue reveals the 60-degree cue first; it plays, and the next cycle's first
    cue, which may not be dropped, cannot follow it (seed 1892). The gate enters each
    placement at each of its first cycle's cues and refuses the template."""
    doc = loop_template_doc(
        "gp_cascade",
        [
            hold_step("a", 0.0, duration=0.5),
            hold_step(
                "b",
                60.0,
                start=0.5,
                duration=0.5,
                color="red",
                reposition_fallback="drop_accent",
            ),
        ],
    )
    grid = bars_grid(*[500.0] * 6)
    rig, job = _rig(_slow), p1_job(reposition_fallback="drop_accent", on_unplayable="error")

    assert _render_fails(doc, (("gp_cascade", 1, 2), ("gp_cascade", 3, 6)), grid, rig, job)
    assert not _render_fails(
        doc, (("gp_cascade", 1, 2), ("gp_cascade", 3, 6)), grid, rig, _dark(job)
    )
    assert "infeasible_transition" in _gate(doc, grid, rig, job)


def test_a_first_cue_a_window_cuts_rather_than_drops_is_checked() -> None:
    """Under `drop_accent`, a hold at 40 degrees (star gobo) that may be dropped, then a
    hold at 38 (dots) that may not. From the initial state at 0 degrees the song's first
    window, sized for a 40-degree move on a 45 degrees/s rig, drops the first cue whole.
    After a section that ends on the 38-degree cue the window needs only the gobo turn,
    so it cuts the first cue and reveals it, and the next cue cannot turn the gobo back
    (seed 437). The gate enters each cue of the first cycle revealed, not only where the
    initial state's window happens to leave it."""
    doc = loop_template_doc(
        "gp_window_cut",
        [
            hold_step(
                "a",
                40.0,
                duration=0.5,
                gobo="star",
                reposition_fallback="drop_accent",
            ),
            hold_step("b", 38.0, start=0.5, duration=0.5, gobo="dots"),
        ],
    )
    grid = bars_grid(*[500.0] * 4)
    rig, job = _rig(_slow), p1_job(reposition_fallback="drop_accent", on_unplayable="error")

    assert _render_fails(doc, (("gp_window_cut", 1, 4),), grid, rig, job) == ""
    assert "gobo" in _render_fails(
        doc, (("gp_window_cut", 1, 1), ("gp_window_cut", 2, 4)), grid, rig, job
    )
    plan = (("gp_window_cut", 1, 1), ("gp_window_cut", 2, 4))
    assert _render_fails(doc, plan, grid, rig, _dark(job)) == ""
    assert "gobo" in _gate(doc, grid, rig, job)


@pytest.mark.parametrize("cycle_bars", [1.0, 2.0])
def test_a_template_that_renders_everywhere_is_still_admitted(cycle_bars: float) -> None:
    """The wider gate refuses nothing that renders at every placement: a continuous hold
    and a periodic sine on a variable-tempo song."""
    doc = loop_template_doc(
        f"gp_clean_{cycle_bars:g}",
        [hold_step("a", 10.0, duration=cycle_bars)],
        cycle_bars=cycle_bars,
    )
    grid = bars_grid(500.0, 600.0, 400.0, 500.0, 700.0, 500.0)
    assert _gate(doc, grid, p1_rig(), p1_job(on_unplayable="error")) == ""


def test_every_alignment_of_a_three_bar_cycle_is_checked() -> None:
    """A 3-bar cycle moving in its third bar puts the move on bars 3 and 6 from bar 1, 4
    and 7 from bar 2, and 5 and 8 from bar 3. Only bar 5 is fast, so only the alignment
    from bar 3 outruns the head; under `dark`, where the gate checks alignments alone,
    it refuses the template there."""
    doc = loop_template_doc(
        "gp_align_3",
        [
            hold_step("a", 0.0, duration=2.0),
            sweep_step("b", 0.0, 45.0, period_beats=2.0, start=2.0, duration=0.5),
            sweep_step("c", 45.0, -45.0, period_beats=2.0, start=2.5, duration=0.5),
        ],
        cycle_bars=3.0,
    )
    grid = bars_grid(*([600.0] * 4 + [400.0] + [600.0] * 4))
    rig, job = _rig(_slow), _dark(p1_job())

    assert "placed at bar 3" in _gate(doc, grid, rig, job)
    assert _render_fails(doc, (("gp_align_3", 1, 2), ("gp_align_3", 3, 9)), grid, rig, job) == ""


def test_a_section_shorter_than_its_cycle_is_compiled() -> None:
    """Step `b` starts 0.001 bar before the first bar ends: in a 1-bar section it is cut
    to nothing on the frame grid and the compile refuses it. A whole cycle never cuts it,
    and a `HOLD_LAST_POSE` remainder replays `b` whole, so only the short section shows
    it."""
    doc = loop_template_doc(
        "gp_short",
        [
            hold_step("a", 0.0, duration=0.999),
            hold_step("b", 0.0, start=0.999, duration=1.001),
        ],
        cycle_bars=2.0,
        remainder_policy="HOLD_LAST_POSE",
    )
    grid = bars_grid(*[500.0] * 4)
    rig, job = p1_rig(), p1_job(on_unplayable="error")

    assert "leaves no frame" in _gate(doc, grid, rig, job)
    plan = (("gp_short", 1, 1), ("gp_short", 2, 4))
    with registered_templates(doc), pytest.raises(ValueError, match="leaves no frame"):
        RenderingPipeline(
            choreography_plan=sections_plan(*plan),
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            output_path=None,
        ).render()
    assert _render_fails(doc, plan, grid, rig, _dark(job)) == ""


def test_the_song_start_enters_from_the_initial_state_too() -> None:
    """With unknown travel speed, a hold at 30 degrees plays from a head revealed already
    there, but not from the initial state at 0 degrees at the song start: the gate plans
    that entry as well and refuses the template."""

    def unknown_speed(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            profile["axes"][name]["travel_speed_per_s"] = None

    doc = loop_template_doc("gp_song_start", [hold_step("h", 30.0)])
    grid = bars_grid(*[500.0] * 4)
    rig, job = _rig(unknown_speed), _dark(p1_job())

    assert "unknown_motion_rate" in _gate(doc, grid, rig, job)
    assert "unknown_motion_rate" in _render_fails(
        doc, (("gp_song_start", 1, 4),), grid, rig, p1_job(on_unplayable="error")
    )


def test_the_gate_cache_never_shares_a_cue_between_profiles() -> None:
    """MH2's pan stops at 60 degrees, MH1's does not: a hold at 90 compiles on MH1 and is
    refused on MH2, whose cue must not come from MH1's."""

    def narrow(profile: dict[str, Any]) -> None:
        profile["axes"]["pan"]["physical_max"] = 60.0

    payload = p1_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for name in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][name]["inverted"] = False
        if fixture["fixture_id"] == "MH2":
            narrow(fixture["config"]["physical_profile"])
    rig = FixtureGroup.model_validate(payload)
    doc = loop_template_doc("gp_cache_profile", [hold_step("h", 90.0)])

    refusal = _gate(doc, bars_grid(*[500.0] * 4), rig, p1_job())
    assert "'MH2'" in refusal and "'MH1'" not in refusal


def test_the_gate_cache_never_shares_a_cue_between_resolved_components() -> None:
    """Both heads share one profile; the rig's position preset aims MH2 past its pan
    range. MH2's cue must not come from MH1's."""
    presets = {
        "positions": {
            "aim": {
                "fixtures": {
                    "MH1": {"pan_deg": 10.0, "tilt_deg": 0.0},
                    "MH2": {"pan_deg": 300.0, "tilt_deg": 0.0},
                }
            }
        },
        "attributes": {},
    }
    rig = topology_rig(("MH1", "MH2"), presets=presets)
    doc = loop_template_doc(
        "gp_cache_components", [referencing_step("h", position_id="aim", attribute_preset_ids=())]
    )

    refusal = _gate(doc, bars_grid(*[500.0] * 4), rig, p1_job())
    assert "'MH2'" in refusal and "'MH1'" not in refusal


def test_the_gate_restores_the_garbage_collector_however_it_ends() -> None:
    """The gate pauses cyclic collection while it runs; it leaves the collector as it
    found it, after admitting, after refusing, and when it was already paused."""
    grid, rig, job = bars_grid(500.0, 500.0, 500.0), p1_rig(), p1_job()
    still = loop_template_doc("p3_gc_still", [hold_step("still", 0.0)])
    jump = loop_template_doc("p3_gc_jump", [sweep_step("go", 0.0, 120.0)])
    enabled = gc.isenabled()
    try:
        gc.enable()
        assert _gate(still, grid, rig, job) == ""
        assert gc.isenabled()
        assert _gate(jump, grid, rig, job) != ""
        assert gc.isenabled()
        gc.disable()
        assert _gate(still, grid, rig, job) == ""
        assert not gc.isenabled()
        assert _gate(jump, grid, rig, job) != ""
        assert not gc.isenabled()
    finally:
        if enabled:
            gc.enable()
        else:
            gc.disable()
