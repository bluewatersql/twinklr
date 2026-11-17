"""The bounded optical pilot (P2.5): one zoom axis.

A profile may declare a `zoom` axis, a beam angle in degrees, mapped over a DMX subrange
(`dmx_min`/`dmx_max`): `dmx_min + round-half-up(normalized * (dmx_max - dmx_min))`, with
inversion reflecting the word about `dmx_min + dmx_max`. At the default subrange every
existing word and profile dump is unchanged. A step's `physical_zoom` holds or waves the
beam angle on the step's movement phase; between cues the transaction pass holds the zoom,
moves it only in the dark and lets it settle before a reveal. A rig without a zoom axis
refuses a zoom step unless the step declares `omit_optional_zoom`, which the trace
records, and the `zoom_wave` family is left out of its offer.

Synthetic data only: the 10°-40° profile over bytes 20-220 is no real fixture, and
accepting a real profile is `PENDING-OWNER`.
"""

from __future__ import annotations

from collections.abc import Callable
import copy
from fractions import Fraction
import hashlib
import math
from typing import Any

from pydantic import ValidationError
import pytest

from tests.config_effects_registry import CONFIG_EFFECTS, ConfigDispositionKind
from tests.support.mh_physical import (
    PHYSICAL_INITIAL_STATE,
    ZOOM_FAMILY_ID,
    ZOOM_INITIAL_STATE,
    assert_honest_transactions,
    family_job,
    family_rig,
    hold_step,
    physical_bars_grid,
    physical_catalog,
    physical_head_profile,
    physical_job,
    physical_rig,
    physical_sections,
    physical_segment,
    physical_template_doc,
    profile_payload,
    registered_templates,
    sine_step,
    zoom_job,
    zoom_pilot_profile_payload,
    zoom_rig,
)
from twinklr.core.config.fixtures import FixtureCapabilities, FixtureGroup, InitialFixtureState
from twinklr.core.config.models import JobConfig
from twinklr.core.config.render_policy import UnsupportedRenderModeError
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.context import TemplateCompileContext
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.moving_heads.physical import (
    ContinuousTrajectory,
    DiscreteTrajectory,
    PhysicalChannelError,
    check_physical_value,
)
from twinklr.core.sequencer.models.moving_heads.rig import rig_profile_from_fixture_group
from twinklr.core.sequencer.models.moving_heads.topology import rig_topology
from twinklr.core.sequencer.models.template import Template, TemplateDoc, TemplateStep
from twinklr.core.sequencer.moving_heads.channels.state import FixtureSegment
from twinklr.core.sequencer.moving_heads.compile.physical import PhysicalCompileError
from twinklr.core.sequencer.moving_heads.compile.preposition import (
    FALLBACK_METADATA_KEY,
    TRANSACTION_METADATA_KEY,
    PrepositionResult,
    plan_prepositions,
    worst_case_entry_ms,
)
from twinklr.core.sequencer.moving_heads.compile.template_compiler import (
    compile_physical_template,
)
from twinklr.core.sequencer.moving_heads.export.frame_encoder import (
    encode_fixture_frames,
    frame_times,
)
from twinklr.core.sequencer.moving_heads.fixture_builder import build_fixture_contexts
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    check_physical_templates,
    physical_cue_limits,
)
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import build_musical_phase_map

_ZOOM = 9
"""The zoom byte of `zoom_pilot_profile_payload`."""
HEADS = ("MH1", "MH2", "MH3", "MH4")


def _zoom_profile(**axis: Any) -> FixtureCapabilities:
    payload = zoom_pilot_profile_payload()
    payload["axes"]["zoom"].update(axis)
    return FixtureCapabilities(**payload)


# --- Encoding --------------------------------------------------------------------------


def test_pilot_profile_is_synthetic_and_fits_a_16_channel_model() -> None:
    """The profile prepared for owner validation is labelled synthetic and every offset,
    zoom included, lies within the owner's 16-channel models."""
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())
    offsets = [axis.coarse_offset for axis in profile.axes.values()]
    offsets += [axis.fine_offset for axis in profile.axes.values() if axis.fine_offset]
    offsets += [wheel.offset for wheel in profile.discrete.values()]
    assert profile.provenance == "synthetic"
    assert profile.footprint == 16 and max(offsets) <= 16
    assert profile.axes["zoom"].coarse_offset == _ZOOM


@pytest.mark.parametrize(
    ("inverted", "expected"),
    [
        pytest.param(False, {10.0: 20, 25.0: 120, 40.0: 220}, id="upright"),
        pytest.param(True, {10.0: 220, 25.0: 120, 40.0: 20}, id="inverted"),
    ],
)
def test_zoom_endpoints_encode_to_the_declared_subrange(
    inverted: bool, expected: dict[float, int]
) -> None:
    axis = _zoom_profile(inverted=inverted).axes["zoom"]
    assert {value: axis.dmx_word(value) for value in expected} == expected


