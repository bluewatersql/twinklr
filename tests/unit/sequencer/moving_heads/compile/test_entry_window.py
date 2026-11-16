"""Section entry windows (P2.4a): a section of a physical render whose first cue cannot
be played as authored after the previous one opens with a derived dark window long
enough for any reposition into it; an entry that plays as authored is kept uncut.

Every render below is gated first (the gate must admit it), then replanned from its cues
and checked from its bytes (`assert_honest_transactions`) on every fixture: no head is
lit while it moves.

The gate's differential fuzz runs the grids known to catch a reduced gate plus 6 random
ones; set `TWINKLR_P24A_FUZZ=full` to sweep 60 random grids as at review.
"""

from __future__ import annotations

from collections.abc import Callable
import os
import random
from typing import Any

import pytest

from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    assert_honest_transactions,
    hold_step,
    physical_bars_grid,
    physical_job,
    physical_rig,
    physical_sections,
    physical_segment,
    physical_template_doc,
    physical_test_templates,
    registered_templates,
    sine_step,
    sweep_step,
    topology_payload,
    topology_rig,
)
from twinklr.core.config.fixtures import FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.curves.registry import CurveRegistry
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import StepCompileContext, TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscretePoint,
    DiscreteTrajectory,
    PhysicalChannelError,
    PhysicalPoint,
)
from twinklr.core.sequencer.models.template import TemplateDoc, TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.compile.step_compiler import compile_step
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    apply_entry_window,
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.handlers.defaults import create_default_registries
from twinklr.core.sequencer.moving_heads.pipeline import (
    PhysicalRenderError,
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.moving_heads.templates import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_LEFT = physical_template_doc("p24a_left", [hold_step("hold", -90.0)])
_LEFT_RED = physical_template_doc("p24a_left_red", [hold_step("hold", -90.0, physical_color="red")])
_LEFT_NEAR = physical_template_doc("p24a_left_near", [hold_step("hold", -80.0)])
_LEFT_FAR = physical_template_doc("p24a_left_far", [hold_step("hold", -60.0)])
_RIGHT = physical_template_doc("p24a_right", [hold_step("hold", 90.0)])
_CENTER = physical_template_doc("p24a_center", [hold_step("hold", 0.0)])
_CENTER_NEAR = physical_template_doc("p24a_center_near", [hold_step("hold", 10.0)])
_RIGHT_ONLY = physical_template_doc("p24a_right_only", [hold_step("hold", 90.0, target="RIGHT")])
_SHORT_HIT = physical_template_doc(
    "p24a_short_hit", [hold_step("hit", 90.0, duration=0.25)], cycle_bars=0.25
)
"""One-beat cues, back to back."""
_SWEEP = physical_template_doc(
    "p24a_sweep",
    [
        sweep_step("out", 10.0, 200.0, period_beats=3.0, duration=0.75),
        sweep_step("back", 210.0, -200.0, period_beats=1.0, start=0.75, duration=0.25),
    ],
)
"""Pan 10 to 210 degrees over three beats, then back over one, lit throughout."""


def _jump(fallback: str | None = "drop_accent") -> Any:
    """Two lit steps per cycle, back to back at -90 and +90 degrees: the second cannot
    continue the first, so only a declared fallback lets the template render."""
    extra = {} if fallback is None else {"physical_reposition_fallback": fallback}
    steps = [
        hold_step("left", -90.0, duration=0.5, **extra),
        hold_step("right", 90.0, start=0.5, duration=0.5, **extra),
    ]
    return physical_template_doc("p24a_jump" if fallback else "p24a_jump_plain", steps)


_DOCS = (_LEFT, _LEFT_RED, _LEFT_NEAR, _LEFT_FAR, _RIGHT, _CENTER, _RIGHT_ONLY, _SHORT_HIT)
_DOCS += (_CENTER_NEAR,)
_DOCS += (_SWEEP, _jump(), _jump(None))


def _grid(*beat_ms: float) -> BeatGrid:
    return physical_bars_grid(*(beat_ms or (500.0,) * 6))


def _slow_rig() -> FixtureGroup:
    """`physical_rig` with pan and tilt at 45 degrees/s: 180 degrees take four seconds."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        for axis in ("pan", "tilt"):
            fixture["config"]["physical_profile"]["axes"][axis]["travel_speed_per_s"] = 45.0
    return FixtureGroup.model_validate(payload)


def _render(
    *sections: tuple[str, int, int],
    grid: BeatGrid | None = None,
    rig: FixtureGroup | None = None,
    job: JobConfig | None = None,
    docs: tuple[TemplateDoc, ...] = (),
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    """Gate the sections' templates, render them and check every fixture's transactions
    from its bytes: the gate must admit what renders."""
    grid, rig, job = grid or _grid(), rig or physical_rig(), job or physical_job()
    policy = job.moving_heads
    with registered_templates(*_DOCS, *docs):
        check_physical_templates(
            sorted({template_id for template_id, _, _ in sections}),
            beat_grid=grid,
            fixture_group=rig,
            initial_states=policy.initial_states,
            failure_mode=policy.reposition_fallback,
        )
        pipeline = RenderingPipeline(
            choreography_plan=physical_sections(*sections),
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            output_path=None,
        )
        segments = pipeline.render()
    cues = _cues(segments)
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    replanned = plan_prepositions(
        cues,
        profiles,  # type: ignore[arg-type]
        initial_states=policy.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=policy.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        assert profile is not None
        initial = policy.initial_states[fixture_id]
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)
    return pipeline, segments


def _cues(segments: list[FixtureSegment], section_id: str | None = None) -> list[FixtureSegment]:
    return [
        s
        for s in segments
        if TRANSACTION_METADATA_KEY not in s.metadata
        and (section_id is None or s.section_id == section_id)
    ]


def _first(segments: list[FixtureSegment], section_id: str, fixture_id: str) -> FixtureSegment:
    return min(
        (c for c in _cues(segments, section_id) if c.fixture_id == fixture_id),
        key=lambda c: c.t0_ms,
    )


def _windows(pipeline: RenderingPipeline, section_id: str) -> dict[str, dict[str, Any]]:
    assert pipeline.render_record is not None
    records = [w for w in pipeline.render_record["entry_windows"] if w["section_id"] == section_id]
    assert len(records) == len({w["fixture_id"] for w in records})
    return {w["fixture_id"]: w for w in records}


def _transaction(pipeline: RenderingPipeline, fixture_id: str, cue_ms: int) -> dict[str, Any]:
    assert pipeline.render_record is not None
    (record,) = [
        d
        for d in pipeline.render_record["transactions"]
        if d["fixture_id"] == fixture_id and d["cue_ms"] == cue_ms
    ]
    return record


def _pan(cue: FixtureSegment) -> float:
    trajectory = cue.channels[ChannelName.PAN].physical
    assert isinstance(trajectory, ContinuousTrajectory)
    return trajectory.points[0].value


# --- The window -------------------------------------------------------------------------


def test_entry_window_cuts_first_cue_and_keeps_phase_origin() -> None:
    """The second section's sweep starts at the window end, where its uncut path is, not
    at its own start: its phase origin stays the quantized section start."""
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_sweep", 3, 4))

    windows = _windows(pipeline, "s2")
    for fixture_id in ("MH1", "MH2"):
        first = _first(segments, "s2", fixture_id)
        assert windows[fixture_id]["action"] == "cut"
        assert first.t0_ms == windows[fixture_id]["window_end_ms"] > 4020
        assert first.metadata["phase_origin_ms"] == "4020"
        assert first.metadata["requested_t0_ms"] == "4015"
        # Linear over three 500 ms beats from the origin: 200 degrees in 1500 ms.
        assert _pan(first) == pytest.approx(10.0 + 200.0 * (first.t0_ms - 4020) / 1500)


def test_entry_window_is_whole_beats_at_the_section_tempo_ending_on_the_frame_grid() -> None:
    """Bars 3-4 have 400 ms beats: the window is the fewest of those beats from the
    section start whose frame-rounded end leaves the bound after the previous cue."""
    grid = _grid(500.0, 500.0, 400.0, 400.0)
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_right", 3, 4), grid=grid)

    beats = grid.beat_boundaries
    assert beats[8] == 4015.0  # the section start, with 400 ms beats from here
    for fixture_id, window in _windows(pipeline, "s2").items():
        end = window["window_end_ms"]
        whole = [k for k in range(9, len(beats)) if -(-beats[k] // EFFECT_GRID_MS) * 20 == end]
        assert whole, f"{fixture_id}: window end {end} is not a frame-rounded beat"
        gap_start = 4020  # the first section's last cue ends at the quantized boundary
        assert gap_start + window["bound_ms"] <= end
        assert -(-beats[whole[0] - 1] // EFFECT_GRID_MS) * 20 < gap_start + window["bound_ms"]
        assert end % EFFECT_GRID_MS == 0
        assert window["window_ms"] == end - 4015
        assert _first(segments, "s2", fixture_id).t0_ms == end
    assert {w["window_end_ms"] for w in _windows(pipeline, "s2").values()} == {4420}


def test_entry_window_applies_once_per_section_not_per_cycle() -> None:
    """Four one-bar cycles at one aim: only the first is cut; the others continue it."""
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_right", 3, 6))

    for fixture_id in ("MH1", "MH2"):
        starts = sorted(c.t0_ms for c in _cues(segments, "s2") if c.fixture_id == fixture_id)
        assert starts[0] > 4020 and starts[1:] == [6020, 8020, 10020]
        for cue_ms in starts[1:]:
            record = _transaction(pipeline, fixture_id, cue_ms)
            assert record["available_ms"] == 0
            assert record["reason"] == "continues the previous cue without a gap"
    assert set(_windows(pipeline, "s2")) == {"MH1", "MH2"}


def test_cue_inside_entry_window_is_dropped_with_a_record() -> None:
    """The section's first one-beat hit lies wholly inside its one-beat window."""
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_short_hit", 3, 4))

    assert pipeline.render_record is not None
    window = {
        (d["fixture_id"], d["requested_start_ms"]): d
        for d in pipeline.render_record["dropped_cues"]
    }
    for fixture_id in ("MH1", "MH2"):
        end = _windows(pipeline, "s2")[fixture_id]["window_end_ms"]
        assert end == 4520  # one beat
        record = window[(fixture_id, 4015)]
        assert record["section_id"] == "s2" and record["step_id"] == "hit"
        assert record["entry_window_end_ms"] == end
        assert record["reason"] == "entry_window"
        # The hits after the window play as compiled.
        starts = [c.t0_ms for c in _cues(segments, "s2") if c.fixture_id == fixture_id]
        assert starts == list(range(4520, 8020, 500))


def test_section_shorter_than_its_window_renders_dark_with_a_record() -> None:
    """At 45 degrees/s the 180-degree entry into bar 3 needs more than its one bar: the
    section renders dark, recorded, and the next section enters from the first's aim."""
    pipeline, segments = _render(
        ("p24a_left", 1, 2), ("p24a_right", 3, 3), ("p24a_left", 4, 5), rig=_slow_rig()
    )

    assert pipeline.render_record is not None
    assert _cues(segments, "s2") == []
    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == "cut"
        assert window["window_end_ms"] >= 6020  # past the section's end
        dropped = [
            d
            for d in pipeline.render_record["dropped_cues"]
            if d["fixture_id"] == fixture_id and d["section_id"] == "s2"
        ]
        assert [d["requested_start_ms"] for d in dropped] == [4015]
    for frame in pipeline.frames:
        channels = dict(frame.channels)
        if 4020 <= frame.time_ms < 6020:
            assert channels[17] == 64 and channels[5] == 0  # shutter closed, dimmer zero


# --- The dip skip -----------------------------------------------------------------------


def test_dip_skipped_when_predecessor_ends_where_successor_begins() -> None:
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_left", 3, 4))

    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == "skipped"
        assert _first(segments, "s2", fixture_id).t0_ms == 4020
        assert _transaction(pipeline, fixture_id, 4020)["available_ms"] == 0


def test_dip_kept_on_a_wheel_change() -> None:
    pipeline, segments = _render(("p24a_left", 1, 2), ("p24a_left_red", 3, 4))

    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == "cut"
        assert _first(segments, "s2", fixture_id).t0_ms == window["window_end_ms"] > 4020


@pytest.mark.parametrize(
    ("template_id", "action"),
    [
        pytest.param("p24a_left_far", "cut", id="30-degrees-is-more-than-a-frame"),
        pytest.param("p24a_left_near", "skipped", id="10-degrees-fits-one-frame"),
    ],
)
def test_dip_kept_on_more_than_one_frame_of_travel(template_id: str, action: str) -> None:
    """At 720 degrees/s one 20 ms frame covers 14.4 degrees."""
    pipeline, segments = _render(("p24a_left", 1, 2), (template_id, 3, 4))

    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == action
        expected = window["window_end_ms"] if action == "cut" else 4020
        assert _first(segments, "s2", fixture_id).t0_ms == expected


def test_window_fits_a_moving_first_cue_cut_at_its_end() -> None:
    """The sweep enters 70 degrees from the predecessor's aim, but cut at the window end
    it starts farther away; the window is sized for the section's whole range."""
    pipeline, segments = _render(("p24a_left_far", 1, 2), ("p24a_sweep", 3, 4))

    for fixture_id in ("MH1", "MH2"):
        first = _first(segments, "s2", fixture_id)
        assert first.t0_ms == _windows(pipeline, "s2")[fixture_id]["window_end_ms"] > 4020
        assert abs(_pan(first) - -60.0) > abs(10.0 - -60.0)


# --- The predecessor ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sections", "rig", "fallback"),
    [
        pytest.param(
            (("p24a_left", 1, 2), ("p24a_right_only", 3, 4), ("p24a_right", 5, 6)),
            physical_rig,
            None,
            id="previous-section-has-no-cue-on-the-fixture",
        ),
        pytest.param(
            (("p24a_left", 1, 2), ("p24a_short_hit", 3, 3), ("p24a_center", 4, 5)),
            physical_rig,
            None,
            id="every-cue-of-the-previous-section-was-dropped",
        ),
        pytest.param(
            (("p24a_left", 1, 2), ("p24a_right", 3, 3), ("p24a_center", 4, 6)),
            _slow_rig,
            None,
            id="previous-section-was-shorter-than-its-window",
        ),
        pytest.param(
            (("p24a_jump", 1, 2), ("p24a_right", 3, 4)),
            physical_rig,
            "drop_accent",
            id="previous-cue-was-substituted-under-drop-accent",
        ),
    ],
)
def test_entry_is_sized_from_the_last_kept_cue(
    sections: tuple[tuple[str, int, int], ...], rig: Any, fallback: str | None
) -> None:
    """Each case renders without a transaction error (checked from the bytes by
    `_render`): the entry is sized from where the last kept cue left each head."""
    job = physical_job(reposition_fallback=fallback) if fallback else physical_job()
    pipeline, _ = _render(*sections, rig=rig(), job=job)

    assert pipeline.render_record is not None
    assert all(d["status"] != "error" for d in pipeline.render_record["transactions"])


