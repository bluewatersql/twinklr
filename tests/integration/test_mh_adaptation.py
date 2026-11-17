"""Families adapt to the rig and the song instead of being left out.

A family is admitted through the first of its variants (base, then its declared presets
in order) that the rig can play on this song: its effective variant, which a section
naming no preset renders. A repeating cycle is stretched to whole bars holding whole
movement periods, so the continuous families play in any meter. Synthetic rigs and
jittered grids only: no audio, provider, owner data or xLights. How any of it looks is
`PENDING-OWNER`.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from itertools import pairwise
import random

import pytest

from tests.support.moving_heads import (
    FAMILY_IDS,
    envelope_step,
    family_catalog,
    family_job,
    family_rig,
    hold_step,
    loop_template_doc,
    p1_job,
    p1_rig,
    registered_templates,
    sections_plan,
    sine_step,
    sweep_step,
    with_preset,
)
from twinklr.core.agents.sequencer.moving_heads.models import ChoreographyPlan
from twinklr.core.config.fixtures import AxisCapability, FixtureCapabilities, FixtureGroup
from twinklr.core.config.models import JobConfig
from twinklr.core.formats.xlights.sequence.fresh import EFFECT_GRID_MS
from twinklr.core.sequencer.models.enum import ChannelName
from twinklr.core.sequencer.models.template import TemplateDoc, TemplatePreset
from twinklr.core.sequencer.moving_heads.compile.preposition import TRANSACTION_METADATA_KEY
from twinklr.core.sequencer.moving_heads.pipeline import (
    RenderingPipeline,
    TemplateAdmission,
    admit_templates,
)
from twinklr.core.sequencer.moving_heads.templates.library import get_template
from twinklr.core.sequencer.timing.beat_grid import BeatGrid
from twinklr.core.sequencer.timing.musical_phase import (
    build_musical_phase_map,
    musical_phase_fraction,
)

HEADS = ("MH1", "MH2", "MH3", "MH4")


def _rig(speed: float) -> FixtureGroup:
    """`family_rig` of four heads moving pan and tilt at `speed` degrees a second, 20 ms
    latency and 60 ms settle, every color and gobo state settling in 150 ms."""
    payload = family_rig(HEADS).model_dump(mode="json")
    for fixture in payload["fixtures"]:
        profile = fixture["config"]["physical_profile"]
        for axis in ("pan", "tilt"):
            profile["axes"][axis].update(travel_speed_per_s=speed, latency_ms=20, settle_ms=60)
        for wheel in ("color", "gobo"):
            for state in profile["discrete"][wheel]["states"].values():
                state["settle_ms"] = 150
    return FixtureGroup.model_validate(payload)


def _grid(
    beats_per_bar: int, low_ms: float, high_ms: float, seconds: float, seed: int = 7
) -> BeatGrid:
    """Beats drawn uniformly from `[low_ms, high_ms]` (seeded) from 15 ms for `seconds`,
    a bar every `beats_per_bar` beats from the first."""
    rng = random.Random(seed)
    beats = [15.0]
    while beats[-1] < seconds * 1000:
        beats.append(round(beats[-1] + rng.uniform(low_ms, high_ms), 3))
    intervals = [later - earlier for earlier, later in pairwise(beats)]
    return BeatGrid(
        bar_boundaries=beats[::beats_per_bar],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=60_000 * len(intervals) / sum(intervals),
        beats_per_bar=beats_per_bar,
        duration_ms=beats[-1] + 15.0,
    )


def _tempo_grid(beats_per_bar: int, bpm: float, seconds: float) -> BeatGrid:
    """`_grid` at `bpm`, each beat jittered by up to 8%."""
    beat = 60_000 / bpm
    return _grid(beats_per_bar, beat * 0.92, beat * 1.08, seconds)


def _gate(grid: BeatGrid, rig: FixtureGroup, job: JobConfig) -> TemplateAdmission:
    return admit_templates(
        list(FAMILY_IDS),
        beat_grid=grid,
        fixture_group=rig,
        initial_states=job.moving_heads.initial_states,
        failure_mode=job.moving_heads.reposition_fallback,
        on_unplayable=job.moving_heads.on_unplayable,
        excludable=list(FAMILY_IDS),
    )


def _plan(*sections: tuple[str, str | None, int, int]) -> ChoreographyPlan:
    """`sections_plan` of `(template_id, preset_id, start_bar, end_bar)`."""
    plan = sections_plan(*((t, start, end) for t, _, start, end in sections))
    return plan.model_copy(
        update={
            "sections": [
                with_preset(section, preset_id)
                for section, (_, preset_id, _, _) in zip(plan.sections, sections, strict=True)
            ]
        }
    )


def _render(
    sections: Sequence[tuple[str, str | None, int, int]],
    grid: BeatGrid,
    rig: FixtureGroup,
    job: JobConfig,
    admission: TemplateAdmission,
) -> tuple[RenderingPipeline, list]:
    pipeline = RenderingPipeline(
        choreography_plan=_plan(*sections),
        beat_grid=grid,
        fixture_group=rig,
        job_config=job,
        admission=admission,
    )
    return pipeline, pipeline.render()


def _degrees(frame: dict[int, int], axis: AxisCapability) -> Fraction:
    word = frame[axis.coarse_offset]
    if axis.fine_offset is not None:
        word = word << 8 | frame[axis.fine_offset]
    span = Fraction(axis.physical_max) - Fraction(axis.physical_min)
    return Fraction(axis.physical_min) + word * span / axis.full_word


def _dark(frame: dict[int, int], profile: FixtureCapabilities) -> bool:
    dimmer = profile.axes["dimmer"]
    if frame[dimmer.coarse_offset] == dimmer.dmx_word(0):
        return True
    shutter = profile.discrete["shutter"]
    state = next(n for n, s in shutter.states.items() if s.value == frame[shutter.offset])
    return state in profile.visibility.extinguishing_shutter_states


def _profile(rig: FixtureGroup) -> FixtureCapabilities:
    profile = rig.expand_fixtures()[0].config.physical_profile
    assert profile is not None
    return profile


# --- B1: the variant ladder -------------------------------------------------------------

_CHASED = ("fly_in_cascade", "fly_out_cascade", "masked_wheel_flick")
"""The families whose base a 150°/s head cannot follow near 157 BPM."""


def test_near_157_bpm_a_family_too_fast_for_the_rig_plays_a_declared_variant() -> None:
    """Beats of 340-420 ms on 150°/s heads: the cascades' base sweep and the flick's
    base mask are too fast, so each is admitted through a later declared variant, its
    effective variant. The gate records why each earlier rung failed (the base as a
    preset exclusion naming no preset), the trace records the effective variant, and a
    section naming no preset renders exactly what naming that variant does."""
    grid = _grid(4, 340.0, 420.0, seconds=30.0)
    rig, job = _rig(150.0), family_job(HEADS)
    with family_catalog():
        admission = _gate(grid, rig, job)
        runs = {
            (template_id, preset_id): _render(
                [(template_id, preset_id, 1, 8)], grid, rig, job, admission
            )[0]
            for template_id in _CHASED
            for preset_id in (None, admission.effective_preset.get(template_id))
        }
        declared = {t: [preset.preset_id for preset in get_template(t).presets] for t in _CHASED}

    assert admission.effective_preset == {
        "finite_snap_hold": None,
        "fly_in_cascade": "narrow",
        "fly_out_cascade": "narrow",
        "masked_wheel_flick": "narrow",
        "mirror_wings": "narrow",
        "target_orbit": None,
    }
    assert admission.entry_dips.keys() == set(admission.admitted)  # over admitted rungs
    failed = {(e["template_id"], e["preset_id"]): e["reason"] for e in admission.preset_exclusions}
    for template_id in _CHASED:
        effective = admission.effective_preset[template_id]
        order = declared[template_id]
        for earlier in [None, *order[: order.index(effective)]]:
            reason = failed[template_id, earlier]
            where = f"template {template_id!r}" + (f", preset {earlier!r}" if earlier else "")
            assert reason.startswith(where), reason
        assert effective in admission.admitted_presets[template_id]
        record = runs[template_id, None].render_record
        assert record is not None
        assert record["admission_effective_presets"][template_id] == effective
        assert {
            "template_id": template_id,
            "preset_id": None,
            "reason": failed[template_id, None],
        } in record["admission_preset_exclusions"]
        assert record["unplayable_totals"] == {}
        assert not [d for d in record["diagnostics"] if "preset" in d["message"]]
        assert runs[template_id, None].frames == runs[template_id, effective].frames


def test_a_render_playing_another_preset_than_named_has_its_own_fingerprint() -> None:
    """The gate's result can change what a section renders, so the fingerprint names
    the preset a section renders where it is not the one named. Gated and ungated, a
    cascade (effective `narrow`) naming no preset, or one it does not declare, renders
    `narrow` or its base and so differs; the orbit, which plays its base either way,
    keeps one fingerprint, and so does a section naming the effective variant itself."""
    grid = _grid(4, 340.0, 420.0, seconds=30.0)
    rig, job = _rig(150.0), family_job(HEADS)

    def fingerprint(template_id: str, preset_id: str | None, gated: bool) -> str:
        return RenderingPipeline(
            choreography_plan=_plan((template_id, preset_id, 1, 8)),
            beat_grid=grid,
            fixture_group=rig,
            job_config=job,
            admission=admission if gated else None,
        ).fingerprint()

    with family_catalog():
        admission = _gate(grid, rig, job)
        assert admission.effective_preset["fly_out_cascade"] == "narrow"
        for preset_id in (None, "undeclared"):
            assert fingerprint("fly_out_cascade", preset_id, True) != fingerprint(
                "fly_out_cascade", preset_id, False
            )
        for template_id, preset_id in (("target_orbit", None), ("fly_out_cascade", "narrow")):
            assert fingerprint(template_id, preset_id, True) == fingerprint(
                template_id, preset_id, False
            )


# --- B2: whole-period cycles ------------------------------------------------------------

_CONTINUOUS = ("masked_wheel_flick", "mirror_wings", "target_orbit")
"""Families whose motion runs on across the cycle boundary, lit."""


@pytest.mark.parametrize(
    ("beats_per_bar", "bpm"),
    [(2, 100.0), (2, 150.0), (3, 100.0), (3, 150.0), (6, 100.0), (6, 150.0)],
)
def test_in_other_meters_the_continuous_families_play_on_across_each_cycle(
    beats_per_bar: int, bpm: float
) -> None:
    """In 2/4, 3/4 and 6/8 the orbit, the wings and the flick are admitted, and each
    renders a section spanning several cycles with no head moving faster than its
    profile from one frame to the next, nothing kept dark for being unplayable, and the
    orbit and the wings lit from entry to the section end: the motion runs on across
    every cycle boundary."""
    grid = _tempo_grid(beats_per_bar, bpm, seconds=60.0)
    rig, job = _rig(150.0), family_job(HEADS)
    profile = _profile(rig)
    pan, tilt = profile.axes["pan"], profile.axes["tilt"]
    with family_catalog():
        admission = _gate(grid, rig, job)
        assert set(_CONTINUOUS) <= set(admission.admitted)
        runs = {
            template_id: _render([(template_id, None, 1, 16)], grid, rig, job, admission)
            for template_id in _CONTINUOUS
        }
    for template_id, (pipeline, segments) in runs.items():
        record = pipeline.render_record
        assert record is not None
        assert record["unplayable_totals"] == {}, template_id
        for fixture_id in HEADS:
            cues = [
                cue
                for cue in segments
                if cue.fixture_id == fixture_id and TRANSACTION_METADATA_KEY not in cue.metadata
            ]
            cycles = {int(cue.metadata["requested_t0_ms"]) for cue in cues}
            assert len(cycles) >= 3, (template_id, fixture_id)  # two cycle boundaries
            section_end = max(cue.t1_ms for cue in cues)
            frames = [
                dict(f.channels)
                for f in pipeline.frames
                if f.fixture_id == fixture_id and f.time_ms < section_end
            ]
            for axis in (pan, tilt):
                assert axis.travel_speed_per_s is not None
                step = Fraction(axis.travel_speed_per_s) * EFFECT_GRID_MS / 1000
                word = (Fraction(axis.physical_max) - Fraction(axis.physical_min)) / axis.full_word
                for before, after in pairwise(frames):
                    move = abs(_degrees(after, axis) - _degrees(before, axis))
                    assert move <= step + word, (template_id, fixture_id, float(move))
            if template_id == "masked_wheel_flick":
                continue
            lit = [not _dark(frame, profile) for frame in frames]
            first = lit.index(True)
            assert all(lit[first:]), (template_id, fixture_id)


def _waltz_with_a_short_beat(short_beat: int) -> BeatGrid:
    """12 bars of 3/4 at 500 ms beats, one of them, at index `short_beat`, 15 ms."""
    beats = [15.0]
    for index in range(36):
        beats.append(beats[-1] + (15.0 if index == short_beat else 500.0))
    return BeatGrid(
        bar_boundaries=beats[::3],
        beat_boundaries=beats,
        eighth_boundaries=BeatGrid._calculate_eighth_boundaries(beats),
        sixteenth_boundaries=BeatGrid._calculate_sixteenth_boundaries(beats),
        tempo_bpm=120.0,
        beats_per_bar=3,
        duration_ms=beats[-1] + 15.0,
    )


def _gate_blink(blink: TemplateDoc, grid: BeatGrid) -> TemplateAdmission:
    """The gate over `blink` and a still template on `p1_rig`."""
    still = loop_template_doc("p3_still", [hold_step("still", 0.0)])
    job = p1_job()
    ids = [blink.template.template_id, "p3_still"]
    with registered_templates(blink, still):
        return admit_templates(
            ids,
            beat_grid=grid,
            fixture_group=p1_rig(),
            initial_states=job.moving_heads.initial_states,
            failure_mode=job.moving_heads.reposition_fallback,
            on_unplayable=job.moving_heads.on_unplayable,
            excludable=ids,
        )


@pytest.mark.parametrize(("short_beat", "bar"), [(7, 3), (10, 4)])
def test_the_gate_places_a_grown_cycle_at_each_of_its_alignments_to_the_bars(
    short_beat: int, bar: int
) -> None:
    """A step lit over the second quarter of each 4-beat period, in a 2-bar 3/4 cycle
    that grows to 4 bars (12 beats): placed from bar 1 it lights beats 1, 5, 9..., from
    bar 2 beats 4, 8..., from bar 3 beats 7, 11..., from bar 4 beats 10, 14.... One
    15 ms beat at index 7 or 10 is a lit window shorter than a frame only where a section
    starting on bar 3 or 4 lights it, so the gate must place the grown cycle at all four
    alignments, not the authored cycle's two, to leave the template out."""
    blink = loop_template_doc(
        "p3_blink",
        [envelope_step("blink", 0.0, 0.5, lit=(0.25, 0.5), duration=2.0)],
        cycle_bars=2.0,
    )
    admission = _gate_blink(blink, _waltz_with_a_short_beat(short_beat))

    assert admission.admitted == ("p3_still",)
    [exclusion] = admission.exclusions
    assert f", placed at bar {bar} " in exclusion["reason"], exclusion["reason"]
    assert "shorter than one 20 ms frame" in exclusion["reason"]