def test_zoom_mapping_is_monotonic_and_inversion_reflects_inside_the_subrange() -> None:
    upright = _zoom_profile().axes["zoom"]
    inverted = _zoom_profile(inverted=True).axes["zoom"]
    values = [Fraction(10) + Fraction(step, 8) for step in range(30 * 8 + 1)]
    words = [upright.dmx_word(value) for value in values]

    assert words == sorted(words) and set(range(20, 221)) == set(words)
    assert [inverted.dmx_word(value) for value in values] == [240 - word for word in words]
    # Each step of 30°/200 words is one word: half a word rounds up, exactly.
    assert upright.dmx_word(Fraction(10) + Fraction(3, 40)) == 21
    assert upright.dmx_word(Fraction(10) + Fraction(3, 40) - Fraction(1, 10**9)) == 20


@pytest.mark.parametrize("value", [9.99, 40.01, -5.0])
def test_out_of_range_zoom_is_rejected(value: float) -> None:
    profile = _zoom_profile()
    with pytest.raises(ValueError, match="outside the operable range"):
        profile.axes["zoom"].dmx_word(value)
    trajectory = ContinuousTrajectory.model_validate(
        {"unit": "degree", "points": [{"t_ms": 0, "value": value}], "interpolation": "hold"}
    )
    with pytest.raises(PhysicalChannelError, match="outside the operable range"):
        check_physical_value("MH1", ChannelName.ZOOM, trajectory, profile)