# --- Fallbacks --------------------------------------------------------------------------


def test_a_declared_drop_accent_keeps_the_cue_dark_and_error_refuses() -> None:
    pipeline, segments = _render(
        ("p24a_jump", 1, 4), job=physical_job(reposition_fallback="drop_accent")
    )

    assert pipeline.render_record is not None
    dropped = [d for d in pipeline.render_record["transactions"] if d["status"] == "drop_accent"]
    assert all(d["code"] == "infeasible_transition" for d in dropped)
    # Every "right" cue (half a bar into each bar) is kept dark at the aim "left" left.
    assert {(d["fixture_id"], d["cue_ms"]) for d in dropped} == {
        (fixture_id, cue_ms) for fixture_id in ("MH1", "MH2") for cue_ms in (1020, 3020, 5020, 7020)
    }
    assert not [c for c in _cues(segments) if c.step_id == "right"]
    assert all(c.metadata[FALLBACK_METADATA_KEY] == "drop_accent" for c in _cues(segments))
    for frame in pipeline.frames:
        if any(start <= frame.time_ms < start + 1000 for start in (1020, 3020, 5020, 7020)):
            assert dict(frame.channels)[5] == 0

    with registered_templates(*_DOCS), pytest.raises(PhysicalRenderError, match="jumps across"):
        RenderingPipeline(
            choreography_plan=physical_sections(("p24a_jump", 1, 4)),
            beat_grid=_grid(),
            fixture_group=physical_rig(),
            job_config=physical_job(on_unplayable="error"),
            output_path=None,
        ).render()


