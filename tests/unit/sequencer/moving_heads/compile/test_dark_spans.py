"""Render-wide dark spans (C1.1a): spans in which every head of a physical render is held
dark, as the combined show's coordination windows rest the moving heads.

A span darkens the cues it covers before section entry and repositioning are planned:
a cue running through a span keeps playing its own authored trajectory there, commanded
dark through the profile's own darkness, so the head never leaves the authored path and
needs no re-entry; a different cue after a span is reached by the ordinary transaction
pass, which sees the final visibility. Every render below is replanned from its cues and
checked from its bytes (`assert_honest_transactions`) on every fixture.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from tests.support.mh_physical import (
    assert_honest_transactions,
    hold_step,
    physical_bars_grid,
    physical_job,
    physical_rig,
    physical_sections,
    physical_template_doc,
    registered_templates,
    sine_step,
)
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    TRANSACTION_METADATA_KEY,
    plan_prepositions,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import frame_times
from twinklr.core.sequencer.moving_heads.pipeline import RenderingPipeline

_SWING = physical_template_doc("dark_span_swing", [sine_step("swing", 0.0, 30.0)])
"""Pan swings 30 degrees either side of centre once a bar, lit throughout: every head is
always moving, so any span lands mid-move."""
_LEFT = physical_template_doc("dark_span_left", [hold_step("hold", -60.0)])
_RIGHT = physical_template_doc("dark_span_right", [hold_step("hold", 60.0)])
"""Holds at -60 and +60 degrees: a section of the one after a section of the other
must be reached by a transaction."""
_FALLBACKS = {
    mode: physical_template_doc(
        f"dark_span_swing_{mode}",
        [sine_step("swing", 0.0, 30.0, physical_reposition_fallback=mode)],
    )
    for mode in ("drop_accent", "preserve_aim")
}
_GRID = physical_bars_grid(500.0, 500.0, 500.0, 500.0)
"""Four bars of 500 ms beats, starting 15 ms off the frame grid."""
_CALLS = [(15 + 1_000 * beat, 515 + 1_000 * beat) for beat in range(8)]
"""Every other beat, as a one-beat call/response rests the heads on each call."""

type Frames = dict[tuple[str, int], dict[int, int]]


@pytest.fixture(autouse=True)
def _templates() -> Iterator[None]:
    with registered_templates(_SWING, _LEFT, _RIGHT, *_FALLBACKS.values()):
        yield


def _rig(**visibility: Any) -> FixtureGroup:
    """`physical_rig`, with its profiles' visibility declaration changed by `visibility`."""
    payload = physical_rig().model_dump(mode="python")
    for fixture in payload["fixtures"]:
        fixture["config"]["physical_profile"]["visibility"].update(visibility)
    return FixtureGroup.model_validate(payload)


def _render(
    dark_spans: Sequence[tuple[int, int]] = (),
    *,
    template: str = "dark_span_swing",
    sections: Sequence[tuple[str, int, int]] = (),
    job: JobConfig | None = None,
    rig: FixtureGroup | None = None,
) -> tuple[RenderingPipeline, Frames]:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*(sections or [(template, 1, 4)])),
        beat_grid=_GRID,
        fixture_group=rig or physical_rig(),
        job_config=job or physical_job(),
        dark_spans=dark_spans,
    )
    segments = pipeline.render()
    _assert_honest(pipeline, segments)
    return pipeline, {(f.fixture_id, f.time_ms): dict(f.channels) for f in pipeline.frames}


def _profiles(pipeline: RenderingPipeline) -> dict[str, FixtureCapabilities]:
    profiles = {}
    for fixture in pipeline.fixture_group.expand_fixtures():
        assert fixture.config.physical_profile is not None
        profiles[fixture.fixture_id] = fixture.config.physical_profile
    return profiles