@pytest.mark.parametrize(
    ("axis", "match"),
    [
        pytest.param({"dmx_min": 220, "dmx_max": 20}, "dmx_min .* below dmx_max", id="reversed"),
        pytest.param({"dmx_min": 20, "dmx_max": 20}, "dmx_min .* below dmx_max", id="empty"),
        pytest.param({"dmx_max": 256}, "dmx_max .* 255", id="past-8-bit"),
        pytest.param({"dmx_min": -1}, "greater than or equal to 0", id="negative"),
        pytest.param(
            {"unit": "normalized", "physical_min": 0.0, "physical_max": 1.0},
            "zoom axis unit must be 'degree'",
            id="unit",
        ),
    ],
)
def test_invalid_zoom_axis_is_rejected(axis: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _zoom_profile(**axis)


def test_zoom_default_byte_outside_the_subrange_is_rejected() -> None:
    payload = zoom_pilot_profile_payload()
    payload["defaults"][_ZOOM] = 10
    with pytest.raises(ValidationError, match="zoom default word 10"):
        FixtureCapabilities(**payload)


def test_a_16_bit_axis_takes_a_subrange_of_its_full_word() -> None:
    payload = physical_head_profile(inverted=False)
    payload["axes"]["pan"].update(dmx_min=1000, dmx_max=64535)
    pan = FixtureCapabilities(**payload).axes["pan"]
    assert (pan.dmx_word(-270.0), pan.dmx_word(270.0)) == (1000, 64535)
    assert pan.dmx_word(0.0) == 32768


_DUMP_SHA256 = {
    "profile": "a3fd5aaf31f077dc69745a8bfe05faefeb8ca9dd7387e73769031a784a566443",
    "head": "068198ba9c45c6a87d65105483f568a1f394ea8af8d910f107b30e4b2bf4ebec",
    "head_inverted": "9cb8db93424b9cabc1734b7d49e5106fa2cf247e7c8c1a4c55c43b723deaabc0",
    "rig": "93ffb351c0110e3208a9dcd7f161e296a04ebb117f57005354eeb6b065a6f192",
    "initial": "65fed8075a2b8887efb602d95cf624b4e965b8df3d194bb09fc01c117e78589f",
}
"""Profile, rig and initial-state dumps recorded before P2.5 (at `36002f2a`). The rig's
was re-recorded in C1.3, which removed the old renderer's fixture fields from its dump
and nothing else."""
_WORDS_SHA256 = "e938a66ff50e48da386232cc4e92bd209397bad0f9082ae08875570f64c088d4"
"""Every axis' words at 998 values across its window, on three profiles, before P2.5."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_default_subrange_leaves_words_and_profile_dumps_unchanged() -> None:
    """With `dmx_min`/`dmx_max` at their defaults, the Phase 1 profiles dump and encode
    exactly as they did before the zoom pilot, and an explicit full subrange encodes the
    same words."""
    payloads = (
        physical_head_profile(inverted=False),
        physical_head_profile(inverted=True),
        profile_payload(),
    )
    dumps = {
        "profile": FixtureCapabilities(**profile_payload()).model_dump_json(),
        "head": FixtureCapabilities(**payloads[0]).model_dump_json(),
        "head_inverted": FixtureCapabilities(**payloads[1]).model_dump_json(),
        "rig": physical_rig().model_dump_json(),
        "initial": InitialFixtureState(**PHYSICAL_INITIAL_STATE).model_dump_json(),
    }
    assert {name: _sha256(dump) for name, dump in dumps.items()} == _DUMP_SHA256
    assert "dmx_min" not in dumps["head"] and "dmx_max" not in dumps["head"]
    assert "zoom_deg" not in dumps["initial"]

    words: list[int] = []
    explicit: list[int] = []
    for payload in payloads:
        widened = copy.deepcopy(payload)
        for axis in widened["axes"].values():
            axis.update(dmx_min=0, dmx_max=65535 if axis.get("fine_offset") else 255)
        for (_, axis), (_, same) in zip(
            sorted(FixtureCapabilities(**payload).axes.items()),
            sorted(FixtureCapabilities(**widened).axes.items()),
            strict=True,
        ):
            low, high = axis.operable_range
            for index in range(998):
                value = Fraction(low) + (Fraction(high) - Fraction(low)) * index / 997
                words.append(axis.dmx_word(value))
                explicit.append(same.dmx_word(value))
    assert _sha256(repr(words)) == _WORDS_SHA256
    assert explicit == words


def test_a_zoomless_profile_refuses_a_zoom_value() -> None:
    profile = FixtureCapabilities(**physical_head_profile(inverted=False))
    trajectory = ContinuousTrajectory.model_validate(
        {"unit": "degree", "points": [{"t_ms": 0, "value": 20.0}], "interpolation": "hold"}
    )
    with pytest.raises(PhysicalChannelError, match="declares no zoom axis"):
        check_physical_value("MH1", ChannelName.ZOOM, trajectory, profile)


def test_initial_zoom_is_required_on_a_zoom_axis_and_refused_without_one() -> None:
    zoom = FixtureCapabilities(**zoom_pilot_profile_payload())
    zoomless = FixtureCapabilities(**physical_head_profile(inverted=False))
    without = InitialFixtureState(**PHYSICAL_INITIAL_STATE)
    with_zoom = InitialFixtureState(**ZOOM_INITIAL_STATE)

    assert zoom.check_initial_state(with_zoom) == ()
    assert zoom.check_initial_state(without) == ("no initial zoom",)
    assert zoom.check_initial_state(with_zoom.model_copy(update={"zoom_deg": 45.0})) == (
        "initial zoom 45.0 is outside the operable range",
    )
    assert zoomless.check_initial_state(with_zoom) == (
        "initial zoom names an axis the profile does not declare",
    )


# --- Compile ---------------------------------------------------------------------------


def _grid(bars: int = 4) -> BeatGrid:
    return physical_bars_grid(*([500.0] * (bars + 1)))


def _compile(
    template: Template, rig: FixtureGroup, *, bars: int = 1, grid: BeatGrid | None = None
) -> list[FixtureSegment]:
    grid = grid or _grid()
    phase_map = build_musical_phase_map(grid)
    start, end = physical_cue_limits(phase_map, int(grid.duration_ms))
    context = TemplateCompileContext(
        section_id="verse",
        template_id=template.template_id,
        fixtures=build_fixture_contexts(rig_profile_from_fixture_group(rig), rig),
        beat_grid=grid,
        start_bar=1,
        duration_bars=bars,
        presets=rig.presets,
        topology=rig_topology(rig),
        fixture_group_id=rig.group_id,
    )
    return compile_physical_template(
        template, context, phase_map=phase_map, start_limit_ms=start, end_limit_ms=end
    ).segments


def _zoom_step(
    shape: str = "sine", start: float = 25.0, extent: float = 10.0, **zoom: Any
) -> dict[str, Any]:
    """`sine_step` (pan ±20° over 4 beats) whose zoom waves on the movement phase."""
    step = sine_step("wave", 0.0, 20.0)
    step["physical_zoom"] = {"shape": shape, "start_deg": start, "extent_deg": extent, **zoom}
    return step


def _doc(step: dict[str, Any], template_id: str = "p25_zoom") -> TemplateDoc:
    return physical_template_doc(template_id, [step])


def _zoom_values(segment: FixtureSegment) -> list[tuple[int, float]]:
    physical = segment.channels[ChannelName.ZOOM].physical
    assert isinstance(physical, ContinuousTrajectory) and physical.unit == "degree"
    return [(point.t_ms, point.value) for point in physical.points]


def test_zoom_waves_on_the_movement_phase() -> None:
    """`start + extent * sin(2*pi*phase)` at the pan movement's own phase: widest a
    quarter period (one 500 ms beat) after the step starts, back at the start angle after
    half a period, narrowest after three quarters; sampled on the same frames as pan."""
    [segment, *_] = _compile(_doc(_zoom_step()).template, zoom_rig(["MH1"], topology=False))
    values = dict(_zoom_values(segment))
    pan = segment.channels[ChannelName.PAN].physical
    assert isinstance(pan, ContinuousTrajectory)
    assert sorted(values) == [point.t_ms for point in pan.points]
    t0 = segment.t0_ms
    assert values[t0] == pytest.approx(25.0)
    assert max(values.values()) == pytest.approx(35.0, abs=0.01)
    assert min(values.values()) == pytest.approx(15.0, abs=0.01)
    beat_one = min(values, key=lambda t: abs(t - (t0 + 500)))
    assert values[beat_one] == pytest.approx(35.0, abs=0.05)


def test_zoom_follows_the_heads_pan_distribution_offset() -> None:
    """Under a pan/tilt distribution a lagging head's zoom lags with its path."""
    step = _zoom_step()
    step["physical_distribution"] = [{"domains": ["pan", "tilt"], "spread_cycles": 0.25}]
    segments = _compile(_doc(step).template, zoom_rig(["MH1", "MH2"]))
    first = {s.fixture_id: _zoom_values(s) for s in segments}
    assert first["MH1"][0][1] == pytest.approx(25.0)  # slot 0 leads at phase 0
    assert first["MH2"][0][1] == pytest.approx(15.0)  # a quarter cycle behind: sin(-pi/2)


@pytest.mark.parametrize(
    ("speed", "match"),
    [
        pytest.param(10.0, "above the configured speed 10", id="too-fast"),
        pytest.param(None, "unknown travel speed", id="unknown"),
    ],
)
def test_zoom_motion_the_axis_cannot_make_is_refused(speed: float | None, match: str) -> None:
    payload = zoom_rig(["MH1"], topology=False).model_dump(mode="json")
    payload["fixtures"][0]["config"]["physical_profile"]["axes"]["zoom"]["travel_speed_per_s"] = (
        speed
    )
    with pytest.raises(PhysicalChannelError, match=match) as error:
        _compile(_doc(_zoom_step()).template, FixtureGroup.model_validate(payload))
    assert error.value.channel is ChannelName.ZOOM


def test_zoom_outside_the_axis_is_refused_at_compile() -> None:
    with pytest.raises(PhysicalChannelError, match="outside the operable range") as error:
        _compile(_doc(_zoom_step(start=35.0)).template, zoom_rig(["MH1"], topology=False))
    assert error.value.channel is ChannelName.ZOOM


def test_a_zoom_hold_holds_its_start_angle() -> None:
    """A `hold` keeps `start_deg` through the step, never the profile's default."""
    step = _zoom_step(shape="hold", start=30.0, extent=0.0)
    [segment] = _compile(_doc(step).template, zoom_rig(["MH1"], topology=False))
    zoom = FixtureCapabilities(**zoom_pilot_profile_payload()).axes["zoom"]
    assert {value for _, value in _zoom_values(segment)} == {30.0}
    assert zoom.dmx_word(30.0) == 153


def test_a_step_without_zoom_holds_the_default_byte_on_a_zoom_rig() -> None:
    """Unauthored, the encoder would write the default byte; the cue holds that value
    explicitly, so its bytes are the same and the transaction pass can hold it."""
    rig = zoom_rig(["MH1"], topology=False)
    [segment] = _compile(_doc(hold_step("still", 0.0)).template, rig)
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())
    zoom = profile.axes["zoom"]
    assert {zoom.dmx_word(value) for _, value in _zoom_values(segment)} == {20}
    frames = encode_fixture_frames([segment], profile, frame_times_ms=(segment.t0_ms,))
    assert dict(frames[0].channels)[_ZOOM] == 20