@pytest.mark.parametrize(
    "config_path",
    [
        "job.moving_heads.reposition_fallback",
        "template.template.steps.physical_reposition_fallback",
    ],
)
def test_reposition_fallback_field_changes_preposition(config_path: str) -> None:
    """Both opt-ins are needed: with the job policy and the step's declaration a cue that
    cannot reposition is kept dark; resetting either one to its default refuses it."""
    _render(("p24a_jump", 1, 2), job=physical_job(reposition_fallback="drop_accent"))

    job = physical_job(reposition_fallback="drop_accent", on_unplayable="error")
    template_id = "p24a_jump"
    if config_path.startswith("job."):
        job = physical_job(on_unplayable="error")
    else:
        template_id = "p24a_jump_plain"
    with registered_templates(*_DOCS), pytest.raises(PhysicalRenderError, match="jumps across"):
        RenderingPipeline(
            choreography_plan=physical_sections((template_id, 1, 2)),
            beat_grid=_grid(),
            fixture_group=physical_rig(),
            job_config=job,
            output_path=None,
        ).render()


# --- apply_entry_window ------------------------------------------------------------------


def test_apply_entry_window_cuts_drops_and_skips() -> None:
    """Directly: a cue across the window end is sliced there, one inside it is dropped
    with a record, a later one is untouched, and a skipped fixture keeps its cues."""

    def cue(fixture_id: str, t0: int, t1: int) -> FixtureSegment:
        line = ContinuousTrajectory(
            unit="degree",
            points=(
                PhysicalPoint(t_ms=t0, value=0.0),
                PhysicalPoint(t_ms=t1, value=float(t1 - t0)),
            ),
            interpolation="linear",
        )
        segment = physical_segment(
            {ChannelName.PAN: line, ChannelName.TILT: line},
            t0_ms=t0,
            t1_ms=t1,
            fixture_id=fixture_id,
            segment_id=f"{fixture_id}-{t0}",
        )
        segment.add_metadata("requested_t0_ms", t0 - 5)
        segment.add_metadata("requested_t1_ms", t1 - 5)
        return segment

    inside, across, after = cue("MH1", 0, 100), cue("MH1", 100, 300), cue("MH1", 300, 400)
    skipped = cue("MH2", 0, 100)

    profile = physical_rig().expand_fixtures()[0].config.physical_profile
    assert profile is not None
    kept, dropped = apply_entry_window(
        [inside, across, after, skipped], {"MH1": 200}, profiles={"MH1": profile, "MH2": profile}
    )

    assert [(c.fixture_id, c.t0_ms, c.t1_ms) for c in kept] == [
        ("MH1", 200, 300),
        ("MH1", 300, 400),
        ("MH2", 0, 100),
    ]
    assert _pan(kept[0]) == pytest.approx(100.0)
    assert kept[0].segment_id == across.segment_id and kept[2] is skipped
    assert dropped == [
        {
            "fixture_id": "MH1",
            "section_id": "section",
            "step_id": "step",
            "requested_start_ms": -5,
            "requested_end_ms": 95,
            "start_ms": 0,
            "end_ms": 100,
            "entry_window_end_ms": 200,
        }
    ]


def test_reposition_fallback_is_physical_only_and_absent_from_dumps() -> None:
    """Unset, the step field is left out of the template's dump (so no fingerprint moves);
    set, it is physical data, which the legacy compile refuses."""
    payload = {
        "step_id": "legacy",
        "timing": {"base_timing": {"start_offset_bars": 0, "duration_bars": 1}},
        "geometry": {},
        "movement": {"movement_type": "sweep_lr"},
        "dimmer": {"dimmer_type": "hold"},
    }
    assert "physical_reposition_fallback" not in TemplateStep.model_validate(payload).model_dump()
    legacy = TemplateStep.model_validate({**payload, "physical_reposition_fallback": "drop_accent"})
    assert legacy.has_physical_data
    registries = create_default_registries()
    context = StepCompileContext(
        section_id="verse",
        segment_id="A",
        template_id="legacy_probe",
        fixture_id="MH1",
        role="OUTER_LEFT",
        calibration={},
        start_ms=0,
        duration_ms=1000,
        beat_grid=_grid(),
        curve_registry=CurveRegistry(),
        geometry_registry=registries["geometry"],
        movement_registry=registries["movement"],
        dimmer_registry=registries["dimmer"],
    )
    with pytest.raises(ValueError, match="physical_v2"):
        compile_step(legacy, context)


# --- Review fixes ----------------------------------------------------------------------


def _rig(edit: Callable[[dict[str, Any]], None]) -> FixtureGroup:
    """`physical_rig` with the same edit applied to both heads' profiles."""
    payload = physical_rig().model_dump(mode="json")
    for fixture in payload["fixtures"]:
        edit(fixture["config"]["physical_profile"])
    return FixtureGroup.model_validate(payload)