def test_the_gate_places_each_preset_at_the_alignments_of_its_own_grown_cycle() -> None:
    """`slow` doubles the period to 8 beats, so in 3/4 its cycle grows to 8 bars (24
    beats), the base's to 4. Lit over one beat of each 8-beat period, `slow` lights beat
    14 only placed from bar 5 (beat 12): placed from bars 1 to 4 it lights beats 2, 5,
    8 and 11 and every 8 after. A 15 ms beat 14 therefore leaves `slow` out only if the
    gate places it at its own cycle's eight alignments, not the base's four. (The base,
    lighting half of beat 14 placed from bar 4, is out too.)"""
    blink = loop_template_doc(
        "p3_blink",
        [envelope_step("blink", 0.0, 0.5, lit=(0.25, 0.375), duration=2.0)],
        cycle_bars=2.0,
    )
    slow = TemplatePreset.model_validate(
        {
            "preset_id": "slow",
            "step_patches": {"blink": {"movement": {"period_beats": 8.0}}},
        }
    )
    admission = _gate_blink(
        TemplateDoc(template=blink.template, presets=[slow]), _waltz_with_a_short_beat(14)
    )

    assert admission.admitted == ("p3_still",)
    [exclusion] = admission.exclusions
    reason = exclusion["reason"]
    assert "template 'p3_blink', step 'blink', fixture 'MH1', placed at bar 4 " in reason
    assert ", preset 'slow', placed at bar 5 " in reason, reason