def test_zoom_step_on_a_zoomless_rig_is_refused_unless_omit_optional_zoom() -> None:
    """Phase 1's rule stands: a missing capability fails. `omit_optional_zoom` is the
    one declared alternative: the step compiles without zoom and says so per cue."""
    with pytest.raises(PhysicalCompileError, match="zoom"):
        _compile(_doc(_zoom_step()).template, physical_rig())
    segments = _compile(
        _doc(_zoom_step(if_unsupported="omit_optional_zoom")).template, physical_rig()
    )
    assert segments
    for segment in segments:
        assert ChannelName.ZOOM not in segment.channels
        assert segment.metadata["omitted_optional"] == "zoom"
    # On a zoom rig the alternative changes nothing.
    rig = zoom_rig(["MH1"], topology=False)
    plain = _compile(_doc(_zoom_step()).template, rig)
    optional = _compile(_doc(_zoom_step(if_unsupported="omit_optional_zoom")).template, rig)
    assert [s.channels for s in optional] == [s.channels for s in plain]
    assert all("omitted_optional" not in s.metadata for s in optional)


def test_omitted_zoom_is_recorded_in_the_render_trace() -> None:
    """Each cue that played without its optional zoom is listed in the trace; a render
    that omits nothing has no such key, so earlier traces keep their keys."""
    omitting = _doc(_zoom_step(if_unsupported="omit_optional_zoom"), "p25_optional")
    plain = _doc(sine_step("wave", 0.0, 20.0), "p25_plain")
    with registered_templates(omitting, plain):
        records = {}
        for template_id in ("p25_optional", "p25_plain"):
            pipeline = RenderingPipeline(
                choreography_plan=physical_sections((template_id, 1, 2)),
                beat_grid=_grid(),
                fixture_group=physical_rig(),
                job_config=physical_job(),
            )
            pipeline.render()
            assert pipeline.render_record is not None
            records[template_id] = pipeline.render_record

    omitted = records["p25_optional"]["omitted_optional"]
    assert {(r["fixture_id"], r["attribute"], r["alternative"]) for r in omitted} == {
        ("MH1", "zoom", "omit_optional_zoom"),
        ("MH2", "zoom", "omit_optional_zoom"),
    }
    assert all(r["section_id"] == "s1" and r["step_id"] == "wave" for r in omitted)
    assert "omitted_optional" not in records["p25_plain"]