def _coarse(speed: float) -> Callable[[dict[str, Any]], None]:
    """8-bit pan and tilt at `speed` degrees/s with no latency or settle."""

    def edit(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            axis = profile["axes"][name]
            axis.pop("fine_offset")
            axis.update(travel_speed_per_s=speed, latency_ms=0, settle_ms=0)

    return edit


def _sine_step(step_id: str, pan: float, extent: float, period: float) -> dict[str, Any]:
    step = hold_step(step_id, pan)
    step["movement"]["physical"].update(
        shape="sine_pan", mode="periodic", pan_extent_deg=extent, period_beats=period
    )
    return step


def _uncut(
    sections: tuple[tuple[str, int, int], ...], grid: BeatGrid, rig: FixtureGroup
) -> list[FixtureSegment]:
    """Phase 1's render of the sections: every cue as compiled, planned in `error` mode."""
    job = physical_job()
    plan = physical_sections(*sections)
    with registered_templates(*_DOCS):
        return _plan_uncut(plan, grid, rig, job)


def _plan_uncut(
    plan: Any, grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> list[FixtureSegment]:
    pipeline = RenderingPipeline(
        choreography_plan=plan, beat_grid=grid, fixture_group=rig, job_config=job
    )
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    cues: list[FixtureSegment] = []
    for section in plan.sections:
        assert section.template_id is not None
        document = get_template(section.template_id)
        context = TemplateCompileContext(
            section_id=section.section_name,
            template_id=document.template.template_id,
            fixtures=pipeline._build_fixture_contexts(),
            beat_grid=grid,
            start_bar=section.start_bar,
            duration_bars=section.end_bar - section.start_bar + 1,
            curve_registry=pipeline.curve_registry,
            geometry_registry=pipeline.geometry_registry,
            movement_registry=pipeline.movement_registry,
            dimmer_registry=pipeline.dimmer_registry,
        )
        cues += compile_physical_template(
            document.template, context, phase_map=phase_map, start_limit_ms=start, end_limit_ms=end
        ).segments
    result = plan_prepositions(
        cues,
        {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()},  # type: ignore[misc]
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
    )
    assert not result.has_errors, result.diagnostics
    return list(result.segments)


@pytest.mark.parametrize(
    "sections",
    [
        pytest.param((("p24a_center", 1, 2),), id="lit-at-the-initial-aim-from-bar-1"),
        pytest.param(
            (("p1_linear_reveal", 1, 2), ("p1_linear_reveal", 3, 4)),
            id="phase-1-test-template-twice",
        ),
        pytest.param((("p24a_center", 1, 2), ("p24a_center_near", 3, 4)), id="within-a-frame"),
    ],
)
def test_an_entry_phase_1_plays_as_authored_is_kept_uncut(
    sections: tuple[tuple[str, int, int], ...],
) -> None:
    """Wherever the transaction pass already plays a section's first cue as authored, the
    render is Phase 1's, cue for cue: no window, so no output changes under an unchanged
    fingerprint (review H4; the first case was cut by a dark first beat)."""
    grid = _grid()
    with physical_test_templates():
        pipeline, segments = _render(*sections, grid=grid)
        reference = _uncut(sections, grid, physical_rig())
    assert segments == reference
    assert pipeline.render_record is not None
    assert {w["action"] for w in pipeline.render_record["entry_windows"]} == {"skipped"}


def test_a_cue_the_head_cannot_follow_is_refused_by_the_gate_and_the_compile() -> None:
    """A 0.55-degree sine every 0.16 beat straddling an 8-bit word boundary at 45.5
    degrees/s: each frame's word change takes 46 ms, so the head falls ever further
    behind (review H1, 9.5 s by the eighth bar). The compile refuses it, naming the
    fixture, the axis and the word-space rates."""
    rig = _rig(_coarse(45.5))
    profile = rig.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    axis = profile.axes["pan"]
    low, high = 0.0, 5.0  # the first word boundary above 0 degrees
    while high - low > 1e-9:
        middle = (low + high) / 2
        low, high = (middle, high) if axis.dmx_word(middle) == axis.dmx_word(0.0) else (low, middle)
    shake = physical_template_doc("p24a_shake", [_sine_step("s", low, 0.55, 0.16)])
    job = physical_job()
    with registered_templates(*_DOCS, shake):
        with pytest.raises(UnsupportedRenderModeError) as refused:
            check_physical_templates(
                ["p24a_shake"],
                beat_grid=_grid(),
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode="error",
            )
        with pytest.raises(PhysicalChannelError, match="trails its commands") as raised:
            RenderingPipeline(
                choreography_plan=physical_sections(("p24a_shake", 1, 4), ("p24a_right", 5, 6)),
                beat_grid=_grid(),
                fixture_group=rig,
                job_config=job,
                output_path=None,
            ).render()
    for message in (str(refused.value), str(raised.value)):
        assert "MH1 pan" in message or "MH2 pan" in message
        assert "word changes/s" in message and "words/s" in message


def test_the_gate_compiles_every_bar_so_an_isolated_fast_bar_is_refused() -> None:
    """One 400 ms-beat bar among 700 and 500 ms bars: a 40-degree out-and-back over two
    beats travels 50 degrees/s there on a 45 degrees/s rig (review H2). The gate compiles
    the whole song from bar 1, so it refuses the template the render would refuse."""
    rig = _rig(
        lambda profile: [
            profile["axes"][a].update(travel_speed_per_s=45.0) for a in ("pan", "tilt")
        ]
    )
    osc = physical_template_doc(
        "p24a_osc",
        [
            sweep_step("o", 0.0, 40.0, period_beats=2.0, duration=0.5),
            sweep_step("b", 40.0, -40.0, period_beats=2.0, start=0.5, duration=0.5),
        ],
    )
    grid = physical_bars_grid(700, 400, 700, 700, 500, 500, 500, 500, 700, 700)
    job = physical_job()
    with registered_templates(osc), pytest.raises(UnsupportedRenderModeError, match="travels 50"):
        check_physical_templates(
            ["p24a_osc"],
            beat_grid=grid,
            fixture_group=rig,
            initial_states=job.moving_heads.initial_states,
            failure_mode="error",
        )


def _pulse_rig(open_settle: int) -> FixtureGroup:
    def edit(profile: dict[str, Any]) -> None:
        profile["discrete"]["shutter"]["states"]["open"]["settle_ms"] = open_settle

    return _rig(edit)


def _pulse_doc() -> TemplateDoc:
    """At +90 degrees, the shutter open for half a beat across every odd beat."""
    step = hold_step("p", 90.0)
    step.pop("physical_shutter_state")
    step["physical_shutter"] = {
        "period_beats": 2.0,
        "duty_cycle": 0.25,
        "phase_cycles": -0.375,
        "low_state": "closed",
        "high_state": "open",
    }
    return physical_template_doc("p24a_pulse", [step])


@pytest.mark.parametrize("open_settle", [0, 130, 150, 200])
def test_a_cut_never_leaves_a_shutter_state_too_short_to_take_effect(open_settle: int) -> None:
    """Cut at the window end inside an open pulse, a 150 ms open settle left the open
    state 140 ms (review H3). The cut now moves on to the pulse's next change, so the
    gate and the render agree; every first state after a cut holds long enough."""
    rig = _pulse_rig(open_settle)
    grid = physical_bars_grid(560, 560, 560, 500, 500, 500, 500, 500)
    pipeline, segments = _render(
        ("p24a_left", 1, 2), ("p24a_pulse", 3, 8), grid=grid, rig=rig, docs=(_pulse_doc(),)
    )
    for window in _windows(pipeline, "s2").values():
        first = _first(segments, "s2", window["fixture_id"])
        assert first.t0_ms == window["first_cue_ms"] >= (window["window_end_ms"] or 0)


def test_apply_entry_window_moves_a_cut_past_a_shutter_state_it_cannot_hold() -> None:
    """Directly: open from 100 to 140 ms needs its 150 ms settle; the cut at 120 ms moves
    to the close at 140 ms, which takes effect at once."""
    profile = _pulse_rig(150).expand_fixtures()[0].config.physical_profile
    assert profile is not None
    line = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=0, value=0.0), PhysicalPoint(t_ms=400, value=0.0)),
        interpolation="linear",
    )
    shutter = DiscreteTrajectory(
        events=tuple(
            DiscretePoint(t_ms=t, state=s)
            for t, s in ((0, "closed"), (100, "open"), (140, "closed"), (300, "open"))
        )
    )
    segment = physical_segment(
        {ChannelName.PAN: line, ChannelName.TILT: line, ChannelName.SHUTTER: shutter},
        t0_ms=0,
        t1_ms=400,
    )
    segment.add_metadata("requested_t0_ms", 0)
    segment.add_metadata("requested_t1_ms", 400)

    (kept,), dropped = apply_entry_window([segment], {"MH1": 120}, profiles={"MH1": profile})
    assert dropped == [] and kept.t0_ms == 140

    # Open from 300 ms holds only to the cue's end, 100 ms: nothing left can be held.
    kept_cues, dropped = apply_entry_window([segment], {"MH1": 300}, profiles={"MH1": profile})
    assert kept_cues == [] and [d["entry_window_end_ms"] for d in dropped] == [300]