@pytest.mark.parametrize("beats_per_bar", [3, 4])
@pytest.mark.parametrize("template_id", ["target_orbit", "mirror_wings", "masked_wheel_flick"])
def test_consecutive_cycles_join_without_a_quantization_step(
    template_id: str, beats_per_bar: int
) -> None:
    """Cycles start on bar boundaries, which a jittered grid puts at varying distances
    from the 20 ms frame grid. Each cycle of a step holding whole periods continues the
    section's musical phase rather than restarting at its own frame-quantized start, so
    where one cue ends and the next begins the commanded pose is the same."""
    grid = _grid(beats_per_bar, 340.0, 420.0, seconds=30.0)
    rig, job = _rig(720.0), family_job(HEADS)
    with family_catalog():
        _, segments = _render([(template_id, None, 1, 12)], grid, rig, job, None)
    joins = 0
    for fixture_id in HEADS:
        cues = sorted(
            (
                cue
                for cue in segments
                if cue.fixture_id == fixture_id and TRANSACTION_METADATA_KEY not in cue.metadata
            ),
            key=lambda cue: cue.t0_ms,
        )
        for before, after in pairwise(cues):
            if before.t1_ms != after.t0_ms:
                continue
            for channel in (ChannelName.PAN, ChannelName.TILT):
                end = before.channels[channel].physical.points[-1]
                start = after.channels[channel].physical.points[0]
                assert end.t_ms == start.t_ms
                assert end.value == pytest.approx(start.value, abs=1e-9), (
                    template_id,
                    fixture_id,
                    channel,
                    start.t_ms,
                )
            joins += 1
    assert joins >= 8