@pytest.mark.parametrize(
    ("step", "match"),
    [
        pytest.param(_zoom_step(shape="hold"), "hold takes no extent_deg", id="hold-extent"),
        pytest.param(_zoom_step(extent=0.0), "sine needs a nonzero extent_deg", id="flat-sine"),
        pytest.param(
            {**hold_step("still", 0.0), "physical_zoom": _zoom_step()["physical_zoom"]},
            "periodic movement",
            id="sine-on-hold",
        ),
    ],
)
def test_invalid_zoom_spec_is_rejected(step: dict[str, Any], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        TemplateStep.model_validate(step)


def test_zoom_spec_is_left_out_of_dumps_when_absent() -> None:
    assert "physical_zoom" not in TemplateStep.model_validate(hold_step("s", 0.0)).model_dump()


# --- Transactions ----------------------------------------------------------------------


def _line(unit: str, value: float, t0: int, t1: int) -> ContinuousTrajectory:
    return ContinuousTrajectory.model_validate(
        {
            "unit": unit,
            "points": [{"t_ms": t0, "value": value}, {"t_ms": t1, "value": value}],
            "interpolation": "linear",
        }
    )


def _cue(name: str, t0: int, t1: int, zoom: float) -> FixtureSegment:
    state = DiscreteTrajectory.model_validate({"events": [{"t_ms": t0, "state": "open"}]})
    return physical_segment(
        {
            ChannelName.PAN: _line("degree", 0.0, t0, t1),
            ChannelName.TILT: _line("degree", 0.0, t0, t1),
            ChannelName.ZOOM: _line("degree", zoom, t0, t1),
            ChannelName.DIMMER: _line("normalized", 1.0, t0, t1),
            ChannelName.SHUTTER: state,
        },
        t0_ms=t0,
        t1_ms=t1,
        segment_id=name,
    )


def _plan(cues: list[FixtureSegment], **options: Any) -> PrepositionResult:
    return plan_prepositions(
        cues,
        {"MH1": FixtureCapabilities(**zoom_pilot_profile_payload())},
        initial_states={"MH1": InitialFixtureState(**ZOOM_INITIAL_STATE)},
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=2000,
        **options,
    )


def test_zoom_is_held_and_settled_across_a_gap() -> None:
    """From 15° to 35° (words 53 to 187) between two lit cues: the transaction moves the
    zoom only in the dark, straight toward the next cue, and the reveal waits for it to
    arrive (134 words of 0.15° at 90°/s, 223 ms) and settle (40 ms): 280 ms on the frame
    grid. After the last cue it parks there. Checked from the bytes."""
    cues = [_cue("A", 200, 400, 15.0), _cue("B", 1000, 1200, 35.0)]
    result = _plan(cues)
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())

    assert not result.has_errors, result.diagnostics
    second = next(d for d in result.diagnostics if d.cue_ms == 1000)
    assert second.status == "feasible" and second.required_ms == 280
    transactions = [s for s in result.segments if TRANSACTION_METADATA_KEY in s.metadata]
    assert all(ChannelName.ZOOM in s.channels for s in transactions)
    frames = encode_fixture_frames(result.segments, profile, frame_times_ms=frame_times(2000))
    zoom = {f.time_ms: dict(f.channels)[_ZOOM] for f in frames}
    gap = [zoom[t] for t in range(400, 1000, EFFECT_GRID_MS)]
    assert zoom[380] == 53 and gap == sorted(gap) and gap[0] > 53 and gap[-1] == 187
    assert zoom[1000] == 187
    assert {zoom[t] for t in range(1200, 2000, EFFECT_GRID_MS)} == {187}  # parked, held
    assert_honest_transactions(result, cues, profile, InitialFixtureState(**ZOOM_INITIAL_STATE))