def test_the_first_cue_after_the_window_also_begins_where_its_shutter_takes_effect() -> None:
    """A cue that starts after the window end is still the first to reveal after the
    transaction's darkness: its 40 ms open state cannot take its 150 ms settle, so it
    begins at its next change instead (the review's seed 50085 failed at render here),
    which it holds until it opens again."""
    profile = _pulse_rig(150).expand_fixtures()[0].config.physical_profile
    assert profile is not None
    line = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=140, value=0.0), PhysicalPoint(t_ms=400, value=0.0)),
        interpolation="linear",
    )
    shutter = DiscreteTrajectory(
        events=tuple(
            DiscretePoint(t_ms=t, state=s)
            for t, s in ((140, "open"), (180, "closed"), (360, "open"))
        )
    )
    segment = physical_segment(
        {ChannelName.PAN: line, ChannelName.TILT: line, ChannelName.SHUTTER: shutter},
        t0_ms=140,
        t1_ms=400,
    )
    segment.add_metadata("requested_t0_ms", 140)
    segment.add_metadata("requested_t1_ms", 400)

    (kept,), dropped = apply_entry_window([segment], {"MH1": 120}, profiles={"MH1": profile})

    assert dropped == [] and kept.t0_ms == 180


def test_a_wheel_state_the_predecessor_already_holds_needs_no_settle() -> None:
    """Blue's settle is unknown, but the heads start on blue and both templates hold it:
    no entry changes it, so the window is sized from the known terms (review M1)."""

    def unknown_blue(profile: dict[str, Any]) -> None:
        profile["discrete"]["color"]["states"]["blue"]["settle_ms"] = None

    state = dict(
        PHYSICAL_INITIAL_STATE,
        discrete_states={"shutter": "closed", "color": "blue", "gobo": "open"},
    )
    job = physical_job(initial_states={"MH1": state, "MH2": state})
    left = physical_template_doc("p24a_left_blue", [hold_step("h", -90.0, physical_color="blue")])
    right = physical_template_doc("p24a_right_blue", [hold_step("h", 90.0, physical_color="blue")])
    pipeline, _ = _render(
        ("p24a_left_blue", 1, 2),
        ("p24a_right_blue", 3, 4),
        grid=_grid(520.0, 520.0, 500.0, 500.0, 500.0, 500.0),
        rig=_rig(unknown_blue),
        job=job,
        docs=(left, right),
    )
    assert {w["action"] for w in _windows(pipeline, "s2").values()} == {"cut"}
    assert all(w["bound_ms"] is not None for w in _windows(pipeline, "s2").values())


def _slow(speed: float = 45.0) -> Callable[[dict[str, Any]], None]:
    def edit(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            profile["axes"][name]["travel_speed_per_s"] = speed

    return edit


def test_the_window_covers_every_cue_of_the_section_not_only_the_first() -> None:
    """The section's first beat holds -60 degrees, 30 from the predecessor; the rest of
    the bar sweeps out to -37.5 and back at 32 degrees/s. The window drops the first beat
    and cuts into the sweep, so it must fit an entry 52.5 degrees away, not 30."""
    near_out_back = physical_template_doc(
        "p24a_near_out_back",
        [
            hold_step("near", -60.0, duration=0.25),
            sweep_step("out", -60.0, 22.5, period_beats=1.4, start=0.25, duration=0.375),
            sweep_step("back", -37.5, -22.5, period_beats=1.4, start=0.625, duration=0.375),
        ],
    )
    pipeline, segments = _render(
        ("p24a_left", 1, 2),
        ("p24a_near_out_back", 3, 4),
        rig=_rig(_slow()),
        docs=(near_out_back,),
    )
    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == "cut" and window["window_end_ms"] - 4020 >= 52.5 / 45 * 1000
        assert _first(segments, "s2", fixture_id).step_id != "near"


def test_the_window_settles_every_wheel_state_the_section_selects() -> None:
    """Blue takes 1.5 s to settle; the window must cover it, not the default white's."""

    def slow_blue(profile: dict[str, Any]) -> None:
        profile["discrete"]["color"]["states"]["blue"]["settle_ms"] = 1500

    blue = physical_template_doc("p24a_right_blue", [hold_step("h", 90.0, physical_color="blue")])
    pipeline, _ = _render(
        ("p24a_left", 1, 2), ("p24a_right_blue", 3, 4), rig=_rig(slow_blue), docs=(blue,)
    )
    for window in _windows(pipeline, "s2").values():
        assert window["action"] == "cut" and window["bound_ms"] >= 1500


def test_after_a_cue_that_may_be_substituted_the_entry_is_sized_from_every_kept_aim() -> None:
    """Under `drop_accent` the jump's +90 cues are dropped, so the head waits at -90 while
    the plan's last kept cue reads +90. The next section at +90 can neither continue
    that cue nor be sized from its aim alone: at 45 degrees/s it needs four seconds."""
    job = physical_job(reposition_fallback="drop_accent")
    pipeline, _ = _render(
        ("p24a_jump", 1, 2),
        ("p24a_right", 3, 8),
        rig=_rig(_slow()),
        job=job,
        grid=_grid(*[500.0] * 8),
    )
    for window in _windows(pipeline, "s2").values():
        assert window["action"] == "cut" and window["window_end_ms"] - 4020 >= 4000


def test_dropped_cues_share_one_record_shape() -> None:
    """A cue inside an entry window and a cue past the covered end are both listed in
    `dropped_cues` with the same keys and a reason."""
    pipeline, _ = _render(("p24a_left", 1, 2), ("p24a_short_hit", 3, 7))
    assert pipeline.render_record is not None
    records = pipeline.render_record["dropped_cues"]
    assert {r["reason"] for r in records} == {"entry_window", "outside_cue_limits"}
    assert len({frozenset(r) for r in records}) == 1
    assert set(records[0]) == {
        "fixture_id",
        "section_id",
        "step_id",
        "requested_start_ms",
        "requested_end_ms",
        "start_ms",
        "end_ms",
        "start_limit_ms",
        "end_limit_ms",
        "entry_window_end_ms",
        "reason",
    }


_DIFFERENTIAL_GRIDS = 60 if os.environ.get("TWINKLR_P24A_FUZZ") == "full" else 6
_DIFFERENTIAL_KNOWN = (34, 148, 187)
"""Grids on which a gate compiling only the first four bars disagrees with the
reference; found by sweeping 400 grids."""


def _random_grid(rng: random.Random) -> BeatGrid:
    """4-12 bars of four beats, 15 ms off the frame grid: mostly 470-700 ms beats with an
    occasional fast one (250-400 ms) anywhere, where rate and pulse checks bite."""
    beats = [15.0]
    for _ in range(4 * rng.randint(4, 12)):
        fast = rng.random() < 0.08
        beats.append(
            beats[-1] + rng.choice([250.0, 320.0, 400.0] if fast else [470.0, 500.0, 610.0, 700.0])
        )
    return BeatGrid(
        bar_boundaries=beats[::4],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=4,
        duration_ms=beats[-1] + 15.0,
    )


def _whole_song_verdict(
    template_id: str, grid: BeatGrid, rig: FixtureGroup, job: JobConfig
) -> bool:
    """The reference gate: every bar of the song from bar 1, every head, no shortcut."""
    from twinklr.core.sequencer.moving_heads.pipeline import _enter_section

    policy = job.moving_heads
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections((template_id, 1, 1)),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
    )
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    profiles = {f.fixture_id: f.config.physical_profile for f in rig.expand_fixtures()}
    document = get_template(template_id)
    bars = sum(1 for bar in grid.bar_boundaries if bar < grid.duration_ms)
    for preset in (None, *document.presets):
        context = TemplateCompileContext(
            section_id="reference",
            template_id=template_id,
            preset_id=None if preset is None else preset.preset_id,
            fixtures=pipeline._build_fixture_contexts(),
            beat_grid=grid,
            start_bar=1,
            duration_bars=bars,
            curve_registry=pipeline.curve_registry,
            geometry_registry=pipeline.geometry_registry,
            movement_registry=pipeline.movement_registry,
            dimmer_registry=pipeline.dimmer_registry,
        )
        try:
            compiled = compile_physical_template(
                document.template,
                context,
                preset,
                phase_map=phase_map,
                start_limit_ms=start,
                end_limit_ms=end,
            )
        except (PhysicalChannelError, ValueError):
            return False
        cues, _, _ = _enter_section(
            compiled.segments,
            {},
            profiles,  # type: ignore[arg-type]
            policy.initial_states,
            section_start_ms=context.start_ms,
            phase_map=phase_map,
            failure_mode=policy.reposition_fallback,
        )
        result = plan_prepositions(
            cues,
            profiles,  # type: ignore[arg-type]
            initial_states=policy.initial_states,
            locks=(),
            frame_ms=EFFECT_GRID_MS,
            sequence_end_ms=len(frame_times(int(grid.duration_ms))) * EFFECT_GRID_MS,
            failure_mode=policy.reposition_fallback,
        )
        if result.has_errors:
            return False
    return True