def test_a_finite_move_restarts_on_its_own_frame_every_cycle() -> None:
    """A finite move restarts by design, so on a drifting grid each cycle's move is
    measured from its own first frame, whatever its distance from the previous cycle's:
    no phase carries over."""
    grid = _grid(4, 340.0, 420.0, seconds=20.0)
    phase_map = build_musical_phase_map(grid)
    sweep = loop_template_doc("p3_sweep", [sweep_step("go", 0.0, 30.0, period_beats=4.0)])
    rig, job = p1_rig(), p1_job()
    with registered_templates(sweep):
        _, segments = _render([("p3_sweep", None, 1, 10)], grid, rig, job, None)
    cues = [
        cue
        for cue in segments
        if cue.fixture_id == "MH1" and TRANSACTION_METADATA_KEY not in cue.metadata
    ]
    assert len(cues) >= 4  # those its jump back leaves unplayable are kept dark
    for cue in cues:
        points = cue.channels[ChannelName.PAN].physical.points
        phase = musical_phase_fraction(
            phase_map, points[1].t_ms, origin_ms=cue.t0_ms, period_beats=4.0
        )
        assert points[0].value == 0.0, cue.t0_ms
        assert points[1].value == 30.0 * (phase.numerator / phase.denominator), cue.t0_ms