def test_a_gap_too_short_for_the_zoom_refuses_the_reveal() -> None:
    """260 ms is one frame short of the zoom's 280 ms; pan and tilt do not move."""
    result = _plan([_cue("A", 200, 400, 15.0), _cue("B", 660, 860, 35.0)])
    [error] = [d for d in result.diagnostics if d.status == "error"]
    assert error.cue_ms == 660 and error.code == "infeasible_transition"
    assert error.required_ms == 280


def test_preserve_aim_holds_the_zoom_at_the_heads_word() -> None:
    """With too little time to move the zoom, a cue that opts into `preserve_aim` plays
    with pan, tilt and zoom held where the head is (15°, word 53), and stays honest."""
    cues = [_cue("A", 200, 400, 15.0), _cue("B", 660, 860, 35.0)]
    cues[1].metadata[FALLBACK_METADATA_KEY] = "preserve_aim"
    result = _plan(cues, failure_mode="preserve_aim")
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())

    assert not result.has_errors, result.diagnostics
    second = next(d for d in result.diagnostics if d.cue_ms == 660)
    assert second.status == "preserve_aim" and second.required_ms == 280
    frames = encode_fixture_frames(result.segments, profile, frame_times_ms=frame_times(2000))
    zoom = {f.time_ms: dict(f.channels)[_ZOOM] for f in frames}
    assert {zoom[t] for t in range(660, 860, EFFECT_GRID_MS)} == {53}
    assert_honest_transactions(result, cues, profile, InitialFixtureState(**ZOOM_INITIAL_STATE))


def test_entry_bound_counts_zoom_words_over_the_subrange() -> None:
    """The worst-case entry from 10° to 40° is 200 words of 0.15° (the 20-220 subrange,
    not 255 words), 333 ms at 90°/s: one frame of wheels, 340 ms of travel, 40 ms of
    settle and 60 ms for motion still under way (40 ms settle plus a word's travel)."""
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())
    still = {ChannelName.PAN: (0.0, 0.0), ChannelName.TILT: (0.0, 0.0)}
    bound = worst_case_entry_ms(
        profile,
        entry_pose={**still, ChannelName.ZOOM: (40.0, 40.0)},
        entry_wheels={},
        pose_envelope={**still, ChannelName.ZOOM: (10.0, 10.0)},
        held_wheels={ChannelName.COLOR: {"white"}, ChannelName.GOBO: {"open"}},
        frame_ms=EFFECT_GRID_MS,
    )
    assert bound == 0 + 20 + 340 + 40 + 60


def test_gate_treats_a_missing_initial_zoom_as_an_unknown_initial_state() -> None:
    """On a zoom rig a run whose initial states give no `zoom_deg` is refused through the
    unknown-initial-state path, naming it, never with a raw error."""
    with (
        physical_catalog(),
        pytest.raises(UnsupportedRenderModeError, match="no initial zoom"),
    ):
        _gate(["target_orbit"], zoom_rig(HEADS), family_job(HEADS))


def test_the_oracle_catches_a_zoom_left_to_its_default_between_cues() -> None:
    """Strip the zoom from every transaction: the gap falls to the default byte (10°) and
    jumps back at the reveal, which the byte-level check must refuse."""
    cues = [_cue("A", 200, 400, 15.0), _cue("B", 1000, 1200, 35.0)]
    result = _plan(cues)
    stripped = [
        s.model_copy(
            update={"channels": {c: v for c, v in s.channels.items() if c is not ChannelName.ZOOM}}
        )
        if TRANSACTION_METADATA_KEY in s.metadata
        else s
        for s in result.segments
    ]
    broken = result.model_copy(update={"segments": tuple(stripped)})
    with pytest.raises(AssertionError, match="zoom"):
        assert_honest_transactions(
            broken,
            cues,
            FixtureCapabilities(**zoom_pilot_profile_payload()),
            InitialFixtureState(**ZOOM_INITIAL_STATE),
        )


# --- The zoom_wave family --------------------------------------------------------------