def _assert_honest(pipeline: RenderingPipeline, segments: list[FixtureSegment]) -> None:
    """Replanning the render's own cues gives its segments, and no head is lit while it
    moves or turns a wheel, nor revealed before it has settled."""
    job = pipeline.job_config
    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    profiles = _profiles(pipeline)
    replanned = plan_prepositions(
        cues,
        profiles,
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(_GRID.duration_ms))) * EFFECT_GRID_MS,
        failure_mode=job.moving_heads.reposition_fallback,
    )
    assert list(replanned.segments) == segments
    for fixture_id, profile in profiles.items():
        initial = job.moving_heads.initial_states[fixture_id]
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)


def _dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    """Whether a frame commands darkness: dimmer at zero or an extinguishing shutter."""
    dimmer = profile.axes["dimmer"]
    word = frame[dimmer.coarse_offset]
    if dimmer.fine_offset is not None:
        word = word << 8 | frame[dimmer.fine_offset]
    if profile.visibility.dimmer_zero_extinguishes and word == dimmer.dmx_word(0):
        return True
    shutter = profile.discrete["shutter"]
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


def _darkening(profile: FixtureCapabilities) -> set[int]:
    """The offsets the profile is darkened through: its dimmer when zero extinguishes,
    else its shutter."""
    if profile.visibility.dimmer_zero_extinguishes:
        dimmer = profile.axes["dimmer"]
        return {dimmer.coarse_offset} | ({dimmer.fine_offset} - {None})  # type: ignore[operator]
    return {profile.discrete["shutter"].offset}


def _in(spans: Sequence[tuple[int, int]], time_ms: int) -> bool:
    return any(start <= time_ms < end for start, end in spans)


def _assert_rests(
    pipeline: RenderingPipeline, frames: Frames, plain: Frames, spans: Sequence[tuple[int, int]]
) -> None:
    """In every span each head is commanded dark on its authored path: only the bytes the
    profile darkens through differ from the plain render, so pose, zoom and wheels
    follow the cues as authored. Outside the spans every lit frame is the plain render's
    and no lit frame of the plain render is lost."""
    profiles = _profiles(pipeline)
    assert frames.keys() == plain.keys()
    for (fixture_id, time_ms), frame in frames.items():
        profile = profiles[fixture_id]
        before = plain[(fixture_id, time_ms)]
        if _in(spans, time_ms):
            assert _dark(frame, profile), f"{fixture_id} is lit at {time_ms} ms in a span"
            changed = {offset for offset in frame if frame[offset] != before[offset]}
            assert changed <= _darkening(profile), f"{fixture_id} left its path at {time_ms}"
        elif not _dark(frame, profile):
            assert frame == before, f"{fixture_id} differs at {time_ms} ms"
        else:
            assert _dark(before, profile), f"{fixture_id} lost a lit frame at {time_ms} ms"


def test_a_cue_crossing_a_span_plays_on_dark_along_its_authored_path() -> None:
    plain_pipeline, plain = _render()
    pipeline, frames = _render([(1_015, 1_515)])

    assert pipeline.render_record is not None
    assert pipeline.render_record["dark_spans"] == [[1_000, 1_520]]  # snapped outward
    assert plain_pipeline.render_record is not None
    assert "dark_spans" not in plain_pipeline.render_record
    _assert_rests(pipeline, frames, plain, [(1_000, 1_520)])
    # Nothing re-enters after the span: the entry records are the plain render's, and
    # outside the span not a byte changes.
    assert pipeline.render_record["entry_windows"] == plain_pipeline.render_record["entry_windows"]
    assert all(frame == plain[key] for key, frame in frames.items() if not 1_000 <= key[1] < 1_520)


def test_a_short_span_darkens_its_own_frames_and_no_more() -> None:
    _, plain = _render()
    pipeline, frames = _render([(1_000, 1_040)])

    _assert_rests(pipeline, frames, plain, [(1_000, 1_040)])
    assert all(frame == plain[key] for key, frame in frames.items() if not 1_000 <= key[1] < 1_040)