_DIFFERENTIAL_TEMPLATES = (
    "p1_linear_reveal",
    "p24a_sweep",
    "p24a_jump",
    "p24a_osc",
    "p24a_sine",
    "p24a_pulse",
    "p24a_short_hit",
    "p24a_center",
)


def _differential_docs() -> tuple[TemplateDoc, ...]:
    osc = physical_template_doc(
        "p24a_osc",
        [
            sweep_step("o", 0.0, 40.0, period_beats=2.0, duration=0.5),
            sweep_step("b", 40.0, -40.0, period_beats=2.0, start=0.5, duration=0.5),
        ],
    )
    sine = physical_template_doc("p24a_sine", [_sine_step("s", 0.0, 30.0, 2.0)])
    return (*_DOCS, osc, sine, _pulse_doc())


def _check_gate_agrees(seed: int) -> set[bool]:
    """Gate three templates on one random grid, rig and policy against the reference;
    return the verdicts seen. Templates must be registered."""
    rigs = {
        "base": physical_rig,
        "slow": lambda: _rig(_slow()),
        "coarse": lambda: _rig(_coarse(90.0)),
    }
    rng = random.Random(seed)
    grid = _random_grid(rng)
    rig = rigs[rng.choice(sorted(rigs))]()
    policy = rng.choice(["error", "drop_accent"])
    job = physical_job() if policy == "error" else physical_job(reposition_fallback=policy)
    verdicts: set[bool] = set()
    for template_id in rng.sample(_DIFFERENTIAL_TEMPLATES, 3):
        try:
            check_physical_templates(
                [template_id],
                beat_grid=grid,
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode=job.moving_heads.reposition_fallback,
            )
            admitted = True
        except UnsupportedRenderModeError:
            admitted = False
        expected = _whole_song_verdict(template_id, grid, rig, job)
        assert admitted == expected, (seed, template_id, policy)
        verdicts.add(admitted)
    return verdicts


def test_the_gate_agrees_with_a_whole_song_reference_on_variable_tempo() -> None:
    """Differential fuzz (review H2): on random variable-tempo grids, rigs and fallback
    policies, the gate admits a template exactly when the whole-song reference does.
    A gate that checks less of the song than the render can reach fails here: the known
    grids catch one compiling only the first four bars; then a random sweep."""
    verdicts: set[bool] = set()
    with physical_test_templates(), registered_templates(*_differential_docs()):
        for seed in (*_DIFFERENTIAL_KNOWN, *range(_DIFFERENTIAL_GRIDS)):
            verdicts |= _check_gate_agrees(seed)
    assert verdicts == {True, False}