def _gate(template_ids: list[str], rig: FixtureGroup, job: JobConfig) -> Any:
    return check_physical_templates(
        template_ids,
        beat_grid=_grid(6),
        fixture_group=rig,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=template_ids,
    )


def test_zoom_wave_is_left_out_on_a_zoomless_rig_and_offered_on_a_zoom_rig() -> None:
    """Admission is P2.4c's: the dry compile's capability failure excludes the family on
    a rig without a zoom axis, naming it, while the rig keeps the others."""
    with physical_catalog():
        zoomless = _gate([ZOOM_FAMILY_ID, "target_orbit"], family_rig(HEADS), family_job(HEADS))
        zoomed = _gate([ZOOM_FAMILY_ID, "target_orbit"], zoom_rig(HEADS), zoom_job(HEADS))

    assert zoomless.admitted == ("target_orbit",)
    [exclusion] = zoomless.exclusions
    assert exclusion["template_id"] == ZOOM_FAMILY_ID
    assert "declares no zoom axis" in exclusion["reason"]
    assert zoomed.admitted == (ZOOM_FAMILY_ID, "target_orbit") and not zoomed.exclusions


def _render(
    sections: list[tuple[str, int, int]], rig: FixtureGroup, job: JobConfig
) -> tuple[RenderingPipeline, list[FixtureSegment]]:
    pipeline = RenderingPipeline(
        choreography_plan=physical_sections(*sections),
        beat_grid=physical_bars_grid(500.0, 500.0, 430.0, 430.0, 500.0, 500.0, 500.0),
        fixture_group=rig,
        job_config=job,
    )
    return pipeline, pipeline.render()


def _without(rig: FixtureGroup, gone: str) -> FixtureGroup:
    payload = rig.model_dump(mode="json")
    payload["fixtures"] = [f for f in payload["fixtures"] if f["fixture_id"] != gone]
    for preset in payload["presets"]["attributes"].values():
        preset["fixtures"].pop(gone, None)
    return FixtureGroup.model_validate(payload)


def test_zoom_wave_renders_honestly_repeatably_and_without_a_head() -> None:
    """The family, another without zoom, then the family again on the zoom rig: honest
    from the bytes (zoom held through each gap and settled before each reveal), nothing
    kept dark, identical on a repeat, and removing a head leaves the others' frames."""
    sections = [(ZOOM_FAMILY_ID, 1, 2), ("target_orbit", 3, 4), (ZOOM_FAMILY_ID, 5, 6)]
    rig, job = zoom_rig(HEADS), zoom_job(HEADS)
    present = tuple(h for h in HEADS if h != "MH2")
    with physical_catalog():
        pipeline, segments = _render(sections, rig, job)
        again, _ = _render(sections, rig, job)
        subset, _ = _render(sections, _without(rig, "MH2"), zoom_job(present))

    cues = [s for s in segments if TRANSACTION_METADATA_KEY not in s.metadata]
    profile = FixtureCapabilities(**zoom_pilot_profile_payload())
    replanned = plan_prepositions(
        cues,
        dict.fromkeys(HEADS, profile),
        initial_states=job.moving_heads.initial_states,
        locks=(),
        frame_ms=EFFECT_GRID_MS,
        sequence_end_ms=len(frame_times(int(pipeline.beat_grid.duration_ms))) * EFFECT_GRID_MS,
    )
    assert list(replanned.segments) == segments
    initial = job.moving_heads.initial_states["MH1"]
    for fixture_id in HEADS:
        assert_honest_transactions(replanned, cues, profile, initial, fixture_id=fixture_id)
    assert pipeline.render_record is not None
    assert pipeline.render_record["unplayable_totals"] == {}
    assert again.frames == pipeline.frames
    frames = {fixture_id: _frames(pipeline, fixture_id) for fixture_id in HEADS}
    for fixture_id in present:
        assert _frames(subset, fixture_id) == frames[fixture_id], fixture_id
    # The beam waves inside the family and holds its default (10°, byte 20) in the orbit.
    orbit_start, orbit_end = (
        pipeline.beat_grid.bar_boundaries[2],
        pipeline.beat_grid.bar_boundaries[4],
    )
    zoom_words = {frame[_ZOOM] for frame in frames["MH1"]}
    assert min(zoom_words) <= 60 and max(zoom_words) >= 180
    orbit = [
        frame[_ZOOM]
        for f, frame in zip(
            (f for f in pipeline.frames if f.fixture_id == "MH1"), frames["MH1"], strict=True
        )
        if orbit_start + 1000 <= f.time_ms < orbit_end
    ]
    assert set(orbit) == {20}


def _frames(pipeline: RenderingPipeline, fixture_id: str) -> list[dict[int, int]]:
    return [dict(f.channels) for f in pipeline.frames if f.fixture_id == fixture_id]