def test_a_cue_wholly_inside_a_span_is_kept_dark_on_its_path() -> None:
    _, plain = _render()
    pipeline, frames = _render([(2_015, 4_015)])

    assert pipeline.render_record is not None
    assert pipeline.render_record["dropped_cues"] == []
    _assert_rests(pipeline, frames, plain, [(2_000, 4_020)])


def test_a_different_cue_after_a_span_is_reached_in_the_dark() -> None:
    """Two sections, a hold at -60 then a hold at +60; a span from the last beat of the
    first to the first beat of the second. The second section is entered as it would be
    without the span (its entry window is the plain render's), the head crosses to +60
    in the dark, and it is revealed on the second hold's own aim, settled."""
    sections = [("dark_span_left", 1, 2), ("dark_span_right", 3, 4)]
    plain_pipeline, plain = _render(sections=sections)
    pipeline, frames = _render([(3_515, 4_515)], sections=sections)

    assert pipeline.render_record is not None and plain_pipeline.render_record is not None
    assert pipeline.render_record["entry_windows"] == plain_pipeline.render_record["entry_windows"]
    _assert_rests(pipeline, frames, plain, [(3_500, 4_520)])
    for fixture_id, profile in _profiles(pipeline).items():
        assert not _dark(frames[(fixture_id, 4_520)], profile)