def test_a_pulse_continues_its_phase_on_a_step_whose_move_restarts() -> None:
    """A finite move restarts every cycle, but a dimmer pulse on the same step, whose
    whole periods the cycle holds, continues one phase across cycles like any pulse:
    its levels are those of the same pulse on a periodic step."""
    grid = _grid(4, 340.0, 420.0, seconds=20.0)
    pulse = {"period_beats": 1.0, "duty_cycle": 0.5, "low": 0.0, "high": 1.0}
    finite = sweep_step("go", 0.0, 0.0, period_beats=4.0)
    periodic = sine_step("go", 0.0, 0.0, period_beats=4.0)
    for step in (finite, periodic):
        step["dimmer"] = pulse
    docs = [
        loop_template_doc("p3_pulse_finite", [finite]),
        loop_template_doc("p3_pulse_periodic", [periodic]),
    ]
    rig, job = p1_rig(), p1_job()
    levels = []
    with registered_templates(*docs):
        for doc in docs:
            _, segments = _render([(doc.template.template_id, None, 1, 12)], grid, rig, job, None)
            levels.append(
                [
                    (cue.t0_ms, cue.channels[ChannelName.DIMMER].physical)
                    for cue in segments
                    if cue.fixture_id == "MH1" and TRANSACTION_METADATA_KEY not in cue.metadata
                ]
            )
    assert len(levels[0]) >= 8
    assert levels[0] == levels[1]