# --- Registry evidence -----------------------------------------------------------------

_STEP = "template.template.steps.physical_zoom"
_COMPONENT_NOTES = {
    "compiled": "exact path changes the physical compile result",
    "rejected": "exact path's alternative is rejected by physical validation or compile",
}


def _zoom_spec(change: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
    return lambda doc: change(doc["template"]["steps"][0]["physical_zoom"])


_MUTATIONS: dict[str, tuple[str, Callable[[dict[str, Any]], Any]]] = {
    _STEP: ("compiled", lambda doc: doc["template"]["steps"][0].pop("physical_zoom")),
    f"{_STEP}.shape": ("rejected", _zoom_spec(lambda z: z.update(shape="hold"))),
    f"{_STEP}.start_deg": ("compiled", _zoom_spec(lambda z: z.update(start_deg=20.0))),
    f"{_STEP}.extent_deg": ("compiled", _zoom_spec(lambda z: z.update(extent_deg=5.0))),
    f"{_STEP}.if_unsupported": ("rejected", _zoom_spec(lambda z: z.update(if_unsupported="error"))),
}
"""Per config path: the component its alternative must change, and that alternative."""

ZOOM_PATHS = tuple(
    path
    for path, disposition in CONFIG_EFFECTS.items()
    if disposition.kind is ConfigDispositionKind.EFFECT_TEST
    and disposition.test_nodeid is not None
    and "::test_zoom_field_changes_compile[" in disposition.test_nodeid
)


def _evidence_payload() -> dict[str, Any]:
    return _doc(_zoom_step(if_unsupported="omit_optional_zoom")).model_dump(mode="json")


def _evidence_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """The template compiled on a zoom rig and on a zoomless one."""
    try:
        template = TemplateDoc.model_validate(payload).template
        compiled = [
            _compile(template, rig) for rig in (zoom_rig(["MH1"], topology=False), physical_rig())
        ]
    except (ValidationError, PhysicalCompileError, PhysicalChannelError) as error:
        return {"rejected": f"{type(error).__name__}: {error}"}
    return {"compiled": [[s.model_dump(mode="json") for s in segments] for segments in compiled]}


def test_zoom_evidence_paths_cover_every_mutation() -> None:
    assert set(ZOOM_PATHS) == set(_MUTATIONS)
    for path, (component, _) in _MUTATIONS.items():
        assert CONFIG_EFFECTS[path].note == _COMPONENT_NOTES[component], path


@pytest.mark.parametrize("config_path", ZOOM_PATHS, ids=ZOOM_PATHS)
def test_zoom_field_changes_compile(config_path: str) -> None:
    """Each zoom spec path changes the compiled cues, or is refused."""
    component, mutate = _MUTATIONS[config_path]
    payload = _evidence_payload()
    mutate(payload)
    base, changed = _evidence_snapshot(_evidence_payload()), _evidence_snapshot(payload)
    assert "rejected" not in base, base
    if component == "rejected":
        assert "rejected" in changed, changed
        return
    assert "rejected" not in changed, changed
    assert changed["compiled"] != base["compiled"]


def test_zoom_wave_presets_only_slow_or_narrow_it() -> None:
    """The family's variants ask for less reach or rate than its base, never more."""
    with physical_catalog():
        segments = {preset: _compile_family(preset) for preset in (None, "narrow", "slow")}

    def peak(preset: str | None, channel: ChannelName) -> float:
        rates = []
        for segment in segments[preset]:
            physical = segment.channels[channel].physical
            assert isinstance(physical, ContinuousTrajectory)
            rates += [
                abs(b.value - a.value) * 1000 / (b.t_ms - a.t_ms)
                for a, b in zip(physical.points, physical.points[1:], strict=False)
            ]
        return max(rates)

    for channel in (ChannelName.PAN, ChannelName.ZOOM):
        assert peak("narrow", channel) <= peak(None, channel) + 1e-9
        assert peak("slow", channel) < peak(None, channel)
    assert math.isclose(
        peak("slow", ChannelName.ZOOM), peak(None, ChannelName.ZOOM) / 2, rel_tol=0.05
    )


def _compile_family(preset_id: str | None) -> list[FixtureSegment]:
    from twinklr.core.sequencer.moving_heads.compile.preset import apply_preset
    from twinklr.core.sequencer.moving_heads.templates import get_template

    document = get_template(ZOOM_FAMILY_ID)
    template = document.template
    if preset_id is not None:
        [preset] = [p for p in document.presets if p.preset_id == preset_id]
        template = apply_preset(template, preset)
    return _compile(template, zoom_rig(HEADS), bars=2)