def test_an_uncut_entry_carries_motion_into_the_sections_first_gap() -> None:
    """Review question: a sine moving at 500 degrees/s ends where the next section's
    first, one-frame cue begins, so that entry plays as authored; the head is still
    settling (80 ms) when the section's first one-frame gap needs it still. From rest,
    as the gate places the section, that gap needs nothing; carried, it needs 80 ms. The
    uncut entry is therefore probed through to the section's first gap, and here it
    gets the window instead of failing at render."""

    def settle_80(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            profile["axes"][name]["settle_ms"] = 80

    sine = physical_template_doc("p24a_sine_fast", [_sine_step("s", 0.0, 40.0, 1.0)])
    gap = physical_template_doc(
        "p24a_gap",
        [
            hold_step("first", 0.0, duration=0.01, target="LEFT"),
            hold_step("other", 0.0, start=0.01, duration=0.01, target="RIGHT"),
            hold_step("rest", 0.0, start=0.02, duration=0.98, target="LEFT"),
        ],
    )
    pipeline, segments = _render(
        ("p24a_sine_fast", 1, 2), ("p24a_gap", 3, 4), rig=_rig(settle_80), docs=(sine, gap)
    )
    window = _windows(pipeline, "s2")["MH1"]
    assert window["action"] == "cut"
    assert _first(segments, "s2", "MH1").t0_ms == window["first_cue_ms"] > 4060


def test_a_cut_waits_for_the_open_latency_too() -> None:
    """Open latency, not only settle, must fit inside the first state after a cut: with
    a 150 ms open latency the 40 ms open state is skipped as with a 150 ms settle."""

    def slow_open(profile: dict[str, Any]) -> None:
        profile["visibility"]["open_latency_ms"] = 150

    profile = _rig(slow_open).expand_fixtures()[0].config.physical_profile
    assert profile is not None
    line = ContinuousTrajectory(
        unit="degree",
        points=(PhysicalPoint(t_ms=0, value=0.0), PhysicalPoint(t_ms=400, value=0.0)),
        interpolation="linear",
    )
    shutter = DiscreteTrajectory(
        events=tuple(
            DiscretePoint(t_ms=t, state=s)
            for t, s in ((0, "closed"), (100, "open"), (140, "closed"), (360, "open"))
        )
    )
    segment = physical_segment(
        {ChannelName.PAN: line, ChannelName.TILT: line, ChannelName.SHUTTER: shutter},
        t0_ms=0,
        t1_ms=400,
    )
    segment.add_metadata("requested_t0_ms", 0)
    segment.add_metadata("requested_t1_ms", 400)

    (kept,), _ = apply_entry_window([segment], {"MH1": 120}, profiles={"MH1": profile})
    assert kept.t0_ms == 140


def _same_heads(edit: Callable[[dict[str, Any]], None] | None = None) -> FixtureGroup:
    """`physical_rig` with both heads on one, uninverted profile."""

    def same(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            profile["axes"][name]["inverted"] = False
        if edit is not None:
            edit(profile)

    return _rig(same)


def _gate(template_id: str, rig: FixtureGroup, job: JobConfig, *docs: TemplateDoc) -> str:
    """The gate's refusal message, or "" when it admits the template."""
    with registered_templates(*_DOCS, *docs):
        try:
            check_physical_templates(
                [template_id],
                beat_grid=_grid(),
                fixture_group=rig,
                initial_states=job.moving_heads.initial_states,
                failure_mode=job.moving_heads.reposition_fallback,
            )
        except UnsupportedRenderModeError as error:
            return str(error)
    return ""


def test_the_gate_names_every_head_that_shares_a_refused_plan() -> None:
    """Identical heads are planned once; a refusal names all of them."""
    message = _gate("p24a_jump_plain", _same_heads(), physical_job())
    assert "MH1/MH2 cue at" in message


def test_the_gate_plans_heads_with_different_initial_states_apart() -> None:
    """Only the centre head has cues; MH1 and MH3 only park, from their initial states.
    MH3 starts unsettled, so its park fails while MH1's passes: they are not one."""
    centre = physical_template_doc("p24a_centre", [hold_step("h", 0.0, target="INNER")])
    unsettled = dict(PHYSICAL_INITIAL_STATE, settled=False)
    states = {"MH1": PHYSICAL_INITIAL_STATE, "MH2": PHYSICAL_INITIAL_STATE, "MH3": unsettled}
    message = _gate(
        "p24a_centre",
        topology_rig(("MH1", "MH2", "MH3")),
        physical_job(initial_states=states),
        centre,
    )
    assert "MH3 cue at" in message
    assert "MH1" not in message


def test_the_gate_plans_heads_with_different_cue_metadata_apart() -> None:
    """The left head's steps declare `drop_accent` and the right head's do not: under
    that policy only the right head's jump is refused, though both heads' cues hold the
    same values at the same times."""
    split = physical_template_doc(
        "p24a_jump_split",
        [
            hold_step(
                "l1", -90.0, duration=0.5, target="LEFT", physical_reposition_fallback="drop_accent"
            ),
            hold_step(
                "l2",
                90.0,
                start=0.5,
                duration=0.5,
                target="LEFT",
                physical_reposition_fallback="drop_accent",
            ),
            hold_step("r1", -90.0, duration=0.5, target="RIGHT"),
            hold_step("r2", 90.0, start=0.5, duration=0.5, target="RIGHT"),
        ],
    )
    message = _gate(
        "p24a_jump_split", _same_heads(), physical_job(reposition_fallback="drop_accent"), split
    )
    assert "MH2 cue at" in message and "MH1 cue at" not in message and "MH1/" not in message


# --- A missing head leaves the other heads' output alone (P2.2 review M1) ----------------


def _subset_docs() -> tuple[TemplateDoc, ...]:
    """Distributed and mirrored families that leave each head at its own aim, so the heads'
    entry windows differ."""
    pulse = {"physical": {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}}
    return (
        physical_template_doc(
            "ss_wings",
            [
                sine_step(
                    "w",
                    0.0,
                    20.0,
                    period_beats=2.0,
                    distribution=[{"domains": ["pan", "dimmer"], "wings": 2, "spread_cycles": 0.5}],
                    dimmer=pulse,
                )
            ],
        ),
        physical_template_doc(
            "ss_reverse",
            [
                sine_step(
                    "s",
                    60.0,
                    30.0,
                    distribution=[
                        {"domains": ["pan"], "spread_cycles": 0.75, "direction": "reverse"}
                    ],
                )
            ],
        ),
        physical_template_doc(
            "ss_fan",
            [
                sweep_step(
                    "c",
                    0.0,
                    120.0,
                    period_beats=8.0,
                    duration=4.0,
                    physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.4, "wings": 2}],
                )
            ],
            cycle_bars=4.0,
        ),
        physical_template_doc(
            "ss_fan_line",
            [
                sweep_step(
                    "c",
                    0.0,
                    120.0,
                    period_beats=16.0,
                    duration=4.0,
                    physical_distribution=[{"domains": ["pan"], "spread_cycles": 0.4}],
                )
            ],
            cycle_bars=4.0,
        ),
        physical_template_doc("ss_hold", [hold_step("d", 120.0)]),
        physical_template_doc("ss_left", [hold_step("d", -90.0)]),
    )


def _head_frames(
    fixture_ids: tuple[str, ...],
    sections: tuple[tuple[str, int, int], ...],
    grid: BeatGrid,
    speed: float,
    full_ids: tuple[str, ...],
) -> dict[str, list[tuple[int, tuple[tuple[int, int], ...]]]]:
    """Render `sections` on the heads present, with the full rig's declared topology."""

    def at_speed(profile: dict[str, Any]) -> None:
        for name in ("pan", "tilt"):
            profile["axes"][name]["travel_speed_per_s"] = speed

    payload = topology_rig(fixture_ids, topology=topology_payload(full_ids)).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        at_speed(fixture["config"]["physical_profile"])
    rig = FixtureGroup.model_validate(payload)
    job = physical_job(initial_states=dict.fromkeys(fixture_ids, PHYSICAL_INITIAL_STATE))
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
        output_path=None,
    )
    pipeline.render()
    frames: dict[str, list[tuple[int, tuple[tuple[int, int], ...]]]] = {}
    for frame in pipeline.frames:
        channels = tuple(sorted(dict(frame.channels).items()))
        frames.setdefault(frame.fixture_id, []).append((frame.time_ms, channels))
    return frames


def _assert_subset_stable(
    sections: tuple[tuple[str, int, int], ...],
    grid: BeatGrid,
    *,
    heads: int,
    missing: tuple[str, ...],
    speed: float,
) -> None:
    full_ids = tuple(f"MH{index}" for index in range(1, heads + 1))
    full = _head_frames(full_ids, sections, grid, speed, full_ids)
    for gone in missing:
        present = tuple(fixture_id for fixture_id in full_ids if fixture_id != gone)
        subset = _head_frames(present, sections, grid, speed, full_ids)
        for fixture_id in present:
            assert subset[fixture_id] == full[fixture_id], (gone, fixture_id)