@pytest.mark.parametrize("mode", ["drop_accent", "preserve_aim"])
def test_spans_under_a_reposition_fallback_lose_no_lit_frame(mode: str) -> None:
    """A fallback the cues and the job both declare changes nothing about a span: the
    cues around it are the same cues, played on through it dark."""
    job = physical_job(reposition_fallback=mode)
    plain_pipeline, plain = _render(template=f"dark_span_swing_{mode}", job=job)
    pipeline, frames = _render(_CALLS, template=f"dark_span_swing_{mode}", job=job)

    spans = [(start // 20 * 20, -(-end // 20) * 20) for start, end in _CALLS]
    assert pipeline.render_record is not None and plain_pipeline.render_record is not None
    assert pipeline.render_record["dark_spans"] == [list(span) for span in spans]
    _assert_rests(pipeline, frames, plain, spans)
    assert pipeline.render_record["entry_windows"] == plain_pipeline.render_record["entry_windows"]


def test_a_rig_dark_only_through_its_shutter_closes_it_over_a_span() -> None:
    rig = _rig(dimmer_zero_extinguishes=False)
    _, plain = _render(rig=rig)
    pipeline, frames = _render(_CALLS, rig=rig)

    spans = [(start // 20 * 20, -(-end // 20) * 20) for start, end in _CALLS]
    _assert_rests(pipeline, frames, plain, spans)


def _shutter_rig(
    *, close: int = 0, closed_settle: int = 0, open_: int = 0, open_settle: int = 0
) -> FixtureGroup:
    """`physical_rig` dark only through its shutter, with the given latencies and the
    closed and open states' settle times."""
    payload = _rig(
        dimmer_zero_extinguishes=False, close_latency_ms=close, open_latency_ms=open_
    ).model_dump(mode="python")
    for fixture in payload["fixtures"]:
        states = fixture["config"]["physical_profile"]["discrete"]["shutter"]["states"]
        states["closed"]["settle_ms"] = closed_settle
        states["open"]["settle_ms"] = open_settle
    return FixtureGroup.model_validate(payload)


@pytest.mark.parametrize("on_unplayable", ["dark", "error"])
def test_a_span_shorter_than_the_shutter_takes_to_close_is_widened(on_unplayable: str) -> None:
    """Closing takes 60 ms of latency and 30 ms of settle: a 15 ms rest, one frame once
    snapped, is widened to the 100 ms the closed shutter needs to take effect, so the
    cue through it plays lit on either side under either setting, rather than being
    kept dark whole or refusing the render after planning."""
    rig = _shutter_rig(close=60, closed_settle=30, open_=40)
    job = physical_job(on_unplayable=on_unplayable)
    _, plain = _render(rig=rig, job=job)
    pipeline, frames = _render([(1_000, 1_015)], rig=rig, job=job)

    assert pipeline.render_record is not None
    assert pipeline.render_record["dark_spans"] == [[1_000, 1_100]]
    assert pipeline.render_record["dropped_cues"] == []
    _assert_rests(pipeline, frames, plain, [(1_000, 1_100)])


@pytest.mark.parametrize(
    ("gap_ms", "merged"),
    [(20, True), (40, False)],
    ids=["one-frame-gap-merged", "two-frame-gap-kept"],
)
def test_a_lit_gap_too_short_to_show_between_spans_is_merged(gap_ms: int, merged: bool) -> None:
    """Between two spans a head is relit only for at least two frames; a shorter gap
    stays dark."""
    _, plain = _render()
    spans = [(1_000, 1_520), (1_520 + gap_ms, 2_000)]
    pipeline, frames = _render(spans)

    assert pipeline.render_record is not None
    expected = [(1_000, 2_000)] if merged else spans
    assert pipeline.render_record["dark_spans"] == [list(span) for span in expected]
    _assert_rests(pipeline, frames, plain, expected)


def test_a_dimmer_rig_relights_between_spans_whatever_its_latencies() -> None:
    """Darkening and relighting through the dimmer have no timing to wait for: with
    200 ms latencies either way, the 380 ms answers of a 150 BPM call/response stay lit,
    and a 40 ms rest is not widened."""
    rig = _rig(close_latency_ms=200, open_latency_ms=200)
    spans = [(1_000, 1_400), (1_780, 2_180), (2_560, 2_960), (4_000, 4_040)]
    _, plain = _render(rig=rig)
    pipeline, frames = _render(spans, rig=rig)

    assert pipeline.render_record is not None
    assert pipeline.render_record["dark_spans"] == [list(span) for span in spans]
    _assert_rests(pipeline, frames, plain, spans)


def test_a_shutter_rig_relights_only_for_as_long_as_its_shutter_needs_to_open() -> None:
    """Opening takes 40 ms of latency and 20 ms of settle: a 40 ms gap between spans is
    merged, a 60 ms one kept lit."""
    rig = _shutter_rig(open_=40, open_settle=20)
    _, plain = _render(rig=rig)
    for gap_ms, merged in ((40, True), (60, False)):
        spans = [(1_000, 1_520), (1_520 + gap_ms, 1_900)]
        pipeline, frames = _render(spans, rig=rig)
        assert pipeline.render_record is not None
        expected = [(1_000, 1_900)] if merged else spans
        assert pipeline.render_record["dark_spans"] == [list(span) for span in expected]
        _assert_rests(pipeline, frames, plain, expected)


def test_a_shutter_rig_keeps_a_cue_dark_to_its_end_after_a_span_ending_just_before() -> None:
    """A span ending 20 ms before the bar's cue ends would relight the shutter for one
    frame, less than the 60 ms it needs to open: that remainder stays dark too. The
    section still enters as without the span, and no cue is lost or refused."""
    rig = _shutter_rig(open_=40, open_settle=20)
    plain_pipeline, plain = _render(rig=rig)
    for job in (physical_job(), physical_job(on_unplayable="error")):
        pipeline, frames = _render([(1_000, 2_000)], rig=rig, job=job)
        assert pipeline.render_record is not None and plain_pipeline.render_record is not None
        assert pipeline.render_record["dropped_cues"] == []
        assert (
            pipeline.render_record["entry_windows"] == plain_pipeline.render_record["entry_windows"]
        )
        _assert_rests(pipeline, frames, plain, [(1_000, 2_020)])


def test_dark_spans_are_render_identity_only_when_given() -> None:
    plain, _ = _render()
    empty, _ = _render([])
    dark, _ = _render([(1_015, 1_515)])
    same_frames, _ = _render([(1_000, 1_520)])

    assert empty.fingerprint() == plain.fingerprint()
    assert dark.fingerprint() != plain.fingerprint()
    # Identity is what renders: spans that snap to the same frames render alike.
    assert same_frames.fingerprint() == dark.fingerprint()