# --- The floor --------------------------------------------------------------------------

_FLOOR = {
    (150.0, 50.0): set(FAMILY_IDS),
    (150.0, 120.0): set(FAMILY_IDS),
    (150.0, 180.0): set(FAMILY_IDS),
    (150.0, 200.0): {
        "finite_snap_hold",
        "target_orbit",
        "fly_in_cascade",
        "fly_out_cascade",
        "mirror_wings",
    },
    (90.0, 150.0): {"finite_snap_hold", "target_orbit", "masked_wheel_flick", "mirror_wings"},
    (90.0, 200.0): {"finite_snap_hold", "target_orbit"},
}
"""Per (head speed in °/s, tempo in BPM), the families every meter must admit."""


@pytest.mark.slow
@pytest.mark.parametrize("beats_per_bar", [3, 4])
@pytest.mark.parametrize(("speed", "bpm"), list(_FLOOR), ids=lambda value: f"{value:g}")
def test_a_four_head_rig_is_offered_a_floor_of_families(
    beats_per_bar: int, speed: float, bpm: float
) -> None:
    """Beats jittered by 8% over 30 s, in 4/4 and 3/4. At 150°/s every zoomless family
    plays from 50 to 180 BPM, and at 200 BPM all but the flick; at 90°/s the snap, the
    orbit, the flick and the wings play at 150 BPM, every energy, and the snap and the
    orbit at 200 BPM. No variant is declared slower than these."""
    grid = _tempo_grid(beats_per_bar, bpm, seconds=30.0)
    with family_catalog():
        admission = _gate(grid, _rig(speed), family_job(HEADS))
        energies = {get_template(t).template.category.value for t in admission.admitted}

    assert _FLOOR[speed, bpm] <= set(admission.admitted), admission.exclusions
    if bpm < 200.0 or speed >= 150.0:
        assert energies == {"low_energy", "medium_energy", "high_energy"}