@pytest.mark.parametrize(
    ("sections", "heads", "missing", "speed"),
    [
        pytest.param(
            (("ss_wings", 1, 2), ("ss_reverse", 3, 3), ("ss_fan", 4, 7), ("ss_hold", 8, 9)),
            5,
            ("MH1", "MH3"),
            150.0,
            id="review-repro-wings-reverse-fan-hold",
        ),
        pytest.param(
            (("ss_left", 1, 2), ("ss_fan_line", 3, 6), ("ss_left", 7, 8)),
            4,
            ("MH1", "MH3"),
            45.0,
            id="lagging-fan-out-and-back-slow",
        ),
    ],
)
def test_a_missing_head_leaves_every_other_heads_frames_unchanged(
    sections: tuple[tuple[str, int, int], ...], heads: int, missing: tuple[str, ...], speed: float
) -> None:
    """Each head's entry window is its own: removing a head (its topology slot kept) never
    lengthens or shortens another head's window, so every remaining head's encoded frames
    equal the full rig's byte for byte. A section-wide window failed the first case: without
    MH1, the fan's window ended 500 ms earlier for MH2-MH5."""
    with registered_templates(*_subset_docs()):
        _assert_subset_stable(
            sections, _grid(*[500.0] * 10), heads=heads, missing=missing, speed=speed
        )


_SUBSET_SEEDS = 4
_SUBSET_KNOWN = (20, 30)
"""Seeds on which a section-wide window changes a remaining head (found in 60)."""


def _subset_case(seed: int) -> bool:
    """One random subset case; return whether the full rig rendered it to compare. The
    subset families must be registered."""
    rng = random.Random(seed)
    ids = [doc.template.template_id for doc in _subset_docs()]
    sections: list[tuple[str, int, int]] = [("ss_left", 1, 1)]
    bar = 2
    for _ in range(rng.randint(1, 3)):
        template_id = rng.choice(ids)
        length = 4 if template_id.startswith("ss_fan") else rng.randint(1, 2)
        sections.append((template_id, bar, bar + length - 1))
        bar += length
    grid = _grid(*[rng.choice([400.0, 500.0, 600.0]) for _ in range(bar)])
    heads = rng.randint(3, 5)
    # The first head leads every distribution, so its window is often the widest.
    missing = (rng.choice(["MH1", f"MH{rng.randint(2, heads)}"]),)
    speed = rng.choice([45.0, 150.0, 360.0])
    try:
        _assert_subset_stable(tuple(sections), grid, heads=heads, missing=missing, speed=speed)
    except AssertionError as error:
        raise AssertionError(f"seed {seed}: {error}") from error
    except (PhysicalChannelError, PhysicalRenderError):
        return False  # the full rig cannot render it either: nothing to compare
    return True


def test_subset_stability_fuzz() -> None:
    """Random sections of the distributed families after an opening hold on 3-5 heads,
    random tempo and speed; one head removed, the leading one half the time. The known
    seeds catch a section-wide window; then a random sweep."""
    with registered_templates(*_subset_docs()):
        for seed in _SUBSET_KNOWN:
            assert _subset_case(seed), seed
        compared = sum(_subset_case(seed) for seed in range(_SUBSET_SEEDS))
    assert compared >= _SUBSET_SEEDS // 2, compared


def test_an_uncut_entry_must_also_give_its_first_shutter_state_time() -> None:
    """The closed-shutter hold continues straight into a pulse that opens for only 40 ms;
    the pose and wheels allow the continuation, but the open state needs 60 ms latency
    and 60 ms settle (later in each bar it opens for 460 ms, which is enough). The uncut entry is therefore not played as authored: it gets a
    window whose cut begins where the shutter can take effect."""

    def slow_open(profile: dict[str, Any]) -> None:
        profile["visibility"]["open_latency_ms"] = 60
        profile["discrete"]["shutter"]["states"]["open"]["settle_ms"] = 60

    closed = physical_template_doc(
        "p24a_closed", [hold_step("h", -90.0, physical_shutter_state="closed")]
    )
    step = hold_step("p", -90.0)
    step.pop("physical_shutter_state")
    step["physical_shutter"] = {
        "period_beats": 4.0,
        "duty_cycle": 0.25,
        "phase_cycles": 0.23,
        "low_state": "closed",
        "high_state": "open",
    }
    pulse = physical_template_doc("p24a_short_open", [step])
    pipeline, segments = _render(
        ("p24a_closed", 1, 2), ("p24a_short_open", 3, 4), rig=_rig(slow_open), docs=(closed, pulse)
    )
    for fixture_id, window in _windows(pipeline, "s2").items():
        assert window["action"] == "cut"
        assert _first(segments, "s2", fixture_id).t0_ms > 4020


# --- Every entry that is not played as authored gets the holdable cut (review H-A) -------


def _straddling_pulse(pan: float) -> TemplateDoc:
    """A pulse open for the first 0.05 beat of each cue (then every other half beat)."""
    step = hold_step("p", pan)
    step.pop("physical_shutter_state")
    step["physical_shutter"] = {
        "period_beats": 1.0,
        "duty_cycle": 0.5,
        "phase_cycles": 0.45,
        "low_state": "closed",
        "high_state": "open",
    }
    return physical_template_doc(f"ha_pulse_{pan:g}", [step])


@pytest.mark.parametrize("open_settle", [60, 100, 150])
def test_an_entry_without_a_window_still_begins_where_its_shutter_takes_effect(
    open_settle: int,
) -> None:
    """MH1 has no cue in the first section, so its bound fits long before the pulse
    section starts and it needs no dark window; but its first, 40 ms open state cannot
    take its settle, so its entry is not played as authored. It still begins where the
    shutter takes effect: the gate admitted this and the render then failed."""
    right_only = physical_template_doc("ha_right_only", [hold_step("h", 90.0, target="RIGHT")])
    pipeline, segments = _render(
        ("ha_right_only", 1, 2),
        ("ha_pulse_0", 3, 6),
        rig=_pulse_rig(open_settle),
        docs=(right_only, _straddling_pulse(0.0)),
    )
    window = _windows(pipeline, "s2")["MH1"]
    assert window["window_end_ms"] is None and window["action"] != "skipped"
    assert _first(segments, "s2", "MH1").t0_ms > 4020


def _unknown_tilt_latency(profile: dict[str, Any]) -> None:
    """A 100 ms open settle, and tilt latency unknown: no entry bound can be computed."""
    profile["discrete"]["shutter"]["states"]["open"]["settle_ms"] = 100
    profile["axes"]["tilt"]["latency_ms"] = None


def _slow_settling(profile: dict[str, Any]) -> None:
    """45 degrees/s and a 100 ms open settle."""
    _slow()(profile)
    profile["discrete"]["shutter"]["states"]["open"]["settle_ms"] = 100


@pytest.mark.parametrize(
    ("sections", "edit", "docs"),
    [
        pytest.param(
            (("p24a_left", 1, 2), ("p24a_right", 3, 3), ("ha_pulse_-90", 4, 7)),
            _slow_settling,
            (),
            id="earlier-cues-all-dropped",
        ),
        pytest.param(
            (("ha_closed_0", 1, 2), ("ha_pulse_0", 3, 6)),
            _unknown_tilt_latency,
            (
                physical_template_doc(
                    "ha_closed_0", [hold_step("h", 0.0, physical_shutter_state="closed")]
                ),
            ),
            id="unknown-bound",
        ),
    ],
)
def test_the_gate_admits_only_what_renders_on_every_entry_path(
    sections: tuple[tuple[str, int, int], ...],
    edit: Callable[[dict[str, Any]], None],
    docs: tuple[TemplateDoc, ...],
) -> None:
    """Entries that need no dark window for other reasons than a fitting bound: a
    predecessor sections back (the section between had every cue dropped), and an
    unknown bound. `_render` gates first; each renders honestly."""
    _render(
        *sections,
        grid=_grid(*[500.0] * 8),
        rig=_rig(edit),
        docs=(*docs, _straddling_pulse(0.0), _straddling_pulse(-90.0)),
    )
